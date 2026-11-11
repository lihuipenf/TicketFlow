"""Durable single-owner worker. Run python -m app.worker."""
from datetime import timedelta
from threading import Event, Thread
from pathlib import Path
import time
from filelock import FileLock
from sqlalchemy import select, or_, and_, update
from openai import APITimeoutError, RateLimitError, APIConnectionError
from app.db import Session, Job, Ticket, Order, Version, Audit, now, uid
from app.config import settings
from app import services, policy, llm


def claim(db, owner):
    job = db.scalar(select(Job).where(or_(Job.state == 'queued', and_(Job.state == 'running', Job.lease_until < now())))
                    .where(Job.attempts < 3).order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
    if job:
        job.state = 'running'
        job.owner = owner
        job.lease_until = now() + timedelta(minutes=3)
        job.attempts += 1
        job.error = None
        db.commit()
    return job


def execute(db, job, index):
    config = job.payload.get('config', services.DEFAULT_CONFIG)
    job.steps = []
    def stage(name, started, detail):
        job.steps = [*job.steps, {'name': name, 'duration_ms': round((time.perf_counter() - started) * 1000), 'detail': detail}]
        db.commit()
    try:
        if job.kind == 'ingest':
            start = time.perf_counter()
            result = index.ingest(db, job.resource_id, config)
            stage('解析 → 切块 → 向量化 → 双索引', start, {'chunks': result['chunk_count']})
        elif job.kind == 'retrieval':
            start = time.perf_counter()
            result = index.search(db, job.payload['query'], config)
            stage('混合检索', start, {'hits': len(result['hits'])})
        elif job.kind == 'ticket':
            ticket = db.get(Ticket, job.resource_id)
            if not ticket or ticket.revision != job.payload['revision']:
                raise ValueError('工单已更新，本次任务失效')
            start = time.perf_counter()
            cleaned = policy.redact(ticket.content)
            stage('清洗脱敏', start, {'characters': len(cleaned)})
            start = time.perf_counter()
            label = policy.classify(cleaned, config.get('urgent_words'))
            ticket.intent, ticket.priority = label['intent'], label['priority']
            stage('意图与优先级', start, label)
            start = time.perf_counter()
            order = db.get(Order, ticket.order_id) if ticket.order_id else None
            if order and order.customer_id != ticket.customer_id:
                raise ValueError('订单归属不匹配')
            facts = {'status': order.status, 'product': order.product, 'amount_cents': order.amount_cents, **order.facts} if order else {}
            order_revision = order.revision if order else None
            stage('订单只读查询', start, {'found': bool(order)})
            start = time.perf_counter()
            retrieval = index.search(db, cleaned, config)
            job.result = {'retrieval': retrieval, 'classification': label}
            stage('向量 + BM25 + RRF', start, {'hits': len(retrieval['hits']), 'duration_ms': retrieval['duration_ms']})
            start = time.perf_counter()
            answer = llm.generate(cleaned, retrieval['hits'], facts)
            stage('模型生成与引用校验', start, {'model': answer['model'], 'usage': answer['usage'], 'risk_flags': answer['risk_flags']})
            db.commit()
            ticket = db.scalar(select(Ticket).where(Ticket.id == job.resource_id).with_for_update().execution_options(populate_existing=True))
            if ticket.revision != job.payload['revision']:
                raise ValueError('生成期间工单已更新，结果未覆盖新版本')
            answer.update(order_revision=order_revision, versions=retrieval['versions'], config_revision=config.get('revision', 0), job_id=job.id)
            ticket.draft = answer
            ticket.approved_text = None
            ticket.approved_revision = None
            ticket.status = 'pending_review'
            ticket.revision += 1
            result = {**job.result, 'answer': answer}
            services.audit(db, 'worker', 'draft.generated', ticket.id, {'job_id': job.id})
        else:
            raise ValueError('未知任务类型')
        job.state, job.result, job.finished_at = 'succeeded', result, now()
        job.lease_until = None
        db.commit()
    except Exception as exc:
        db.rollback()
        job = db.get(Job, job.id)
        transient = isinstance(exc, (APITimeoutError, RateLimitError, APIConnectionError))
        job.state = 'queued' if transient and job.attempts < 3 else 'failed'
        # Never persist raw upstream errors (may include prompts, keys, headers).
        job.error = policy.redact(str(exc))[:500] if isinstance(exc, llm.ModelNotConfigured) or type(exc) is ValueError else f'{type(exc).__name__}：处理失败，请检查配置及依赖'
        job.finished_at = now() if job.state == 'failed' else None
        job.lease_until = None
        if job.kind == 'ingest':
            version = db.get(Version, job.resource_id)
            version.state, version.error = 'failed', job.error
        db.commit()


def heartbeat(stop, job_id, owner):
    while not stop.wait(20):
        with Session() as db:
            db.execute(update(Job).where(Job.id == job_id, Job.owner == owner, Job.state == 'running')
                       .values(lease_until=now() + timedelta(minutes=3)))
            db.commit()


def main():
    from app.rag import Index
    settings().storage.mkdir(parents=True, exist_ok=True)
    owner = uid()
    with FileLock(str(settings().storage / 'worker.lock'), timeout=0):
        index = Index()
        print('TicketFlow Worker ready', flush=True)
        try:
            while True:
                with Session() as db:
                    # Interrupted final attempts are terminal instead of remaining stuck forever.
                    db.execute(update(Job).where(Job.state == 'running', Job.lease_until < now(), Job.attempts >= 3)
                               .values(state='failed', error='任务中断且达到重试上限', finished_at=now()))
                    db.commit()
                    job = claim(db, owner)
                    if job:
                        stop = Event()
                        thread = Thread(target=heartbeat, args=(stop, job.id, owner), daemon=True)
                        thread.start()
                        try:
                            execute(db, job, index)
                        finally:
                            stop.set(); thread.join(timeout=5)
                    else:
                        time.sleep(1)
        finally:
            index.close()


if __name__ == '__main__':
    main()

from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, func, or_, text
from sqlalchemy.orm import Session
from app.db import session, Ticket, Order, User, Document, Version, Chunk, Job, Audit, WorkflowConfig, now, uid
from app.auth import current_user, require, login
from app import services
from app.config import settings
from app.policy import redact

router = APIRouter(prefix='/api/v1')
staff = require('admin', 'supervisor', 'agent')
managers = require('admin', 'supervisor')
knowledge_staff = require('admin', 'supervisor', 'knowledge')


def serialize(row, exclude=()):
    return {c.name: getattr(row, c.name) for c in row.__table__.columns if c.name not in exclude}


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=200)


class TicketBody(BaseModel):
    subject: str = Field(min_length=1, max_length=180)
    content: str = Field(min_length=1, max_length=8000)
    customer_id: str = Field(min_length=1, max_length=40, pattern=r'^[A-Za-z0-9_-]+$')
    order_id: str | None = Field(default=None, max_length=40)


class RevisionBody(BaseModel):
    revision: int = Field(ge=1)


class ReviewBody(RevisionBody):
    action: Literal['approve', 'reject', 'escalate', 'request_information']
    text: str = Field(default='', max_length=6000)


class RetrievalBody(BaseModel):
    query: str = Field(min_length=1, max_length=2000)


class ConfigBody(BaseModel):
    vector_top_k: int = Field(default=20, ge=1, le=100)
    bm25_top_k: int = Field(default=20, ge=1, le=100)
    context_top_k: int = Field(default=6, ge=1, le=12)
    chunk_chars: int = Field(default=1100, ge=200, le=1800)
    overlap_chars: int = Field(default=100, ge=0, le=500)
    context_chars: int = Field(default=6500, ge=1000, le=12000)
    min_similarity: float = Field(default=0.4, ge=0, le=1)
    urgent_words: list[str] = Field(default=['投诉', '超时', '逾期', '紧急', '三天没发货'], max_length=30)

    @model_validator(mode='after')
    def validate_overlap(self):
        if self.overlap_chars >= self.chunk_chars:
            raise ValueError('重叠长度必须小于切块长度')
        if any(not word.strip() or len(word) > 40 for word in self.urgent_words):
            raise ValueError('优先级关键词须为 1 至 40 字符')
        return self


@router.post('/auth/login')
def auth_login(body: LoginBody, db: Session = Depends(session)):
    return login(db, body.username, body.password)


@router.get('/auth/me')
def me(user=Depends(current_user)):
    return serialize(user, ('password_hash',))


@router.get('/system/status')
def system_status(user=Depends(current_user), db: Session = Depends(session)):
    db.execute(text('SELECT 1'))
    return {'database': 'connected', 'llm_configured': bool(settings().llm_api_key.get_secret_value()),
            'model': settings().llm_model, 'provider': settings().llm_provider,
            'embedding': settings().embedding_model, 'channel': '模拟客服渠道'}


@router.get('/tickets')
def list_tickets(q: str = '', status: str = '', priority: str = '', intent: str = '', page: int = Query(1, ge=1),
                 page_size: int = Query(20, ge=1, le=100), user=Depends(staff), db: Session = Depends(session)):
    stmt = select(Ticket)
    if user.role == 'agent':
        stmt = stmt.where(Ticket.assignee == user.id)
    for column, value in ((Ticket.status, status), (Ticket.priority, priority), (Ticket.intent, intent)):
        if value:
            stmt = stmt.where(column == value)
    if q:
        stmt = stmt.where(or_(Ticket.subject.contains(q, autoescape=True), Ticket.content.contains(q, autoescape=True), Ticket.id == q))
    count = db.scalar(select(func.count()).select_from(stmt.subquery()))
    items = db.scalars(stmt.order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size))
    return {'items': [serialize(t, ('draft', 'approved_text', 'sent_text')) for t in items], 'total': count}


@router.post('/tickets', status_code=201)
def create_ticket(body: TicketBody, user=Depends(staff), db: Session = Depends(session)):
    return serialize(services.create_ticket(db, user, body.model_dump()))


@router.get('/tickets/{ticket_id}')
def get_ticket(ticket_id: str, user=Depends(staff), db: Session = Depends(session)):
    ticket = services.access_ticket(db, user, ticket_id)
    jobs = db.scalars(select(Job).where(Job.resource_id == ticket_id).order_by(Job.created_at.desc()).limit(10))
    events = db.scalars(select(Audit).where(Audit.resource_id == ticket_id).order_by(Audit.created_at.desc()).limit(30))
    return {**serialize(ticket), 'order': serialize(db.get(Order, ticket.order_id)) if ticket.order_id else None,
            'runs': [serialize(j) for j in jobs], 'events': [serialize(e) for e in events]}


@router.post('/tickets/{ticket_id}/runs', status_code=202)
def run_ticket(ticket_id: str, body: RevisionBody, user=Depends(staff), db: Session = Depends(session)):
    ticket = services.access_ticket(db, user, ticket_id, lock=True)
    if ticket.revision != body.revision or ticket.status in ('replied', 'closed'):
        raise HTTPException(409, '工单已更新或已回复，请刷新')
    job = services.enqueue(db, 'ticket', {'revision': ticket.revision, 'config': services.config_snapshot(db), 'actor_id': user.id},
                           f'ticket:{ticket.id}:{ticket.revision}', ticket.id)
    return serialize(job)


@router.post('/tickets/{ticket_id}/reviews')
def review(ticket_id: str, body: ReviewBody, user=Depends(staff), db: Session = Depends(session)):
    return serialize(services.review(db, user, ticket_id, body.revision, body.action, body.text))


@router.post('/tickets/{ticket_id}/send')
def send(ticket_id: str, body: RevisionBody, user=Depends(staff), db: Session = Depends(session)):
    return serialize(services.send_reply(db, user, ticket_id, body.revision))


class AssignBody(BaseModel):
    ticket_ids: list[str] = Field(min_length=1, max_length=100)
    user_id: str


@router.post('/tickets/assign/batch')
def assign(body: AssignBody, user=Depends(managers), db: Session = Depends(session)):
    target = db.get(User, body.user_id)
    if not target or target.role not in ('agent', 'supervisor', 'admin'):
        raise HTTPException(422, '无效客服账号')
    for ticket_id in body.ticket_ids:
        ticket = services.access_ticket(db, user, ticket_id, lock=True)
        ticket.assignee = target.id
        ticket.revision += 1
        ticket.approved_text = None
        ticket.approved_revision = None
        if ticket.status == 'approved':
            ticket.status = 'pending_review'
        services.audit(db, user.username, 'ticket.assigned', ticket.id, {'assignee': target.username})
    db.commit()
    return {'updated': len(body.ticket_ids)}


@router.get('/users')
def users(user=Depends(managers), db: Session = Depends(session)):
    return [serialize(u, ('password_hash',)) for u in db.scalars(select(User))]


@router.get('/orders')
def orders(q: str = '', user=Depends(managers), db: Session = Depends(session)):
    stmt = select(Order)
    if q:
        stmt = stmt.where(or_(Order.id.contains(q, autoescape=True), Order.customer_id == q))
    return [serialize(o) for o in db.scalars(stmt.order_by(Order.id).limit(100))]


@router.get('/orders/{order_id}')
def order(order_id: str, user=Depends(staff), db: Session = Depends(session)):
    return serialize(services.access_order(db, user, order_id))


@router.get('/knowledge/documents')
def documents(user=Depends(current_user), db: Session = Depends(session)):
    docs = db.scalars(select(Document).order_by(Document.created_at.desc()))
    return [{**serialize(d), 'versions': [serialize(v, ('path',)) for v in db.scalars(select(Version).where(Version.document_id == d.id).order_by(Version.created_at.desc()))]} for d in docs]


@router.post('/knowledge/documents', status_code=202)
async def upload(file: UploadFile = File(), document_id: str | None = Form(None), user=Depends(knowledge_staff), db: Session = Depends(session)):
    raw = await file.read(10 * 1024 * 1024 + 1)
    version = services.upload(db, user.username, file.filename or 'document.txt', raw, document_id)
    return serialize(version, ('path',))


@router.get('/knowledge/versions/{version_id}/chunks')
def chunks(version_id: str, user=Depends(current_user), db: Session = Depends(session)):
    return [serialize(c) for c in db.scalars(select(Chunk).where(Chunk.version_id == version_id).limit(500))]


@router.post('/knowledge/versions/{version_id}/publish')
def publish(version_id: str, user=Depends(knowledge_staff), db: Session = Depends(session)):
    return serialize(services.publish(db, version_id, user.username))


@router.post('/knowledge/documents/{document_id}/disable')
def disable(document_id: str, user=Depends(knowledge_staff), db: Session = Depends(session)):
    doc = db.get(Document, document_id)
    if not doc:
        raise HTTPException(404, '文档不存在')
    doc.active_version = None
    services.audit(db, user.username, 'knowledge.disabled', doc.id)
    db.commit()
    return serialize(doc)


@router.post('/retrieval-tests', status_code=202)
def retrieval(body: RetrievalBody, user=Depends(current_user), db: Session = Depends(session)):
    return serialize(services.enqueue(db, 'retrieval', {'query': redact(body.query), 'config': services.config_snapshot(db), 'actor_id': user.id}, uid()))


@router.get('/jobs/{job_id}')
def get_job(job_id: str, user=Depends(current_user), db: Session = Depends(session)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(404, '任务不存在')
    if job.kind == 'ticket':
        services.access_ticket(db, user, job.resource_id)
    elif user.role not in ('admin', 'supervisor', 'knowledge') and job.payload.get('actor_id') != user.id:
        raise HTTPException(403, '无权读取此任务')
    return serialize(job)


@router.post('/jobs/{job_id}/retry', status_code=202)
def retry(job_id: str, user=Depends(current_user), db: Session = Depends(session)):
    get_job(job_id, user, db)
    job = db.scalar(select(Job).where(Job.id == job_id).with_for_update())
    if job.state != 'failed':
        raise HTTPException(409, '仅失败任务可以重试')
    job.state, job.attempts, job.error = 'queued', 0, None
    services.audit(db, user.username, 'job.retried', job.id)
    db.commit()
    return serialize(job)


@router.get('/workflow/config')
def config(user=Depends(current_user), db: Session = Depends(session)):
    return services.config_snapshot(db)


@router.put('/workflow/config')
def save_config(body: ConfigBody, user=Depends(managers), db: Session = Depends(session)):
    row = WorkflowConfig(config=body.model_dump())
    db.add(row); db.flush()
    services.audit(db, user.username, 'workflow.configured', str(row.id))
    db.commit()
    return services.config_snapshot(db)


@router.get('/analytics/overview')
def analytics(user=Depends(staff), db: Session = Depends(session)):
    ticket_scope = [] if user.role != 'agent' else [Ticket.assignee == user.id]
    counts = dict(db.execute(select(Ticket.status, func.count()).where(*ticket_scope).group_by(Ticket.status)).all())
    priorities = dict(db.execute(select(Ticket.priority, func.count()).where(*ticket_scope).group_by(Ticket.priority)).all())
    intents = dict(db.execute(select(Ticket.intent, func.count()).where(*ticket_scope).group_by(Ticket.intent)).all())
    job_query = select(Job).order_by(Job.created_at.desc()).limit(100)
    if user.role == 'agent':
        job_query = job_query.where(Job.resource_id.in_(select(Ticket.id).where(*ticket_scope)))
    jobs = list(db.scalars(job_query))
    succeeded = sum(j.state == 'succeeded' for j in jobs)
    failed = sum(j.state == 'failed' for j in jobs)
    durations = [sum(s['duration_ms'] for s in j.steps) for j in jobs if j.state == 'succeeded']
    token_total = sum((j.result or {}).get('answer', {}).get('usage', {}).get('total_tokens', 0) for j in jobs)
    return {'total': sum(counts.values()), 'statuses': counts, 'priorities': priorities, 'intents': intents,
            'jobs_succeeded': succeeded, 'jobs_failed': failed, 'success_rate': round(100 * succeeded / (succeeded + failed), 1) if succeeded + failed else None,
            'mean_duration_ms': round(sum(durations) / len(durations)) if durations else None,
            'tokens': token_total, 'sample_note': '运行指标基于最近100个任务；工单统计为全部可见工单'}


@router.get('/runs')
def runs(page: int = Query(1, ge=1), user=Depends(managers), db: Session = Depends(session)):
    total = db.scalar(select(func.count()).select_from(Job))
    rows = db.scalars(select(Job).order_by(Job.created_at.desc()).offset((page - 1) * 20).limit(20))
    return {'items': [serialize(j) for j in rows], 'total': total}


@router.get('/audit-events')
def audit_events(user=Depends(managers), db: Session = Depends(session)):
    return [serialize(e) for e in db.scalars(select(Audit).order_by(Audit.created_at.desc()).limit(100))]

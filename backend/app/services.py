"""Transactional business services."""
from pathlib import Path
from hashlib import sha256
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.db import Ticket, Order, Job, Audit, Document, Version, WorkflowConfig, uid
from app.config import settings
from app.policy import redact, classify

DEFAULT_CONFIG = {'vector_top_k': 20, 'bm25_top_k': 20, 'context_top_k': 6,
    'chunk_chars': 1100, 'overlap_chars': 100, 'context_chars': 6500,
    'min_similarity': 0.4, 'urgent_words': ['投诉', '超时', '逾期', '紧急', '三天没发货']}


def config_snapshot(db):
    config = db.scalar(select(WorkflowConfig).order_by(WorkflowConfig.id.desc()).limit(1))
    return {'revision': config.id if config else 0, **(config.config if config else DEFAULT_CONFIG)}


def audit(db, actor, action, resource_id, detail=None):
    db.add(Audit(actor=actor, action=action, resource_id=resource_id, detail=detail or {}))


def access_ticket(db, user, ticket_id, lock=False):
    stmt = select(Ticket).where(Ticket.id == ticket_id)
    if lock:
        stmt = stmt.with_for_update()
    ticket = db.scalar(stmt)
    if ticket is None:
        raise HTTPException(404, '工单不存在')
    if user.role not in ('admin', 'supervisor') and ticket.assignee != user.id:
        raise HTTPException(403, '只能访问分配给自己的工单')
    return ticket


def access_order(db, user, order_id):
    if user.role not in ('admin', 'supervisor'):
        if user.role != 'agent' or not db.scalar(select(Ticket.id).where(
                Ticket.order_id == order_id, Ticket.assignee == user.id).limit(1)):
            raise HTTPException(403, '无关联工单访问权限，请由主管接入订单并分派')
    order = db.get(Order, order_id)
    if not order:
        raise HTTPException(404, '订单不存在')
    return order


def create_ticket(db, user, data):
    if data.get('order_id'):
        # Authorize BEFORE this new ticket can itself become an access relationship.
        order = access_order(db, user, data['order_id'])
        if order.customer_id != data['customer_id']:
            raise HTTPException(403, '订单与客户不匹配')
    cleaned = redact(data['content'])
    label = classify(cleaned)
    ticket = Ticket(subject=redact(data['subject']), content=cleaned, customer_id=data['customer_id'],
                    order_id=data.get('order_id'), assignee=user.id, priority=label['priority'], intent=label['intent'])
    db.add(ticket); db.flush()
    audit(db, user.username, 'ticket.created', ticket.id)
    db.commit()
    return ticket


def enqueue(db, kind, payload, key, resource_id=None):
    existing = db.scalar(select(Job).where(Job.idempotency_key == key))
    if existing:
        return existing
    job = Job(kind=kind, payload=payload, idempotency_key=key, resource_id=resource_id)
    try:
        with db.begin_nested():
            db.add(job); db.flush()
    except IntegrityError:
        return db.scalar(select(Job).where(Job.idempotency_key == key))
    db.commit()
    return job


def check_draft_fresh(db, ticket):
    draft = ticket.draft or {}
    if ticket.order_id:
        order = db.scalar(select(Order).where(Order.id == ticket.order_id).with_for_update().execution_options(populate_existing=True))
        if order.revision != draft.get('order_revision'):
            raise HTTPException(409, '订单已变化，请重新生成并审核')
    # Locking reads bypass REPEATABLE READ snapshots and hold dependency locks through send/approval.
    # All documents are locked, including disabled ones, to serialize reactivation/publication.
    documents = db.scalars(select(Document).order_by(Document.id).with_for_update().execution_options(populate_existing=True))
    active = {document.active_version for document in documents if document.active_version}
    if set(draft.get('versions', [])) != active:
        raise HTTPException(409, '知识库已变化，请重新生成并审核')


def review(db, user, ticket_id, revision, action, text):
    ticket = access_ticket(db, user, ticket_id, lock=True)
    if ticket.revision != revision:
        raise HTTPException(409, '工单已被更新，请刷新')
    if ticket.status not in ('pending_review', 'escalated', 'needs_information') or not ticket.draft:
        raise HTTPException(409, '当前工单没有可审核草稿')
    if action == 'approve':
        check_draft_fresh(db, ticket)
        if not text or not text.strip():
            raise HTTPException(422, '回复不能为空')
        if ticket.priority == 'P0' and user.role not in ('admin', 'supervisor'):
            raise HTTPException(403, 'P0 工单须由主管确认')
        if '疑似未经授权的资金或时效承诺' in (ticket.draft.get('risk_flags') or []) and user.role not in ('admin', 'supervisor'):
            raise HTTPException(403, '高风险回复须由主管审核')
        from app.policy import validate_answer
        if '疑似未经授权的资金或时效承诺' in validate_answer({'reply_text': text}, [])['risk_flags']:
            raise HTTPException(422, '请移除未经执行的退款或绝对时效承诺')
        ticket.approved_text = redact(text)
        ticket.status = 'approved'
        ticket.approved_revision = revision + 1
    elif action in ('escalate', 'request_information', 'reject'):
        ticket.status = {'escalate': 'escalated', 'request_information': 'needs_information', 'reject': 'new'}[action]
        ticket.approved_text = None
        ticket.approved_revision = None
    else:
        raise HTTPException(422, '未知审核动作')
    ticket.revision += 1
    audit(db, user.username, 'review.' + action, ticket.id, {'revision': ticket.revision, 'edited_reply': redact(text) if text else None})
    db.commit()
    return ticket


def send_reply(db, user, ticket_id, revision):
    ticket = access_ticket(db, user, ticket_id, lock=True)
    if ticket.status == 'replied' and ticket.sent_text:
        return ticket
    if ticket.revision != revision or ticket.status != 'approved' or ticket.approved_revision != revision:
        raise HTTPException(409, '请先确认当前版本的回复')
    check_draft_fresh(db, ticket)
    ticket.sent_text = ticket.approved_text
    ticket.status = 'replied'
    ticket.revision += 1
    audit(db, user.username, 'reply.sent_to_simulator', ticket.id)
    db.commit()
    return ticket


def upload(db, actor, filename, raw, document_id=None):
    filename = Path(filename.replace('\\', '/')).name
    if Path(filename).suffix.lower() not in ('.pdf', '.md', '.txt'):
        raise HTTPException(415, '仅支持 PDF、Markdown、TXT')
    if not raw or len(raw) > 10 * 1024 * 1024:
        raise HTTPException(413, '文档须为 1 字节至 10 MB')
    if len(filename) > 180:
        raise HTTPException(422, '文件名过长')
    doc = db.get(Document, document_id) if document_id else Document(name=filename)
    if not doc:
        raise HTTPException(404, '文档不存在')
    db.add(doc); db.flush()
    checksum = sha256(raw).hexdigest()
    existing = db.scalar(select(Version).where(Version.document_id == doc.id, Version.checksum == checksum))
    if existing:
        return existing
    version_id = uid()
    directory = settings().storage / 'uploads'
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (version_id + Path(filename).suffix.lower())
    target.write_bytes(raw)
    version = Version(id=version_id, document_id=doc.id, filename=filename, path=str(target), checksum=checksum)
    db.add(version)
    audit(db, actor, 'knowledge.uploaded', version.id)
    db.flush()
    enqueue(db, 'ingest', {'config': config_snapshot(db)}, 'ingest:' + version.id, version.id)
    return version


def publish(db, version_id, actor):
    version = db.get(Version, version_id)
    if not version:
        raise HTTPException(404, '知识版本不存在')
    if version.state not in ('ready', 'published') or not Path(version.index_meta.get('lexical_path', '_missing_')).is_file():
        raise HTTPException(409, '索引尚未构建完成')
    doc = db.scalar(select(Document).where(Document.id == version.document_id).with_for_update())
    previous = doc.active_version
    doc.active_version = version.id
    version.state = 'published'
    audit(db, actor, 'knowledge.published', doc.id, {'from': previous, 'to': version.id})
    db.commit()
    return doc

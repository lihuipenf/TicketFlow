from datetime import datetime, timezone
from uuid import uuid4
from sqlalchemy import create_engine, String, Text, JSON, DateTime, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from app.config import settings


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def uid():
    return uuid4().hex


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(30), default='agent')


class Order(Base):
    __tablename__ = 'orders'
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(40), index=True)
    product: Mapped[str] = mapped_column(String(120))
    amount_cents: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(30))
    facts: Mapped[dict] = mapped_column(JSON, default=dict)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Ticket(Base):
    __tablename__ = 'tickets'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    subject: Mapped[str] = mapped_column(String(180))
    content: Mapped[str] = mapped_column(Text)
    customer_id: Mapped[str] = mapped_column(String(40), index=True)
    order_id: Mapped[str | None] = mapped_column(ForeignKey('orders.id'))
    status: Mapped[str] = mapped_column(String(30), default='new', index=True)
    priority: Mapped[str] = mapped_column(String(3), default='P2', index=True)
    intent: Mapped[str] = mapped_column(String(40), default='其他')
    assignee: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    revision: Mapped[int] = mapped_column(Integer, default=1)
    draft: Mapped[dict | None] = mapped_column(JSON)
    approved_text: Mapped[str | None] = mapped_column(Text)
    approved_revision: Mapped[int | None] = mapped_column(Integer)
    sent_text: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class Document(Base):
    __tablename__ = 'knowledge_documents'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(180))
    active_version: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Version(Base):
    __tablename__ = 'document_versions'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    document_id: Mapped[str] = mapped_column(ForeignKey('knowledge_documents.id'), index=True)
    filename: Mapped[str] = mapped_column(String(180))
    path: Mapped[str] = mapped_column(Text)
    checksum: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(30), default='queued')
    index_meta: Mapped[dict] = mapped_column(JSON, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Chunk(Base):
    __tablename__ = 'knowledge_chunks'
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version_id: Mapped[str] = mapped_column(ForeignKey('document_versions.id'), index=True)
    content: Mapped[str] = mapped_column(Text)
    source: Mapped[dict] = mapped_column(JSON)


class Job(Base):
    __tablename__ = 'jobs'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    kind: Mapped[str] = mapped_column(String(30))
    resource_id: Mapped[str | None] = mapped_column(String(64))
    idempotency_key: Mapped[str] = mapped_column(String(180), unique=True)
    state: Mapped[str] = mapped_column(String(30), default='queued', index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict | None] = mapped_column(JSON)
    steps: Mapped[list] = mapped_column(JSON, default=list)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    lease_until: Mapped[datetime | None] = mapped_column(DateTime)
    owner: Mapped[str | None] = mapped_column(String(32))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Audit(Base):
    __tablename__ = 'audit_events'
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=uid)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now, index=True)


class WorkflowConfig(Base):
    __tablename__ = 'workflow_configs'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


engine = create_engine(settings().database_url.get_secret_value(), pool_pre_ping=True, pool_recycle=1800)
Session = sessionmaker(engine, expire_on_commit=False)


def session():
    with Session() as db:
        yield db

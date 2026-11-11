from datetime import timedelta
from app import worker, services
from app.db import Job, now, uid


def test_claim_recovers_expired_lease_but_not_active_job(db):
    active = Job(kind='retrieval', idempotency_key=uid(), state='running', lease_until=now() + timedelta(minutes=5), owner='other')
    expired = Job(kind='retrieval', idempotency_key=uid(), state='running', lease_until=now() - timedelta(seconds=5), owner='dead')
    db.add_all([active, expired]); db.flush()
    claimed = worker.claim(db, 'new-owner')
    assert claimed.id == expired.id
    assert claimed.owner == 'new-owner'
    assert active.owner == 'other'


def test_job_persists_failure_when_model_not_configured(db):
    from app.db import Ticket, User
    from app.config import settings
    from pydantic import SecretStr
    user = User(username=uid(), password_hash='unused', role='admin')
    db.add(user); db.flush()
    ticket = Ticket(subject='退款', content='退款', customer_id='C1', assignee=user.id)
    db.add(ticket); db.flush()
    job = services.enqueue(db, 'ticket', {'revision': ticket.revision, 'config': services.DEFAULT_CONFIG}, uid(), ticket.id)
    class EmptyIndex:
        def search(self, db, query, config):
            return {'hits': [], 'versions': [], 'duration_ms': 1}
    worker.execute(db, job, EmptyIndex())
    assert job.state == 'failed'
    assert 'LLM_API_KEY' in job.error
    assert ticket.draft is None

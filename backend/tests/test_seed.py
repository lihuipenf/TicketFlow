from sqlalchemy import select, func
from app import seed
from app.db import Ticket, Order, Document
from app.db import User
from app.auth import passwords
import os
import pytest


def test_seed_counts_relationships_and_repeated_runs(db):
    seed.populate(db)
    seed.populate(db)
    assert db.scalar(select(func.count()).select_from(Order).where(Order.id.like('TF2026%'))) == 50
    assert db.scalar(select(func.count()).select_from(Ticket).where(Ticket.id.like('seed%'))) == 500
    assert len(seed.FAQS) == 20
    rows = db.execute(select(Ticket.customer_id, Order.customer_id).join(Order, Ticket.order_id == Order.id).where(Ticket.id.like('seed%'))).all()
    assert len(rows) == 500
    assert all(customer == owner for customer, owner in rows)


def test_seed_users_each_accept_only_their_own_configured_password(db):
    seed.populate(db)
    credentials = {role: os.environ[role.upper() + '_PASSWORD']
                   for role in ('admin', 'supervisor', 'agent', 'knowledge')}
    for role, password in credentials.items():
        user = db.scalar(select(User).where(User.username == role))
        assert passwords.verify(password, user.password_hash)
        for other_role, other_password in credentials.items():
            if other_role != role:
                assert not passwords.verify(other_password, user.password_hash)


def test_reseeding_replaces_existing_legacy_shared_passwords(db):
    for role in ('admin', 'supervisor', 'agent', 'knowledge'):
        db.add(User(username=role, role=role, password_hash=passwords.hash('legacy-shared-password')))
    db.flush()
    seed.populate(db)
    for role in ('admin', 'supervisor', 'agent', 'knowledge'):
        user = db.scalar(select(User).where(User.username == role))
        assert not passwords.verify('legacy-shared-password', user.password_hash)
        assert passwords.verify(os.environ[role.upper() + '_PASSWORD'], user.password_hash)


@pytest.mark.parametrize('bad_password', ['', 'CHANGE_ME_AT_LEAST_12_CHARACTERS', 'test-only-admin-password'])
def test_seed_rejects_missing_placeholder_or_duplicate_role_password_before_writes(db, monkeypatch, bad_password):
    from app.config import settings
    from pydantic import SecretStr
    monkeypatch.setattr(settings(), 'agent_password', SecretStr(bad_password))
    with pytest.raises(ValueError):
        seed.populate(db)
    assert db.scalar(select(func.count()).select_from(User)) == 0

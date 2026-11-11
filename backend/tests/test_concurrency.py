import pytest
from fastapi import HTTPException
from sqlalchemy import select, text, update
from sqlalchemy.exc import OperationalError
from app.db import Session, Document, Ticket, Order, User, uid
from app.services import check_draft_fresh


def test_freshness_uses_current_knowledge_not_mysql_snapshot():
    key, old, new = uid(), uid(), uid()
    with Session() as setup:
        doc = Document(id=key, name='concurrency-test', active_version=old)
        setup.add(doc); setup.commit()
    try:
        with Session() as first, Session() as second:
            first.execute(select(User)).all()  # Authentication establishes a repeatable-read snapshot.
            second.execute(update(Document).where(Document.id == key).values(active_version=new))
            second.commit()
            ticket = Ticket(draft={'versions': [old]}, customer_id='test', subject='test', content='test')
            with pytest.raises(HTTPException) as exc:
                check_draft_fresh(first, ticket)
            assert exc.value.status_code == 409
    finally:
        with Session() as cleanup:
            cleanup.execute(update(Document).where(Document.id == key).values(active_version=None))
            cleanup.commit()


def test_order_cannot_change_between_freshness_check_and_commit():
    key = uid()
    with Session() as setup:
        setup.add(Order(id=key, customer_id='test', product='test', amount_cents=1, status='paid', revision=1))
        setup.commit()
    with Session() as first, Session() as second:
        ticket = Ticket(order_id=key, draft={'order_revision': 1, 'versions': []}, customer_id='test', subject='test', content='test')
        check_draft_fresh(first, ticket)
        second.execute(text('SET SESSION innodb_lock_wait_timeout=1'))
        with pytest.raises(OperationalError) as exc:
            second.execute(update(Order).where(Order.id == key).values(revision=2))
        assert exc.value.orig.args[0] == 1205
        second.rollback()
        first.rollback()

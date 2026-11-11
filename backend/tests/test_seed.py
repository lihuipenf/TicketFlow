from sqlalchemy import select, func
from app import seed
from app.db import Ticket, Order, Document


def test_seed_counts_relationships_and_repeated_runs(db):
    seed.populate(db)
    seed.populate(db)
    assert db.scalar(select(func.count()).select_from(Order).where(Order.id.like('TF2026%'))) == 50
    assert db.scalar(select(func.count()).select_from(Ticket).where(Ticket.id.like('seed%'))) == 500
    assert len(seed.FAQS) == 20
    rows = db.execute(select(Ticket.customer_id, Order.customer_id).join(Order, Ticket.order_id == Order.id).where(Ticket.id.like('seed%'))).all()
    assert len(rows) == 500
    assert all(customer == owner for customer, owner in rows)

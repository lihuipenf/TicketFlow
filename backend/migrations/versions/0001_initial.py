"""Initial TicketFlow schema."""
from alembic import op
from app.db import Base

revision = '0001'
down_revision = None


def upgrade():
    Base.metadata.create_all(op.get_bind())


def downgrade():
    raise RuntimeError('Destructive downgrade is disabled; restore a verified backup instead.')

"""add EXPIRED booking status

Revision ID: b3f1c2d4e5a6
Revises: e69961e64923
Create Date: 2026-11-19 12:00:00.000000

The initial schema made booking_status a native Postgres enum type,
bookingstatusenum. A booking whose hold expired gets the new value EXPIRED,
so the type needs that value.

ALTER TYPE ... ADD VALUE runs outside the migration transaction, because a
new enum value cannot be used in the transaction that adds it.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b3f1c2d4e5a6'
down_revision: Union[str, None] = 'e69961e64923'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    # A database made with create_all stores the status as VARCHAR and has no
    # enum type. It needs no change.
    has_type = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = 'bookingstatusenum'")
    ).first()
    if not has_type:
        return
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE bookingstatusenum ADD VALUE IF NOT EXISTS 'EXPIRED'")


def downgrade() -> None:
    # Postgres cannot remove a value from an enum type. The value stays, and
    # bookings with the status EXPIRED stay valid.
    pass

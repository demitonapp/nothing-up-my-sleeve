"""a ship can be retired: s1.ships.status ('in service' or 'retired')

Justin, 2026-11-08: "we need to clean up all the versions of 300k and 1m, can we just prune it down to the top 5 for
both of them". A retired ship is hidden from the dashboard's ship lists by default and shown on request; nothing
is deleted. (`archived` stays what it was: the First Fleet, fitted out before 7 November.)

Revision ID: c7e4a1d90b52
Revises: 42266ae2e729
Create Date: 2026-11-08 16:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c7e4a1d90b52"
down_revision: str | Sequence[str] | None = "42266ae2e729"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ships", sa.Column("status", sa.Text(), server_default="in service", nullable=False), schema="s1")
    op.add_column("ships", sa.Column("retired_note", sa.Text(), nullable=True), schema="s1")


def downgrade() -> None:
    op.drop_column("ships", "retired_note", schema="s1")
    op.drop_column("ships", "status", schema="s1")

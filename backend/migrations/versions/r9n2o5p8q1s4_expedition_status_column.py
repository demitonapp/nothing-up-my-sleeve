"""The expedition state is a column

The 11 November status pass: `s1.expedition_status` holds the six-state value the Expeditions page shows
(`at sea`, `under way`, `in port`, `home`, `paused`, `awaiting orders`). The coordinator writes it when
the helm or the queue moves (`liberty_machine.refresh_expedition_states`); the page reads it. Additive: one table.

Revision ID: r9n2o5p8q1s4
Revises: q8m1n4o7p0r3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "r9n2o5p8q1s4"
down_revision = "q8m1n4o7p0r3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # if not exists: a fresh server may have made the table lazily before the migration ran
    op.execute(
        "create table if not exists s1.expedition_status ("
        "key text primary key, status text not null, "
        "updated_at timestamptz not null default now())"
    )


def downgrade() -> None:
    op.drop_table("expedition_status", schema="s1")

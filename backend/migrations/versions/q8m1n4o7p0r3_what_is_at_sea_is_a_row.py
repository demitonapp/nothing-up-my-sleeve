"""What is at sea is a row, not the coordinator's memory

The architecture audit of 11 November, item 2: a queue line was deleted from `s2.queue_lines` before its launch
and `s2.queue_history` was written only when the coordinator saw the exit, so a coordinator that died lost
every voyage it had out. `s2.at_sea` holds one row per launched line, written in the step that takes the line
and deleted in the step that writes its history; a restarted coordinator adopts what it finds there
(`thorp.viable.s2_coordination.lanes.run`). Additive: one new table, nothing else touched.

Revision ID: q8m1n4o7p0r3
Revises: p7l0m3n6o9q2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "q8m1n4o7p0r3"
down_revision = "p7l0m3n6o9q2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "at_sea",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("lane", sa.Text(), nullable=False),
        sa.Column("seat", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("pid", sa.Integer(), nullable=True),
        sa.Column("started", sa.Text(), nullable=True),
        sa.Column("started_ts", sa.Float(), nullable=True),
        sa.Column("coordinator", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        schema="s2",
    )


def downgrade() -> None:
    op.drop_table("at_sea", schema="s2")

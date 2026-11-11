"""the purser's calls

S3's allocation of the backlog between local and foreign waters (DECISIONS.md, "The purser", adopted 8 November
as proposed, Justin: "Accept all five"; built 12 November, Justin: "We need to build the router"). Each call is
kept in `s3.allocations`: the line, the waters chosen, both estimates, the cost, the allowance and the reason.
It sits beside `s3.spend_events`, so S3* can audit the estimates against what the voyages took.

Revision ID: f3a6b9c2d5e8
Revises: e2z5a8b1c4d7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f3a6b9c2d5e8"
down_revision = "e2z5a8b1c4d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "allocations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("line", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("run_id", sa.Text(), nullable=True),
        sa.Column("expedition", sa.Text(), nullable=True),
        sa.Column("waters", sa.Text(), nullable=False),
        sa.Column("gpu", sa.Text(), nullable=True),
        sa.Column("local_min", sa.Float(), nullable=True),
        sa.Column("local_home_min", sa.Float(), nullable=True),
        sa.Column("foreign_min", sa.Float(), nullable=True),
        sa.Column("foreign_home_min", sa.Float(), nullable=True),
        sa.Column("cost", sa.Float(), nullable=True),
        sa.Column("allowance", sa.Float(), nullable=True),
        sa.Column("mode", sa.Text(), nullable=False),
        sa.Column("applied", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        schema="s3",
    )
    op.create_index("allocations_line_at", "allocations", ["line", "at"], schema="s3")


def downgrade() -> None:
    op.drop_index("allocations_line_at", table_name="allocations", schema="s3")
    op.drop_table("allocations", schema="s3")

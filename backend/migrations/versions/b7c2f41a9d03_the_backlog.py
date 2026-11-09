"""the backlog: work that may run while a decision waits (s4.backlog)

Justin, 2026-11-08: "there will always be a backlog of things that can run while waiting for me to make a decision,
so another rule should be if justin's not available then catch up on the backlog experiments if they're still valid".
An item carries the decision it still feeds; the audit strikes what no longer sails or no longer decides, with its
reason. `thorp backlog audit` writes the verdicts (thorp/viable/s4_intelligence/backlog.py).

Revision ID: b7c2f41a9d03
Revises: 93d94cd08802
Create Date: 2026-11-08 18:40:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b7c2f41a9d03"
down_revision: str | Sequence[str] | None = "93d94cd08802"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backlog",
        sa.Column("line", sa.Text(), nullable=False),
        sa.Column("expedition", sa.Text(), server_default="", nullable=False),
        sa.Column("decision", sa.Text(), server_default="", nullable=False),
        sa.Column("control", sa.Text(), server_default="", nullable=False),
        sa.Column("prediction", sa.Text(), server_default="", nullable=False),
        sa.Column("minutes", sa.Float(), nullable=True),
        sa.Column("gain", sa.Float(), nullable=True),
        sa.Column("state", sa.Text(), server_default="unknown", nullable=False),
        sa.Column("why", sa.Text(), server_default="", nullable=False),
        sa.Column("source", sa.Text(), server_default="", nullable=False),
        sa.Column(
            "added_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "state in ('valid', 'blocked', 'struck', 'sailed', 'unknown')", name="backlog_state"
        ),
        sa.PrimaryKeyConstraint("line"),
        schema="s4",
    )
    op.create_index("backlog_state", "backlog", ["state"], schema="s4")


def downgrade() -> None:
    op.drop_index("backlog_state", table_name="backlog", schema="s4")
    op.drop_table("backlog", schema="s4")

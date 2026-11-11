"""a line keeps its goal at sea and in its history

Every queued line serves a goal (`s2.queue_lines.goal_id`, 11-12 November). But a line that sails leaves
`queue_lines` for `s2.at_sea`, and a line that ends goes to `s2.queue_history`. Neither table had the column, so
the goal was lost the moment a line was taken. The queue page then showed the voyage at sea with no goal
(12 November, Justin: "the current voyage has no goal. I thought that wasn't possible"; 9m@v0.0.6-converse
serves kipling:3). The column goes on both tables. The coordinator carries the goal from the queued row to the
at-sea row, and from there to the history. Rows written before this are filled from each line's spec or
investigation by `queue_store.backfill_goals()`.

Revision ID: e2z5a8b1c4d7
Revises: d1y4z7a0b3c6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e2z5a8b1c4d7"
down_revision = "d1y4z7a0b3c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("at_sea", sa.Column("goal_id", sa.Text(), nullable=True), schema="s2")
    op.add_column("queue_history", sa.Column("goal_id", sa.Text(), nullable=True), schema="s2")


def downgrade() -> None:
    op.drop_column("queue_history", "goal_id", schema="s2")
    op.drop_column("at_sea", "goal_id", schema="s2")

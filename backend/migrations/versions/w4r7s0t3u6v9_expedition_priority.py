"""The priority order in Postgres, not a JSON file

11 November (Justin: "it shouldn't be saved in json it should be saved in postgres"). `s1.expedition_priority`
is one row a rank — `position` (0 is highest), `key` (an expedition:goal, or a bare expedition key) — and
`thorp.priorities` reads and writes it. The old `data/expedition-priority.json` is imported once by the
module on the first read of an empty table and then deleted. Additive: one table.

Revision ID: w4r7s0t3u6v9
Revises: v3q6r9s2t5u8
"""

from __future__ import annotations

from alembic import op

revision = "w4r7s0t3u6v9"
down_revision = "v3q6r9s2t5u8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create table if not exists s1.expedition_priority ("
        "position integer primary key, "
        "key text not null unique, "
        "updated_at timestamptz not null default now())"
    )


def downgrade() -> None:
    op.execute("drop table if exists s1.expedition_priority")

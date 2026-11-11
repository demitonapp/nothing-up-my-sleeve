"""Goals as rows, with a real relationship to expeditions

The 11 November pass (Justin: "the goals have to have a relationship to expeditions in the db ... so we
start retiring expeditions"). `s1.expeditions` is one row an expedition; `s1.expedition_goals` one row a
goal, keyed `expedition:position` (or the bare expedition key where it states no goals), with the
verdict the store owns (`status`, `evidence`, `words`, `settled_at`). `s2.queue_lines.goal_id` names the
goal a line serves. Additive: two tables, one column, two indexes.

Revision ID: v3q6r9s2t5u8
Revises: u2p5q8r1s4t7
"""

from __future__ import annotations

from alembic import op

revision = "v3q6r9s2t5u8"
down_revision = "u2p5q8r1s4t7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create table if not exists s1.expeditions ("
        "key text primary key, "
        "name text not null, "
        "goal text, "
        "fleet text, "
        "preset text, "
        "ship text, "
        "declared_status text, "
        "updated_at timestamptz not null default now())"
    )
    op.execute(
        "create table if not exists s1.expedition_goals ("
        "goal_id text primary key, "
        "expedition_key text not null references s1.expeditions(key) on delete cascade, "
        "position integer not null default 0, "
        "text text not null default '', "
        "detail text not null default '', "
        "why text not null default '', "
        "status text not null default 'open', "
        "evidence text not null default '', "
        "words text not null default '', "
        "settled_at timestamptz, "
        "updated_at timestamptz not null default now(), "
        "unique (expedition_key, position))"
    )
    op.execute(
        "create index if not exists expedition_goals_expedition "
        "on s1.expedition_goals (expedition_key)"
    )
    op.execute(
        "alter table if exists s2.queue_lines add column if not exists goal_id text "
        "references s1.expedition_goals(goal_id) on delete set null"
    )
    op.execute(
        "create index if not exists queue_lines_goal on s2.queue_lines (goal_id)"
    )


def downgrade() -> None:
    op.execute("alter table if exists s2.queue_lines drop column if exists goal_id")
    op.execute("drop table if exists s1.expedition_goals")
    op.execute("drop table if exists s1.expeditions")

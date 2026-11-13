"""The tables Python used to make at run time are Alembic's, and the rules Python used to state are checks

13 November (Justin: S5 policy "postgres": "ACID and all database stuff has to occur in postgres ... eliminate all the tech debt
and spaghetti code where python is trying to be a database"). Eight modules ran `create table if not exists` at run time. Five
already had a migration (chat notes, chat questions, chat threads, the expeditions' status, the priority order); three never did
and the table was made the first time a page read it (`s4.arc_answers`, `s1.discoveries`, `s5.charter_signoffs`), and one column
(`s4.chat_threads.folder`) was only ever added by a runtime `alter table`. All of it is here now, `if not exists` because the real
store has it already, and the modules' `ensure()` does nothing.

The rules Python stated about a value are checks, so the database refuses what it should whoever writes:

- `s1.expedition_status.status` is one of the six states the pages show;
- `s1.expedition_goals.status` is open, partly, done or dropped, and `position` is not negative;
- `s4.arc_answers.kind` is outside or ship.

Revision ID: f7b9d1e3a5c8
Revises: e6a8b0c2d4f6
"""

from __future__ import annotations

from alembic import op

revision = "f7b9d1e3a5c8"
down_revision = "e6a8b0c2d4f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create table if not exists s4.arc_answers ("
        "reader text not null, kind text not null, config text not null, part text not null, "
        "question_id text not null, source text not null default '', n_options integer not null, "
        "answer integer not null, prediction integer, correct boolean not null default false, "
        "read boolean not null default true, rank integer, p_answer double precision, "
        "margin double precision, ce jsonb, revision text not null default '', "
        "scored_at timestamptz not null default now(), "
        "primary key (reader, config, part, question_id))"
    )
    op.execute("create index if not exists arc_answers_question on s4.arc_answers (config, part, question_id)")
    op.execute(
        "create table if not exists s1.discoveries ("
        "key text primary key, payload jsonb not null, built_at timestamptz not null default now(), runs integer)"
    )
    op.execute(
        "create table if not exists s5.charter_signoffs ("
        "charter text not null, param text not null, value jsonb not null default '{}'::jsonb, "
        "signed_by text not null default '', note text not null default '', "
        "signed_at timestamptz not null default now(), primary key (charter, param))"
    )
    op.execute("alter table s4.chat_threads add column if not exists folder text not null default ''")
    op.execute(
        "alter table s1.expedition_status add constraint expedition_status_state check "
        "(status in ('at sea', 'under way', 'in port', 'home', 'paused', 'awaiting orders'))"
    )
    op.execute(
        "alter table s1.expedition_goals add constraint expedition_goals_status check "
        "(status in ('open', 'partly', 'done', 'dropped')), "
        "add constraint expedition_goals_position check (position >= 0)"
    )
    op.execute("alter table s4.arc_answers add constraint arc_answers_kind check (kind in ('outside', 'ship'))")


def downgrade() -> None:
    op.execute("alter table s4.arc_answers drop constraint if exists arc_answers_kind")
    op.execute("alter table s1.expedition_goals drop constraint if exists expedition_goals_position")
    op.execute("alter table s1.expedition_goals drop constraint if exists expedition_goals_status")
    op.execute("alter table s1.expedition_status drop constraint if exists expedition_status_state")
    # the tables and the folder column stay: dropping them would lose records

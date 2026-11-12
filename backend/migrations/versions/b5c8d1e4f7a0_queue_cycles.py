"""the queue's planning cycle, and what the judge said

12 November (Justin: "talk me through how in our VSM the optimal way to schedule the queue every 12 hours to
maximise speed and maintain the cost ceilings"; "build it").

`s3.cycles` is one row a turn of the cycle: what S3* found when it set the last cycle's plan against what
happened, what S4 had measured (each class's set-up, its failures, its rates), the envelope S5 allowed, the plan
the purser made (the fleets it tried and the one it chose), and what it proposes to S5. JSONB throughout: the
shape is the planner's and will grow.

`s4.judgments` is one row each time S5's judge (s5.judges) was asked something a number cannot say, today why
a fit-out died: the subject, what a person already said the cause was (where one did), the judge's verdict and
all it said.

Revision ID: b5c8d1e4f7a0
Revises: a4b7c0d3e6f9
"""

from __future__ import annotations

from alembic import op

revision = "b5c8d1e4f7a0"
down_revision = "a4b7c0d3e6f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create table if not exists s3.cycles ("
        "id bigserial primary key, "
        "at timestamptz not null default now(), "
        "hours double precision not null, "
        "how text not null default 'by hand', "
        "audit jsonb not null default '{}', "
        "measured jsonb not null default '{}', "
        "envelope jsonb not null default '{}', "
        "plan jsonb not null default '{}', "
        "proposals jsonb not null default '[]', "
        "judged jsonb not null default '[]', "
        "seconds double precision)"
    )
    op.execute("create index if not exists cycles_at on s3.cycles (at desc)")
    op.execute(
        "create table if not exists s4.judgments ("
        "id bigserial primary key, "
        "at timestamptz not null default now(), "
        "judge text not null, "
        "kind text not null, "
        "subject text not null, "
        "known text, "
        "verdict jsonb not null default '{}', "
        "said text not null default '', "
        "seconds double precision, "
        "outcome text not null default 'ok')"
    )
    op.execute("create index if not exists judgments_subject on s4.judgments (kind, subject, at desc)")


def downgrade() -> None:
    op.execute("drop table if exists s4.judgments")
    op.execute("drop table if exists s3.cycles")

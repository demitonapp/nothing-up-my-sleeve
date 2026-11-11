"""What a voyage was trained from, beside its run id

11 November (the architecture audit, item 3: "a run id does not pin what was trained"). The run id hashes the
spec, and the spec names its lists by path, its parents by name and its code by a commit that is nearly always
"-dirty". The id cannot change (a changed id makes finished voyages look unsailed), so what pins the voyage is
kept beside it: `s1.run_provenance`, one row a run, the document `thorp/versioning.py` `provenance()` writes at
the start of a voyage (the spec as hashed, the bytes of every list it names, the parents by id, the tokeniser, the
code and its diff, the backend and the environment that changes results).

A side table, not a column on `s1.runs`: the coordinator holds a lock on that table, and nothing here may wait on
it. No foreign key, for the same reason (and a box's run row reaches home after its provenance may).

Revision ID: y6t9u2v5w8x1
Revises: x5s8t1u4v7w0
"""

from __future__ import annotations

from alembic import op

revision = "y6t9u2v5w8x1"
down_revision = "x5s8t1u4v7w0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(
        "create table if not exists s1.run_provenance ("
        "run_id text primary key, "
        "doc jsonb not null, "
        "recorded_at timestamptz not null default now())"
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("drop table if exists s1.run_provenance")

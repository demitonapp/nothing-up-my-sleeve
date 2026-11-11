"""How far a hired box's ledger has been folded home, per run and table

11 November (the architecture audit, item 4: "the fold from a hired box deletes and re-inserts every row of the leg
every 20 minutes, in three separate transactions"). `s2.fold_marks` holds, per (run_id, tbl), the leg it belongs to
(`leg_start`, the step the leg set out from, -1 for a voyage from step 0), the box's last SQLite rowid folded
(`last_id`), how many of the leg's rows the box held up to it (`rows`), a digest of those rows (`digest`), and when.
`s2_coordination.charter.bring_home` then inserts only the box's rows past the mark, and folds the whole leg again,
as before, when the box's rows up to the mark are no longer the ones folded (a resume aboard truncated them, or a new
box sails the leg).

A side table in s2, keyed by run id, with no foreign key: nothing here may wait on the coordinator's lock on s1.runs.

Revision ID: a8v1w4x7y0z3
Revises: z7u0v3w6x9y2
"""

from __future__ import annotations

from alembic import op

revision = "a8v1w4x7y0z3"
down_revision = "z7u0v3w6x9y2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("create schema if not exists s2")
    op.execute(
        "create table if not exists s2.fold_marks ("
        "run_id text not null, "
        "tbl text not null, "
        "leg_start bigint not null, "
        "last_id bigint not null, "
        "rows bigint not null, "
        "digest text not null, "
        "folded_at timestamptz not null default now(), "
        "primary key (run_id, tbl))"
    )


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("drop table if exists s2.fold_marks")

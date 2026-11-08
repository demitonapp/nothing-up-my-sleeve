"""the systems own their schemas: fitout's tables and views into s3 (control), game's into s4 (intelligence), ship's
into s1 (operations), as decided with the model (DECISIONS.md, "One store: Postgres, by the viable system", 13:42).
ALTER ... SET SCHEMA: no rows copied, the sequences and views follow their tables. Alembic's own version table moves
from `fitout` to `s3` at the next alembic command (migrations/env.py), since a migration cannot move the table its own
revision is written to; `fitout` is dropped then, once empty.

Revision ID: a3f1c0de5b1b
Revises: 09d8a21e0199
Create Date: 2026-11-08 14:20:00

"""
from collections.abc import Sequence

from alembic import op

revision: str = "a3f1c0de5b1b"
down_revision: str | Sequence[str] | None = "09d8a21e0199"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MOVES = {
    ("fitout", "s3"): ("fitouts", "stages", "precheck_items", "fitout_prechecks", "precheck_results"),
    ("game", "s4"): ("rounds", "bets"),
    ("ship", "s1"): ("sizes", "ships", "voyages"),
}
VIEWS = {("fitout", "s3"): ("current_results", "readiness")}


def _drop_if_empty(schema: str) -> None:
    op.execute(f"""do $$ begin
        if exists (select 1 from pg_namespace where nspname = '{schema}')
           and not exists (select 1 from pg_class c join pg_namespace n on n.oid = c.relnamespace where n.nspname = '{schema}')
        then execute 'drop schema {schema}'; end if; end $$""")


def upgrade() -> None:
    for (old, new), tables in MOVES.items():
        op.execute(f"create schema if not exists {new}")
        for t in tables:
            op.execute(f"alter table {old}.{t} set schema {new}")
    for (old, new), views in VIEWS.items():
        for v in views:
            op.execute(f"alter view {old}.{v} set schema {new}")
    for old, _ in MOVES:
        _drop_if_empty(old)  # fitout keeps alembic_version until env.py moves it


def downgrade() -> None:
    for (old, new), views in VIEWS.items():
        op.execute(f"create schema if not exists {old}")
        for v in views:
            op.execute(f"alter view {new}.{v} set schema {old}")
    for (old, new), tables in MOVES.items():
        op.execute(f"create schema if not exists {old}")
        for t in tables:
            op.execute(f"alter table {new}.{t} set schema {old}")

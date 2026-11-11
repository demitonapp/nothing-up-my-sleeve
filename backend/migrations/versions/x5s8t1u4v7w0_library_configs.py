"""A branch's configurations are a JSON of choices, not a version

11 November (Justin: "a branch doesn't get a version but rather a json of choices"). `s3.library_configs`
is one row a saved configuration: the branch, a name and note, the normalised choices (JSONB), and the
content hash that names it. The old named lists stay in `s3.library_variations` as sailed, read-only rows.

Revision ID: x5s8t1u4v7w0
Revises: w4r7s0t3u6v9
"""

from __future__ import annotations

from alembic import op

revision = "x5s8t1u4v7w0"
down_revision = "w4r7s0t3u6v9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create table if not exists s3.library_configs ("
        "key text primary key, "
        "branch_key text not null references s3.library_branches(key) on delete cascade, "
        "name text not null, "
        "about text not null default '', "
        "choices jsonb not null, "
        "config_hash text not null, "
        "ordinal integer not null default 0, "
        "created_at timestamptz not null default now(), "
        "created_by text not null default '')"
    )
    op.execute("create index if not exists library_configs_branch on s3.library_configs (branch_key, created_at desc)")


def downgrade() -> None:
    op.execute("drop table if exists s3.library_configs")

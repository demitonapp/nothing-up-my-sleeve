"""Chat threads persisted in Postgres

The 11 November persistence pass: `s4.chat_threads`, a chat thread (its model, title, saved mark,
timestamps and messages as JSON) so a saved chat survives the browser. Additive: one table and an index.

Revision ID: u2p5q8r1s4t7
Revises: t1o4p7q0r3s6
"""

from __future__ import annotations

from alembic import op

revision = "u2p5q8r1s4t7"
down_revision = "t1o4p7q0r3s6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create table if not exists s4.chat_threads ("
        "id text primary key, key text not null, name text, kind text, model text, ship_key text, "
        "href text, title text, saved boolean not null default false, created_ms bigint, "
        "updated_ms bigint, messages jsonb not null default '[]')"
    )
    op.execute(
        "create index if not exists chat_threads_updated on s4.chat_threads (updated_ms desc)"
    )


def downgrade() -> None:
    op.drop_table("chat_threads", schema="s4")

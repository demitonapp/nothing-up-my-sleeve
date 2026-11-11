"""The question library: kept questions filed under folders

The 11 November question library: `s4.chat_questions`, a question, the folder it is filed under, and
the model it was typed against. The chat console writes and reads it. Additive: one table and an index.

Revision ID: t1o4p7q0r3s6
Revises: s0n3p6q9r2t5
"""

from __future__ import annotations

from alembic import op

revision = "t1o4p7q0r3s6"
down_revision = "s0n3p6q9r2t5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create table if not exists s4.chat_questions ("
        "id bigserial primary key, created_at timestamptz not null default now(), "
        "folder text not null default 'inbox', question text not null, model text)"
    )
    op.execute(
        "create index if not exists chat_questions_folder on s4.chat_questions (folder, created_at desc)"
    )


def downgrade() -> None:
    op.drop_table("chat_questions", schema="s4")

"""Notes taken in a chat, with the model and the session

The 11 November notes pass: `s4.chat_notes` holds Justin's notes, tagged with the model (kind, key,
label, run), the chat session and that session's whole reasoning trace, with the conversation as JSON.
The chat writes them; the chat reads them back. Additive: one table and two indexes.

Revision ID: s0n3p6q9r2t5
Revises: r9n2o5p8q1s4
"""

from __future__ import annotations

from alembic import op

revision = "s0n3p6q9r2t5"
down_revision = "r9n2o5p8q1s4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create table if not exists s4.chat_notes ("
        "id bigserial primary key, created_at timestamptz not null default now(), "
        "session_id text, kind text, model_key text, model_label text, run text, "
        "note text not null, thinking text, conversation jsonb)"
    )
    op.execute("create index if not exists chat_notes_model on s4.chat_notes (model_key, created_at desc)")
    op.execute("create index if not exists chat_notes_session on s4.chat_notes (session_id, created_at desc)")


def downgrade() -> None:
    op.drop_table("chat_notes", schema="s4")

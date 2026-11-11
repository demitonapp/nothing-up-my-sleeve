"""Notes taken in a chat (11 November, Justin: "an ability for me to take notes and then tag that
note with the model I'm talking to, and the chat session and all thinking ... in the db so I can review
those notes").

`s4.chat_notes` holds one row a note: the words, and the tags the chat supplies — the model (kind, key,
label, run), the session id, and the whole reasoning trace of that session up to the note, with the
conversation beside it as JSON. A note is Justin's; nothing here edits or ranks them.
"""

from __future__ import annotations

import json

from sqlalchemy import text

from thorp import store

_DDL = (
    "create table if not exists s4.chat_notes ("
    "id bigserial primary key, "
    "created_at timestamptz not null default now(), "
    "session_id text, "
    "kind text, "
    "model_key text, "
    "model_label text, "
    "run text, "
    "note text not null, "
    "thinking text, "
    "conversation jsonb)"
)


def ensure() -> None:
    with store.session() as s:
        s.execute(text(_DDL))
        s.execute(text("create index if not exists chat_notes_model on s4.chat_notes (model_key, created_at desc)"))
        s.execute(text("create index if not exists chat_notes_session on s4.chat_notes (session_id, created_at desc)"))


def save(
    note: str,
    *,
    session_id: str | None = None,
    kind: str | None = None,
    model_key: str | None = None,
    model_label: str | None = None,
    run: str | None = None,
    thinking: str | None = None,
    conversation: list | None = None,
) -> dict:
    """Add one note; returns the row as the page reads it."""
    ensure()
    with store.session() as s:
        row = s.execute(
            text(
                "insert into s4.chat_notes (session_id, kind, model_key, model_label, run, note, thinking, conversation) "
                "values (:session, :kind, :model, :label, :run, :note, :thinking, cast(:conv as jsonb)) "
                "returning id, created_at, session_id, kind, model_key, model_label, run, note, thinking"
            ),
            {
                "session": session_id,
                "kind": kind,
                "model": model_key,
                "label": model_label,
                "run": run,
                "note": note.strip(),
                "thinking": thinking or "",
                "conv": json.dumps(conversation or []),
            },
        ).one()
        s.commit()
        return dict(row._mapping)


def notes(model: str | None = None, session: str | None = None, limit: int = 100) -> list[dict]:
    """The notes, newest first; by model or session when asked."""
    ensure()
    where, params = [], {"limit": max(1, min(int(limit), 500))}
    if model:
        where.append("model_key = :model")
        params["model"] = model
    if session:
        where.append("session_id = :session")
        params["session"] = session
    clause = (" where " + " and ".join(where)) if where else ""
    with store.session() as s:
        rows = s.execute(
            text(
                "select id, created_at, session_id, kind, model_key, model_label, run, note, thinking, conversation "
                "from s4.chat_notes" + clause + " order by created_at desc limit :limit"
            ),
            params,
        ).all()
        return [dict(r._mapping) for r in rows]

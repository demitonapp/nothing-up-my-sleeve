"""The question library (11 November, Justin: "I'd like to be able to type in questions and then save
them to a library of questions against folders").

`s4.chat_questions` holds one question a row with the folder it was filed under and, when it was typed
against a model, that model's name. The console writes and reads it; nothing else does.
"""

from __future__ import annotations

from sqlalchemy import text

from thorp import store

_DDL = (
    "create table if not exists s4.chat_questions ("
    "id bigserial primary key, "
    "created_at timestamptz not null default now(), "
    "folder text not null default 'inbox', "
    "question text not null, "
    "model text)"
)


def ensure() -> None:
    with store.session() as s:
        s.execute(text(_DDL))
        s.execute(
            text(
                "create index if not exists chat_questions_folder on s4.chat_questions (folder, created_at desc)"
            )
        )


def save(question: str, folder: str = "inbox", model: str | None = None) -> dict:
    q = question.strip()
    if not q:
        raise ValueError("no question")
    name = (folder or "inbox").strip() or "inbox"
    ensure()
    with store.session() as s:
        row = s.execute(
            text(
                "insert into s4.chat_questions (folder, question, model) values (:folder, :question, :model) "
                "returning id, created_at, folder, question, model"
            ),
            {"folder": name, "question": q, "model": model},
        ).one()
        s.commit()
        return dict(row._mapping)


def payload() -> dict:
    """Every question, newest first, with the folders and their counts."""
    ensure()
    with store.session() as s:
        rows = [
            dict(r._mapping)
            for r in s.execute(
                text(
                    "select id, created_at, folder, question, model from s4.chat_questions order by folder, created_at desc"
                )
            ).all()
        ]
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["folder"]] = counts.get(r["folder"], 0) + 1
    return {
        "folders": [{"name": k, "count": v} for k, v in sorted(counts.items())],
        "questions": rows,
    }


def remove(qid: int) -> None:
    """Take one question out of the library (13 November: the console's Questions folder forgets one)."""
    ensure()
    with store.session() as s:
        s.execute(text("delete from s4.chat_questions where id = :id"), {"id": int(qid)})
        s.commit()

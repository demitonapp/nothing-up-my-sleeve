"""Chat threads kept in Postgres (11 November, Justin: "add a functionality to save a chat and persist
to postgres").

A thread is the same shape the chat keeps in the browser (`lib/conversations.ts`): id, the model key,
its name and kind, the title, whether it is saved, the two timestamps (milliseconds), and the messages
as JSON. The browser writes one here on every save and reads them back when it syncs, so a chat survives
a cleared browser and is the same on another one.
"""

from __future__ import annotations

import json

from sqlalchemy import text

from thorp import store

_DDL = (
    "create table if not exists s4.chat_threads ("
    "id text primary key, "
    "key text not null, "
    "name text, "
    "kind text, "
    "model text, "
    "ship_key text, "
    "href text, "
    "title text, "
    "saved boolean not null default false, "
    "created_ms bigint, "
    "updated_ms bigint, "
    "messages jsonb not null default '[]')"
)


def ensure() -> None:
    with store.session() as s:
        s.execute(text(_DDL))
        s.execute(
            text(
                "create index if not exists chat_threads_updated on s4.chat_threads (updated_ms desc)"
            )
        )


def _thread(row) -> dict:
    m = dict(row._mapping)
    return {
        "id": m["id"],
        "key": m["key"],
        "name": m["name"] or "",
        "kind": m["kind"] or "foreign",
        "model": m["model"],
        "shipKey": m["ship_key"] or "",
        "href": m["href"] or "",
        "title": m["title"] or "",
        "saved": bool(m["saved"]),
        "createdAt": int(m["created_ms"] or 0),
        "updatedAt": int(m["updated_ms"] or 0),
        "messages": m["messages"] or [],
    }


def save(t: dict) -> dict:
    tid = str(t.get("id") or "").strip()
    if not tid:
        raise ValueError("no thread id")
    ensure()
    with store.session() as s:
        s.execute(
            text(
                "insert into s4.chat_threads (id, key, name, kind, model, ship_key, href, title, saved, created_ms, updated_ms, messages) "
                "values (:id, :key, :name, :kind, :model, :ship, :href, :title, :saved, :created, :updated, cast(:messages as jsonb)) "
                "on conflict (id) do update set key=excluded.key, name=excluded.name, kind=excluded.kind, model=excluded.model, "
                "ship_key=excluded.ship_key, href=excluded.href, title=excluded.title, saved=excluded.saved, "
                "created_ms=excluded.created_ms, updated_ms=excluded.updated_ms, messages=excluded.messages"
            ),
            {
                "id": tid,
                "key": str(t.get("key") or ""),
                "name": t.get("name"),
                "kind": t.get("kind"),
                "model": t.get("model"),
                "ship": t.get("shipKey"),
                "href": t.get("href"),
                "title": t.get("title"),
                "saved": bool(t.get("saved")),
                "created": int(t.get("createdAt") or 0),
                "updated": int(t.get("updatedAt") or 0),
                "messages": json.dumps(t.get("messages") or []),
            },
        )
        row = s.execute(text("select * from s4.chat_threads where id = :id"), {"id": tid}).one()
        s.commit()
        return _thread(row)


def all_threads() -> list[dict]:
    ensure()
    with store.session() as s:
        rows = s.execute(
            text("select * from s4.chat_threads order by updated_ms desc limit 200")
        ).all()
        return [_thread(r) for r in rows]


def remove(tid: str) -> None:
    ensure()
    with store.session() as s:
        s.execute(text("delete from s4.chat_threads where id = :id"), {"id": tid})
        s.commit()

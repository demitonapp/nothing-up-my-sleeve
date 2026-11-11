"""The book register. This module creates, and is the only writer of, data/manifest.sqlite."""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict, dataclass

from thorp import paths

SCHEMA = """
create table if not exists books (
    id text primary key,
    source text not null,
    title text,
    author text,
    language text,
    family text,
    text text,
    chars integer,
    bytes integer,
    sha1 text,
    fetched_at text,
    "set" text
);
"""


@dataclass
class Book:
    id: str
    source: str
    title: str
    author: str
    language: str
    family: str
    text: str
    chars: int
    bytes: int
    sha1: str
    fetched_at: str
    set: str


def _connect() -> sqlite3.Connection:
    path = paths.manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("pragma journal_mode=wal")
    con.executescript(SCHEMA)
    return con


def upsert(book: Book) -> None:
    """Register a book. At home it is written to the store first (`s1.books`, where every reader looks; a store
    that is down raises `store.StoreDown` before anything is written), then to `data/manifest.sqlite`, which is
    no longer read at home but is the copy `charter.stage` carries to a hired box (11 November: a box reads its
    library from that file, so a book registered only in Postgres would be missing aboard). On a box, or with
    `THORP_LIBRARY_PG=0`, the file is the register and the only write."""
    row = asdict(book)
    if _pg():  # the one store: a new book is written where the readers look
        from thorp import manifest_store, store

        with store.session() as s:
            manifest_store.put_book(s, row)
    cols = ", ".join(f'"{k}"' for k in row)
    qs = ", ".join("?" for _ in row)
    updates = ", ".join(f'"{k}"=excluded."{k}"' for k in row if k != "id")
    with _connect() as con:
        con.execute(
            f"insert into books ({cols}) values ({qs}) on conflict(id) do update set {updates}",
            list(row.values()),
        )


def _pg() -> bool:
    """Whether the store answers for the register: Postgres by default on this Mac (11 November, the cut-over's
    second half: the same rule as the ledger and the queue, so no process reads the library from a file by
    accident). A hired box (`THORP_SHIP_LOG` or `THORP_PAPERS`) reads the `manifest.sqlite` it carries;
    `THORP_LIBRARY_PG` overrides either way (`0` for the file, `1` for the store)."""
    flag = os.environ.get("THORP_LIBRARY_PG")
    if flag is not None:
        return flag.strip().lower() not in ("0", "false", "no", "off", "")
    if os.environ.get("THORP_PAPERS"):
        return False
    return os.environ.get("THORP_SHIP_LOG", "").strip().lower() not in ("1", "true", "yes")


def get(book_id: str) -> Book | None:
    if _pg():
        from thorp import manifest_store

        row = manifest_store.get_book(book_id)
        return Book(**row) if row else None
    with _connect() as con:
        r = con.execute("select * from books where id=?", (book_id,)).fetchone()
    return Book(**dict(r)) if r else None


def same_text(sha1: str, other_than: str) -> str | None:
    """The id of another book in the register with this text's sha1, or None (intake's duplicate check)."""
    if _pg():
        from sqlalchemy import select

        from thorp import manifest_store, store

        with store.session() as s:
            B = manifest_store.Book
            return s.scalar(select(B.id).where(B.sha1 == sha1, B.id != other_than).limit(1))
    with _connect() as con:
        r = con.execute("select id from books where sha1=? and id<>? limit 1", (sha1, other_than)).fetchone()
    return r["id"] if r else None


def get_many(book_ids: Iterable[str]) -> dict[str, Book]:
    out = {}
    for b in book_ids:
        book = get(b)
        if book is None:
            raise KeyError(f"{b} is not in the manifest; run `thorp fetch` first")
        out[b] = book
    return out


def all_books() -> list[Book]:
    if _pg():
        from thorp import manifest_store

        return [Book(**row) for row in manifest_store.all_books()]
    with _connect() as con:
        return [Book(**dict(r)) for r in con.execute("select * from books order by id")]

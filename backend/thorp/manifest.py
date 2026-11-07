"""The book register. This module creates, and is the only writer of, data/manifest.sqlite."""

from __future__ import annotations

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
    row = asdict(book)
    cols = ", ".join(f'"{k}"' for k in row)
    qs = ", ".join("?" for _ in row)
    updates = ", ".join(f'"{k}"=excluded."{k}"' for k in row if k != "id")
    with _connect() as con:
        con.execute(
            f"insert into books ({cols}) values ({qs}) on conflict(id) do update set {updates}",
            list(row.values()),
        )


def get(book_id: str) -> Book | None:
    with _connect() as con:
        r = con.execute("select * from books where id=?", (book_id,)).fetchone()
    return Book(**dict(r)) if r else None


def get_many(book_ids: Iterable[str]) -> dict[str, Book]:
    out = {}
    for b in book_ids:
        book = get(b)
        if book is None:
            raise KeyError(f"{b} is not in the manifest; run `thorp fetch` first")
        out[b] = book
    return out


def all_books() -> list[Book]:
    with _connect() as con:
        return [Book(**dict(r)) for r in con.execute("select * from books order by id")]

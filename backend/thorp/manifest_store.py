"""The book register in Postgres (schema `s1`): `books`, copied from `data/manifest.sqlite`.

This is the library half of the "one store" cut-over (DECISIONS.md, "One store: Postgres, by the viable
system", phase 2: *the library*). `thorp/manifest.py` stays the writer of record until the cut-over; this
module holds the Postgres table those rows move into, and the read-only backfill with a count check.

- **The table mirrors the SQLite schema** (`books`: id, source, title, author, language, family, text,
  chars, bytes, sha1, fetched_at, "set"). SQLAlchemy calls the `set` column `book_set`, as the ledger's
  evals do (`eval_set`).
- **Nothing here is read by the readers yet.** They move over in the cut-over phase, after the backfill is
  verified. Until then `thorp/manifest.py` still reads `manifest.sqlite`.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import BigInteger, Float, ForeignKey, Index, Integer, Text, delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Mapped, mapped_column

from thorp.viable.s3_control.models import Base

SCHEMA = "s1"

# the SQLite books columns, in their own order (thorp/manifest.py), so a row copies field for field
BOOK_COLUMNS = ("id", "source", "title", "author", "language", "family", "text", "chars", "bytes", "sha1", "fetched_at", "set")


def _book_values(r: dict) -> dict:
    """A books row keyed by the model's attributes: the SQLite column `set` is the attribute `book_set`."""
    return {
        "id": r["id"],
        "source": r["source"],
        "title": r["title"],
        "author": r["author"],
        "language": r["language"],
        "family": r["family"],
        "text": r["text"],
        "chars": r["chars"],
        "bytes": r["bytes"],
        "sha1": r["sha1"],
        "fetched_at": r["fetched_at"],
        "book_set": r["set"],
    }


class Book(Base):
    """One book in the register (its source, the text it names, its measures and the shelf it belongs to)."""

    __tablename__ = "books"
    __table_args__ = (Index("books_source", "source"), {"schema": SCHEMA})

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    family: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str | None] = mapped_column(Text)
    chars: Mapped[int | None] = mapped_column(Integer)
    bytes: Mapped[int | None] = mapped_column(Integer)
    sha1: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[str | None] = mapped_column(Text)
    book_set: Mapped[str | None] = mapped_column("set", Text)


class BookMeasure(Base):
    """A book's trigram measures (data/trigrams.csv): repeat rate, variety, words, name repetition."""

    __tablename__ = "book_measures"
    __table_args__ = (Index("book_measures_book", "book_id"), {"schema": SCHEMA})

    book_id: Mapped[str] = mapped_column(Text, ForeignKey(f"{SCHEMA}.books.id", ondelete="CASCADE"), primary_key=True)
    repeat_rate: Mapped[float | None] = mapped_column(Float)
    variety: Mapped[float | None] = mapped_column(Float)
    words: Mapped[int | None] = mapped_column(Integer)
    name_repeat: Mapped[float | None] = mapped_column(Float)
    name_density: Mapped[float | None] = mapped_column(Float)


class List(Base):
    """One hand-written list (`ships/lists/*.csv`), the shelf a fitout's recipe names."""

    __tablename__ = "lists"
    __table_args__ = ({"schema": SCHEMA})

    path: Mapped[str] = mapped_column(Text, primary_key=True)


class ListResolution(Base):
    """One title of a list, and the book it resolved to (or none): data/resolution.csv and unresolved.csv."""

    __tablename__ = "list_resolutions"
    __table_args__ = (Index("list_resolutions_list", "list"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    list: Mapped[str] = mapped_column(Text, ForeignKey(f"{SCHEMA}.lists.path", ondelete="CASCADE"))
    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    chosen: Mapped[str | None] = mapped_column(Text)  # a manifest book id, or None when unresolved
    how: Mapped[str | None] = mapped_column(Text)
    n_candidates: Mapped[int | None] = mapped_column(Integer)
    candidates: Mapped[str | None] = mapped_column(Text)


class ListRow(Base):
    """One row of a hand-written shelf (`ships/lists/*.csv`): its title, and the book when the list
    names one. The resolutions for the fitout lists live in `list_resolutions`; these are the shelf's
    own rows, so a shelf summary can be a join rather than a CSV read and a title resolver."""

    __tablename__ = "list_rows"
    __table_args__ = (Index("list_rows_list", "list"), {"schema": SCHEMA})

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    list: Mapped[str] = mapped_column(Text)
    ordinal: Mapped[int] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(Text)
    language: Mapped[str | None] = mapped_column(Text)
    family: Mapped[str | None] = mapped_column(Text)
    book: Mapped[str | None] = mapped_column(Text)  # a manifest book id, when the list names its text


def tables() -> list:
    """The tables this module defines, for the test fixtures' truncate."""
    return [m.local_table for m in Base.registry.mappers if m.class_.__module__ == __name__]


def put_book(s, book: dict) -> None:
    """Upsert one book (the SQLite `insert ... on conflict(id) do update`)."""
    values = _book_values(book)
    stmt = insert(Book).values(**values)
    # stmt.excluded is keyed by column names, so `set` is "set" (not the attribute name `book_set`)
    updates = {c: getattr(stmt.excluded, c) for c in BOOK_COLUMNS if c != "id"}
    s.execute(stmt.on_conflict_do_update(index_elements=["id"], set_=updates))


# ---------------------------------------------------------------- the backfill


def _csv_rows(name: str) -> list[dict]:
    """data/<name> as a list of dicts (empty when the file is not there, as in a fresh test data dir)."""
    import csv

    from thorp import paths

    p = paths.data_dir() / name
    if not p.exists():
        return []
    with p.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if any(v for v in r.values())]


def backfill(only: list[str] | None = None, source: Path | None = None, log=print) -> dict:
    """Copy `data/manifest.sqlite` and the library CSVs into `s1`. Idempotent, read-only.

    The books come from the manifest (the `only` list filters them for tests); the trigram measures, the
    lists and their resolutions come from `data/trigrams.csv`, `data/resolution.csv` and `data/unresolved.csv`
    in full (they are small, and not keyed by the `only` books). Returns per-table counts for the caller to
    check against the files.
    """
    import sqlite3

    from thorp import paths, store

    counts = {"books": 0, "book_measures": 0, "lists": 0, "list_resolutions": 0}

    src = source or paths.manifest_path()
    con = sqlite3.connect(f"file:{src}?mode=ro", uri=True, check_same_thread=False, timeout=2.0)
    con.row_factory = sqlite3.Row
    if only:
        marks = ",".join("?" * len(only))
        books = [dict(r) for r in con.execute(f"select * from books where id in ({marks})", only)]
    else:
        books = [dict(r) for r in con.execute("select * from books order by id")]
    con.close()

    measures = []
    for r in _csv_rows("trigrams.csv"):
        if not r.get("name_repeat") or not r.get("name_density"):
            continue  # a row written before the name measures existed: measured again, not copied
        measures.append({
            "book_id": r["book"], "repeat_rate": float(r["repeat_rate"]), "variety": float(r["variety"]),
            "words": int(r["words"]), "name_repeat": float(r["name_repeat"]), "name_density": float(r["name_density"]),
        })

    resolutions = []
    for r in _csv_rows("resolution.csv"):
        resolutions.append({
            "list": r["list"], "title": r.get("title") or None, "author": r.get("author") or None,
            "language": r.get("language") or None,
            "chosen": f"pg{r['chosen']}" if (r.get("chosen") or "").isdigit() else None,
            "how": r.get("how") or None,
            "n_candidates": int(r["n_candidates"]) if (r.get("n_candidates") or "").isdigit() else None,
            "candidates": r.get("candidates") or None,
        })
    # unresolved.csv has no header: list, title, author, language (thorp/sources/gutenberg.py)
    import csv as _csv

    up = paths.data_dir() / "unresolved.csv"
    if up.exists():
        with up.open(encoding="utf-8") as f:
            for row in _csv.reader(f):
                if not any(row):
                    continue
                list_name, title, author, language = (row + ["", "", "", ""])[:4]
                resolutions.append({
                    "list": list_name, "title": title or None, "author": author or None,
                    "language": language or None,
                    "chosen": None, "how": None, "n_candidates": None, "candidates": None,
                })
    lists = sorted({r["list"] for r in resolutions})

    with store.session() as s:
        for r in books:
            put_book(s, r)
        counts["books"] = len(books)
        for r in measures:
            s.execute(insert(BookMeasure).values(**r).on_conflict_do_nothing())
        counts["book_measures"] = len(measures)
        for p in lists:
            s.execute(insert(List).values(path=p).on_conflict_do_nothing())
        counts["lists"] = len(lists)
        s.execute(delete(ListResolution))
        if resolutions:
            s.execute(insert(ListResolution), resolutions)
        counts["list_resolutions"] = len(resolutions)
    log(
        f"library: {counts['books']} books, {counts['book_measures']} measures, "
        f"{counts['lists']} lists, {counts['list_resolutions']} resolutions"
    )
    return counts


def verify(source: Path | None = None, log=print) -> bool:
    """The manifest's and the CSVs' row counts match `s1`."""
    import sqlite3

    from thorp import paths, store

    src = source or paths.manifest_path()
    con = sqlite3.connect(f"file:{src}?mode=ro", uri=True, check_same_thread=False, timeout=2.0)
    n_books = con.execute("select count(*) from books").fetchone()[0]
    con.close()

    n_measures = len([r for r in _csv_rows("trigrams.csv") if r.get("name_repeat") and r.get("name_density")])
    n_resolved = len(_csv_rows("resolution.csv"))
    # unresolved.csv has no header: one line per unresolved title
    import csv as _csv

    lists: set[str] = {r["list"] for r in _csv_rows("resolution.csv")}
    n_unresolved = 0
    up = paths.data_dir() / "unresolved.csv"
    if up.exists():
        with up.open(encoding="utf-8") as f:
            for row in _csv.reader(f):
                if any(row):
                    n_unresolved += 1
                    lists.add(row[0])
    n_resolutions = n_resolved + n_unresolved
    n_lists = len(lists)

    with store.session() as s:
        got = {
            "books": s.scalar(select(func.count()).select_from(Book)),
            "book_measures": s.scalar(select(func.count()).select_from(BookMeasure)),
            "lists": s.scalar(select(func.count()).select_from(List)),
            "list_resolutions": s.scalar(select(func.count()).select_from(ListResolution)),
        }
    want = {"books": n_books, "book_measures": n_measures, "lists": n_lists, "list_resolutions": n_resolutions}
    ok = got == want
    log(f"library: {got} vs {want}: {'ok' if ok else 'MISMATCH'}")
    return ok


def _shelf_book(text: str | None) -> str | None:
    """The book a shelf row names: `local:pg10557` is the manifest's `pg10557`; a bare `pg…` is itself."""
    t = (text or "").strip()
    if not t:
        return None
    if ":" in t:
        prefix, rest = t.split(":", 1)
        return rest if prefix in ("local", "gutenberg", "pg") and rest else None
    return t if t.startswith("pg") else None


def backfill_shelves(log=print) -> dict:
    """Copy every hand-written shelf (`ships/lists/*.csv`, `stores/*.csv`) into `s1.list_rows`.

    Idempotent: each shelf's rows are replaced. The book id comes from the list's `text` column
    (`local:pg10557`), so the shelf summary is a join to `books` and `library_facts`, with no CSV read
    and no title resolution at read time.
    """
    import csv

    from thorp import paths, store

    ListRow.__table__.create(store.engine(), checkfirst=True)
    base = paths.resolve("lists")
    files = sorted(base.glob("*.csv")) + sorted((base / "stores").glob("*.csv"))
    counts = {"lists": 0, "rows": 0, "resolved": 0}
    with store.session() as s:
        for p in files:
            if p.stat().st_size > 20_000_000:  # a synthetic deck, not a shelf of books
                continue
            rel = "lists/" + str(p.relative_to(base))
            s.execute(delete(ListRow).where(ListRow.list == rel))
            rows: list[ListRow] = []
            with p.open(encoding="utf-8") as f:
                for i, r in enumerate(csv.DictReader(f)):
                    if not any((v or "").strip() for v in r.values()):
                        continue
                    rows.append(ListRow(
                        list=rel, ordinal=i, title=(r.get("title") or None), author=(r.get("author") or None),
                        language=(r.get("language") or None), family=(r.get("family") or None),
                        book=_shelf_book(r.get("text")),
                    ))
            s.add_all(rows)
            counts["lists"] += 1
            counts["rows"] += len(rows)
            counts["resolved"] += sum(1 for r in rows if r.book)
    log(f"shelves: {counts['lists']} lists, {counts['rows']} rows, {counts['resolved']} with a book")
    return counts


# ---------------------------------------------------------------- the readers (for the cut-over)


def get_book(book_id: str) -> dict | None:
    """One book's row (the columns `manifest.get` returns), or None."""
    from thorp import store

    with store.session() as s:
        r = s.get(Book, book_id)
    return {c: getattr(r, c if c != "set" else "book_set") for c in BOOK_COLUMNS} if r else None


def all_books() -> list[dict]:
    """Every book, ordered by id, as `manifest.all_books` returns it."""
    from thorp import store

    with store.session() as s:
        rows = s.scalars(select(Book).order_by(Book.id)).all()
    return [{c: getattr(r, c if c != "set" else "book_set") for c in BOOK_COLUMNS} for r in rows]


def book_measures() -> dict[str, dict]:
    """book id -> its trigram measures, as `trigrams._cache` returns them (the rows with name measures)."""
    from thorp import store

    with store.session() as s:
        rows = s.scalars(select(BookMeasure)).all()
    return {
        r.book_id: {
            "repeat_rate": r.repeat_rate, "variety": r.variety, "words": r.words,
            "name_repeat": r.name_repeat, "name_density": r.name_density,
        }
        for r in rows
    }


def resolved_lists() -> dict[str, list[str]]:
    """list path -> manifest book ids, as `library._resolved` returns them (chosen rows, in CSV order)."""
    from thorp import store

    with store.session() as s:
        rows = s.scalars(select(ListResolution).where(ListResolution.chosen.isnot(None)).order_by(ListResolution.id)).all()
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(r.list, []).append(r.chosen)
    return out

"""Gather: acquisition's S1 for a corpus too big to list, through the same S3 gate.

An **intake** (thorp/acquisition.py) takes a CSV of books and fetches each one. A **gather** is the
same operation over a bulk source (thorp/sources/bulk.py): it reads the source's records one at a
time, puts each through the intake gate, and writes the admitted ones where every book lives
(data/texts/<source>/, the manifest). The gate is not reimplemented here. A gather uses
`acquisition.admit`, records its verdicts in s1.intakes and s1.intake_verdicts, takes the same S2
intake lock, and obeys S5's switch "intake".

The order matters:

1. **Before the fetch** the record's own words and dates are judged: the source is admitted, the
   book is English, printed before 1930, its people died by 1955, it is not a held-out deck book by
   title.
2. **After the fetch** the text is judged too: it cleans, it is not a duplicate by SHA-1, it is not a
   deck's text under another name (shingle overlap, the plan's "protect the decks by text"), and its
   title and author are not already in the library.

A book the gate refuses is not written. A dry run fetches nothing and writes nothing, but the
records are read, so the gate's verdicts are the ones a real gather would give.

    uv run thorp gather --list
    uv run thorp gather common-pile-pre-1929 --limit 100 --dry-run
    uv run thorp gather common-pile-pre-1929 --limit 500
    uv run thorp gather blbooks --limit 100
    uv run thorp gather archive --collection americana --limit 25
"""

from __future__ import annotations

import csv
import hashlib
import time
from pathlib import Path

from thorp import acquisition, manifest, paths
from thorp.sources import base, bulk, catalog

BYTES_PER_TOKEN = acquisition.BYTES_PER_TOKEN


def _intake_id() -> str:
    return "g-" + time.strftime("%Y%m%d-%H%M%S")


def _rec(key: str, src, dry_run: bool) -> dict:
    return {
        "id": _intake_id(),
        "list": f"bulk:{key}",
        "set": "recipe",
        "dry_run": dry_run,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "finished": None,
        "status": "taking in",
        "counts": {
            "admitted": 0,
            "known": 0,
            "refused": 0,
            "failed": 0,
            "unresolved": 0,
            "would fetch": 0,
            "read": 0,
        },
        "refused_by_rule": {},
        "bytes": 0,
        "gate_enforced": acquisition.enforced(),
        "source": key,
        "source_name": src.name,
    }


def run(
    key: str,
    *,
    limit: int | None = None,
    offset: int = 0,
    dry_run: bool = False,
    allow_unsigned: bool = False,
    authority: bool = False,
    set_name: str = "recipe",
    log=print,
    **source_kw,
) -> dict:
    """S1: one bulk intake. `limit` bounds the records read (not the books admitted); `offset` skips
    records, for a second pass over a shard that was cut short."""
    src = bulk.source(key)
    entry = catalog.get(key)
    unsigned_gather = entry["status"] == "awaits S5 (unsigned work)" and allow_unsigned
    if entry["status"] != "admitted" and not unsigned_gather:
        raise PermissionError(f"{key} is {entry['status']}: {entry.get('wall', 'not admitted')}")
    if src.unsigned and not allow_unsigned:
        raise PermissionError(
            f"{key}'s records are unsigned, so the death rule cannot speak to them. The proposed "
            "'signed' rule has not been adopted by S5. Pass --allow-unsigned to gather them as a "
            "separate branch, with the printing date as the only period evidence."
        )
    rec = _rec(key, src, dry_run)
    rec["set"] = set_name
    rec["unsigned"] = bool(src.unsigned)
    with acquisition._intake_lock(rec["id"], f"bulk:{key}", log):
        acquisition._write_intake(rec)
        try:
            for b in src.books(limit=limit, offset=offset, **source_kw):
                rec["counts"]["read"] += 1
                _one(b, key, src, rec, dry_run, set_name, authority, log)
                if rec["counts"]["read"] % 25 == 0:
                    acquisition._write_intake(rec)
        finally:
            rec["status"] = "home"
            rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            acquisition._write_intake(rec)
    c = rec["counts"]
    log(
        f"gather {rec['id']} from {key}: read {c['read']}, admitted {c['admitted']}, "
        f"already here {c['known']}, refused {c['refused']}, failed {c['failed']}"
        + (f", {c['would fetch']} would be admitted (dry run)" if dry_run else "")
        + f", {rec['bytes'] / 1e6:.1f} MB"
    )
    return rec


def _one(
    b: bulk.BulkBook,
    key: str,
    src,
    rec: dict,
    dry_run: bool,
    set_name: str,
    authority: bool,
    log,
) -> None:
    book_id = f"{src.prefix}{bulk.safe_id(b.ident)}"
    c = acquisition.Candidate(
        book_id=book_id,
        title=b.title,
        authors=b.authors,
        language=b.language or "",
        set=set_name,
        source=key,
        ref=f"{key}:{b.ident}",
        published=b.published,
        origin=b.origin,
        text=b.text,
        sha1=hashlib.sha1(b.text.encode("utf-8")).hexdigest(),
    )
    if authority:
        _resolve_dates(c)
    if manifest.get(book_id) is not None:
        rec["counts"]["known"] += 1
        acquisition._append_log(acquisition._entry(c, "known", None, rec["id"], "gather"))
        return
    v = acquisition.admit(c, ("before fetch",))
    if not v.admitted:
        _refused(c, v, rec, log)
        return
    if dry_run:
        rec["counts"]["would fetch"] += 1
        acquisition._append_log(acquisition._entry(c, "would fetch", v, rec["id"], "gather"))
        return
    try:
        f = base.Fetched(
            title=c.title,
            author=c.authors,
            language=c.language or "en",
            text=c.text or b.text,
            published=c.published,
            origin=c.origin,
        )
        v = acquisition.admit(c)  # every rule again, now with the text
        if not v.admitted:
            _refused(c, v, rec, log)
            return
        book = base.register_text(
            key, book_id, f, set_name=set_name, observe=False, how="thorp gather"
        )
    except Exception as e:  # noqa: BLE001  (one bad record must not stop a corpus)
        rec["counts"]["failed"] += 1
        acquisition._append_log(
            acquisition._entry(c, "failed", None, rec["id"], "gather", error=str(e)[:300])
        )
        log(f"  failed   {book_id}: {e}")
        return
    rec["counts"]["admitted"] += 1
    rec["bytes"] += book.bytes
    acquisition.note_edition(book)
    acquisition._append_log(
        acquisition._entry(
            c, "admitted", v, rec["id"], "gather", bytes=book.bytes, title=book.title
        )
    )
    if rec["counts"]["admitted"] % 25 == 0:
        log(f"  {rec['counts']['admitted']} admitted, {rec['bytes'] / 1e6:.1f} MB")


def _refused(c: acquisition.Candidate, v, rec: dict, log) -> None:
    """Record a refusal; don't print one line a book in a corpus of thousands."""
    acquisition._refuse(c, v, rec, lambda *a: None)
    if rec["counts"]["refused"] % 250 == 0:
        log(f"  {rec['counts']['refused']} refused so far ({rec['counts']['admitted']} admitted)")


def _resolve_dates(c: acquisition.Candidate) -> None:
    """Fill an undated person's death year from the authority lookup, when the book is not already old
    enough for the undated reading (printed before 1870)."""
    if c.published is not None and c.published < acquisition.UNDATED_PRINTED_BEFORE:
        return
    from thorp.sources import authority

    for p in acquisition.persons(c.authors):
        if p.died is None:
            got = authority.lookup(p.name)
            if got:
                c.resolved[p.name] = got
    if c.resolved:
        c.authors = acquisition.with_dates(c.authors, c.resolved)


def export_list(key: str, path: str) -> int:
    """Write the books gathered from `key` as a list a branch can read: rows are `<key>:<identifier>`
    references, so `library._ids` resolves them back to their manifest ids. Returns the rows written."""
    src = bulk.source(key)
    books = [b for b in manifest.all_books() if b.source == key]
    families = {"la": "Classical", "lat": "Classical", "grc": "Classical", "gre": "Classical", "el": "Classical",
                "ita": "Romance", "fre": "Romance", "fra": "Romance", "spa": "Romance", "por": "Romance",
                "ger": "Germanic", "deu": "Germanic", "dut": "Germanic", "nld": "Germanic", "eng": "Germanic"}
    out = paths.resolve(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "author", "language", "family", "text"])
        for b in sorted(books, key=lambda x: x.id):
            ident = b.id[len(src.prefix):] if b.id.startswith(src.prefix) else b.id
            w.writerow([b.title, b.author, b.language, families.get(b.language, "Other"), f"{key}:{ident}"])
    return len(books)


def _in_library(source: str) -> dict:
    bs = [b for b in manifest.all_books() if b.source == source]
    return {
        "books": len(bs),
        "bytes": sum(b.bytes or 0 for b in bs),
        "tokens": int(sum(b.bytes or 0 for b in bs) / BYTES_PER_TOKEN),
    }


def status() -> list[dict]:
    """Every source in S4's catalogue with what the pipeline can do with it now, and what is already
    in the library."""
    adapters = bulk.bulk_sources()
    out = []
    for s in catalog.SOURCES:
        row = dict(s)
        row["adapter_ready"] = bool(s.get("adapter") and s["adapter"] in adapters)
        row["in_library"] = _in_library(s["key"])
        row["wall"] = s.get("wall", "")
        out.append(row)
    return out


def plan(limit: int | None = None) -> list[dict]:
    """For each fetchable source, the catalogue's estimate and the share a pilot of `limit` records
    would sample: records times the mean book's bytes. It is a plan, not a measurement."""
    rows = []
    for s in catalog.SOURCES:
        if s["status"] != "admitted" or not s.get("adapter") or not s.get("books"):
            continue
        books = s.get("books") or 0
        tokens = s.get("tokens") or [0, 0]
        mean_tokens = (sum(tokens) / 2 / books) if books and tokens[0] else None
        rows.append(
            {
                "key": s["key"],
                "name": s["name"],
                "books": books,
                "after_rule_tokens": tokens,
                "sample_records": limit,
                "sample_tokens_est": int(limit * mean_tokens) if limit and mean_tokens else None,
                "how": s["how"],
            }
        )
    return rows


def summary() -> dict:
    """For acquisition's own S1: what the gathers have brought in, by source."""
    books = manifest.all_books()
    by_source = {}
    for b in books:
        if b.source in ("gutenberg", "local"):
            continue
        g = by_source.setdefault(b.source, {"books": 0, "bytes": 0})
        g["books"] += 1
        g["bytes"] += b.bytes or 0
    return {
        "sources": len(by_source),
        "books": sum(g["books"] for g in by_source.values()),
        "bytes": sum(g["bytes"] for g in by_source.values()),
        "by_source": by_source,
    }


def text_path(book_id: str) -> Path:
    """Where a gathered book's text lives, for a reader that has only its manifest id."""
    b = manifest.get(book_id)
    if b is None:
        raise KeyError(book_id)
    return paths.texts_dir(b.source) / f"{b.id}.txt"

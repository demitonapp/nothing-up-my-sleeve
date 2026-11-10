"""Ogden v0.1.4: v0.1.3 with the control tokens actually exercised, stamped as 618 local books.

The problem (10 November): v0.1.3 declares ten control symbols but only ever uses five. `<bos>/<eos>` wrap
every book, eleven catechisms carry `<question>/<answer>/<end>`, and `<premise>`, `<conclusion>` and `<sep>`
never appear — so on a chaining expedition the two markers that matter are dead embeddings.

The fix: keep v0.1.3's 592 books exactly as they are, and add the logic tutor's passages at `--share` of the
words (Ogden v0.2's slice is 7.5%; this is 5%). Every tutor passage is two or more facts and the conclusion
that needs them, so each fact is marked `<premise> ... <sep>` and the last sentence `<conclusion> ... <end>`.
The ten declared symbols are then all exercised: bos, eos, sep, premise, conclusion, question, answer, end
(pad and unk are special and carry no text).

Why every book is stamped as a local book: the trainer reads a recipe row by resolving it to a **book id** and
reading that book's text (`Tokeniser.text` -> `load_text` -> the book's source), never the row's inline text.
A row that names no book is unresolved, and a recipe of mixed inline rows and refs cannot resolve both (the
title matcher only knows Gutenberg, the ref path only runs when *every* row is a ref). So each of the 618
documents is written under data/texts/local, registered in the register's two stores, and the list is 618
`local:` refs read with `clean: raw` — the stamp is what the ship reads.

    python backend/scripts/make_ogden_v014.py [--base ships/lists/ogden-v0.1.3.csv]
                                              [--tutor ships/lists/ogden-v0.2-tutor.csv]
                                              [--share 0.05]

Writes ships/lists/ogden-v0.1.4.csv, its .manifest.json, and data/texts/local/ogden-v014-*.txt /
tutor-v014-*.txt.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pathlib
import re
import sys
from dataclasses import asdict

ROOT = pathlib.Path(__file__).resolve().parents[2]
csv.field_size_limit(10**9)  # a stamped book is one field, and some run past csv's 128 KB default

_SENT = re.compile(r"(?<=[.!?])\s+")


def _load_tutor(id_: str) -> str:
    sys.path.insert(0, str(ROOT / "backend"))
    from thorp.sources import load_text

    return load_text(id_, "raw")


def mark_passage(passage: str) -> str:
    """A tutor passage with its facts as premises and its last sentence as the conclusion."""
    sents = [s.strip() for s in _SENT.split(passage.strip()) if s.strip()]
    if len(sents) < 2:
        return f"<conclusion> {passage.strip()} <end>"
    out = [f"<premise> {s} <sep>" for s in sents[:-1]]
    out.append(f"<conclusion> {sents[-1]} <end>")
    return " ".join(out)


def mark_document(text: str) -> str:
    """One tutor book: each passage marked, the whole document wrapped <bos> ... <eos>."""
    passages = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    body = "\n\n".join(mark_passage(p) for p in passages)
    return f"<bos>\n{body}\n<eos>"


def build(base: pathlib.Path, tutor: pathlib.Path, share: float, log=print) -> dict:
    from thorp import manifest, manifest_store, paths, store

    with base.open(encoding="utf-8", newline="") as f:
        books = list(csv.DictReader(f))
    fields = ["title", "author", "language", "family", "text"]
    base_words = sum(len((r.get("text") or "").split()) for r in books)

    with tutor.open(encoding="utf-8", newline="") as f:
        tutor_rows = list(csv.DictReader(f))

    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)

    def stamp(bid: str, title: str, author: str, language: str, family: str, text: str, about: str) -> dict:
        (d / f"{bid}.txt").write_text(text, encoding="utf-8")
        data = text.encode("utf-8")
        book = manifest.Book(
            id=bid, source="local", title=title, author=author, language=language, family=family,
            text=about, chars=len(text), bytes=len(data), sha1=hashlib.sha1(data).hexdigest(),
            fetched_at="", set="recipe",
        )  # fmt: skip
        manifest.upsert(book)
        pg.append(asdict(book))
        return {"title": title, "author": author, "language": language, "family": family, "text": f"local:{bid}"}

    rows, pg = [], []
    for i, r in enumerate(books, 1):
        rows.append(
            stamp(
                f"ogden-v014-{i:03d}", r["title"], r["author"], r["language"], r["family"],
                r["text"], "derived: Ogden v0.1.3 stamped text (marks-v1), read raw (v0.1.4)",
            )
        )  # fmt: skip

    want = int(base_words * share)
    added_words = 0
    for i, r in enumerate(tutor_rows, 1):
        if added_words >= want:
            break
        text = _load_tutor((r.get("text") or "").split(":")[-1])
        marked = mark_document(text)
        rows.append(
            stamp(
                f"tutor-v014-{i:03d}", f"The logic tutor's passages, book {i} (marked)",
                "Thorp's logic tutor", "en", "Germanic", marked,
                "derived: logic tutor template writer, marked premise/conclusion (v0.1.4)",
            )
        )  # fmt: skip
        added_words += len(text.split())

    with store.session() as s:
        for book in pg:
            manifest_store.put_book(s, book)

    dst = ROOT / "ships" / "lists" / "ogden-v0.1.4.csv"
    with dst.open("w", encoding="utf-8", newline="") as g:
        w = csv.DictWriter(g, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    counts = {s: 0 for s in ("bos", "eos", "sep", "premise", "conclusion", "question", "answer", "end")}
    for r in rows:
        text = (d / f"{r['text'].split(':', 1)[1]}.txt").read_text(encoding="utf-8")
        for s in counts:
            counts[s] += text.count(f"<{s}>")
    manifest_row = {
        "version": "ogden-v0.1.4",
        "from": "ogden-v0.1.3",
        "transform": "tutor-marks",
        "about": "v0.1.3's 592 stamped books plus the logic tutor's passages at "
                 f"{share:.0%} of the words, each fact as <premise> and the conclusion as <conclusion>",
        "generator": "backend/scripts/make_ogden_v014.py",
        "read_as": "clean: raw (each book is stamped; the list is 618 local refs)",
        "books": len(rows),
        "base_books": len(books),
        "tutor_books": len(rows) - len(books),
        "base_words": base_words,
        "tutor_words": added_words,
        "share": round(added_words / base_words, 4),
        "symbol_counts": counts,
        "sha1": hashlib.sha1(dst.read_bytes()).hexdigest(),
    }
    dst.with_suffix(".manifest.json").write_text(json.dumps(manifest_row, indent=1) + "\n")
    log(f"ogden-v0.1.4: {len(rows)} books ({len(rows) - len(books)} tutor), {added_words:,} tutor words "
        f"({added_words / base_words:.1%})")
    log(f"  symbols: {counts}")
    return manifest_row


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="ships/lists/ogden-v0.1.3.csv")
    ap.add_argument("--tutor", default="ships/lists/ogden-v0.2-tutor.csv")
    ap.add_argument("--share", type=float, default=0.05)
    a = ap.parse_args()
    m = build(ROOT / a.base, ROOT / a.tutor, a.share)
    missing = [s for s in ("premise", "conclusion", "sep", "question", "answer", "end") if not m["symbol_counts"][s]]
    print("every content symbol exercised:", not missing, "missing:", missing)
    return 0 if not missing else 1


if __name__ == "__main__":
    raise SystemExit(main())

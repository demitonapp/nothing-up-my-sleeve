"""Ogden v0.1, doubled: the 300k charter's "more to read" shelf (14 November 2026; Justin: "I thought the research says
you don't get anything from more than 4 readings of the same stuff, so I'd rather add more content").

Ogden v0.1's 592 books, and as much again of new books chosen by v0.1's own rule: the books Ogden v0.2 added to the
library at Ogden-ness 68% or more (backend/scripts/make_ogden_v02.py scored every English recipe book, one copy per
title, the King James Bible struck), most Ogden first, until the new books hold as many characters as v0.1. No logic
tutor passages: those are v0.2's other change, and they would be a second difference. Judge books are refused by the
voyage as always.

Read four times, it is the same tokens as eight passes of v0.1 (the eight-pass arm), so fresh text and repeated text are
compared at the same cost.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/make_ogden_double.py
Writes ships/lists/ogden-v0.1-double.csv and its .manifest.json.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from sqlalchemy import text

from thorp import store

ROOT = Path(__file__).resolve().parents[2]
LISTS = ROOT / "ships/lists"
V1, V2, SCORES = LISTS / "ogden-v0.1.csv", LISTS / "ogden-v0.2-books.csv", LISTS / "ogden-v0.2-scores.csv"
OUT = LISTS / "ogden-v0.1-double.csv"
FIELDS = ["title", "author", "language", "family", "text"]


def chars(ids: list[str]) -> dict[str, int]:
    with store.session() as s:
        rows = s.execute(text("select id, chars from s1.books where id = any(:ids)"), {"ids": ids}).all()
    return {i: int(c or 0) for i, c in rows}


def main() -> int:
    v1 = list(csv.DictReader(open(V1, encoding="utf-8")))
    v1_ids = {r["text"] for r in v1}
    new = [r for r in csv.DictReader(open(V2, encoding="utf-8")) if r["text"] not in v1_ids]
    ogden = {r["book"]: float(r["ogden"]) for r in csv.DictReader(open(SCORES, encoding="utf-8"))}
    size = chars([r["text"].split(":", 1)[1] for r in v1 + new])
    target = sum(size.get(r["text"].split(":", 1)[1], 0) for r in v1)
    new.sort(key=lambda r: (-ogden.get(r["text"].split(":", 1)[1], 0.0), r["text"]))
    taken, got = [], 0
    for r in new:
        if got >= target:
            break
        c = size.get(r["text"].split(":", 1)[1], 0)
        if not c:
            continue
        taken.append(r)
        got += c
    rows = [{k: r[k] for k in FIELDS} for r in v1 + taken]
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    lowest = min(ogden.get(r["text"].split(":", 1)[1], 0.0) for r in taken) if taken else None
    meta = {
        "version": "ogden-v0.1-double",
        "generator": "backend/scripts/make_ogden_double.py",
        "about": "Ogden v0.1's books and as much again of the books Ogden v0.2 added at Ogden-ness 68% or more, most Ogden first",
        "books": len(rows), "v0.1_books": len(v1), "new_books": len(taken),
        "v0.1_chars": target, "new_chars": got, "lowest_new_ogden": lowest,
        "sha1": hashlib.sha1(OUT.read_bytes()).hexdigest(),
    }  # fmt: skip
    OUT.with_suffix(".manifest.json").write_text(json.dumps(meta, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(meta, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

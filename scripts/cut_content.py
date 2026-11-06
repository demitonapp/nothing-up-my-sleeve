"""Cut the content experiment's shelves to the same bytes (2026-11-06; rule in DECISIONS.md).

B is the smallest shelf's whole size over the fetched books. Curated shelves take their books in
catalogue order (lowest id first) and random shelves in draw order, skipping a book that would take
the shelf past B by more than 2%, until the shelf is within 2% of B. Writes lists/content-<shelf>.csv
and prints each shelf's books, bytes and largest-work share.
Usage: uv run python scripts/cut_content.py
"""

from __future__ import annotations

import csv
from pathlib import Path

from thorp import manifest
from thorp.sources import gutenberg as g

ROOT = Path(__file__).resolve().parents[1]
SHELVES = ["greek", "islamic", "renaissance", "about", "random-1", "random-2", "random-3"]
TOL = 0.02


def fetched(name):
    rows = list(csv.DictReader(open(ROOT / f"lists/content-{name}-draft.csv", encoding="utf-8")))
    res = {r.row.title: r.chosen for r in g.resolve_list(ROOT / f"lists/content-{name}-draft.csv")}
    out = []
    for r in rows:
        gid = res.get(r["title"])
        try:
            b = manifest.get(f"pg{gid}") if gid else None
        except KeyError:  # not fetched (no plain text, or unresolved): not on the shelf
            b = None
        if b is not None and b.bytes > 0:
            out.append({**r, "gid": gid, "bytes": b.bytes})
    if not name.startswith("random"):
        out.sort(key=lambda r: r["gid"])
    return out


def main():
    shelves = {n: fetched(n) for n in SHELVES}
    totals = {n: sum(r["bytes"] for r in rows) for n, rows in shelves.items()}
    B = min(totals.values())
    print(f"budget B = {B / 1e6:.2f} MB (smallest shelf: {min(totals, key=totals.get)})")
    for n, rows in shelves.items():
        take, total = [], 0
        for r in rows:
            if total + r["bytes"] > B * (1 + TOL):
                continue
            take.append(r)
            total += r["bytes"]
            if total >= B * (1 - TOL):
                break
        works = {}
        for r in take:
            works[r["work"]] = works.get(r["work"], 0) + r["bytes"]
        top = max(works, key=works.get)
        with open(ROOT / f"lists/content-{n}.csv", "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["title", "author", "language", "family", "text"])
            for r in take:
                w.writerow([r["title"], r["author"], r["language"], r["family"], r["text"]])
        print(f"{n:12} {len(take):3} books {total / 1e6:6.2f} MB  (of {totals[n] / 1e6:6.2f} fetched)  largest work {top} {works[top] / total:.0%}")


if __name__ == "__main__":
    main()

"""Cut the data-lever shelves (2026-11-06; DECISIONS.md, "The data levers").

    uv run python scripts/cut_levers.py

From Endeavour's shelf (lists/pool-400.csv, B bytes):
  lists/pool-800.csv  pool-400, then the unused books of lists/pool-draft.csv and then
                      lists/pool-draft-2.csv of at least 100 KB, lowest ids first, until 2B bytes
  lists/pool-200.csv  pool-400's books in one seeded shuffle, the first B/2 bytes
  lists/pool-100.csv  the first B/4 bytes of the same shuffle, so pool-100 sits inside pool-200
Every book that is a hole card (v1 or v2) or on the truths deck is left out, by Gutenberg id.
Books not yet fetched are skipped, so run this after the drafts are fetched.
"""

from __future__ import annotations

import csv
import random
import sqlite3

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)
from thorp.sources.gutenberg import resolve_list

FIELDS = ["title", "author", "language", "family", "text"]


def rows(path):
    with open(ROOT / path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def ids(path):
    return [r.chosen for r in resolve_list(ROOT / path)]


def write(path, out):
    with open(ROOT / path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)


def main() -> None:
    con = sqlite3.connect(ROOT / "data/manifest.sqlite")
    size = {b: n for b, n in con.execute("select id, bytes from books")}
    held = {
        g
        for p in ("lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/truths.csv")
        for g in ids(p)
        if g
    }

    def with_ids(path):
        return list(zip(rows(path), ids(path), strict=True))

    pool = with_ids("lists/pool-400.csv")
    B = sum(size.get(f"pg{g}", 0) for _, g in pool)
    seen = {g for _, g in pool}
    big, total = [r for r, _ in pool], B
    extra = [
        (r, g)
        for r, g in with_ids("lists/pool-draft.csv") + with_ids("lists/pool-draft-2.csv")
        if g and g not in seen and g not in held and size.get(f"pg{g}", 0) >= 100 * 1024
    ]
    for r, g in sorted(extra, key=lambda x: x[1]):
        if total >= 2 * B:
            break
        if g in seen:
            continue
        seen.add(g)
        big.append(r)
        total += size[f"pg{g}"]
    write("lists/pool-800.csv", big)
    print(f"pool-800: {len(big)} books, {total / 1e6:.1f} MB (target {2 * B / 1e6:.1f})")

    shuffled = pool[:]
    random.Random(20261106).shuffle(shuffled)
    for name, frac in (("pool-200", 0.5), ("pool-100", 0.25)):
        out, t = [], 0
        for r, g in shuffled:
            if t >= frac * B:
                break
            out.append(r)
            t += size.get(f"pg{g}", 0)
        write(f"lists/{name}.csv", out)
        print(f"{name}: {len(out)} books, {t / 1e6:.1f} MB (target {frac * B / 1e6:.1f})")


if __name__ == "__main__":
    main()

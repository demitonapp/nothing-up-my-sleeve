"""Cut the fetched pool draft into the recipes the next runs need, by bytes from the manifest.

    uv run python scripts/cut_pool.py [N] [MIN_KB]

Writes:
  lists/pool-N.csv            the hundred by reach plus the first draft books of at least MIN_KB,
                              lowest ids first, N books in all: the whole-pool shelf
  lists/pool-N-fiction.csv    the fiction-tagged books of that shelf, cut to the token budget
  lists/pool-N-nonfiction.csv the rest, cut to the same budget (bytes within 2%): the kind test
The two kind shelves are the same size in bytes, so a difference in hole-card score between them
is the kind of book and not the amount. Rows keep the list columns, so the resolver and the
overrides do the rest.
"""

from __future__ import annotations

import csv
import sqlite3
import sys

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)


def read(path):
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write(path, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(rows)


def main(n: int, min_kb: int) -> None:
    con = sqlite3.connect(ROOT / "data/manifest.sqlite")
    bytes_of = {t: b for t, b in con.execute("select title, bytes from books")}
    hundred = read(ROOT / "lists/hundred-by-reach.csv")
    draft = read(ROOT / "lists/pool-draft.csv")
    traits = {r["title"]: r for r in read(ROOT / "lists/traits.csv")}
    shelf = [r for r in hundred if r["title"] in bytes_of]
    for r in draft:
        if len(shelf) >= n:
            break
        if bytes_of.get(r["title"], 0) >= min_kb * 1024:
            shelf.append(r)
    write(ROOT / f"lists/pool-{n}.csv", shelf)
    fic = [r for r in shelf if traits.get(r["title"], {}).get("fiction") == "1"]
    non = [r for r in shelf if traits.get(r["title"], {}).get("fiction") == "0"]
    budget = min(sum(bytes_of[r["title"]] for r in fic), sum(bytes_of[r["title"]] for r in non))

    def cut(rows):
        out, total = [], 0
        for r in rows:  # lowest ids first, as the shelf is ordered
            if total + bytes_of[r["title"]] > budget * 1.02:
                continue
            out.append(r)
            total += bytes_of[r["title"]]
        return out, total

    fic_cut, fb = cut(fic)
    non_cut, nb = cut(non)
    write(ROOT / f"lists/pool-{n}-fiction.csv", fic_cut)
    write(ROOT / f"lists/pool-{n}-nonfiction.csv", non_cut)
    total = sum(bytes_of[r["title"]] for r in shelf)
    print(
        f"shelf {len(shelf)} books, {total / 1e6:.1f} MB; fiction {len(fic_cut)} books {fb / 1e6:.1f} MB;"
        f" non-fiction {len(non_cut)} books {nb / 1e6:.1f} MB (budget {budget / 1e6:.1f} MB)"
    )


if __name__ == "__main__":
    main(
        int(sys.argv[1]) if len(sys.argv) > 1 else 400,
        int(sys.argv[2]) if len(sys.argv) > 2 else 100,
    )

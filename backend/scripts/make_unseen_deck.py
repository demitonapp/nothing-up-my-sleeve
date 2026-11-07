"""Draw the unseen deck (2026-11-06; DECISIONS.md, "Thorp against Qwen"): period books that Qwen
3.8 27B cannot have trained on, for the bits-per-byte contest between the two.

    uv run python scripts/make_unseen_deck.py [N]

Rules: English text released on Gutenberg on or after 2026-08-05 (Qwen/Qwen3.8-27B's release
date on Hugging Face, so after its training data was gathered); every person in Authors with both
dates, born 1500 to 1880 and dead by 1955 (born by 1880 keeps the writing mostly before 1930,
which the catalogue cannot date); no periodicals, indexes or encyclopaedias. N books drawn in one
seeded shuffle, keeping those whose fetched text is 100 KB to 1 MB, so no single book dominates
the mean or the scoring time. Writes lists/unseen-qwen.csv with an override per row.
"""

from __future__ import annotations

import csv
import random
import re
import sys

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

RELEASED = "2026-08-05"
SKIP = re.compile(r"Periodicals|Index of|Magazine|Journal|Encyclop", re.I)
PERSON = re.compile(r"(\d{3,4})\??-(\d{3,4})\??")


def eligible(r: dict) -> bool:
    if r["Type"] != "Text" or r["Language"] != "en" or r["Issued"] < RELEASED:
        return False
    if SKIP.search(r["Title"] + r["Subjects"] + r["Bookshelves"]):
        return False
    people = [p.strip() for p in r["Authors"].split(";") if p.strip()]
    for p in people:
        m = PERSON.search(p)
        if (
            not m
            or "active" in p
            or not (1500 <= int(m.group(1)) <= 1880)
            or int(m.group(2)) > 1955
        ):
            return False
    return bool(people)


def main(n: int) -> None:
    rows = [
        r
        for r in csv.DictReader(open(ROOT / "data/catalogue/pg_catalog.csv", encoding="utf-8"))
        if eligible(r)
    ]
    random.Random(20260805).shuffle(rows)
    out = rows[: n * 3]  # candidates; the fetch and the size filter cut them to n
    with open(ROOT / "lists/unseen-qwen-candidates.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["title", "author", "language", "family", "text"])
        for r in out:
            title = " ".join(r["Title"].split())
            w.writerow(
                [title, r["Authors"].split(",")[0], "en", "Germanic", f"released {r['Issued']}"]
            )
    with open(ROOT / "lists/overrides.csv", "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        for r in out:
            w.writerow([" ".join(r["Title"].split()), r["Authors"].split(",")[0], r["Text#"]])
    print(f"{len(rows)} eligible; {len(out)} candidates written")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 16)

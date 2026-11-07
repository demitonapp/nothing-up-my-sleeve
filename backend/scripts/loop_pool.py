"""Build the book-value loop's pool and its book features (2026-11-07; DECISIONS.md, "The
book-value loop").

    uv run python scripts/loop_pool.py

Pool: every fetched English book on the hundred and the two pool drafts, at least 20 KB, that is
not a hole card (v1, v2), on the truths deck or a Forgotten Tome. Writes lists/loop-pool.csv (rows
copied from their source lists, so they resolve exactly) and data/loop/features.csv, one row per
book: book_id, title, bytes, family, kind (verse, fiction or nonfiction; verse first, so a verse
novel is verse), first_person, translated (the original's family is not Germanic, or the catalogue
names a translator), and stratum (kind x original/translated) for the sampler.
"""

from __future__ import annotations

import csv

from thorp import manifest
from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)
from thorp.sources.gutenberg import catalogue, resolve_list

SOURCES = ["lists/hundred-by-reach.csv", "lists/pool-draft.csv", "lists/pool-draft-2.csv"]
HELD = [
    "lists/hole-cards.csv",
    "lists/hole-cards-v2.csv",
    "lists/truths.csv",
    "lists/hole-cards-unseen.csv",
]
FIELDS = ["title", "author", "language", "family", "text"]


def main() -> None:
    held = {f"pg{r.chosen}" for p in HELD for r in resolve_list(ROOT / p) if r.chosen}
    traits = {
        r["title"]: r for r in csv.DictReader(open(ROOT / "lists/traits.csv", encoding="utf-8"))
    }
    authors = {f"pg{c['Text#']}": c["Authors"] for c in catalogue()}
    rows, feats, seen = [], [], set()
    for src in SOURCES:
        lrows = list(csv.DictReader(open(ROOT / src, encoding="utf-8")))
        for row, res in zip(lrows, resolve_list(ROOT / src), strict=True):
            if not res.chosen:
                continue
            b = f"pg{res.chosen}"
            book = manifest.get(b)
            if (
                b in seen
                or b in held
                or book is None
                or book.language != "en"
                or book.bytes < 20 * 1024
            ):
                continue
            seen.add(b)
            t = traits.get(row["title"], {})
            kind = (
                "verse"
                if t.get("verse") == "1"
                else "fiction"
                if t.get("fiction") == "1"
                else "nonfiction"
            )
            translated = row.get(
                "family", "Germanic"
            ) != "Germanic" or "[Translator]" in authors.get(b, "")
            rows.append({k: row.get(k, "") for k in FIELDS})
            feats.append(
                {
                    "book_id": b,
                    "title": book.title,
                    "bytes": book.bytes,
                    "family": row.get("family", ""),
                    "kind": kind,
                    "first_person": t.get("first_person", ""),
                    "translated": int(translated),
                    "stratum": f"{kind}/{'translated' if translated else 'original'}",
                }
            )
    with open(ROOT / "lists/loop-pool.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    with open(ROOT / "data/loop/features.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(feats[0]))
        w.writeheader()
        w.writerows(feats)
    from collections import Counter

    c = Counter(x["stratum"] for x in feats)
    mb = Counter()
    for x in feats:
        mb[x["stratum"]] += x["bytes"]
    print(f"{len(feats)} books, {sum(x['bytes'] for x in feats) / 1e6:.0f} MB")
    for k in sorted(c):
        print(f"  {k:24} {c[k]:4} books {mb[k] / 1e6:7.1f} MB")


if __name__ == "__main__":
    main()

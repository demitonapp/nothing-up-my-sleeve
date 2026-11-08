"""Write the two primers (thorp/primers.py): the held-out test items (ships/lists/tricks/<who>-primer.csv, the maths
book's shape) and the reading (local books `primer-<who>-<n>` and the shelf lists/primer-<who>.csv, as the logic tutor's
passages are written). Justin, 2026-11-08: chapters approved; "i'll take your recs".

**Size.** Each primer has about 100 distinct lesson sentences, so a large share of the reading would be the same
sentences over and over: the default is **about 2% of Ogden v0.2's words** (34,000 passages, 1.9M words), not the 10%
first proposed, and DECISIONS.md says why.

    uv run --project backend python backend/scripts/make_primers.py [passages] [books]
"""

from __future__ import annotations

import csv
import hashlib
import sys

from thorp import manifest, paths, primers

PASSAGES, BOOKS = 34000, 40


def write_tests(who: str) -> int:
    rows = primers.test_items(who)
    out = paths.resolve(f"lists/tricks/{who}-primer.csv")
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def write_reading(who: str, n: int, books: int) -> tuple[int, int]:
    texts = primers.passages(who, n, seed=1)
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    per = -(-len(texts) // books)
    shelf, words = [], 0
    for i in range(books):
        chunk = texts[i * per : (i + 1) * per]
        if not chunk:
            break
        bid = f"primer-{who}-{i + 1:03d}"
        text = "\n\n".join(chunk) + "\n"
        (d / f"{bid}.txt").write_text(text, encoding="utf-8")
        data = text.encode("utf-8")
        title = f"{primers.TITLES[who]}, book {i + 1}"
        manifest.upsert(manifest.Book(
            id=bid, source="local", title=title, author=f"Thorp's primer ({who})", language="en", family="Germanic",
            text=f"derived: {primers.TITLES[who]}, template writer, seed 1", chars=len(text), bytes=len(data),
            sha1=hashlib.sha1(data).hexdigest(), fetched_at="", set="recipe",
        ))  # fmt: skip
        shelf.append({"title": title, "author": f"Thorp's primer ({who})", "language": "en", "family": "Germanic", "text": f"local:{bid}"})
        words += sum(len(p.split()) for p in chunk)
    with paths.resolve(f"lists/primer-{who}.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(shelf)
    return len(shelf), words


def main(n: int = PASSAGES, books: int = BOOKS) -> int:
    for who in primers.PRIMERS:
        t = write_tests(who)
        b, w = write_reading(who, n, books)
        print(f"{who}: {t} held-out items, {n} passages in {b} books, {w / 1e6:.2f}M words")
    return 0


if __name__ == "__main__":
    sys.exit(main(*(int(a) for a in sys.argv[1:])))

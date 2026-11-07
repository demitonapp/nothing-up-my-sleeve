"""The apprentice's shelf (2026-11-07; DECISIONS.md, "The Magician's Apprentice"): every book of
lists/stars-fiction.csv with the words of each line shuffled (seeded per book and line). Spelling,
word frequencies and which words share a line survive; word order does not, so the word before
tells a reader nothing the line's other words do not, and a model has no reason to learn the
previous-word trick. Registered as local books `shuf-<book id>`; writes
lists/stars-fiction-shuffled.csv (rows "local:<id>").

    uv run python scripts/make_shuffled_shelf.py
"""

from __future__ import annotations

import csv
import hashlib
import random

from thorp import manifest, paths
from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)
from thorp.sources import load_text
from thorp.train import gutenberg_resolver


def shuffle_lines(text: str, seed: str) -> str:
    out = []
    for i, line in enumerate(text.split("\n")):
        words = line.split()
        random.Random(f"{seed}:{i}").shuffle(words)
        out.append(" ".join(words))
    return "\n".join(out)


def main() -> None:
    ids, missing = gutenberg_resolver("lists/stars-fiction.csv")
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    for b in ids:
        src = manifest.get(b)
        text = shuffle_lines(load_text(b), b)
        nid = f"shuf-{b}"
        (d / f"{nid}.txt").write_text(text, encoding="utf-8")
        data = text.encode("utf-8")
        manifest.upsert(
            manifest.Book(
                id=nid,
                source="local",
                title=f"{src.title} (words shuffled within lines)",
                author=src.author,
                language=src.language,
                family=src.family,
                text="derived: words shuffled within lines",
                chars=len(text),
                bytes=len(data),
                sha1=hashlib.sha1(data).hexdigest(),
                fetched_at="",
                set="recipe",
            )
        )
        rows.append(
            {
                "title": f"{src.title} (shuffled)",
                "author": src.author,
                "language": "en",
                "family": src.family,
                "text": f"local:{nid}",
            }
        )
    with open(ROOT / "lists/stars-fiction-shuffled.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} shuffled books ({len(missing)} missing)")


if __name__ == "__main__":
    main()

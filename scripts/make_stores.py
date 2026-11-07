"""The ship's stores (2026-11-07, Justin): "from now on runs can only occur on two canonical stores: one
optimised for prose and one optimised for trigrams, the furthest ends of the spectrum. All runs have to
use one or the other; no other data unless explicitly opted in."

Built from every fetched period English book in the manifest (pre-1930 public domain, Justin: period
only), leaving out the held-out decks, the shuffled shelf and the books behind the chaining tests
themselves (Darwin, Wallace, Huxley on evolution, Tyndall, the energy physicists, perpetual motion,
non-Euclidean geometry), measured by thorp/trigrams.py:

- **The prose stores** (`lists/stores/prose.csv`): novels and stories (catalogue subject "Fiction", or
  English literature LoCC PR/PS/PZ, not verse or drama) with at least the median name density, ranked by
  name repetition (names recurring within the window: what tracked the Nevermore beyond the amount read),
  taken until PROSE_TOKENS.
- **The trigram stores** (`lists/stores/trigram.csv`): everything else, with a variety floor (so indexes,
  tables and lists do not win), ranked by in-window trigram repetition, taken until TRIGRAM_TOKENS.

Each store is frozen: data/stores.json records its books, tokens and the list's content hash, and the
rule (thorp/stores.py) checks the hash, so a store cannot drift under the runs that read it.

    uv run python scripts/make_stores.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROSE_TOKENS = 150_000_000
TRIGRAM_TOKENS = 60_000_000
BYTES_PER_TOKEN = 4.0
VARIETY_FLOOR = 0.6
EXCLUDE = re.compile(
    r"Darwin|Wallace, Alfred|Huxley, Thomas|Tyndall|Joule|Helmholtz|Mendele|Perpetual motion|Non-Euclidean|Evolution",
    re.I,
)
FICTION = re.compile(r"Fiction|Short stories|Juvenile fiction", re.I)
NOT_PROSE = re.compile(r"Poetry|Drama|Verse|Plays", re.I)


def catalogue() -> dict[str, dict]:
    with (ROOT / "data" / "catalogue" / "pg_catalog.csv").open(encoding="utf-8") as f:
        return {f"pg{r['Text#']}": r for r in csv.DictReader(f)}


def main() -> None:
    from thorp import manifest, trigrams

    cat = catalogue()
    refuse: set[str] = set()
    for deck in ("hole-cards.csv", "hole-cards-v2.csv", "hole-cards-unseen.csv"):
        with (ROOT / "lists" / deck).open() as f:
            refuse |= {r["title"].strip().lower() for r in csv.DictReader(f)}
    books = [
        b
        for b in manifest.all_books()
        if b.id.startswith("pg")
        and (b.language or "en") == "en"
        and b.id in cat
        and b.title.strip().lower() not in refuse
        and not EXCLUDE.search(f"{b.title} {b.author} {cat[b.id]['Subjects']}")
    ]
    stats = trigrams.measure_books([b.id for b in books])
    by_id = {b.id: b for b in books if b.id in stats}

    def is_prose(bid: str) -> bool:
        r = cat[bid]
        lit = r["LoCC"].startswith(("PR", "PS", "PZ"))
        return (FICTION.search(r["Subjects"]) or lit) and not NOT_PROSE.search(
            r["Subjects"] + " " + r["Bookshelves"]
        )

    prose_c = [b for b in by_id if is_prose(b)]
    other_c = [b for b in by_id if not is_prose(b)]
    floor = statistics.median(stats[b]["name_density"] for b in prose_c)
    prose_c = [b for b in prose_c if stats[b]["name_density"] >= floor]
    prose_c.sort(key=lambda b: -stats[b]["name_repeat"])
    other_c = [b for b in other_c if stats[b]["variety"] >= VARIETY_FLOOR]
    other_c.sort(key=lambda b: -stats[b]["repeat_rate"])

    def take(ids, budget):
        out, got = [], 0.0
        for b in ids:
            if got >= budget * BYTES_PER_TOKEN:
                break
            out.append(b)
            got += by_id[b].bytes or 0
        return out, got / BYTES_PER_TOKEN

    stores = {}
    for key, ids, budget, rank in (
        ("prose", prose_c, PROSE_TOKENS, "name repetition"),
        ("trigram", other_c, TRIGRAM_TOKENS, "trigram repetition"),
    ):
        chosen, tokens = take(ids, budget)
        out = ROOT / "lists" / "stores" / f"{key}.csv"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["title", "author", "language", "family", "text"])
            w.writeheader()
            for b in chosen:
                bk = by_id[b]
                w.writerow(
                    {
                        "title": bk.title,
                        "author": bk.author,
                        "language": "en",
                        "family": bk.family or "",
                        "text": f"local:{b}",
                    }
                )
        st = [stats[b] for b in chosen]
        stores[key] = {
            "path": f"lists/stores/{key}.csv",
            "books": len(chosen),
            "tokens": int(tokens),
            "ranked_by": rank,
            "repeat_rate": statistics.mean(s["repeat_rate"] for s in st),
            "name_repeat": statistics.mean(s["name_repeat"] for s in st),
            "variety": statistics.mean(s["variety"] for s in st),
            "sha1": hashlib.sha1(out.read_bytes()).hexdigest(),
            "candidates": len(ids),
        }
        print(
            f"{key}: {len(chosen)} books, {tokens / 1e6:.0f}M tokens, trigram {stores[key]['repeat_rate']:.3f}, names {stores[key]['name_repeat']:.3f}"
        )
    (ROOT / "data" / "stores.json").write_text(json.dumps(stores, indent=1))


if __name__ == "__main__":
    main()

"""Ogden v0.2's corpus (Justin, 2026-11-08 08:10: "let's go with A and strike the Bible and then C1 as you suggest").

- **A, the same rule over the whole library:** v0.1 scored only the two stores' 883 books. This scores every other
  English recipe book in the library (never a judge book, never a control text: the shuffled-words copies), keeps
  those at Ogden-ness 68% or more (thorp/ogden.py, v0.1's own bar), one copy per title and none already scored,
  and strikes **The Bible, King James Version** (Justin). The period gate's rule is applied here as at the gate:
  a Gutenberg book with an author dead after 1955 is left out. Written: `lists/ogden-v0.2-scores.csv` (every
  book scored) and `lists/ogden-v0.2-books.csv` (v0.1's 592 and the new books).
- **C1, the logic tutor's passages, template writer only** (thorp/logic_tutor.py: skeletons of two facts and the
  conclusion that needs both, in order, cause, membership and proportion; fixed frames, no model's text; every
  passage passes `check_passage`: strict Basic English, no 50m-rung word, no run of six words shared with any
  test). Sized to TUTOR_SHARE of the corpus's words, written as TUTOR_BOOKS local books (`tutor-v02-<n>`,
  passages a paragraph each), `lists/ogden-v0.2-tutor.csv`.
- **The recipe:** `lists/ogden-v0.2.csv`, the books and the tutor's shelf.

    uv run --project backend python backend/scripts/make_ogden_v02.py
"""

from __future__ import annotations

import csv
import hashlib
import random
import re

from thorp import logic_tutor as lt
from thorp import manifest, ogden, paths, vsm
from thorp.paths import ROUTER as ROOT
from thorp.sources import load_text

BAR = 0.68  # v0.1's Ogden-ness bar, unchanged
STRUCK = ("The Bible, King James Version",)  # Justin, 08:10
TUTOR_SHARE = 0.075  # C1: 5 to 10% of the reading (08:10: "C1 as you suggest"), the middle of it
TUTOR_BOOKS = 100
TUTOR_SEED = 2
CONTROL = re.compile(r"shuffled|scrambled", re.I)  # the library's control texts: never in a corpus
FIELDS = ["title", "author", "language", "family", "text"]


def norm(t: str | None) -> str:
    return re.sub(r"[^a-z]", "", (t or "").lower())[:40]


def ids_of(lp: str) -> set[str]:
    p = paths.resolve(lp)
    if not p.exists():
        return set()
    with p.open() as f:
        return {(r.get("text") or "").split(":")[-1] for r in csv.DictReader(f)}


def books() -> tuple[list[dict], list[dict]]:
    with open(ROOT / "lists/ogden-v0.1-scores.csv") as f:
        v1_scored = list(csv.DictReader(f))
    scored_ids = {r["book"] for r in v1_scored}
    scored_titles = {norm(r["title"]) for r in v1_scored}
    judge = ids_of("lists/hole-cards-unseen.csv") | ids_of("lists/hole-cards.csv") | ids_of("lists/hole-cards-v2.csv")
    deaths = vsm._deaths()
    scores, keep, seen = [], [], set()
    for b in sorted(manifest.all_books(), key=lambda b: b.id):
        if b.language != "en" or b.set != "recipe" or b.id in scored_ids or b.id in judge or CONTROL.search(b.title or ""):
            continue
        try:
            text = load_text(b.id)
        except Exception:  # noqa: BLE001 (a book whose text is not here cannot be scored)
            continue
        s = ogden.score(text[:400000])
        row = {"book": b.id, "title": b.title, "author": b.author or "", "source": b.source,
               "words": int(len(text) / 5.7), "ogden": round(s["ogden"], 4), "names": round(s["names"], 4)}  # fmt: skip
        scores.append(row)
        t = norm(b.title)
        if s["ogden"] < BAR or t in scored_titles or t in seen or b.title in STRUCK or deaths.get(b.id, 0) > 1955:
            continue
        seen.add(t)
        keep.append({"title": b.title, "author": b.author or "", "language": "en", "family": b.family or "Germanic",
                     "text": f"local:{b.id}", "_words": row["words"]})  # fmt: skip
    return scores, keep


def tutor_shelf(words: int) -> list[dict]:
    """The C1 shelf: passages enough for `words` words, in TUTOR_BOOKS local books."""
    per = 28  # words a passage, about (the template writer's mean)
    sks = lt.skeletons(words // per + TUTOR_BOOKS, seed=TUTOR_SEED)
    rng = random.Random(f"ogden-v0.2-tutor:{TUTOR_SEED}")
    passages, seen = [], set()
    for sk in sks:
        t = lt.template(sk, rng)
        if t in seen or lt.check_passage(sk, t):
            continue
        seen.add(t)
        passages.append(t)
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    rows = []
    per_book = -(-len(passages) // TUTOR_BOOKS)
    for i in range(TUTOR_BOOKS):
        chunk = passages[i * per_book : (i + 1) * per_book]
        if not chunk:
            break
        bid = f"tutor-v02-{i + 1:03d}"
        text = "\n\n".join(chunk) + "\n"
        (d / f"{bid}.txt").write_text(text, encoding="utf-8")
        data = text.encode("utf-8")
        manifest.upsert(manifest.Book(
            id=bid, source="local", title=f"The logic tutor's passages, book {i + 1} (template writer)",
            author="Thorp's logic tutor (template writer)", language="en", family="Germanic",
            text=f"derived: logic tutor template writer, seed {TUTOR_SEED}", chars=len(text), bytes=len(data),
            sha1=hashlib.sha1(data).hexdigest(), fetched_at="", set="recipe",
        ))  # fmt: skip
        rows.append({"title": f"The logic tutor's passages, book {i + 1}", "author": "Thorp's logic tutor",
                     "language": "en", "family": "Germanic", "text": f"local:{bid}"})  # fmt: skip
    print(f"tutor: {len(passages)} passages, {sum(len(p.split()) for p in passages) / 1e6:.2f}M words, {len(rows)} books")
    return rows


def write(lp: str, rows: list[dict]) -> None:
    with open(ROOT / lp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    with open(ROOT / "lists/ogden-v0.1.csv") as f:
        v1 = list(csv.DictReader(f))
    scores, new = books()
    with open(ROOT / "lists/ogden-v0.2-scores.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["book", "title", "author", "source", "words", "ogden", "names"])
        w.writeheader()
        w.writerows(sorted(scores, key=lambda r: -r["ogden"]))
    with open(ROOT / "lists/ogden-v0.1-scores.csv") as f:
        v1_words = sum(int(r["words"]) for r in csv.DictReader(f) if float(r["ogden"]) >= BAR)
    book_words = v1_words + sum(r["_words"] for r in new)
    write("lists/ogden-v0.2-books.csv", v1 + new)
    tutor = tutor_shelf(int(book_words * TUTOR_SHARE / (1 - TUTOR_SHARE)))
    write("lists/ogden-v0.2-tutor.csv", tutor)
    write("lists/ogden-v0.2.csv", v1 + new + tutor)
    print(f"scored {len(scores)}; v0.1 {len(v1)} books + {len(new)} new ({sum(r['_words'] for r in new) / 1e6:.1f}M words) "
          f"+ {len(tutor)} tutor books: lists/ogden-v0.2.csv, {len(v1) + len(new) + len(tutor)} rows")  # fmt: skip


if __name__ == "__main__":
    main()

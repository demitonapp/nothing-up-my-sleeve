"""The Ogden branch's maths shelf, and Augustus's four variations (Justin, 2026-11-08: "Yeah to for Pan and
Augustus, they need to use the Ogden branch of the libraries. So add it to the ogden branch of the library so
it's included and then the ogden branches, bibliography changes"): Ogden v0.1's 592 books with De Morgan's tutor
(thorp/maths_tutor.py) mixed in at 2, 5, 10 and 20% of the words.

- **The shelf:** TUTOR_BOOKS local books (`maths-tutor-<n>`), the lessons dealt in De Morgan's order, written
  for the largest share; each smaller share reads the first books of it. Every book is scored for Ogden-ness
  and must clear v0.1's bar (68%). `lists/ogden-maths-tutor.csv`.
- **The variations** (the Ogden branch: v0.1's bibliography plus the shelf; v0.1 and v0.2 unchanged):
  `lists/ogden-v0.1-maths<share>.csv`, fitouts `ogden-v0-1-maths<share>` (ships/fitouts), v0.1's tokeniser, its
  cleaning and its four passes.

    uv run --project backend python backend/scripts/make_ogden_maths.py
"""

from __future__ import annotations

import csv
import hashlib
import json

from thorp import manifest, maths_tutor, ogden, paths
from thorp.paths import ROUTER as ROOT

SHARES = (2, 5, 10, 20)  # percent of the reading's words
TUTOR_BOOKS = 100
SEED = 1830  # Elements of Arithmetic, first published
BAR = 0.68
FIELDS = ["title", "author", "language", "family", "text"]


def v1_words() -> int:
    with open(ROOT / "lists/ogden-v0.1-scores.csv") as f:
        return sum(int(r["words"]) for r in csv.DictReader(f) if float(r["ogden"]) >= BAR)


def shelf(words: int) -> list[dict]:
    per = 30  # words a lesson, about
    lessons = maths_tutor.lessons(words // per + TUTOR_BOOKS, seed=SEED)
    d = paths.texts_dir("local")
    d.mkdir(parents=True, exist_ok=True)
    per_book = -(-len(lessons) // TUTOR_BOOKS)
    rows = []
    for i in range(TUTOR_BOOKS):
        chunk = lessons[i * per_book : (i + 1) * per_book]
        if not chunk:
            break
        bid = f"maths-tutor-{i + 1:03d}"
        text = "\n\n".join(chunk) + "\n"
        sc = ogden.score(text)["ogden"]
        if sc < BAR:
            raise SystemExit(f"{bid}: Ogden-ness {sc:.2f} is under the bar {BAR}")
        (d / f"{bid}.txt").write_text(text, encoding="utf-8")
        data = text.encode("utf-8")
        manifest.upsert(manifest.Book(
            id=bid, source="local", title=f"De Morgan's tutor, lessons in sums, book {i + 1}",
            author="Thorp's maths tutor (after De Morgan, Elements of Arithmetic)", language="en", family="Germanic",
            text=f"derived: maths tutor, seed {SEED}", chars=len(text), bytes=len(data),
            sha1=hashlib.sha1(data).hexdigest(), fetched_at="", set="recipe",
        ))  # fmt: skip
        rows.append({"title": f"De Morgan's tutor, book {i + 1}", "author": "Thorp's maths tutor", "language": "en",
                     "family": "Germanic", "text": f"local:{bid}", "_words": len(text.split()), "_ogden": sc})  # fmt: skip
    return rows


def write(lp: str, rows: list[dict]) -> None:
    with open(ROOT / lp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    with open(ROOT / "lists/ogden-v0.1.csv") as f:
        v1 = list(csv.DictReader(f))
    base = v1_words()
    top = max(SHARES) / 100
    rows = shelf(int(base * top / (1 - top)))
    total = sum(r["_words"] for r in rows)
    write("lists/ogden-maths-tutor.csv", rows)
    v01 = json.loads((ROOT / "fitouts/ogden-v0-1.json").read_text())
    for s in SHARES:
        need = base * (s / 100) / (1 - s / 100)
        k, got = 0, 0
        while k < len(rows) and got < need:
            got += rows[k]["_words"]
            k += 1
        lp = f"lists/ogden-v0.1-maths{s}.csv"
        write(lp, v1 + rows[:k])
        key = f"ogden-v0-1-maths{s}"
        fit = {
            **{k2: v01[k2] for k2 in v01 if k2 not in ("key", "name", "aim", "stages", "opt_in")},
            "key": key, "name": f"Ogden v0.1 + De Morgan's tutor, {s}%",
            "aim": (f"Augustus's reading (Justin, 2026-11-08: the Ogden branch, its bibliography changed): Ogden v0.1's 592 books "
                    f"and the first {k} books of De Morgan's tutor (thorp/maths_tutor.py, lessons in sums in Ogden's words in "
                    f"De Morgan's order, the maths book's sums held out), {got / 1e6:.2f}M words, {100 * got / (base + got):.1f}% of the reading"),
            "opt_in": "De Morgan's tutor: Thorp's own lessons in sums, local books outside the two stores, approved by Justin (2026-11-08: \"Yeah\", for Augustus, on the Ogden branch)",
            "stages": [{"phase": "pretraining", "name": f"ogden-v0.1-maths{s}", "shelf": lp, "tokens": None, "select": "all", "passes": 4,
                        "lr": None, "tack": None, "purpose": f"Ogden v0.1 and {k} books of De Morgan's tutor, four passes"}],
        }  # fmt: skip
        (ROOT / f"fitouts/{key}.json").write_text(json.dumps(fit, indent=1) + "\n")
        print(f"{key}: v0.1 {len(v1)} books + {k} tutor books, {got / 1e6:.2f}M tutor words, {100 * got / (base + got):.1f}% ({lp})")
    print(f"shelf: {len(rows)} books, {total / 1e6:.2f}M words, Ogden-ness {min(r['_ogden'] for r in rows):.2f} to {max(r['_ogden'] for r in rows):.2f}")


if __name__ == "__main__":
    main()

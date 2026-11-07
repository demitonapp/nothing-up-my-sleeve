"""Draw the pool: the earliest Gutenberg transcriptions that pass both legal checks, by id.

Writes lists/pool-draft.csv (title, author, language, family, text), appends an override per row
so the resolver's choice is exact, and appends fiction / verse labels to lists/traits.csv from the
catalogue's subject tags (first person is left blank: the catalogue does not know it).

Rules: Type Text, Language en, every person named in Authors dead by 1955 and born after 1500, no
periodicals, no index or catalogue entries, not an edition of a hole card (by title), not a book
already in the manifest (so the hundred is not drawn twice), lowest ids first. The draft is cut to
the recipe after the fetch, by bytes (scripts/cut_pool.py), so a speech never becomes a book.

    uv run python scripts/make_pool.py 560
"""

from __future__ import annotations

import csv
import re
import sqlite3
import sys

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

CATALOGUE = ROOT / "data/catalogue/pg_catalog.csv"
MANIFEST = ROOT / "data/manifest.sqlite"
HOLE_TITLE_KEYS = [
    "don quixote",
    "war and peace",
    "brothers karamazov",
    "swann",
    "remembrance of things past",
    "ulysses",
    "moby",
    "red chamber",
    "hung lou",
    "braz cubas",
    "bras cubas",
    "small winner",
    "peloponnesian",
    "montaigne",
    "principia",
    "natural philosophy",
    "origin of species",
    "dream psychology",
    "interpretation of dreams",
    "relativity",
]
FAMILY_OF = {
    "French": "Romance",
    "Spanish": "Romance",
    "Italian": "Romance",
    "Portuguese": "Romance",
    "Latin": "Italic",
    "Greek": "Hellenic",
    "German": "Germanic",
    "Dutch": "Germanic",
    "Danish": "Germanic",
    "Norwegian": "Germanic",
    "Swedish": "Germanic",
    "Icelandic": "Germanic",
    "Russian": "Slavic",
    "Polish": "Slavic",
    "Czech": "Slavic",
    "Sanskrit": "Indo-Iranian",
    "Persian": "Indo-Iranian",
    "Hindi": "Indo-Iranian",
    "Chinese": "Sino-Tibetan",
    "Japanese": "Japonic",
    "Arabic": "Afroasiatic",
    "Hebrew": "Afroasiatic",
    "Finnish": "Uralic",
    "Hungarian": "Uralic",
}
YEARS = re.compile(r"(\d{4})\??-(\d{4})\??")


def family(subjects: str) -> str:
    if "translations into english" not in subjects.lower():
        return "Germanic"
    for lang, fam in FAMILY_OF.items():
        if re.search(rf"\b{lang}\b", subjects):
            return fam
    return "Germanic"


def passes(r: dict) -> bool:
    if r["Type"] != "Text" or r["Language"] != "en" or not r["Authors"]:
        return False
    t, s = r["Title"].lower(), r["Subjects"].lower()
    if "periodical" in s or "periodical" in t or "index" in t[:12] or "project gutenberg" in t:
        return False
    if any(k in t for k in HOLE_TITLE_KEYS):
        return False
    years = YEARS.findall(r["Authors"])
    if not years or len(years) < r["Authors"].count(";") + 1 - r["Authors"].count("Anonymous"):
        return False  # a person without dates cannot be checked
    return all(int(d) <= 1955 and int(b) >= 1500 for b, d in years)


def main(n: int) -> None:
    have = {
        int(i[2:])
        for (i,) in sqlite3.connect(MANIFEST).execute("select id from books")
        if i.startswith("pg")
    }
    rows = [r for r in csv.DictReader(open(CATALOGUE, encoding="utf-8")) if passes(r)]
    rows.sort(key=lambda r: int(r["Text#"]))
    seen_titles = set()
    picked = []
    for r in rows:
        pid = int(r["Text#"])
        title = " ".join(r["Title"].split())
        key = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
        if pid in have or key in seen_titles:
            continue
        seen_titles.add(key)
        picked.append((pid, title, r))
        if len(picked) >= n:
            break
    author = lambda a: a.split(";")[0].split(",")[0].strip()  # noqa: E731
    with open(ROOT / "lists/pool-draft.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["title", "author", "language", "family", "text"])
        for _pid, title, r in picked:
            w.writerow([title, author(r["Authors"]), "en", family(r["Subjects"]), "original"])
    with open(ROOT / "lists/overrides.csv", "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for pid, title, r in picked:
            w.writerow([title, author(r["Authors"]), pid])
    with open(ROOT / "lists/traits.csv", "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        for _pid, title, r in picked:
            s = r["Subjects"].lower()
            fiction = int(
                any(k in s for k in ("fiction", "stories", "novel", "drama", "tales", "fairy"))
            )
            verse = int(any(k in s for k in ("poetry", "poems", "verse")))
            w.writerow([title, fiction, verse, ""])
    fams = {}
    for _, _, r in picked:
        fams[family(r["Subjects"])] = fams.get(family(r["Subjects"]), 0) + 1
    print(f"{len(picked)} books, ids {picked[0][0]}..{picked[-1][0]}, families {fams}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 560)

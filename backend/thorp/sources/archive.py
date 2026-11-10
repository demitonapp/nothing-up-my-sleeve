"""The Internet Archive as a Nothing up my sleeve source (2026-11-07): an item's OCR text (`<id>_djvu.txt`),
cleaned, with the publication year from the item's metadata.

Cleaning, for scans of old type: Google Books' digitisation notice and "Digitized by" lines are
dropped; lines that are only a page number are dropped; a word broken across a line with a hyphen
is joined; runs of blank lines are folded to one. For books printed before 1800, the long s (ſ),
which OCR reads as "f" ("alfo", "purpofe"), is repaired word by word: a word with an "f" that is not
an English word, but becomes one when some "f"s are read as "s", takes that reading (the word list is
every word of the 1,108-book loop pool, built once into data/lexicon-en.txt). Scanned books still go
on discovery shelves first, not into the spelling pool.
"""

from __future__ import annotations

import re

from thorp.sources.base import Fetched, http_get, register_source

GOOGLE_NOTICE = re.compile(
    r"This is a digital copy of a book.*?(?:books\.google\.com/?|http://books\.google\.com/)\s*\|?",
    re.S | re.I,
)
DIGITIZED = re.compile(r"^\s*Digiti[sz]ed by.*$", re.M | re.I)
PAGE_NUMBER = re.compile(r"^\s*[\divxlcIVXLC]{1,6}\s*$", re.M)
HYPHEN_BREAK = re.compile(r"(\w)-\n\s*(\w)")
BLANKS = re.compile(r"\n{3,}")


def clean(raw: str) -> str:
    t = raw.replace("\r\n", "\n")
    t = GOOGLE_NOTICE.sub("", t)
    t = DIGITIZED.sub("", t)
    t = PAGE_NUMBER.sub("", t)
    t = HYPHEN_BREAK.sub(r"\1\2", t)
    t = BLANKS.sub("\n\n", t)
    return t.strip() + "\n"


WORDLIKE = re.compile(r"[A-Za-z]+")
_lexicon: set[str] | None = None


def lexicon() -> set[str]:
    """Every word (lower case) of the loop pool, from data/lexicon-en.txt, built once."""
    global _lexicon
    if _lexicon is None:
        from thorp import paths

        p = paths.data_dir() / "lexicon-en.txt"
        if not p.exists():
            from thorp.sources import load_text
            from thorp.train import gutenberg_resolver

            words: set[str] = set()
            for b in gutenberg_resolver("lists/loop-pool.csv")[0]:
                words.update(w.lower() for w in WORDLIKE.findall(load_text(b)))
            p.write_text("\n".join(sorted(words)), encoding="utf-8")
        _lexicon = set(p.read_text(encoding="utf-8").split())
    return _lexicon


def fix_long_s(text: str, words: set[str]) -> str:
    """Read OCR's "f" as the long s where that, and only that, makes an English word."""
    from itertools import product

    def mend(m: re.Match) -> str:
        w = m.group(0)
        low = w.lower()
        if "f" not in low or low in words:
            return w
        spots = [i for i, c in enumerate(low) if c == "f"]
        if len(spots) > 4:
            return w
        for choice in product((False, True), repeat=len(spots)):
            if not any(choice):
                continue
            cand = list(w)
            for i, s_ in zip(spots, choice, strict=True):
                if s_:
                    cand[i] = "s" if w[i] == "f" else "S"
            if "".join(cand).lower() in words:
                return "".join(cand)
        return w

    return WORDLIKE.sub(mend, text)


def _year(meta: dict) -> int | None:
    for k in ("year", "date"):
        v = meta.get(k)
        if isinstance(v, list):
            v = v[0] if v else None
        m = re.search(r"(?<!\d)(1[0-9]{3})(?!\d)", str(v or ""))
        if m:
            year = int(m.group(1))
            if 1000 <= year <= 2100:
                return year
    return None


def _one(v) -> str:
    return (v[0] if isinstance(v, list) and v else v) or ""


class ArchiveSource:
    key = "archive"
    prefix = "ia-"

    def fetch(self, ident: str) -> Fetched:
        r = http_get(f"https://archive.org/metadata/{ident}")
        r.raise_for_status()
        md = r.json()
        meta = md.get("metadata", {})
        files = [f["name"] for f in md.get("files", [])]
        txt = next((f for f in files if f.endswith("_djvu.txt")), None) or next(
            (f for f in files if f.endswith(".txt")), None
        )
        if txt is None:
            raise LookupError(f"archive item {ident} has no text file")
        body = http_get(f"https://archive.org/download/{ident}/{txt}")
        body.raise_for_status()
        lang = _one(meta.get("language")).lower()
        text = clean(body.content.decode("utf-8", errors="replace"))
        year = _year(meta)
        if year is not None and year < 1800:
            text = fix_long_s(text, lexicon())
        return Fetched(
            title=_one(meta.get("title")),
            author=_one(meta.get("creator")),
            language="en" if lang in ("", "eng", "english", "en") else lang,
            text=text,
            published=year,
            origin=f"https://archive.org/details/{ident}",
        )


register_source(ArchiveSource())

"""Incunabula: the first printed books, before 1501.

The open route is the Boston Public Library's incunabula set on the Internet Archive (`bplscinc`):
315 volumes printed 1450-1500, 307 of them carrying the public-domain mark. It is mostly Latin
(239), with Italian (20), German (16), Greek (11) and only six English: the English incunabula are
mostly in EEBO and its ProQuest scans (`pub_early-english-books-1475-1640`,
`early-european-books`), which are walled.

The Internet Archive's date field is noisy: modern books with a wrong `date`, manuscripts and single
leaves all appear under `date:[1450 TO 1500]`. This module is the filter: a strict four-digit year,
a public-domain licence, a known open collection, no manuscript or fragment, and a text long enough
to be a book. A single item can also be fetched as `incunabula:<archive id>`.
"""

from __future__ import annotations

import re

from thorp.sources.archive import ArchiveSource
from thorp.sources.base import Fetched, http_get, register_source

QUERY = "collection:bplscinc AND date:[1450 TO 1500]"
MIN_YEAR, MAX_YEAR = 1450, 1500
MIN_CHARS = 5000  # a single leaf or a binding scan is not a book

BAD_COLLECTIONS = {
    "early-european-books",  # ProQuest Early European Books
    "pub_early-english-books-1475-1640",  # EEBO's microfilm/ProQuest set
    "folkscanomy",
    "folkscanomy_historical_texts",
    "ds-legacy-data",
    "findmypastpersi",
    "booksbylanguage",
    "booksbylanguage_german",
}
BAD_TITLE = (
    "manuscript",
    "fragment",
    "book of hours",
    " ms ",
    "ms.",
    "leaf from",
    "detached leaves",
)

_YEAR = re.compile(r"^(\d{4})(?:-\d{2}-\d{2}T.*)?$")


def strict_year(value) -> int | None:
    """A four-digit year from a plain or ISO date; None for a range like '800 - 1500'."""
    m = _YEAR.match(str(value or "").strip())
    return int(m.group(1)) if m else None


def collections(doc: dict) -> set[str]:
    c = doc.get("collection") or []
    return {c} if isinstance(c, str) else set(c)


def description(doc: dict) -> str:
    d = doc.get("description") or ""
    return " ".join(d) if isinstance(d, list) else str(d)


def plausible(doc: dict) -> bool:
    """A record the archive's date query returned that is really a pre-1501 printed book, openly licensed."""
    y = strict_year(doc.get("date")) if doc.get("date") else strict_year(doc.get("year"))
    if y is None or not MIN_YEAR <= y <= MAX_YEAR:
        return False
    if BAD_COLLECTIONS & collections(doc):
        return False
    licence = str(doc.get("licenseurl") or "").lower()
    if "publicdomain" not in licence and "cc0" not in licence:
        return False
    title = str(doc.get("title") or "").lower()
    if len(title) < 8 or any(w in title for w in BAD_TITLE):
        return False
    d = description(doc).lower()
    if "manuscript" in d or "fragment" in d:
        return False
    return True


def year_of(doc: dict) -> int | None:
    return strict_year(doc.get("date")) if doc.get("date") else strict_year(doc.get("year"))


def from_doc(doc: dict) -> Fetched:
    """A search result's book, reading `<id>_djvu.txt` directly (one request, not metadata and then text).
    Falls back to the item fetcher when the archive names the text differently."""
    ident = str(doc.get("identifier"))
    year = year_of(doc)
    r = http_get(f"https://archive.org/download/{ident}/{ident}_djvu.txt", timeout=300)
    if r.status_code == 200 and len(r.content) >= MIN_CHARS:
        from thorp.sources.archive import clean, fix_long_s, lexicon
        from thorp.sources.bulk import iso_language

        text = clean(r.content.decode("utf-8", errors="replace"))
        language = iso_language(doc.get("language"))
        # the long-s repair's word list is English: on Latin it is slow and wrong, so only English
        if language == "en" and year is not None and year < 1800:
            text = fix_long_s(text, lexicon())
        creator = doc.get("creator") or ""
        if isinstance(creator, list):
            creator = "; ".join(str(x) for x in creator)
        return Fetched(
            title=str(doc.get("title") or ""),
            author=str(creator),
            language=language,
            text=text,
            published=year,
            origin=f"https://archive.org/details/{ident}",
        )
    return IncunabulaSource().fetch(ident)


class IncunabulaSource:
    """One incunabulum by its Internet Archive identifier (`incunabula:thusendethlegend00jaco`)."""

    key = "incunabula"
    prefix = "inc-"

    def fetch(self, ident: str) -> Fetched:
        f = ArchiveSource().fetch(ident)
        if f.published is None or not MIN_YEAR <= f.published <= MAX_YEAR:
            raise LookupError(f"archive item {ident} is not dated {MIN_YEAR}–{MAX_YEAR} ({f.published})")
        head = f.text[:2000].lower()
        if "early european books" in head or "proquest" in head:
            raise LookupError(f"archive item {ident} carries a ProQuest Early European Books notice")
        return f


register_source(IncunabulaSource())

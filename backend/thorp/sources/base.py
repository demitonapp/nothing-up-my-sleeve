"""One fetcher, many sources (2026-11-07, Justin: "the fetcher must be generalised").

A **Source** turns an identifier into clean text and the facts Thorp needs about it: title, author,
language, the year it was published (for cutoff tests: a book is before a cutoff when it was
printed before it), and where it came from. Sources are registered in SOURCES by key:

- `gutenberg`: Project Gutenberg, by catalogue number (`gutenberg:1228`); the original title-matched
  lists still resolve as before (thorp/sources/gutenberg.py).
- `archive`: the Internet Archive, by item identifier (`archive:Lyell1837jf09J-a`): its OCR text,
  cleaned (thorp/sources/archive.py).
- `local`: a book that exists only here, already in the manifest (`local:shuf-pg100`, the shuffled
  shelf).

A book list may name any book as `<source>:<identifier>` in its `text` column; `fetch_ref` fetches it
once (cached under data/texts/<source>/), registers it in the manifest as `<prefix><identifier>`, and
returns its manifest entry. Requests go through `http_get`: one project User-Agent and at most one
request every two seconds per host.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import requests

from thorp import manifest, paths

REQUEST_INTERVAL_S = 2.0
_last: dict[str, float] = {}


def http_get(url: str, timeout: int = 120) -> requests.Response:
    """GET with the project's User-Agent, at most one request every two seconds per host, three
    retries on connection errors and 5xx."""
    from thorp.sources.gutenberg import USER_AGENT

    host = urlparse(url).netloc
    r = None
    for attempt in range(4):
        wait = REQUEST_INTERVAL_S - (time.monotonic() - _last.get(host, 0.0))
        if wait > 0:
            time.sleep(wait)
        _last[host] = time.monotonic()
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        except requests.ConnectionError:
            if attempt == 3:
                raise
            continue
        if r.status_code < 500 or attempt == 3:
            return r
    return r


@dataclass
class Fetched:
    title: str
    author: str
    language: str
    text: str  # clean text, as Thorp reads it
    published: int | None = None  # the year this edition was printed, when the source knows it
    origin: str = ""  # where it came from (a URL)


class Source(Protocol):
    key: str
    prefix: str  # book ids from this source start with it

    def fetch(self, ident: str) -> Fetched: ...


SOURCES: dict[str, Source] = {}


def register_source(src: Source) -> Source:
    SOURCES[src.key] = src
    return src


def _sources() -> dict[str, Source]:
    # importing the modules registers them
    from thorp.sources import archive, gutenberg, incunabula  # noqa: F401

    return SOURCES


def is_ref(text: str) -> bool:
    key = (text or "").split(":", 1)[0]
    return ":" in (text or "") and (key == "local" or key in _sources())


def fetch_ref(ref: str, family: str = "", set_name: str = "recipe") -> manifest.Book:
    """`<source>:<identifier>` -> its manifest entry, fetching and registering it if new."""
    key, ident = ref.split(":", 1)
    if key == "local":
        book = manifest.get(ident)
        if book is None:
            raise LookupError(f"no local book {ident!r} in the manifest")
        return book
    src = _sources()[key]
    book_id = f"{src.prefix}{ident}"
    known = manifest.get(book_id)
    path = paths.texts_dir(key) / f"{book_id}.txt"
    if known is not None and path.exists():
        return known
    return register_fetched(key, ident, src.fetch(ident), family, set_name)


def register_fetched(
    key: str,
    ident: str,
    f: Fetched,
    family: str = "",
    set_name: str = "recipe",
    observe: bool = True,
) -> manifest.Book:
    """Write a fetched book's text to its source's cache and register it in the manifest. A book new to the
    library is observed by acquisition's S1 (thorp/acquisition.py: logged with the verdict its gate would
    give, never refused) unless an intake, which has already passed it through the gate, registers it."""
    src = _sources()[key]
    return register_text(
        key,
        f"{src.prefix}{ident}",
        f,
        family=family,
        set_name=set_name,
        observe=observe,
        how="fetch_ref",
    )


def register_text(
    key: str,
    book_id: str,
    f: Fetched,
    family: str = "",
    set_name: str = "recipe",
    observe: bool = True,
    how: str = "thorp fetch",
) -> manifest.Book:
    """The one writer of a fetched book: its text in data/texts/<source>/, its row in the manifest.
    `register_fetched` is this for an item fetcher; a bulk source (thorp/sources/bulk.py) names its own
    book id because its identifier is not a `<source>:<identifier>` ref."""
    new = manifest.get(book_id) is None
    path = paths.texts_dir(key) / f"{book_id}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f.text, encoding="utf-8")
    data = f.text.encode("utf-8")
    book = manifest.Book(
        id=book_id,
        source=key,
        title=f.title,
        author=f.author,
        language=f.language,
        family=family,
        text=f"published {f.published}; {f.origin}" if f.published else f.origin,
        chars=len(f.text),
        bytes=len(data),
        sha1=hashlib.sha1(data).hexdigest(),
        fetched_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        set=set_name,
    )
    manifest.upsert(book)
    if new and observe:
        try:
            from thorp import acquisition

            acquisition.observe(book, how)
        except Exception:  # noqa: BLE001  (the record must never cost a fetch)
            pass
    return book


def published(book: manifest.Book) -> int | None:
    """The year a registered book's edition was printed, when its source recorded it."""
    t = book.text or ""
    if t.startswith("published "):
        try:
            return int(t.split(";", 1)[0].split()[1])
        except (IndexError, ValueError):
            return None
    return None

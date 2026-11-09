"""A name's life dates when the catalogue gives none (acquisition's S4, for scanned sources).

The Gutenberg catalogue dates almost every person. The scanned catalogues often do not: the Library
of Congress set's author strings are names only ("Greene, Charles E."), so the death rule cannot
speak and the book is refused. This resolver asks Wikidata for the person and reads the life dates
from the search result's description ("American poet and playwright (1869-1926)"), one request a
second, cached in data/catalogue/authority.json.

It is opt-in (`thorp gather ... --authority`) and it never guesses: a description with no death year
("(1874-?)") returns nothing, a name that is not a person (a college, a company) returns nothing, and
a result whose label does not contain the surname returns nothing. The resolved dates are kept on the
candidate (`Candidate.resolved`), so the gate's own rule decides, not this module.
"""

from __future__ import annotations

import json
import re
import time
from urllib.parse import urlencode

from thorp import paths
from thorp.sources.base import http_get

API = "https://www.wikidata.org/w/api.php"
_LIFE = re.compile(r"\((\d{3,4})\s*[–-]\s*(\d{3,4})\)")
_BORN = re.compile(r"\((\d{3,4})\s*[–-]\s*\?\)")
_PAREN = re.compile(r"\s*\([^)]*\)")
_cache: dict[str, dict | None] | None = None


def _cache_path():
    return paths.data_dir() / "catalogue" / "authority.json"


def _load() -> dict[str, dict | None]:
    global _cache
    if _cache is None:
        p = _cache_path()
        _cache = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    return _cache


def _save() -> None:
    p = _cache_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(_load(), indent=1, sort_keys=True), encoding="utf-8")


def query(name: str) -> str:
    """'Sterling, George' -> 'George Sterling'; a corporate name stays as it is (and will not resolve)."""
    n = _PAREN.sub("", name or "").strip().strip(",")
    if "," in n:
        surname, given = (x.strip() for x in n.split(",", 1))
        return f"{given} {surname}".strip()
    return n


def surname(name: str) -> str:
    return (name.split(",", 1)[0] if "," in name else name.split()[-1]).strip().lower()


def _search(q: str) -> dict | None:
    """The first Wikidata item whose description gives a death year and whose label names the person.
    A 429 is waited out; the caller treats a failure as "not now", not as "no such person"."""
    params = {
        "action": "wbsearchentities",
        "search": q,
        "language": "en",
        "format": "json",
        "limit": "5",
        "type": "item",
    }
    url = API + "?" + urlencode(params)
    r = None
    for attempt in range(4):
        r = http_get(url)
        if r.status_code == 429:
            time.sleep(5 * (attempt + 1))
            continue
        break
    assert r is not None
    r.raise_for_status()
    for hit in r.json().get("search", []):
        desc = hit.get("description") or ""
        label = hit.get("label") or ""
        m = _LIFE.search(desc)
        if not m:
            continue
        if surname(q) not in label.lower() and surname(q) not in desc.lower():
            continue
        return {
            "label": label,
            "description": desc,
            "born": int(m.group(1)),
            "died": int(m.group(2)),
        }
    return None


def lookup(name: str) -> tuple[int | None, int | None] | None:
    """(born, died) for a person, or None. Cached by the query, including the misses."""
    q = query(name)
    if len(q.split()) < 2 or not re.search(r"[A-Za-z]", q):
        return None
    cache = _load()
    if q in cache:
        hit = cache[q]
    else:
        try:
            hit = _search(q)
        except Exception:  # noqa: BLE001  (a lookup that fails is not a miss, and is not cached)
            return None
        cache[q] = hit
        _save()
        time.sleep(2.0)  # gentler than the base fetcher's two: Wikidata's search API rate-limits
    if not hit:
        return None
    return int(hit["born"]), int(hit["died"])

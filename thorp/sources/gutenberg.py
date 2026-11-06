"""Project Gutenberg: catalogue, resolution of list rows to ids, polite cached fetching, stripping."""

from __future__ import annotations

import csv
import hashlib
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import requests

from thorp import manifest, paths

CATALOGUE_URL = "https://www.gutenberg.org/cache/epub/feeds/pg_catalog.csv"
TEXT_URLS = [
    "https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt",
    "https://www.gutenberg.org/files/{id}/{id}-0.txt",
]
CONTACT = os.environ.get("THORP_CONTACT", "contact via the thorp repository owner")
USER_AGENT = f"thorp-harness/0.1 (small-LM research on public-domain books; {CONTACT})"
REQUEST_INTERVAL_S = 2.0
SOURCE = "gutenberg"

_last_request = 0.0


# ---------------------------------------------------------------- lists


@dataclass
class ListRow:
    title: str
    author: str
    language: str
    family: str
    text: str


def read_list(path: str | Path) -> list[ListRow]:
    with open(paths.resolve(path), newline="", encoding="utf-8") as f:
        return [ListRow(**{k: (v or "").strip() for k, v in r.items()}) for r in csv.DictReader(f)]


def set_for_list(path: str | Path) -> str:
    return "hole-card" if "hole" in Path(path).stem else "recipe"


def book_id(gutenberg_id: int) -> str:
    return f"pg{gutenberg_id}"


# ---------------------------------------------------------------- catalogue


def _get(url: str) -> requests.Response:
    """GET with a project User-Agent, one request every two seconds, three retries on 5xx."""
    global _last_request
    for attempt in range(4):
        wait = REQUEST_INTERVAL_S - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
        try:
            r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=60)
        except requests.ConnectionError:
            if attempt == 3:
                raise
            continue
        if r.status_code < 500 or attempt == 3:
            return r
    return r


def catalogue_path() -> Path:
    return paths.catalogue_dir() / "pg_catalog.csv"


def ensure_catalogue() -> Path:
    p = catalogue_path()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        r = _get(CATALOGUE_URL)
        r.raise_for_status()
        p.write_bytes(r.content)
    return p


_catalogue_cache: list[dict] | None = None


def catalogue() -> list[dict]:
    global _catalogue_cache
    if _catalogue_cache is None:
        with open(ensure_catalogue(), newline="", encoding="utf-8") as f:
            _catalogue_cache = list(csv.DictReader(f))
    return _catalogue_cache


# ---------------------------------------------------------------- resolution


def norm(s: str) -> str:
    """Lowercase, strip accents and punctuation, collapse whitespace. CJK passes through."""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^\w\s]", " ", s.lower())
    s = s.replace("_", " ")
    return re.sub(r"\s+", " ", s).strip()


def surname(author: str) -> str:
    parts = norm(author).split()
    return parts[-1] if parts else ""


@dataclass
class Resolution:
    row: ListRow
    candidates: list[tuple[int, str, str]] = field(default_factory=list)  # (id, title, authors)
    chosen: int | None = None
    how: str = ""


def load_overrides() -> dict[tuple[str, str], int]:
    p = paths.resolve("lists/overrides.csv")
    if not p.exists():
        return {}
    with open(p, newline="", encoding="utf-8") as f:
        return {
            (r["title"].strip(), (r.get("author") or "").strip()): int(r["gutenberg_id"])
            for r in csv.DictReader(f)
            if r.get("gutenberg_id", "").strip()
        }


def resolve(row: ListRow, overrides: dict | None = None) -> Resolution:
    overrides = load_overrides() if overrides is None else overrides
    res = Resolution(row)
    want = norm(row.title)
    sur = surname(row.author)
    for c in catalogue():
        if c["Type"] != "Text":
            continue
        langs = [x.strip() for x in c["Language"].split(";")]
        if row.language not in langs:
            continue
        if want and want in norm(c["Title"]):
            res.candidates.append((int(c["Text#"]), c["Title"].replace("\n", " "), c["Authors"]))
    res.candidates.sort()
    key = (row.title, row.author)
    if key in overrides:
        res.chosen, res.how = overrides[key], "override"
        return res
    if not res.candidates:
        res.how = "unresolved"
        return res
    by_author = [c for c in res.candidates if sur and sur in norm(c[2])]
    pick = by_author or res.candidates
    res.chosen = pick[0][0]
    res.how = "title+author" if by_author else "title only"
    return res


def resolve_list(path: str | Path) -> list[Resolution]:
    overrides = load_overrides()
    return [resolve(r, overrides) for r in read_list(path)]


def write_resolution_csv(list_path: str | Path, resolutions: list[Resolution]) -> Path:
    """data/resolution.csv holds every list fetched so far; rows for this list are replaced."""
    out = paths.data_dir() / "resolution.csv"
    list_name = str(list_path)
    keep = []
    if out.exists():
        with open(out, newline="", encoding="utf-8") as f:
            keep = [r for r in csv.DictReader(f) if r["list"] != list_name]
    fields = ["list", "title", "author", "language", "chosen", "how", "n_candidates", "candidates"]
    rows = keep + [
        {
            "list": list_name,
            "title": r.row.title,
            "author": r.row.author,
            "language": r.row.language,
            "chosen": r.chosen or "",
            "how": r.how,
            "n_candidates": len(r.candidates),
            "candidates": " | ".join(f"{i}: {t} / {a}" for i, t, a in r.candidates[:25]),
        }
        for r in resolutions
    ]
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    unresolved = [r for r in resolutions if r.chosen is None]
    if unresolved:
        up = paths.data_dir() / "unresolved.csv"
        with open(up, "a", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            for r in unresolved:
                w.writerow([list_name, r.row.title, r.row.author, r.row.language])
    return out


# ---------------------------------------------------------------- fetch and strip


def raw_path(gid: int) -> Path:
    return paths.texts_dir(SOURCE) / f"{gid}.txt"


def fetch(gid: int) -> Path:
    """Fetch the plain text for a Gutenberg id, once. Never re-fetches a cached file."""
    p = raw_path(gid)
    if p.exists() and p.stat().st_size > 0:
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for tmpl in TEXT_URLS:
        r = _get(tmpl.format(id=gid))
        if r.status_code == 200 and r.content:
            p.write_bytes(r.content)
            return p
        last = r.status_code
    raise RuntimeError(f"could not fetch Gutenberg {gid} (last status {last})")


_START = re.compile(r"^\*\*\*\s*START OF", re.IGNORECASE)
_END = re.compile(r"^\*\*\*\s*END OF", re.IGNORECASE)
_LICENCE = re.compile(
    r"^\s*(end of (the )?project gutenberg|\*\*\* ?end of|start: full license"
    r"|the full project gutenberg license)",
    re.IGNORECASE,
)


def strip(raw: str) -> str:
    """Keep the text between the START and END markers; drop a surviving licence block."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n").lstrip("﻿")
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if _START.match(ln)), None)
    end = next((i for i, ln in enumerate(lines) if _END.match(ln)), None)
    if start is not None:
        lines = lines[start + 1 :]
        if end is not None:
            end -= start + 1
    if end is not None and end >= 0:
        lines = lines[:end]
    else:
        cut = next((i for i, ln in enumerate(lines) if _LICENCE.match(ln)), None)
        if cut is not None:
            lines = lines[:cut]
    return "\n".join(lines).strip("\n") + "\n"


def text(gid: int) -> str:
    raw = raw_path(gid).read_bytes().decode("utf-8", errors="replace")
    return strip(raw)


def fetch_and_register(res: Resolution, set_name: str) -> manifest.Book:
    assert res.chosen is not None
    gid = res.chosen
    fetch(gid)
    t = text(gid)
    b = t.encode("utf-8")
    book = manifest.Book(
        id=book_id(gid),
        source=SOURCE,
        title=res.row.title,
        author=res.row.author,
        language=res.row.language,
        family=res.row.family,
        text=res.row.text,
        chars=len(t),
        bytes=len(b),
        sha1=hashlib.sha1(b).hexdigest(),
        fetched_at=datetime.fromtimestamp(raw_path(gid).stat().st_mtime, UTC).isoformat(),
        set=set_name,
    )
    manifest.upsert(book)
    return book


def book_text(bid: str) -> str:
    assert bid.startswith("pg"), bid
    return text(int(bid[2:]))


def fetch_list(list_path: str | Path, set_name: str | None = None):
    """Resolve, fetch, strip and register every row of a list.

    Returns [(Resolution, Book | None, error | None)] and rewrites data/resolution.csv.
    """
    set_name = set_name or set_for_list(list_path)
    resolutions = resolve_list(list_path)
    write_resolution_csv(list_path, resolutions)
    out = []
    for r in resolutions:
        if r.chosen is None:
            out.append((r, None, "unresolved"))
            continue
        try:
            out.append((r, fetch_and_register(r, set_name), None))
        except Exception as e:  # noqa: BLE001
            out.append((r, None, str(e)))
    return out

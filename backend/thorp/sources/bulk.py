"""Bulk sources: one record at a time from a corpus that is too big to fetch book by book.

The per-item fetcher (thorp/sources/base.py) turns a `<source>:<identifier>` into one book. A bulk
source is the same idea over a dataset: it yields a `BulkBook` for each volume in a Hugging Face
dataset, an Internet Archive collection or a folder of licensed texts. `thorp gather` (thorp/gather.py)
puts every yielded book through acquisition's S3 intake gate, so the rules do not depend on how the
text arrived.

Adapters:

- `common-pile-pre-1929`, `common-pile-loc`: Common Pile's gzip JSON shards (Dolma records).
- `blbooks`: the British Library's parquet, one row per page; pages are joined into a volume.
- `americanstories`: yearly tar.gz of page JSON; pages are joined into an issue.
- `archive`: an Internet Archive collection, by its advanced-search query.
- `institutional-books`: Harvard's gated parquet, after the agreement.
- `folder`: a directory of licensed texts (EEBO-TCP, HathiTrust or Google exports) with a metadata CSV.

Nothing here decides what may enter the library: it maps a record's own words and dates into Nothing up my sleeve's
fields, and `gather` asks the gate. A source that is walled in thorp/sources/catalog.py has no adapter.
"""

from __future__ import annotations

import csv
import fnmatch
import gzip
import json
import re
import sqlite3
import tarfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol
from urllib.parse import quote

from thorp import paths


@dataclass
class BulkBook:
    """One volume as a bulk source reads it, before the gate."""

    ident: str
    title: str
    authors: str
    language: str  # ISO 639-1 where the source gives one ("en", "fr")
    published: int | None
    origin: str
    text: str
    extra: dict = field(default_factory=dict)


class BulkSource(Protocol):
    key: str
    prefix: str
    name: str
    unsigned: (
        bool  # the records are mostly unsigned (newspapers): the proposed 'signed' rule speaks
    )

    def books(self, *, limit: int | None = None, offset: int = 0, **kw) -> Iterator[BulkBook]: ...


BULK_SOURCES: dict[str, BulkSource] = {}


def register_bulk(src: BulkSource) -> BulkSource:
    BULK_SOURCES[src.key] = src
    return src


def bulk_sources() -> dict[str, BulkSource]:
    from thorp.sources import classics, cuneiform  # noqa: F401  (importing registers them)

    return BULK_SOURCES


def source(key: str) -> BulkSource:
    src = bulk_sources().get(key)
    if src is None:
        raise KeyError(
            f"no bulk adapter {key!r}; the adapters: {', '.join(sorted(bulk_sources())) or 'none'}"
        )
    return src


# ------------------------------------------------------------------------------------ the Hugging Face cache


def hf_home() -> Path:
    return paths.data_dir() / "catalogue" / "hf"


def _files_cache() -> Path:
    return paths.data_dir() / "catalogue" / "hf-files.json"


def hf_files(repo: str, pattern: str = "*") -> list[str]:
    """The dataset's files matching `pattern`, sorted. The list is cached in data/catalogue/hf-files.json,
    so a second gather does not ask Hugging Face again."""
    cache = _files_cache()
    cache.parent.mkdir(parents=True, exist_ok=True)
    known: dict[str, list[str]] = {}
    if cache.exists():
        known = json.loads(cache.read_text(encoding="utf-8"))
    if repo not in known:
        from huggingface_hub import list_repo_files

        known[repo] = sorted(list_repo_files(repo, repo_type="dataset"))
        cache.write_text(json.dumps(known, indent=1), encoding="utf-8")
    return [f for f in known[repo] if fnmatch.fnmatch(f, pattern)]


def hf_download(repo: str, path: str) -> Path:
    """One file, in data/catalogue/hf (not the user's cache): the pipeline's cache is the library's."""
    from huggingface_hub import hf_hub_download

    return Path(
        hf_hub_download(
            repo_id=repo,
            filename=path,
            repo_type="dataset",
            cache_dir=str(hf_home()),
        )
    )


def hf_available(repo: str) -> tuple[bool, str]:
    """Whether the dataset can be read with the token in the environment, and why not."""
    try:
        hf_files(repo)
        return True, ""
    except Exception as e:  # noqa: BLE001  (gated and missing are both "not now")
        return False, str(e)[:300]


# ------------------------------------------------------------------------------------ fields


_LANG = {
    "en": "en",
    "eng": "en",
    "english": "en",
    "fr": "fr",
    "fre": "fr",
    "fra": "fr",
    "french": "fr",
    "de": "de",
    "ger": "de",
    "deu": "de",
    "german": "de",
    "es": "es",
    "spa": "es",
    "spanish": "es",
    "it": "it",
    "ita": "it",
    "italian": "it",
    "nl": "nl",
    "dut": "nl",
    "nld": "nl",
    "la": "la",
    "lat": "la",
    "latin": "la",
    "grc": "el",
    "gre": "el",
    "el": "el",
    "greek": "el",
    "dutch": "nl",
    "hebrew": "he",
    "middle english": "en",
    "low german": "de",
    "he": "he",
    "heb": "he",
    "ar": "ar",
    "ara": "ar",
    "ru": "ru",
    "rus": "ru",
    "pt": "pt",
    "por": "pt",
    "zh": "zh",
    "chi": "zh",
}


def iso_language(value) -> str:
    """A source's language field as one ISO code, the first when it names several."""
    if isinstance(value, (list, tuple)):
        for v in value:
            if v:
                return iso_language(v)
        return ""
    first = re.split(r"[;,/|]", str(value or ""))[0].strip().lower()
    return _LANG.get(first, first[:8])


def year_of(value) -> int | None:
    """A printing year from a number or a catalogue string; None for '[18--]', 'n.d.' and the like."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        y = int(value)
        return y if 1000 <= y <= 2100 else None
    m = re.search(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", str(value or ""))
    return int(m.group(1)) if m else None


def safe_id(value: str, *, limit: int = 120) -> str:
    """A record's own id as a file name and manifest id: letters, digits, dot, dash, underscore."""
    s = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip(".-")
    return (s or "book")[:limit]


def _int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def repair_long_s(text: str, year: int | None) -> str:
    """OCR reads the long s (ſ) as "f" before 1800: the archive source's repair, applied to any early scan.
    Every other year is left alone (it would read "first" as "firſt" back)."""
    if not text or year is None or year >= 1800:
        return text
    from thorp.sources.archive import fix_long_s, lexicon

    return fix_long_s(text, lexicon())


def _text(value) -> str:
    if isinstance(value, list):
        return "\n\n".join(str(v) for v in value if v)
    return str(value or "")


# ------------------------------------------------------------------------------------ Common Pile


class CommonPile:
    """Common Pile's gzip shards: one JSON record a line, the text and the catalogue's metadata."""

    unsigned = False

    def __init__(self, key: str, name: str, repo: str, pattern: str, prefix: str):
        self.key, self.name, self.repo, self.pattern, self.prefix = key, name, repo, pattern, prefix

    def books(self, *, limit: int | None = None, offset: int = 0, **_):
        seen = skipped = 0
        for file in hf_files(self.repo, self.pattern):
            path = hf_download(self.repo, file)
            with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
                for line in f:
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    b = self.book(row)
                    if b is None:
                        continue
                    if skipped < offset:
                        skipped += 1
                        continue
                    yield b
                    seen += 1
                    if limit is not None and seen >= limit:
                        return

    def book(self, row: dict) -> BulkBook | None:  # pragma: no cover - the two adapters below
        raise NotImplementedError


class Pre1929(CommonPile):
    """common-pile/pre_1929_books_filtered: HathiTrust (and so Google) scans, US public domain."""

    def __init__(self):
        super().__init__(
            "common-pile-pre-1929",
            "Common Pile: pre-1929 books",
            "common-pile/pre_1929_books_filtered",
            "public_library_1929_dolma-*.json.gz",
            "cp29-",
        )

    def book(self, row: dict) -> BulkBook | None:
        md = row.get("metadata") or {}
        text = _text(row.get("text"))
        if not text.strip():
            return None
        ident = row.get("id") or md.get("htid") or md.get("ia_ark_id")
        year = year_of(md.get("year"))
        return BulkBook(
            ident=safe_id(str(ident)),
            title=_text(md.get("title")),
            authors=_text(md.get("author")),
            language=iso_language(md.get("language")),
            published=year,
            origin=_text(md.get("ia_url") or md.get("hathi_url")),
            text=repair_long_s(text, year),
            extra={"htid": md.get("htid", ""), "provenance": md.get("provenance", "")},
        )


class LibraryOfCongress(CommonPile):
    """common-pile/library_of_congress: the LoC's Selected Digitized Books, CC-BY-4.0 compilation."""

    def __init__(self):
        super().__init__(
            "common-pile-loc",
            "Common Pile: Library of Congress books",
            "common-pile/library_of_congress",
            "data/*.jsonl.gz",
            "loc-",
        )

    def book(self, row: dict) -> BulkBook | None:
        md = row.get("metadata") or {}
        text = _text(row.get("text"))
        if not text.strip():
            return None
        year = year_of(md.get("year"))
        return BulkBook(
            ident=safe_id(str(row.get("id"))),
            title=_text(md.get("title")),
            authors=_text(md.get("author")),
            language=iso_language(md.get("language")),
            published=year,
            origin=_text(md.get("item_url") or md.get("text_file_url")),
            text=repair_long_s(text, year),
            extra={"license": md.get("license", "")},
        )


# ------------------------------------------------------------------------------------ British Library


class BritishLibrary:
    """The British Library's parquet: one row a page, records contiguous. Pages of a record are joined
    in `pg` order into one volume; a record never spans two shards (checked on the first shard)."""

    key, prefix, name, unsigned = "blbooks", "bl-", "British Library books", False
    repo = "TheBritishLibrary/blbooks"
    columns = [
        "record_id", "pg", "date", "title", "all_names", "name",
        "Language_1", "empty_pg", "text",
    ]  # fmt: skip

    def books(self, *, limit: int | None = None, offset: int = 0, **_):
        import pyarrow.parquet as pq

        seen = skipped = 0
        for file in hf_files(self.repo, "*.parquet"):
            pf = pq.ParquetFile(hf_download(self.repo, file))
            current: dict | None = None
            for batch in pf.iter_batches(batch_size=8192, columns=self.columns):
                for row in batch.to_pylist():
                    rid = row.get("record_id")
                    if current is None or rid != current["record_id"]:
                        if current is not None:
                            if skipped < offset:
                                skipped += 1
                            else:
                                b = self._volume(current)
                                if b is not None:
                                    yield b
                                    seen += 1
                                    if limit is not None and seen >= limit:
                                        return
                        current = {"record_id": rid, "pages": [], "rows": []}
                    current["pages"].append((_int(row.get("pg")), _text(row.get("text"))))
                    current["rows"].append(row)
            if current is not None:
                if skipped < offset:
                    skipped += 1
                else:
                    b = self._volume(current)
                    if b is not None:
                        yield b
                        seen += 1
                        if limit is not None and seen >= limit:
                            return

    def _volume(self, current: dict) -> BulkBook | None:
        rows = current["rows"]
        first = rows[0]
        pages = [t for _, t in sorted(current["pages"]) if t.strip()]
        text = "\n\n".join(pages)
        if not text.strip():
            return None
        date = first.get("date")
        year = year_of(date)
        return BulkBook(
            ident=safe_id(current["record_id"]),
            title=_text(first.get("title")),
            authors=_text(first.get("all_names") or first.get("name")),
            language=iso_language(first.get("Language_1")),
            published=year,
            origin=f"https://huggingface.co/datasets/{self.repo}#{current['record_id']}",
            text=repair_long_s(text, year),
            extra={"pages": len(pages), "raw_date": first.get("raw_date", "")},
        )


# ------------------------------------------------------------------------------------ AmericanStories


class AmericanStories:
    """Newspaper pages from Chronicling America, yearly tar.gz of page JSON. Pages are joined into an
    issue (one LCCN on one date). The tar is staged in SQLite so a year larger than memory can pass
    through; the staged rows are deleted with the file at the end of the year."""

    key, prefix, name, unsigned = "americanstories", "as-", "AmericanStories", True
    repo = "dell-research-harvard/AmericanStories"

    def books(self, *, limit: int | None = None, offset: int = 0, year: int | None = None, **_):
        years = [year] if year else self._years()
        seen = skipped = 0
        for y in years:
            path = hf_download(self.repo, f"faro_{y}.tar.gz")
            for b in self._issues(path, y):
                if skipped < offset:
                    skipped += 1
                    continue
                yield b
                seen += 1
                if limit is not None and seen >= limit:
                    return

    def _years(self) -> list[int]:
        out = []
        for f in hf_files(self.repo, "faro_*.tar.gz"):
            if m := re.search(r"faro_(\d{4})", f):
                out.append(int(m.group(1)))
        return sorted(out)

    def _issues(self, path: Path, year: int) -> Iterator[BulkBook]:
        stage = paths.data_dir() / "catalogue" / "americanstories" / f"{year}.sqlite3"
        stage.parent.mkdir(parents=True, exist_ok=True)
        if stage.exists():
            stage.unlink()
        con = sqlite3.connect(stage)
        con.execute(
            "create table pages (issue text, page int, title text, date text, lccn text, text text)"
        )
        try:
            with tarfile.open(path, "r:gz") as tar:
                for member in tar:
                    if not member.name.endswith(".json"):
                        continue
                    f = tar.extractfile(member)
                    if f is None:
                        continue
                    try:
                        d = json.load(f)
                    except json.JSONDecodeError:
                        continue
                    self._stage(con, d, member.name)
            con.commit()
            rows = con.execute(
                "select issue, page, title, date, lccn, text from pages order by issue, page"
            )
            current = None
            for issue, _page, title, date, lccn, text in rows:
                if current is None or issue != current["issue"]:
                    if current is not None:
                        b = self._issue(current)
                        if b is not None:
                            yield b
                    current = {
                        "issue": issue,
                        "title": title,
                        "date": date,
                        "lccn": lccn,
                        "texts": [],
                    }
                if text:
                    current["texts"].append(text)
            if current is not None:
                b = self._issue(current)
                if b is not None:
                    yield b
        finally:
            con.close()
            stage.unlink(missing_ok=True)

    def _stage(self, con: sqlite3.Connection, d: dict, name: str) -> None:
        lccn = (d.get("lccn") or {}).get("lccn") or ""
        title = (d.get("lccn") or {}).get("title") or ""
        date = (d.get("edition") or {}).get("date") or ""
        m = re.search(r"(\d{4}-\d{2}-\d{2})", name)
        date = date or (m.group(1) if m else "")
        pages = d.get("full articles") or []
        text = "\n\n".join(
            "\n".join(x for x in (a.get("headline") or "", a.get("article") or "") if x).strip()
            for a in pages
        ).strip()
        if not lccn or not date or not text:
            return
        con.execute(
            "insert into pages values (?,?,?,?,?,?)",
            (f"{lccn}_{date}", _int(d.get("page_number")), title, date, lccn, text),
        )

    def _issue(self, current: dict) -> BulkBook | None:
        text = "\n\n".join(current["texts"]).strip()
        if not text:
            return None
        year = year_of(current["date"])
        return BulkBook(
            ident=safe_id(current["issue"]),
            title=_text(current["title"]),
            authors="",  # newspapers are unsigned
            language="en",
            published=year,
            origin=f"https://chroniclingamerica.loc.gov/lccn/{current['lccn']}/{current['date']}/ed-1/",
            text=repair_long_s(text, year),
            extra={"lccn": current["lccn"], "date": current["date"]},
        )


# ------------------------------------------------------------------------------------ Internet Archive


ARCHIVE_FIELDS = (
    "identifier",
    "title",
    "year",
    "date",
    "language",
    "publisher",
    "description",
    "collection",
    "licenseurl",
    "creator",
)


def archive_search(query: str, rows: int = 1000, page: int = 1) -> list[dict]:
    """One advanced-search page, with the fields the bulk adapters judge on."""
    from thorp.sources.base import http_get

    fields = "".join(f"&fl%5B%5D={f}" for f in ARCHIVE_FIELDS)
    url = (
        f"https://archive.org/advancedsearch.php?q={quote(query)}"
        f"{fields}&rows={rows}&page={page}&output=json"
    )
    r = http_get(url)
    r.raise_for_status()
    return (r.json().get("response") or {}).get("docs") or []


class ArchiveCollection:
    """An Internet Archive collection by its advanced-search query, one item at a time. The per-item
    fetch is thorp/sources/archive.py's, so the OCR cleaning and the long-s repair are the same."""

    key, prefix, name, unsigned = "archive", "ia-", "Internet Archive", False

    def books(self, *, limit: int | None = None, offset: int = 0, collection: str = "", **_):
        from thorp.sources.archive import ArchiveSource

        if not collection:
            raise ValueError("archive needs a collection, e.g. --collection americana")
        if limit is None:
            raise ValueError("archive needs --limit: a collection can be millions of items, one request each")
        rows = min(1000, max(1, limit + offset))
        docs = archive_search(f"collection:{collection} AND mediatype:texts", rows=rows)
        src = ArchiveSource()
        seen = skipped = 0
        for doc in docs:
            ident = doc.get("identifier")
            if not ident:
                continue
            if skipped < offset:
                skipped += 1
                continue
            try:
                f = src.fetch(ident)
            except Exception:  # noqa: BLE001  (an item without text is not the collection's failure)
                continue
            yield BulkBook(
                ident=safe_id(ident),
                title=f.title,
                authors=f.author,
                language=f.language,
                published=f.published,
                origin=f.origin,
                text=f.text,
            )
            seen += 1
            if limit is not None and seen >= limit:
                return


# ------------------------------------------------------------------------------------ Incunabula


class Incunabula:
    """The Boston Public Library's incunabula on the Internet Archive, 1450-1500, filtered by
    thorp/sources/incunabula.py. A discovery set, not a training recipe: it is mostly Latin."""

    key, prefix, name, unsigned = "incunabula", "inc-", "Incunabula (pre-1501 printing)", True

    def books(self, *, limit: int | None = None, offset: int = 0, **_):
        from thorp.sources import incunabula as inc

        docs = [d for d in archive_search(inc.QUERY, rows=1000) if inc.plausible(d)]
        seen = skipped = 0
        for doc in docs:
            ident = doc.get("identifier")
            if not ident:
                continue
            if skipped < offset:
                skipped += 1
                continue
            try:
                f = inc.from_doc(doc)
            except Exception:  # noqa: BLE001  (one bad item does not stop the set)
                continue
            if len(f.text) < inc.MIN_CHARS:
                continue
            year = inc.year_of(doc)
            yield BulkBook(
                ident=safe_id(ident),
                title=f.title or _text(doc.get("title")),
                authors=f.author,
                language=iso_language(f.language) or iso_language(doc.get("language")),
                published=year,
                origin=f.origin,
                text=f.text,
                extra={
                    "licence": doc.get("licenseurl", ""),
                    "publisher": _text(doc.get("publisher")),
                },
            )
            seen += 1
            if limit is not None and seen >= limit:
                return


# ------------------------------------------------------------------------------------ Institutional Books


class InstitutionalBooks:
    """Harvard's Institutional Books 1.0, gated. The parquet carries `text` and the catalogue's
    `title_src`, `author_src`, `date1_src`, `language_src`, `ocr_score_src`, `barcode_src`."""

    key, prefix, name, unsigned = "institutional-books", "ib-", "Institutional Books 1.0", False
    repo = "institutional/institutional-books-1.0"

    def books(self, *, limit: int | None = None, offset: int = 0, **_):
        ok, why = hf_available(self.repo)
        if not ok:
            raise PermissionError(
                "Institutional Books is gated: accept the terms at "
                f"https://huggingface.co/datasets/{self.repo} and set HF_TOKEN. ({why})"
            )
        import pyarrow.parquet as pq

        seen = skipped = 0
        for file in hf_files(self.repo, "*.parquet"):
            pf = pq.ParquetFile(hf_download(self.repo, file))
            names = set(pf.schema_arrow.names)
            cols = [
                c
                for c in (
                    "text",
                    "barcode_src",
                    "title_src",
                    "author_src",
                    "date1_src",
                    "language_src",
                )
                if c in names
            ]
            if "text" not in cols:
                continue
            for batch in pf.iter_batches(batch_size=2048, columns=cols):
                for row in batch.to_pylist():
                    text = _text(row.get("text"))
                    if not text.strip():
                        continue
                    b = BulkBook(
                        ident=safe_id(str(row.get("barcode_src") or "")),
                        title=_text(row.get("title_src")),
                        authors=_text(row.get("author_src")),
                        language=iso_language(row.get("language_src")),
                        published=year_of(row.get("date1_src")),
                        origin=f"https://huggingface.co/datasets/{self.repo}#{row.get('barcode_src', '')}",
                        text=text,
                    )
                    if skipped < offset:
                        skipped += 1
                        continue
                    yield b
                    seen += 1
                    if limit is not None and seen >= limit:
                        return


# ------------------------------------------------------------------------------------ licensed folders


class Folder:
    """A directory of licensed texts (EEBO-TCP, a HathiTrust or Google export) with a metadata CSV:
    `file,title,author,language,year,origin` (only `file` required). One file a volume."""

    key, prefix, name, unsigned = "folder", "fld-", "a licensed folder", False

    def books(
        self, *, limit: int | None = None, offset: int = 0, path: str = "", metadata: str = "", **_
    ):
        if not path:
            raise ValueError("folder needs --path")
        root = Path(path)
        rows: list[dict] = []
        if metadata:
            with Path(metadata).open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
        else:
            rows = [{"file": p.name} for p in sorted(root.glob("*.txt"))]
        seen = skipped = 0
        for r in rows:
            p = root / r["file"]
            if not p.exists():
                continue
            text = p.read_text(encoding="utf-8", errors="replace")
            b = BulkBook(
                ident=safe_id(p.stem),
                title=r.get("title") or p.stem,
                authors=r.get("author") or "",
                language=iso_language(r.get("language") or "en"),
                published=year_of(r.get("year")),
                origin=r.get("origin") or str(p),
                text=text,
            )
            if skipped < offset:
                skipped += 1
                continue
            yield b
            seen += 1
            if limit is not None and seen >= limit:
                return


# ------------------------------------------------------------------------------------ the registry

for _src in (
    Pre1929(),
    LibraryOfCongress(),
    BritishLibrary(),
    AmericanStories(),
    ArchiveCollection(),
    Incunabula(),
    InstitutionalBooks(),
    Folder(),
):
    register_bulk(_src)

del _src

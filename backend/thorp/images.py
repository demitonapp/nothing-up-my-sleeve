"""The Library's images (12 November, Justin: "can you also start gathering some images? I'd love to replace
fal with a Nothing up my sleeve image model").

The first source is the illustrations in Project Gutenberg's HTML editions. They come under the books' own
rule, read from the catalogue's authors field, where an illustrator is a person like any other
('Doré, Gustave, 1832-1883 [Illustrator]'): every named person dead by 1955, and none undated. The book
must also be English text with at least one credited illustrator, so the images have a maker on record.

Fetching goes through the Gutenberg source's own polite GET (its User-Agent, one request every two
seconds), so an image gathering is as gentle as a book fetch. Files land in data/images/gutenberg/<id>/,
outside the repository like the texts; each kept image is one line of data/images/manifest.jsonl with
where it came from, who made it, its caption, size and hash. Decorations (initials, rules, tailpieces)
are left out by size.

Not yet under acquisition's Liberty Machine: no intake lock, no S3 audit, no Postgres table. This is the pilot that
shows what is there; moving it under the intake gate is the next step once the shelf is worth keeping.

Usage:
  thorp images gather --illustrator Doré --limit 3
  thorp images gather --ids 2701 11 --per-book 20
  thorp images candidates --illustrator Rackham
  thorp images summary
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from thorp import paths
from thorp.acquisition import DIED_BY, persons
from thorp.sources import gutenberg

HTML_URL = "https://www.gutenberg.org/cache/epub/{id}/pg{id}-images.html"
MIN_SIDE = 200  # px: below this on either side an image is a decoration, not a picture
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".gif")
# The transcriber's photographs of the physical book (its cover, spine, back) are recent photographs of an
# object, not the period's pictures: left out by name (12 November, the first Doré gathering kept a spine).
NOT_PLATES = re.compile(r"(^|[-_])(cover|bookcover|frontcover|backcover|spine|back|endpaper)s?([-_.]|$)", re.I)


def is_plate(url: str) -> bool:
    return not NOT_PLATES.search(Path(url.split("?")[0]).name)


def images_dir() -> Path:
    return paths.data_dir() / "images"


def manifest_path() -> Path:
    return images_dir() / "manifest.jsonl"


# ---------------------------------------------------------------- the rule


def _illustrators(authors: str) -> list[str]:
    return [p.name for p in persons(authors) if "illustrat" in p.role.lower()]


def verdict(row: dict) -> list[str]:
    """Why a catalogue row's images may not be gathered; empty when they may."""
    bad = []
    if (row.get("Type") or "").strip() != "Text":
        bad.append("not a text")
    if "en" not in [x.strip() for x in (row.get("Language") or "").split(";")]:
        bad.append("not English")
    people = persons(row.get("Authors") or "")
    if not any("illustrat" in p.role.lower() for p in people):
        bad.append("no credited illustrator")
    for p in people:
        role = f" ({p.role})" if p.role else ""
        if p.died is None:
            bad.append(f"{p.name}{role} has no death year")
        elif p.died > DIED_BY:
            bad.append(f"{p.name}{role} died in {p.died}")
    return bad


def candidates(illustrator: str = "", limit: int | None = None) -> list[dict]:
    """Catalogue rows whose illustrations pass the rule, optionally by an illustrator's name."""
    want = illustrator.lower()
    out = []
    for row in gutenberg.catalogue():
        if want and not any(want in n.lower() for n in _illustrators(row.get("Authors") or "")):
            continue
        if verdict(row):
            continue
        out.append(row)
        if limit and len(out) >= limit:
            break
    return out


# ---------------------------------------------------------------- the page


class _Figures(HTMLParser):
    """Every <img> in reading order with its alt text and the caption that follows it (Gutenberg's
    `p.caption`, `figcaption` or `span.caption`), up to the next image."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.figs: list[dict] = []
        self._in_caption = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "img" and a.get("src"):
            self.figs.append({"src": a["src"], "alt": (a.get("alt") or "").strip(), "caption": ""})
        elif self.figs and (tag == "figcaption" or "caption" in (a.get("class") or "")):
            self._in_caption += 1

    def handle_endtag(self, tag):
        if self._in_caption and tag in ("p", "figcaption", "span", "div"):
            self._in_caption -= 1

    def handle_data(self, data):
        if self._in_caption and self.figs:
            self.figs[-1]["caption"] = (self.figs[-1]["caption"] + " " + data).strip()


def figures(gid: int) -> tuple[str, list[dict]]:
    """The HTML edition's address and its figures, each with an absolute image URL."""
    url = HTML_URL.format(id=gid)
    r = gutenberg._get(url)
    if r.status_code != 200:
        return url, []
    p = _Figures()
    p.feed(r.text)
    out = []
    seen = set()
    for f in p.figs:
        src = urljoin(url, f["src"])
        if not src.lower().split("?")[0].endswith(IMAGE_EXT) or src in seen:
            continue
        seen.add(src)
        out.append({**f, "url": src, "caption": re.sub(r"\s+", " ", f["caption"])[:400]})
    return url, out


def size_of(b: bytes) -> tuple[int, int] | None:
    """Width and height from a PNG, GIF or JPEG header, without an imaging library."""
    if b[:8] == b"\x89PNG\r\n\x1a\n" and len(b) >= 24:
        return struct.unpack(">II", b[16:24])
    if b[:6] in (b"GIF87a", b"GIF89a") and len(b) >= 10:
        return struct.unpack("<HH", b[6:10])
    if b[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(b):
            if b[i] != 0xFF:
                i += 1
                continue
            marker = b[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", b[i + 5 : i + 9])
                return w, h
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            i += 2 + struct.unpack(">H", b[i + 2 : i + 4])[0]
    return None


# ---------------------------------------------------------------- gathering


@dataclass
class Image:
    id: str  # sha1 of the bytes
    source: str
    book: int
    title: str
    authors: str
    illustrators: list[str]
    page: str
    url: str
    path: str  # under data/images
    alt: str
    caption: str
    width: int
    height: int
    bytes: int
    gathered_at: str


def _known() -> set[str]:
    p = manifest_path()
    if not p.exists():
        return set()
    return {json.loads(line)["url"] for line in p.read_text().splitlines() if line.strip()}


def gather_book(row: dict, per_book: int = 30, known: set[str] | None = None) -> list[Image]:
    """Fetch one book's illustrations that pass the size bar, write them and their manifest lines."""
    gid = int(row["Text#"])
    if why := verdict(row):
        raise ValueError(f"book {gid} may not be gathered: {'; '.join(why)}")
    known = _known() if known is None else known
    page, figs = figures(gid)
    folder = images_dir() / "gutenberg" / str(gid)
    kept: list[Image] = []
    for f in figs:
        if len(kept) >= per_book:
            break
        if f["url"] in known or not is_plate(f["url"]):
            continue
        r = gutenberg._get(f["url"])
        if r.status_code != 200:
            continue
        b = r.content
        wh = size_of(b)
        if not wh or min(wh) < MIN_SIDE:
            continue
        folder.mkdir(parents=True, exist_ok=True)
        name = Path(f["url"].split("?")[0]).name
        (folder / name).write_bytes(b)
        img = Image(
            id=hashlib.sha1(b).hexdigest(),
            source="gutenberg",
            book=gid,
            title=(row.get("Title") or "").strip(),
            authors=(row.get("Authors") or "").strip(),
            illustrators=_illustrators(row.get("Authors") or ""),
            page=page,
            url=f["url"],
            path=str((folder / name).relative_to(images_dir())),
            alt=f["alt"],
            caption=f["caption"],
            width=wh[0],
            height=wh[1],
            bytes=len(b),
            gathered_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
        with manifest_path().open("a", encoding="utf-8") as out:
            out.write(json.dumps(asdict(img), ensure_ascii=False) + "\n")
        known.add(f["url"])
        kept.append(img)
    return kept


def gather(ids: list[int] | None = None, illustrator: str = "", limit: int = 3, per_book: int = 30) -> list[Image]:
    rows = {int(r["Text#"]): r for r in gutenberg.catalogue()} if ids else {}
    books = [rows[i] for i in ids if i in rows] if ids else candidates(illustrator, limit)
    images_dir().mkdir(parents=True, exist_ok=True)
    known = _known()
    out: list[Image] = []
    for row in books:
        try:
            got = gather_book(row, per_book, known)
        except ValueError as e:
            print(f"skipped: {e}", flush=True)
            continue
        print(f"{row['Text#']}: {len(got)} images · {row['Title'].splitlines()[0][:60]}", flush=True)
        out += got
    return out


def prune() -> list[dict]:
    """Drop gathered images that are not plates under today's rule: their manifest lines and their files.
    Run it when nothing is gathering (the manifest is rewritten whole)."""
    rows = manifest()
    keep = [r for r in rows if is_plate(r["url"])]
    gone = [r for r in rows if not is_plate(r["url"])]
    for r in gone:
        p = (images_dir() / r["path"]).resolve()
        if images_dir().resolve() in p.parents and p.exists():
            p.unlink()
    if gone:
        tmp = manifest_path().with_suffix(".tmp")
        tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8")
        tmp.replace(manifest_path())
    return gone


# ---------------------------------------------------------------- reading


def manifest() -> list[dict]:
    p = manifest_path()
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def summary() -> dict:
    rows = manifest()
    books: dict[int, dict] = {}
    for r in rows:
        b = books.setdefault(r["book"], {"book": r["book"], "title": r["title"], "illustrators": r["illustrators"], "images": 0})
        b["images"] += 1
    return {
        "images": len(rows),
        "books": len(books),
        "bytes": sum(r["bytes"] for r in rows),
        "by_book": sorted(books.values(), key=lambda b: -b["images"]),
        "rule": f"Gutenberg HTML illustrations; English text; at least one credited illustrator; every named person dead by {DIED_BY}; at least {MIN_SIDE}px a side",
        "items": rows[-600:][::-1],
    }


def file_for(image_id: str) -> tuple[Path, str] | None:
    """The file and content type of a gathered image, by its id; None when unknown."""
    for r in manifest():
        if r["id"] == image_id:
            p = (images_dir() / r["path"]).resolve()
            if images_dir().resolve() not in p.parents or not p.exists():
                return None
            ext = p.suffix.lower()
            return p, {".png": "image/png", ".gif": "image/gif"}.get(ext, "image/jpeg")
    return None

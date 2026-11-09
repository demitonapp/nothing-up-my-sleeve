"""Cuneiform: the Electronic Text Corpus of Sumerian Literature (ETCSL).

ETCSL's 243 compositions are Sumerian literary texts with a transliteration and an English
translation. The composite page (`text=c.<id>`) holds the transliteration line by line; the
translation page (`text=t.<id>`) holds the translation. A **cuneiform** set is a discovery corpus:
the texts are anonymous, ancient, and not English, so the English/period rules do not apply; the
deck, duplicate and provenance rules do.

The catalogue is one page (`edition2/etcslfullcat.php`); the compositions are fetched one at a time,
two requests each, through the polite fetcher. The text is kept as transliteration + translation.
"""

from __future__ import annotations

import re
from html import unescape
from html.parser import HTMLParser

from thorp.sources.base import http_get
from thorp.sources.bulk import BulkBook, register_bulk, safe_id

CATALOGUE = "https://etcsl.orinst.ox.ac.uk/edition2/etcslfullcat.php"
BASE = "https://etcsl.orinst.ox.ac.uk/cgi-bin/etcsl.cgi"
MIN_CHARS = 400


class _Cells(HTMLParser):
    """The text of every `<td>` (transliteration rows) or `<p>` (translation paragraphs)."""

    def __init__(self, tag: str):
        super().__init__()
        self.tag = tag
        self.inside = False
        self.buf: list[str] = []
        self.rows: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag == self.tag:
            self.inside = True
            self.buf = []

    def handle_endtag(self, tag):
        if tag == self.tag and self.inside:
            self.rows.append(" ".join("".join(self.buf).split()))
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.buf.append(data)


def catalogue() -> list[tuple[str, str]]:
    """(composition id, title) from the complete catalogue, in catalogue order."""
    t = http_get(CATALOGUE).text
    out = []
    for mid, title in re.findall(r"<li><b>(\d+\.\d+\.\d+)</b>\s*([^<]+)", t):
        out.append((mid, unescape(title).strip()))
    return out


def _strip_navigation(rows: list[str]) -> list[str]:
    bad = ("ETCSL", "transliteration :", "translation :", "cgi-bin", "Home", "Catalogue", "Search")
    return [r for r in rows if len(r) > 10 and not any(b.lower() in r.lower() for b in bad)]


def transliteration(mid: str) -> str:
    t = http_get(f"{BASE}?text=c.{mid}&charenc=j").text
    p = _Cells("td")
    p.feed(t)
    lines = [r for r in _strip_navigation(p.rows) if not re.fullmatch(r"\d+\.", r)]
    return "\n".join(lines).strip()


def translation(mid: str) -> str:
    t = http_get(f"{BASE}?text=t.{mid}&charenc=j").text
    p = _Cells("p")
    p.feed(t)
    return "\n\n".join(_strip_navigation(p.rows)).strip()


class ETCSL:
    key, prefix, name, unsigned = "etcsl", "etc-", "ETCSL (Sumerian)", True

    def books(self, *, limit: int | None = None, offset: int = 0, **_):
        seen = skipped = 0
        for mid, title in catalogue():
            if skipped < offset:
                skipped += 1
                continue
            try:
                trans = transliteration(mid)
                english = translation(mid)
            except Exception:  # noqa: BLE001  (one composition does not stop the corpus)
                continue
            if len(trans) < MIN_CHARS:
                continue
            text = f"TRANSLITERATION\n\n{trans}"
            if english:
                text += f"\n\nTRANSLATION\n\n{english}"
            yield BulkBook(
                ident=safe_id(f"etcsl-{mid}"),
                title=title or f"ETCSL {mid}",
                authors="",  # the compositions are anonymous
                language="sux",  # Sumerian
                published=None,  # ancient: no printing year
                origin=f"https://etcsl.orinst.ox.ac.uk/cgi-bin/etcsl.cgi?text=c.{mid}",
                text=text,
                extra={"etcsl": mid},
            )
            seen += 1
            if limit is not None and seen >= limit:
                return


ATF_URL = "https://media.githubusercontent.com/media/cdli-gh/data/master/cdliatf_unblocked.atf"
ATF_NAME = "cdliatf_unblocked.atf"


def _atf_path():
    from thorp import paths

    p = paths.data_dir() / "classics" / ATF_NAME
    if p.exists() and p.stat().st_size > 1_000_000:
        return p
    import requests

    from thorp.sources.gutenberg import USER_AGENT

    p.parent.mkdir(parents=True, exist_ok=True)
    with requests.get(ATF_URL, headers={"User-Agent": USER_AGENT}, stream=True, timeout=600) as r:
        r.raise_for_status()
        with p.open("wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return p


def _records(path):
    """CDLI's ATF records: one &P... tablet, its language, its transliteration lines."""
    rec = None
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("&P"):
                if rec is not None:
                    yield rec
                head = line.strip()[1:]
                ident, _, title = head.partition("=")
                rec = {"id": ident.strip(), "title": title.strip(), "lang": "", "lines": []}
                continue
            if rec is None:
                continue
            if line.startswith("#atf: lang"):
                rec["lang"] = line.split("lang", 1)[1].strip().split()[0] if line.split() else ""
            elif line.startswith(("#", "@", "$", ">>")):
                continue
            else:
                text = line.strip()
                if text and not text.startswith("..."):
                    rec["lines"].append(text)
    if rec is not None:
        yield rec


class CDLI:
    """The Cuneiform Digital Library Initiative's ATF dump, grouped into language volumes.

    ATF is one record a tablet (135,254 of them: 93k Sumerian, 20k Akkadian, 7.8k proto-cuneiform).
    A model should not see 135k one-line files, so records are grouped by language into volumes of
    at most `max_chars` characters. Each volume is a book; the tablet headers stay in the text.
    """

    key, prefix, name, unsigned = "cdli", "cdli-", "CDLI (cuneiform)", True
    MAX_CHARS = 2_000_000

    def books(
        self,
        *,
        limit: int | None = None,
        offset: int = 0,
        language: str = "",
        max_chars: int | None = None,
        **_,
    ):
        path = _atf_path()
        cap = max_chars or self.MAX_CHARS
        want = language.strip().lower()
        volumes: dict[str, list[str]] = {}
        sizes: dict[str, int] = {}
        numbers: dict[str, int] = {}
        seen = skipped = 0
        for rec in _records(path):
            lang = (rec["lang"] or "und").lower()
            if want and lang != want:
                continue
            if not rec["lines"]:
                continue
            body = f"&{rec['id']} = {rec['title']}\n" + "\n".join(rec["lines"])
            if len(body) < 80:
                continue
            if lang not in volumes:
                volumes[lang], sizes[lang], numbers[lang] = [], 0, 0
            if sizes[lang] + len(body) > cap and volumes[lang]:
                n = numbers[lang]
                numbers[lang] += 1
                if skipped < offset:
                    skipped += 1
                else:
                    yield BulkBook(
                        ident=safe_id(f"{lang}-{n:03d}"),
                        title=f"CDLI {lang} transliterations, volume {n + 1}",
                        authors="",
                        language=lang,
                        published=None,
                        origin="https://cdli.mpiwg-berlin.mpg.de/",
                        text="\n\n".join(volumes[lang]),
                        extra={"tablets": len(volumes[lang]), "language": lang},
                    )
                    seen += 1
                    if limit is not None and seen >= limit:
                        return
                volumes[lang], sizes[lang] = [], 0
            volumes[lang].append(body)
            sizes[lang] += len(body) + 2
        for lang, parts in volumes.items():
            if not parts:
                continue
            n = numbers.get(lang, 0)
            if skipped < offset:
                skipped += 1
                continue
            yield BulkBook(
                ident=safe_id(f"{lang}-{n:03d}"),
                title=f"CDLI {lang} transliterations, volume {n + 1}",
                authors="",
                language=lang,
                published=None,
                origin="https://cdli.mpiwg-berlin.mpg.de/",
                text="\n\n".join(parts),
                extra={"tablets": len(parts), "language": lang},
            )
            seen += 1
            if limit is not None and seen >= limit:
                return


register_bulk(ETCSL())
register_bulk(CDLI())

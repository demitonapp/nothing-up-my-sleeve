"""The classics: Perseus's Greek and Latin TEI, as discovery corpora.

The Perseus Digital Library's canonical repositories (`PerseusDL/canonical-latinLit` and
`canonical-greekLit`, CC BY-SA 4.0) hold the editions behind Perseus: TEI XML with the title, the
ancient author, the editor and the imprint, and the text itself. A **classics** set is not an English
recipe: these are Greek and Latin, the editions are modern (the imprint dates are 19th and 20th
century), and the author's death is not the edition's. The gate's period rules are therefore not
applied to this discovery set; the deck, duplicate and provenance rules are.

The first gather downloads the repository archive (about 48 MB Latin, 75 MB Greek) into
`data/classics/` and unzips it. A second gather reads the files already there.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from thorp import paths
from thorp.sources.bulk import BulkBook, register_bulk, safe_id

TEI = "{http://www.tei-c.org/ns/1.0}"
BLOCKS = {
    TEI + "l",
    TEI + "p",
    TEI + "head",
    TEI + "ab",
    TEI + "div",
    TEI + "lg",
    TEI + "milestone",
    TEI + "pb",
    TEI + "gap",
}
GITHUB = "https://github.com/{repo}/archive/refs/heads/master.zip"


def _ensure(repo: str, directory: str) -> Path:
    """The repository's data directory, downloaded and unzipped on the first gather."""
    root = paths.data_dir() / "classics" / directory
    if root.exists() and any(root.rglob("*.xml")):
        return root
    import requests

    from thorp.sources.gutenberg import USER_AGENT

    base = paths.data_dir() / "classics"
    base.mkdir(parents=True, exist_ok=True)
    archive = base / f"{directory}.zip"
    if not archive.exists():
        with requests.get(
            GITHUB.format(repo=repo), headers={"User-Agent": USER_AGENT}, stream=True, timeout=600
        ) as r:
            r.raise_for_status()
            with archive.open("wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    with zipfile.ZipFile(archive) as z:
        z.extractall(base)
    return root


def _body_text(body: ET.Element) -> str:
    out: list[str] = []
    for el in body.iter():
        if el.tag in BLOCKS:
            out.append("\n")
        if el.text:
            out.append(el.text)
        if el.tail:
            out.append(el.tail)
    text = re.sub(r"[ \t]+", " ", "".join(out))
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def _meta(root: ET.Element) -> tuple[str, str, str, int | None]:
    header = root.find(f".//{TEI}teiHeader")
    title = author = editor = ""
    year = None
    if header is not None:
        ts = header.find(f".//{TEI}titleStmt")
        if ts is not None:
            title = (ts.findtext(f"{TEI}title") or "").strip()
            author = (ts.findtext(f"{TEI}author") or "").strip()
            editor = (ts.findtext(f"{TEI}editor") or "").strip()
        for d in header.findall(f".//{TEI}imprint/{TEI}date"):
            m = re.search(r"(?<!\d)(1[0-9]{3}|20[0-9]{2})(?!\d)", d.text or "")
            if m:
                year = int(m.group(1))
                break
    return title, author, editor, year


class Perseus:
    """One Perseus repository of TEI editions, in one language."""

    repo = ""
    directory = ""
    marker = ""  # "lat" or "grc": the file-name marker of this language's editions
    language = ""  # "la" or "grc"
    unsigned = False

    def books(self, *, limit: int | None = None, offset: int = 0, **_):
        root = _ensure(self.repo, self.directory)
        seen = skipped = 0
        for p in sorted(root.rglob("*.xml")):
            if p.name == "__cts__.xml" or self.marker not in p.name:
                continue
            try:
                root_el = ET.parse(p).getroot()
            except ET.ParseError:
                continue
            body = root_el.find(f".//{TEI}text/{TEI}body") or root_el.find(f".//{TEI}body")
            if body is None:
                continue
            text = _body_text(body)
            if len(text) < 500:
                continue
            if skipped < offset:
                skipped += 1
                continue
            title, author, editor, year = _meta(root_el)
            yield BulkBook(
                ident=safe_id(p.stem),
                title=title or p.stem,
                authors=author or "Anonymous",
                language=self.language,
                published=year,
                origin=f"https://github.com/{self.repo}/blob/master/{p.relative_to(root)}",
                text=text,
                extra={"editor": editor},
            )
            seen += 1
            if limit is not None and seen >= limit:
                return


class PerseusLatin(Perseus):
    key, prefix, name = "perseus-latin", "lat-", "Perseus Latin"
    repo = "PerseusDL/canonical-latinLit"
    directory = "canonical-latinLit-master"
    marker = "lat"
    language = "la"


class PerseusGreek(Perseus):
    key, prefix, name = "perseus-greek", "grc-", "Perseus Greek"
    repo = "PerseusDL/canonical-greekLit"
    directory = "canonical-greekLit-master"
    marker = "grc"
    language = "grc"


for _src in (PerseusLatin(), PerseusGreek()):
    register_bulk(_src)
del _src

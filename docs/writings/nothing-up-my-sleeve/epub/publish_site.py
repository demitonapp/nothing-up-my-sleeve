"""Put the latest epub where the site can serve it (13 November 2026, Justin: the site's first cards offer the
latest epub to download, send to a Kindle or read).

Usage, from anywhere:  python3 docs/writings/nothing-up-my-sleeve/epub/publish_site.py

It finds the highest `Nothing Up My Sleeve (vN).epub` beside this script and writes three things:
  frontend/public/book/nothing-up-my-sleeve.epub   the file itself, at one fixed address, so the link never changes
  frontend/public/book/cover.jpg                   the cover the card shows
  frontend/src/data/book.json                      what the pages say about it: version, size, date, download name

The site reads the epub itself in the browser (frontend/src/lib/epub.ts), so nothing is unpacked here and the
copy a visitor reads is the copy a visitor downloads. Run it after every build of a new version.
"""
import datetime, json, pathlib, re, shutil, zipfile

HERE = pathlib.Path(__file__).resolve().parent
BOOK = HERE.parent
REPO = BOOK.parents[2]
PUBLIC = REPO / "frontend/public/book"
DATA = REPO / "frontend/src/data/book.json"

versions = sorted(
    ((int(m.group(1)), p) for p in HERE.glob("Nothing Up My Sleeve (v*).epub")
     if (m := re.search(r"\(v(\d+)\)\.epub$", p.name))),
    key=lambda t: t[0])
if not versions:
    raise SystemExit("no `Nothing Up My Sleeve (vN).epub` beside this script; build one first (README.md)")
n, epub = versions[-1]

front = (BOOK / "book.md").read_text().split("\n\n")
standfirst = next((p.strip().strip("*") for p in front if p.strip().startswith("*")), "")
with zipfile.ZipFile(epub) as z:
    nav = z.read("OEBPS/nav.xhtml").decode("utf-8")
chapters = [c for c in re.findall(r'<a href="(c\d+\.xhtml)">', nav)]

PUBLIC.mkdir(parents=True, exist_ok=True)
shutil.copyfile(epub, PUBLIC / "nothing-up-my-sleeve.epub")
shutil.copyfile(HERE / "cover.jpg", PUBLIC / "cover.jpg")
DATA.write_text(json.dumps({
    "title": "Nothing Up My Sleeve",
    "byline": "Fable, author · Justin Trollip, Head of Metaphors · Demiton, 2026",
    "standfirst": standfirst,
    "version": f"v{n}",
    "file": "/book/nothing-up-my-sleeve.epub",
    "cover": "/book/cover.jpg",
    "downloadName": epub.name,
    "bytes": epub.stat().st_size,
    "chapters": len(chapters),
    "published": datetime.date.today().isoformat(),
}, indent=2, ensure_ascii=False) + "\n")
print(f"published {epub.name} ({epub.stat().st_size / 1e6:.1f} MB, {len(chapters)} pages) to {PUBLIC.relative_to(REPO)}")

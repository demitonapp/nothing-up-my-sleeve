"""Build an EPUB from markdown files, with a cover, footnotes, pictures and diagrams.
Usage: build_epub.py out.epub "Title" "Author" cover.jpg file1.md [file2.md ...]
Each file is one chapter, titled by its first `# ` line; its later headings are demoted a level and its
`##` sections appear nested under it in the contents. The cover (D16) is the first page and the gallery image.
Footnotes (D46): a marker `[^id]` in the chapter text, and its body in the sidecar beside the chapter
(`<file>.notes.md`) as a line `[^id]: ...`, continued on lines indented two spaces, blank lines allowed
between them. The marker becomes a numbered EPUB 3 note reference and the body an aside the Kindle shows as
a pop-up footnote. A marker with no body, or a body with no marker, fails the build.
Pictures: a link `[text](peek:id)` keeps its text in the sentence and puts `pictures/<id>.png` (the book's own
folder) as a figure after the paragraph, captioned with the text. Diagrams: a ```mermaid block is rendered to
PNG once, by render_mermaid.mjs beside this script (Playwright's Chromium and the Atlas reader's mermaid, run
from packages/ui/apps/app), cached by content hash under the system temp dir, and placed as a figure."""
import sys, re, zipfile, uuid, html, datetime, pathlib, hashlib, json, subprocess, tempfile
import markdown

out, title, author, cover, *files = sys.argv[1:]
HERE = pathlib.Path(__file__).resolve().parent
BOOK = next((pathlib.Path(f).resolve().parent for f in files if pathlib.Path(f).name == "book.md"), HERE.parent)
# The mermaid renderer lives in the monorepo (packages/ui/apps/app). The book's canonical copy is in Thorp,
# so look there last: $NUMS_MONOREPO, then the repo the book sits in, then a `monorepo` checkout beside it.
import os
REPO = next((r for r in (pathlib.Path(os.environ["NUMS_MONOREPO"]) if os.environ.get("NUMS_MONOREPO") else None,
                         BOOK.parents[2], BOOK.parents[2].parent / "monorepo")
             if r is not None and (r / "packages/ui/apps/app").is_dir()), BOOK.parents[2])
md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists", "toc"])
fn_md = markdown.Markdown(extensions=["tables", "sane_lists"])
MARKER = re.compile(r"\[\^([A-Za-z0-9-]+)\]")
PEEK = re.compile(r"\[([^\]]+)\]\(peek:([a-z0-9-]+)\)")
MERMAID = re.compile(r"^```mermaid\n(.*?)^```\s*$", re.M | re.S)
CACHE = pathlib.Path(tempfile.gettempdir()) / "nums-epub-diagrams"
CACHE.mkdir(parents=True, exist_ok=True)
images: dict[str, pathlib.Path] = {}  # zip name under OEBPS/images -> source file

def footnote_bodies(path: pathlib.Path) -> dict[str, str]:
    """The `[^id]: body` definitions in the chapter's sidecar, by id."""
    side = path.with_suffix(".notes.md")
    if not side.exists():
        return {}
    bodies: dict[str, list[str]] = {}
    cur = None
    for line in side.read_text(encoding="utf-8").split("\n"):
        m = re.match(r"^\[\^([A-Za-z0-9-]+)\]:\s?(.*)$", line)
        if m:
            cur = m.group(1)
            bodies[cur] = [m.group(2)]
        elif cur is not None and line.startswith("  "):
            bodies[cur].append(line[2:])
        elif cur is not None and line.strip() == "":
            bodies[cur].append("")
        else:
            cur = None
    return {k: "\n".join(v).strip() for k, v in bodies.items()}

def shrink(src: pathlib.Path, max_width: int = 1200) -> pathlib.Path:
    """A picture as a JPEG no wider than the Kindle's screen, cached by the source's size and mtime."""
    from PIL import Image
    st = src.stat()
    dst = CACHE / f"{src.stem}-{st.st_size}-{int(st.st_mtime)}.jpg"
    if not dst.exists():
        with Image.open(src) as im:
            im = im.convert("RGB")
            if im.width > max_width:
                im = im.resize((max_width, round(im.height * max_width / im.width)), Image.LANCZOS)
            im.save(dst, "JPEG", quality=82, optimize=True)
    return dst

def render_diagrams(blocks: dict[str, str]) -> None:
    """Render every uncached mermaid block (by hash) to CACHE/<hash>.png in one browser session."""
    jobs = []
    for h, src in blocks.items():
        png = CACHE / f"{h}.png"
        if png.exists():
            continue
        mmd = CACHE / f"{h}.mmd"
        mmd.write_text(src, encoding="utf-8")
        jobs.append({"src": str(mmd), "out": str(png)})
    if not jobs:
        return
    jobs_file = CACHE / "jobs.json"
    jobs_file.write_text(json.dumps(jobs))
    mermaid_js = REPO / "node_modules/.pnpm/mermaid@11.12.3/node_modules/mermaid/dist/mermaid.min.js"
    if not mermaid_js.exists():
        found = sorted((REPO / "node_modules/.pnpm").glob("mermaid@*/node_modules/mermaid/dist/mermaid.min.js"))
        if not found:
            sys.exit("mermaid.min.js not found under node_modules/.pnpm; run pnpm install")
        mermaid_js = found[-1]
    r = subprocess.run(["node", str(HERE / "render_mermaid.mjs"), str(mermaid_js), str(jobs_file)],
                       cwd=REPO / "packages/ui/apps/app", capture_output=True, text=True)
    sys.stderr.write(r.stderr)
    print(r.stdout.strip())
    if r.returncode != 0:
        sys.exit(f"diagram rendering failed ({r.returncode})")

# Pass one: collect every diagram so they render in one browser session.
sources: list[tuple[pathlib.Path, str]] = []
blocks: dict[str, str] = {}
for f in files:
    path = pathlib.Path(f)
    text = path.read_text(encoding="utf-8").replace("\r", "")
    for m in MERMAID.finditer(text):
        blocks[hashlib.sha1(m.group(1).encode()).hexdigest()[:12]] = m.group(1)
    sources.append((path, text))
render_diagrams(blocks)

chapters = []  # (id, title, html, [(anchor, heading), ...])
for path, text in sources:
    # One file is one chapter. Its first `# ` line is the chapter title; every later heading is
    # demoted one level so the file's own sections become `##`, which the nested contents list.
    lines = text.split("\n")
    first = next((i for i, l in enumerate(lines) if re.match(r"^# ", l)), None)
    title_line = lines[first].lstrip("# ").strip() if first is not None else "Untitled"
    body = []
    for i, l in enumerate(lines):
        if i == first:
            continue
        m = re.match(r"^(#{1,5}) (.*)", l)
        body.append(("#" + m.group(1) + " " + m.group(2)) if m and first is not None and i > first else l)
    source = "\n".join(body)
    # Diagrams: each mermaid block becomes a figure holding its rendered PNG.
    def diagram(m: re.Match) -> str:
        h = hashlib.sha1(m.group(1).encode()).hexdigest()[:12]
        png = CACHE / f"{h}.png"
        if not png.exists():
            return f"<pre>{html.escape(m.group(1))}</pre>"  # the render failed; the source stays readable
        images[f"d-{h}.png"] = png
        return f'\n<figure class="diagram"><img src="images/d-{h}.png" alt="diagram"/></figure>\n'
    source = MERMAID.sub(diagram, source)
    # Pictures: the link text stays in the sentence; the picture follows its paragraph as a captioned figure.
    paras = source.split("\n\n")
    for pi, para in enumerate(paras):
        figs = ""
        for m in PEEK.finditer(para):
            caption, pid = m.group(1), m.group(2)
            src = next((c for c in (path.parent.parent / "pictures", BOOK / "pictures") if (c / f"{pid}.png").exists()), None)
            if src is None:
                sys.stderr.write(f"{path}: picture peek:{pid} not found under pictures/\n")
                continue
            images[f"{pid}.jpg"] = shrink(src / f"{pid}.png")
            figs += f'\n<figure class="picture"><img src="images/{pid}.jpg" alt="{html.escape(caption)}"/><figcaption>{html.escape(caption)}</figcaption></figure>\n'
        if figs:
            paras[pi] = PEEK.sub(lambda m: m.group(1), para) + "\n" + figs
    source = "\n\n".join(paras)
    # Footnotes: number the markers in order of appearance, link each to an aside at the chapter's foot.
    bodies = footnote_bodies(path)
    order: list[str] = []
    for fid in MARKER.findall(source):
        if fid not in order:
            order.append(fid)
    missing = [fid for fid in order if fid not in bodies]
    unused = [fid for fid in bodies if fid not in order]
    if missing or unused:
        sys.exit(f"{path}: footnote markers without a body {missing}; bodies without a marker {unused}")
    def ref(m: re.Match) -> str:
        n = order.index(m.group(1)) + 1
        return f'<sup class="noteref"><a epub:type="noteref" href="#fn-{m.group(1)}">{n}</a></sup>'
    source = MARKER.sub(ref, source)
    md.reset()
    html_body = md.convert(source)
    subs = [(t["id"], t["name"]) for t in md.toc_tokens if t["level"] == 2]
    asides = ""
    for n, fid in enumerate(order, 1):
        fn_md.reset()
        inner = fn_md.convert(bodies[fid])
        inner = inner.replace("<p>", f'<p><span class="fnnum">{n}.</span> ', 1) if "<p>" in inner else f"<p>{n}. {inner}</p>"
        asides += f'<aside epub:type="footnote" id="fn-{fid}" class="footnote">{inner}</aside>'
    if asides:
        html_body += '<section epub:type="footnotes" class="footnotes">' + asides + "</section>"
    chapters.append((f"c{len(chapters)+1}", title_line, f"<h1>{html.escape(title_line)}</h1>" + html_body, subs))

css = """body{font-family:serif;line-height:1.45}h1{font-size:1.5em}h2{font-size:1.25em;margin-top:1.4em}
table{border-collapse:collapse;font-size:0.85em}td,th{border:1px solid #888;padding:3px 6px;vertical-align:top}
pre{white-space:pre-wrap;font-size:0.8em}blockquote{margin:0.6em 1em;font-style:italic}code{font-size:0.9em}
.cover{text-align:center;margin:0;padding:0}.cover img{max-width:100%;max-height:100%}
ol.toc{list-style:none;padding-left:0}ol.toc ol{list-style:none;padding-left:1.2em;font-size:0.9em}ol.toc li{margin:0.35em 0}
sup.noteref{font-size:0.7em;line-height:0}sup.noteref a{text-decoration:none}
section.footnotes{margin-top:2em;border-top:1px solid #888;padding-top:0.6em;font-size:0.9em}
aside.footnote{margin:0.6em 0}aside.footnote p{margin:0.3em 0}span.fnnum{font-weight:bold}
figure{margin:1em 0;text-align:center;page-break-inside:avoid}figure img{max-width:100%;height:auto}
figcaption{font-size:0.85em;font-style:italic;margin-top:0.3em}"""

def page(ctitle, body):
    return f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><meta charset="utf-8"/>
<title>{html.escape(ctitle)}</title><link rel="stylesheet" type="text/css" href="style.css"/></head><body>{body}</body></html>"""

uid = str(uuid.uuid4())
manifest = "".join(f'<item id="{cid}" href="{cid}.xhtml" media-type="application/xhtml+xml"/>' for cid, _, _, _ in chapters)
manifest += "".join(f'<item id="img{i}" href="images/{name}" media-type="image/{"jpeg" if name.endswith(".jpg") else "png"}"/>' for i, name in enumerate(images))
spine = "".join(f'<itemref idref="{cid}"/>' for cid, _, _, _ in chapters)
opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="uid">
<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
<dc:identifier id="uid">urn:uuid:{uid}</dc:identifier><dc:title>{html.escape(title)}</dc:title>
<dc:creator>{html.escape(author)}</dc:creator><dc:language>en</dc:language>
<meta name="cover" content="cover-image"/>
<meta property="dcterms:modified">{datetime.datetime.now(datetime.timezone.utc):%Y-%m-%dT%H:%M:%SZ}</meta></metadata>
<manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>
<item id="cover-image" href="cover.jpg" media-type="image/jpeg" properties="cover-image"/>
<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>
<item id="contents" href="contents.xhtml" media-type="application/xhtml+xml"/>
<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
<item id="css" href="style.css" media-type="text/css"/>{manifest}</manifest>
<spine toc="ncx"><itemref idref="cover" linear="yes"/><itemref idref="contents" linear="yes"/>{spine}</spine>
<guide><reference type="cover" title="Cover" href="cover.xhtml"/><reference type="toc" title="Contents" href="contents.xhtml"/><reference type="text" title="Start" href="c1.xhtml"/></guide></package>"""
def nav_item(cid, t, subs):
    inner = "".join(f'<li><a href="{cid}.xhtml#{a}">{html.escape(h)}</a></li>' for a, h in subs)
    return f'<li><a href="{cid}.xhtml">{html.escape(t)}</a>' + (f"<ol>{inner}</ol>" if inner else "") + "</li>"
nav_items = "".join(nav_item(cid, t, subs) for cid, t, _, subs in chapters)
nav = f"""<?xml version="1.0" encoding="utf-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops"><head><meta charset="utf-8"/><title>Contents</title></head>
<body><nav epub:type="toc"><h1>Contents</h1><ol><li><a href="cover.xhtml">Cover</a></li>{nav_items}</ol></nav></body></html>"""

contents_body = "<h1>Contents</h1><ol class=\"toc\">" + nav_items + "</ol>"
def ncx_points():
    out_, n = [], 0
    for cid, t, _, subs in chapters:
        n += 1
        inner = ""
        for a, h in subs:
            n += 1
            inner += f'<navPoint id="np{n}" playOrder="{n}"><navLabel><text>{html.escape(h)}</text></navLabel><content src="{cid}.xhtml#{a}"/></navPoint>'
        out_.append(f'<navPoint id="np{n}" playOrder="{n}"><navLabel><text>{html.escape(t)}</text></navLabel><content src="{cid}.xhtml"/>{inner}</navPoint>')
    return "".join(out_)
ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1"><head><meta name="dtb:uid" content="urn:uuid:{uid}"/><meta name="dtb:depth" content="2"/></head>
<docTitle><text>{html.escape(title)}</text></docTitle><navMap>{ncx_points()}</navMap></ncx>"""

with zipfile.ZipFile(out, "w") as z:
    z.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip", compress_type=zipfile.ZIP_STORED)
    z.writestr("META-INF/container.xml", """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles>
<rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>""", compress_type=zipfile.ZIP_DEFLATED)
    z.writestr("OEBPS/content.opf", opf, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr("OEBPS/nav.xhtml", nav, compress_type=zipfile.ZIP_DEFLATED)
    z.writestr("OEBPS/style.css", css, compress_type=zipfile.ZIP_DEFLATED)
    z.write(cover, "OEBPS/cover.jpg", compress_type=zipfile.ZIP_STORED)
    for name, src in images.items():
        z.write(src, f"OEBPS/images/{name}", compress_type=zipfile.ZIP_STORED)
    z.writestr("OEBPS/cover.xhtml", page("Cover", '<div class="cover"><img src="cover.jpg" alt="Cover"/></div>'), compress_type=zipfile.ZIP_DEFLATED)
    z.writestr("OEBPS/contents.xhtml", page("Contents", contents_body), compress_type=zipfile.ZIP_DEFLATED)
    z.writestr("OEBPS/toc.ncx", ncx, compress_type=zipfile.ZIP_DEFLATED)
    for cid, t, body, _ in chapters:
        z.writestr(f"OEBPS/{cid}.xhtml", page(t, body), compress_type=zipfile.ZIP_DEFLATED)
print(f"{out}: {len(chapters)} chapters, {len(images)} images, cover {cover}")

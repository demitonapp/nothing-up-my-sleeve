"""The book's files in reading order, for build_epub.py: the front page, then each part, opened by its own
page (the `00-*.md` poem page, D40, with the part's numeral put before its title; or a divider page from the
front-page table where a part has no such page yet) and followed by its chapters, then the apparatus a new
reader meets last (the plan, the decisions, the Kindle notes).
Usage: build_list.py <book dir> <scratch dir>   -> prints the file list, one per line."""
import sys, re, pathlib
B = pathlib.Path(sys.argv[1]); P = pathlib.Path(sys.argv[2]); P.mkdir(parents=True, exist_ok=True)
front = (B / "book.md").read_text()
parts = re.findall(r"^\| ([IVX]+) \| (\d{2}-[a-z0-9-]+) \| ([^|]+?) \| ([^|]*?) \|\s*$", front, re.M)
files = [str(B / "book.md")]
for num, folder, title, blurb in parts:
    chapters = [f for f in sorted((B / folder).glob("[0-9]*.md")) if not f.name.endswith(".notes.md")]
    opener = next((f for f in chapters if f.name.startswith("00-")), None)
    div = P / f"{folder}.md"
    if opener is not None:
        # The part's own opening page is its divider: the same text, titled "Part I · <its title>".
        div.write_text(re.sub(r"^# (.+)$", lambda m: f"# Part {num} · {m.group(1)}", opener.read_text(), count=1, flags=re.M))
        side = opener.with_suffix(".notes.md")
        if side.exists():
            div.with_suffix(".notes.md").write_text(side.read_text())  # its footnote bodies travel with it
        chapters.remove(opener)
    else:
        div.write_text(f"# Part {num} · {title.strip()}\n\n{blurb.strip()}\n")
    files.append(str(div))
    files += [str(f) for f in chapters]
files += [str(B / "plan.md"), str(B / "decisions.md")] + sorted(str(p) for p in B.glob("kindle-notes-*.md"))
print("\n".join(files))

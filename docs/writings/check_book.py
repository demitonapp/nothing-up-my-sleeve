#!/usr/bin/env python3
"""The sidecar contract for docs/writings (see docs/writings/README.md).

Every chapter file NN[a-z]?-slug.md in a part folder has a sidecar NN-slug.notes.md; every sidecar anchor
(`## @x`) is `@chapter` or names a `## ` heading of the chapter; a chapter carries no `## Sources` section;
every `peek:` id a chapter uses is listed in its sidecar; book.md lists every part folder. Exit 1 on any
failure, with each one named.
"""
import re, sys, pathlib

BOOKS = [pathlib.Path("docs/writings/nothing-up-my-sleeve")]
CHAPTER = re.compile(r"^(\d{2})([a-z]?)-([a-z0-9-]+)\.md$")

def anchor(h: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", h.lower())).strip("-")

def check(book: pathlib.Path) -> list[str]:
    errors: list[str] = []
    front = book / "book.md"
    listed = set(re.findall(r"^\| [IVX]+ \| (\d{2}-[a-z0-9-]+) \|", front.read_text(), re.M)) if front.exists() else set()
    if not front.exists():
        errors.append(f"{book}: no book.md")
    for part in sorted(p for p in book.iterdir() if p.is_dir() and re.match(r"^\d{2}-", p.name)):
        if part.name not in listed:
            errors.append(f"{front}: part folder {part.name} is not in the parts table")
        for f in sorted(part.iterdir()):
            m = CHAPTER.match(f.name)
            if not m or f.name.endswith(".notes.md"):
                if f.suffix == ".md" and not f.name.endswith(".notes.md"):
                    errors.append(f"{f}: not a chapter file name (NN-slug.md)")
                continue
            text = f.read_text()
            if not re.search(r"^# .+", text, re.M):
                errors.append(f"{f}: no `# Title` line")
            if re.search(r"^## Sources\s*$", text, re.M):
                errors.append(f"{f}: carries a Sources section; it belongs in the sidecar's References")
            side = f.with_suffix(".notes.md")
            if not side.exists():
                errors.append(f"{f}: no sidecar {side.name}")
                continue
            headings = {anchor(h) for h in re.findall(r"^## (.+)$", text, re.M)}
            stext = side.read_text()
            for a in re.findall(r"^## @([a-z0-9-]+)\s*$", stext, re.M):
                if a != "chapter" and a not in headings:
                    errors.append(f"{side}: anchor @{a} names no heading of {f.name}")
            for bad in re.findall(r"^## (?!@)(.+)$", stext, re.M):
                errors.append(f"{side}: section `## {bad}` is not an anchor (`## @...`)")
            for block in re.findall(r"^### (.+)$", stext, re.M):
                if block not in ("Quentin", "Pictures", "References"):
                    errors.append(f"{side}: block `### {block}` is not Quentin, Pictures or References")
            used = set(re.findall(r"\(peek:([a-z0-9-]+)\)", text))
            listed_peeks = set(re.findall(r"`peek:([a-z0-9-]+)`", stext))
            for pid in sorted(used - listed_peeks):
                errors.append(f"{side}: peek:{pid} is used by the chapter and not listed under Pictures")
            # Footnotes (D46): every `[^id]` marker in the chapter has a `[^id]: body` in the sidecar, and no body is orphaned.
            markers = set(re.findall(r"\[\^([A-Za-z0-9-]+)\]", text))
            bodies = set(re.findall(r"^\[\^([A-Za-z0-9-]+)\]:", stext, re.M))
            for fid in sorted(markers - bodies):
                errors.append(f"{side}: footnote [^{fid}] is marked in {f.name} and has no body here")
            for fid in sorted(bodies - markers):
                errors.append(f"{side}: footnote [^{fid}] has a body here and no marker in {f.name}")
    return errors

if __name__ == "__main__":
    errs = [e for b in BOOKS for e in check(b)]
    for e in errs:
        print(e)
    print(f"check_book: {len(errs)} problem(s)")
    sys.exit(1 if errs else 0)

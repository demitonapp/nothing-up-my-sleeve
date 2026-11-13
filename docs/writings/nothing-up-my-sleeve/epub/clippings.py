"""Read the Kindle's My Clippings.txt (over USB: /Volumes/Kindle/documents/My Clippings.txt).
Usage: clippings.py <clippings.txt> titles            -> every document with its clipping count
       clippings.py <clippings.txt> "<document title>" -> its highlights and notes, deduplicated by location
(the Kindle writes a clipping per keystroke of a note, so each location keeps the latest note and the longest
highlight). Both header forms are read: "on page N | Location N" and the newer "on Location N"."""
import re, sys, collections
raw = open(sys.argv[1], encoding="utf-8-sig").read()
entries = []
for block in raw.split("=========="):
    lines = [l.strip("﻿\r ") for l in block.strip("\r\n").split("\n")]
    if len(lines) < 2: continue
    title = lines[0].strip()
    m = re.match(r"- Your (Highlight|Note|Bookmark)(?: on page (\d+))?(?: \||\s+on) [Ll]ocation (\d+)(?:-(\d+))? \| Added on (.*)", lines[1])
    if not m: continue
    kind, page, loc, loc2, when = m.groups()
    text = "\n".join(lines[3:]).strip()
    entries.append(dict(title=title, kind=kind, page=page, loc=int(loc), loc2=int(loc2) if loc2 else None, when=when, text=text))
titles = collections.Counter(e["title"] for e in entries)
mode = sys.argv[2] if len(sys.argv) > 2 else "titles"
if mode == "titles":
    for t, n in titles.most_common():
        last = max(e["when"] for e in entries if e["title"] == t)
        print(f"{n:5d}  {t}  | last {last}")
else:
    want = [e for e in entries if e["title"] == mode]
    # dedupe: notes keep the latest text per location; highlights keep the longest per location
    notes, highs = {}, {}
    for e in want:
        if e["kind"] == "Note": notes[e["loc"]] = e
        elif e["kind"] == "Highlight":
            if e["loc"] not in highs or len(e["text"]) > len(highs[e["loc"]]["text"]): highs[e["loc"]] = e
    print(f"{len(want)} raw -> {len(highs)} highlights, {len(notes)} notes")
    for loc in sorted(set(notes) | set(highs)):
        h = highs.get(loc); n = notes.get(loc)
        print(f"\n--- loc {loc}" + (f" (page {h['page']})" if h and h['page'] else ""))
        if h: print("HIGHLIGHT: " + h["text"][:400])
        if n: print("NOTE: " + n["text"])

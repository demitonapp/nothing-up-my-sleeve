"""Read the Kindle's My Clippings.txt (over USB: /Volumes/Kindle/documents/My Clippings.txt).
Usage: clippings.py <clippings.txt> titles            -> every document with its clipping count
       clippings.py <clippings.txt> "<document title>" -> its highlights and notes, one entry per note
(the Kindle writes a clipping per keystroke of a note, so a run of clippings at one location that each extend
the one before is one note, and its last clipping is the note; a second note typed at the same location starts
a new run and is kept. Until 13 November 2026 this kept one note per location, and four notes on v13 were
lost that way. A location keeps its longest highlight). Both header forms are read: "on page N | Location N"
and the newer "on Location N"."""
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
    def extends(prev, text):
        """True when `text` is the next keystroke of the note `prev`: same start, and not much shorter."""
        if len(text) < len(prev) - 3: return False
        k = max(1, min(len(prev), len(text)) - 3)
        return text.startswith(prev[:k])
    notes, highs, last = {}, {}, None   # notes: location -> the notes typed there, in order
    for e in want:                      # the file is in the order the clippings were written
        if e["kind"] == "Note":
            if last and last["loc"] == e["loc"] and extends(last["text"], e["text"]): notes[e["loc"]][-1] = e
            else: notes.setdefault(e["loc"], []).append(e)
            last = e
        elif e["kind"] == "Highlight":
            if e["loc"] not in highs or len(e["text"]) > len(highs[e["loc"]]["text"]): highs[e["loc"]] = e
    print(f"{len(want)} raw -> {len(highs)} highlights, {sum(len(v) for v in notes.values())} notes")
    for loc in sorted(set(notes) | set(highs)):
        h = highs.get(loc)
        print(f"\n--- loc {loc}" + (f" (page {h['page']})" if h and h['page'] else ""))
        if h: print("HIGHLIGHT: " + h["text"][:400])
        for n in notes.get(loc, []): print(f"NOTE ({n['when'][-8:]}): " + n["text"])

# EPUBs of the writings

Built copies of the essays and plans for the Kindle, one file per version, so the copy on the device can be
matched to the commit it was built from. Every build carries the cover (D16: the card-table art from
`scripts/generate-government-art.py cover:nothing-up-my-sleeve`, saved here as `cover-art.png` and composed in
grayscale by `make_cover.py`; Fable as author, Justin Trollip as Head of Metaphors). Name the file as the book, since the Kindle titles a document
from its filename.

```bash
B=docs/writings/nothing-up-my-sleeve
uv run --python 3.12 --with pillow python $B/epub/make_cover.py $B/epub/cover.jpg "Nothing Up My Sleeve" "<subtitle>"
uv run --python 3.12 --with markdown --with pillow python $B/epub/build_epub.py "$B/epub/Nothing Up My Sleeve (v<N>).epub" "Nothing Up My Sleeve (v<N>)" "Fable" $B/epub/cover.jpg $(uv run --python 3.12 python $B/epub/build_list.py $B /tmp/parts | tr '\n' ' ')
```

`publish_site.py` puts the newest epub on the site (13 November): it copies the highest `(vN)` file to
`frontend/public/book/nothing-up-my-sleeve.epub` and the cover beside it, and writes `frontend/src/data/book.json`,
which the home page's book card, `/book` and the reader at `/book/read` read. Run it after every build:
`python3 docs/writings/nothing-up-my-sleeve/epub/publish_site.py`.

`clippings.py` reads the notes back off the Kindle: `uv run --python 3.12 python $B/epub/clippings.py "/Volumes/Kindle/documents/My Clippings.txt" titles` lists the documents, and the same with a document's title in place of `titles` prints its highlights and notes deduplicated by location. It reads both header forms the Kindle has used (`on page N | Location N` and `on Location N`); the second form is what the v12 notes were missed under.

`build_list.py` gives the reading order: the front page (the title, the byline and the standfirst of
`book.md`, D51), each part opened by its poem page (with the numeral put before its title, and its sidecar
copied beside it so its footnotes travel), then its chapters, then what a reader meets last: About this book
(`about.md`, with the parts and blurbs added from `book.md`'s table), the Beats (`the-beats.md`), Plan,
Decisions and the Kindle notes.

The builder also does three things the Kindle needs (since v12): **footnotes** (D46), a `[^id]` marker in the
chapter and its body in the sidecar, become EPUB 3 note references and asides, which the Kindle shows as
pop-ups; **pictures**, a `[text](peek:id)` link, keep their text in the sentence and follow the paragraph as
a captioned figure, resized to a 1200-pixel JPEG; and **diagrams**, every ```mermaid block, are rendered to
PNG by `render_mermaid.mjs`, which runs the Atlas reader's mermaid in Playwright's Chromium from
`packages/ui/apps/app` (it tries each Playwright in the pnpm store until one has its browser), cached by
content hash under the system temp directory. That app is in the monorepo and the book's canonical copy is
in Thorp, so the builder looks for it in `$NUMS_MONOREPO`, then the repository the book sits in, then a
`monorepo` checkout beside that repository; built from Thorp with the monorepo at `~/Source/monorepo`, it
finds it without being told.

Each input file is one chapter, titled by its first `# ` line, with its sections nested in the contents. Send from jtrollip@gmail.com (the address Amazon accepts)
to the Kindle address, bump the version in the filename and the title on every send, and add a row below.

| File | Built from | Sent | Contents |
| --- | --- | --- | --- |
| `nothing-up-my-sleeve-plan-v1.epub` | `eb8656e444` | 2026-11-05 | the plan (D1 to D11) + the Kindle notes; no cover |
| `nothing-up-my-sleeve-plan-v3.epub` | `f8dce282a3` | 2026-11-06 | the plan with D12 to D16, chapter 9 and the epigraphs + the Kindle notes; first with the cover (v2 was built without one and never sent; its draft is in Gmail) |
| `nothing-up-my-sleeve-plan-v4.epub` | `3f83c1876e` | 2026-11-06 | the plan re-cut for D17 (the world's books to 1930), chapter one written, the front page, the Kindle notes |
| `Nothing Up My Sleeve (v6).epub` | `4aaac792fa` | 2026-11-06 | the whole book so far: front page, the plan (D1 to D28), the five parts with chapters 1 and 8 written and the rest as stubs or source essays, both sets of Kindle notes; one file per chapter with a nested contents list; the cover is the Risso-style card-table art from the Atlas generator (`cover-art.png`, composed in grayscale). v5 was the same text with a drawn-cards cover and was never sent |
| `Nothing Up My Sleeve (v7).epub` | `9bbf3abdf6` | 2026-11-06 | the second draft of the plan, around the safety question, twenty-two chapters with The Concerns and The Charter as new stubs; a visible Contents page after the cover and an NCX index for the Kindle Go To menu; v6 retired from the folder, its row kept |
| `Nothing Up My Sleeve (v8).epub` | `a8783ec984` | 2026-11-06 | the preface on Blake; Part I re-cut to three chapters; the Super-agent chapter opening Part V; the twenty hole cards; Plan, Decisions (D1 to D38) and the notes behind the book; v7 retired from the folder, its row kept |
| `Nothing Up My Sleeve (v9).epub` | `6712185fc9` | 2026-11-06 | Part I written: the Argument, Who Owned the Fire, The Guessing Machine, The Method, with the preface; the Culture essay absorbed and archived; v8 retired from the folder, its row kept |
| `Nothing Up My Sleeve (v10).epub` | `4bbdcae400` | 2026-11-06 | the Argument dropped; every part opens on a page in the preface's form (Blake, Dickinson, Kipling, Tennyson, Yeats); v9 retired from the folder, its row kept |
| `Nothing Up My Sleeve (v14).epub` | this commit, in Thorp | built 2026-11-13, not yet sent | the first build from Thorp, answering the 24 notes on v13: the preface rewritten (a language model, AI and Mind, the credit to the commons, curiosity as the only trait set, the stop as the ship's); the line at 1930 an option, in the preface, chapters 3, 9 and 10 and the opening of Part III (D49); chapter 1's text changes and six new footnotes of Luck's (the chip seller, the collapse, Australia, the Index, the Falcon models, the seventeen titles); the front page cut to three lines, with About this book and the Beats read last (D51); D49 to D54; the v13 notes file; v13 retired from the folder, its row kept |
| `Nothing Up My Sleeve (v13).epub` | monorepo `34dbd01e4c` | 2026-11-06 | chapter 3 opens as the dialogue, Quentin and the author, with the oke from Cambridge; six more footnotes from the v12 notes (Bacon, Childe, the chokepoint, the token owners, dark knowledge, sixty-four); the blog pointer on the front page and in the Beat of Part III; D47 (version 0.0 is about the shelf) and D48 (Quentin's series on the blog); the v12 notes file; v12 retired from the folder, its row kept |
| `Nothing Up My Sleeve (v12).epub` | `b74838753d`+ | 2026-11-06 | the first build with footnotes, pictures and diagrams: Quentin's eight footnotes from the v11 notes (the cesspool, hallucinatory warfare, the chicken dinner, the cock-fighting rings, the dash, the Dickinson poem stanza by stanza, art, the ex-wife's mother), every `peek:` picture as a captioned figure, every mermaid block rendered; Quentin, not Damien (D46); the v10 and v11 notes as a third notes file; v11 retired from the folder, its row kept |
| `Nothing Up My Sleeve (v11).epub` | `b74838753d` | 2026-11-06 | the parts renamed for their poems' lines (Did he who made the Lamb make thee?, Wider than the Sky, Not built to comprehend a lie, To follow knowledge, The falconer), each opened by its poem page as the divider and then its Beat page, two paragraphs on the cadence of its chapters; chapter 10 written, with Seeds by hand (D43) and the Language kind (D44); v10 retired from the folder, its row kept |

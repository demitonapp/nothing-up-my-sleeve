# Writings

**This is the canonical copy of *Nothing Up My Sleeve*.** Edit the book here, in Thorp, and nowhere else.

The book was written in the monorepo (`docs/writings/nothing-up-my-sleeve/`, last changed there in
`34dbd01e4c`, epub v13) and was copied here on 13 November 2026 from monorepo `d112eab0dd`, byte for byte.
The monorepo copy is now a mirror: it stays so the Atlas reader (`packages/ui/apps/atlas/src/essays.ts`), the
art generator (`packages/ui/apps/atlas/scripts/generate-government-art.py`) and the monorepo's own
`scripts/check_book.py` keep working, and it is brought up to date from here, never the other way round.

```bash
rsync -a --delete --exclude .DS_Store --exclude MIRROR.md ~/Source/Thorp/docs/writings/nothing-up-my-sleeve/ ~/Source/monorepo/docs/writings/nothing-up-my-sleeve/
```

```text
docs/writings/
  README.md                 this file: which copy is canonical, and how the mirror is refreshed
  check_book.py             the sidecar contract, copied from monorepo scripts/check_book.py; run from the Thorp root
  nothing-up-my-sleeve/     the book: book.md (front page and the parts table), about.md and the-beats.md
                            (read last), plan.md, decisions.md, the Kindle notes, one folder per part,
                            pictures/, epub/
```

The layout of the book, the chapter and sidecar contract, footnotes and pictures are described in the
monorepo's `docs/writings/README.md`, which the book was built against; nothing about them changed in the move.
Check the book after every edit:

```bash
python3 docs/writings/check_book.py
```

**What still lives in the monorepo.** Three tools the book uses were not moved:

- the Atlas reader, which shows the book at `#/essays` (it reads the mirror);
- the picture and cover generator, `generate-government-art.py` (`peek:<id>` and `cover:nothing-up-my-sleeve`);
  a new picture made there is copied back here into `nothing-up-my-sleeve/pictures/`;
- `epub/render_mermaid.mjs` runs the Atlas reader's mermaid in Playwright from the monorepo's
  `packages/ui/apps/app`. The epub is built here all the same: `build_epub.py` finds the monorepo checkout
  beside Thorp (or at `$NUMS_MONOREPO`) and renders the diagrams through it, as `epub/README.md` says. Without
  that checkout, an epub with diagrams cannot be built.

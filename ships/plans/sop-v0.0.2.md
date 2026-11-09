# Thorp Ship SOP v0.0.2 — content first, the cards after, a fifth by heart

**Status: adopted by Justin, 9 November 06:25: "Content first should be 0.2".** Supersedes v0.0.1.
Everything in v0.0.1 stands — the corpus, the tokeniser, the cleaning, the passes, the parameters, the five cards in
rank order, the capacity rule — **except the order of the phases.**

## What changed

| | v0.0.1 | v0.0.2 |
|---|---|---|
| 0–10% | scaffold at full weight | **content** (the ship learns to read) |
| 10–60% | the pull fades to zero | content |
| 40% | — | **scaffold full weight** (the cards come in) |
| 50–80% | — | the pull fades to zero |
| 60–100% | content (by heart) | content from 80% (by heart) |

Three phases, as data (`ships/plans/sop-v0.0.2.json`):
`[{content 0.40}, {scaffold 0.40, hold 0.25, fade 1.0}, {content 0.20}]`.

## Why

The 300k under v0.0.1 paid for the cards it pinned from step 0: its delimiter — the one card it already had — was
halved (3.42 → 1.68), while the cards that were actually missing barely moved. The Basics form on their own during
plain reading (previous_word 0.36, delimiter 3.42 in the control); the pull is only needed for what does **not** form.
Reading first also stops the pull fighting the language loss in the steps where the model is still learning that text
is text.

## What it tests

Whether the cards a size can hold are held **better** when the ship reads first — and whether the 300k stops losing
its delimiter. The prediction, stated before the voyage: previous_word at least as high as v0.0.1's 0.761, delimiter
above the control's 3.42, and the Stage 1s (induction, duplicate_word) no worse — if the ordering is what mattered.
If the cards fall instead, the pull needed to be there early, and v0.0.1's order was right.

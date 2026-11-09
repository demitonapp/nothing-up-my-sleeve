# Thorp Ship SOP v0.0.5 — the one standard

**Consolidated by Justin, 9 November 10:10: "consolidate all the current versions into 0.0.5 and then restart the queue
with 300k, 1m, 9m with all the versions changes consolidated in 0.0.5".** Supersedes v0.0.4; v0.0.6, v0.0.7 and v0.0.8
are folded in and deleted — their content lives here.

## What a voyage is

A ship's size (the model preset) and an SOP version. The size is the shape; the standard is the content, the
tokeniser, the parameters, the phases, the pinning and the depth. A voyage with neither is an experiment, not a ship's
voyage (S5 policy `standard`). The **fitout is retired** — a voyage names the standard, not a corpus label.

## The content

Ogden's 850-word English: `lists/ogden-v0.1.csv`, cleaned `unwrap-v2`, shuffled, four passes, refusing the three
held-out decks. Tokeniser `spm-bpe`, 2,048 pieces, byte fallback, trained on the same list.

## The phases

1. **content, 0–10%** — the ship learns to read; the cards are pulled in at full weight from step 0.
2. **the fade, 10–60%** — the pull falls to zero.
3. **content by heart, 60–100%** — nothing is telling the ship anything; this is the test.
4. **the post-training stage** — after the four pretraining passes, one more pass over the card-linked corpus
   (`lists/card-stage-deck-v2.csv`) with the pull off, where a circuit that decayed can be rebuilt.

## The depth

**Depth is dynamic**: every size takes the most layers its budget allows at its standard width, capped at Qwen3 4B's
36. The ladder was rebuilt on 9 November so the width pays for depth:

| size | layers | width | parameters |
|---|---|---|---|
| 300k | 6 | 48 | 313,968 |
| 1m | 12 | 80 | 1,169,360 |
| 9m | 18 | 120 | 3,483,480 |
| 21m | 24 | 192 | 11,216,064 |
| 50m | 36 | 304 | 40,879,792 |

The pinning table follows the depth: a Basic at layer 0, a Stage 1 or a Face at two-thirds (300k L4, 1m L8, 9m L12,
21m L16, 50m L24), the comparator at one-third. `sop.check` reports a voyage whose layers depart from the table.

## The star chart, and its arm

The chart is the map to chaining: sixteen cards in the deck's order, the four relations and the four chaining tests,
the depth of each card, and the retention tier — **keeper** (holds with the pull off), **decayer** (reads under the pull
and falls), **untested** (never pinned). Its ten points are what Qwen3 4B's own reading and ablation put in the
journey, and **the arm is the same set at every size** — previous_word, delimiter, induction and the comparator as the
riddle — so a size is compared with the 300k on the same points, not on a richer one.

## The rule the chart enforces

A point is **carried** when its card reads *and* the chaining gap opens; it is a **reporter** when its card reads and
the gap does not. The fleet's evidence so far: every arm chained while the pull was on and lost it when the pull went
(the 300k chart arm read nature +0.105 at step 1,920 and +0.012 at the end; its comparator went from 1.00 to 0.04).
Which is why the post-training stage exists and why the depth was raised.

## The goal, restated (Justin, 9 November 10:58)

The goal is **chaining**, and it has two statements:

- **the 300k's goal is chaining at the smallest size possible** — not the bigram table. The trigram/keyed table is a
  *reading*, not the objective; a 300k that holds the keys and never chains has failed its job.
- **the fleet's goal is chaining equal to Qwen3 4B.** Qwen3 4B reads 0.538 on the chaining lift; every rung is measured
  against that line, not against the rung below it.

One assumption is open and should be recorded as such: **that chaining is the thing that most contributes to solving
quantum-physics reasoning.** The fleet assumes causation for now; the assumption is not tested, and a size that chains
without reasoning, or reasons without chaining, would test it. Until then, chaining is the proxy and the crown.

What this changes in practice: the size pages and the queue should lead with **chaining against Qwen3 4B**, not with
`keyed_top1` or the maths chapters. Those remain readings — the maths book is still Augustus's answer to its own
question — but they are not the goal.

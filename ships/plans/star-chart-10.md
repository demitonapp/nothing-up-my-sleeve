# The ten-point star chart (9 November) — what to test on the 300k

The sixteen-card deck was our summary of a chaining model. The probe and the causal test have now measured Qwen3 4B
directly, and the two disagree in a way the chart has to carry: **a head whose attention rises with chaining is
usually reporting the answer, not producing it.** Of the ten heads measured, one clears the random band.

This is the reduced chart: ten points, each a place chaining might live, each with what Qwen says about it and how the
300k can test it. The 300k has **two layers and two heads** — four slots — so the points are tested by *role*, not by
layer index, in three arms plus the existing control.

| # | point — the role | Qwen3 4B evidence | the deck card it is | how the 300k tests it |
|---|---|---|---|---|
| 1 | **the token reader** | L0 head 2: correlation −0.172, but silencing it costs **0.052** of chaining — **1.86× the random band**. The only causal head found. | previous_word (already pinned at L0H0) | pin at L0·0 and read; it is in every arm today |
| 2 | **the boundary reader** | the L0/L1 family: the delimiter is the shallowest reading in the fleet and the strongest by size | delimiter (L0H1) | pin at L0·1 |
| 3 | **the second-premise attendee** | L15 head 17: correlation **+0.274** (the highest), causal drop 0.009 — a *reporter* | the mover (a premise carried to the frame) | the 300k's deepest slot, L1·0, reading the mover |
| 4 | **the copy gain** | L18 head 27: correlation −0.159, causal drop **0.028 — exactly the band** | the Nevermore | L1·1, read on the copy-gain card |
| 5 | **the order holder** | L21 head 12: correlation +0.270, causal drop **0.000** — a *pure reporter* | the comparator | L1·0 with a riddle; if it chains, the reporter was the cause |
| 6 | **the repeat catcher** | L15 head 7: correlation +0.258, and silencing it *improves* chaining by 0.005 | duplicate_word | L1·0/L1·1 |
| 7 | **the induction chain** | L19 head 9: correlation +0.264, causal 0.003 | induction | L1·1 |
| 8 | **the middle term** | L3 head 2: correlation +0.258 (early), causal 0.005 | the bridge (never held at any size) | L0·1, the only "carrying" card the shallow half can hold |
| 9 | **the suppressor** | L1 head 1: correlation −0.208, and silencing it **raises** chaining by 0.008 — a real suppressor, below the band | **the sink** (the deck's one no-op head) | the 300k's sink: a head that absorbs attention and earns nothing |
| 10 | **the blocker** | L8 head 30: correlation −0.209, causal 0.002 | **the sink** | as point 9: measured as the sink's presence, not as a card of its own |

## The three arms, plus the control

The existing 300k arm (`sop001@300k`, chaining 0.034) is the control. Three arms carry the ten points, each reading
all sixteen cards so every point is visible:

- **Arm A — the shallow pair (points 1, 2, 8).** previous_word at L0·0, delimiter at L0·1, and the bridge's *riddle*
  at L0·1. Tests whether the only causal role in Qwen is the one the 300k already holds.
- **Arm B — the carrying pair (points 3, 5, 6).** The mover and comparator at L1·0/L1·1 — the deepest slots, where the
  reporters live. If the reporters are causes at 300k, this arm chains.
- **Arm C — the copy pair (points 4, 7).** induction and duplicate_word at L1, the pair that gives the Nevermore.
- **Arm D — the suppressors (points 9, 10) are not built.** They are the negative control: a ship that has learnt
  them should chain *worse*, and the deck has no card for them, which is itself the finding.

## The predictions, fixed before any arm sails

1. **Arm A chains least of the arms that chain at all** — because the shallow pair is already in every arm, and Qwen
   says the token reader is *necessary but not sufficient*.
2. **Arm B is the one to watch.** If the second-premise attendees and the order holder are causal at 300k, B opens the
   chaining gap; if they are reporters there too, B reads the cards and no gap.
3. **No arm clears the 0.1 mark.** The honest expectation, given the causal test: distributed circuits, one necessary
   shallow head, and a 300k with four slots that can hold at most two of the ten roles.

## The mapping caveat

Qwen's points live at L0–L21 of 36 layers; the 300k has two layers. The chart maps them **by role** (a token reader, a
carrying head, a copy gain), not by index. That is a real loss of resolution, and the reason the depth arms matter:
a 28-layer 300k has twenty-eight places to put a carrying head, and it is the smallest ship on which this chart can be
tested without collapsing it.

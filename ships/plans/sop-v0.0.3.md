# Thorp Ship SOP v0.0.3 — the star chart is part of the standard

**Adopted by Justin, 9 November 07:25: "once we have the star chart we'll run it on 300k, 1m and 9m to test what the
lowest model is that can chain. The star chart has to be included in the SOP".** Supersedes v0.0.2.

v0.0.2 stands entire — content first, the cards after, a fifth by heart. **v0.0.3 adds one thing: every SOP voyage is
read on the star chart.**

## The star chart

A matrix, drawn for any model or ship:

- **Rows — the sixteen cards**, in the deck's order: within each suit the Basics, then the Stage 1 that sits above
  them, then the Face that trades in both. That order is the journey, not a list.
- **Columns — the four chaining relations** (order, cause, membership, proportion) and the aggregate, plus the four
  chaining tests (nature, mill, between, pigeonhole).
- **Cells — the reading**, and where a model is ablated, the **causal weight**: how much that relation falls when the
  card is silenced, against same-size random-head controls.
- **Models on one axis**: an outside model that chains (Qwen3 4B first), then the fleet's ships, so a size is placed
  on the same map as the reference rather than on a scale of its own.

## What it is for

The chart says **which rung carries which relation**. If a relation is carried by a Basic, a small ship can hold it;
if it is carried by a Face, no amount of pinning supplies it. So the chart is the route to chaining at the bottom of
the ladder — what a 300k must build, in what order — and it is how we answer "what is the lowest model that can chain".

## The readings it requires

Every SOP voyage carries: `ce_bpb`, `discovery` (the four chaining tests), `logic40` (the four relations),
`logic`, `stars`, `nevermore`, `cards`, `shapes`, `pips`. **`logic40` and `discovery` were missing from the
voyages of 8–9 November**; they are being read back onto those checkpoints, which is cheap and makes the chart
complete without re-sailing anything.

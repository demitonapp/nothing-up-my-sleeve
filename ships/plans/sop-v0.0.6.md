# Thorp Ship SOP v0.0.6 — the post-training stage

**Adopted by Justin, 9 November 10:30: "drop post training and add it to 0.0.6".** v0.0.5 is the standard in force;
this version is v0.0.5 plus **one phase at the end**.

## What it adds

After the four pretraining passes, **one more pass over the card-linked corpus** (`lists/card-stage-deck-v2.csv`) with
the pull off. The ship meets the chart's ten points as text, carrying each on its own — the phase where a circuit the
pretraining built and lost can be rebuilt without the pin.

## Status: not yet sailable

The staged data path (`data.stages` with the deck after Ogden) **hangs in `prepare()`** — five minutes at full CPU with
no first step, reproducible outside a voyage. Until that is fixed, **no voyage names v0.0.6**; the ladder runs v0.0.5
on the single-recipe path, which works.

## What it will settle when it runs

The chart arms of 9 November all chained while the pull was on and lost it when it went — the 300k chart arm read nature
+0.105 at step 1,920 and +0.012 at the end, its comparator falling from 1.00 to 0.04 at the fade. If a post-training
pass on the card-linked corpus keeps those cards, the circuit is teachable after pretraining and v0.0.6 becomes the
standard. If it does not, the circuit cannot be taught at all at these sizes, and the answer is depth or data, not
schedule.

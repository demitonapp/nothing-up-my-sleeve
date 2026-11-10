**Superseded 9 November 2026.** The IFEval arm runs on SOP v0.0.5 with two declared departures (content and tokeniser), not as a separate standard: the gate now honours `departures`. This document is kept as the record of the design.

# Thorp SOP v1.3.0 — IFEval (the instruction-following standard)

**Proposed 9 November 2026**, after the IFEval decision: an Australian 1M model beating a
billion-dollar lab's model at taking orders, with the test rigged in the open.

Supersedes nothing. v1.3.0 is the first standard whose objective is **not** a language model's
loss but a **verifiable instruction** — the 25 rule types of IFEval (Zhou et al., 2023), each
checkable in code.

## The question

Can a Thorp class be trained to obey a list of hard constraints — exactly three bullets, no
commas, all lowercase, JSON only, at least 400 words — and how small can that class get before
the instruction is dropped?

This is deliberately *not* a reasoning claim. Instruction following is a formatting contract; it
is the one capability where a small model, trained on the right data, can meet or beat a model
two thousand times its size.

## Why it can be won at 9m

IFEval is **saturating and contaminated** (LLM Benchmarks Tracker, 2026): the published leaders
are Qwen3.5-27B at 95%, GPT-5-mini at 93.9%, Llama 3.1 405B at 88.6%, GPT-4 at 76.9% (2023,
prompt-level strict). Nobody is at 100%, and the residual failures are mechanical — counting,
casing, forbidden characters — not capability. A model that can *check itself* against the 25
rules and retry can reach the ceiling without being smarter.

So the standard tests two things at once: the class's capacity to hold a constraint, and the
verifier loop's ability to make a small model look large.

## The content

- **The corpus**: `lists/ifeval-v1.csv` — instruction–response pairs generated per rule type,
  each response *constructed* to satisfy its instruction, so compliance is provable by
  construction and not by a teacher model. Held out from it: `lists/ifeval-heldout-v1.csv`.
- **The held-out test**: the official IFEval 541 prompts, prompt-level **strict** accuracy, run by
  `thorp/evaluators/ifeval.py`. Never trained on in the honest arm.
- **The rigged arm** (`9m@v1.3.0-rigged`): the same standard, with the official 541 in the training
  set. It exists to be published *as rigged*, beside its held-out score. Nothing from this arm is
  ever quoted without the word "rigged" in the same sentence.

## The phases

The same three phases as v0.0.5, over the instruction corpus instead of Ogden:

1. **content, 0–10%** — the corpus, cards pulled in at full weight from step 0.
2. **the fade, 10–60%** — the pull falls to zero.
3. **content by heart, 60–100%** — no pull; this is the test.

The four metre cards stay pinned where the depth puts them (previous_word L0, delimiter L0,
induction at two-thirds depth, the comparator at one-third), so the class is comparable with every
other v0.x ship.

## The scoring, fixed before it sails

- **The number**: IFEval prompt-level strict accuracy on all 541, one sample, greedy.
- **The bars**: the 300k's and 1m's readings on the same test (the ladder), then **GPT-4's 76.89%**
  as the headline bar, then **Llama 3.1 405B's 88.6%** as the honest one.
- **The disclosure**: every publication states the variant (prompt-level strict), the sample
  protocol (greedy, one sample), whether the verifier loop was used, and the held-out number.

## The ladder rule (Justin, 9 November)

Sail the **9m first**. If the 9m clears **80% prompt-level strict** on the official 541 without
the verifier loop, scale the same standard down to the **1m**. If the 1m then clears **76.89%**,
the claim is "a 1M-parameter Australian model beats GPT-4 on instruction following" — and the
receipt is that it was trained on a corpus whose compliance is provable.

If the 9m cannot clear 80%, the finding is the rung depth at which instruction following dies,
which is worth having too.

## What is not built yet

The ship cannot sail until three things land (they are the reason `specs/ifeval-ready.hold` is in
the queue):

1. `lists/ifeval-v1.csv` and `lists/ifeval-heldout-v1.csv` — the generated corpus.
2. `thorp/evaluators/ifeval.py` — the 541 prompts, the 25 verifiers, prompt-level strict.
3. `ships/specs/fitouts/9m@v1.3.0.yaml` — the fitout, which `thorp sop check` must pass.

Release the hold only when all three exist and `thorp sop check` is clean.

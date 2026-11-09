# Thorp Ship SOP v0.0.1 — the standard a voyage is built to

**Status: draft, for Justin's word.** This is the first version of the standing operating procedure that
dictates, for every ship at every size: **what it reads (content), the parameters it is trained with, and the
phases it is trained in** — and then how it is read and how a version is crowned.
(8 November, Justin: "we need to have some form of crown doctrine or sop across all ships. That's what i meant by
0.3. But let's do the first SOP v0.0.1" … "and that dictates content, parameters, phases of training everything".)

**v0.0.1 is a recording, not a reform.** It writes down what the fleet already does, in one place, so that a
voyage can be checked against it. Where the practice is silent or inconsistent, the point is marked **OPEN** and
left for Justin — not decided here.

---

## 1. Scope

Every size on the ladder (300k to 350m), every ship, every voyage that sails on this Mac or a hired GPU.
A voyage that does not follow the SOP is an experiment, and must say so in its spec and its expedition write-up.

## 2. The invariant: what every ship shares

One corpus, one tokeniser, one cleaning, one context, one batch: **ships differ in size alone**, which is what
makes a size's reading comparable with the size beneath it.

| The invariant | Value | Where |
|---|---|---|
| Corpus | Ogden v0.1 (`lists/ogden-v0.1.csv`), the fixed corpus | `data.recipe` |
| Tokeniser | spm-bpe, vocab 2048, byte fallback, **trained on `lists/ogden-v0.1.csv`** — shared by every size, including ships that read v0.2 | `tokeniser` |
| Cleaning | `unwrap-v2` — the current version, and the only one a new voyage may read | `data.clean` |
| Refused decks | `hole-cards.csv`, `hole-cards-v2.csv`, `hole-cards-unseen.csv` (the judge books never train) | `data.refuse` |
| Context | 1024 pieces | `model.context` |
| Positions | rope | `model.positions` |
| Order | shuffled | `data.order` |
| Passes | 4 | `data.passes` |
| Batch | 32,768 tokens | `optim.batch_tokens` |
| Optimiser | AdamW, betas 0.9/0.95, weight decay 0.1, cosine to 10% of peak, grad clip 1.0, bf16 | `optim` |
| Lanes | one voyage per lane; the Mac lane is Phaleron, the Vast lane the Market Harbour | S2 |

## 3. What varies, by size

Two things only: **the shape**, and **the learning rate and its warmup**. Both are the size's, and a ship may
not choose them — they are what the class *is*.

| size | shape (layers × width × heads) | lr | warmup steps |
|---|---|---|---|
| 300k (Pan) | 2 × 64 × 2 | 0.003 | 100 |
| 1m (Augustus) | 4 × 128 × 4 | 0.002 | 100 |
| 9m (the speller) | 6 × 192 × 6 | 0.001 | 200 |
| 21m (the stylist) | 8 × 320 × 8 | 0.0008 | 300 |
| 50m (the paragraph) | 12 × 512 × 8 | 0.0006 | 400 |

A size's **goal** is its own (the primary objective in `s1.sizes`): the 300k the bigram table, the 1m the maths
book, the 9m spelling in bits per byte and the cards, the 21m grammar and the chaining deck, the 50m paragraphs
and the chaining gain. The goal does not change what the ship reads; it changes what the ship is *read on*.

## 4. The phases of training

A voyage is trained in one of two structures, and the spec must say which.

**P0 — the plain keel (the baseline).** No scaffold. Read text from step 0 to the end. Every size's control
voyages are P0, and every experiment is measured against a P0 of the same size and corpus.

**P1–P3 — the scaffolded voyage.** Three phases in one run (`optim.scaffold`):
- **P1 metre**: chosen heads are pulled toward a metre card's pattern (a rule over the token ids; no teacher
  needed) at full weight, to `hold` of the voyage.
- **P2 fade**: the pull is eased to a floor (or to zero) by `fade` of the voyage.
- **P3 content**: the language-model loss alone. A card still played here is held **by heart**; a card that
  disappears was only ever from the page.
- **Riddles** (the comparator, the bridge) may be pulled on composed items, with their own layer and their own
  start share — but only after the cards they rest on are held (the staged composition).
- `release` zeroes the pull outright from a share of the voyage, and is the only setting that yields a
  by-heart reading; a `floor` above zero means the card is never read without the pull.

**A teacher** (`optim.teacher`) is not a phase: it is a second model whose softened next-word distribution (alpha,
temperature) or whose attention (alpha 0, `teacher_layer`/`teacher_head`) the voyage learns from. A teacher must
share the voyage's tokeniser, and the voyage must say so in its expedition.

## 4a. The standard launch (SOP v0.0.1)

The first voyage of every size under this SOP, and the reference every later improvement is measured against:
`fu-ogden-v0-1~sop001@<size>-pre-s1`, one per size, **the same corpus, the same tokeniser, the same passes, the
same phases and the same cards** — shape and learning rate alone differ (§3).

**The card set, in rank order** (the five that the fleet's readings say are worth teaching; see DECISIONS
"The Library filters..." and the card grid):

| # | card | stage | how supplied |
|---|---|---|---|
| 1 | previous_word | Basic | metre: layer 0, head 0 |
| 2 | delimiter | Basic | metre: layer 0, head 1 |
| 3 | induction | Stage 1 | metre: layer 1, head 0 (above previous_word) |
| 4 | duplicate_word | Basic | metre: layer 1, head 1 |
| 5 | comparator | Stage 1 | riddle: composed greater-than items, where the size has a free layer and head |

**Capacity rule.** A size pins the cards in rank order up to the heads it has: the 300k (4 heads) pins the four
metre cards and carries no riddle; the 1m (16) and 9m (36) pin all four and add the comparator as a riddle
(layer 2 for the 1m, layer 3 for the 9m, 16 items, pool 2048). Withholding a card a size has room for is not
SOP-conformant; pinning a Stage 1 below what it rests on is not either.

**The schedule, identical at every size:** `weight: 1.0`, `hold: 0.10`, `fade: 0.60`, **no floor and no release
flag** — the pull is at full strength for the first 10% of the voyage, eased linearly to zero by 60%, and the last
40% is content alone. There is no floor because a floor is never by heart: the bridge's 2.27 under a floor of 0.2
was 0.11 once it was measured properly. The last 40% is the window in which a card counts.

**Why this schedule and not 5%/25%:** at 5%/25% the 300k's previous-word survived (0.76) and induction did not
(0.09); the 9m's own rule from the night was full to 10%, faded by 60%. v0.0.1 adopts the measured rule.

**What a SOP voyage may not do:** read a different corpus, use a different tokeniser or cleaning, choose its own
lr or warmup, run a teacher, or carry a floor. Those are experiments and must be named as such.

**Operational rule (learned the hard way, 8 November):** a voyage's launch must never depend on the network. uv's
sync answered 504 from GitHub for a spaCy wheel and killed nine voyages in thirty seconds each while the
environment was intact; the queue now launches with `--no-sync` and the coordinator starts the same way.

## 5. How a ship is read

- **At the end of the voyage**, not at its best: a peak under a scaffold is the scaffold, not the ship. (The bridge
  is the proof: 2.27 at step 1,280, 0.11 at the end.)
- On its **goal's metric** and on the **deck** (the sixteen cards), from the artifacts the evaluators write; plus
  the judge books for bits per byte where the size is read on them.
- A reading that clears its card's mark is **lit**; a card still lit after `release` is **held by heart**.
- A reading inside the noise is not a reading: ±0.008 on `shapes/keyed_top1` at the 300k, and the chaining
  noise of 0.03.

## 6. The crown doctrine (answered by Justin, 9 November: "chaining lift is the goal across all ships in the fleet, so ultimately to earn launching the 100m, we only earn launching the 100m when we get chaining as high as possible across the fleet")

**Chaining lift is the fleet's goal.** Every size's goal (§3) is what that ship is *for*, but the measure across the
fleet is chaining: a size is doing its job when its chaining lift is as high as that size can reach. **The 100m is not
earned by a schedule or a budget; it is earned when chaining is as high as possible across the fleet** — the explorer
sails when the ladder beneath it has stopped rising, and not before. That is the gate on the largest hire.

The crown itself is as coded (below): chaining lift, noise 0.03, two sailings, a version only by beating the
incumbent by more than the noise — which is now consistent with the fleet's goal rather than beside it.

From `leaderboard.crown()`:
- The crown is decided on **chaining lift**, noise **0.03**.
- A candidate needs **two sailings**; among candidates within the noise of the best, the tie-break is: has a logic
  reading, then more sailings, then the higher lift.
- A new version is crowned only when it is a **different ship** and beats the incumbent by **more than the
  noise**; the version number is the next in the register (`s1.crownings`), and the ship is named
  `Thorp <size> v<n>`.
- Retiring a ship is by hand (`s1.ships.status`); nothing is deleted.

## 7. Versioning of this SOP

- The SOP is versioned separately from the corpus. **v0.0.1 = what is done today.** A change is a new version,
  with the reason and Justin's word, recorded in DECISIONS.
- A voyage's spec will carry the SOP version it was built to (a `sop:` field), so a reading can be read against
  the standard it sailed under. **Not enforced yet** — the field does not exist, and no gate check reads it.

## 8. OPEN — where the practice is silent, for Justin

1. ~~**What the crown decides on.**~~ **Answered, 9 November: chaining lift, fleet-wide.** A size's own goal stays
   what that ship is for, but the crown and the 100m's launch are decided on chaining: the 100m is earned when
   chaining is as high as possible across the fleet.
2. **Regression.** Nothing stops a ship crowning while losing cards the incumbent held. Should a crown require
   no held card to fall below its mark?
3. **What a sailing is.** The code counts `sailings`; nothing defines one. One finished voyage? One seed? Two?
4. **Who signs.** The crown is automatic today. Should a new corpus version, or a change of goal, need Justin's
   word explicitly (it does in practice, not in code)?
5. **The corpus version.** v0.2 read a different corpus but kept v0.1's tokeniser. May a new corpus version
   change the tokeniser — and if it does, how is it compared with the ships it must beat?
6. **Retirement.** Should a challenger that misses three times in a row be retired automatically, as a rule,
   rather than by hand?

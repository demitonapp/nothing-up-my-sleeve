# Nothing up my sleeve v0.1: a proposal for the full charter

12 November 2026, night. A draft for Justin to walk and sign, row by row. Nothing here is signed, and nothing
here has been built or queued by being written down.

**The bar** (Justin, 12 November): "I want the first Nothin up my sleeve to have a reasoining variant, tool
calling, decent context window and be as good as possible on all our tests on the leaderboard." And the same
night: the reasoning and the tools are the 50m's; the first fleet's corpus may take any text; the teacher is
Qwen3.8 27B; the window is 4,096 on the 50m; and the fleet's leaning is curiosity ("the bias should be
curiosity bias as in that's the bias i want locked in"), which is section 8a.

**How to read a row.** *Proposed* is the value I would put in front of you. *Rests on* is the evidence: ours
(a voyage, by name) or the field's (a discovery on the map, with its source). *How sure*: **sure** (our own
readings and the field agree), **fairly** (one of the two, or one seed), **a bet** (nobody has shown it at our
sizes). *Sign* says whether it can be signed tonight or what it waits for.

**Where it stands** (after the walk of 12 November, night). Of the charter's 38 rows: 16 are signed, 13 of them
that night (*bias terms* last, once it was named for what it is); 1 (*clean*) waits on a one-line rework of the 9m's fitout; 11 wait on voyages already
queued or proposed below; and 10 (the corpus, the symbols and the return leg) wait on things not yet built.
Seven more rows are proposed that the charter does not have. Three of the waiting rows could be signed for four
of the five classes, if a row could be signed class by class; today a signature takes all five.

---

## 1. The fleet

Nine ships, where the charter has eight.

| Ship | Class | What it is |
|---|---|---|
| base | 300k, 1m, 9m, 21m, 50m | as the charter has them |
| instruct | 9m, 21m | the conversation leg |
| instruct | 50m | the conversation leg, then the tool leg |
| reasoning | 50m | **new**: the 50m instruct ship taught the thinking switch, as a ship of its own |

Why a ship of its own for the reasoning: you asked for a reasoning *variant*, and the one published report of a
small tool caller (90M) found that reasoning traces among its tool lessons made it run on without end. Keeping
the tool ship and the reasoning ship apart means a fault in one does not sink the other.

*How sure:* a bet. The 50m would be the smallest plain decoder shown to call a tool (nearest published: 90M, of
another build, 41% on the standard test) or to reason in plain English (nearest: 125M, on twelve million
problems). A 100m is the fallback if the 50m reads low; it is not proposed for v0.1.

---

## 2. The ship

| Row | Proposed | Rests on | How sure | Sign |
|---|---|---|---|---|
| layers, width, query heads | **hold**: the deep ladder (6x48, 12x80, 18x120, 24x192, 36x304) is not proposed for signing | Field: at a fixed 41M the best model had five layers and nothing was gained past it; facts followed width; every published model near 40M is shallow and wide (8x512, 4x768, 6x512). Ours: the wide 1m once read 1.611 against the deep one's 1.723, on voyages that differed in more than shape; a step's time grows with every layer | a bet either way | after the 1m pair (queued, kipling:8) **and a wide 50m beside the deep one** (proposed, voyage A) |
| KV heads | one per query head, every class | `300k@v0.0.6-gqa` (two seeds), `9m@v0.0.6-gqa`: language unchanged, 0.5 GB of 13.5 saved, comparator lower. Field: neutral at 125M | sure | **signed**, 12 November |
| context | 1,024 pieces at 300k, 1m, 9m, 21m. 50m: 1,024 for the voyage, stretched to 4,096 at its end | `9m@v0.0.6-ctx2048`: the books read no better at 2,048 (1.943 against 1.937) for 22.4 GB against 13.5. Field: train short and stretch late, 5% more steps in the nearest case, with long documents in the stretch; every small case is an encoder | sure for the four; a bet for the stretch | the four tonight **if the row is split by class** (not built); the 50m after voyage D |
| positions | rope | signed | | signed |
| feed-forward | plain: GELU at 4x the width | Field: within a point of the gated layer at 50M; the gated layer's gain is shown at 125M | fairly | **signed**, 12 November |
| normalisation | before each sublayer: LayerNorm | Field: pre-norm far easier to tune from 4M to 134M; no winner against RMSNorm at 27M (unreviewed) | fairly | **signed**, 12 November |
| embeddings | tied | Field: 0.2 points for an eighth of the parameters at 125M; the table is 37% of the 300k | sure | **signed**, 12 November |
| bias terms (the constant a layer adds to its sum; the row was called "biases") | none | nothing found either way; every voyage has sailed without | fairly | **signed**, 12 November |
| built | from nothing | signed | | signed |

---

## 3. The tokeniser

| Row | Proposed | Rests on | How sure | Sign |
|---|---|---|---|---|
| pieces | one tokeniser for the fleet, spm-bpe, 2,048 pieces | `9m@v0.0.6-v4096`: 1.890 against 1.937, inside the spread two like voyages show, with more non-words. Field: a vocabulary should grow with the model, slowly, and less when text is scarce; nothing published below 33M | fairly | after the three queued arms (`300k@v0.0.6-v1024`, `-s2`, `1m@v0.0.6-v4096`). **I had these down as droppable; the reading says only a voyage can answer this, so keep them** |
| byte fallback | yes | signed | | signed |
| trained on | the fleet's own corpus (section 4), with every mark below written into it | Field: a mark the tokeniser holds and training never shows is barely learned | fairly | when the tokeniser is rebuilt |
| control symbols | the eight locked on 12 November, **and**: `<think>` (closed by `<answer>`; thinking off is `<think>` with nothing after it), `<call>` and `<result>`, and one piece for each tool of a fixed set of about eight | Field: two marks and an empty pair for the switch (Qwen3, SmolLM3; nothing below 0.6B); a token a function costs the window almost nothing where JSON costs about 350 of our pieces a prompt. Ours: `300k@v0.0.6-marks-s2` reads 1.922 against the plain ship's 1.932, so marking the books cost no language (one seed; the other is at sea) | fairly for marking; a bet for these particular marks | after voyage C (the 9m rehearsal on the new tokeniser) |

The 9m's worse reading (1.937 against the earlier 9m's 1.579) is now less likely to be the marks: the marked
300k reads as the plain one does. What is left is the corpus it read (Ogden v0.1.4) and that it read it raw.

---

## 4. What it reads

| Row | Proposed | Rests on | How sure | Sign |
|---|---|---|---|---|
| recipe | **300k, 1m, 9m, 21m:** Ogden v0.1, as rehearsed. **50m:** every English book in the store (about 1.3B tokens), a science shelf (the corpus published with AI2 ARC and a set of middle-school textbooks), then Ogden's catechisms | Field: twenty tokens a parameter is a floor; a 70M model's ARC-Easy score rose from 30% to the high thirties only over tens of billions of tokens; teaching-grade text helps (shown at 1.8B). Ours: every class reads ARC at chance on Ogden's books | fairly for the four; a bet for the 50m | the four tonight if split by class; the 50m after voyage E |
| passes | 4 at 300k to 21m; 1 at the 50m over its larger shelf | Field: four passes read about as well as four times the text | sure for the four | with the recipe |
| clean | unwrap-v2 at every class, marks written onto the unwrapped text | The 9m alone reads raw, and raw text carries 2.0% newlines at 4.9 bits where unwrapped carries 0.9% at 0.9 | fairly | after the 9m's fitout is reworked to read unwrapped (a signature freezes the values as they stand, and the 9m's stands at raw) |
| order | shuffled | every voyage | sure | **signed**, 12 November |
| refuses | the three hole-card lists; **and for the 50m**, any document sharing a ten-word run with an AI2 ARC test item over half the item's length, and IFEval's 139 held-out prompts | Field: the published practice for exactly this; the 0.906 we read on IFEval is on taught prompts | sure | the lists tonight; the filter when it is built |

Why two shelves. The four smaller classes are the instruments (the towing tank, the measured mile, the sea
trial, the coasting run): they are worth most read on one fixed text, class against class, and at two bits a
parameter none of them can hold grade-school science whatever it reads. The 50m is the ship the bar is about.
The cost is that the 50m no longer reads what the others read, so "every class climbs closer than the class
beneath" (knockout:8) stops at the 21m. If you would rather keep one text for all five, the 50m gives up most
of what it could score.

---

## 5. The scaffold

| Row | Proposed | Rests on | How sure | Sign |
|---|---|---|---|---|
| pins | the candidate: previous-word and delimiter at layer 0, induction and duplicate-word at two-thirds depth | Ours: with ten pins the duplicate word lights (0.45, 0.49) and nothing else moves, at half the speed; the knockout found no card necessary for chaining; the delimiter pin never took its card in either probe sailing | fairly | after the 300k candidate pair (queued) |
| riddles | the comparator at one-third depth; no bridge | Your call on the comparator (12 November). `9m@v0.0.6-candidate-bridge`: the bridge did not light, did not move chaining and cost the language. Field: silent chaining is not learned from a pull | sure on the bridge | with the pins |
| weight | 1.0 | every voyage | fairly | **signed**, 12 November |
| hold, fade | 25% and to the end at the 300k; 10% and 60% from the 1m up | The 300k probe (two seeds): induction, the duplicate word and the comparator still lean on the pull at 80% of the voyage. The 10%/60% has no probe: `9m@v0.0.6` ends with the comparator at 0.65 after 40% unpulled. Field: the one published scaffold also fades to zero, and never measured what was kept | fairly at the 300k; a bet above it | the 300k after its candidate pair, which tries 10%/60% there; the rest with the 1m base |
| release | none | The probe, and the release arms that lost the comparator (0.11, 0.07 against 1.00) | sure | **signed**, 12 November |

One thing to say plainly: the scaffold is our own line of research and nothing read says it lifts a
leaderboard score. It is proposed because the stars are what the fleet is for, not because the bar needs it.
At the 50m it comes off for the stretch to 4,096, where each pinned head's map is a quarter of a gigabyte.

---

## 6. The training

| Row | Proposed | Rests on | How sure | Sign |
|---|---|---|---|---|
| optimiser | AdamW | every published recipe from 15M to 70M | sure | **signed**, 12 November |
| *weight decay, betas* (new rows) | 0.1; 0.9 and 0.95 | in every fitout already, and in every published recipe | sure | when they are rows |
| learning rate | 0.003, 0.002, 0.001, 0.001, 0.0006 | The 50m's is the published 50M recipe's; the 9m's has sailed many times. Field: small models are the hardest to tune (7.9% of settings near the best at 4M, 28.1% at 134M). The 300k's and 1m's are above anything published and were never swept; the 21m's 0.001 has never sailed (v0.0.5 used 0.0008) | fairly from the 9m up; a bet below | after voyage B (a small sweep at the 300k and the 1m) and the 21m's rehearsal |
| warm-up | 100, 100, 200, 200, 400 steps | Ours: stable at every class sailed. Field: a thousand steps and more, several times ours | fairly | with voyage B, which tries 5% |
| batch | 32,768 tokens | every voyage | sure | **signed**, 12 November |
| schedule | cosine to 10% | every voyage; the published ones decay likewise | sure | **signed**, 12 November |
| grad clip | 1 | every voyage; the published recipes | sure | **signed**, 12 November |
| precision | bf16 | measured the fastest on this Mac (11 November) | sure | **signed**, 12 November |

---

## 7. The return leg

| Row | Proposed | Rests on | How sure | Sign |
|---|---|---|---|---|
| inherits, the pull, learning rate | free; off; 0.0003 | `9m@v0.0.6-talk` against `-talk-hot`: the lower rate kept the language (hole cards 1.815 against 2.017) at no cost to the replies. Field: a leg should be short and gentle | fairly | after the leg below shows it answers its question |
| turns | marks | the symbols above | fairly | with the symbols |
| stages (9m, 21m, 50m) | the dialogue shelf once, then the conversation corpus | The first talk legs barely read their question (worth 0.037 bits a byte); the conversation corpus and the question-gain reading were built to mend that, and `9m@v0.0.6-converse` has docked. I have not found its question gain in the ledger | a bet | when that reading is taken |
| *the tool leg* (new, 50m) | about eight fixed tools; calls and results made by code, the question and the closing sentence by the teacher; one lesson in eight with no call to make; about two thousand examples a tool; no thinking in it | Field: the shape reported by the builders of the 90M and 121M tool callers; a few hundred examples teach which tool, thousands the arguments | a bet | after voyage C |
| *the reasoning leg* (new, 50m reasoning ship) | short chains in Ogden's words, on questions whose two facts the ship met apart, every answer checked by code; half the lessons with thinking and half without | Field: a 10.6M model from nothing got every sum right with 1,000 written-out examples where 10,000 plain ones stalled at 85%; steps help when the facts were never seen together; small students learn more from short chains; silently a fact must be learned twice | a bet | after voyage C |
| *the stretch* (new, 50m) | the last 5% of the base voyage at 4,096 pieces, on the longest books, the scaffold off | Field: NeoBERT and SmolLM2 did this; no small decoder has | a bet | after voyage D |

---

## 8. The bar, in numbers

Proposed targets for the 50m, so that "as good as possible" can be read. Each is set from what the reading
found, and each should be reset once its first honest reading is in.

| Test | Today | Proposed target | Why that number |
|---|---|---|---|
| AI2 ARC, Easy | 26% (chance is 25%) | 32% | A 70M model reached the high thirties over tens of billions of tokens; low thirties at 40M is the reader's inference, not a published figure |
| AI2 ARC, Challenge | 21% | none | published small models never leave chance |
| IFEval, held-out prompts | never read | read it first | the 0.906 is on taught prompts |
| Tool calls (our own test, simple English, one call, eight tools) | no test exists | 40% of calls exact | what the 90M model reads on the standard test's single calls |
| Chaining two facts, thinking on | gain within noise at every class | a gain above the 0.1 mark | written out, a fact need only be learned once |
| ARC-AGI-2 | 0 | none | Qwen3 4B reads 0 of 120 |

### 8a. The leaning: curiosity

Justin, 12 November: "the bias should be curiosity bias as in that's the bias i want locked in." The fleet is
to lean toward curiosity. No row of the charter holds a leaning, so this is a seventh row to add, and it can be
locked in three places.

| Where | Proposed | What exists | How sure |
|---|---|---|---|
| Measured | the curiosity ladder read on every ship of the fleet, as part of the standard | Built (six rungs, from knowing what it does not know up to asking). Read on one ship only, a 21m: rungs 1, 3 and 4 present; noticing the strange, expecting an answer and asking absent. It is not in SOP v0.0.6's readings | sure it can be read |
| Taught | the conversation and reasoning corpora written by the teacher as a curious speaker: it asks when it does not know, says what it would look for, and still answers | Nothing. Field: a thousand well-chosen examples set an assistant's manner; a manner taught by reward can sour into agreeing with the user, so the lessons ask and do not flatter | a bet |
| Read inside | a curious-against-incurious direction looked for in the 50m, as it is in Qwen3 4B | The reading exists for outside models (six traits, curious among them); never run on a ship of ours | a bet |

A target to judge it by: the 50m base with rungs 1 to 4 present and in order, and the 50m instruct ship with
rung 6 (asking) present, which no ship of ours has shown.

---

## 9. What has to sail before the launch

In order. The costs are estimates from the one 50m that has sailed abroad (683M tokens in 140 minutes on a
hired RTX 4090, about a dollar) and from this Mac's own times.

**Already queued, keep:** the 1m base and its hull pair; the 300k candidate pair; the three vocabulary arms;
the AI2 ARC and IFEval readings. **Still for you to call:** the four 300k return legs, `1m@v0.0.6-pins`,
`300k@v0.0.6-base`, the five knowledge-kind arms (they read the language and the cards by kind, which the two
shelves above no longer turn on) and the 8.3 h Qwen3 4B ARC-AGI-2 reading.

| | Voyage | Decides | Where, and about how much |
|---|---|---|---|
| A | A wide 50m (8 layers of 640, the same count) beside the deep one, on Ogden v0.1 | layers, width, heads at the top | abroad; two voyages of under an hour, well under a dollar each |
| B | The rate at 1x, 0.5x and 0.25x, and a 5% warm-up, at the 300k and the 1m | learning rate, warm-up | this Mac; six voyages, about four hours |
| C | A 9m on the rebuilt tokeniser, then its conversation, tool and reasoning legs | the symbols, the legs' mechanics, the two new evaluators | this Mac; a base voyage (about 4.5 h) and three short legs |
| D | A 9m stretched from 1,024 to 4,096 for its last 5%, and one measured step of the 50m at 4,096 | the stretch; whether 4,096 fits a hired GPU | abroad; the memory of a step there is unmeasured |
| E | The 50m on its larger shelf with the science, read on AI2 ARC, beside the 50m on Ogden v0.1 | the 50m's recipe | abroad; about 2.6 h and a little over a dollar |
| F | The 21m at SOP v0.0.6 | the 21m's rate; its first rehearsal on this standard | abroad (12.5 h on this Mac at v0.0.5) |
| G | The 50m entire: base, stretch, conversation and tool legs, and the reasoning ship | the launch rehearsal | abroad |

**To build first** (none exists): the tokeniser with the new marks; the 50m's corpus list and the filter that
keeps the test out; the tool corpus and a tool-call evaluator; the reasoning corpus and a thinking-on,
thinking-off evaluator; a voyage that changes its window part-way; the six new rows in the charter, and a row
that can be signed class by class; the freeze to SOP v0.1 and the fleet's specs.

**Before the teacher is used:** its tool calling in our harness (never tried) and its speed at corpus scale
(unmeasured). Its licence reads Apache 2.0 on the copy held here.

---

## 10. Where I have changed my mind today

- **The deep ladder.** I took it as given this morning. The one comparison at the 50m's size goes against it,
  so the hull rows are held, not proposed.
- **Twenty tokens a parameter.** I said the 50m wanted about 800M tokens. That is the floor; the models it will
  be read beside saw thousands a parameter.
- **One leg for tools and reasoning.** I recommended one 50m ship carrying both. The reading argues for two.
- **The three vocabulary arms.** I listed them as droppable. Nothing is published at our sizes, so they are the
  only way to know.

## 11. What could sink it

- **The 50m may be too small for either new ability.** Nothing published shows a plain decoder of 40M doing
  either. Voyage C tells us at the 9m whether the mechanics work; only G tells us whether the 50m can.
- **The 9m's lost language is unexplained.** If it is the corpus or the raw text, section 4's cleaning fixes it;
  if it is something else, the 9m's column is wrong in a way this proposal has not found.
- **Text.** Even on every English book in the store the 50m sees about thirty-two tokens a parameter.
- **The scaffold at the top.** No ship above the 9m has sailed the candidate scaffold on this standard.
- **Sources.** Eight of the papers behind this were opened twice and confirmed; the rest rest on an abstract, a
  summary or a reader's word (`DECISIONS.md` lists which). The Pythia ARC readings and the tool-call formats are
  among the unconfirmed.

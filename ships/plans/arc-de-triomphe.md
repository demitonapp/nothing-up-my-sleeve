# Arc de Triomphe — the expedition after Kipling

Written 11 November 2026, revised the same afternoon. Registered as `fleet.EXPEDITIONS["arc_de_triomphe"]`; a
voyage belongs to it when its ship label starts `Arc de Triomphe`, and an investigation when its spec says so.
Status: **planned**. Two investigations are queued (below); no standard is cut, because the learning ships'
standard is leg 1's verdict.

Justin, 11 November: "reverse engineer Qwen's 27B architecture against the ARC-AGI-2 score ... a deep audit
of every head, card, whatever that then indicates how it's working when asked the question and to determine
definitely why Qwen 27 is the only model of its size that scores so high on that test"; then "taking the
findings from auditing Qwen 27B and applying them against 300k, 1m, 9, and then the 21m to try get a 21m to
score on ARC-AGI-2. This may not be practical but we need to understand what the theoretical lowest size
model is that can score above 5".

And that afternoon, on reading the first version of this plan: "First thing we need to do is heavily audit Qwen
27B to determine how it got such a high score. We need to add audits/investigations into the queue so we can
queue them alongside our ship voyages"; "we need a new instrument for the 48 before we do the audit"; "Let's
start with Qwen3 4B on the Arc tests then. We'll need to test with both reasoning and no reasoning and another
goal for Arc de Triomphe is for Nothing up my sleeve ships to be able to have reasoning".

And later that afternoon: "in the arc de triomphe expedition one of the goals must be for us to have our first reasoning
model".

## The four aims

1. **The audit.** What, exactly, does Qwen3.8 27B do to score 42.4? Read with reasoning off and on, starting
   with Qwen3 4B.
2. **The arch.** What is the smallest ship that scores above 5 on ARC-AGI-2?
3. **Our first reasoning model.** A Nothing up my sleeve ship that thinks before it answers and answers better
   for it, read the way Qwen is read: the same ship with its thinking off against on. It is the first ship whose
   reasoning gain is above zero on two seeds, which the ladder asks of the 1m.
4. **The AI2 ARC audit: where our best ship stands against SmolLM2-360M.** ARC-AGI-2 gives nothing under 1B — every
   model of this size solves 0 of the 120 tasks — so the band's ranking rests on the one peer-recognised test that
   does have a gradient there, AI2 ARC (leg 4, below). The aim is to make that ranking a result rather than a
   claim, and to put our best ship on it beside a model 8.8 times its size.

**The mark** is pass@2 above 5% on the 120-task public evaluation set: 7 tasks or more (6 of 120 is 5.0%, which
is not above). It is read on the public set and labelled so; it is never set beside the semi-private 42.4 as
if they were the same reading.

## What is already known (checked 11 November)

| Fact | Value | Source |
| --- | --- | --- |
| Qwen3.8 27B, ARC-AGI-2, reasoning xhigh | **42.4%** (semi-private), $0.4469 a task | ARC Prize, verified |
| the same, low / medium / none | 22.8% / 13.2% / **1.5%** | ARC Prize, verified |
| ARC-AGI-1, xhigh / low / medium / none | 87.5 / 69.2 / 68.7 / 34.0 | ARC Prize, verified |
| what the effort setting is | one sentence in the system prompt for xhigh and for low, nothing for medium; not a budget | the model's own `chat_template.jinja`, lines 47–55, on this Mac |
| layers | 64: **48 Gated DeltaNet (linear attention), 16 full attention** (every fourth) | `config.json` on this Mac |
| attention layers | 24 query heads over 4 key/value heads, head width 256: 384 heads | the same |
| DeltaNet layers | 16 key heads, 48 value heads, width 128: 768 key heads, 2,304 value heads | the same |
| width, vocabulary, window | 5,120 / 248,320 / 262,144 | the same |
| on this Mac | the 4-bit MLX copy, 15 GB | `~/.cache/huggingface` |

Three things follow before any work is done.

1. **The score lives in the reasoning, not in one forward pass.** With reasoning off the model reads 1.5. At
   the list price of $2.55 a million output pieces, $0.4469 a task is up to about **175,000 output pieces a
   task** across its attempts (derived from the price, not stated by ARC Prize). "How it's working when asked
   the question" is therefore a question about a very long trace, and a census taken at the answer position of a
   reasoning-off run would be auditing the 1.5, not the 42.4.
2. **Three quarters of the layers have no attention map.** Thorp's cards and its head census read attention
   patterns. They apply to the 384 heads of the 16 attention layers. The 48 DeltaNet layers carry a recurrent
   state instead. The instrument for them is now built (see "The instrument for the 48").
3. **"The only model of its size" is not yet established.** ARC Prize's index gives no sizes; Qwen3.8 27B is
   the only entry whose name states one below 30B. Inkling Small (40.1) and Inkling 2 Small (81.7) have no
   stated size. Leg 1 tests the claim instead of assuming it.

And one about our own ships: in the harness's compact form at one piece a cell, **2 of the 120 evaluation
tasks fit a 1,024-piece window whole, 24 fit 2,048, 87 fit 4,096 and 118 fit 8,192** (measured 11 November).
The 300k that read ARC under Kipling scored nothing because every task was skipped for length. No ship with
today's window can reach the mark whatever it has learned.

## The outside floor

The size is already known to be possible, by models that are not language models:

- a 7M-parameter recursive model is reported at about 8% on ARC-AGI-2 (ARC Prize 2025, first paper award; the
  split is not stated there, and one outlet gives 7.8% on the public evaluation set);
- a model with no pretraining at all, trained on each puzzle alone, is reported at about 4% (third paper award;
  its parameter count is not on that page);
- the 2025 competition's best private score was 24.0%, by an ensemble that trains at test time.

So the 21m is not impractical on size. What nobody has shown is a small **autoregressive text model** doing it,
which is what our ships are. The expedition's answer will be two numbers: the smallest ship of our kind above
5, and how far above the outside floor it sits.

## Leg 1 — the audit of Qwen3.8 27B

Four causes are stated now, so the verdict cannot be fitted to the readings afterwards.

| | Cause | Held if | Refuted if |
| --- | --- | --- | --- |
| A | **The trace**: the work is done in the written reasoning | cutting the thinking at fixed budgets lowers the score in step, and solved tasks' traces carry a stated rule the answer follows | the score survives a short budget |
| B | **The training**, not the architecture | Qwen3.6 27B, reported to share the configuration, reads far lower on the same harness | the predecessor reads within a few points |
| C | **Specific components** | removing a small named set drops exact match by half or more on the contrast set while matched random removals do not | no set smaller than a random one does it |
| D | **Recall** of public tasks | solved tasks fall under rotations, flips and recolourings that keep the rule | the score survives them |

The causes are not exclusive; A and B can both hold. "Definitely" means each is marked held or refuted with its
reading.

| n | Investigation | What it settles | Where it stands |
| --- | --- | --- | --- |
| 1 | **Qwen3 4B on ARC-AGI-2, reasoning off and on** | what reasoning buys a 4B on the same 120 tasks; its solved tasks are the contrast set its heads are read on | queued: `investigations/arc-qwen3-4b` |
| 2 | **The instrument for the 48 linear-attention layers** | that the DeltaNet layers can be read and edited at all | built and passing on the 0.8B; the check on the 27B is queued: `investigations/deltanet-check-qwen3.8-27b` |
| 3 | A harness that can reproduce the 27B's number | The scorer now has the thinking switch and a budget. It does not yet set the 27B's effort (none, low, medium, xhigh) or use the published prompt form. Gate: task-by-task agreement with ARC Prize's public-evaluation grid at xhigh | to build |
| 4 | The reasoning ladder on all 120 | none, low, medium, xhigh; every trace and its length kept | a hired 80 GB box (Piraeus), bf16 |
| 5 | Is it the only one of its size | Qwen3.6 27B, Gemma 4 26B A4B, gpt-oss 20B, Phi-4 14B on the same harness: cause B | the same box |
| 6 | The anatomy of a trace | the moves in a trace, length against success, the budget cuts, wrong rule against right rule written wrongly: cause A | the 4B's after 1; the 27B's after 4 |
| 7 | Induction or recall | the solved tasks transformed: cause D | after 4 |
| 8 | The census of every component | cards on the attention heads and, through the effective attention, on the DeltaNet heads; removal and patching for every head and MLP, at the answer positions and at the rule-stating positions: cause C | after 2 and 6; the 4B first |
| 9 | The outside floor | the 7M recursive model and the no-pretraining model read on our harness | independent |
| 10 | The verdict | A–D held or refuted, what transfers, and the form a ship's thinking takes; it becomes the standard | Justin signs |

### Investigations in the queue

An investigation is a spec under `ships/specs/investigations/`, as a voyage is a spec under
`ships/specs/fitouts/`. It names its expedition outright, its subject, the command that does the reading, a
deadline and where the reading lands (`thorp/investigate.py`).

    thorp queue add investigations/arc-qwen3-4b      # queued like a voyage; --top to put it first
    python -m thorp.investigate list                  # every investigation and where it stands

In the queue it is a command line the coordinator already at sea knows how to sail, so nothing needed a
restart. It takes the Mac lane's seat in order with the voyages. Its log is
`data/runs/investigations/<name>.out` and its standing is in the store as `investigation-<name>`. What is not
done: the expedition's Plan tab does not list queued investigations yet (the queue page shows the line).

### The instrument for the 48

`thorp/deltanet.py`. A Gated DeltaNet head keeps a state, decays it, erases along the new key, writes the new
value and reads it out with the query. Unrolled, its output at a position is an exact weighted sum of the
values written before it. Those weights are the layer's **effective attention**: what an attention map is for
an attention head. So the cards can read a DeltaNet head, with two cautions: the weights are signed, and a row
does not sum to one (the instrument also gives each row as shares).

It also removes a head, replaces it with its mean, or patches in another run's output, **by real layer index**
and inside the layer, so the edit holds through cached, token-by-token generation. The attention knockout in
`thorp/inside.py` counts calls instead and loses its place there; it is not fixed by this.

Tested: against mlx-lm's own reference recurrence on made-up layers, exactly (`tests/test_deltanet.py`); and on
Qwen3.5 0.8B (18 linear layers), where it rebuilds every layer's own output to 0.3% of its largest value, an
empty edit changes nothing, and a removal reads the same through the cache as in one pass. Not yet run on the
27B, which has three value heads to a key head and 4-bit weights: that check is the queued investigation.

**Why not this Mac.** At about 175,000 pieces a task and a 27B's local speed, one xhigh reading of the 120 is
weeks, and the Mac is the learning ships' lane. The reading is a few hours on one hired 80 GB card. The 4-bit
copy here is read on a 12-task subset first; the census uses it only if it holds the score, otherwise the census
runs on the hired box with the bf16 weights (about 55 GB).

**The census cannot keep whole traces.** The residual stream of one 90,000-piece trace is about 59 GB in bf16.
The census reads chosen positions (where the rule is stated, where each row of the answer is written), not
everything.


## Leg 2 — the arch: 300k, 1m, 9m, 21m

No ship sails before investigation 10 is signed. Each rung sails only if the one below clears its mark.

| Rung | Its mark | Its reasoning mark |
| --- | --- | --- |
| 300k | the form: format rate 0.9 or more, and cell accuracy above copying the input | opens and closes a thinking span before it answers |
| 1m | the first rules: exact match above zero on held-out training tasks, on two seeds | the first reasoning gain above zero on them: **our first reasoning model** |
| 9m | the first evaluation tasks: pass@2 of 2 or more of 120 | read both ways |
| 21m | **the mark: pass@2 above 5 (7 or more of 120), on two seeds** | read both ways |

### Reasoning for our ships

The reading is the one taken on Qwen: the same ship on the same tasks with its thinking off and on, and the
difference is its **reasoning gain** (`arc/reasoning_gain`). A ship's thinking is a span it writes between two
control tokens before its answer; only what follows the span is read as the answer, as the scorer already does
for an outside model.

Three things have to exist first, and none does yet:

- **The tokens.** `<think>` and its close as single pieces. Until 11 November a voyage's declared control
  tokens never reached the tokeniser; the Kipling session fixed that the same day.
- **The room.** A window that holds the task and the thinking. At 4,096 pieces 87 of the 120 fit with no room
  to think.
- **Something to learn thinking from.** The open choice (see "Not yet decided").

Fixed before the audit, because they do not depend on it:

- **The window.** At least 4,096 pieces (87 of 120 whole); 8,192 is the arm that sees 118.
- **The refusal.** The 120 evaluation tasks are refused from every reading, as the hole cards are.
- **Two seeds for any claim.** Kipling's single-seed 300k readings moved by more than the arms differed.

Turned as levers, in the order leg 1's verdict gives them weight:

- **content**: the 1,000 training tasks; their rotations, flips and recolourings; generated tasks;
- **test-time reading**: a short reading of the task's own example pairs before answering, which ARC's rules
  allow and every small entry that scores uses;
- **reasoning**: off against on, on every ship, whatever cause A's verdict;
- **thinking taught from**: worked rules or Qwen's traces (see "Not yet decided");
- **scaffold**: the components cause C names, pinned as cards, against the same ship without them.

## Leg 4 — the AI2 ARC audit (11 November, this afternoon)

Justin: "talk me through how we can audit all those results on the 9 foreign ships to see if we can figure out
where our best ship is against SmolM2 360m".

It is independent of legs 1 to 3: it reads a test, trains nothing, and blocks no ship. The board at
`/leaderboard/xsmall` now leads with AI2 ARC, ranked by ARC-Easy (11 November), so this leg is what keeps that
ranking honest.

**Where the board stands.** Test split, zero-shot, the option's own text as the continuation, mean loss a piece:
SmolLM2-360M 64.8% Easy / 37.4% Challenge; gemma-3-270m 58.8 / 29.0; Qwen3.5-0.8B 55.3 / 34.5; Qwen3-0.6B 52.5 /
34.4; pythia-410m 45.5 / 24.9; pythia-160m 38.8 / 22.6; pythia-70m 34.3 / 21.8; pythia-31m 33.4 / 21.2; pythia-14m
29.0 / 20.7. Chance is 25%. Our five ships are unread and stand below the line.

**Step 15, receipts.** `thorp/arc_ai2.py` already builds a row a question — the CE of every option, the bet, whether
it was right, the margin — and `scripts/score_arc_ai2.py` keeps only the summary. Persist the rows with the question
id and the pinned revision, sha1'd. Then two models can be compared question by question, and "SmolLM2 beats
Qwen3.5 by 9.5 points" becomes "they disagree on these 77 questions".

**Step 16, determinism and the format.** Greedy, fixed order, no sampling: a re-run must be bit-identical, so drift is
a bug and not noise. Then four ablations on the same checkpoints: mean against sum loss (sum rewards the short
option), options shuffled (position bias), the question stripped (does the model read it at all), and the no-model
baselines — longest option, first option, word-overlap with the question — that a real reading clears by a wide
margin, or does not.

**Step 17, the normalisation the ships can share.** A 2,048-piece Ogden vocabulary spells *evaporation* as six cheap
byte pieces where SmolLM2 spells it as one expensive word piece, so mean loss a piece is not the same denominator.
Re-score the nine by bits per byte. If the ordering survives, the board is comparable across vocabularies; if it does
not, our ships need their own column and the page says so.

**Step 18, the tenth-the-size reading.** The answer-swap contamination probe on the two models whose order decides the
board (SmolLM2-360M, Qwen3.5-0.8B): keep the questions, permute the correct option — a reader drops to chance, a
memoriser does not. Then `arc_ai2` in each of the five ships' fitouts and a `thorp eval`, and the pairing: **50m at
41M against SmolLM2-360M at 360M, 8.8 times its size**, on the common subset of questions both can spell and on both
normalisations. SmolLM2-360M is read on the chaining deck too, so each stands on ARC and chaining together: behind on
ARC and level or ahead on chaining is a result, and at chance on both is also one.

**What would overturn the board.** SmolLM2-360M falling to the length or first-option baseline; the 9.5-point gap
over Qwen3.5-0.8B inverting under sum loss or shuffled options; the ordering breaking under bpb; or the answer swap
leaving its accuracy high, which would say the reading is recall and not science.

## How it ends

At the smallest rung that reads above 5 on two seeds; or, if the 21m does not, with the 21m's best reading and
the floor stated as "above 21m for this method", beside the outside floor. At most 30 voyages and
investigations in all.

## Not yet decided

- **What a ship learns thinking from.** Two sources. *Worked rules*: the generator that makes a task writes out
  the rule it used, in a compact form with no modern prose; this keeps the ships' reading honest and is the
  recommended first arm. *Qwen's traces*: the outside model's own thinking on the training tasks; it is what
  Qwen actually does, but it is modern English and another model's words, so it needs an opt-in.
- **Where the first two investigations sit in the queue.** They are at the end, behind Kipling's nine lines.

- **One expedition or two.** It is registered as one with two legs. Splitting the audit into its own
  expedition is a rename, not a redesign.
- **The standard's version.** Cut when the verdict is signed.
- **Spend.** One xhigh reading of the 120 is about $54 at Alibaba's list price; the hired-box route is a few
  hours of one 80 GB card a reading. Neither is authorised by this plan.
- **Kipling's `1m@v0.0.6-arc`** is still queued with a 1,024 window and will mostly skip the evaluation set. It
  belongs to Kipling; whether it sails as it stands is Kipling's call.

## Sources

- ARC Prize, Qwen3.8-27B results: https://arcprize.org/results/alibaba-qwen3-8-27b
- ARC Prize results index: https://arcprize.org/results
- ARC Prize 2025 (paper awards, top scores): https://arcprize.org/competitions/2025
- The model's configuration and chat template: `mlx-community/Qwen3.8-27B-4bit`, read locally
- The claim that Qwen3.6 27B shares the configuration is from a secondary write-up and is checked in investigation 3

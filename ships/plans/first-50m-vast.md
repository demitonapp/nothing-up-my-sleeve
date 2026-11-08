# The first 50m: a Table Talk ship, sailed on Vast.ai

Written 2026-11-08 13:22, from Justin: "I'd like to run my first 50m ... on vast.ai but its goals are more table
talk goals than beating Qwen 4B. I'd like it to still record all the logic deck and cards ... I want the first
true Thorp model whereby I can have a conversation. So we'll need to test the Nvidia on Vast and then after that
tests then train the 50m."

Three parts, in order: **A**, prove the NVIDIA path on Vast; **B**, build what Table Talk still lacks; **C**, sail
the 50m. A and B don't depend on each other and can run side by side.

## Where things stand

| piece | state | where |
|---|---|---|
| PyTorch model and training loop, matching MLX (logits to about 1e-5, evaluators to 2e-3, checkpoints load either way) | built, checked on CPU torch only | branch `torch-backend`: `models/gpt_torch.py`, `train_torch.py`, `models/ops.py`, `backend/CUDA.md` |
| The charter: hire a Vast GPU, fit it out, sail, bring checkpoints and ledger rows home every 20 minutes, release | built, tested against a fake market only | branch `torch-backend`: `thorp charter quote\|sail\|audit\|terms` |
| The charter's terms | adopted: $10 a voyage, $30 a week, RTX 4090 at most $0.50/h, H100 SXM $2.60, verified hosts, one ship out | DECISIONS.md on that branch, "The charter" |
| Merging `torch-backend` into the working branch | **in progress in another session** (`Thorp-parity` worktree, conflict on DECISIONS.md) | — |
| Named data stages | built | `data.stages`, `thorp/data.py` |
| The table, with the blank-line stop | built | `thorp/table.py`, the Table tab |
| Readings the 50m keeps: logic, logic40, crowns, stars, nevermore, cards, shapes, pips | built (crowns new today) | `thorp/evaluators/` |
| Dialogue library for the conversation stage | **not built; needs your approval** | — |
| Turn converter (plays, dialogues, catechisms into turns) | **not built** | — |
| Table Talk's checks: turn-taking, on topic | **declared, no evaluator** | `fleet.VOYAGES["table_talk"]` |
| The shakedown spec and the 9m torch twin (part A) | **not written** | — |
| The 50m spec | **not written** | — |

## Decisions

1. **Decided (DECISIONS.md, "The first 50m is a Table Talk ship"):** this replaces the 12:45 plan. The first
   50m's aim is the first Thorp you can talk to, sailed on Vast. The logic deck, the cards and the crowns are
   still read, but they aren't the verdict.
2. **Decided, same entry ("No, just record it"):** the 21m (`fu-ogden-v0-2~deck@21m-pre-s1`) sails as
   pre-registered, and its 12-of-15 reading against Qwen3 4B is recorded. The 50m borrows its reading recipe
   but doesn't wait on its verdict.
3. **Open: the dialogue library** (part B1). Either the dialogue books clear the Ogden rule, or you set a
   separate bar for dialogue.

## Part A: prove the NVIDIA path on Vast

Do this once the `torch-backend` merge lands on the working branch.

### A0. Once, on the Mac

```bash
uv sync --project backend --group torch
```

- Put about $20 of credit on the Vast account (the terms want credit covering a quote 1.25 times over).
- Write the API key to `data/secrets/vast-api-key` (never committed, never carried aboard), or export
  `VAST_API_KEY`.
- Add your SSH public key in Vast (Account → SSH Keys).
- Read the terms:

```bash
uv run --project backend thorp charter terms
```

### A1. The parity test on a real GPU (manual box, about 15 minutes, under $0.50)

The torch path has never run on CUDA. Hire one RTX 4090 by hand in the Vast console (Ubuntu 22.04 or later,
CUDA 12.8 or later), then on the box:

```bash
git clone <the repo> thorp && cd thorp && git checkout <the merged branch>
cd backend && uv sync --group torch
uv run --group torch python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name())"
THORP_DEVICE=cuda uv run --group torch pytest tests/test_torch.py -q
```

**Pass:** CUDA is available, and `test_torch.py` passes on the GPU (logits and every head's attention match MLX
to about 1e-5; bf16 needs an Ampere or later card, so a 4090 is fine). Destroy the box afterwards.

### A2. The charter's shakedown (about 10 minutes)

**First, write the shakedown spec.** The obvious one, `smoke-10` (a 9m reading 3.3M tokens), is refused by the
gate: it reads neither the stores nor a fitout (checked 13:22). `data.passes` is a whole number, so the voyage is
made short by its library instead:
- the 9m on about 20 books of Ogden v0.1, one pass;
- `fitout: ogden-v0-1` with a `shakedown` variation;
- `data.opt_in` saying it's a shakedown.

`charter quote` runs the gate here on the Mac, so a refusal shows up before anything is hired.

```bash
uv run --project backend --group torch thorp charter quote ships/specs/fitouts/fu-ogden-v0-1~shakedown@9m-pre-s1.yaml
uv run --project backend --group torch thorp charter sail ships/specs/fitouts/fu-ogden-v0-1~shakedown@9m-pre-s1.yaml --gpu "RTX 4090"
uv run --project backend thorp charter audit
```

**Pass:**
- the charter hires, fits out, sails, brings the rows home into this Mac's ledger, and releases;
- the audit shows nothing left out, and `data/charter-log.jsonl` has the hire and release with their cost;
- the two points the code left open are settled: how Vast spells the GPU name, and the credit field.

### A3. The 9m twin: does a CUDA voyage match an MLX one? (the $100 bet's first gate)

The bet's gates start with "the PyTorch backend matches MLX at 9m". Write a twin of the finished Mac voyage
`fu-ogden-v0-1@9m-pre-s1` with `model.backend: torch` (which gives it a new run id), then sail it:

```bash
uv run --project backend --group torch thorp charter sail ships/specs/fitouts/fu-ogden-v0-1@9m-pre-s1-torch.yaml --gpu "RTX 4090"
```

- **Pass:** its Forgotten Tomes score is within 0.02 bits per byte of the MLX voyage's, and its cards land
  within the spread of the two MLX seeds. The second seed, `fu-ogden-v0-1@9m-pre-s2`, is in the Mac's queue.
  Torch starts from different random weights, so it's judged against seed spread, not to the digit.
- **Also check:** score one of its checkpoints on the Mac (`thorp eval`) and compare with the box's own rows
  (to within 2e-3).
- **What this measures:** the 4090's real tokens a second. From then on the charter quotes the 50m from that
  rate, not a guess.

If A1 to A3 pass, the NVIDIA path is proved.

## Part B: build what Table Talk lacks (on the Mac, while A runs)

### B1. The dialogue library (your approval)

Ogden v0.2 (1,380 books, about 92M words) holds only about 23 books that look like dialogue: Luther's and the
Baltimore catechisms, one volume of Plato's dialogues, Synge's *The Well of the Saints*, *Dolly Dialogues*, and
a few others. The 7 November count of eligible dialogue on Gutenberg was 1,224 plays, 61 philosophical
dialogues, 24 catechisms and 77 books of table talk. Nobody has measured how many of those clear the Ogden bar.

- **To build:** score those books for Ogden-ness as v0.2 was scored, and show you the list.
- **Your call:** the same bar, or a separate bar for dialogue. Strike any you don't want (as the Bible was
  struck).
- **For the crowns** (DECISIONS.md, "The crowns"): include dialogues that question the premise (Plato,
  Berkeley, Hume), not only catechisms. Catechisms teach one authority's fixed answer.

### B2. The turn converter (to build)

Turn each kind of book into the table's turn format:
- **Catechisms:** "Q." and "A." lines become "Q:" and "A:".
- **Socratic dialogues:** alternating speakers become turns.
- **Plays:** keep the scene heading and the speaker's name. That's how the asker's standpoint (the crowns)
  reaches the model.

Each turn ends at a blank line, matching the table's new stop. Exchanges are held out for the checks in B4.

### B3. The stages (the code exists: `data.stages`)

1. **Reading:** Ogden v0.2 with the 21m's full-deck scaffold, copy tack and release, scaled to 12 layers. About
   four passes, roughly 0.48B tokens: about 12 tokens a parameter for the 50m's 38.8M parameters. Chinchilla's
   20 would need six-plus passes, and passes past four count for less.
2. **Dialogue:** the converted turns, about 10% of the reading's tokens.

The checkpoint at the boundary between the stages is the reading-only twin. That gives Table Talk's
"no worse on the Forgotten Tomes" check without a second voyage.

### B4. Table Talk's checks as evaluators (to build)

Write them before the voyage, with the marks pre-registered on 7 November:
- **`turn_taking`:** on held-out exchanges, it opens the next "Q:" itself at least 80% of the time. Only
  stops at a "Q:" count; the table's blank-line cut doesn't count as the ship handing back the turn.
- **`on_topic`:** its answers share the question's words more than a shuffled pairing does, beyond the seeds'
  spread.
- **The Forgotten Tomes:** no worse than the boundary checkpoint by more than 0.05 bits per byte.
- **The crowns:** read as built. `ask` is the reading Table Talk cares about. Its fifth check, framed questions
  at the table, comes only if the crowns are performed.

### B5. The spec and its pre-registration

`ships/specs/fitouts/fu-ogden-v0-3~table-talk@50m-pre-s1.yaml`:
- Built from `fu-ogden-v0-2~deck@21m-pre-s1.yaml`, with preset `50m`, `model.backend: torch` and the two stages.
- Evaluators: ce_bpb, logic, logic40, crowns, stars, nevermore, cards, shapes, pips, turn_taking and on_topic.
- **Readings less often than on the Mac:** full every 1,024 steps and light every 256. The 21m reads every 640
  and 64; at that rate the readings, not the training, would fill the hired hours.
- Pre-register in DECISIONS.md: the aim, the checks and marks, and what is only recorded (the logic deck, the
  cards, the crowns against Qwen3 4B's readings).

## Part C: sail the 50m

```bash
uv run --project backend --group torch thorp charter quote ships/specs/fitouts/fu-ogden-v0-3~table-talk@50m-pre-s1.yaml
```

- **If the quote is under $10:** sail it.

  ```bash
  uv run --project backend --group torch thorp charter sail ships/specs/fitouts/fu-ogden-v0-3~table-talk@50m-pre-s1.yaml
  ```

- **If it's over $10:** the terms refuse the hire. Choices:
  - fewer passes;
  - sparser readings;
  - raising the per-voyage cap in `data/charter.json`, which is a change to the terms and gets its own
    DECISIONS entry.
- **While it sails:**
  - checkpoints and rows come home every 20 minutes;
  - `thorp charter audit` shows the spend;
  - if the ship is lost, sailing again resumes from the last checkpoint;
  - the box is released at its quoted hours × 1.5.

Run the charter from its own terminal. It doesn't take the Mac's helm, so the Mac's queue (the 21m) keeps
sailing beside it.

## When it docks

- **Talk to it:** the Table tab (`#/expeditions/table_talk/table`, sailing
  `fu-ogden-v0-3~table-talk@50m-pre-s1`). Restart `thorp dash` first if it predates the blank-line stop.
- **Read the checks:** turn-taking, on topic, and the Forgotten Tomes against the boundary checkpoint.
- **Read what was recorded:** the logic deck and logic40 (the chaining gain against +0.10), the 16 cards against
  Qwen3 4B, and the crowns (`gain`, `moves`, `ask`).
- **Write it up:** DECISIONS.md, as every voyage is.

**Expect (from Table Talk's own entry):** period English, mostly grammatical, answering in turn, often loosely on
topic, with no reliable knowledge and no memory past its 1,024-piece window (about 775 words, roughly 20 short
exchanges). It would be the first Thorp shaped to converse; it won't be a good conversationalist.

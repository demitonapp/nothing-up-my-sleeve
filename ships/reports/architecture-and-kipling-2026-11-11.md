# The architecture audit and the Kipling review

Report for Justin, 11 November 2026. Three readers went through the store and coordinator, the training path,
and the dashboard, read-only, while `1m@v0.0.6-early` was at sea. Items marked **checked** were re-read against
the code by the session that wrote this; the rest stand as the readers reported them. Line numbers are as of
about 14:00 and drift: two other sessions were editing `server.py`, `train.py` and `fleet.py` the same hour.

## Part 1 — What will stop Thorp scaling

### The programme (Justin, 11 November: "we need to do 1 - 7 and then 9, 10 and 11")

Items 8 (the dashboard's open port) and 12 (backup and tests) are not in the programme. They are kept below so
the decision is visible.

| # | Weakness | In the programme | Built (11 November, night) |
| --- | --- | --- | --- |
| 1 | The two trainers have drifted | yes | built: refusal allow-list, the gaps closed, twin-leg parity |
| 2 | A coordinator death loses voyages; a hired voyage hangs on this Mac | yes | built: `s2.at_sea`, own process groups, `charter attach` |
| 3 | A run id does not pin what was trained | yes | built as provenance beside an unchanged id |
| 4 | The metrics table will not survive 10x | yes | built: buffered writes, incremental atomic fold |
| 5 | Evaluators run inside the training loop | yes | built: per-evaluator times, `eval.offline` + `thorp score`, greedy KV cache |
| 6 | The Postgres cut-over is half done | yes | built: queue from the store only, library on Postgres, no silent fallback |
| 7 | Dashboard endpoints loop over every run | yes | built: `s1.metric_latest`, set-based readers |
| 8 | The dashboard listens on every interface with no login | no | — |
| 9 | The outside-model tooling cannot read Qwen3.8 27B | yes | built: `thorp/hooked.py`, real layer indices |
| 10 | The data stream rebuilds the corpus in RAM; checkpoints are never pruned | yes | built: memmap windows, retention, SIGTERM checkpoint |
| 11 | Expeditions, lanes and run status are hard-coded | yes | built: `expedition:`, `s2.lane_defs`, `s1.run_state` |
| 12 | No Postgres backup found; restart, fold and API payloads untested | no | — |

What was built, what it measured and what is still open is in DECISIONS.md, "The architecture programme,
built". Nothing of the coordinator's own changes is live until it is restarted in port.

**What can start while a voyage is at sea.** Items 1, 5, 7, 9, 10 and 11 change code a running trainer has
already loaded, or code it does not use; they are safe on a branch at any time. Items 3, 4 and 6 change what a
run id is, how metrics are written and which store answers. The standing rule is never to cut over while a
voyage is at sea, and a change to the id rule makes finished voyages look unsailed. They need an empty sea and
a migration plan. Item 2 changes the coordinator, which only takes effect at its next restart.

### 1. The two trainers have drifted (**checked**)

- Only the pure-Python schedule helpers are shared. The loss terms, seeding, teaching, transplanting and the
  whole loop are typed twice (`train_torch.py:218-335` against `train.py:569-782`; `train_torch.py:492-864`
  against `train.py:935-1421`).
- The PyTorch trainer ignores, with no error: per-head `hold/fade/floor/release` (`train_torch.py:295-307`
  takes no weights), teacher-head targets, shared key/value heads (`train_torch.py:78-88` never passes
  `kv_heads`), and `sop_version` on the run row.
- At scale: every rung from 50m up sails on PyTorch, so a 50m built to SOP v0.0.6 trains a different
  objective and shape from its 21m twin under the same spec.
- Fix: first make the PyTorch trainer refuse any spec key it does not implement. Then move the loop skeleton
  into one driver that calls a small per-backend `step()` and `state()`.

### 2. A coordinator death loses voyages; a hired voyage hangs on this Mac (**checked**)

- A queue line is deleted before launch and history is written only when the coordinator sees the exit
  (`lanes.py:695`, `:706`, `:656`). What is at sea lives in the coordinator's memory.
- Children are started in the coordinator's own process group (`lanes.py:599-606`), and the launchd job has no
  `AbandonProcessGroup`. Not tested: that launchd then kills the trainer with the job.
- A hired box is released after ten unanswered one-minute polls, and at the overrun deadline "whatever its
  state" (`s1_operations/charter.py:504-523`). The release in `finally` does not run on SIGTERM, so the box
  keeps billing.
- Fix: an `at_sea` row per launched line, adopted on restart; children in their own session; a resumable
  `charter attach`; never release a box on a Mac-side timeout.

### 3. A run id does not pin what was trained (**checked**)

- The id hashes list paths, not list contents (`train.py:58-68`), and `load_spec` adds the ladder's evaluators
  before hashing (`train.py:40-45`), so adding one evaluator changes the id of every Ogden and Kipling spec.
- The coordinator hashes the raw YAML, the trainer the altered one: `1m@v0.0.6-early` is `221018fb…` in the
  queue and `dfdeefeb…` in the ledger.
- 177 of 180 runs carry a `-dirty` commit. 22 names are reused. Seeds, teachers and donors resolve to "the
  newest finished run with that name" (`train.py:351`, `:398`, `:430`).
- Fix: resolve the spec once (ladder, SOP, parent run ids, list hashes) into a frozen document, hash that,
  store it at queue-add time and hand the trainer the stored id.

### 4. The metrics table will not survive 10x

- 16.35M rows for 197 runs; 3.1 GB of heap and 4.7 GB of indexes. One insert and one commit per training step
  (`train.py:1372`, `ledger_store.py:452-456`), with no retry.
- A 1m run carries 1,213 metric names, 619 of them per-book losses.
- The fold from a hired box deletes and re-inserts every row of the leg every 20 minutes
  (`s2_coordination/charter.py:113-123`), in three separate transactions.
- Fix: buffer trainer writes; move per-book and per-head series to one row per step; a per-run "latest value"
  table; fold incrementally by rowid in one transaction.

### 5. Evaluators run inside the training loop

- 12 evaluators are forced onto every Ogden and Kipling spec (`ladder.py:14-27`). Generation is one full
  forward pass per token at batch 1 (`evaluators/samples.py:38-45`).
- Measured from the ledger: 39% of the 50m reading stage's hired wall time, 80% of the PyTorch 9m parity run,
  10% of the MLX `21m@v0.0.5`.
- Fix: keep `ce_bpb` and the cheap attention readings in the loop; score the rest from checkpoints offline
  (`train.rescore` already does it for the latest checkpoint); add a cached, batched `generate`.

### 6. The Postgres cut-over is half done (**checked**)

- The store is chosen per process by env flags with three different defaults: ledger and queue default to
  Postgres, the library to SQLite (`manifest.py:73-75`).
- The fitout builder and the Navigator's Wager still write `ships/specs/queue.txt` (`fitouts.py:289-299`,
  `wager.py:534-545`), which the coordinator no longer reads. About ten readers still read that file,
  including the queue lint and the audit (`vsm.py:938`, `:1046`, `:1059`, `:1123`).
- `data/manifest.sqlite` has 12,791 books; `s1.books` has 12,790.
- Fix: one `queue.pending()` and `queue.add()` over the store; delete the file readers and writers; make the
  library Postgres-only; rename the SQLite files `.imported`.

### 7. Dashboard endpoints loop over every run

- Measured at 197 runs: `/api/ships` 40 s, `/api/compare` 37 s and 27.5 MB, `/api/bridge` 37 s. Each does a
  prefix-`LIKE` over a run's whole metric history, per run (`server.py` `_last_scores`,
  `ledger_store.py:677-687`).
- `/api/metrics` returns 16 MB for one run; the ship page polls `/api/runs` every 5 s.
- Six hand-rolled caches hide it elsewhere, with refresh failures swallowed.
- Fix: the "latest value" table from item 4; `ship_key`, `expedition` and `preset` as columns on the run;
  one set-based query per endpoint; a point cap and `names=` on `/api/metrics`.

### 8. The dashboard listens on every interface with no login (**checked**; not in the programme)

- It binds `::` with V6ONLY off (`server.py`, `_DualStack`). POSTs replace the Vast key and queue voyages with
  no Origin check; `/api/hulls/save` and `/api/lanes/slots` write on a GET.
- Fix: bind loopback only; make every write a POST; reject a foreign Origin.

### 9. The outside-model tooling cannot read Qwen3.8 27B (**checked**)

- The only hook is one monkey-patch of mlx-lm's attention function, with process-global state (`inside.py`).
  It is MLX-only and its only ablation is zeroing a head.
- On the 27B it sees only the 16 full-attention layers, returns them indexed 0–15 when their real layers are
  3, 7, 11, …, and draws random controls from all 64 layers, so most controls do nothing.
- The silenced "layer" is a call counter reset only in `Inside.__call__`; generation through
  `mlx_lm.batch_generate` never resets it, so a knockout over generated text silences the wrong head after the
  first pass. From reading the code, not from running it.
- `math_heads.py` and `head_causal.py` hard-code Qwen3 4B's 36 × 32.
- Fix: one hooked-model with a single loader, hooks by real layer index, a capability flag per layer type, and
  ablation applied inside the block. The DeltaNet instrument (`thorp/deltanet.py`, 11 November) is the first
  piece of it.

### 10. The data stream rebuilds the corpus in RAM; checkpoints are never pruned

- `Stream._pass` concatenates every book into one int32 array plus a per-token owner array (`data.py:106-112`):
  about 8 bytes a token, 14 at peak. The 32 GB Mac's ceiling is about 1.5–2B tokens.
- Every `step-N` checkpoint is kept (`train.py:282-294`): about 650 GB for a 100k-step 350m run.
- Neither trainer handles SIGTERM, so a preempted box loses up to 640 steps.
- Fix: per-book memmaps and a prefix-sum, shuffling window indices only; keep the last K checkpoints and the
  milestones; a SIGTERM handler that checkpoints.

### 11. Expeditions, lanes and run status are hard-coded

- Expedition membership is a prefix if-chain on a free-text label (`fleet.py`, `expedition_of_label`); an SOP
  v0.0.7 voyage lands in Ogden. Expeditions are a 2,500-line Python dict.
- `LANES = ("mac", "vast")` with a database CHECK to match; a third lane is a migration.
- `s1.runs.status` holds 11 distinct strings, some of them prose; a signal leaves a run `running`.
- Fix: an `s1.expeditions` table and an explicit `expedition:` field on every spec (the investigation specs
  added on 11 November already carry one); lanes and seats as rows; a status enum with a reason and a heartbeat.

### 12. No Postgres backup found; restart, fold and API payloads untested (not in the programme)

- No `pg_dump` or backup script in the repository; the only store is `data/postgres` in the working tree.
- Tests name 5 of 110 API functions; nothing tests coordinator restart, the fold, or a failed parent.

### Sound; leave alone

Deterministic stream and resume; the portable checkpoint format; the gate failing closed; flock locks on one
machine; Alembic schemas; `models/ops.py` as the one evaluator seam; Postgres as the one store; the
`discoveries_store` pattern (a materialised document, 0.09 s for 3 MB).

## Part 2 — Kipling: 14 finished voyages of 32 started

Final readings from `s1.metrics`. Chaining is the mean lift on the four chaining tests; its noise band is 0.03.

| Voyage | bpb | chaining | one-hop | comparator | induction | duplicate | number |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 300k control (marks in the text) | 1.958 | 0.160 | 0.189 | 0.997 | 0.344 | 0.004 | 1.4 |
| 300k control, seed 2 | 1.968 | 0.057 | 0.039 | 0.998 | 0.339 | 0.004 | 1.3 |
| 300k ten pins | 1.908 | −0.003 | 0.187 | 1.000 | 0.288 | 0.445 | 98.0 |
| 300k ten pins, seed 2 | 1.876 | 0.013 | 0.167 | 1.000 | 0.284 | 0.490 | 97.9 |
| 300k shared KV heads | 1.929 | −0.001 | 0.234 | 1.000 | 0.348 | 0.005 | 1.3 |
| 300k shared KV heads, seed 2 | 1.930 | −0.033 | 0.064 | 1.000 | 0.390 | 0.004 | 1.1 |
| 300k release | 1.904 | 0.012 | 0.128 | 0.108 | 0.145 | 0.004 | 1.1 |
| 300k release, seed 2 | 1.878 | 0.025 | 0.114 | 0.074 | 0.094 | 0.005 | 1.2 |
| 300k release, induction's own fade | 1.909 | 0.014 | 0.109 | 0.100 | 0.211 | 0.004 | 1.1 |
| 300k ten pins released | 1.863 | 0.005 | 0.051 | 0.345 | 0.077 | 0.011 | 2.6 |
| 300k four Faces | 1.902 | −0.051 | 0.174 | 0.998 | 0.242 | 0.004 | 98.0 |
| 1m full deck | 2.109 | −0.011 | 0.098 | 0.998 | 0.068 | 0.365 | 12.5 |
| 300k deck as content, marked (v0.0.7) | 5.350 | −0.020 | 0.087 | 0.931 | 0.005 | 0.005 | 1.5 |
| 300k deck as content, plain (v0.0.8) | 8.097 | −0.106 | 0.052 | 0.325 | 0.005 | 0.005 | 1.1 |

### The five most promising

1. **Control tokens in the text are the only arm with chaining above the noise**: 0.160 and 0.057. Every other
   300k arm is within ±0.05 of zero. It has the worst bits per byte of the 300k arms and its two seeds differ
   by 0.10, so it needs a third seed. (The Kipling session found the same day that declared control tokens were
   never passed to the tokeniser, so this arm's markers were split into byte pieces; the reading is of that.)
2. **Ten pins hold for a whole voyage at no cost to language.** Number, order and premise read about 98, 108
   and 105 against about 1.2 unpinned; duplicate-word 0.45–0.49 against 0.004; both seeds agree.
3. **Releasing the pull buys language.** The released ten-pin arm has the best bits per byte (1.863) and the
   best keyed top-1 (0.212).
4. **Shared key/value heads keep the cards.** Comparator 1.000, induction 0.35–0.39 (the highest of any arm),
   at 1.929. No matched base has finished.
5. **The Bridge is reachable at 1m.** The riddle pulled it to 0.977 at 15% of the voyage, and the comparator
   survived the release at 0.998.

### The five most disappointing

1. **Chaining, the fleet's goal, did not move.** Ten of twelve Ogden-reading voyages are within noise of zero;
   the 1m with twelve cards reads −0.011.
2. **The 1m is worse at language than the 300k**: 2.109 against 1.86–1.93. The hard release at 60% dropped
   number from 86.8 to 12.5, order from 127 to 41.7, premise from 109.6 to 9.7, and the Bridge to 0.039.
3. **The weights do not keep what the pull put there.** After release the comparator falls from 1.000 to
   0.07–0.11, induction to 0.08–0.21, duplicate-word to 0.011.
4. **The headline aims have no reading.** IFEval was never read; the ARC arm and the 9m never sailed; the base
   `300k@v0.0.6` never finished; the 300k that read ARC skipped every task for length. The two
   deck-as-content arms read 24M and 39M tokens and never learned English, so marked against plain is
   unanswered.
5. **Seed noise swamps the arms.** One-hop lift reads 0.234 and 0.064 on the two shared-head seeds; three-hop
   reads −0.488 and +0.645 on the two control seeds. Single-seed 300k readings on a 40-item deck cannot rank
   arms.

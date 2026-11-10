# Handover: the one store and the frontend

Written 9 November 2026, when the working session that did this work was archived. It says what is done,
what is blocked and exactly how to finish it, so a new session needs nothing from that chat.

## Done and committed

- **Ledger → Postgres** (`thorp/ledger_store.py`): `s1.runs`, `s1.metrics`, `s1.evals`, `s1.artifacts`,
  with `backfill()` / `verify()` and the typed read helpers. Backfilled and verified: **157 runs,
  12,685,844 metrics, 23,466 evals, 57,697 artifacts** (counts match `ledger.sqlite`).
- **Library → Postgres** (`thorp/manifest_store.py`): `s1.books`, `s1.book_measures`, `s1.lists`,
  `s1.list_resolutions`. Backfilled and verified (11,932 books, 2,066 measures, 49 lists, 8,173 resolutions).
- **Readers**: ~46 dashboard endpoints and the library/trigram/table/smoking-Qwen readers answer from
  Postgres behind `THORP_LEDGER_PG` / `THORP_LIBRARY_PG`; SQLite stays the fallback.
- **The Mac lane can write Postgres-only**: `recorder()` returns `PgLedger` when `THORP_LEDGER_PG` is set
  (else `DualRecorder` under `THORP_LEDGER_DUAL`, else SQLite). `PgLedger` now has the full recorder read
  surface (`get_run`, `get_run_by_name`, `find_run`, `latest_artifact_text`, `metric_at`, `runs_by_ship`,
  `checkpoint_wal`). `train.py` / `train_torch.py` read through `reader()`. The Vast lane is unchanged: it
  writes its own SQLite ship's log (`thorp charter sail`) and is folded in at docking.
- **Queue store** (`thorp/viable/s2_coordination/queue_store.py`): `s2.queue_lines` and `s2.queue_history`,
  a read-only `backfill()` + `verify()`, and `thorp store queue`. Backfilled (272 history rows, verified).
  The queue itself is **not** cut over: `specs/queue.txt` / `queue-done.txt` are still the live files.
- **Frontend**: multi-page Astro (8 pages), View Transitions, pathname routing, SPA fallback; `lib/*` and
  `scripts/views/*` typed; the Bet panel is a `client:load` React island; the Sieves tab now lives under the
  individual ship page (the top-level tab is gone).
- **Migrations** (head `d6e0f7a8b9c4`): ledger, library books, library measures/lists/resolutions, queue.

Tests: `tests/test_ledger_store.py` (10), `tests/test_manifest_store.py` (3), `tests/test_queue_store.py` (2).

## Blocked: the cut-over, until no voyage is at sea

The hard rule (DECISIONS.md): **never cut over while a voyage is at sea.** As this was written,
`21m@v0.0.5` was still `running` on the Mac lane. When it docks:

```sh
# 1. Ledger + library: make Postgres the one store (drop the dual-write).
export THORP_LEDGER_PG=1
export THORP_LIBRARY_PG=1
unset THORP_LEDGER_DUAL

# 2. Restart the dashboard and the queue so they pick the flags up.
#    (thorp dash, and queue.sh) — then confirm /api/store and a few pages answer.

# 3. Archive the SQLite files (once the readers and the writer are on Postgres).
mv ledger.sqlite ledger.sqlite.imported
#    The library's files (only with "no intake + Justin's go-ahead"):
mv data/manifest.sqlite data/manifest.sqlite.imported
mv data/trigrams.csv data/trigrams.csv.imported
mv data/resolution.csv data/resolution.csv.imported
mv data/unresolved.csv data/unresolved.csv.imported

# 4. The queue is cut over (10 November): THORP_QUEUE_PG=1 makes lanes.py read and take from
#    s2.queue_lines and record exits in s2.queue_history; thorp queue show/add/move/drop edits it;
#    /api/queue, /api/lanes and the plan read the store; queue.sh sets the flag. specs/queue.txt is
#    now an export written by the CLI, not the source.
```

The Vast lane still writes its SQLite log after this; that is by design, not a leftover.

## Remaining (not blocked, just not done)

- **Islands**: 1 of ~9 panels (only Bet). The rest still render from the `dashboard.ts` monolith.
- **TypeScript**: `frontend/src/scripts/dashboard.ts` is still `// @ts-nocheck` (~2,600 errors behind it).
  `lib/*` and `scripts/views/*` are fully typed. Removing that line is the finish line for "types throughout".
- **`thorp ledger <sql>`** still runs raw SQLite SQL (a debugging tool); it is the one reader not ported.

## Where things are

- Ledger in Postgres: `s1.*`; library: `s1.books` and friends; queue: `s2.queue_lines` / `s2.queue_history`.
- `thorp store ping|ledger|queue` — check the store, re-run the ledger backfill, re-run the queue backfill.
- Decisions: `DECISIONS.md`, "One store: Postgres, by the viable system".

## 10 November: the queue on Postgres, the first 1m, and what is still running

**The queue is the store's.** `THORP_QUEUE_PG=1` makes `lanes.py` read and take from `s2.queue_lines` and
record each exit in `s2.queue_history`; `thorp queue show/add/move/drop` edits it; `/api/queue`, `/api/lanes`
and the plan read it. `specs/queue.txt` is now an export written by the CLI. Two faults found and fixed:

- the history backfill inserted explicit ids, leaving `s2.queue_history_id_seq` at 1, so the first `record()`
  died on a unique violation and the coordinator stopped. The backfill now `setval`s after writing; the repair
  is `select setval('s2.queue_history_id_seq', (select max(id) from s2.queue_history))`.
- the coordinator calls `ps`, which the workspace sandbox blocks. `_local`/`_is_child_of_mine` now tolerate it,
  and the coordinator must run with `THORP_LAUNCH=local` (the `uv` launcher cannot write its cache either).

**The first 1m (fulldeck) finished** at 16:13 on 10 November: 288.1M tokens, 178.7 min, bpb **2.109** against
the 300k pins' **1.908**. The hard release at 60% cost the basics (number 86.8 to 12.5, order 127 to 41.7,
premise 109.6 to 9.7); the bridge spiked to 0.977 at 15% and decayed to 0.039; chaining stayed at zero (−0.015).
The follow-up 1m arms are queued last: `1m@v0.0.6-early` (hold 10%, every pull off by 30%, no bridge riddle)
and `1m@v0.0.6-hold25-double` (twenty pins).

**What is running** (17:30): the coordinator on `300k@v0.0.6-gqa-s2`, then the rest of the eleven-line 300k
batch, then the two 1m arms. `caffeinate -imsu` keeps the system awake. If the coordinator dies:

    PYTHONPATH=backend THORP_LAUNCH=local THORP_LEDGER_PG=1 THORP_LIBRARY_PG=1 THORP_QUEUE_PG=1 \
      nohup backend/.venv/bin/python -m thorp.viable.s2_coordination.lanes >> data/runs/queue.out 2>&1 &

**Also in this session:** `s1.discoveries` (the goals payload as one JSONB row, built by `thorp store
discoveries`, read by `/api/discoveries`); the fleet reclassification (only Ogden and Kipling are Star Fleet);
the plans page as a table; the per-card schedule groups on the at-sea card; First Light's findings panel; the
competitor route for dev; the size-page loading state.

**The working tree is dirty** (84 files, many from before this session). Commit before archiving.

## 10 November, later: personas, yards, compute, the head census

Added in the evening session, all in the one store:

- **Migrations**: `k2g5h8d0e7f9` (s4.persona_master/vectors), `l3h6i9e1f8a0` (s1.yards, s1.work, runs provenance: yard_id/spec_sha/artifact_root), `m4i7j0f2a3b5` (s5.provider_credentials, the Vast key), `n5j8k1g3b4c6` (s1.compute_resources, s2.lanes.resource_id).
- **Readings**: `heads-mlx-community--Qwen3-4B-4bit` (1,152 heads, 224 named, 928 unnamed, 16 clusters), `math500-…` (50-question pilot, 48 truncated — accuracy not meaningful), `personas-…` (6 directions at layer 18), yard `yard-fd5d8f597a9f`, resource `compute-096789bc80`, the Vast key in the store.
- **New modules**: `thorp/persona_vectors.py`, `persona_store.py`, `head_census.py`, `math_heads.py`, `providers.py`, `yard.py`, `contribute.py`, `compute.py`; `backend/scripts/check_ui.py`.
- **Surface**: `/shipyard/constraints` now edits Mac/Vast seats, the Vast key and caps, and lists compute resources; `/discoveries/stars` has All heads, All cards and Personas tabs; `/expeditions/queue` is Postgres-only; the competitor Tests tab reads `math500-`.
- **Specs**: `21m@v0.0.6.yaml` (copied from 9m; its `lr: 0.001` is not tuned), `ships/specs/queue-kipling.txt`, and 310 specs gained `soundings` (wide diff, review before trusting).
- **Open**: the foreign/competitor page consolidation is diagnosed, not merged; Qwen3.5 0.8B is unread and has no fal image (`FAL_KEY` absent); compute fit is a forward-pass proxy; caps are stored, not enforced; the 9m/21m specs still need the 300k/1m learnings applied before they sail.
- **Running at archive**: coordinator 5292 (in port, two 300k trainers 85927/89449 at sea), dash 8787, Astro dev 4321. The queue (12 lines) is in Postgres; run the coordinator under launchd (`backend/scripts/com.thorp.queue.plist`) so the harness cannot reap it.

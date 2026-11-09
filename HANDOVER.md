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

# 4. The queue (only in port, at a time agreed with Justin): make lanes.py read s2.queue_lines,
#    add thorp queue show/add/move/drop, then the dashboard can edit the queue.
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

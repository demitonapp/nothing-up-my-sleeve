# Storage audit — 12 November 2026

Disk: **926 GB**, **330 GB free**; `data/` is **74 GB**, the repository root's legacy `ledger.sqlite` is
**2.2 GB**. This is an inventory and a cleanup plan; the only deletions made so far are the safe caches
and duplicate archives listed under “Freed now”.

## Freed now (~1.3 GB)

| Removed | Size | Why safe |
|---|---:|---|
| `.uv-cache/` | 504 MB | uv's download cache; rebuilt on the next `uv` command |
| `.chrome-k`, `.chrome-lb2`, `.chrome-p` | 66 MB | old test profiles; the browser drone uses `data/browser-profile` |
| `.pytest_cache`, `.ruff_cache` | <1 MB | tool caches |
| `data/classics/*.zip` (3 archives) | 326 MB | the extracted `*-master/` trees are already there; the zips are only the download |
| `data/charter/c4c9…/stage`, `data/charter/909794…/stage` | 402 MB | staging copies for two runs that are finished/on the Mac; no charter is using them |
| `data/charter/c4c9…/box-ledger.recovered.sqlite` | 39 MB | duplicate of `box-ledger.sqlite`; the original malformed copy is kept |

`data/` is now **74 GB**; free space is **330 GB**.

## The big consumers

| Path | Size | What it is |
|---|---:|---|
| `data/checkpoints` | **31 GB** | 186 run checkpoint directories; the single largest reclaimable pool |
| `data/models` | **22 GB** | downloaded outside models: Fara 9B/4B, PersonaPlex, Ling, Qwen |
| `data/postgres` | **8.9 GB** | the live store (ledger, queue, fitouts, library) |
| `data/texts` | **4.3 GB** | the books themselves |
| `data/shards` | **3.5 GB** | tokenised training shards |
| `data/catalogue` | **2.3 GB** | catalogue caches, mostly `catalogue/hf/blobs` (2.1 GB) |
| `ledger.sqlite` (root) | **2.2 GB** | the old SQLite ledger; the live ledger is Postgres |
| `frontend/node_modules` | **1.8 GB** | needed for `pnpm dev`; do not delete |
| `.pnpm-store` | **1.6 GB** | hard-linked into `node_modules`; deleting it without reinstalling breaks packages |
| `data/classics` | **1.3 GB** | extracted Greek/Latin repositories |
| `backend/.venv` + `.venv` | **2.5 GB** | the running environments |
| `data/charter` | **449 MB** | charter artifacts and the current stage (407d, 201 MB) |
| `data/manifest.sqlite` | **201 MB** | SQLite manifest; the live library is Postgres |
| `data/browser-profile` | **131 MB** | the browser drone's signed-in Chrome profile; keep |
| `data/runs` | **186 MB** | run logs (a few old logs are 15 MB each) |

## Best next candidates

### 1. Old checkpoints — up to ~15 GB without touching current runs

The largest directories, with their run status:

| Run | Size | State |
|---|---:|---|
| `c353647d…` `fu-ogden-v0-2~table-talk-reading@50m-pre-s1` | **9.8 GB** | finished 8 Nov — the first 50m; keep or archive |
| `55eec445…` `21m@v0.0.5` | 1.7 GB | finished 9 Nov — the latest 21m; keep |
| `e5e82e73…` 21m metre | 1.6 GB | finished 7 Nov |
| `cdc3da85…` 21m | 1.6 GB | finished 7 Nov |
| `9f51face…` 21m sop001 | 1.6 GB | finished 8 Nov |
| `048346fa…` 9m staged | 1.2 GB | finished 8 Nov |
| `0099f15f…` `50m@v0.0.5` | 0.97 GB | `chartered: overran` — never trained |
| `6b00313e…` 9m converse | 0.73 GB | finished 11 Nov |
| `1fed7774…` 9m talk | 0.69 GB | finished 11 Nov |
| `c1317c70…` 9m talk-hot | 0.69 GB | finished 11 Nov |
| `136246a7…` 9m | 0.57 GB | finished 11 Nov |
| `c4c9cbd6…` bridge | 0.54 GB | finished today; keep |
| 9m/1m/300k older arms | ~0.4–0.5 GB each | many, finished |

**Safe first pass (~6.5 GB):**
- Delete the three superseded 21m checkpoints (`e5e82e73…`, `cdc3da85…`, `9f51face…`) — **~4.9 GB**, keeping `55eec445…`.
- Delete failed/abandoned runs: `0099f15f…` (0.97 GB), `e892af0d…` (0.29 GB), `c596b5bf…` (0.22 GB), `dfdeefeb…` (0.16 GB), and the small killed/stopped 300k/1m dirs — **~1.7 GB**.

**Second pass (~8–10 GB):** cull the older 9m/1m/300k arms, keeping the latest of each class, the best
leaderboard reading, the runs referenced by queued specs (`seeded_from`, transplant, teacher), and the
current `909794…` (Mac 9m), `407d0a89…` (Vast gqa) and `c4c9cbd6…` (bridge). The 9.8 GB 50m is the
single biggest model: archive it if you may want its checkpoints again, delete only if the 50m has been
superseded and you do not need to re-score or chat with it.

Do **not** delete checkpoint directories while their run is at sea or while a queued spec reads them.

### 2. Downloaded models — 22 GB, but active

| Model | Size | Used by |
|---|---:|---|
| `fara-1.5-9b` | 6.4 GB | browser drone pilot |
| `personaplex-edge-q4` | 5.4 GB | phone drone live voice |
| `ling-3.0-tiny-oq4e-mlx` | 4.3 GB | chat console |
| `fara-1.5-4b` | 3.3 GB | browser drone pilot |
| `qwen3.5-4b-instruct` | 2.6 GB | chat / model pages |

These are re-downloadable, but deleting them breaks the feature that uses them until re-downloaded.
Keep unless you have retired that drone/chat.

### 3. Re-downloadable caches and legacy copies

- **`data/catalogue/hf/blobs` — 2.1 GB.** Hugging Face dataset cache; safe to delete if you are not
  gathering from those datasets soon. It will re-download.
- **Root `ledger.sqlite` — 2.2 GB.** The old SQLite ledger; Postgres is the live ledger. Archive it
  (gzip to `data/archive/`) rather than deleting it if you want the history. Do not remove it while
  `THORP_LEDGER_PG=0` is in use.
- **`data/manifest.sqlite` — 201 MB.** The SQLite book register; Postgres is the live library. Archive
  it if you do not need the fallback.
- **`data/postgres` — 8.9 GB.** Not a deletion candidate; a `VACUUM (ANALYZE)` may reclaim some bloat,
  but it will not free much and it takes a lock. Leave it while the queue runs.
- **Current `data/charter/407d…/stage` — 201 MB.** Can be removed once the gqa hire is home.

## Do not delete

`data/texts`, `data/shards`, `data/catalogue` (unless the HF cache above), `data/postgres`,
`data/browser-profile`, `.pnpm-store` (hard-linked into `node_modules`), the `.venv`s,
`frontend/node_modules`, and the current/queued-run checkpoints.

## Recommended order

1. Delete the failed/abandoned checkpoints (~1.7 GB).
2. Delete the three superseded 21m checkpoints (~4.9 GB), keeping the latest.
3. Archive the old 50m checkpoints (9.8 GB) if not needed for re-scoring/chat.
4. Archive root `ledger.sqlite` and `data/manifest.sqlite` (~2.4 GB) if the Postgres store is trusted.
5. Delete `data/catalogue/hf/blobs` (2.1 GB) if no gather is planned.
6. Cull older 9m/1m/300k arms (~8–10 GB), keeping the latest per class and every run a queued spec reads.
7. Leave models alone unless a feature is retired.

That gets back roughly **6–20 GB** depending on how much checkpoint history you want to keep.

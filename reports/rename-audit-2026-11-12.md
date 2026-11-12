# Thorp → Nothing up my sleeve: what is still left

Audit of the repository on 12 November 2026. Scope: versioned text and current runtime stores. Excluded:
`.git`, `.venv`, `node_modules`, `.uv-cache`, `.pnpm-store`, `data/texts` (real books), and binary files.

The short version: **the live UI source is almost clean**; the remaining work is mostly
**generated library metadata, old ship/fitout labels, and docs**. The lowercase `thorp` code
namespace is a separate, much larger decision.

## At a glance

| Surface | Remaining | Risk | Recommendation |
|---|---:|---|---|
| Live React UI strings | 2 | low | replace now |
| UI standard (`backend/thorp/dash/UI.md`) | 27 lines | low | replace now |
| Living plans | 16 | low | replace now, except historical section names |
| Versioned SOPs & dated plans | 10 | none | keep as written (unless retroactive policy) |
| Historical reports | 7 | none | keep as written |
| `DECISIONS.md` | 82 lines / 106 occurrences | none | keep; add a new rename-scope entry |
| Library author metadata | 660,432 rows, 6 brand strings | high | data migration, not find/replace |
| Fitout/ship labels | 108 spec YAMLs, 6 fitout JSONs, 38 ship names, 36 run labels | high | migrate or display-alias |
| Runtime caches | 237 occurrences in 4 files | low | regenerate/invalidate |
| Generated static build | 10 occurrences | none | rebuild after source fix |
| Stale root `thorp/dash/static` | 53 occurrences | none | delete as dead build output |
| Code/deployment namespace (`thorp`, `THORP_*`) | 3,991 lowercase + 360 env-var occurrences | high | separate alias-first migration |

## Already clean

- `README.md`, `HANDOVER.md` and `backend/README.md` have no capital-`Thorp` product references.
- The leaderboard’s naming code already uses “Nothing up my sleeve 300k v1”
  (`backend/thorp/leaderboard.py`), and most backend docstrings already say “Nothing up my sleeve”.
- The live queue/Liberty Machine page copy is already the new name except for the two React strings below;
  any old “Fitout: Thorp” text on a queue card is a data label (§3), not a UI string.

## 1. Safe product-copy fixes (do first)

These are live or developer-facing strings with no data identity behind them.

- `frontend/src/components/islands/Governance.tsx:92` — “how Thorp governs itself” →
  “how Nothing up my sleeve governs itself”.
- `frontend/src/components/islands/LibertyMachineCycle.tsx:261` — “a job on Thorp's own schedule” →
  “a job on Nothing up my sleeve's own schedule”.
- `backend/thorp/dash/UI.md` — 27 occurrences, including the title “Thorp dashboard: UI and UX
  standards”. Several are shorthand in a developer doc (“Thorp `--muted`”, “Thorp component”,
  “Thorp's own”); a blind replace reads badly, so prefer “the app” or “our” in those places and
  the full name in headings.
- `backend/thorp/dash/cost.py:4` — docstring “The money Thorp spends”.
- `backend/thorp/viable/s3_control/cycle.py:36,301` — “Thorp's own schedule”.
- `backend/thorp/dash/server.py:6117,6118,6182` — “Thorp run / Thorp model” in the chat API
  docstrings.
- `backend/box/Dockerfile:8,12` — “installs Thorp itself”, “no Thorp code”.
- `.github/workflows/box-image.yml:47` — OCI description “Thorp's box”.
- `ships/plans/corpus-ceiling.md` — 11 occurrences; update the prose (`Thorp's S5 policy`,
  `Thorp's tokeniser`, `Thorp's fetcher`, `reach Thorp`, `Thorp cannot lawfully fetch`), but keep
  the quoted references to the historical DECISIONS section “Thorp against Qwen” until that
  section is renamed.
- `ships/plans/first-50m-vast.md` — 4 occurrences; update the prose. Keep the
  `Thorp-parity` worktree name in the table: it is a real directory name, not brand copy.
- `ships/plans/arc-de-triomphe.md:62` — “Thorp's cards”.
- `ships/plans/sop-v*.md` — the titles read “Thorp Ship SOP v…”. These are versioned historical
  standards; update only if the policy is that old standards are renamed retroactively. New
  standards should use the new name.
- `ships/plans/sop-v0.0.1.md:141` — the naming convention `Thorp <size> v<n>`.

After these, rebuild the static dashboard (`pnpm --dir frontend build`); the 10 occurrences in
`backend/thorp/dash/static` are only the compiled form of the two React strings above.

## 2. Generated library metadata (the big one)

The author column of the synthetic reading material still says `Thorp's …`. A blind text replace
would also hit a real person, so this needs an exact-value migration.

### Distinct brand author strings

There are **6 brand values** and **1 real-person value**:

| Author value | CSV rows | `s1.books` | `s1.list_rows` |
|---|---:|---:|---:|
| `Thorp's card stage` | 657,620 | 240 | 240 |
| `Thorp's instruction stage` | 361 | 0 | 361 |
| `Thorp's logic tutor` | 352 | 126 | 200 |
| `Thorp's maths tutor` | 277 | 100 | 277 |
| `Thorp's primer (plato)` | 62 | 40 | 40 |
| `Thorp's primer (francis)` | 56 | 40 | 40 |
| **Brand total** | **658,728** | **546** | **1,158** |
| `Thorp, Thomas, former owner` (real person) | 1 | 1 | 1 |

The `Thorp's logic tutor` and `Thorp's maths tutor` counts differ because some stored books use the
long forms (`Thorp's logic tutor (template writer)`, `Thorp's maths tutor (after De Morgan, …)`);
include those variants in the migration.

### Where the data lives

- `ships/lists/**/*.csv` — 22 files, 658,728 brand rows. The largest are
  `card-stage-deck-v1/v2/v3.csv` (190,140 + 360,000 + 107,240).
- `s1.books.author` — 546 rows.
- `s1.list_rows.author` — 1,158 rows.
- Generators that will reintroduce the old value on the next run:
  `backend/scripts/make_card_stage.py`, `make_ifeval_corpus.py`, `make_ogden_maths.py`,
  `make_ogden_v02.py`, `make_ogden_v014.py`, `make_position_fitouts.py`, `make_primers.py`.

**Do not touch** `ships/lists/incunabula.csv:115` (“Thorp, Thomas, former owner”), and do not
replace the substring in “Thorpe, Francis Newton” (`ogden-v0.1-scores.csv`, `law-shelf.csv`,
`stores/trigram.csv`). Match the six exact brand values instead.

## 3. Old fitout/ship labels and opt-in text

These are user-visible in the queue card’s **ship** field and on ship pages, and are persisted in
several places.

- `ships/specs/fitouts/*.yaml` — **108 files** with `ship: 'Fitout: Thorp 300k/1m: the four cards…'`.
  (`21m@v0.0.6-ctx8192.yaml` also has one question: “every other Thorp has been limited to”.)
- `ships/specs/queue-removed-2026-11-07.txt` — 2 historical queue comments; keep with the
  historical queue.
- `ships/fitouts/ogden-v0-1-*.json` — **6 files** with `opt_in` text “Thorp's own lessons…”.
- `s1.ships.name` — **38 rows** beginning `Fitout: Thorp …`.
- `s1.runs.ship` — **39 rows / 36 distinct labels** beginning `Fitout: Thorp …`.
- `data/ships.json` — **38 occurrences**, a cache of `s1.ships`.
- `data/voyages-cache.json` — **116**, `data/ladder-cache.json` — **78**, `data/drones.json` — **5**.
- `backend/thorp/fleet.py:1556` — `"Fitout: Thorp"` in the expedition mapping is a
  **compatibility alias** for old labels. Keep it until the data is migrated, with a comment that
  it is the historical label.

Two viable approaches:

1. **Display alias (fastest, least destructive):** normalise `Fitout: Thorp` → `Fitout: Nothing up
   my sleeve` when labels are read for display. Historical ledger rows stay exactly as recorded.
2. **Data migration (complete):** update the 108 spec YAMLs, the 6 fitout JSONs, `s1.ships.name`,
   `s1.runs.ship`, and the caches; regenerate from the updated generators. Record it in DECISIONS
   because `s1.ships` is otherwise “named once and never renamed”.

The current `FITOUTS` definitions in `backend/thorp/fleet.py` already use
`Nothing up my sleeve 300k/1m…`, so newly generated specs will be correct; only the old artefacts
are stale.

## 4. Code and deployment namespace (decide separately)

This is **not** copy. Renaming it is an alias-first migration, not a find/replace.

- **3,991** lowercase `thorp` occurrences in **538** files: Python package `thorp`, CLI `thorp`,
  import paths, module names, docs commands.
- **360** `THORP_*` occurrences in **69** files, **33 distinct** names (`THORP_PG`,
  `THORP_BACKEND`, `THORP_DATA`, `THORP_QUEUE_PG`, …).
- Python and filesystem: `backend/thorp/`, the stale root `thorp/`, `backend/.venv/bin/thorp`,
  `backend/scripts/score_thorp_unseen.sh`.
- Web and storage: `/leaderboard/thorp`, `/api/thorp`, `kind: 'thorp'`, `.lb-thorp`,
  `localStorage` keys `thorp.*`, events `thorp:*`, `frontend/package.json` name `thorp-dash`.
- Deployment: `.claude/launch.json` configuration names; launchd labels `io.thorp.schedule` and
  `com.thorp.queue`; hard-coded `/Users/justintrollip/Source/Thorp` paths in both plists.
- Protocol/asset: `X-Thorp-Onboard` header (both `backend/thorp/onboard/api.py` and
  `backend/thorp/onboard/web/app.js`, plus its test).
- `frontend/public/flags/thorp.svg` is unused; the flag in use is `demiton.svg`. The flag key
  `"thorp"` in `backend/thorp/foreign.py` maps to Demiton.
- Repository root `~/Source/Thorp` and the `Thorp-parity` worktree name.

Recommendation: keep the executable/package/paths stable for now, and define that in a new
DECISIONS entry. If it is renamed later, use the alias pattern: add the new name, keep the old one
working, migrate data, then remove the alias.

## 5. Historical record and false positives (do not rewrite)

- `DECISIONS.md` — 82 lines / 106 occurrences. Historical entries keep the names they were written
  under; section titles such as “Thorp against Qwen”, “Thorp as a viable system” and “Thorp's
  schedule” are referenced elsewhere. Add a new entry for the rename scope instead of editing old
  ones. The only path/namespace statement in the header is line 7 (`~/Source/Thorp`, package
  `thorp/`), which stays true if the code namespace stays.
- `ships/reports/*.md` — 7 occurrences across 3 historical reports; keep.
- `ships/specs/queue-removed-2026-11-07.txt` — historical queue export; keep.
- `ships/plans/queue-audit-2026-11-09.md` — a dated audit; keep as written.
- `backend/scripts/make_unseen_deck.py:1`, `backend/scripts/score_external.py:2` and
  `backend/scripts/score_thorp_unseen.sh:3` refer to the historical DECISIONS section
  “Thorp against Qwen”; keep the section reference unless that section is renamed.
- `ships/plans/sop-v0.0.1` … `v0.0.6` and `v1.3.0` — versioned standards; keep unless the policy
  is retroactive doc renaming.
- `data/texts/**` — real books; a blind replacement would corrupt historical names.
- Real people/works: `Thorp, Thomas` (former owner, `incunabula.csv`), `Thorpe, Francis Newton`
  (three library lists), `Thorpe's “Elder Eddas”` (`DECISIONS.md:26`).
- `Thorp-parity` in `ships/plans/first-50m-vast.md` — a worktree name, not copy.
- `fleet.py:1556` — compatibility alias, keep until data migration.

## 6. Recommended order

1. **Define the scope in DECISIONS** (a new entry): product name = Nothing up my sleeve; code
   namespace stays `thorp` for now; historical records are immutable; generated data follows the
   new name. There is currently no DECISIONS entry for the product rename itself — only the commit
   message “Nothing up my sleeve: rename…” — so the scope has been implicit.
2. **Fix the two live UI strings** and `UI.md`, then rebuild the static dashboard.
3. **Fix the living plans** (`corpus-ceiling`, `first-50m-vast`, `arc-de-triomphe`), keeping
   historical section references.
4. **Add a display normalization** for `Fitout: Thorp` labels so the queue modal and ship pages
   show the new name immediately, without rewriting the ledger. This is the fastest visible win.
5. **Migrate the library authors** (CSV + `s1.books` + `s1.list_rows`) and update the generators;
   add a test that the real-person row is untouched.
6. **Decide** whether to migrate `s1.ships.name` / `s1.runs.ship` and the old spec YAMLs, or keep
   the display alias permanently. If migrating, update the 108 specs, the 6 fitout JSONs, all
   historical runs, and the four caches.
7. **Rebuild/invalidate**: `backend/thorp/dash/static`, `data/ships.json`,
   `data/voyages-cache.json`, `data/ladder-cache.json`, `data/drones.json`.
8. **Leave the code namespace for a separate, aliased migration**, and delete the dead root
   `thorp/dash/static` build.

## 7. Acceptance checks

- `rg '\bThorp\b'` on versioned text should return only: historical DECISIONS/reports, real
  people, the `fleet.py` compatibility alias, and the deliberate code-namespace strings.
- No brand string remains in `s1.books.author` or `s1.list_rows.author` except the real-person row.
- No `Fitout: Thorp` in the queue modal or ship pages after the display fix/migration.
- `pnpm check` passes; the queue/Liberty Machine pages render the new name; `backend/thorp/dash/static` has no
  brand occurrence after a rebuild.

# Thorp

A small language model trained only on books printed before 1930 whose authors died by 1955. Experiments hold the model still and change the books, scoring each shelf by how well the model predicts held-out books (the "hole cards"), in bits per byte.

A run is a document: every setting is in one YAML spec, the spec's SHA-1 (without `name`) is the run id, and every artifact is content-addressed by what produced it.

## First score

Run `49bd401ea915434b44f350f00e04fb0c43016073` (`hundred-by-reach-v1`, preset 9m), commit `0bc08f7` (the ledger says `-dirty` because uncommitted edits to other files arrived at 19:31, after every module this run uses was already loaded), 67.0M tokens seen (16.8M unique × 4 passes) in 28.3 minutes on Mac mini · Apple M6 · proc 12:2:4:6 · 12 GPU cores · 32 GB. Scores at the final step (2044) on the 13 hole cards that resolved; Newton's *Principia* is not on Gutenberg.

| book | language | bits per byte | cross-entropy (nats/token) |
| --- | --- | ---: | ---: |
| The Brothers Karamazov (`pg28054`) | en | 1.6176 | 4.2352 |
| The History of the Peloponnesian War (`pg7142`) | en | 1.6449 | 4.5754 |
| War and Peace (`pg2600`) | en | 1.6826 | 4.5020 |
| Dream Psychology (`pg15489`) | en | 1.6983 | 4.7523 |
| Swann's Way (`pg7178`) | en | 1.7119 | 4.6064 |
| On the Origin of Species (`pg1228`) | en | 1.7430 | 4.7596 |
| Don Quixote (`pg996`) | en | 1.7530 | 4.5904 |
| Essays of Michel de Montaigne (`pg3600`) | en | 1.7850 | 4.7821 |
| Relativity: The Special and General Theory (`pg30155`) | en | 1.9211 | 4.8465 |
| Moby Dick (`pg15`) | en | 1.9246 | 4.8849 |
| Ulysses (`pg4300`) | en | 2.3144 | 5.3680 |
| Memorias Posthumas de Braz Cubas (`pg54829`) | pt | 2.7661 | 4.9487 |
| 紅樓夢 (`pg24264`) | zh | 3.3683 | 5.7284 |
| **mean, all 13** | | **1.9947** | **4.8138** |
| mean, English only | en | 1.7997 | 4.7184 |

**Chinchilla prediction (indicative).** `L(N, D) = 1.69 + 406.4 / N^0.34 + 410.7 / D^0.28` nats per token, with N the non-embedding parameter count:

- N = 2,656,704, D = 66,977,792 tokens seen: **L = 6.993** nats/token.
- N = 2,656,704, D = 16,777,515 unique tokens: L = 8.245. Muennighoff et al. (2023) find up to about four passes count almost fully as new data, so the D = tokens-seen figure is the one to compare.
- **Gap = mean English hole-card cross-entropy − L(N, D) = 4.718 − 6.993 = -2.274** nats/token.

The gap is a yardstick, not a residual: the constants were fitted on MassiveText with a different tokeniser and much larger models, and cross-entropy per token depends on the tokeniser (this one averages about 3.6 bytes per English token). This shelf's own curve gets fitted later from this harness's runs at several sizes. A seed-2 run of the same spec (`specs/hundred-by-reach-v1-seed2.yaml`) started at 19:35 behind this one; it runs the working tree as it stood then, including those uncommitted edits; the difference between the two means is the error bar for later comparisons.

## The ladder

Five model sizes, each with one job. The 9m, 21m and 100m train on this Mac mini; 50m and 350m on rented GPUs (that needs a PyTorch backend, not built yet). Each rung is tuned once against its own job, then frozen for its shelf experiments. Details and reasons in `DECISIONS.md` ("The ladder").

| preset | total params | the job | how it is scored |
| --- | ---: | --- | --- |
| `9m` | 6.0M | spelling, punctuation, the statistical laws of text | `bpb_split` (bits per byte inside words, at word starts, on punctuation, on layout) and `laws` (non-word rate, Zipf, Heaps, word length, punctuation mix, balanced brackets and quotes, capitals after a full stop) |
| `21m` | 15.4M | grammar and style | to come: minimal pairs, loss by position in the window, a register probe |
| `50m` | 46.7M | paragraphs; the third point of this corpus's own size curve | to come |
| `100m` | 98.3M | the Origin test: trained on English before 1858, does it bet on natural selection over its rivals? | to come: matched rival passages; the precursor shelf removed at equal bytes |
| `350m` | 319.8M | the top of the Origin curve | as for 100m |

## The next runs

Queued the evening of 2026-11-06. `scripts/queue_next.sh` runs *Endeavour* (`pool-400-v1`), *Hispaniola* (`pool-400-fiction-v1`), *Mayflower* (`pool-400-nonfiction-v1`), then each with seed 2; `scripts/queue_rescore.sh` then re-scores finished runs on the v2 hole cards and the truths deck. The pool is the hundred plus 300 catalogue books cut by `scripts/cut_pool.py` (see `DECISIONS.md`), read twice; the fiction and non-fiction halves are matched in bytes, so a difference between them is the kind of book.

At 22:00 the order changed (`DECISIONS.md`): Endeavour's seed 2 was stopped and the phase-2 re-score dropped, so the 9m rung's job runs now. `scripts/queue_9m.sh` (log `data/runs/queue-9m.out`) gives every finished 9m run the bits-per-byte split and the laws, runs the 9m tuning sweep (vocabulary 4,096 and 8,192 against 16,384, context 256 against 1,024, two seeds each: *Smaller Pieces*, *Half The Pieces*, *Short Memory*, each "Rolled Again"; every 250 steps also scored on the v2 hole cards with the trait probes, for the traits that emerge while spelling is learned), then the fifteen content ships and the four traits ships, all carrying the split and the laws. Every run carries a `ship` name in its spec (a label, not part of the run id).

After the sweep, the speller curriculum (DECISIONS.md, 22:10): *Mixed Lessons* (the 13-book speller shelf shuffled into the pool), *Primer First* (the same books first) and *Lines Written a Hundred Times* (the six rule books read a hundred times first), two seeds each.

From 22:30 the queue is `scripts/queue.sh` (now `backend/scripts/queue.sh`), which runs `specs/queue.txt` (now `ships/specs/queue.txt`) top to bottom and can be edited while it runs (log `data/runs/queue.out`). After the sweep's seed-1 runs come the data levers (DECISIONS.md): distinct text against total reading, five runs around Endeavour.

## Running it

The repository has three parts (2026-11-07): `backend/` (the Python package, its tests, scripts and the
Postgres migrations), `frontend/` (the dashboard) and `ships/` (what the voyages are made of). Runtime state
stays at the root, outside git: `data/` and `ledger.sqlite`. Every command runs from the repository root.

```bash
uv sync --project backend
uv run --project backend ruff check backend
uv run --project backend pytest backend/tests
uv run --project backend alembic -c backend/alembic.ini upgrade head   # the Postgres fitout store
uv run --project backend thorp fetch lists/hole-cards.csv
uv run --project backend thorp gather --list                  # the sources beyond Gutenberg, and their walls
uv run --project backend thorp gather common-pile-pre-1929 --limit 500   # a bulk corpus through the intake gate
uv run --project backend thorp gather incunabula --set incunabula --allow-unsigned   # the first printed books, pre-1501
uv run --project backend thorp gather perseus-latin --set classics                   # Perseus Latin TEI
uv run --project backend thorp gather perseus-greek --set classics                   # Perseus Greek TEI
uv run --project backend thorp gather etcsl --set cuneiform --allow-unsigned         # Sumerian transliterations
uv run --project backend thorp run ships/specs/fitouts/fu-ogden-v0-1@300k-pre-s1.yaml
uv run --project backend python -m thorp.viable.s1_operations.prechecks ogden-v0-1   # a fitout's prechecks
sh backend/scripts/queue.sh                                  # the standing queue: ships/specs/queue.txt
pnpm --dir frontend install && pnpm --dir frontend build     # the dashboard page, once and after UI changes
uv run --project backend thorp dash                          # http://localhost:8787
uv run --project backend thorp ledger "select book_id, bpb, ce_nats from evals where run_id=? and step=(select max(step) from evals where run_id=?) order by bpb"
```

A path a spec or a script names (`lists/...`, `specs/...`, `scripts/...`) is found in its part by its first
folder (`thorp/paths.py`: `resolve` and `ROUTER`), so specs read the same as before the split.

The dashboard is an Astro app in `frontend/`. It builds to `backend/thorp/dash/static` (not committed), which `thorp dash` serves beside its JSON API. While working on the page, `pnpm --dir frontend dev` serves it with hot reload on http://localhost:4321 and forwards `/api` to a running `thorp dash`. Its standards are in `backend/thorp/dash/UI.md`.

`thorp run` on a finished spec prints its ledger row and exits; on a spec with a checkpoint it resumes from the latest one. `thorp eval RUN` re-scores a run's latest checkpoint. Each `?` in `thorp ledger` binds to the latest finished run unless you pass parameters or `--run ID`.

## Layout

- `backend/thorp/`: the harness (see `DECISIONS.md` for every choice the brief left open); `backend/thorp/viable/` the code laid out by VSM system (S1 to S5) with the Postgres fitout store; `backend/migrations/` and `backend/alembic.ini` its Alembic migrations. `backend/thorp/gather.py` is acquisition's S1 over a bulk corpus, `backend/thorp/sources/catalog.py` and `bulk.py` its S4 (the sources, their walls and their adapters).
- `backend/scripts/`: the spec writers (`make_*.py`), the pool and shelf cutters, and the queues (`queue.sh`, the standing queue).
- `backend/tests/`: the test suite.
- `frontend/`: the dashboard page (Astro): `src/pages/index.astro` the shell, `src/components/` one per tab, `src/scripts/dashboard.js` the panels, `src/lib/` the shared pieces (DataTable, charts, formatters, the book reader), `src/styles/global.css` the tokens.
- `ships/specs/`: run specs, and `queue.txt` (the standing queue) and `queue-done.txt`. `ships/lists/`: the libraries (the stores, the Ogden corpus), the hole cards, the Forgotten Tomes, and `overrides.csv` (title, author → Gutenberg id). `ships/fitouts/`: the saved fitouts (in git since the split; they were in `data/`). `ships/plans/`, `ships/reports/`.
- `data/` (not committed): catalogue, texts, tokenisers, shards, checkpoints, `manifest.sqlite`, run logs, `postgres/` (Thorp's own Postgres cluster).
- `ledger.sqlite` (not committed since 2026-11-07): every run, metric, eval and artifact.

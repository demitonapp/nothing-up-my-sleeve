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

## Running it

```bash
uv sync
uv run ruff check .
uv run pytest
uv run thorp fetch lists/hole-cards.csv
uv run thorp fetch lists/hundred-by-reach.csv
uv run thorp run specs/smoke-10.yaml
uv run thorp run specs/hundred-by-reach-v1.yaml
uv run thorp dash          # http://localhost:8787
uv run thorp ledger "select book_id, bpb, ce_nats from evals where run_id=? and step=(select max(step) from evals where run_id=?) order by bpb"
```

`thorp run` on a finished spec prints its ledger row and exits; on a spec with a checkpoint it resumes from the latest one. `thorp eval RUN` re-scores a run's latest checkpoint. Each `?` in `thorp ledger` binds to the latest finished run unless you pass parameters or `--run ID`.

## Layout

- `specs/`: run specs. `lists/`: the recipe, the hole cards, and `overrides.csv` (title, author → Gutenberg id).
- `thorp/`: the harness (see `DECISIONS.md` for every choice the brief left open).
- `data/` (not committed): catalogue, texts, tokenisers, shards, checkpoints, `manifest.sqlite`, run logs.
- `ledger.sqlite`: every run, metric, eval and artifact.

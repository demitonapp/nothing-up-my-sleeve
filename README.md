# Thorp

A small language model trained only on books printed before 1930 whose authors died by 1955. Experiments hold the model still and change the books, scoring each shelf by how well the model predicts held-out books (the "hole cards"), in bits per byte.

A run is a document: every setting is in one YAML spec, the spec's SHA-1 (without `name`) is the run id, and every artifact is content-addressed by what produced it.

## First score

_Pending: the first run of `specs/hundred-by-reach-v1.yaml` is in progress._

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

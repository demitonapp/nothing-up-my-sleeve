# Sailing a voyage on an NVIDIA GPU (the torch backend)

Every voyage trains on MLX on the Mac unless it says otherwise. The same loop runs on PyTorch, so a voyage can
also sail on a CUDA machine: `thorp/models/gpt_torch.py` (the model), `thorp/train_torch.py` (the loop) and
`thorp/models/ops.py` (what the evaluators ask of a model, on either backend).

As of 2026-11-08 this has been checked on the CPU build of torch only. No CUDA GPU was available, so the first
voyage on a GPU box is also the first test on CUDA.

## Choosing the backend

| How | Run id | When to use it |
|---|---|---|
| `model.backend: torch` in the spec | a new id (the key is hashed) | a voyage written to sail on CUDA |
| `THORP_BACKEND=torch` in the environment | unchanged | an existing spec sails, or resumes, on CUDA under its own id |

Leave `model.backend` out for MLX. Writing `backend: mlx` explicitly also changes the id. The run's `hardware`
column records `torch <version> on <GPU name>`, so a voyage that changed backend through the environment can
still be told apart.

Other settings:

- `THORP_DEVICE`: `cuda` (the default when a GPU is present), `cuda:1`, `cpu`, or `mps`.
- `THORP_TORCH_COMPILE=1`: `torch.compile` the plain forward pass. The scaffold's attending passes and the
  riddles stay eager. Try it once the voyage runs eagerly.
- `optim.precision`: `bf16` (the default) needs an Ampere or later GPU (A100, H100, L4, RTX 30/40). Use `fp32`
  on older cards. TF32 matmuls are switched on for CUDA.

## What is the same and what is not

The same by construction, and checked by `tests/test_torch.py`:

- **Architecture:** pre-norm blocks, learned or rotary positions (MLX's non-traditional RoPE), the tanh-GELU MLP
  at 4x, LayerNorm without bias, tied embeddings, no biases, and the same initialisation scheme. Given the same
  weights, the logits, residual streams and every head's attention match MLX's to about 1e-5.
- **Optimiser:** MLX's AdamW exactly (decay first, no bias correction) and MLX's `clip_grad_norm`, with fp32
  master weights and the model computing in `precision`.
- **Loss terms:** cross-entropy, teacher distillation, the copy-weighted tack (induction, duplicate,
  conclusion), the metre scaffold (every card rule, `hold`/`fade`/`floor`, staged `from` starts, `sample`), the
  comparator and bridge riddles, and seeding (`free`/`slow`/`freeze`) and transplants.
- **Checkpoints:** the same three files, with the same weight names and MLX's optimiser layout. A torch
  checkpoint loads in MLX, and an MLX checkpoint resumes on torch (tested), so `thorp eval` on the Mac can score
  a checkpoint made on the GPU.
- **Ledger rows:** the same metric names each step and every 50 steps (the sieves, per-book loss, the
  scaffold's weight, loss, phase, starts and riddles), and the same evaluator rows. Every evaluator runs on
  either backend: ce_bpb, bpb_split, stars, nevermore, cards, shapes, pips, logic, discovery, successor, probes,
  curiosity, soundings, samples and laws. Given the same weights, their scores agree with MLX's to within 2e-3.

Not the same:

- **The random initialisation:** torch's generator, not MLX's. A torch voyage starts from other weights than
  its MLX twin, unless it is seeded or resumed from a checkpoint.
- **Kernel arithmetic:** floating-point order differs, so trajectories drift apart at bf16 precision as two
  GPU runs of MLX already do.
- **Sampling:** `samples` and `laws` draw from numpy's generator, seeded by the step, instead of MLX's keys.
- **MLX imports:** the MLX path was not touched. Its run ids, losses, metrics, eval rows and artifacts are
  identical to before (checked on a 40-step scaffolded voyage with all 15 evaluators). Its evaluators now go
  through `ops.py`, which holds their old MLX code unchanged.

## Setting up a CUDA box

```bash
git clone <the repo> thorp && cd thorp && git checkout <branch>
cd backend && uv sync --group torch   # PyPI's Linux torch wheels are CUDA builds
uv run --group torch python -c "import torch; print(torch.cuda.is_available(), torch.cuda.get_device_name())"
uv run --group torch pytest tests/test_torch.py -q   # with THORP_DEVICE=cuda to test the GPU itself
```

`uv sync` also installs the `mlx` wheel on Linux, which may not import there. That is fine: the torch path
imports no MLX (`test_the_torch_path_needs_no_mlx` blocks it and runs anyway). For a CUDA version PyPI's
default does not cover, install torch from the PyTorch index into the same environment.

**Data.** A voyage reads `data/` (texts, tokenisers, shards) and `ships/` (specs, lists, fitouts). Copy the
data folder rather than refetching it, because some shelves are built locally (the logic tutor's passages):

```bash
rsync -a --info=progress2 data/texts data/tokenisers data/shards box:thorp/data/
```

**Ledger.** The S3 gate, `seeded_from` and teachers look up runs in the ledger. Copy a snapshot and point the
box at it. Never copy the live file, and never move it:

```bash
sqlite3 ledger.sqlite ".backup ledger-snapshot.sqlite"
```

```bash
scp ledger-snapshot.sqlite box:thorp/ledger.sqlite
```

**The fitout store.** The gate's `prechecks` policy reads the Postgres fitout store (`THORP_PG`). From the box,
reach the Mac's store through a tunnel, for example `ssh -L 5432:localhost:5432 mac`, or the gate refuses the
voyage.

## Sailing

```bash
cd thorp
THORP_BACKEND=torch uv run --project backend --group torch thorp run ships/specs/<voyage>.yaml
```

For a spec written with `model.backend: torch`, the environment variable is not needed. The standing queue
(`backend/scripts/queue.sh`) works on the box too, run with `THORP_BACKEND=torch` exported. Its `uv run`
line needs `--group torch` added, or torch installed into the default environment.

## Bringing a voyage home

- **Checkpoints** (`data/checkpoints/<run_id>/step-N/`) are backend-neutral. Copy them back and the Mac can
  score them (`thorp eval`) or resume them on MLX.
- **The ledger rows** are written to the box's ledger. Merging them into the Mac's ledger is not built yet. Until
  it is, copy the run's rows from the `runs`, `metrics`, `evals` and `artifacts` tables, or rescore its
  checkpoints on the Mac.

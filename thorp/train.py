"""The one training loop: step, record, evaluate, checkpoint, resume. Same code for every preset."""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import yaml
from mlx.utils import tree_flatten, tree_map, tree_unflatten

from thorp import data, evaluators, manifest, paths, shards
from thorp import tokeniser as tokmod
from thorp.ledger import Ledger
from thorp.models import registry

METRICS_EVERY = 50


# ---------------------------------------------------------------- the spec


def load_spec(path: str | Path) -> dict:
    with open(paths.resolve(path), encoding="utf-8") as f:
        return yaml.safe_load(f)


NOT_HASHED = (
    "name",
    "ship",
    "experiment",
    "question",
)  # labels: a run's id is its settings, never what it is called or what it is for


def canonical(spec: dict) -> str:
    return json.dumps(
        {k: v for k, v in spec.items() if k not in NOT_HASHED},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def run_id(spec: dict) -> str:
    return hashlib.sha1(canonical(spec).encode()).hexdigest()


def set_name(list_path: str) -> str:
    return Path(list_path).stem


# ---------------------------------------------------------------- environment


def git_commit() -> str:
    try:
        sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=paths.ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "uncommitted"
    dirty = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=no"],
        cwd=paths.ROOT,
        capture_output=True,
        text=True,
    ).stdout.strip()
    return sha + ("-dirty" if dirty else "")


_hardware: str | None = None


def hardware() -> str:
    global _hardware
    if _hardware is None:
        try:
            out = subprocess.run(
                ["system_profiler", "SPHardwareDataType", "SPDisplaysDataType", "-json"],
                capture_output=True,
                text=True,
                timeout=30,
            ).stdout
            j = json.loads(out)
            hw = j["SPHardwareDataType"][0]
            gpu = (j.get("SPDisplaysDataType") or [{}])[0]
            parts = [
                hw.get("machine_name", ""),
                hw.get("chip_type", ""),
                hw.get("number_processors", ""),
                f"{gpu.get('sppci_cores', '?')} GPU cores",
                hw.get("physical_memory", ""),
            ]
            _hardware = " · ".join(str(p) for p in parts if p)
        except Exception as e:  # noqa: BLE001
            _hardware = f"unknown ({e.__class__.__name__})"
    return _hardware


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class Log:
    def __init__(self, path: Path | None):
        self.f = None
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.f = open(path, "a", encoding="utf-8")  # noqa: SIM115

    def __call__(self, *a):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] " + " ".join(str(x) for x in a)
        print(line, flush=True)
        if self.f:
            self.f.write(line + "\n")
            self.f.flush()


# ---------------------------------------------------------------- preparation


class RefusedBook(RuntimeError):
    pass


@dataclass
class Prepared:
    recipe: list[str]
    eval_sets: dict[str, list[str]]
    missing: dict[str, list[str]] = field(default_factory=dict)
    tokeniser: tokmod.Tokeniser | None = None
    first: list[str] = field(default_factory=list)  # a curriculum's opening books (data.first)

    def books(self) -> dict[str, manifest.Book]:
        ids = set(self.recipe) | {b for s in self.eval_sets.values() for b in s}
        return manifest.get_many(sorted(ids))


ListResolver = Callable[[str], tuple[list[str], list[str]]]  # path -> (book ids, missing titles)


def gutenberg_resolver(list_path: str) -> tuple[list[str], list[str]]:
    from thorp.sources import gutenberg

    ids, missing = [], []
    for res, book, err in gutenberg.fetch_list(list_path):
        if book is not None:
            ids.append(book.id)
        else:
            missing.append(f"{res.row.title} ({err})")
    return ids, missing


def check_refusals(recipe: list[str], refused: dict[str, list[str]]) -> None:
    clash = {name: sorted(set(recipe) & set(ids)) for name, ids in refused.items()}
    clash = {k: v for k, v in clash.items() if v}
    if clash:
        raise RefusedBook(f"recipe contains refused books: {clash}")


def prepare(spec: dict, resolver: ListResolver = gutenberg_resolver, log=print) -> Prepared:
    d = spec["data"]
    recipe, missing_recipe = resolver(d["recipe"])
    refused = {set_name(p): resolver(p)[0] for p in d.get("refuse", [])}
    eval_sets, missing = {}, {}
    for p in spec["eval"]["sets"]:
        ids, miss = resolver(p)
        eval_sets[set_name(p)] = ids
        missing[set_name(p)] = miss
    check_refusals(recipe, {**refused, **eval_sets})
    missing["recipe"] = missing_recipe
    prep = Prepared(recipe=recipe, eval_sets=eval_sets, missing=missing)
    if d.get("first"):
        prep.first, missing["first"] = resolver(d["first"])
    t = spec["tokeniser"]
    # train_on: "recipe" (the default) or a list path, so runs on different shelves can share one
    # tokeniser and differ only in what they read (the data-lever experiment, 2026-11-06)
    train_on = t.get("train_on", "recipe")
    tok_books = recipe if train_on == "recipe" else resolver(train_on)[0]
    settings = {"kind": t["kind"], "vocab": t["vocab"], "byte_fallback": t["byte_fallback"]}
    log(f"tokeniser: training or loading on {len(tok_books)} books ({train_on})")
    prep.tokeniser = tokmod.train_or_load(tok_books, settings)
    log(f"tokeniser {prep.tokeniser.id[:12]} vocab {prep.tokeniser.vocab_size}; sharding")
    for b in recipe + [b for s in eval_sets.values() for b in s]:
        shards.encode(prep.tokeniser.id, b, prep.tokeniser)
    return prep


# ---------------------------------------------------------------- checkpoints


def checkpoint_root(rid: str) -> Path:
    return paths.checkpoints_dir() / rid


def latest_checkpoint(rid: str) -> Path | None:
    root = checkpoint_root(rid)
    if not root.exists():
        return None
    done = [p for p in root.glob("step-*") if (p / "state.json").exists()]
    return max(done, key=lambda p: int(p.name.split("-")[1]), default=None)


def save_checkpoint(rid: str, step: int, master, opt, state: dict) -> Path:
    d = checkpoint_root(rid) / f"step-{step}"
    tmp = d.with_name(d.name + ".tmp")
    tmp.mkdir(parents=True, exist_ok=True)
    mx.save_safetensors(str(tmp / "model.safetensors"), dict(tree_flatten(master)))
    mx.save_safetensors(str(tmp / "optimizer.safetensors"), dict(tree_flatten(opt.state)))
    (tmp / "state.json").write_text(json.dumps(state, indent=1))
    if d.exists():
        import shutil

        shutil.rmtree(d)
    tmp.rename(d)
    return d


def load_master(ckpt: Path):
    return tree_unflatten(list(mx.load(str(ckpt / "model.safetensors")).items()))


# ---------------------------------------------------------------- the loop


def lr_at(step: int, total: int, o: dict) -> float:
    lr, warm, floor = o["lr"], o["warmup_steps"], o["lr"] * o["min_lr_ratio"]
    if step < warm:
        return lr * (step + 1) / warm
    if o.get("schedule", "cosine") != "cosine":
        return lr
    prog = min(1.0, (step - warm) / max(1, total - warm))
    return floor + (lr - floor) * 0.5 * (1 + math.cos(math.pi * prog))


def build_model(spec: dict, vocab: int):
    m = spec["model"]
    mx.random.seed(spec["seed"])
    return registry.build(m["family"], m["preset"], vocab, m["context"])


def init_model(spec: dict, vocab: int):
    """The run's model at initialisation (its own seed), in its compute precision: the untrained
    floor the probes and the curiosity ladder are measured against. build_model reseeds MLX's
    global generator; that is safe mid-run only because nothing in training draws from it after
    the model is built (the samples evaluator uses explicit keys)."""
    m = build_model(spec, vocab)
    m.update(to_compute(m.parameters(), spec["optim"].get("precision", "bf16")))
    return m


def to_compute(master, precision: str):
    dt = mx.bfloat16 if precision == "bf16" else mx.float32
    return tree_map(lambda p: p.astype(dt), master)


def run_evaluators(spec, rid, step, model, prep, rec: Ledger, log) -> dict:
    books = prep.books()
    ctx = evaluators.EvalContext(
        run_id=rid,
        step=step,
        model=model,
        tokeniser=prep.tokeniser,
        context=spec["model"]["context"],
        sets=prep.eval_sets,
        languages={b: books[b].language for b in books},
        recipe=list(prep.recipe),
        init_model=lambda: init_model(spec, prep.tokeniser.vocab_size),
    )
    if "ce_bpb" in spec["eval"]["evaluators"]:  # the only evaluator that writes evals rows, so a
        # re-score with others alone (bpb_split, laws) leaves the step's scores in place
        rec.clear_step(rid, step, tables=("evals",), sets=list(prep.eval_sets))
    t0 = time.time()
    merged = {}
    for name in spec["eval"]["evaluators"]:
        try:
            res = evaluators.get(name)(ctx)
        except Exception as e:  # noqa: BLE001
            # the score (ce_bpb) may stop a run; any other evaluator that fails is recorded at the
            # step and skipped, so a probe or the ladder can never cost a night's training
            if name == "ce_bpb":
                raise
            msg = f"{name} failed at step {step}: {e.__class__.__name__}: {e}"
            log(msg)
            rec.artifact(
                rid, step, "eval_error", "", "", json.dumps({"evaluator": name, "error": msg})
            )
            continue
        if res.evals:
            rec.evals(res.evals)
        if res.metrics:
            rec.metrics(rid, step, res.metrics)
            merged.update(res.metrics)
        for a in res.artifacts:
            rec.artifact(
                rid, step, a["kind"], a.get("path", ""), a.get("sha1", ""), a.get("text", "")
            )
    rec.metrics(rid, step, {"eval/seconds": time.time() - t0})
    log(f"eval @ {step}: " + ", ".join(f"{k}={v:.4f}" for k, v in merged.items()))
    return merged


def record_eval_sets(rid: str, step: int, prep: Prepared, rec: Ledger) -> None:
    """The held-out books scored from this step on, with titles and families, as an artifact."""
    books = prep.books()
    sets = {
        name: [
            {
                "book_id": b,
                "title": books[b].title,
                "language": books[b].language,
                "family": books[b].family,
                "bytes": books[b].bytes,
            }
            for b in ids
        ]
        for name, ids in prep.eval_sets.items()
    }
    rec.artifact(
        rid,
        step,
        "eval_sets",
        "",
        "",
        json.dumps({"sets": sets, "missing": prep.missing}, ensure_ascii=False),
    )


def record_setup(spec, rid, prep: Prepared, stream: data.Stream, counts: dict, rec: Ledger):
    books = prep.books()
    stats = prep.tokeniser.stats()
    recipe = [
        {
            "book_id": b,
            "title": books[b].title,
            "family": books[b].family,
            "language": books[b].language,
            "tokens": int(len(shards.load(prep.tokeniser.id, b))),
            **{k: stats.get(b, {}).get(k) for k in ("bytes_per_token", "byte_fallback_rate")},
        }
        for b in prep.recipe
    ]
    rec.artifact(rid, 0, "recipe", "", "", json.dumps(recipe, ensure_ascii=False))
    record_eval_sets(rid, 0, prep, rec)
    rec.artifact(rid, 0, "tokeniser", str(prep.tokeniser.dir), prep.tokeniser.id, "")
    rec.metrics(
        rid,
        0,
        {
            "model/params_total": counts["total"],
            "model/params_embedding": counts["embedding"],
            "model/params_non_embedding": counts["non_embedding"],
            "plan/total_steps": stream.total_steps,
            "plan/tokens_total": stream.total_steps * stream.tokens_per_step,
            "plan/unique_tokens": stream.unique_tokens,
            "plan/passes": stream.passes,
        },
    )


def train(
    spec: dict, prep: Prepared, rec: Ledger | None = None, stop_after: int | None = None, log=None
) -> dict:
    """Train (or resume) the run this spec describes. stop_after simulates an interruption."""
    rid = run_id(spec)
    rec = rec or Ledger()
    log = log or Log(paths.runs_dir() / f"{rid}.log")
    o, m = spec["optim"], spec["model"]
    precision = o.get("precision", "bf16")
    tok = prep.tokeniser
    books = prep.books()
    families = {b: books[b].family for b in books}
    stream = data.stream(
        prep.recipe,
        tok.id,
        spec["seed"],
        o["batch_tokens"],
        m["context"],
        spec["data"]["passes"],
        families,
        first=prep.first,
        first_repeats=spec["data"].get("first_repeats", 1),
    )
    total = stream.total_steps

    model = build_model(spec, tok.vocab_size)
    counts = model.parameter_counts()
    master = tree_map(lambda p: p.astype(mx.float32), model.parameters())
    opt = optim.AdamW(learning_rate=o["lr"], betas=list(o["betas"]), weight_decay=o["weight_decay"])

    start, tokens_seen, wall_before = 0, 0, 0.0
    ckpt = latest_checkpoint(rid)
    if ckpt is not None:
        st = json.loads((ckpt / "state.json").read_text())
        start, tokens_seen, wall_before = st["step"], st["tokens_seen"], st["wall_seconds"]
        master = load_master(ckpt)
        opt.state = tree_unflatten(list(mx.load(str(ckpt / "optimizer.safetensors")).items()))
        rec.truncate_after(rid, start)
        log(f"resuming {rid[:12]} from {ckpt.name}")
    model.update(to_compute(master, precision))
    mx.eval(model.parameters())

    rec.run(
        {
            "run_id": rid,
            "name": spec.get("name"),
            "ship": spec.get("ship"),
            "spec_json": canonical(spec),
            "commit": git_commit(),
            "hardware": hardware(),
            "status": "running",
            "started": None if (rec.get_run(rid) or {}).get("started") else now(),
        }
    )
    if start == 0:
        rec.truncate_after(rid, -1)
        record_setup(spec, rid, prep, stream, counts, rec)
    log(
        f"run {rid} ({spec.get('name')}): {m['preset']} {counts}, {total} steps x "
        f"{stream.tokens_per_step} tokens, {stream.unique_tokens} unique tokens/pass"
    )

    def loss_fn(mdl, x, y):
        # (batch, time) -> the mean per window, so the loss can be attributed to the window's book;
        # every window is the same length, so the mean of the window means is the batch mean.
        ce = nn.losses.cross_entropy(mdl(x).astype(mx.float32), y, reduction="none")
        per_window = ce.mean(axis=1)
        return per_window.mean(), per_window

    value_and_grad = nn.value_and_grad(model, loss_fn)
    step_fn = mx.compile(
        lambda x, y: value_and_grad(model, x, y), inputs=model.state, outputs=model.state
    )
    groups = model.param_groups()
    # the sieves: the weights as they stood at the last record, so the move per group is measured
    prev_flat, prev_step = dict(tree_flatten(master)), start
    # the loss per book: window losses summed per recipe book since the last record
    book_loss: dict[int, float] = {}
    book_n: dict[int, int] = {}
    every_eval = spec["eval"]["every_steps"]
    every_ckpt = spec["checkpoint"]["every_steps"]
    t_run = time.time()

    step = start
    for batch in stream.iter_from(start):
        t0 = time.time()
        lr = lr_at(step, total, o)
        opt.learning_rate = lr
        tokens = mx.array(batch.tokens)
        (loss, per_window), grads = step_fn(tokens[:, :-1], tokens[:, 1:])
        grads = tree_map(lambda g: g.astype(mx.float32), grads)
        grads, gnorm = optim.clip_grad_norm(grads, o["grad_clip"])
        master = opt.apply_gradients(grads, master)
        model.update(to_compute(master, precision))
        mx.eval(loss, per_window, gnorm, master, opt.state)
        step += 1
        for bi, lw in zip(batch.book_index.tolist(), per_window.tolist(), strict=True):
            book_loss[bi] = book_loss.get(bi, 0.0) + lw
            book_n[bi] = book_n.get(bi, 0) + 1
        tokens_seen += stream.tokens_per_step
        dt = time.time() - t0
        loss_v = loss.item()
        if not math.isfinite(loss_v):
            raise FloatingPointError(f"loss is {loss_v} at step {step}")
        vals = {
            "loss": loss_v,
            "lr": lr,
            "step_ms": dt * 1000,
            "tokens_per_s": stream.tokens_per_step / dt,
            "tokens_seen": tokens_seen,
        }
        if step % METRICS_EVERY == 0 or step == 1:
            flat = dict(tree_flatten(grads))
            vals["grad_norm"] = gnorm.item()
            vals["param_norm"] = math.sqrt(
                sum((p * p).sum().item() for _, p in tree_flatten(master))
            )
            vals["mem_gb"] = mx.get_peak_memory() / 1e9
            # the sieves, per group (each layer, its attn and mlp halves, the two embeddings):
            # the push is the gradient, the size is the weights, the move is what Adam made of
            # the push since the last record
            mflat = dict(tree_flatten(master))
            moved = step - prev_step == METRICS_EVERY
            for g, prefix in groups.items():
                keys = [k for k in mflat if k.startswith(prefix)]
                vals[f"grad_norm/{g}"] = math.sqrt(
                    sum((flat[k] * flat[k]).sum().item() for k in keys if k in flat)
                )
                pn = math.sqrt(sum((mflat[k] * mflat[k]).sum().item() for k in keys))
                vals[f"param_norm/{g}"] = pn
                if moved:
                    un = math.sqrt(sum(((mflat[k] - prev_flat[k]) ** 2).sum().item() for k in keys))
                    vals[f"update_norm/{g}"] = un
                    vals[f"update_ratio/{g}"] = un / pn if pn else 0.0
            if step % METRICS_EVERY == 0:
                prev_flat, prev_step = mflat, step
            for fam, frac in batch.family_mix(stream.families).items():
                vals[f"data/family/{fam}"] = frac
            # the loss per book over the window since the last record
            for bi, n in book_n.items():
                vals[f"loss/book/{stream.book_ids[bi]}"] = book_loss[bi] / n
            book_loss, book_n = {}, {}
            log(
                f"step {step}/{total} loss {loss_v:.4f} lr {lr:.2e} "
                f"{vals['tokens_per_s']:.0f} tok/s mem {vals['mem_gb']:.1f} GB"
            )
        rec.metrics(rid, step, vals)

        if step % every_eval == 0 or step == total:
            run_evaluators(spec, rid, step, model, prep, rec, log)
        if step % every_ckpt == 0 or step == total:
            wall = wall_before + time.time() - t_run
            d = save_checkpoint(
                rid,
                step,
                master,
                opt,
                {
                    "run_id": rid,
                    "step": step,
                    "tokens_seen": tokens_seen,
                    "wall_seconds": wall,
                    "tokeniser_id": tok.id,
                    "total_steps": total,
                },
            )
            rec.artifact(rid, step, "checkpoint", str(d), "", "")
        if stop_after is not None and step >= stop_after:
            log(f"stopping at step {step} (stop_after)")
            return {"run_id": rid, "step": step, "status": "running"}

    wall = wall_before + time.time() - t_run
    rec.run(
        {
            "run_id": rid,
            "finished": now(),
            "status": "finished",
            "tokens_seen": tokens_seen,
            "wall_minutes": wall / 60,
            "commit": git_commit(),
        }
    )
    log(f"finished {rid}: {tokens_seen} tokens in {wall / 60:.1f} min")
    return {"run_id": rid, "step": step, "status": "finished"}


def rescore(
    run: str,
    sets: list[str] | None = None,
    evaluators: list[str] | None = None,
    resolver: ListResolver = gutenberg_resolver,
    rec: Ledger | None = None,
    log=print,
) -> int:
    """Re-run the evaluators on a run's latest checkpoint; returns the step scored.

    With `sets`, score those lists instead of the spec's (2026-11-06, phase 2): the run's own spec
    in the ledger is untouched, the held-out books are refused against the recipe exactly as at
    training, an `eval_sets` artifact records what was scored at that step, and only the evals rows
    of those sets at that step are replaced.
    """
    from thorp.ledger import spec_of

    rec = rec or Ledger()
    rows = rec.query("select * from runs where run_id like ? order by started desc", [run + "%"])
    if not rows:
        raise LookupError(f"no run {run}")
    spec, rid = spec_of(rows[0]), rows[0]["run_id"]
    ckpt = latest_checkpoint(rid)
    if ckpt is None:
        raise LookupError(f"run {rid} has no checkpoint")
    if sets:
        spec["eval"] = {**spec["eval"], "sets": list(sets)}
    if evaluators:
        spec["eval"] = {**spec["eval"], "evaluators": list(evaluators)}
    prep = prepare(spec, resolver=resolver, log=log)
    step = json.loads((ckpt / "state.json").read_text())["step"]
    model = build_model(spec, prep.tokeniser.vocab_size)
    model.update(to_compute(load_master(ckpt), spec["optim"].get("precision", "bf16")))
    if sets:
        record_eval_sets(rid, step, prep, rec)
    run_evaluators(spec, rid, step, model, prep, rec, log)
    return step


def run(spec_path: str | Path, rec: Ledger | None = None) -> dict:
    spec = load_spec(spec_path)
    rid = run_id(spec)
    rec = rec or Ledger()
    existing = rec.get_run(rid)
    if existing and existing["status"] == "finished":
        print(json.dumps({k: v for k, v in existing.items() if k != "spec_json"}, indent=1))
        return existing
    log = Log(paths.runs_dir() / f"{rid}.log")
    log(f"spec {spec_path} -> run id {rid}")
    prep = prepare(spec, log=log)
    for name, miss in prep.missing.items():
        if miss:
            log(f"missing from {name}: {miss}")
    try:
        return train(spec, prep, rec, log=log)
    except Exception as e:
        rec.run({"run_id": rid, "status": f"failed: {e.__class__.__name__}"})
        log(f"FAILED: {e!r}")
        raise


if __name__ == "__main__":
    run(sys.argv[1])

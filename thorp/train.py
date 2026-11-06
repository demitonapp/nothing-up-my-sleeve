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


def canonical(spec: dict) -> str:
    return json.dumps(
        {k: v for k, v in spec.items() if k != "name"},
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
    t = spec["tokeniser"]
    if t.get("train_on", "recipe") != "recipe":
        raise ValueError("only tokeniser.train_on: recipe is implemented")
    settings = {"kind": t["kind"], "vocab": t["vocab"], "byte_fallback": t["byte_fallback"]}
    log(f"tokeniser: training or loading on {len(recipe)} recipe books")
    prep.tokeniser = tokmod.train_or_load(recipe, settings)
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
    )
    rec.clear_step(rid, step, tables=("evals",))
    t0 = time.time()
    merged = {}
    for name in spec["eval"]["evaluators"]:
        res = evaluators.get(name)(ctx)
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
    rec.artifact(rid, 0, "recipe", "", "", json.dumps(recipe, ensure_ascii=False))
    rec.artifact(
        rid,
        0,
        "eval_sets",
        "",
        "",
        json.dumps({"sets": sets, "missing": prep.missing}, ensure_ascii=False),
    )
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
        return nn.losses.cross_entropy(mdl(x).astype(mx.float32), y, reduction="mean")

    value_and_grad = nn.value_and_grad(model, loss_fn)
    step_fn = mx.compile(
        lambda x, y: value_and_grad(model, x, y), inputs=model.state, outputs=model.state
    )
    layer_names = model.layer_names()
    every_eval = spec["eval"]["every_steps"]
    every_ckpt = spec["checkpoint"]["every_steps"]
    t_run = time.time()

    step = start
    for batch in stream.iter_from(start):
        t0 = time.time()
        lr = lr_at(step, total, o)
        opt.learning_rate = lr
        tokens = mx.array(batch.tokens)
        loss, grads = step_fn(tokens[:, :-1], tokens[:, 1:])
        grads = tree_map(lambda g: g.astype(mx.float32), grads)
        grads, gnorm = optim.clip_grad_norm(grads, o["grad_clip"])
        master = opt.apply_gradients(grads, master)
        model.update(to_compute(master, precision))
        mx.eval(loss, gnorm, master, opt.state)
        step += 1
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
            for i, ln in enumerate(layer_names):
                sq = sum((g * g).sum().item() for k, g in flat.items() if k.startswith(ln + "."))
                vals[f"grad_norm/layer_{i}"] = math.sqrt(sq)
            for fam, frac in batch.family_mix(stream.families).items():
                vals[f"data/family/{fam}"] = frac
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

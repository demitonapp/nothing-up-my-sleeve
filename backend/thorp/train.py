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

import yaml

try:
    import mlx.core as mx
    import mlx.nn as nn
    import mlx.optimizers as optim
    from mlx.utils import tree_flatten, tree_map, tree_unflatten
except (
    ImportError
):  # a CUDA box without MLX: a torch voyage (thorp/train_torch.py) needs none of it
    mx = nn = optim = tree_flatten = tree_map = tree_unflatten = None

from thorp import data, evaluators, manifest, paths, shards
from thorp import tokeniser as tokmod
from thorp.ledger import Ledger, reader, recorder
from thorp.models import registry
from thorp.models.backend import backend_of

METRICS_EVERY = 50


# ---------------------------------------------------------------- the spec


def load_spec(path: str | Path) -> dict:
    with open(paths.resolve(path), encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    from thorp import ladder
    ladder.ensure(spec)  # the Ogden/Kipling measurement contract, before the id is computed
    return spec


NOT_HASHED = (
    "name",
    "ship",
    "experiment",
    "question",
    "fitout",  # the named fitout a voyage is a variation of (S5 policy 'fitout'): a label, so naming it moves no id
    "charter",  # where it sails (a GPU hired from Vast.ai, thorp/viable/s1_operations/charter.py), not what it is
    "gpu",  # the GPU class a hire must be (13 November: the deep 50m does not fit an RTX 4090): where, not what
    # the expedition it sails for, named outright (11 November, item 11; fleet.expedition_of_spec): no spec or run
    # carried the key that day, so no id moved (tests/test_run_state.py holds every spec and run to it)
    "expedition",
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
    stage_recipes: list[list[str]] = field(default_factory=list)  # each training stage's books

    def books(self) -> dict[str, manifest.Book]:
        ids = set(self.recipe) | {b for s in self.eval_sets.values() for b in s}
        return manifest.get_many(sorted(ids))


ListResolver = Callable[[str], tuple[list[str], list[str]]]  # path -> (book ids, missing titles)


def gutenberg_resolver(list_path: str) -> tuple[list[str], list[str]]:
    from thorp.sources import base, gutenberg

    # rows naming a book directly ("<source>:<identifier>" in the text column: archive:<id>,
    # gutenberg:<number>, local:<book id>) go through the general fetcher; the rest are matched by
    # title on Gutenberg as before (2026-11-07)
    rows = gutenberg.read_list(list_path)
    if rows and all(base.is_ref(r.text) for r in rows):
        ids, missing = [], []
        for r in rows:
            try:
                ids.append(
                    base.fetch_ref(
                        r.text, family=r.family, set_name=gutenberg.set_for_list(list_path)
                    ).id
                )
            except Exception as e:  # noqa: BLE001
                missing.append(f"{r.text} ({e})")
        return ids, missing
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


def _checkpoint_tokeniser(rid: str) -> str | None:
    """The tokeniser a voyage's latest checkpoint was written with, if it has one."""
    try:
        ck = latest_checkpoint(rid)
        return json.loads((ck / "state.json").read_text()).get("tokeniser_id") if ck else None
    except Exception:  # noqa: BLE001
        return None


def _grafted(tid: str) -> bool:
    """Whether a tokeniser on this machine is a seed's piece table under another cleaning (tokeniser.graft)."""
    try:
        return bool(json.loads((paths.tokenisers_dir() / tid / "settings.json").read_text()).get("pieces_of"))
    except Exception:  # noqa: BLE001
        return False


def _seed_tokeniser(seed) -> str | None:
    """The tokeniser a leg's seed was trained with, from the seed's own checkpoint: the newest finished run of
    that name (the one `seeded_master` will take), or, before the seed has docked, the run of that name now at
    sea, so a queued leg can be prepared and checked while its seed still sails. None when the spec names no
    seed or no run of that name has a checkpoint yet."""
    if not isinstance(seed, dict) or not seed.get("run"):
        return None
    from thorp import versioning

    ref = str(seed["run"])
    try:
        if versioning.is_run_id(ref):
            row = reader().get_run(ref)
        else:
            row = reader().get_run_by_name(ref, finished=True) or reader().get_run_by_name(ref)
    except Exception:  # noqa: BLE001  (no ledger on a box: seeded_master is the check that refuses)
        return None
    return _checkpoint_tokeniser(row["run_id"]) if row else None


def prepare(
    spec: dict, resolver: ListResolver = gutenberg_resolver, log=print, known: bool | None = None,
    sailed: str | None = None,
) -> Prepared:
    """`sailed` is the run this spec was read from when the spec has since been changed (a rescore swaps the
    eval sets, which moves run_id(spec)): its checkpoint says which tokeniser the voyage was trained with."""
    d = spec["data"]
    # S3, the gate (thorp/liberty_machine.py): every enforced S5 policy applied to a new run, before it reads a page. A rescore
    # re-runs prepare with the spec's eval sets changed, which changes run_id(spec): the run is known by definition,
    # so the reader passes `known=True` rather than letting the gate mistake it for a new voyage (8 November: three
    # eval commands refused for a fitout their run already sailed under).
    from thorp import liberty_machine

    if known is None:
        known = reader().get_run(run_id(spec)) is not None
    for note in liberty_machine.gate(spec, known_run=known):
        log(f"S3 gate: {note}")
    # a line a step, so silence is never ambiguous: three voyages went quiet here for five minutes and were
    # read as hung (9 November). Each stage resolves once, and says how many books it found.
    stage_recipes = []
    for st in d.get("stages", []):
        name = st.get("name") or st["recipe"]
        log(f"preparing: stage {name} ({st['recipe']})")
        ids, miss = resolver(st["recipe"])
        log(f"preparing: stage {name}: {len(ids)} books, {len(miss)} missing")
        stage_recipes.append((ids, miss))
    if not stage_recipes:
        log(f"preparing: {d['recipe']}")
    if stage_recipes:  # training stages: the recipe is every stage's shelf together
        seen: dict[str, None] = {}
        for ids, _ in stage_recipes:
            seen.update(dict.fromkeys(ids))
        recipe, missing_recipe = list(seen), [m for _, miss in stage_recipes for m in miss]
    else:
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
    prep.stage_recipes = [ids for ids, _ in stage_recipes]
    if d.get("first"):
        prep.first, missing["first"] = resolver(d["first"])
    t = spec["tokeniser"]
    # train_on: "recipe" (the default) or a list path, so runs on different shelves can share one
    # tokeniser and differ only in what they read (the data-lever experiment, 2026-11-06)
    train_on = t.get("train_on", "recipe")
    tok_books = recipe if train_on == "recipe" else resolver(train_on)[0]
    settings = {"kind": t["kind"], "vocab": t["vocab"], "byte_fallback": t["byte_fallback"]}
    from thorp import cleaning

    clean = cleaning.version_of(
        spec
    )  # data.clean: the text as read, training and held-out decks alike
    if clean != "raw":  # a raw voyage keeps its old tokeniser id
        settings["clean"] = clean
    # the control tokens a voyage declares become single pieces (11 November: until now `symbols` was
    # read by the SOP check and never passed on, so every "control-token" arm split its markers into
    # byte pieces). The tokeniser's own specials are not user-defined pieces; a plain voyage declares
    # none and keeps its tokeniser id. A voyage that already has a checkpoint keeps the tokeniser that
    # checkpoint was written with, so a resume or a rescore of an earlier sailing reads it as it was trained.
    symbols = tokmod.user_symbols(t.get("symbols"))
    if symbols:
        before = tokmod.tokeniser_id(tok_books, {**tokmod.DEFAULTS, **settings})
        if _checkpoint_tokeniser(sailed or run_id(spec)) == before:
            log(f"control tokens: this voyage's checkpoint was written without them as pieces; kept as trained ({before[:12]})")
        else:
            settings["symbols"] = symbols
            log(f"control tokens: {len(symbols)} declared as single pieces")
    log(f"cleaning: {clean}")
    # a leg reads with its seed's pieces (11 November, the return leg): the tokeniser's id carries the cleaning,
    # so a leg that cleans its text another way than its seed would build a second tokeniser, and the merges
    # learned from differently cleaned text need not land on the same ids (thorp/tokeniser.py graft). A voyage
    # that already has a checkpoint keeps the tokeniser it was written with.
    own_tid = tokmod.tokeniser_id(tok_books, {**tokmod.DEFAULTS, **settings})
    kept_tid = _checkpoint_tokeniser(sailed or run_id(spec))
    seed_tid = _seed_tokeniser(spec.get("seeded_from"))
    if kept_tid and kept_tid != own_tid and _grafted(kept_tid):
        log(f"tokeniser: this voyage's checkpoint was written with its seed's pieces ({kept_tid[:12]}); kept")
        prep.tokeniser = tokmod.load(kept_tid)
    elif seed_tid and seed_tid != own_tid and not kept_tid:
        prep.tokeniser = tokmod.graft(seed_tid, tok_books, settings)
        log(f"tokeniser: the seed's pieces ({seed_tid[:12]}) read with this leg's cleaning ({clean}): "
            f"{prep.tokeniser.id[:12]}, not a second tokeniser of its own ({own_tid[:12]})")  # fmt: skip
    else:
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
    # step-N only: a half-written step-N.tmp (a crash between state.json and the rename) or a pruned
    # .step-N.pruned is never a checkpoint (11 November)
    done = [p for p in root.glob("step-*") if p.name[5:].isdigit() and (p / "state.json").exists()]
    return max(done, key=lambda p: int(p.name[5:]), default=None)


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


# Checkpoint retention (11 November, the audit's item 10): every `step-N` was kept, about 650 GB for a 100k-step
# 350m voyage. A spec may now say `checkpoint.keep_last: K` (the newest K) and `checkpoint.keep_every: M` (every
# step that is a multiple of M, the voyage's milestones in its own history); after each new checkpoint is safely
# written, the others are deleted. With neither key every checkpoint is kept, as before. The newest is never
# deleted (a resume reads it, and so do a seed, a teacher and a heads' donor named without a step), and nor is a
# step a queued or at-sea voyage names as its seed (`seeded_from: {run, step}`, the only parent read at a step),
# nor a step whose deferred evaluators (eval.offline) `thorp score` has still to read from it.


def retention(spec: dict) -> tuple[int, int] | None:
    """(keep_last, keep_every) from the spec's checkpoint block, or None to keep every checkpoint. keep_last is
    at least 1 (1 when only keep_every is given); keep_every 0 keeps no milestones."""
    c = spec.get("checkpoint") or {}
    if c.get("keep_last") is None and c.get("keep_every") is None:
        return None
    return max(1, int(c.get("keep_last") or 1)), max(0, int(c.get("keep_every") or 0))


def checkpoint_steps(rid: str) -> list[int]:
    """The steps of a run's complete checkpoints (state.json written), oldest first."""
    root = checkpoint_root(rid)
    if not root.exists():
        return []
    return sorted(
        int(p.name[5:]) for p in root.glob("step-*") if p.name[5:].isdigit() and (p / "state.json").exists()
    )


def _voyages_waiting() -> list[dict]:
    """The specs of every voyage queued or at sea at home, read from the queue store (raw YAML: only their
    parents are wanted). A hired box has no standing queue: none. Raises when the store cannot be read, so
    that nothing is pruned on a guess."""
    from thorp import store
    from thorp.viable.s2_coordination import queue_store

    if store.papers() is not None or not queue_store.enabled():
        return []
    texts = queue_store.pending_texts() + [r["text"] for r in queue_store.at_sea()]
    out = []
    for t in texts:
        line = queue_store.parse_line(t)
        if line["kind"] != "spec":
            continue
        p = paths.resolve("specs") / f"{line['payload']}.yaml"
        if p.exists():
            s = yaml.safe_load(p.read_text(encoding="utf-8"))
            if isinstance(s, dict):
                out.append(s)
    return out


def pinned_steps(rid: str, name: str | None = None, specs: list[dict] | None = None) -> set[int]:
    """The steps of this run a queued or at-sea voyage reads by step: a `seeded_from` naming the run (by id or
    by its name; by name it may mean another run of that name, so it is kept to be safe) with a `step`."""
    specs = _voyages_waiting() if specs is None else specs
    out: set[int] = set()
    for s in specs:
        seed = s.get("seeded_from") or {}
        ref = str(seed.get("run") or "")
        if seed.get("step") is not None and ref and (ref == rid or (name and ref == name)):
            out.add(int(seed["step"]))
    return out


def prune_plan(rid: str, keep_last: int, keep_every: int, pinned: set[int] = frozenset()) -> list[Path]:
    """The checkpoints retention would delete: neither among the newest `keep_last`, nor a multiple of
    `keep_every`, nor pinned, nor the newest."""
    steps = checkpoint_steps(rid)
    keep = set(steps[-max(1, keep_last) :]) | set(pinned)
    if keep_every:
        keep |= {s for s in steps if s % keep_every == 0}
    return [checkpoint_root(rid) / f"step-{s}" for s in steps if s not in keep]


def unscored_steps(rid: str, look) -> set[int]:
    """The steps whose evaluators the loop deferred (eval.offline, item 5) and `thorp score` has not yet all
    scored: a checkpoint step among them is the weights `thorp score` will read, so it is kept until then."""
    plan = offline_plan(rid, look)
    return {s for s, names in plan.items() if not set(names) <= scored_at(rid, s, look)}


def prune_checkpoints(rid: str, keep_last: int, keep_every: int, apply: bool = False, name: str | None = None,
                      look=None) -> list[Path]:  # fmt: skip
    """The checkpoints of `rid` that retention deletes, deleted when `apply`. Kept besides: a step a waiting
    voyage seeds from, and a step whose deferred evaluators are not yet scored (read from `look`, the ledger in
    hand, else the reader). Each is first renamed out of the `step-*` pattern, so a half-deleted one is never
    read as a checkpoint."""
    import shutil

    pinned = pinned_steps(rid, name) | unscored_steps(rid, look if look is not None else reader())
    doomed = prune_plan(rid, keep_last, keep_every, pinned)
    if apply:
        for d in doomed:
            gone = d.with_name(f".{d.name}.pruned")
            d.rename(gone)
            shutil.rmtree(gone)
    return doomed


def retain(spec: dict, rid: str, log, look=None) -> None:
    """After a checkpoint is written: delete what the spec's retention does not keep. Never raises (a failed
    prune keeps every checkpoint, and costs disk, not the voyage)."""
    r = retention(spec)
    if r is None:
        return
    try:
        gone = prune_checkpoints(rid, *r, apply=True, name=spec.get("name"), look=look)
        if gone:
            log(f"checkpoints: pruned {', '.join(d.name for d in gone)} (keep_last {r[0]}, keep_every {r[1]})")
    except Exception as e:  # noqa: BLE001
        log(f"checkpoints: none pruned ({e.__class__.__name__}: {e})")


# Stopping on a signal (11 November, the audit's item 10): neither loop handled SIGTERM, so a preempted box or a
# recalled voyage lost up to a checkpoint's interval of steps. While a voyage trains, SIGTERM and SIGHUP only
# raise a flag: the step under way finishes, the loop flushes, checkpoints that step, writes the run's status as
# `stopped: SIGTERM at step N` and returns, and the process exits 143. A second signal is logged and ignored:
# nothing may cut the checkpoint short. The handlers are put back on leaving, and none is set off the main thread.


class Stop:
    """The flag a signal raises while a voyage trains."""

    def __init__(self):
        self.signal: str | None = None
        self.again: list[str] = []  # signals that came after the first, ignored
        self.log = None


_stops: list[Stop] = []


def stop_flag() -> Stop:
    """The flag the training loop in hand reads: the one `stoppable` set, or one no signal will raise."""
    return _stops[-1] if _stops else Stop()


class stoppable:
    """While inside, SIGTERM and SIGHUP raise `stop_flag()` instead of ending the process."""

    def __enter__(self) -> Stop:
        import contextlib
        import signal
        import threading

        flag, self.old = Stop(), {}

        def say(text: str) -> None:
            with contextlib.suppress(Exception):  # a print inside a print is a RuntimeError: never raise here
                if flag.log:
                    flag.log(text)

        def handler(signum, frame):
            name = signal.Signals(signum).name
            if flag.signal:
                flag.again.append(name)
                say(f"{name} again, while stopping on {flag.signal}: ignored until the checkpoint is written")
                return
            flag.signal = name
            say(f"{name}: the step under way finishes, then a checkpoint, then the voyage stops")

        if threading.current_thread() is threading.main_thread():
            for sig in (signal.SIGTERM, signal.SIGHUP):
                self.old[sig] = signal.signal(sig, handler)
        _stops.append(flag)
        return flag

    def __exit__(self, *exc) -> None:
        import signal

        _stops.pop()
        for sig, was in self.old.items():
            signal.signal(sig, was)


def exit_code(out: dict | None) -> int:
    """The process's exit status for what train returned: 143 (128 + SIGTERM) for a voyage stopped by a signal."""
    return 143 if (out or {}).get("status") == "stopped" else 0


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
    return registry.build(
        m["family"], m["preset"], vocab, m["context"], m.get("positions", "learned"),
        kv_heads=int(m.get("kv_heads") or 0),
        layers=m.get("layers"), width=m.get("width"), heads=m.get("heads"),
    )


def init_model(spec: dict, vocab: int):
    """The run's model at initialisation (its own seed), in its compute precision: the untrained
    floor the probes and the curiosity ladder are measured against. build_model reseeds MLX's
    global generator; that is safe mid-run only because nothing in training draws from it after
    the model is built (the samples evaluator uses explicit keys)."""
    if backend_of(spec) == "torch":
        from thorp import train_torch

        return train_torch.init_model(spec, vocab)
    m = build_model(spec, vocab)
    m.update(to_compute(m.parameters(), spec["optim"].get("precision", "bf16")))
    return m


def to_compute(master, precision: str):
    dt = mx.bfloat16 if precision == "bf16" else mx.float32
    return tree_map(lambda p: p.astype(dt), master)


def parent_run(ref: str, what: str, log=None) -> dict:
    """A parent voyage's run row (a seed, a teacher, a heads' donor). Named by its run id (forty hex characters), it
    is that run, which must be finished; named by name, it is as it always was, the newest finished run with that
    name. A name resolves to whichever run of it finished last (11 November, the audit's item 3: 22 names are
    reused), so the id used is logged here and kept in the voyage's provenance (thorp/versioning.py)."""
    from thorp import versioning

    if versioning.is_run_id(ref):
        rows = reader().get_run(ref)
        if not rows or rows.get("status") != "finished":
            raise LookupError(f"{what}: no finished run {ref}")
    else:
        rows = reader().get_run_by_name(ref, finished=True)
        if not rows:
            raise LookupError(f"{what}: no finished run named {ref!r}")
    if log is not None:
        log(f"{what}: {ref} is run {rows['run_id']}")
    return rows


def seeded_master(spec: dict, seed: dict, master, vocab: int, log, tokeniser_id: str | None = None) -> tuple:
    """The finished run `seed["run"]` grown into this spec's model (thorp/growth.py): the new fp32
    master weights, and {"mask", "values"} for the inherited part (flat, by weight name)."""
    import numpy as np

    from thorp import growth
    from thorp.ledger import spec_of

    rows = parent_run(seed["run"], "seeded_from", log)
    src_spec, src_rid = spec_of(rows), rows["run_id"]
    if src_spec.get("tokeniser", {}).get("vocab") != spec["tokeniser"]["vocab"] or src_spec[
        "tokeniser"
    ].get("train_on") != spec["tokeniser"].get("train_on"):
        raise ValueError("seeded_from: the seed must share this run's tokeniser")
    # the same vocabulary and list are not the same pieces: a cleaning that differs retrains the merges (11
    # November, the return leg: four ids of 2,048 had changed hands). Refuse rather than read the seed's weights
    # through another table; prepare() grafts the seed's pieces, so this only fires when that was bypassed.
    seed_tid = _checkpoint_tokeniser(src_rid)
    if tokeniser_id and seed_tid and not tokmod.same_pieces(seed_tid, tokeniser_id):
        raise ValueError(
            f"seeded_from: {seed['run']} was trained with tokeniser {seed_tid[:12]} and this leg reads with "
            f"{tokeniser_id[:12]}, whose pieces differ: the inherited weights would read other pieces than they learned"
        )
    src_pos = src_spec["model"].get("positions", "learned")
    dst_pos = spec["model"].get("positions", "learned")
    if src_pos != dst_pos:
        raise ValueError("seeded_from: the seed must use the same kind of positions as this run")
    # the shapes the two runs were actually built with: build_model honours the layers/width/heads overrides,
    # so the growth must too (11 November: a seeded voyage with an override grew from the preset's shape)
    def _shape(m: dict) -> dict:
        return {"layers": m.get("layers"), "width": m.get("width"), "heads": m.get("heads")}

    src_cfg = registry.config(
        src_spec["model"]["preset"], vocab, src_spec["model"]["context"], src_pos, **_shape(src_spec["model"])
    )
    dst_cfg = registry.config(
        spec["model"]["preset"], vocab, spec["model"]["context"], dst_pos, **_shape(spec["model"])
    )
    ck = latest_checkpoint(src_rid)
    if seed.get("step") is not None:  # an earlier checkpoint of the seed run (its own lineage)
        ck = checkpoint_root(src_rid) / f"step-{int(seed['step'])}"
        if not (ck / "state.json").exists():
            raise LookupError(
                f"seeded_from: {seed['run']} has no checkpoint at step {seed['step']}"
            )
    src = {k: np.array(v) for k, v in tree_flatten(load_master(ck))}
    dst = {k: np.array(v) for k, v in tree_flatten(master)}
    new, mask = growth.grow(src, src_cfg, dst, dst_cfg)
    share = sum(m.sum() for m in mask.values()) / sum(m.size for m in mask.values())
    log(
        f"seeded from {seed['run']} ({src_rid[:12]}, {src_cfg.layers}x{src_cfg.width}), mode {seed.get('mode', 'free')}: {share:.1%} of the weights inherited"
    )
    # rebuilt on the master's own structure, so empty branches (a rotary layer's "rope": {}) survive
    from mlx.utils import tree_map_with_path

    grown = tree_map_with_path(
        lambda path, v: mx.array(new[path], dtype=mx.float32) if path in new else v, master
    )
    inherit = {
        "mask": {k: mx.array(v, dtype=mx.float32) for k, v in mask.items() if v.any()},
        "values": {k: mx.array(new[k], dtype=mx.float32) for k, v in mask.items() if v.any()},
    }
    return grown, inherit


def load_teacher(teach: dict, spec: dict, vocab: int, log):
    """A finished run's model, frozen, to teach from: same tokeniser, any class."""
    from thorp.ledger import spec_of

    rows = parent_run(teach["run"], "teacher", log)
    t_spec, t_rid = spec_of(rows), rows["run_id"]
    if t_spec["tokeniser"].get("vocab") != spec["tokeniser"]["vocab"] or t_spec["tokeniser"].get(
        "train_on"
    ) != spec["tokeniser"].get("train_on"):
        raise ValueError("teacher: must share this run's tokeniser")
    t_model = build_model(t_spec, vocab)
    t_model.update(
        to_compute(load_master(latest_checkpoint(t_rid)), t_spec["optim"].get("precision", "bf16"))
    )
    t_model.freeze()
    mx.eval(t_model.parameters())
    log(
        f"teacher: {teach['run']} ({t_rid[:12]}), alpha {teach.get('alpha', 0.5)}, temperature {teach.get('temperature', 1.0)}"
    )
    return t_model


def transplant_heads(spec: dict, master, log) -> tuple:
    """Copy a finished run's heads for a star into this model (same class and tokeniser): the heads,
    chosen from the donor's last 'stars' artifact, are the best layer's two strongest for the star
    (one if it alone reaches the star's threshold); their query, key and value rows and their columns
    of the output projection are copied into the same layer and head slots, and with `pos` the
    position embeddings they read too. Returns the new master and a record of what was handed over."""
    import numpy as np

    from thorp.fleet import STARS
    from thorp.ledger import spec_of

    t = spec["transplant"]
    rows = parent_run(t["from_run"], "transplant", log)
    donor_spec, donor_rid = spec_of(rows), rows["run_id"]
    if (
        donor_spec["model"]["preset"] != spec["model"]["preset"]
        or donor_spec["tokeniser"] != spec["tokeniser"]
    ):
        raise ValueError("transplant: the donor must be the same class with the same tokeniser")
    star = t.get("star", "previous_word")
    # the Nevermore's per-head scores live in its own artifact (real prose); the other stars in 'stars'
    kind, key = ("nevermore", "natural_scores") if star == "nevermore" else ("stars", star)
    text = reader().latest_artifact_text(donor_rid, kind)
    if text is None:
        raise LookupError(f"transplant: no {kind!r} artifact on {t['from_run']!r}")
    scores = np.array(json.loads(text)[key])  # layers x heads
    layer = int(np.sort(scores, axis=1)[:, -2:].sum(axis=1).argmax())
    order = list(np.argsort(scores[layer])[::-1])
    heads = order[:1] if scores[layer][order[0]] >= STARS[star].threshold else order[:2]
    donor = dict(tree_flatten(load_master(latest_checkpoint(donor_rid))))
    flat = dict(tree_flatten(master))
    cfg = registry.config(
        spec["model"]["preset"], flat["tok.weight"].shape[0], spec["model"]["context"]
    )
    D, hd = cfg.width, cfg.width // cfg.heads
    qkv, proj = f"layers.{layer}.attn.qkv.weight", f"layers.{layer}.attn.proj.weight"
    q_new, p_new = np.array(flat[qkv]), np.array(flat[proj])
    q_don, p_don = np.array(donor[qkv]), np.array(donor[proj])
    for h in heads:
        for b in range(3):  # q, k, v rows of this head
            r = slice(b * D + h * hd, b * D + (h + 1) * hd)
            q_new[r] = q_don[r]
        p_new[:, h * hd : (h + 1) * hd] = p_don[:, h * hd : (h + 1) * hd]
    flat[qkv], flat[proj] = mx.array(q_new), mx.array(p_new)
    if t.get("pos", True):
        flat["pos.weight"] = donor["pos.weight"]
    if t.get("tok"):  # the deck: the token embeddings the heads learned to read
        flat["tok.weight"] = donor["tok.weight"]
    below = list(range(layer)) if t.get("below") else []
    for (
        i
    ) in below:  # and the layers beneath them, whole, so the stream they read is the one they knew
        for k in [k for k in donor if k.startswith(f"layers.{i}.")]:
            flat[k] = donor[k]
    if t.get("ln", t.get("below")):  # the heads' own LayerNorm, which scales what they read
        flat[f"layers.{layer}.ln1.weight"] = donor[f"layers.{layer}.ln1.weight"]
    handed = {
        "from_run": t["from_run"],
        "from_run_id": donor_rid,
        "star": star,
        "layer": layer,
        "heads": [int(h) for h in heads],
        "donor_scores": [float(scores[layer][h]) for h in heads],
        "pos": bool(t.get("pos", True)),
        "tok": bool(t.get("tok")),
        "below": below,
        "ln": bool(t.get("ln", t.get("below"))),
    }
    log(
        f"transplant: {star} heads {handed['heads']} of layer {layer} from {t['from_run']} (scores {handed['donor_scores']}), position embeddings {'too' if handed['pos'] else 'not'}"
    )
    return tree_unflatten(list(flat.items())), handed


def scale_inherited(grads, mask: dict, scale: float):
    flat = dict(tree_flatten(grads))
    for k, m in mask.items():
        flat[k] = flat[k] * (m * scale + (1.0 - m))
    return tree_unflatten(list(flat.items()))


def shaped_like(loaded, template):
    """`loaded` (a tree rebuilt from a flat checkpoint) in `template`'s shape: every branch the template has is
    kept; where the loaded tree lacks one that holds no arrays (a module with no weights, as nn.RoPE), the
    template's empty branch is put in; a missing branch that does hold weights is an error, as before."""
    if isinstance(template, dict):
        src = loaded if isinstance(loaded, dict) else {}
        out = {}
        for k, v in template.items():
            if k in src:
                out[k] = shaped_like(src[k], v)
            elif not tree_flatten(v):
                out[k] = v
            else:
                raise KeyError(f"the checkpoint has no {k!r}")
        for (
            k,
            v,
        ) in (
            src.items()
        ):  # what the checkpoint holds beyond the template (the step, the learning rate)
            out.setdefault(k, v)
        return out
    if isinstance(template, (list, tuple)):
        src = loaded if isinstance(loaded, (list, tuple)) else []
        out = [
            shaped_like(src[i], v)
            if i < len(src)
            else (v if not tree_flatten(v) else shaped_like(None, v))
            for i, v in enumerate(template)
        ]
        return type(template)(out) if isinstance(template, tuple) else out
    return template if loaded is None else loaded


def restore_inherited(master, inherit: dict):
    flat = dict(tree_flatten(master))
    for k, m in inherit["mask"].items():
        flat[k] = flat[k] * (1.0 - m) + inherit["values"][k] * m
    return tree_unflatten(list(flat.items()))


# the words that open a conclusion: the conclusion-weighted tack (the two-fact problem, round 2)
CONCLUSION_WORDS = (
    "so",
    "therefore",
    "hence",
    "thus",
    "consequently",
    "accordingly",
    "follows",
    "wherefore",
)
CONCLUSION_SPAN = 8  # pieces after the word that count as its conclusion


def conclusion_ids(tok) -> list[int]:
    """The pieces that open a conclusion, as the tokeniser writes them after a space, capitalised or not."""
    out = set()
    for w in CONCLUSION_WORDS:
        for form in (w, w.capitalize()):
            ids = tok.encode(" " + form)
            if (
                len(ids) == 1
            ):  # whole-word pieces only: a fragment of a longer word would mark noise
                out.add(int(ids[0]))
    return sorted(out)


def copy_mask(x, y, kind: str, markers: mx.array | None = None):
    """(batch, time) bool: the guesses the earlier text in the window could answer. "induction": the
    target at t followed an earlier occurrence of the token at t (what a Nevermore can get right);
    "duplicate": the target at t appeared earlier in the window; "conclusion": the target is one of
    the CONCLUSION_SPAN pieces after a word that opens a conclusion ("so", "therefore", "hence"...),
    the moment of concluding, where two facts must be put together."""
    T = x.shape[1]
    if kind == "conclusion":
        if markers is None or markers.size == 0:
            return mx.zeros(x.shape, dtype=mx.bool_)
        is_mark = (x[:, :, None] == markers[None, None, :]).any(axis=-1)  # (batch, time)
        # t is in a conclusion when a marker sits at some j with t - SPAN < j <= t
        win = mx.tril(mx.ones((T, T), dtype=mx.bool_), k=0) & ~mx.tril(
            mx.ones((T, T), dtype=mx.bool_), k=-CONCLUSION_SPAN
        )
        return (is_mark[:, None, :] & win[None, :, :]).any(axis=-1)
    if kind == "induction":
        before = mx.tril(mx.ones((T, T), dtype=mx.bool_), k=-1)  # j < t
        hit = (x[:, :, None] == x[:, None, :]) & (y[:, :, None] == y[:, None, :]) & before
    elif kind == "duplicate":
        upto = mx.tril(mx.ones((T, T), dtype=mx.bool_), k=0)  # j <= t
        hit = (y[:, :, None] == x[:, None, :]) & upto
    else:
        raise ValueError(f"unknown copy_weight kind {kind!r}")
    return hit.any(axis=-1)


def copy_weighted(ce, x, y, cw: dict, markers: mx.array | None = None):
    w = 1.0 + float(cw["alpha"]) * copy_mask(x, y, cw.get("kind", "induction"), markers).astype(
        mx.float32
    )
    return (ce * w).sum() / w.sum()


# ---------------------------------------------------------------- the metre scaffold
# (Justin, 2026-11-07 23:10: "pretraining is broken up into phases, the insertion of the metre topics and then
# normal training on content"). optim.scaffold pulls chosen heads' attention toward a metre card's pattern, a
# rule over the token ids (thorp/viable/s5_policy/deck.py: metre needs no teacher), while the model reads text as
# always. Three phases of one voyage: **metre** (the scaffold at full weight, to `hold` of the voyage), **fade**
# (eased linearly to zero by `fade`), **content** (the language-model loss alone). A card still played after the
# fade is held by heart; `fade: null` never releases it (the ceiling arm). `release` (a share of the voyage, at or
# after `fade`) sets the weight to 0 from there, past any floor: the last stretch read by heart (the 21m, 2026-11-08).
#
#   optim:
#     scaffold:
#       weight: 1.0
#       hold: 0.05
#       fade: 0.25
#       heads: [{layer: 0, head: 0, card: previous_word}, {layer: 1, head: 0, card: induction}]

METRE_PATTERNS = (
    "previous_word", "induction", "duplicate_word", "sink", "delimiter", "words_back",
    "number_spotter", "order_word", "premise_marker", "rare_word",
)  # fmt: skip
RIDDLES = (
    "comparator",
    "bridge",
)  # the riddle cards the scaffold can pull on composed items (thorp/riddles.py)
KEYED = (
    "delimiter",
    "number_spotter",
    "order_word",
    "premise_marker",
)  # a class of pieces, read off the vocabulary


def metre_flags(tok, recipe: list[str]) -> dict:
    """The per-piece tables the keyed metre cards' rules read: a bool per vocabulary id for the delimiter and the
    three word classes (as stars.py and pips.py read them), and for the rare word each piece's rarity on the shelf
    (-log frequency, less the commonest piece's, so the commonest weighs nothing)."""
    from thorp.evaluators import pips, stars

    out = {"delimiter": mx.array(stars.delimiters(tok))}
    for k in ("number_spotter", "order_word", "premise_marker"):
        out[k] = mx.array(pips.flags(tok, k))
    r = stars.rarity(tok, recipe)
    if r is not None:
        out["rare_word"] = mx.array((r - r.min()).astype("float32"))
    return out


def metre_target(x, card: str, flags: dict | None = None):
    """((batch, time, time) target attention, each row summing to 1 or 0; (batch, time) rows that have one): each
    metre card's pattern, a rule over the token ids (thorp/viable/s5_policy/deck.py).

    previous_word: the piece before (t - 1). words_back: two pieces back (t - 2). induction: the pieces that
    followed an earlier copy of this piece (key j where x[j - 1] == x[t] and j <= t). duplicate_word: the earlier
    copies of this piece. sink: the first piece. delimiter, number_spotter, order_word, premise_marker: the earlier
    pieces of the card's class (flags). rare_word: every earlier piece, weighted by its rarity. Shared evenly (or
    by weight) among the keys a row has."""
    B, T = x.shape
    before = mx.tril(mx.ones((T, T), dtype=mx.bool_), k=-1)[None]  # keys j < t
    if card == "previous_word":
        hit = mx.broadcast_to(mx.eye(T, k=-1, dtype=mx.bool_)[None], (B, T, T))
    elif card == "words_back":
        hit = mx.broadcast_to(mx.eye(T, k=-2, dtype=mx.bool_)[None], (B, T, T))
    elif card == "induction":
        eq = x[:, :, None] == x[:, None, :]  # (t, p): the same piece
        shifted = mx.concatenate(
            [mx.zeros((B, T, 1), dtype=mx.bool_), eq[:, :, :-1]], axis=2
        )  # (t, p + 1)
        hit = shifted & mx.tril(mx.ones((T, T), dtype=mx.bool_), k=0)[None]
    elif card == "duplicate_word":
        hit = (x[:, :, None] == x[:, None, :]) & before
    elif card == "sink":
        first = (mx.arange(T)[None, :] == 0) & (mx.arange(T)[:, None] >= 1)
        hit = mx.broadcast_to(first[None], (B, T, T))
    elif card in KEYED:
        if not flags or card not in flags:
            raise ValueError(f"the {card} rule needs its class of pieces (metre_flags)")
        k = flags[card][x]  # (batch, time): the piece is of the class
        hit = k[:, None, :] & before
    elif card == "rare_word":
        if not flags or "rare_word" not in flags:
            raise ValueError("the rare word's rule needs the shelf's rarities (metre_flags)")
        hit = flags["rare_word"][x][:, None, :] * before.astype(mx.float32)
    else:
        raise ValueError(f"no metre pattern for {card!r} (have {', '.join(METRE_PATTERNS)})")
    hit = hit.astype(mx.float32)
    n = hit.sum(axis=-1)
    return hit / mx.maximum(n, 1e-6)[..., None], n > 0


def scaffold_weight(step: int, total: int, sc: dict) -> float:
    """The scaffold's weight at this step: full to hold x total, then linearly down to its floor (0 unless set) at
    fade x total, and the floor after."""
    w = float(sc.get("weight", 1.0))
    rel = sc.get(
        "release"
    )  # the release stage (2026-11-08, the 21m): the pull off from this share of the voyage
    if rel is not None and step >= float(rel) * total:
        return 0.0
    pulse = probe_at(step, total, sc)
    scale = 1.0 if pulse is None else float(pulse.get("to", 0.0))
    fade = sc.get("fade")
    if fade is None:
        return w * scale
    floor = float(sc.get("floor", 0.0))
    hold, end = float(sc.get("hold", 0.0)) * total, float(fade) * total
    if step < hold:
        return w * scale
    if step >= end:
        return floor * scale
    return (floor + (w - floor) * (end - step) / max(end - hold, 1.0)) * scale


def probe_windows(total: int, sc: dict) -> list[tuple[int, int, dict]]:
    """The probe phase (Kipling, aim 4): `probes: [{at, steps, to}]` pulses the pull down for `steps` steps from
    `at` (a share of the voyage), to `to` times its scheduled weight (0 unless set), then lets it return. Each
    window as (first step, first step after it, the probe)."""
    out = []
    for p in sc.get("probes") or []:
        a = int(float(p["at"]) * total)
        out.append((a, a + int(p["steps"]), p))
    return out


def probe_at(step: int, total: int, sc: dict) -> dict | None:
    """The probe this step falls in, if any."""
    for a, b, p in probe_windows(total, sc):
        if a <= step < b:
            return p
    return None


def scaffold_weights(step: int, total: int, sc: dict) -> list[float]:
    """The weight of every pinned head at this step. A head may carry its own `hold`, `fade`, `floor`
    and `release`; anything it does not name falls back to the scaffold's. With no per-head overrides
    this is the old single schedule repeated, so every existing fitout is unchanged (10 November:
    the induction card needed a fade of its own while the basic cards were released)."""
    out = []
    for h in sc.get("heads") or []:
        s = dict(sc)
        for key in ("hold", "fade", "floor", "release"):
            if key in h:
                s[key] = h[key]
        out.append(scaffold_weight(step, total, s))
    return out


def scaffold_phase(step: int, total: int, sc: dict) -> str:
    if sc.get("release") is not None and step >= float(sc["release"]) * total:
        return "release"
    if sc.get("fade") is None or step < float(sc.get("hold", 0.0)) * total:
        return "metre"
    return "fade" if step < float(sc["fade"]) * total else "content"


def scaffold_picks(sc: dict) -> dict[int, list[int]]:
    picks: dict[int, list[int]] = {}
    for h in sc["heads"]:
        picks.setdefault(int(h["layer"]), []).append(int(h["head"]))
    return picks


def scaffold_on(step: int, total: int, sc: dict) -> list[float]:
    """1 for each scaffolded head and riddle whose start (`from`, a share of the voyage; 0 unless set) has come, else
    0 (The Smallest Bridge, 2026-11-08: the Basics first, a Stage 1 only once what it sits on is held): the heads in
    order, then the comparator and the bridge."""
    on = [1.0 if step >= float(h.get("from", 0.0)) * total else 0.0 for h in sc.get("heads") or []]
    rid = sc.get("riddles") or {}
    return on + [
        1.0 if k in rid and step >= float(rid[k].get("from", 0.0)) * total else 0.0 for k in RIDDLES
    ]


def scaffold_head_losses(
    pats: dict, x, sc: dict, targets: dict | None = None, flags: dict | None = None
) -> list:
    """Each scaffolded head's distance from its card: the cross-entropy from the card's pattern to the head's
    attention, over the queries that have a target, whatever the pull's weight. The probe phase reads these
    while the weight is zero: the leak when the pull goes, the recovery when it returns."""
    out = []
    for h in sc["heads"]:
        card = h["card"]
        tgt, has = targets[card] if targets and card in targets else metre_target(x, card, flags)
        p = pats[(int(h["layer"]), int(h["head"]))]
        ce = -(tgt * mx.log(p + 1e-9)).sum(axis=-1)
        hf = has.astype(mx.float32)
        out.append((ce * hf).sum() / mx.maximum(hf.sum(), 1.0))
    return out


def scaffold_loss(
    pats: dict,
    x,
    sc: dict,
    targets: dict | None = None,
    flags: dict | None = None,
    on=None,
    weights=None,
    per_head: list | None = None,
):
    """The mean, over the scaffolded heads (those started, when `on` is given), of the cross-entropy from the card's
    pattern to the head's attention (over the queries that have a target). Its floor is the target's own entropy
    (0 for previous-word). `weights` gives one weight a head, so a card can fade out while another holds (the
    induction's own fade, 10 November). `per_head` passes the heads' distances in when the caller has them."""
    out = per_head if per_head is not None else scaffold_head_losses(pats, x, sc, targets, flags)
    if on is None:
        if weights is None:
            return sum(out) / len(out)
        return sum(weights[i] * v for i, v in enumerate(out)) / len(out)
    denom = mx.maximum(on[: len(out)].sum(), 1.0)
    if weights is None:
        return sum(on[i] * v for i, v in enumerate(out)) / denom
    return sum(weights[i] * on[i] * v for i, v in enumerate(out)) / denom


def check_scaffold(sc: dict, layers: int, heads: int) -> None:
    for h in sc.get("heads") or []:
        if h.get("card") not in METRE_PATTERNS:
            raise ValueError(
                f"scaffold card {h.get('card')!r}: only metre cards with a rule ({', '.join(METRE_PATTERNS)})"
            )
        if not (0 <= int(h["layer"]) < layers and 0 <= int(h["head"]) < heads):
            raise ValueError(f"scaffold head {h} is not in a {layers} x {heads} model")
        # a head may carry its own schedule (10 November, the induction fade)
        for key in ("hold", "fade", "floor"):
            if h.get(key) is not None and not 0.0 <= float(h[key]) <= 1.0:
                raise ValueError(f"scaffold head {h['card']}: {key} must be a share from 0 to 1")
        if h.get("release") is not None:
            rel = float(h["release"])
            fade = h.get("fade", sc.get("fade"))
            if fade is None or not float(fade) <= rel < 1.0:
                raise ValueError(
                    f"scaffold head {h['card']}: release must be at or after its fade's end, under 1"
                )
        if h.get("fade") is not None and h.get("hold") is not None:
            if float(h["fade"]) < float(h["hold"]):
                raise ValueError(f"scaffold head {h['card']}: fade before hold")
    for x in [*(sc.get("heads") or []), *(sc.get("riddles") or {}).values()]:
        if not 0.0 <= float(x.get("from", 0.0)) < 1.0:
            raise ValueError(
                f"scaffold start {x}: `from` is a share of the voyage, from 0 to under 1"
            )
    if not sc.get("heads") and not sc.get("riddles"):
        raise ValueError("scaffold names no heads")
    last = -1.0
    for p in sc.get("probes") or []:
        if not 0.0 <= float(p.get("at", -1)) < 1.0 or int(p.get("steps", 0)) < 1:
            raise ValueError(f"scaffold probe {p}: `at` is a share of the voyage, `steps` at least 1")
        if not 0.0 <= float(p.get("to", 0.0)) < 1.0:
            raise ValueError(f"scaffold probe {p}: `to` scales the pull down, from 0 to under 1")
        if float(p["at"]) <= last:
            raise ValueError(f"scaffold probe {p}: the probes are in order and do not repeat")
        last = float(p["at"])
    if sc.get("release") is not None:
        rel = float(sc["release"])
        if not float(sc.get("fade") or 0.0) <= rel < 1.0:
            raise ValueError(
                f"scaffold release {rel}: a share of the voyage at or after the fade's end, under 1"
            )
    for key, r in (sc.get("riddles") or {}).items():
        if key not in RIDDLES:
            raise ValueError(f"scaffold riddle {key!r}: the riddles are {', '.join(RIDDLES)}")
        if not 0 <= int(r["layer"]) < layers or ("head" in r and not 0 <= int(r["head"]) < heads):
            raise ValueError(f"scaffold riddle {key} {r} is not in a {layers} x {heads} model")


def run_evaluators(spec, rid, step, model, prep, rec: Ledger, log, total: bool = True) -> dict:
    """Run the spec's evaluators at `step` and record what each returns. Beside the step's `eval/seconds` it
    records `eval/seconds/<evaluator>` (11 November, item 5: the ledger held only the total, so which evaluator
    cost a voyage its hours could not be read), written only when that evaluator returned, so the per-evaluator
    figure also marks a step as scored on it (`score`). `total=False` (an offline score) leaves the step's
    `eval/seconds`, the loop's own cost, as the loop wrote it."""
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
        options=dict((spec.get("eval") or {}).get("options") or {}),
    )
    if "ce_bpb" in spec["eval"]["evaluators"]:  # the only evaluator that writes evals rows, so a
        # re-score with others alone (bpb_split, laws) leaves the step's scores in place
        rec.clear_step(rid, step, tables=("evals",), sets=list(prep.eval_sets))
    t0 = time.time()
    merged = {}
    took: dict[str, float] = {}
    for name in spec["eval"]["evaluators"]:
        t1 = time.time()
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
        took[f"eval/seconds/{name}"] = time.time() - t1
    rec.metrics(rid, step, ({"eval/seconds": time.time() - t0} if total else {}) | took)
    log(f"eval @ {step}: " + ", ".join(f"{k}={v:.4f}" for k, v in merged.items()))
    return merged


# ---------------------------------------------------------------- offline evaluation (11 November, item 5)
#
# The evaluators ran inside the loop: 39% of the 50m reading stage's hired hours, 80% of the torch 9m parity run.
# `eval.offline: [names]` takes the named evaluators out of the loop. At each evaluation step that would have run
# them, the loop keeps the weights instead (the step's checkpoint when it is a checkpoint step, else a weights-only
# snapshot `eval-<step>` beside the checkpoints) and records an `eval_offline` artifact naming what it deferred.
# `thorp score <run>` (train.score) then scores those steps from the saved weights, writing the metrics at the step
# the loop would have, and removes each snapshot once every evaluator deferred at its step has been scored. A spec
# without the key evaluates exactly as before.

SNAPSHOT_PREFIX = "eval-"


def offline_evaluators(spec: dict) -> list[str]:
    """eval.offline, checked: the names the loop defers to `thorp score`. ce_bpb stays in the loop (it is the score
    that may stop a voyage, and the milestones read it); a name the loop would never run is a mistake, not a no-op."""
    ev = spec.get("eval") or {}
    off = list(ev.get("offline") or [])
    if not off:
        return []
    if "ce_bpb" in off:
        raise ValueError("eval.offline: ce_bpb is the loop's own score and stays in the loop")
    ran = set(ev.get("evaluators") or []) | set((ev.get("light") or {}).get("evaluators") or [])
    stray = [n for n in off if n not in ran]
    if stray:
        raise ValueError(f"eval.offline names {stray}, which are not among the voyage's evaluators")
    return off


def save_snapshot(rid: str, step: int, master, torch: bool = False) -> Path:
    """`eval-<step>`: the master weights only, as a checkpoint's model.safetensors (no optimiser state), written to a
    temporary name and renamed, so a reader never sees half of one. `master` is the MLX loop's tree of fp32 weights,
    or, with `torch`, the torch loop's dict of fp32 tensors."""
    import shutil

    d = checkpoint_root(rid) / f"{SNAPSHOT_PREFIX}{step}"
    tmp = d.with_name(d.name + ".tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    if torch:
        from thorp.train_torch import save_flat

        save_flat(tmp / "model.safetensors", {k: v.detach().cpu().numpy() for k, v in master.items()})
    else:
        mx.save_safetensors(str(tmp / "model.safetensors"), dict(tree_flatten(master)))
    (tmp / "state.json").write_text(json.dumps({"run_id": rid, "step": step, "weights_only": True}, indent=1))
    if d.exists():
        shutil.rmtree(d)
    tmp.rename(d)
    return d


def evaluate_in_loop(
    spec, rid, step, model, prep, rec: Ledger, log, names: list[str], offline: list[str], saved: bool, master
) -> dict:
    """One of the loop's evaluations: `names` at `step`, except those in eval.offline. With nothing offline it is
    run_evaluators exactly as the loop called it before. A deferred evaluator's weights are the step's checkpoint
    when `saved` (the loop writes it straight after), else `master` is written as the snapshot eval-<step>."""
    if spec["eval"]["evaluators"] == names:
        full = spec
    else:  # a light evaluation, as the loop has always built it
        full = {**spec, "eval": {**spec["eval"], "evaluators": names}}
    later = [n for n in names if n in offline]
    if not later:
        return run_evaluators(full, rid, step, model, prep, rec, log)
    now = [n for n in names if n not in offline]
    latest = (
        run_evaluators({**spec, "eval": {**spec["eval"], "evaluators": now}}, rid, step, model, prep, rec, log)
        if now
        else {}
    )
    where = f"step-{step}" if saved else save_snapshot(rid, step, master, backend_of(spec) == "torch").name
    rec.artifact(rid, step, "eval_offline", where, "", json.dumps({"evaluators": later, "weights": where}))
    log(f"eval @ {step}: {', '.join(later)} deferred to `thorp score` ({where})")
    return latest


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
                "bytes": prep.tokeniser.text_bytes(b) if prep.tokeniser else books[b].bytes,
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
    from thorp import library  # the library aboard this voyage, as it was when it sailed

    rec.artifact(rid, 0, "library", "", "", json.dumps(library.carried(spec), ensure_ascii=False))
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
    if (
        backend_of(spec) == "torch"
    ):  # the same loop on PyTorch, for NVIDIA GPUs (thorp/train_torch.py)
        from thorp import train_torch

        return train_torch.train(spec, prep, rec, stop_after=stop_after, log=log)
    from thorp.ledger import MetricBuffer, flush_every

    rec = rec or recorder()
    # the per-step metrics, written `ledger.flush_every` steps at a time (11 November, item 4); whatever waits is
    # written on the way out of an exception too, before it reaches the caller (which marks the run failed)
    buf = MetricBuffer(rec, every=flush_every(spec))
    with stoppable():  # SIGTERM/SIGHUP: checkpoint the step under way and stop (item 10)
        try:
            return _train(spec, prep, rec, buf, stop_after, log)
        except BaseException:
            buf.flush_quietly()
            raise


def _train(spec: dict, prep: Prepared, rec: Ledger, buf, stop_after: int | None, log) -> dict:
    """train's MLX loop; `buf` holds the per-step metrics until they are flushed."""
    rid = run_id(spec)
    rec = rec or recorder()
    log = log or Log(paths.runs_dir() / f"{rid}.log")
    buf.log = log
    o, m = spec["optim"], spec["model"]
    precision = o.get("precision", "bf16")
    tok = prep.tokeniser
    books = prep.books()
    families = {b: books[b].family for b in books}
    stages = spec["data"].get("stages")
    if stages:  # training stages, read in order under one schedule (data.Staged)
        stream = data.Staged(
            stages,
            [
                data.stream(
                    ids,
                    tok.id,
                    spec["seed"] * 1000 + i,
                    o["batch_tokens"],
                    m["context"],
                    st["passes"],
                    families,
                )
                for i, (st, ids) in enumerate(zip(stages, prep.stage_recipes, strict=True))
            ],
        )
    else:
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
    # the window lengthened for the voyage's end, when the spec says so (data.stretched; 12 November, kipling:9)
    stream = data.stretched(
        stream, spec, tok.id, list(prep.stage_recipes) if stages else [list(prep.recipe)], families
    )
    total = stream.total_steps

    model = build_model(spec, tok.vocab_size)
    counts = model.parameter_counts()
    master = tree_map(lambda p: p.astype(mx.float32), model.parameters())
    opt = optim.AdamW(learning_rate=o["lr"], betas=list(o["betas"]), weight_decay=o["weight_decay"])

    start, tokens_seen, wall_before = 0, 0, 0.0
    ckpt = latest_checkpoint(rid)
    seed = spec.get("seeded_from")  # grow a finished smaller run into this model (growth.py)
    inherit = None
    if seed:
        grown, inherit = seeded_master(spec, seed, master, tok.vocab_size, log, tokeniser_id=tok.id)
        if ckpt is None:
            master = grown
    handed = None
    if (
        spec.get("transplant") and ckpt is None
    ):  # hand over another run's trick (Magician's Apprentice)
        master, handed = transplant_heads(spec, master, log)
    if ckpt is not None:
        st = json.loads((ckpt / "state.json").read_text())
        from thorp import versioning

        # the checkpoint's tokeniser against the one this sailing built, before anything is truncated: a list
        # edited under the same run id would otherwise resume the weights on other pieces (11 November, item 3)
        if why := versioning.tokeniser_mismatch(st, tok.id):
            raise ValueError(why)
        start, tokens_seen, wall_before = st["step"], st["tokens_seen"], st["wall_seconds"]
        # both rebuilt on the model's own tree: a checkpoint is a flat file, which cannot hold a module with no
        # weights (nn.RoPE: an empty `rope` in every layer), so every rotary voyage failed to resume (8 November,
        # leg 1b: KeyError 'rope' at its first step after the Postgres switch)
        master = shaped_like(load_master(ckpt), master)
        opt.init(master)
        opt.state = shaped_like(
            tree_unflatten(list(mx.load(str(ckpt / "optimizer.safetensors")).items())), opt.state
        )
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
            "sop_version": spec.get("sop"),
            "commit": git_commit(),
            "hardware": hardware(),
            "status": "running",
            "started": None if (rec.get_run(rid) or {}).get("started") else now(),
        }
    )
    if start == 0:
        rec.truncate_after(rid, -1)
        record_setup(spec, rid, prep, stream, counts, rec)
        if hasattr(stream, "record"):  # the stages, with the steps each covers
            rec.artifact(rid, 0, "stages", "", "", json.dumps(stream.record()))
        if (
            handed is not None
        ):  # after the step-0 clear-out, or it is wiped (as on 7 November, 08:19)
            rec.artifact(rid, 0, "transplant", "", "", json.dumps(handed))
    # what the id does not pin, written beside it (11 November, item 3); never raises
    from thorp import versioning

    versioning.record_provenance(spec, rid, tok.id, rec, log, start=start)
    # the run's state (with a heartbeat) and its expedition, as rows beside it (11 November, item 11); never raises
    from thorp import run_state

    run_state.started(spec, rid, rec, log)
    log(
        f"run {rid} ({spec.get('name')}): {m['preset']} {counts}, {total} steps x "
        f"{stream.tokens_per_step} tokens, {stream.unique_tokens} unique tokens/pass"
    )

    cw = o.get("copy_weight")  # the copy-weighted tack (2026-11-07): {"alpha": a, "kind": ...}
    markers = (
        mx.array(conclusion_ids(tok), dtype=mx.int32)
        if cw and cw.get("kind") == "conclusion"
        else None
    )
    if markers is not None:
        log(f"conclusion-weighted tack: {markers.size} marker pieces, alpha {cw['alpha']}")
    teach = o.get(
        "teacher"
    )  # learning from a teacher run's predictions (2026-11-07): {run, alpha, temperature}
    teacher = load_teacher(teach, spec, tok.vocab_size, log) if teach else None

    sc = o.get(
        "scaffold"
    )  # the metre scaffold (2026-11-07): {weight, hold, fade, floor, heads, sample, riddles}
    picks, flags, sample, riddle_cfg, pools = None, None, None, {}, {}
    probing = False  # the probe phase: the pull pulsed down, each pinned head's distance logged every step
    if sc:
        check_scaffold(sc, model.cfg.layers, model.cfg.heads)
        picks = scaffold_picks(sc) if sc.get("heads") else None
        probing = bool(picks and sc.get("probes"))
        if any(h["card"] in KEYED or h["card"] == "rare_word" for h in sc.get("heads") or []):
            flags = metre_flags(tok, list(prep.recipe))
        sample = sc.get(
            "sample"
        )  # {windows, length}: the metre pull read on part of the batch (the full deck)
        riddle_cfg = sc.get("riddles") or {}
        if riddle_cfg:
            from thorp import riddles

            makers = {"comparator": riddles.comparator_items, "bridge": riddles.bridge_items}

            def maker(
                k, r
            ):  # the Bridge in all four relations, by `kinds: all` (2026-11-08, after leg 0)
                return (
                    riddles.bridge_items_all
                    if k == "bridge" and r.get("kinds") == "all"
                    else makers[k]
                )

            pools = {
                k: maker(k, r)(tok, int(r.get("pool", 2048)), seed=int(r.get("seed", 1)))
                for k, r in riddle_cfg.items()
            }
            for k, pool in pools.items():
                if pool["tokens"].shape[1] > m["context"]:
                    raise ValueError(
                        f"the {k} riddle's items run to {pool['tokens'].shape[1]} pieces, past the context ({m['context']})"
                    )
        where = ", ".join(
            f"{h['card']} on layer {h['layer']} head {h['head']}" for h in sc.get("heads") or []
        )
        until = f"faded out by {sc['fade']}" if sc.get("fade") is not None else "never released"
        if sc.get("floor"):
            until += f" to a floor of {sc['floor']}"
        if sc.get("release") is not None:
            until += f", released (weight 0) from {sc['release']}"
        log(f"metre scaffold: {where}; weight {sc.get('weight', 1.0)} to {sc.get('hold', 0)} of the voyage, {until}"
            + (f"; read on {sample['windows']} windows of {sample['length']}" if sample else "")
            + "".join(f"; riddle {k} on layer {r['layer']}" + (f" head {r['head']}" if "head" in r else " (logit lens)")
                      + f", {len(pools[k]['q'])} composed items" for k, r in riddle_cfg.items()))  # fmt: skip

    def riddle_losses(mdl, rb):
        """The riddles' pulls on this step's composed items: the comparator's head onto the year to exceed; the
        bridge's logit lens preferring the middle term to the distractor."""
        out = []
        for key in ("comparator", "bridge"):
            r = riddle_cfg.get(key)
            if r is None:
                out.append(mx.array(0.0))
                continue
            w = float(r.get("weight", 1.0))
            if key == "comparator":
                t, q, m = rb["comparator"]
                li, hi = int(r["layer"]), int(r["head"])
                _, pats = mdl.forward_attending(t, {li: [hi]})
                p = pats[(li, hi)]
                row = mx.take_along_axis(
                    p, mx.broadcast_to(q[:, None, None], (p.shape[0], 1, p.shape[2])), axis=1
                )[:, 0, :]
                out.append(w * (-(m * mx.log(row + 1e-9)).sum(axis=-1)).mean())
            else:
                t, q, bb, dd = rb["bridge"]
                h = mdl.hidden(t)[int(r["layer"])]
                hq = mx.take_along_axis(
                    h, mx.broadcast_to(q[:, None, None], (h.shape[0], 1, h.shape[2])), axis=1
                )[:, 0, :]
                lg = mdl.tok.as_linear(mdl.ln_f(hq)).astype(mx.float32)
                lp = lg - mx.logsumexp(lg, axis=-1, keepdims=True)
                diff = (
                    mx.take_along_axis(lp, bb[:, None], axis=1)[:, 0]
                    - mx.take_along_axis(lp, dd[:, None], axis=1)[:, 0]
                )
                out.append(w * mx.logaddexp(mx.array(0.0), -diff).mean())
        return out

    staged = bool(sc) and (
        any("from" in h for h in sc.get("heads") or [])
        or any("from" in r for r in riddle_cfg.values())
    )

    def scaffold_targets(x):
        """The teacher's own heads as the scaffold's target (the third way to push a bigger ship's cards into a
        smaller one, 8 November: "all the metre cards from 50m being pushed into Pan early"). The heads themselves
        cannot be copied across classes (the 50m is 12x8x64, Pan 2x2x32), so what transfers is the distribution the
        donating head puts on the same tokens — what the card does, not the weights that do it. A head with no
        `teacher_head` falls back to its card's rule, so one arm may mix the two."""
        if teacher is None:
            return None
        t_picks: dict[int, list[int]] = {}
        for h in sc.get("heads") or []:
            if h.get("teacher_head") is not None:
                t_picks.setdefault(int(h["teacher_layer"]), []).append(int(h["teacher_head"]))
        if not t_picks:
            return None
        _, tp = teacher.forward_attending(x, t_picks)
        out = {}
        for h in sc["heads"]:
            if h.get("teacher_head") is None:
                continue
            a = mx.stop_gradient(
                tp[(int(h["teacher_layer"]), int(h["teacher_head"]))].astype(mx.float32)
            )
            out[h["card"]] = (a, mx.ones(a.shape[:-1], dtype=mx.float32))
        return out

    def loss_fn(mdl, x, y, sw, hw, rb, on):
        # (batch, time) -> the mean per window, so the loss can be attributed to the window's book;
        # every window is the same length, so the mean of the window means is the batch mean.
        dist = []  # each pinned head's distance from its card, whatever the weight (the probe phase reads it)
        # the stretch's long windows read no pinned head's map: the pull is zero by then at every class, and each map
        # is a (windows, length, length) array (data.Stretched; a probing voyage cannot stretch)
        long = x.shape[1] > int(m["context"])
        if picks and not sample and not long:
            logits, pats = mdl.forward_attending(x, picks)
            dist = scaffold_head_losses(pats, x, sc, scaffold_targets(x), flags)
            sl = scaffold_loss(
                pats, x, sc, on=on if staged else None, weights=hw, per_head=dist,
            )
        elif picks and not long:  # the pull read on part of the batch: a second, smaller forward pass
            logits = mdl(x)
            xs = x[: int(sample["windows"]), : int(sample["length"])]
            _, pats = mdl.forward_attending(xs, picks)
            dist = scaffold_head_losses(pats, xs, sc, scaffold_targets(xs), flags)
            sl = scaffold_loss(
                pats, xs, sc, on=on if staged else None, weights=hw, per_head=dist,
            )
        else:
            logits, sl = mdl(x), mx.array(0.0)
        riddle = riddle_losses(mdl, rb) if riddle_cfg else [mx.array(0.0), mx.array(0.0)]
        if staged:  # a riddle pulls only once its start has come
            riddle = [riddle[0] * on[-2], riddle[1] * on[-1]]
        parts = [sl] + riddle
        ce = nn.losses.cross_entropy(logits.astype(mx.float32), y, reduction="none")
        per_window = ce.mean(axis=1)
        if teacher is not None and float(teach.get("alpha", 0.5)) > 0:
            # distillation: the student's loss is (1 - alpha) x its own cross-entropy plus alpha x
            # the KL divergence from the teacher's softened bets to its own (times T^2, so the
            # gradient's size does not shrink with the temperature)
            T, a = float(teach.get("temperature", 1.0)), float(teach.get("alpha", 0.5))
            t_logits = mx.stop_gradient(teacher(x).astype(mx.float32)) / T
            s_logits = logits.astype(mx.float32) / T
            t_lp = t_logits - mx.logsumexp(t_logits, axis=-1, keepdims=True)
            s_lp = s_logits - mx.logsumexp(s_logits, axis=-1, keepdims=True)
            kl = (mx.exp(t_lp) * (t_lp - s_lp)).sum(axis=-1).mean()
            base = (1 - a) * per_window.mean() + a * T * T * kl
        elif not cw or not cw.get("alpha"):
            base = per_window.mean()
        else:
            # the copy-weighted tack: guesses the earlier text in the window could answer weigh
            # 1 + alpha, the rest 1, normalised by the total weight so the tack's size is comparable.
            # The per-window losses (and so the logged loss) stay unweighted.
            base = copy_weighted(ce, x, y, cw, markers)
        # the metre scaffold: the heads carry their own weights (the induction's fade), the riddles the
        # voyage's; zero in the content phase
        pull = parts[0] + sw * (parts[1] + parts[2]) if riddle_cfg else parts[0]
        if probing:  # a probing voyage logs every pinned head's distance beside the three parts
            parts = parts + [mx.stop_gradient(d) for d in dist]
        return base + pull, per_window, mx.stack(parts)

    value_and_grad = nn.value_and_grad(model, loss_fn)
    step_fn = mx.compile(
        lambda x, y, sw, hw, rb, on: value_and_grad(model, x, y, sw, hw, rb, on),
        inputs=model.state,
        outputs=model.state,
    )
    no_riddles = {
        "comparator": (mx.zeros((1, 2), dtype=mx.int32),) * 3,
        "bridge": (mx.zeros((1, 2), dtype=mx.int32),) * 4,
    }

    def riddle_batch(step: int) -> dict:
        if not riddle_cfg:
            return no_riddles
        from thorp import riddles

        out = dict(no_riddles)
        for key, r in riddle_cfg.items():
            d = riddles.draw(pools[key], step, int(r.get("items", 16)))
            if key == "comparator":
                out[key] = (mx.array(d["tokens"]), mx.array(d["q"]), mx.array(d["target"]))
            else:
                out[key] = (
                    mx.array(d["tokens"]),
                    mx.array(d["q"]),
                    mx.array(d["b"]),
                    mx.array(d["d"]),
                )
        return out

    groups = model.param_groups()
    # the sieves: the weights as they stood at the last record, so the move per group is measured
    prev_flat, prev_step = dict(tree_flatten(master)), start
    prev_delta: dict = {}  # the last window's move per weight, for the heading sieve
    # the loss per book: window losses summed per recipe book since the last record
    book_loss: dict[int, float] = {}
    book_n: dict[int, int] = {}
    every_eval = spec["eval"]["every_steps"]
    light = spec["eval"].get("light")  # {"every_steps": N, "evaluators": [...]}, optional
    offline = offline_evaluators(spec)  # eval.offline: scored later from saved weights (`thorp score`)
    every_ckpt = spec["checkpoint"]["every_steps"]
    stop = stop_flag()  # raised by SIGTERM/SIGHUP (stoppable): checkpoint this step and stop
    stop.log = log
    # per-voyage milestones (12 November): judged at the first evaluation at or after their step, and a
    # missed one that asks for a recall stops the voyage here, at a checkpoint
    from thorp import milestones as milestones_mod

    ms = milestones_mod.declared(spec, total)
    judged_milestones: set[int] = set()
    t_run = time.time()

    step = start
    for batch in stream.iter_from(start):
        t0 = time.time()
        lr = lr_at(step, total, o)
        opt.learning_rate = lr
        tokens = mx.array(batch.tokens)
        sw = scaffold_weight(step, total, sc) if sc else 0.0
        hw_list = scaffold_weights(step, total, sc) if sc else []
        (loss, per_window, sl), grads = step_fn(
            tokens[:, :-1],
            tokens[:, 1:],
            mx.array(sw, dtype=mx.float32),
            mx.array(hw_list, dtype=mx.float32),
            riddle_batch(step),
            mx.array(scaffold_on(step, total, sc) if staged else [1.0], dtype=mx.float32),
        )
        grads = tree_map(lambda g: g.astype(mx.float32), grads)
        grads, gnorm = optim.clip_grad_norm(grads, o["grad_clip"])
        if inherit and seed.get("mode") == "slow":  # the inherited weights learn at lr_scale
            grads = scale_inherited(grads, inherit["mask"], float(seed.get("lr_scale", 0.1)))
        master = opt.apply_gradients(grads, master)
        if inherit and seed.get("mode") == "freeze":  # the inherited weights stay as they were
            master = restore_inherited(master, inherit)
        model.update(to_compute(master, precision))
        mx.eval(loss, per_window, gnorm, master, opt.state)
        step += 1
        for bi, lw in zip(batch.book_index.tolist(), per_window.tolist(), strict=True):
            book_loss[bi] = book_loss.get(bi, 0.0) + lw
            book_n[bi] = book_n.get(bi, 0) + 1
        tokens_seen += stream.tokens_per_step
        dt = time.time() - t0
        loss_v = (
            per_window.mean().item() if (cw and cw.get("alpha")) or teach or sc else loss.item()
        )
        if not math.isfinite(loss_v):
            raise FloatingPointError(f"loss is {loss_v} at step {step}")
        vals = {
            "loss": loss_v,
            "lr": lr,
            "step_ms": dt * 1000,
            "tokens_per_s": stream.tokens_per_step / dt,
            "tokens_seen": tokens_seen,
        }
        if sc:  # the scaffold's weight, how far the heads are from its pattern, and the phase (0 metre, 1 fade, 2 content)
            vals["scaffold/weight"] = sw
            for h, w in zip(sc.get("heads") or [], hw_list):
                vals[f"scaffold/weight/{h['card']}"] = w
            if staged:
                vals["scaffold/started"] = float(sum(scaffold_on(step - 1, total, sc)))
            parts = sl.tolist()
            vals["scaffold/loss"] = parts[0]
            for key, v in zip(("comparator", "bridge"), parts[1:3], strict=True):
                if key in riddle_cfg:
                    vals[f"scaffold/riddle/{key}"] = v
            if probing:
                vals["scaffold/probe"] = 1.0 if probe_at(step - 1, total, sc) else 0.0
                for h, v in zip(sc.get("heads") or [], parts[3:]):
                    vals[f"scaffold/distance/{h['card']}/l{h['layer']}h{h['head']}"] = v
            vals["scaffold/phase"] = float(
                ("metre", "fade", "content", "release").index(scaffold_phase(step - 1, total, sc))
            )
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
                    # the heading sieve (2026-11-07): the cosine between this window's move and the
                    # last window's, per group. Near 1 the tacks keep one angle (the layer has found
                    # its heading); near 0 they wander; below 0 they come about.
                    if prev_delta and all(k in prev_delta for k in keys):
                        dot = sum(
                            ((mflat[k] - prev_flat[k]) * prev_delta[k]).sum().item() for k in keys
                        )
                        pdn = math.sqrt(
                            sum((prev_delta[k] * prev_delta[k]).sum().item() for k in keys)
                        )
                        if un and pdn:
                            vals[f"heading/{g}"] = dot / (un * pdn)
            if step % METRICS_EVERY == 0:
                prev_delta = (
                    {k: mflat[k] - prev_flat[k] for k in mflat if k in prev_flat}
                    if step - prev_step == METRICS_EVERY
                    else {}
                )
                prev_flat, prev_step = mflat, step
            if hasattr(stream, "stages"):
                vals["stage"] = float(batch.stage)
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
        buf.add(rid, step, vals)  # written with the next flush (MetricBuffer), not a commit a step
        run_state.beat(rid, rec)  # the heartbeat: one upsert at most a minute, else a clock read (item 11)

        latest: dict | None = None
        if step % every_eval == 0 or step == total:
            buf.flush()  # an evaluation, and anyone reading the store meanwhile, sees every step before it
            latest = evaluate_in_loop(
                spec, rid, step, model, prep, rec, log, spec["eval"]["evaluators"], offline,
                step % every_ckpt == 0 or step == total, master,
            )  # fmt: skip
        elif light and step % light["every_steps"] == 0:
            # a light eval between full ones (eval.light, 2026-11-07): only the cheap evaluators,
            # such as the Nevermores, so a lean run can still be watched forming
            buf.flush()
            latest = evaluate_in_loop(
                spec, rid, step, model, prep, rec, log, light["evaluators"], offline,
                step % every_ckpt == 0 or step == total, master,
            )  # fmt: skip
        recall_reason = None
        if ms and latest:
            # a bug in a milestone must never cost a night's training: it is reported and the voyage
            # sails on (the gate that stops a run is policy, not bookkeeping)
            try:
                verdicts = milestones_mod.check(ms, step, latest, judged_milestones)
                if verdicts:
                    milestones_mod.record(verdicts, rid, rec, log)
                    recall_reason = milestones_mod.recall_reason(verdicts)
            except Exception as e:  # noqa: BLE001
                log(f"milestones: {e.__class__.__name__}: {e}")
        stopping = stop.signal is not None and step < total  # read once: a signal from here on waits a step
        if step % every_ckpt == 0 or step == total or recall_reason or stopping:
            # every row up to this step is in the store before the checkpoint exists, or a resume from it would
            # leave a gap (it forgets only what lies after its step): strict, so it raises rather than sail past
            buf.flush(strict=True)
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
            retain(spec, rid, log, rec)  # checkpoint.keep_last / keep_every; nothing without them
        if stopping and not recall_reason:
            wall = wall_before + time.time() - t_run
            rec.run(
                {
                    "run_id": rid,
                    "status": f"stopped: {stop.signal} at step {step}",
                    "tokens_seen": tokens_seen,
                    "wall_minutes": wall / 60,
                    "commit": git_commit(),
                }
            )
            log(f"stopped at step {step} by {stop.signal}: checkpointed, to resume from {d.name}")
            run_state.ended(rid, f"stopped: {stop.signal} at step {step}", rec, log)  # item 11's state row
            return {"run_id": rid, "step": step, "status": "stopped", "signal": stop.signal}
        if recall_reason:
            wall = wall_before + time.time() - t_run
            rec.run(
                {
                    "run_id": rid,
                    "finished": now(),
                    "status": f"recalled: {recall_reason}",
                    "tokens_seen": tokens_seen,
                    "wall_minutes": wall / 60,
                    "commit": git_commit(),
                }
            )
            log(f"recalled at step {step}: {recall_reason}")
            run_state.ended(rid, f"recalled: {recall_reason}", rec, log)
            return {"run_id": rid, "step": step, "status": "recalled", "reason": recall_reason}
        if stop_after is not None and step >= stop_after:
            buf.flush(strict=True)
            log(f"stopping at step {step} (stop_after)")
            return {"run_id": rid, "step": step, "status": "running"}

    buf.flush(strict=True)
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
    run_state.ended(rid, "finished", rec, log)
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

    rec = rec or recorder()
    # a run id, a unique prefix of one, or a run name (2026-11-07: queue lines are written by name)
    row = reader().find_run(run)
    if not row:
        raise LookupError(f"no run {run}")
    spec, rid = spec_of(row), row["run_id"]
    from thorp import ladder
    ladder.ensure(spec)  # a rescore backfills the ladder the voyage was missing
    ckpt = latest_checkpoint(rid)
    if ckpt is not None:
        ladder.repair_spec(spec, rid)  # an old checkpoint's shape, not today's preset
    if ckpt is None:
        raise LookupError(f"run {rid} has no checkpoint")
    if sets:
        spec["eval"] = {**spec["eval"], "sets": list(sets)}
    if evaluators:
        spec["eval"] = {**spec["eval"], "evaluators": list(evaluators)}
    prep = prepare(spec, resolver=resolver, log=log, known=True, sailed=rid)
    step = json.loads((ckpt / "state.json").read_text())["step"]
    model = scoring_model(spec, prep.tokeniser.vocab_size, ckpt)
    if sets:
        record_eval_sets(rid, step, prep, rec)
    run_evaluators(spec, rid, step, model, prep, rec, log)
    return step


def scoring_model(spec: dict, vocab: int, ckpt: Path, model=None):
    """The run's model in its compute precision with a checkpoint's (or an eval snapshot's) weights, as the loop held
    it at that step. Either backend's weights load in the torch model. `model`, when given, is reused."""
    if backend_of(spec) == "torch":
        from thorp import train_torch

        if model is None:
            return train_torch.load_model(spec, vocab, ckpt)
        train_torch.set_weights(model, train_torch.load_master(ckpt, model.device))
        return model
    model = model if model is not None else build_model(spec, vocab)
    model.update(to_compute(load_master(ckpt), spec["optim"].get("precision", "bf16")))
    return model


def saved_weights(rid: str) -> dict[int, Path]:
    """Every finished set of weights a run has on disk, by step: its checkpoints (step-N) and its eval snapshots
    (eval-N; where both exist, the snapshot, which is the one to consume). A name still being written (`.tmp`) or
    without its state.json is not finished and is left out, so a voyage at sea is read safely."""
    root = checkpoint_root(rid)
    out: dict[int, Path] = {}
    if not root.is_dir():
        return out
    for p in sorted(root.iterdir()):
        for prefix in ("step-", SNAPSHOT_PREFIX):
            n = p.name.removeprefix(prefix)
            if n != p.name and n.isdigit() and (p / "state.json").exists() and (p / "model.safetensors").exists():
                if prefix == SNAPSHOT_PREFIX or int(n) not in out:
                    out[int(n)] = p
    return out


def offline_plan(rid: str, look) -> dict[int, list[str]]:
    """step -> the evaluators the loop deferred there (its `eval_offline` artifacts), in the loop's order."""
    plan: dict[int, list[str]] = {}
    for r in look.query(
        "select step, text from artifacts where run_id=? and kind='eval_offline' order by step", [rid]
    ):
        names = plan.setdefault(int(r["step"]), [])
        names += [n for n in json.loads(r["text"] or "{}").get("evaluators") or [] if n not in names]
    return plan


def scored_at(rid: str, step: int, look) -> set[str]:
    """The evaluators that have returned at a step: those with an `eval/seconds/<name>` there."""
    rows = look.query(
        "select distinct name from metrics where run_id=? and step=? and name like 'eval/seconds/%'", [rid, step]
    )
    return {r["name"].removeprefix("eval/seconds/") for r in rows}


def score(
    run: str,
    steps: str = "pending",
    evaluators: list[str] | None = None,
    keep_snapshots: bool = False,
    resolver: ListResolver = gutenberg_resolver,
    rec: Ledger | None = None,
    log=print,
) -> list[int]:
    """`thorp score`: run evaluators on a run's saved weights and record them at those steps, as the loop would have
    (11 November, item 5). Returns the steps scored.

    `steps` is "pending" (every step whose deferred evaluators have not all returned), "all" (every step the loop
    deferred, again), or "N,M". `evaluators` replaces the deferred names (and with "all"/"pending" reaches every
    saved step, checkpoints included, so a run with no eval.offline can be scored this way too). The step's
    `eval/seconds` is the loop's and is left alone; each evaluator's own `eval/seconds/<name>` is written. A
    snapshot (eval-N) is removed once every evaluator deferred at its step has returned, unless `keep_snapshots`;
    a checkpoint is never removed. Safe while the voyage is at sea: it reads only finished weights."""
    import shutil

    from thorp import ladder
    from thorp.ledger import spec_of

    look = reader() if rec is None else rec
    rec = rec or recorder()
    row = look.find_run(run)
    if not row:
        raise LookupError(f"no run {run}")
    spec, rid = spec_of(row), row["run_id"]
    plan, weights, want = offline_plan(rid, look), saved_weights(rid), list(evaluators or [])
    if not want and not plan:
        raise LookupError(
            f"run {rid[:12]} deferred no evaluators (no eval.offline): name --evaluators to score its checkpoints"
        )
    if steps in ("all", "pending"):
        chosen = sorted(set(weights) if want else set(plan))
    else:
        chosen = sorted({int(x) for x in str(steps).split(",") if x.strip()})
    todo: dict[int, list[str]] = {}
    for s in chosen:
        names = want or plan.get(s, [])
        if steps == "pending":
            done = scored_at(rid, s, look)
            names = [n for n in names if n not in done]
        if not names:
            continue
        if s not in weights:
            log(f"step {s}: no finished weights on disk (still being written, or not kept); skipped")
            continue
        todo[s] = names
    if not todo:
        log(f"{rid[:12]}: nothing to score")
        return []
    ladder.repair_spec(spec, rid)  # an old checkpoint's shape, not today's preset (a no-op for a current one)
    prep = prepare(spec, resolver=resolver, log=log, known=True, sailed=rid)
    model = None
    for s, names in todo.items():
        model = scoring_model(spec, prep.tokeniser.vocab_size, weights[s], model)
        log(f"score {rid[:12]} @ {s} ({weights[s].name}): {', '.join(names)}")
        run_evaluators(
            {**spec, "eval": {**spec["eval"], "evaluators": names}}, rid, s, model, prep, rec, log, total=False
        )
        snap = weights[s]
        if snap.name.startswith(SNAPSHOT_PREFIX) and s in plan and not keep_snapshots:
            left = [n for n in plan[s] if n not in scored_at(rid, s, look)]
            if left:
                log(f"step {s}: {snap.name} kept; not yet scored: {', '.join(left)}")
            else:
                shutil.rmtree(snap, ignore_errors=True)
                log(f"step {s}: {snap.name} removed")
    return list(todo)


def run(spec_path: str | Path, rec: Ledger | None = None) -> dict:
    """One voyage. S2 (thorp/liberty_machine.py): it takes the helm first, so one voyage is at sea at a time."""
    from thorp import liberty_machine

    name = load_spec(spec_path).get("name") or str(spec_path)
    with liberty_machine.at_sea(name):
        return _run(spec_path, rec)


def _run(spec_path: str | Path, rec: Ledger | None = None) -> dict:
    spec = load_spec(spec_path)
    from thorp import ladder
    ladder.ensure(spec)  # Ogden/Kipling voyages carry the whole quantum ladder
    if backend_of(spec) != "torch":
        # MLX's free-buffer cache defaults to its memory limit, and that limit is the GPU's
        # recommended working set (26.8 GB on this Mac). A run therefore keeps every buffer it has
        # ever freed: the 21m held 24.3 GB from step 1, macOS was left to swap around it, and a step
        # that could not get its allocation stalled for 1,009 s (9 November). Cap the cache so freed
        # buffers go back to the OS; `model.cache_gb` overrides the 4 GB default.
        mx.set_cache_limit(int(float(spec["model"].get("cache_gb", 4))) << 30)
    rid = run_id(spec)
    rec = rec or recorder()
    existing = rec.get_run(rid)
    if existing and existing["status"] == "finished":
        print(json.dumps({k: v for k, v in existing.items() if k != "spec_json"}, indent=1))
        try:  # the same id over other list bytes: said loudly, never re-sailed (11 November, item 3)
            from thorp import versioning

            versioning.warn_if_lists_changed(rid, rec)
        except Exception as e:  # noqa: BLE001
            print(f"provenance: lists not compared ({e.__class__.__name__}: {e})")
        return existing
    log = Log(paths.runs_dir() / f"{rid}.log")
    log(f"spec {spec_path} -> run id {rid}")
    try:  # the plan's version, 1.2.3 (thorp/versioning.py): a numbering that never blocks a run
        from thorp import versioning

        log(f"version {versioning.assign(spec, run_id=rid, spec_path=str(spec_path))}")
    except Exception as e:  # noqa: BLE001
        log(f"version: not assigned ({e})")
    try:  # every run sails on a ship: a class and a fitout (thorp/fleet.py); never blocks a run
        from thorp import fleet

        ship = fleet.ship_for(
            spec, expedition=fleet.expedition_of_spec(spec)
        )
        log(f"ship {ship.name} ({ship.key}): {ship.subtitle}")
    except Exception as e:  # noqa: BLE001
        log(f"ship not registered: {e!r}")
    prep = prepare(spec, log=log)
    for name, miss in prep.missing.items():
        if miss:
            log(f"missing from {name}: {miss}")
    try:
        return train(spec, prep, rec, log=log)
    except Exception as e:
        rec.run({"run_id": rid, "status": f"failed: {e.__class__.__name__}"})
        log(f"FAILED: {e!r}")
        # the final state beside the status (11 November, item 11); never raises
        from thorp import run_state

        run_state.ended(rid, f"failed: {e.__class__.__name__}", rec, log, reason=f"failed: {e!r}"[:500])
        raise


if __name__ == "__main__":
    sys.exit(exit_code(run(sys.argv[1])))  # 143 when a signal stopped it at a checkpoint, else 0 as before

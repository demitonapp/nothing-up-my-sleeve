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
    "fitout",  # the named fitout a voyage is a variation of (S5 policy 'fitout'): a label, so naming it moves no id
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


def prepare(spec: dict, resolver: ListResolver = gutenberg_resolver, log=print) -> Prepared:
    d = spec["data"]
    # S3, the gate (thorp/vsm.py): every enforced S5 policy applied to a new run, before it reads a page
    from thorp import vsm

    known = bool(Ledger().query("select 1 from runs where run_id=? limit 1", [run_id(spec)]))
    for note in vsm.gate(spec, known_run=known):
        log(f"S3 gate: {note}")
    stage_recipes = [resolver(st["recipe"]) for st in d.get("stages", [])]
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

    clean = cleaning.version_of(spec)  # data.clean: the text as read, training and held-out decks alike
    if clean != "raw":  # a raw voyage keeps its old tokeniser id
        settings["clean"] = clean
    log(f"cleaning: {clean}")
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
    return registry.build(
        m["family"], m["preset"], vocab, m["context"], m.get("positions", "learned")
    )


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


def seeded_master(spec: dict, seed: dict, master, vocab: int, log) -> tuple:
    """The finished run `seed["run"]` grown into this spec's model (thorp/growth.py): the new fp32
    master weights, and {"mask", "values"} for the inherited part (flat, by weight name)."""
    import numpy as np

    from thorp import growth
    from thorp.ledger import spec_of

    rows = Ledger().query(
        "select * from runs where name=? and status='finished' order by started desc", [seed["run"]]
    )
    if not rows:
        raise LookupError(f"seeded_from: no finished run named {seed['run']!r}")
    src_spec, src_rid = spec_of(rows[0]), rows[0]["run_id"]
    if src_spec.get("tokeniser", {}).get("vocab") != spec["tokeniser"]["vocab"] or src_spec[
        "tokeniser"
    ].get("train_on") != spec["tokeniser"].get("train_on"):
        raise ValueError("seeded_from: the seed must share this run's tokeniser")
    src_pos = src_spec["model"].get("positions", "learned")
    dst_pos = spec["model"].get("positions", "learned")
    if src_pos != dst_pos:
        raise ValueError("seeded_from: the seed must use the same kind of positions as this run")
    src_cfg = registry.config(
        src_spec["model"]["preset"], vocab, src_spec["model"]["context"], src_pos
    )
    dst_cfg = registry.config(spec["model"]["preset"], vocab, spec["model"]["context"], dst_pos)
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

    rows = Ledger().query(
        "select * from runs where name=? and status='finished' order by started desc",
        [teach["run"]],
    )
    if not rows:
        raise LookupError(f"teacher: no finished run named {teach['run']!r}")
    t_spec, t_rid = spec_of(rows[0]), rows[0]["run_id"]
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
    rows = Ledger().query(
        "select * from runs where name=? and status='finished' order by started desc",
        [t["from_run"]],
    )
    if not rows:
        raise LookupError(f"transplant: no finished run named {t['from_run']!r}")
    donor_spec, donor_rid = spec_of(rows[0]), rows[0]["run_id"]
    if (
        donor_spec["model"]["preset"] != spec["model"]["preset"]
        or donor_spec["tokeniser"] != spec["tokeniser"]
    ):
        raise ValueError("transplant: the donor must be the same class with the same tokeniser")
    star = t.get("star", "previous_word")
    # the Nevermore's per-head scores live in its own artifact (real prose); the other stars in 'stars'
    kind, key = ("nevermore", "natural_scores") if star == "nevermore" else ("stars", star)
    art = Ledger().query(
        "select text from artifacts where run_id=? and kind=? order by step desc, rowid desc limit 1",
        [donor_rid, kind],
    )
    scores = np.array(json.loads(art[0]["text"])[key])  # layers x heads
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
# fade is held by heart; `fade: null` never releases it (the ceiling arm).
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
RIDDLES = ("comparator", "bridge")  # the riddle cards the scaffold can pull on composed items (thorp/riddles.py)
KEYED = ("delimiter", "number_spotter", "order_word", "premise_marker")  # a class of pieces, read off the vocabulary


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
        shifted = mx.concatenate([mx.zeros((B, T, 1), dtype=mx.bool_), eq[:, :, :-1]], axis=2)  # (t, p + 1)
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
    fade = sc.get("fade")
    if fade is None:
        return w
    floor = float(sc.get("floor", 0.0))
    hold, end = float(sc.get("hold", 0.0)) * total, float(fade) * total
    if step < hold:
        return w
    if step >= end:
        return floor
    return floor + (w - floor) * (end - step) / max(end - hold, 1.0)


def scaffold_phase(step: int, total: int, sc: dict) -> str:
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
    return on + [1.0 if k in rid and step >= float(rid[k].get("from", 0.0)) * total else 0.0 for k in RIDDLES]


def scaffold_loss(pats: dict, x, sc: dict, targets: dict | None = None, flags: dict | None = None, on=None):
    """The mean, over the scaffolded heads (those started, when `on` is given), of the cross-entropy from the card's
    pattern to the head's attention (over the queries that have a target). Its floor is the target's own entropy
    (0 for previous-word)."""
    out = []
    for h in sc["heads"]:
        card = h["card"]
        tgt, has = targets[card] if targets and card in targets else metre_target(x, card, flags)
        p = pats[(int(h["layer"]), int(h["head"]))]
        ce = -(tgt * mx.log(p + 1e-9)).sum(axis=-1)
        hf = has.astype(mx.float32)
        out.append((ce * hf).sum() / mx.maximum(hf.sum(), 1.0))
    if on is None:
        return sum(out) / len(out)
    return sum(on[i] * v for i, v in enumerate(out)) / mx.maximum(on[: len(out)].sum(), 1.0)


def check_scaffold(sc: dict, layers: int, heads: int) -> None:
    for h in sc.get("heads") or []:
        if h.get("card") not in METRE_PATTERNS:
            raise ValueError(f"scaffold card {h.get('card')!r}: only metre cards with a rule ({', '.join(METRE_PATTERNS)})")
        if not (0 <= int(h["layer"]) < layers and 0 <= int(h["head"]) < heads):
            raise ValueError(f"scaffold head {h} is not in a {layers} x {heads} model")
    for x in [*(sc.get("heads") or []), *(sc.get("riddles") or {}).values()]:
        if not 0.0 <= float(x.get("from", 0.0)) < 1.0:
            raise ValueError(f"scaffold start {x}: `from` is a share of the voyage, from 0 to under 1")
    if not sc.get("heads") and not sc.get("riddles"):
        raise ValueError("scaffold names no heads")
    for key, r in (sc.get("riddles") or {}).items():
        if key not in RIDDLES:
            raise ValueError(f"scaffold riddle {key!r}: the riddles are {', '.join(RIDDLES)}")
        if not 0 <= int(r["layer"]) < layers or ("head" in r and not 0 <= int(r["head"]) < heads):
            raise ValueError(f"scaffold riddle {key} {r} is not in a {layers} x {heads} model")


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
    rid = run_id(spec)
    rec = rec or Ledger()
    log = log or Log(paths.runs_dir() / f"{rid}.log")
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
        grown, inherit = seeded_master(spec, seed, master, tok.vocab_size, log)
        if ckpt is None:
            master = grown
    handed = None
    if (
        spec.get("transplant") and ckpt is None
    ):  # hand over another run's trick (Magician's Apprentice)
        master, handed = transplant_heads(spec, master, log)
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
        if hasattr(stream, "record"):  # the stages, with the steps each covers
            rec.artifact(rid, 0, "stages", "", "", json.dumps(stream.record()))
        if (
            handed is not None
        ):  # after the step-0 clear-out, or it is wiped (as on 7 November, 08:19)
            rec.artifact(rid, 0, "transplant", "", "", json.dumps(handed))
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

    sc = o.get("scaffold")  # the metre scaffold (2026-11-07): {weight, hold, fade, floor, heads, sample, riddles}
    picks, flags, sample, riddle_cfg, pools = None, None, None, {}, {}
    if sc:
        check_scaffold(sc, model.cfg.layers, model.cfg.heads)
        picks = scaffold_picks(sc) if sc.get("heads") else None
        if any(h["card"] in KEYED or h["card"] == "rare_word" for h in sc.get("heads") or []):
            flags = metre_flags(tok, list(prep.recipe))
        sample = sc.get("sample")  # {windows, length}: the metre pull read on part of the batch (the full deck)
        riddle_cfg = sc.get("riddles") or {}
        if riddle_cfg:
            from thorp import riddles

            makers = {"comparator": riddles.comparator_items, "bridge": riddles.bridge_items}

            def maker(k, r):  # the Bridge in all four relations, by `kinds: all` (2026-11-08, after leg 0)
                return riddles.bridge_items_all if k == "bridge" and r.get("kinds") == "all" else makers[k]

            pools = {k: maker(k, r)(tok, int(r.get("pool", 2048)), seed=int(r.get("seed", 1))) for k, r in riddle_cfg.items()}
            for k, pool in pools.items():
                if pool["tokens"].shape[1] > m["context"]:
                    raise ValueError(f"the {k} riddle's items run to {pool['tokens'].shape[1]} pieces, past the context ({m['context']})")
        where = ", ".join(f"{h['card']} on layer {h['layer']} head {h['head']}" for h in sc.get("heads") or [])
        until = f"faded out by {sc['fade']}" if sc.get("fade") is not None else "never released"
        if sc.get("floor"):
            until += f" to a floor of {sc['floor']}"
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
                row = mx.take_along_axis(p, mx.broadcast_to(q[:, None, None], (p.shape[0], 1, p.shape[2])), axis=1)[:, 0, :]
                out.append(w * (-(m * mx.log(row + 1e-9)).sum(axis=-1)).mean())
            else:
                t, q, bb, dd = rb["bridge"]
                h = mdl.hidden(t)[int(r["layer"])]
                hq = mx.take_along_axis(h, mx.broadcast_to(q[:, None, None], (h.shape[0], 1, h.shape[2])), axis=1)[:, 0, :]
                lg = mdl.tok.as_linear(mdl.ln_f(hq)).astype(mx.float32)
                lp = lg - mx.logsumexp(lg, axis=-1, keepdims=True)
                diff = mx.take_along_axis(lp, bb[:, None], axis=1)[:, 0] - mx.take_along_axis(lp, dd[:, None], axis=1)[:, 0]
                out.append(w * mx.logaddexp(mx.array(0.0), -diff).mean())
        return out

    staged = bool(sc) and (any("from" in h for h in sc.get("heads") or []) or any("from" in r for r in riddle_cfg.values()))

    def loss_fn(mdl, x, y, sw, rb, on):
        # (batch, time) -> the mean per window, so the loss can be attributed to the window's book;
        # every window is the same length, so the mean of the window means is the batch mean.
        if picks and not sample:
            logits, pats = mdl.forward_attending(x, picks)
            sl = scaffold_loss(pats, x, sc, flags=flags, on=on if staged else None)
        elif picks:  # the pull read on part of the batch: a second, smaller forward pass
            logits = mdl(x)
            xs = x[: int(sample["windows"]), : int(sample["length"])]
            _, pats = mdl.forward_attending(xs, picks)
            sl = scaffold_loss(pats, xs, sc, flags=flags, on=on if staged else None)
        else:
            logits, sl = mdl(x), mx.array(0.0)
        riddle = riddle_losses(mdl, rb) if riddle_cfg else [mx.array(0.0), mx.array(0.0)]
        if staged:  # a riddle pulls only once its start has come
            riddle = [riddle[0] * on[-2], riddle[1] * on[-1]]
        parts = [sl] + riddle
        ce = nn.losses.cross_entropy(logits.astype(mx.float32), y, reduction="none")
        per_window = ce.mean(axis=1)
        if teacher is not None:
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
        # the metre scaffold (and the riddles) ride on top, at this step's weight (zero in the content phase)
        pull = parts[0] + parts[1] + parts[2] if riddle_cfg else parts[0]
        return base + sw * pull, per_window, mx.stack(parts)

    value_and_grad = nn.value_and_grad(model, loss_fn)
    step_fn = mx.compile(
        lambda x, y, sw, rb, on: value_and_grad(model, x, y, sw, rb, on), inputs=model.state, outputs=model.state
    )
    no_riddles = {"comparator": (mx.zeros((1, 2), dtype=mx.int32),) * 3, "bridge": (mx.zeros((1, 2), dtype=mx.int32),) * 4}

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
                out[key] = (mx.array(d["tokens"]), mx.array(d["q"]), mx.array(d["b"]), mx.array(d["d"]))
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
    every_ckpt = spec["checkpoint"]["every_steps"]
    t_run = time.time()

    step = start
    for batch in stream.iter_from(start):
        t0 = time.time()
        lr = lr_at(step, total, o)
        opt.learning_rate = lr
        tokens = mx.array(batch.tokens)
        sw = scaffold_weight(step, total, sc) if sc else 0.0
        (loss, per_window, sl), grads = step_fn(
            tokens[:, :-1], tokens[:, 1:], mx.array(sw, dtype=mx.float32), riddle_batch(step),
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
        loss_v = per_window.mean().item() if (cw and cw.get("alpha")) or teach or sc else loss.item()
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
            if staged:
                vals["scaffold/started"] = float(sum(scaffold_on(step - 1, total, sc)))
            parts = sl.tolist()
            vals["scaffold/loss"] = parts[0]
            for key, v in zip(("comparator", "bridge"), parts[1:], strict=True):
                if key in riddle_cfg:
                    vals[f"scaffold/riddle/{key}"] = v
            vals["scaffold/phase"] = float(("metre", "fade", "content").index(scaffold_phase(step - 1, total, sc)))
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
        rec.metrics(rid, step, vals)

        if step % every_eval == 0 or step == total:
            run_evaluators(spec, rid, step, model, prep, rec, log)
        elif light and step % light["every_steps"] == 0:
            # a light eval between full ones (eval.light, 2026-11-07): only the cheap evaluators,
            # such as the Nevermores, so a lean run can still be watched forming
            run_evaluators(
                {**spec, "eval": {**spec["eval"], "evaluators": light["evaluators"]}},
                rid,
                step,
                model,
                prep,
                rec,
                log,
            )
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
    # a run id, a unique prefix of one, or a run name (2026-11-07: queue lines are written by name)
    rows = rec.query("select * from runs where name = ? order by started desc", [run]) or rec.query(
        "select * from runs where run_id like ? order by started desc", [run + "%"]
    )
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
    """One voyage. S2 (thorp/vsm.py): it takes the helm first, so one voyage is at sea at a time."""
    from thorp import vsm

    name = load_spec(spec_path).get("name") or str(spec_path)
    with vsm.at_sea(name):
        return _run(spec_path, rec)


def _run(spec_path: str | Path, rec: Ledger | None = None) -> dict:
    spec = load_spec(spec_path)
    rid = run_id(spec)
    rec = rec or Ledger()
    existing = rec.get_run(rid)
    if existing and existing["status"] == "finished":
        print(json.dumps({k: v for k, v in existing.items() if k != "spec_json"}, indent=1))
        return existing
    log = Log(paths.runs_dir() / f"{rid}.log")
    log(f"spec {spec_path} -> run id {rid}")
    try:  # every run sails on a ship: a class and a fitout (thorp/fleet.py); never blocks a run
        from thorp import fleet

        ship = fleet.ship_for(
            spec, voyage=fleet.expedition_of_label(spec.get("name"), spec.get("ship"))
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
        raise


if __name__ == "__main__":
    run(sys.argv[1])

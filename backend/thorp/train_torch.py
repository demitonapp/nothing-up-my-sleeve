"""The training loop of train.py on PyTorch, for NVIDIA GPUs (CUDA), with the CPU for the tests.

Chosen per voyage by `model.backend: torch` in the spec (part of the run id) or THORP_BACKEND=torch in the
environment (not part of it): thorp/models/backend.py. train.train hands such a voyage here; everything
that is not arithmetic (the spec, preparation, the data stream, the ledger, the evaluators, the scaffold's
schedule and checks) is train.py's own, imported, so the two loops cannot drift apart on those.

What is the same as the MLX loop, by construction:
- the model (thorp/models/gpt_torch.py: the same architecture, parameter names and shapes);
- fp32 master weights, the model computing in the spec's precision (bf16 unless fp32), gradients taken
  through the compute weights and cast to fp32;
- the optimiser: MLX's AdamW exactly (decoupled decay applied first, no bias correction), and MLX's
  clip_grad_norm (scale by max_norm / (norm + 1e-6) when above);
- every loss term: cross-entropy, distillation from a teacher, the copy-weighted tack (induction,
  duplicate, conclusion), the metre scaffold with its phases and starts, each head's own schedule, a teacher's
  heads as targets and the probe phase, the comparator and bridge riddles;
- checkpoints: the same files (model.safetensors, optimizer.safetensors, state.json) with the same names
  (MLX's optimizer layout: "<param>.m", "<param>.v", "step", "learning_rate"), so a checkpoint written by
  either backend resumes or is scored by the other;
- the ledger rows: the same metric names every step and every METRICS_EVERY steps (the sieves).

What this loop has not been taught it refuses (refuse_unsupported, below): a spec is read against the keys the loop
honours before any work is done, so a key train.py learns and this file does not is an error here, never a voyage
that quietly trains something else.

What is not: the random initialisation (torch's generator, not MLX's, so a torch voyage starts from other
weights unless it is seeded from a checkpoint) and the floating-point order of the kernels.
"""

from __future__ import annotations

import json
import math
import os
import resource
import shutil
import sys
import time

import numpy as np
import torch
import torch.nn.functional as F

from thorp import data, paths
from thorp import train as T
from thorp.ledger import Ledger, reader, recorder
from thorp.models import registry

# ---------------------------------------------------------------- what this loop honours (refuse, never ignore)
# The two loops are typed twice, so a key taught to train.py is not known here until someone types it again. Until
# 11 November this loop passed over such keys in silence: a spec with shared key/value heads, a head's own fade or a
# teacher's attention as the target trained another shape or another objective on a hired box than on the Mac, under
# the same run id. So the loop now reads a spec against the list of what it honours before it does any work, and
# refuses the voyage, naming every key, when the spec asks for something it would not do.
#
# HONOURED is every key this loop (and the shared code it calls) reads, dotted, a list's items as "[]". A key is added
# here when the loop is taught it AND a test in tests/test_torch.py holds it to the MLX loop's numbers. UNSUPPORTED is
# for a key the MLX loop honours and this one is known not to: the reason is given to whoever sails the spec.


def _honoured() -> frozenset[str]:
    def under(path: str, keys: str) -> list[str]:
        return [f"{path}.{k}" for k in keys.split()]

    riddle = "layer head weight items pool seed kinds from"
    return frozenset(
        # the top level: every key that is part of the run id (the labels, train.NOT_HASHED, are never refused)
        "data tokeniser model optim eval checkpoint seed sop departures seeded_from transplant ledger".split()
        # goal: the expedition goal a voyage serves, read by the queue (queue_store, priorities.py), never the loop
        + ["goal"]
        # the 50m's abilities as a leg declares them (12 November, kipling:14): read by the charter and the evaluators,
        # never by the loop, which trains a leg on its stages alone
        + ["thinking", "tools"]
        + under("thinking", "open close share")
        + under("tools", "set about")
        # (data.turns: the turn format the voyage was taught, read by thorp/turns.py for the evaluators, not here)
        + under("data", "recipe passes order refuse clean opt_in first first_repeats stages turns")
        + under("data.stages[]", "name recipe passes")
        # eval.offline (11 November, item 5): those evaluators are scored later from saved weights (train.score)
        # eval.targets (12 November, the charter's bar): the marks a ship is judged against, read by the charter
        + under("eval", "sets every_steps evaluators light options offline targets")
        + under("eval.light", "every_steps evaluators")
        # keep_last / keep_every: checkpoint retention, train.retain, called by both loops (11 November, item 10)
        + under("checkpoint", "every_steps keep_last keep_every")
        # a voyage's milestones (thorp/milestones.py), judged by both loops alike (11 November, item 10)
        + ["milestones"]
        + under("milestones[]", "at step metric at_least at_most if_missed why")
        # how many steps' metrics are written at once (ledger.MetricBuffer, 11 November): when, never what
        + under("ledger", "flush_every")
        # cache_gb is MLX's free-buffer cache (train._run): there is nothing of it to honour here
        + under("model", "family preset context positions backend layers width heads kv_heads cache_gb stretch")
        # the window lengthened for the voyage's end (data.Stretched, 12 November): both loops read it
        + under("model.stretch", "to at")
        + under(
            "optim",
            "name lr betas weight_decay warmup_steps schedule min_lr_ratio batch_tokens grad_clip precision "
            "copy_weight teacher scaffold",
        )
        + under("optim.copy_weight", "alpha kind")
        + under("optim.teacher", "run alpha temperature")
        + under("optim.scaffold", "weight hold fade floor release heads sample riddles probes")
        + under("optim.scaffold.heads[]", "layer head card from hold fade floor release teacher_layer teacher_head")
        + under("optim.scaffold.probes[]", "at steps to")
        + under("optim.scaffold.sample", "windows length")
        + under("optim.scaffold.riddles", " ".join(T.RIDDLES))
        + [k for r in T.RIDDLES for k in under(f"optim.scaffold.riddles.{r}", riddle)]
        + under("seeded_from", "run step mode lr_scale")
        + under("transplant", "from_run star pos tok below ln")
    )


HONOURED = _honoured()
# read by shared code only (the tokeniser, the evaluators' options, the declared departures): not this loop's to judge
OPAQUE = frozenset({"tokeniser", "departures", "eval.options"})
# key -> (why this loop cannot honour it, the values that leave it switched off). Empty since 11 November: the keys
# it held that day (model.kv_heads, a head's own hold/fade/floor/release, a head's teacher_layer/teacher_head, the
# scaffold's probes, and sop for the run row) were each taught to the loop and taken out as their tests passed.
UNSUPPORTED: dict[str, tuple[str, tuple]] = {}


class UnsupportedSpec(ValueError):
    """A spec asks for something the torch loop does not do."""


def _spec_keys(block: dict, path: str = ""):
    """Every key of a spec with its value, dotted ("optim.scaffold.heads[].fade"): a dict's keys, and those of each
    dict in a list. The labels and the blocks only shared code reads are single keys, not looked into."""
    for k, v in block.items():
        p = f"{path}.{k}" if path else str(k)
        yield p, v
        if p in OPAQUE or (not path and k in T.NOT_HASHED):
            continue
        if isinstance(v, dict):
            yield from _spec_keys(v, p)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    yield from _spec_keys(item, p + "[]")


def refuse_unsupported(spec: dict) -> None:
    """Raise UnsupportedSpec, naming every key, when the spec asks for something this loop would not do: a key in
    UNSUPPORTED that is switched on, a key this loop has never been taught (not in HONOURED), or a model family with
    no torch model. A key that is absent, null or at its off value is never refused, nor is a label. Pure Python: it
    reads the spec and nothing else, so the charter asks it before a box is hired."""
    found: dict[str, str] = {}
    for path, v in _spec_keys(spec):
        if v is None or path in T.NOT_HASHED:
            continue
        if any(path.startswith((known + ".", known + "[]")) for known in found):
            continue  # what lies under a key already refused needs no line of its own
        if path in UNSUPPORTED:
            why, off = UNSUPPORTED[path]
            if v not in off and v != [] and v != {}:
                found[path] = why
        elif path not in HONOURED:
            found[path] = "a key this loop has not been taught"
    family = (spec.get("model") or {}).get("family")
    if family is not None and family not in registry.TORCH_FAMILIES:
        found["model.family"] = (
            f"no torch model of the family {family!r} (have: {', '.join(sorted(registry.TORCH_FAMILIES))})"
        )
    if found:
        raise UnsupportedSpec(
            f"the torch loop cannot honour {spec.get('name') or 'this spec'}: "
            + "; ".join(f"{k} ({why})" for k, why in found.items())
            + ". The MLX loop (thorp/train.py) is the reference: sail it there, or teach thorp/train_torch.py the "
            "key, hold it to MLX's numbers in tests/test_torch.py and add it to HONOURED (a key only shared code "
            "reads, as the tokeniser's or an evaluator's, is added to HONOURED with a note of who reads it)."
        )


# ---------------------------------------------------------------- the device


def device() -> torch.device:
    """THORP_DEVICE when set (cuda, cuda:1, cpu, mps), else the first CUDA GPU, else the CPU."""
    want = os.environ.get("THORP_DEVICE")
    if want:
        return torch.device(want)
    return torch.device("cuda" if torch.cuda.is_available() else "cpu")


def compute_dtype(precision: str) -> torch.dtype:
    return torch.bfloat16 if precision == "bf16" else torch.float32


def hardware(dev: torch.device) -> str:
    """train.hardware (the Mac's profile; 'unknown' elsewhere) and the torch device the voyage ran on."""
    where = torch.cuda.get_device_name(dev) if dev.type == "cuda" else dev.type
    return f"{T.hardware()} · torch {torch.__version__} on {where}"


def peak_memory_gb(dev: torch.device) -> float:
    if dev.type == "cuda":
        return torch.cuda.max_memory_allocated(dev) / 1e9
    rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss  # bytes on macOS, KiB on Linux
    return rss / 1e9 if sys.platform == "darwin" else rss * 1024 / 1e9


# ---------------------------------------------------------------- models and checkpoints


def build_model(spec: dict, vocab: int, dev: torch.device | None = None):
    m = spec["model"]
    torch.manual_seed(spec["seed"])
    model = registry.build(
        m["family"],
        m["preset"],
        vocab,
        m["context"],
        m.get("positions", "learned"),
        backend="torch",
        kv_heads=int(m.get("kv_heads") or 0),
        layers=m.get("layers"),
        width=m.get("width"),
        heads=m.get("heads"),
    )
    return model.to(dev or device())


def init_model(spec: dict, vocab: int):
    """The run's model at initialisation (its own seed), in its compute precision (train.init_model)."""
    model = build_model(spec, vocab)
    return model.to(compute_dtype(spec["optim"].get("precision", "bf16")))


def load_flat(path) -> dict[str, np.ndarray]:
    from safetensors.numpy import load_file

    return load_file(str(path))


def save_flat(path, flat: dict[str, np.ndarray]) -> None:
    from safetensors.numpy import save_file

    # (np.ascontiguousarray would make a scalar, the optimiser's step, one-dimensional)
    save_file({k: np.ascontiguousarray(v) if v.ndim else v for k, v in flat.items()}, str(path))


def load_master(ckpt, dev: torch.device | None = None) -> dict[str, torch.Tensor]:
    dev = dev or device()
    return {
        k: torch.from_numpy(v.astype(np.float32)).to(dev)
        for k, v in load_flat(ckpt / "model.safetensors").items()
    }


def set_weights(model, master: dict[str, torch.Tensor]) -> None:
    """Copy the fp32 master weights into the model's parameters, cast to their dtype."""
    params = dict(model.named_parameters())
    missing = set(params) - set(master)
    if missing:
        raise KeyError(f"checkpoint lacks {sorted(missing)}")
    with torch.no_grad():
        for k, p in params.items():
            p.copy_(master[k])


def load_model(spec: dict, vocab: int, ckpt):
    """A run's model from a checkpoint (either backend's), in its compute precision: rescore, teachers."""
    model = init_model(spec, vocab)
    set_weights(model, load_master(ckpt, model.device))
    return model


def save_checkpoint(rid: str, step: int, master: dict, opt: AdamW, state: dict):
    d = T.checkpoint_root(rid) / f"step-{step}"
    tmp = d.with_name(d.name + ".tmp")
    tmp.mkdir(parents=True, exist_ok=True)
    save_flat(tmp / "model.safetensors", {k: v.detach().cpu().numpy() for k, v in master.items()})
    save_flat(tmp / "optimizer.safetensors", opt.state_flat())
    (tmp / "state.json").write_text(json.dumps(state, indent=1))
    if d.exists():
        shutil.rmtree(d)
    tmp.rename(d)
    return d


# ---------------------------------------------------------------- the optimiser (MLX's, exactly)


class AdamW:
    """mlx.optimizers.AdamW with its defaults (eps 1e-8, bias_correction False): w <- w (1 - lr wd), then
    m <- b1 m + (1 - b1) g, v <- b2 v + (1 - b2) g^2, w <- w - lr m / (sqrt(v) + eps). In place, fp32."""

    def __init__(self, lr: float, betas, weight_decay: float, eps: float = 1e-8):
        self.learning_rate, self.betas, self.weight_decay, self.eps = (
            lr,
            tuple(betas),
            weight_decay,
            eps,
        )
        self.m: dict[str, torch.Tensor] = {}
        self.v: dict[str, torch.Tensor] = {}
        self.step = 0

    @torch.no_grad()
    def apply(self, grads: dict[str, torch.Tensor], master: dict[str, torch.Tensor]) -> None:
        lr, (b1, b2), eps, wd = self.learning_rate, self.betas, self.eps, self.weight_decay
        self.step += 1
        for k, g in grads.items():
            p = master[k]
            if k not in self.m:
                self.m[k], self.v[k] = torch.zeros_like(p), torch.zeros_like(p)
            m, v = self.m[k], self.v[k]
            p.mul_(1 - lr * wd)
            m.mul_(b1).add_(g, alpha=1 - b1)
            v.mul_(b2).addcmul_(g, g, value=1 - b2)
            p.sub_(lr * m / (v.sqrt() + eps))

    def state_flat(self) -> dict[str, np.ndarray]:
        out = {
            "step": np.array(self.step, dtype=np.uint64),
            "learning_rate": np.array(self.learning_rate, dtype=np.float32),
        }
        for k in self.m:
            out[f"{k}.m"] = self.m[k].detach().cpu().numpy()
            out[f"{k}.v"] = self.v[k].detach().cpu().numpy()
        return out

    def load_flat(self, flat: dict[str, np.ndarray], dev: torch.device) -> None:
        self.step = int(np.asarray(flat.get("step", 0)).reshape(-1)[0])
        for key, a in flat.items():
            if key.endswith(".m"):
                self.m[key[:-2]] = torch.from_numpy(a.astype(np.float32)).to(dev)
            elif key.endswith(".v"):
                self.v[key[:-2]] = torch.from_numpy(a.astype(np.float32)).to(dev)


@torch.no_grad()
def clip_grad_norm(grads: dict[str, torch.Tensor], max_norm: float) -> torch.Tensor:
    """mlx.optimizers.clip_grad_norm, in place: returns the norm before clipping."""
    total = torch.sqrt(sum((g * g).sum() for g in grads.values()))
    scale = torch.clamp(max_norm / (total + 1e-6), max=1.0)
    for g in grads.values():
        g.mul_(scale)
    return total


# ---------------------------------------------------------------- the loss terms (train.py's, in torch)


def _tril(T_: int, k: int, dev) -> torch.Tensor:
    return torch.ones((T_, T_), dtype=torch.bool, device=dev).tril(k)


def copy_mask(x, y, kind: str, markers: torch.Tensor | None = None) -> torch.Tensor:
    """train.copy_mask: (batch, time) bool, the guesses the earlier text in the window could answer."""
    T_ = x.shape[1]
    if kind == "conclusion":
        if markers is None or markers.numel() == 0:
            return torch.zeros(x.shape, dtype=torch.bool, device=x.device)
        is_mark = (x[:, :, None] == markers[None, None, :]).any(dim=-1)
        win = _tril(T_, 0, x.device) & ~_tril(T_, -T.CONCLUSION_SPAN, x.device)
        return (is_mark[:, None, :] & win[None, :, :]).any(dim=-1)
    if kind == "induction":
        hit = (
            (x[:, :, None] == x[:, None, :])
            & (y[:, :, None] == y[:, None, :])
            & _tril(T_, -1, x.device)
        )
    elif kind == "duplicate":
        hit = (y[:, :, None] == x[:, None, :]) & _tril(T_, 0, x.device)
    else:
        raise ValueError(f"unknown copy_weight kind {kind!r}")
    return hit.any(dim=-1)


def copy_weighted(ce, x, y, cw: dict, markers=None):
    w = 1.0 + float(cw["alpha"]) * copy_mask(x, y, cw.get("kind", "induction"), markers).float()
    return (ce * w).sum() / w.sum()


def metre_flags(tok, recipe: list[str], dev) -> dict:
    """train.metre_flags, as tensors on the device."""
    from thorp.evaluators import pips, stars

    out = {"delimiter": torch.as_tensor(stars.delimiters(tok), device=dev)}
    for k in ("number_spotter", "order_word", "premise_marker"):
        out[k] = torch.as_tensor(pips.flags(tok, k), device=dev)
    r = stars.rarity(tok, recipe)
    if r is not None:
        out["rare_word"] = torch.as_tensor((r - r.min()).astype("float32"), device=dev)
    return out


def metre_target(x, card: str, flags: dict | None = None):
    """train.metre_target: ((batch, time, time) target attention, (batch, time) rows that have one)."""
    B, T_ = x.shape
    dev = x.device
    idx = torch.arange(T_, device=dev)
    lag = idx[:, None] - idx[None, :]  # t - j
    before = (lag > 0)[None]
    if card == "previous_word":
        hit = (lag == 1)[None].expand(B, T_, T_)
    elif card == "words_back":
        hit = (lag == 2)[None].expand(B, T_, T_)
    elif card == "induction":
        eq = x[:, :, None] == x[:, None, :]
        shifted = torch.cat(
            [torch.zeros((B, T_, 1), dtype=torch.bool, device=dev), eq[:, :, :-1]], dim=2
        )
        hit = shifted & (lag >= 0)[None]
    elif card == "duplicate_word":
        hit = (x[:, :, None] == x[:, None, :]) & before
    elif card == "sink":
        first = (idx[None, :] == 0) & (idx[:, None] >= 1)
        hit = first[None].expand(B, T_, T_)
    elif card in T.KEYED:
        if not flags or card not in flags:
            raise ValueError(f"the {card} rule needs its class of pieces (metre_flags)")
        hit = flags[card][x][:, None, :] & before
    elif card == "rare_word":
        if not flags or "rare_word" not in flags:
            raise ValueError("the rare word's rule needs the shelf's rarities (metre_flags)")
        hit = flags["rare_word"][x][:, None, :] * before.float()
    else:
        raise ValueError(f"no metre pattern for {card!r} (have {', '.join(T.METRE_PATTERNS)})")
    hit = hit.float()
    n = hit.sum(dim=-1)
    return hit / torch.clamp(n, min=1e-6)[..., None], n > 0


def scaffold_head_losses(pats: dict, x, sc: dict, targets=None, flags=None) -> list:
    """train.scaffold_head_losses: each scaffolded head's distance from its card (or from the target given for the
    card: a teacher's attention), whatever the pull's weight."""
    out = []
    for h in sc["heads"]:
        card = h["card"]
        tgt, has = targets[card] if targets and card in targets else metre_target(x, card, flags)
        p = pats[(int(h["layer"]), int(h["head"]))]
        ce = -(tgt * torch.log(p + 1e-9)).sum(dim=-1)
        hf = has.float()
        out.append((ce * hf).sum() / torch.clamp(hf.sum(), min=1.0))
    return out


def scaffold_loss(
    pats: dict, x, sc: dict, targets=None, flags=None, on=None, weights=None, per_head: list | None = None
):
    """train.scaffold_loss: the mean, over the scaffolded heads (those started, when `on` is given), of each head's
    distance from its card. `weights` gives one weight a head (train.scaffold_weights: a head's own hold, fade, floor
    and release), so a card can fade out while another holds; without it the heads weigh 1 and the caller scales."""
    out = per_head if per_head is not None else scaffold_head_losses(pats, x, sc, targets, flags)
    if on is None:
        if weights is None:
            return sum(out) / len(out)
        return sum(weights[i] * v for i, v in enumerate(out)) / len(out)
    denom = torch.clamp(on[: len(out)].sum(), min=1.0)
    if weights is None:
        return sum(on[i] * v for i, v in enumerate(out)) / denom
    return sum(weights[i] * on[i] * v for i, v in enumerate(out)) / denom


def teacher_targets(teacher, x, sc: dict) -> dict | None:
    """train.py's scaffold_targets: the teacher's own heads as the scaffold's targets. For each head that names a
    `teacher_layer` and `teacher_head`, the attention the teacher's head puts on these tokens, with no gradient, every
    query row counted; keyed by the head's card, as train.py keys it. None when there is no teacher or no head names
    one, so every card falls back to its rule."""
    if teacher is None:
        return None
    t_picks: dict[int, list[int]] = {}
    for h in sc.get("heads") or []:
        if h.get("teacher_head") is not None:
            t_picks.setdefault(int(h["teacher_layer"]), []).append(int(h["teacher_head"]))
    if not t_picks:
        return None
    with torch.no_grad():
        _, tp = teacher.forward_attending(x, t_picks)
    out = {}
    for h in sc["heads"]:
        if h.get("teacher_head") is None:
            continue
        a = tp[(int(h["teacher_layer"]), int(h["teacher_head"]))].detach().float()
        out[h["card"]] = (a, torch.ones(a.shape[:-1], dtype=torch.float32, device=a.device))
    return out


def riddle_losses(model, rb: dict, riddle_cfg: dict) -> list:
    """train.py's riddle_losses: the comparator's head onto the year to exceed; the bridge's logit lens
    preferring the middle term to the distractor."""
    zero = torch.zeros((), device=model.device)
    out = []
    for key in ("comparator", "bridge"):
        r = riddle_cfg.get(key)
        if r is None or key not in rb:
            out.append(zero)
            continue
        w = float(r.get("weight", 1.0))
        if key == "comparator":
            t, q, m = rb["comparator"]
            li, hi = int(r["layer"]), int(r["head"])
            _, pats = model.forward_attending(t, {li: [hi]})
            p = pats[(li, hi)]
            row = p[torch.arange(p.shape[0], device=p.device), q.long(), :]
            out.append(w * (-(m * torch.log(row + 1e-9)).sum(dim=-1)).mean())
        else:
            t, q, bb, dd = rb["bridge"]
            h = model.hidden(t)[int(r["layer"])]
            ar = torch.arange(h.shape[0], device=h.device)
            lp = torch.log_softmax(model.lens(h[ar, q.long(), :]).float(), dim=-1)
            diff = lp[ar, bb.long()] - lp[ar, dd.long()]
            out.append(w * F.softplus(-diff).mean())  # log(1 + e^-diff), MLX's logaddexp(0, -diff)
    return out


# ---------------------------------------------------------------- what a voyage carries over


def _flat_np(master: dict[str, torch.Tensor]) -> dict[str, np.ndarray]:
    return {k: v.detach().cpu().numpy() for k, v in master.items()}


def seeded_master(spec: dict, seed: dict, master: dict, vocab: int, log) -> tuple:
    """train.seeded_master: the finished run `seed["run"]` grown into this model (thorp/growth.py)."""
    from thorp import growth
    from thorp.ledger import spec_of

    rows = T.parent_run(seed["run"], "seeded_from", log)
    src_spec, src_rid = spec_of(rows), rows["run_id"]
    if src_spec.get("tokeniser", {}).get("vocab") != spec["tokeniser"]["vocab"] or src_spec[
        "tokeniser"
    ].get("train_on") != spec["tokeniser"].get("train_on"):
        raise ValueError("seeded_from: the seed must share this run's tokeniser")
    src_pos, dst_pos = (
        src_spec["model"].get("positions", "learned"),
        spec["model"].get("positions", "learned"),
    )
    if src_pos != dst_pos:
        raise ValueError("seeded_from: the seed must use the same kind of positions as this run")
    # the shapes the runs were built with, overrides included, as train.seeded_master (11 November)
    def _shape(m: dict) -> dict:
        return {"layers": m.get("layers"), "width": m.get("width"), "heads": m.get("heads")}

    src_cfg = registry.config(
        src_spec["model"]["preset"], vocab, src_spec["model"]["context"], src_pos, **_shape(src_spec["model"])
    )
    dst_cfg = registry.config(
        spec["model"]["preset"], vocab, spec["model"]["context"], dst_pos, **_shape(spec["model"])
    )
    ck = T.latest_checkpoint(src_rid)
    if seed.get("step") is not None:
        ck = T.checkpoint_root(src_rid) / f"step-{int(seed['step'])}"
        if not (ck / "state.json").exists():
            raise LookupError(
                f"seeded_from: {seed['run']} has no checkpoint at step {seed['step']}"
            )
    src = {k: v.astype(np.float32) for k, v in load_flat(ck / "model.safetensors").items()}
    new, mask = growth.grow(src, src_cfg, _flat_np(master), dst_cfg)
    share = sum(m.sum() for m in mask.values()) / sum(m.size for m in mask.values())
    log(
        f"seeded from {seed['run']} ({src_rid[:12]}, {src_cfg.layers}x{src_cfg.width}), mode {seed.get('mode', 'free')}: {share:.1%} of the weights inherited"
    )
    dev = next(iter(master.values())).device
    grown = {
        k: torch.as_tensor(new[k], dtype=torch.float32, device=dev) if k in new else v
        for k, v in master.items()
    }
    inherit = {
        "mask": {
            k: torch.as_tensor(v, dtype=torch.float32, device=dev)
            for k, v in mask.items()
            if v.any()
        },
        "values": {
            k: torch.as_tensor(new[k], dtype=torch.float32, device=dev)
            for k, v in mask.items()
            if v.any()
        },
    }
    return grown, inherit


def load_teacher(teach: dict, spec: dict, vocab: int, log):
    """train.load_teacher: a finished run's model (either backend's checkpoint), frozen."""
    from thorp.ledger import spec_of

    rows = T.parent_run(teach["run"], "teacher", log)
    t_spec, t_rid = spec_of(rows), rows["run_id"]
    if t_spec["tokeniser"].get("vocab") != spec["tokeniser"]["vocab"] or t_spec["tokeniser"].get(
        "train_on"
    ) != spec["tokeniser"].get("train_on"):
        raise ValueError("teacher: must share this run's tokeniser")
    t_model = load_model(t_spec, vocab, T.latest_checkpoint(t_rid))
    t_model.requires_grad_(False)
    t_model.eval()
    log(
        f"teacher: {teach['run']} ({t_rid[:12]}), alpha {teach.get('alpha', 0.5)}, temperature {teach.get('temperature', 1.0)}"
    )
    return t_model


def transplant_heads(spec: dict, master: dict, log) -> tuple:
    """train.transplant_heads on torch master weights: a finished run's heads for a star copied in."""
    from thorp.fleet import STARS
    from thorp.ledger import spec_of

    t = spec["transplant"]
    rows = T.parent_run(t["from_run"], "transplant", log)
    donor_spec, donor_rid = spec_of(rows), rows["run_id"]
    if (
        donor_spec["model"]["preset"] != spec["model"]["preset"]
        or donor_spec["tokeniser"] != spec["tokeniser"]
    ):
        raise ValueError("transplant: the donor must be the same class with the same tokeniser")
    star = t.get("star", "previous_word")
    kind, key = ("nevermore", "natural_scores") if star == "nevermore" else ("stars", star)
    text = reader().latest_artifact_text(donor_rid, kind)
    if text is None:
        raise LookupError(f"transplant: no {kind!r} artifact on {t['from_run']!r}")
    scores = np.array(json.loads(text)[key])
    layer = int(np.sort(scores, axis=1)[:, -2:].sum(axis=1).argmax())
    order = list(np.argsort(scores[layer])[::-1])
    heads = order[:1] if scores[layer][order[0]] >= STARS[star].threshold else order[:2]
    donor = load_flat(T.latest_checkpoint(donor_rid) / "model.safetensors")
    flat = _flat_np(master)
    cfg = registry.config(
        spec["model"]["preset"], flat["tok.weight"].shape[0], spec["model"]["context"]
    )
    D, hd = cfg.width, cfg.width // cfg.heads
    qkv, proj = f"layers.{layer}.attn.qkv.weight", f"layers.{layer}.attn.proj.weight"
    for h in heads:
        for b in range(3):
            r = slice(b * D + h * hd, b * D + (h + 1) * hd)
            flat[qkv][r] = donor[qkv][r]
        flat[proj][:, h * hd : (h + 1) * hd] = donor[proj][:, h * hd : (h + 1) * hd]
    if t.get("pos", True):
        flat["pos.weight"] = donor["pos.weight"]
    if t.get("tok"):
        flat["tok.weight"] = donor["tok.weight"]
    below = list(range(layer)) if t.get("below") else []
    for i in below:
        for k in [k for k in donor if k.startswith(f"layers.{i}.")]:
            flat[k] = donor[k]
    if t.get("ln", t.get("below")):
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
    dev = next(iter(master.values())).device
    return {
        k: torch.as_tensor(np.array(v, dtype=np.float32), device=dev) for k, v in flat.items()
    }, handed


# ---------------------------------------------------------------- the loop


def train(
    spec: dict, prep, rec: Ledger | None = None, stop_after: int | None = None, log=None
) -> dict:
    """train.train on PyTorch: train (or resume) the run this spec describes."""
    refuse_unsupported(spec)  # before any work: a key this loop would pass over is a refusal, never a silent drift
    from thorp.ledger import MetricBuffer, flush_every

    rec = rec or recorder()
    buf = MetricBuffer(rec, every=flush_every(spec))  # the per-step metrics, as train.train writes them (item 4)
    with T.stoppable():  # SIGTERM/SIGHUP: checkpoint the step under way and stop, as train.train (item 10)
        try:
            return _train(spec, prep, rec, buf, stop_after, log)
        except BaseException:
            buf.flush_quietly()
            raise


def _train(spec: dict, prep, rec: Ledger, buf, stop_after: int | None, log) -> dict:
    """train's loop; `buf` holds the per-step metrics until they are flushed (train._train's rules)."""
    rid = T.run_id(spec)
    log = log or T.Log(paths.runs_dir() / f"{rid}.log")
    buf.log = log
    o, m = spec["optim"], spec["model"]
    precision = o.get("precision", "bf16")
    tok = prep.tokeniser
    books = prep.books()
    families = {b: books[b].family for b in books}
    stages = spec["data"].get("stages")
    if stages:
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

    dev = device()
    if dev.type == "cuda":
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
    model = build_model(spec, tok.vocab_size, dev)
    counts = model.parameter_counts()
    master = {k: p.detach().float().clone() for k, p in model.named_parameters()}
    model.to(compute_dtype(precision))
    opt = AdamW(o["lr"], o["betas"], o["weight_decay"])

    start, tokens_seen, wall_before = 0, 0, 0.0
    ckpt = T.latest_checkpoint(rid)
    seed = spec.get("seeded_from")
    inherit = None
    if seed:
        grown, inherit = seeded_master(spec, seed, master, tok.vocab_size, log)
        if ckpt is None:
            master = grown
    handed = None
    if spec.get("transplant") and ckpt is None:
        master, handed = transplant_heads(spec, master, log)
    if ckpt is not None:
        st = json.loads((ckpt / "state.json").read_text())
        from thorp import versioning

        # train.train's check: the checkpoint's tokeniser is the one this sailing built, before anything is truncated
        if why := versioning.tokeniser_mismatch(st, tok.id):
            raise ValueError(why)
        start, tokens_seen, wall_before = st["step"], st["tokens_seen"], st["wall_seconds"]
        master = load_master(ckpt, dev)
        opt.load_flat(load_flat(ckpt / "optimizer.safetensors"), dev)
        rec.truncate_after(rid, start)
        log(f"resuming {rid[:12]} from {ckpt.name}")
    set_weights(model, master)
    model.train()

    rec.run(
        {
            "run_id": rid,
            "name": spec.get("name"),
            "ship": spec.get("ship"),
            "spec_json": T.canonical(spec),
            "sop_version": spec.get("sop"),
            "commit": T.git_commit(),
            "hardware": hardware(dev),
            "status": "running",
            "started": None if (rec.get_run(rid) or {}).get("started") else T.now(),
        }
    )
    if start == 0:
        rec.truncate_after(rid, -1)
        T.record_setup(spec, rid, prep, stream, counts, rec)
        if hasattr(stream, "record"):
            rec.artifact(rid, 0, "stages", "", "", json.dumps(stream.record()))
        if handed is not None:
            rec.artifact(rid, 0, "transplant", "", "", json.dumps(handed))
    from thorp import versioning  # train.train's provenance, beside the id; never raises

    versioning.record_provenance(spec, rid, tok.id, rec, log, start=start)
    # train.train's run state and expedition rows (11 November, item 11); never raises
    from thorp import run_state

    run_state.started(spec, rid, rec, log)
    log(
        f"run {rid} ({spec.get('name')}): {m['preset']} {counts}, {total} steps x "
        f"{stream.tokens_per_step} tokens, {stream.unique_tokens} unique tokens/pass; torch on {dev}"
    )

    cw = o.get("copy_weight")
    markers = (
        torch.as_tensor(T.conclusion_ids(tok), dtype=torch.long, device=dev)
        if cw and cw.get("kind") == "conclusion"
        else None
    )
    if markers is not None:
        log(f"conclusion-weighted tack: {markers.numel()} marker pieces, alpha {cw['alpha']}")
    teach = o.get("teacher")
    teacher = load_teacher(teach, spec, tok.vocab_size, log) if teach else None

    sc = o.get("scaffold")
    picks, flags, sample, riddle_cfg, pools = None, None, None, {}, {}
    probing = False  # the probe phase: the pull pulsed down, each pinned head's distance logged every step
    if sc:
        T.check_scaffold(sc, model.cfg.layers, model.cfg.heads)
        picks = T.scaffold_picks(sc) if sc.get("heads") else None
        probing = bool(picks and sc.get("probes"))
        if any(h["card"] in T.KEYED or h["card"] == "rare_word" for h in sc.get("heads") or []):
            flags = metre_flags(tok, list(prep.recipe), dev)
        sample = sc.get("sample")
        riddle_cfg = sc.get("riddles") or {}
        if riddle_cfg:
            from thorp import riddles

            makers = {"comparator": riddles.comparator_items, "bridge": riddles.bridge_items}

            def maker(k, r):
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

    staged = bool(sc) and (
        any("from" in h for h in sc.get("heads") or [])
        or any("from" in r for r in riddle_cfg.values())
    )
    zero = torch.zeros((), device=dev)
    # THORP_TORCH_COMPILE=1 compiles the plain forward pass (the scaffold's own passes stay eager)
    fwd = torch.compile(model) if os.environ.get("THORP_TORCH_COMPILE") == "1" else model

    def loss_fn(x, y, sw: float, hw, rb: dict, on):
        dist = []  # each pinned head's distance from its card, whatever the weight (the probe phase reads it)
        # the stretch's long windows read no pinned head's map (train.py's rule, data.Stretched)
        long = x.shape[1] > int(m["context"])
        if picks and not sample and not long:
            logits, pats = model.forward_attending(x, picks)
            dist = scaffold_head_losses(pats, x, sc, teacher_targets(teacher, x, sc), flags)
            sl = scaffold_loss(pats, x, sc, on=on if staged else None, weights=hw, per_head=dist)
        elif picks and not long:
            logits = fwd(x)
            xs = x[: int(sample["windows"]), : int(sample["length"])]
            _, pats = model.forward_attending(xs, picks)
            dist = scaffold_head_losses(pats, xs, sc, teacher_targets(teacher, xs, sc), flags)
            sl = scaffold_loss(pats, xs, sc, on=on if staged else None, weights=hw, per_head=dist)
        else:
            logits, sl = fwd(x), zero
        riddle = riddle_losses(model, rb, riddle_cfg) if riddle_cfg else [zero, zero]
        if staged:
            riddle = [riddle[0] * on[-2], riddle[1] * on[-1]]
        parts = [sl] + riddle
        ce = F.cross_entropy(logits.float().transpose(1, 2), y, reduction="none")  # (batch, time)
        per_window = ce.mean(dim=1)
        # (alpha 0 is a teacher kept for its attention only, train.py's rule: no distillation, and the
        # copy-weighted tack still applies)
        if teacher is not None and float(teach.get("alpha", 0.5)) > 0:
            Tt, a = float(teach.get("temperature", 1.0)), float(teach.get("alpha", 0.5))
            with torch.no_grad():
                t_lp = torch.log_softmax(teacher(x).float() / Tt, dim=-1)
            s_lp = torch.log_softmax(logits.float() / Tt, dim=-1)
            kl = (t_lp.exp() * (t_lp - s_lp)).sum(dim=-1).mean()
            base = (1 - a) * per_window.mean() + a * Tt * Tt * kl
        elif not cw or not cw.get("alpha"):
            base = per_window.mean()
        else:
            base = copy_weighted(ce, x, y, cw, markers)
        # the heads carry their own weights (train.scaffold_weights), the riddles the voyage's
        pull = parts[0] + sw * (parts[1] + parts[2]) if riddle_cfg else parts[0]
        if probing:  # a probing voyage logs every pinned head's distance beside the three parts
            parts = parts + [d.detach() for d in dist]
        return base + pull, per_window, torch.stack([p.float() for p in parts])

    def riddle_batch(step: int) -> dict:
        from thorp import riddles

        out = {}
        for key, r in riddle_cfg.items():
            d = riddles.draw(pools[key], step, int(r.get("items", 16)))
            t = lambda a: torch.as_tensor(np.asarray(a), device=dev)  # noqa: E731
            if key == "comparator":
                out[key] = (t(d["tokens"]).long(), t(d["q"]), t(d["target"]).float())
            else:
                out[key] = (t(d["tokens"]).long(), t(d["q"]), t(d["b"]), t(d["d"]))
        return out

    groups = model.param_groups()
    prev_flat, prev_step = {k: v.clone() for k, v in master.items()}, start
    prev_delta: dict = {}
    book_loss: dict[int, float] = {}
    book_n: dict[int, int] = {}
    every_eval = spec["eval"]["every_steps"]
    light = spec["eval"].get("light")
    offline = T.offline_evaluators(spec)  # eval.offline: scored later from saved weights (`thorp score`)
    every_ckpt = spec["checkpoint"]["every_steps"]
    stop = T.stop_flag()  # raised by SIGTERM/SIGHUP (train.stoppable): checkpoint this step and stop
    stop.log = log
    # per-voyage milestones (train.train's, 12 November): judged at the first evaluation at or after their step,
    # and a missed one that asks for a recall stops the voyage there, at a checkpoint
    from thorp import milestones as milestones_mod

    ms = milestones_mod.declared(spec, total)
    judged_milestones: set[int] = set()
    t_run = time.time()
    params = dict(model.named_parameters())

    def sq(t) -> float:
        return float((t * t).sum())

    step = start
    for batch in stream.iter_from(start):
        t0 = time.time()
        lr = T.lr_at(step, total, o)
        opt.learning_rate = lr
        tokens = torch.as_tensor(np.asarray(batch.tokens), dtype=torch.long, device=dev)
        sw = T.scaffold_weight(step, total, sc) if sc else 0.0
        hw_list = T.scaffold_weights(step, total, sc) if sc else []
        on = torch.as_tensor(
            T.scaffold_on(step, total, sc) if staged else [1.0], dtype=torch.float32, device=dev
        )
        for p in params.values():
            p.grad = None
        loss, per_window, sl = loss_fn(
            tokens[:, :-1],
            tokens[:, 1:],
            sw,
            torch.as_tensor(hw_list, dtype=torch.float32, device=dev),
            riddle_batch(step) if riddle_cfg else {},
            on,
        )
        loss.backward()
        grads = {
            k: (p.grad.float() if p.grad is not None else torch.zeros_like(master[k]))
            for k, p in params.items()
        }
        gnorm = clip_grad_norm(grads, o["grad_clip"])
        if inherit and seed.get("mode") == "slow":
            s = float(seed.get("lr_scale", 0.1))
            for k, mk in inherit["mask"].items():
                grads[k].mul_(mk * s + (1.0 - mk))
        opt.apply(grads, master)
        if inherit and seed.get("mode") == "freeze":
            with torch.no_grad():
                for k, mk in inherit["mask"].items():
                    master[k].copy_(master[k] * (1.0 - mk) + inherit["values"][k] * mk)
        set_weights(model, master)
        step += 1
        pw = per_window.detach().cpu().tolist()
        for bi, lw in zip(batch.book_index.tolist(), pw, strict=True):
            book_loss[bi] = book_loss.get(bi, 0.0) + lw
            book_n[bi] = book_n.get(bi, 0) + 1
        tokens_seen += stream.tokens_per_step
        loss_v = (
            float(np.mean(pw)) if (cw and cw.get("alpha")) or teach or sc else float(loss.detach())
        )
        if dev.type == "cuda":
            torch.cuda.synchronize(dev)
        dt = time.time() - t0
        if not math.isfinite(loss_v):
            raise FloatingPointError(f"loss is {loss_v} at step {step}")
        vals = {
            "loss": loss_v,
            "lr": lr,
            "step_ms": dt * 1000,
            "tokens_per_s": stream.tokens_per_step / dt,
            "tokens_seen": tokens_seen,
        }
        if sc:
            vals["scaffold/weight"] = sw
            for h, w in zip(sc.get("heads") or [], hw_list, strict=True):
                vals[f"scaffold/weight/{h['card']}"] = w
            if staged:
                vals["scaffold/started"] = float(sum(T.scaffold_on(step - 1, total, sc)))
            parts = sl.detach().cpu().tolist()
            vals["scaffold/loss"] = parts[0]
            for key, v in zip(("comparator", "bridge"), parts[1:3], strict=True):
                if key in riddle_cfg:
                    vals[f"scaffold/riddle/{key}"] = v
            if probing:
                vals["scaffold/probe"] = 1.0 if T.probe_at(step - 1, total, sc) else 0.0
                for h, v in zip(sc.get("heads") or [], parts[3:], strict=True):
                    vals[f"scaffold/distance/{h['card']}/l{h['layer']}h{h['head']}"] = v
            vals["scaffold/phase"] = float(
                ("metre", "fade", "content", "release").index(T.scaffold_phase(step - 1, total, sc))
            )
        if step % T.METRICS_EVERY == 0 or step == 1:
            with torch.no_grad():
                vals["grad_norm"] = float(gnorm)
                vals["param_norm"] = math.sqrt(sum(sq(p) for p in master.values()))
                vals["mem_gb"] = peak_memory_gb(dev)
                moved = step - prev_step == T.METRICS_EVERY
                for g, prefix in groups.items():
                    keys = [k for k in master if k.startswith(prefix)]
                    vals[f"grad_norm/{g}"] = math.sqrt(
                        sum(sq(grads[k]) for k in keys if k in grads)
                    )
                    pn = math.sqrt(sum(sq(master[k]) for k in keys))
                    vals[f"param_norm/{g}"] = pn
                    if moved:
                        un = math.sqrt(sum(sq(master[k] - prev_flat[k]) for k in keys))
                        vals[f"update_norm/{g}"] = un
                        vals[f"update_ratio/{g}"] = un / pn if pn else 0.0
                        if prev_delta and all(k in prev_delta for k in keys):
                            dot = sum(
                                float(((master[k] - prev_flat[k]) * prev_delta[k]).sum())
                                for k in keys
                            )
                            pdn = math.sqrt(sum(sq(prev_delta[k]) for k in keys))
                            if un and pdn:
                                vals[f"heading/{g}"] = dot / (un * pdn)
                if step % T.METRICS_EVERY == 0:
                    prev_delta = (
                        {k: master[k] - prev_flat[k] for k in master if k in prev_flat}
                        if step - prev_step == T.METRICS_EVERY
                        else {}
                    )
                    prev_flat, prev_step = {k: v.clone() for k, v in master.items()}, step
            if hasattr(stream, "stages"):
                vals["stage"] = float(batch.stage)
            for fam, frac in batch.family_mix(stream.families).items():
                vals[f"data/family/{fam}"] = frac
            for bi, n in book_n.items():
                vals[f"loss/book/{stream.book_ids[bi]}"] = book_loss[bi] / n
            book_loss, book_n = {}, {}
            log(
                f"step {step}/{total} loss {loss_v:.4f} lr {lr:.2e} "
                f"{vals['tokens_per_s']:.0f} tok/s mem {vals['mem_gb']:.1f} GB"
            )
        buf.add(rid, step, vals)
        run_state.beat(rid, rec)  # train.train's heartbeat, at most one upsert a minute (item 11)

        latest: dict | None = None
        if step % every_eval == 0 or step == total:
            buf.flush()
            latest = T.evaluate_in_loop(
                spec, rid, step, model, prep, rec, log, spec["eval"]["evaluators"], offline,
                step % every_ckpt == 0 or step == total, master,
            )  # fmt: skip
        elif light and step % light["every_steps"] == 0:
            buf.flush()
            latest = T.evaluate_in_loop(
                spec, rid, step, model, prep, rec, log, light["evaluators"], offline,
                step % every_ckpt == 0 or step == total, master,
            )  # fmt: skip
        model.train()
        recall_reason = None
        if ms and latest:
            # train.train's rule: a bug in a milestone is reported and the voyage sails on
            try:
                verdicts = milestones_mod.check(ms, step, latest, judged_milestones)
                if verdicts:
                    milestones_mod.record(verdicts, rid, rec, log)
                    recall_reason = milestones_mod.recall_reason(verdicts)
            except Exception as e:  # noqa: BLE001
                log(f"milestones: {e.__class__.__name__}: {e}")
        stopping = stop.signal is not None and step < total  # read once: a signal from here on waits a step
        if step % every_ckpt == 0 or step == total or recall_reason or stopping:
            buf.flush(strict=True)  # every row up to the checkpoint's step is in the store before it exists
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
                    "backend": "torch",
                },
            )
            rec.artifact(rid, step, "checkpoint", str(d), "", "")
            T.retain(spec, rid, log, rec)  # checkpoint.keep_last / keep_every; nothing without them
        if stopping and not recall_reason:
            wall = wall_before + time.time() - t_run
            rec.run(
                {
                    "run_id": rid,
                    "status": f"stopped: {stop.signal} at step {step}",
                    "tokens_seen": tokens_seen,
                    "wall_minutes": wall / 60,
                    "commit": T.git_commit(),
                }
            )
            log(f"stopped at step {step} by {stop.signal}: checkpointed, to resume from {d.name}")
            run_state.ended(rid, f"stopped: {stop.signal} at step {step}", rec, log)
            return {"run_id": rid, "step": step, "status": "stopped", "signal": stop.signal}
        if recall_reason:
            wall = wall_before + time.time() - t_run
            rec.run(
                {
                    "run_id": rid,
                    "finished": T.now(),
                    "status": f"recalled: {recall_reason}",
                    "tokens_seen": tokens_seen,
                    "wall_minutes": wall / 60,
                    "commit": T.git_commit(),
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
            "finished": T.now(),
            "status": "finished",
            "tokens_seen": tokens_seen,
            "wall_minutes": wall / 60,
            "commit": T.git_commit(),
        }
    )
    log(f"finished {rid}: {tokens_seen} tokens in {wall / 60:.1f} min")
    run_state.ended(rid, "finished", rec, log)
    return {"run_id": rid, "step": step, "status": "finished"}

"""Soundings: what each layer does to a passage on its way up the stack (2026-11-07, Justin).

The sieves measure training (how each layer's weights were pushed, moved and steered); soundings
measure reading. A passage enters as embeddings, and every layer adds its attention half's write and
then its feed-forward half's write to the stream. At each depth we take a sounding:

- **bpb** (`soundings/layer_<k>/bpb`): the guess the model would make if it stopped here: the stream
  after layer k (k = 0 is the embeddings alone) through the final LayerNorm and the output, scored
  in bits per byte on the next piece (the "logit lens"). The last layer's is the model's own score.
  How much each layer lowers it is how much that layer adds to the guess.
- **write** (`soundings/layer_<i>/attn_write`, `mlp_write`): how hard each half writes: the size of
  its contribution over the size of the stream it read (both as root-mean-square per position).
- **turn** (`soundings/layer_<i>/attn_turn`, `mlp_turn`): which way it writes: 1 minus the cosine
  between its contribution and the stream it read. 0 pushes the stream further the way it already
  points, 1 writes at right angles (new information), 2 pushes it back.

Measured on the same SEQS real passages of a Forgotten Tome as the stars, every eval step it is
asked for. Artifact `soundings`: all of the above as lists by layer.
"""

from __future__ import annotations

import hashlib
import json
import math

import numpy as np

from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.stars import passages
from thorp.models import ops


def _rms(x):
    import mlx.core as mx

    return mx.sqrt((x * x).mean(axis=-1))


def _cos(a, b):
    import mlx.core as mx

    return (a * b).sum(axis=-1) / (mx.sqrt((a * a).sum(axis=-1) * (b * b).sum(axis=-1)) + 1e-9)


def _held_out_passages(ctx: EvalContext) -> np.ndarray | None:
    from thorp import shards
    from thorp.evaluators.nevermore import LENGTH, SEQS

    books = [b for ids in ctx.sets.values() for b in ids]
    if not books:
        return None
    arr = np.asarray(shards.load(ctx.tokeniser.id, books[0], ctx.tokeniser))
    n = min(2 * LENGTH, ctx.context - 1, len(arr) - 1)
    starts = np.linspace(0, len(arr) - n - 1, SEQS).astype(int)
    return np.stack(
        [np.concatenate([[ctx.tokeniser.eos_id], arr[s : s + n]]) for s in starts]
    ).astype(np.int32)


def _sound_mlx(model, nat: np.ndarray, targets: np.ndarray, nbytes: int) -> dict:
    import mlx.core as mx
    import mlx.nn as nn

    x_in = mx.array(nat[:, :-1])
    y = mx.array(targets)
    T = x_in.shape[1]
    x = model.embed(x_in) if hasattr(model, "embed") else model.tok(x_in) + model.pos(mx.arange(T))

    def bits(h) -> float:
        logits = model.tok.as_linear(model.ln_f(h)).astype(mx.float32)
        ce = nn.losses.cross_entropy(logits, y, reduction="sum")
        mx.eval(ce)
        return ce.item() / math.log(2) / nbytes

    rec = {"bpb": [bits(x)], "attn_write": [], "mlp_write": [], "attn_turn": [], "mlp_turn": []}
    for b in model.layers:
        a = b.attn(b.ln1(x))
        rec["attn_write"].append((_rms(a) / (_rms(x) + 1e-9)).mean())
        rec["attn_turn"].append((1 - _cos(a, x)).mean())
        x1 = x + a
        m = b.mlp(b.ln2(x1))
        rec["mlp_write"].append((_rms(m) / (_rms(x1) + 1e-9)).mean())
        rec["mlp_turn"].append((1 - _cos(m, x1)).mean())
        x = x1 + m
        rec["bpb"].append(bits(x))
    for k in ("attn_write", "mlp_write", "attn_turn", "mlp_turn"):
        vals = mx.stack(rec[k]).astype(mx.float32)  # the model may compute in bf16
        mx.eval(vals)
        rec[k] = [float(v) for v in np.array(vals)]
    return rec


def _sound_torch(model, nat: np.ndarray, targets: np.ndarray, nbytes: int) -> dict:
    """_sound_mlx in PyTorch, on the torch GPT (the same blocks and names)."""
    import torch

    def rms(x):
        return torch.sqrt((x * x).mean(dim=-1))

    def cos(a, b):
        return (a * b).sum(dim=-1) / (torch.sqrt((a * a).sum(dim=-1) * (b * b).sum(dim=-1)) + 1e-9)

    was = model.training
    model.eval()
    with torch.no_grad():
        x_in = model._tokens(nat[:, :-1])
        y = model._tokens(targets)
        x = model.embed(x_in)

        def bits(h) -> float:
            logits = model.lens(h).float()
            ce = torch.nn.functional.cross_entropy(logits.transpose(1, 2), y, reduction="sum")
            return ce.item() / math.log(2) / nbytes

        rec = {"bpb": [bits(x)], "attn_write": [], "mlp_write": [], "attn_turn": [], "mlp_turn": []}
        for b in model.layers:
            a = b.attn(b.ln1(x))
            rec["attn_write"].append(float((rms(a) / (rms(x) + 1e-9)).float().mean()))
            rec["attn_turn"].append(float((1 - cos(a, x)).float().mean()))
            x1 = x + a
            m = b.mlp(b.ln2(x1))
            rec["mlp_write"].append(float((rms(m) / (rms(x1) + 1e-9)).float().mean()))
            rec["mlp_turn"].append(float((1 - cos(m, x1)).float().mean()))
            x = x1 + m
            rec["bpb"].append(bits(x))
    model.train(was)
    return rec


def evaluate(ctx: EvalContext) -> EvalResult:
    model, tok = ctx.model, ctx.tokeniser
    if not all(hasattr(model, a) for a in ("tok", "layers", "ln_f")):
        return EvalResult()
    nat = passages(tok, ctx.context)
    if nat is None:  # no Forgotten Tome here (a test library): sound the run's own held-out books
        nat = _held_out_passages(ctx)
    if nat is None:
        return EvalResult()
    from thorp.evaluators.bpb_split import piece_bytes

    pb = piece_bytes(tok)
    targets = nat[:, 1:]
    nbytes = sum(len(pb[t]) for t in targets.ravel()) or 1
    sound = _sound_torch if ops.is_torch(model) else _sound_mlx
    rec = sound(model, nat, targets, nbytes)
    metrics = {f"soundings/layer_{k}/bpb": v for k, v in enumerate(rec["bpb"])}
    for k in ("attn_write", "mlp_write", "attn_turn", "mlp_turn"):
        metrics.update({f"soundings/layer_{i}/{k}": v for i, v in enumerate(rec[k])})
    text = json.dumps(
        {"layers": len(model.layers), **{k: [round(v, 5) for v in vs] for k, vs in rec.items()}}
    )
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "soundings",
                "path": "",
                "sha1": hashlib.sha1(text.encode()).hexdigest(),
                "text": text,
            }
        ],
    )

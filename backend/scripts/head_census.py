"""The head census: ablate every head in a model, one at a time, and rank what each one moves.

An expedition's investigation, not a voyage (SOP v0.0.6's launching order, step 1): the learning ships
are asked to grow what this map says is worth growing, so it must be home before they sail.

For every (layer, head) the head's slice of the attention output is zeroed and the model is read on a
probe set; the reading is the change in next-token loss against the unablated model. The output is one
row per head: layer, head, mean loss delta, and the worst single-probe delta. A head with a delta near
zero is a slot nothing in this probe set leans on — which is a finding, not an empty slot.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/head_census.py \
        mlx-community/Qwen3-4B-4bit --probes 40 --out data/runs/head-census-qwen3-4b.json

The probe set is held-out text from the lab's own books (the Forgotten Tomes), not the deck: the deck's
cards are 16 hypotheses, and this is meant to find the heads they do not name.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def probes_from_books(n: int, tokens: int) -> list[str]:
    """Held-out passages: the first text files under data/texts, cut into `tokens`-word chunks.

    The books are stored by source (data/texts/<source>/<book>.txt), so the census walks the tree
    rather than assuming one filename per book id.
    """
    root = ROOT / "data" / "texts"
    out: list[str] = []
    for p in sorted(root.glob("*/*.txt"))[: max(8, n * 2)]:
        try:
            words = p.read_text(encoding="utf-8", errors="ignore").split()
        except OSError:
            continue
        if len(words) < tokens:
            continue
        for j in range(0, len(words) - tokens, tokens):
            out.append(" ".join(words[j : j + tokens]))
            if len(out) >= n:
                return out
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", nargs="?", default="mlx-community/Qwen3-4B-4bit")
    ap.add_argument("--probes", type=int, default=16)
    ap.add_argument("--tokens", type=int, default=256)
    ap.add_argument("--layers", type=int, default=0, help="0 = every layer (a quick test: 2)")
    ap.add_argument("--heads", type=int, default=0, help="0 = every head")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    import mlx.core as mx
    from mlx_lm import load

    t0 = time.time()
    model, tok = load(a.model)
    inner = getattr(model, "model", model)
    layers = inner.layers
    n_layers, n_heads, head_dim = len(layers), inner.args.num_attention_heads, inner.args.head_dim
    print(f"{a.model}: {n_layers} layers x {n_heads} heads = {n_layers * n_heads} heads", flush=True)

    texts = probes_from_books(a.probes, a.tokens)
    if not texts:
        raise SystemExit("no probe text: data/texts is empty")
    ids = [tok.encode(t)[: a.tokens] for t in texts]
    ids = [x for x in ids if len(x) > 8]
    print(f"probes: {len(ids)}", flush=True)

    # every probe in one batch: one forward per head instead of one per probe (a 4B at 4-bit
    # takes ~10k prompt tokens in a few seconds, so 1,152 heads is under an hour instead of a day)
    T = min(len(x) for x in ids)
    batch = mx.array([x[:T] for x in ids])

    def loss_batched() -> float:
        logits = model(batch[:, :-1])
        lp = logits - mx.logsumexp(logits, axis=-1, keepdims=True)
        picked = mx.take_along_axis(lp, batch[:, 1:, None], axis=-1)[..., 0]
        return float(-picked.mean())

    base = loss_batched()
    print(f"base loss {base:.4f} nats/token ({time.time() - t0:.0f}s)", flush=True)

    def mask_head(layer: int, head: int, on: bool):
        attn = layers[layer].self_attn
        proj = attn.o_proj
        orig = proj.__call__

        def patched(x):
            if on:
                sl = slice(head * head_dim, (head + 1) * head_dim)
                x = mx.concatenate([x[..., : sl.start], mx.zeros_like(x[..., sl]), x[..., sl.stop :]], axis=-1)
            return orig(x)

        proj.__call__ = patched
        return lambda: setattr(proj, "__call__", orig)

    rows = []
    lay = range(n_layers) if not a.layers else range(min(a.layers, n_layers))
    for li in lay:
        for hi in (range(n_heads) if not a.heads else range(min(a.heads, n_heads))):
            restore = mask_head(li, hi, True)
            try:
                dl = loss_batched() - base
            finally:
                restore()
            rows.append({"layer": li, "head": hi, "loss_delta": round(dl, 5)})
        print(f"layer {li}: done ({len(rows)} heads, {time.time() - t0:.0f}s)", flush=True)

    rows.sort(key=lambda r: -r["loss_delta"])
    out = Path(a.out) if a.out else ROOT / "data" / "runs" / f"head-census-{a.model.split('/')[-1]}.json"
    out.write_text(json.dumps({"model": a.model, "probes": len(ids), "base_loss": base, "heads": rows}, indent=0))
    print(f"wrote {out}: {len(rows)} heads; worst {rows[0] if rows else None}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

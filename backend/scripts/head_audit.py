"""The Qwen3-4B audit, stages 1 and 2.

Stage 1 — **fingerprints**: one forward per probe, capturing every head's attention weights, and
summarising each head by what it looks at: the previous token, the first token (sink), the token that
followed the last occurrence of this one (induction), the same token elsewhere (copy), fixed offsets,
and its profile by relative distance. Also the two structural questions: whether the four query heads
inside a KV group look alike (would Thorps' suit-grouped GQA suit this model?), and how the heads sit
on RoPE's distance bands.

Stage 2 — **ablation**: each head's slice of the attention output zeroed, one at a time, and the loss
delta on the same probes. Importance, not meaning: stage 1 is the meaning, stage 2 the weight.

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/head_audit.py --stage 1 --probes 24
    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/head_audit.py --stage 2 --probes 8

Both write JSON to data/runs/; both take --layers/--heads for a smoke test.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BINS = (1, 2, 3, 4, 8, 16, 10**9)


def probes(n: int, tokens: int) -> list[list[int]]:
    """Probe passages as token ids: the first `n` chunks of the text tree, `tokens` words each."""
    import mlx.core as mx  # noqa: F401  (the caller loads the tokeniser first)
    from thorp.paths import resolve  # noqa: F401

    texts = []
    for p in sorted((ROOT / "data" / "texts").glob("*/*.txt")):
        words = p.read_text(encoding="utf-8", errors="ignore").split()
        if len(words) < tokens:
            continue
        for j in range(0, len(words) - tokens, tokens):
            texts.append(" ".join(words[j : j + tokens]))
            if len(texts) >= n:
                return texts
    return texts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("model", nargs="?", default="mlx-community/Qwen3-4B-4bit")
    ap.add_argument("--stage", type=int, choices=(1, 2), default=1)
    ap.add_argument("--probes", type=int, default=24)
    ap.add_argument("--tokens", type=int, default=256)
    ap.add_argument("--layers", type=int, default=0, help="0 = every layer (smoke test: 2)")
    ap.add_argument("--heads", type=int, default=0, help="0 = every head")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    import mlx.core as mx
    from mlx_lm import load

    t0 = time.time()
    model, tok = load(a.model)
    inner = getattr(model, "model", model)
    layers = inner.layers
    n_layers, n_heads = len(layers), inner.args.num_attention_heads
    n_kv = getattr(inner.args, "num_key_value_heads", n_heads)
    out_path = Path(a.out) if a.out else ROOT / "data" / "runs" / f"qwen-audit-stage{a.stage}.json"

    ids = [tok.encode(t)[: a.tokens] for t in probes(a.probes, a.tokens)]
    ids = [x for x in ids if len(x) > 16]
    T = min(len(x) for x in ids)
    ids = [x[:T] for x in ids]
    print(f"{a.model}: {n_layers}L x {n_heads}H ({n_kv} KV) · {len(ids)} probes x {T} tokens", flush=True)

    if a.stage == 2:
        batch = mx.array(ids)

        def loss() -> float:
            logits = model(batch[:, :-1])
            lp = logits - mx.logsumexp(logits, axis=-1, keepdims=True)
            picked = mx.take_along_axis(lp, batch[:, 1:, None], axis=-1)[..., 0]
            return float(-picked.mean())

        base = loss()
        print(f"base loss {base:.4f} ({time.time() - t0:.0f}s)", flush=True)
        rows = []
        lay = range(n_layers) if not a.layers else range(min(a.layers, n_layers))
        for li in lay:
            attn = layers[li].self_attn
            proj, orig = attn.o_proj, attn.o_proj.__call__
            hd = attn.q_proj.weight.shape[0] // attn.n_heads
            for hi in (range(n_heads) if not a.heads else range(min(a.heads, n_heads))):

                def patched(x, _h=hi):
                    sl = slice(_h * hd, (_h + 1) * hd)
                    x = mx.concatenate([x[..., : sl.start], mx.zeros_like(x[..., sl]), x[..., sl.stop :]], axis=-1)
                    return orig(x)

                proj.__call__ = patched
                try:
                    d = loss() - base
                finally:
                    proj.__call__ = orig
                rows.append({"layer": li, "head": hi, "loss_delta": round(d, 5)})
            print(f"  layer {li}: {len(rows)} heads ({time.time() - t0:.0f}s)", flush=True)
        rows.sort(key=lambda r: -r["loss_delta"])
        out_path.write_text(json.dumps({"model": a.model, "probes": len(ids), "base_loss": base, "heads": rows}, indent=0))
        print(f"wrote {out_path}", flush=True)
        return 0

    # ---- stage 1: fingerprints
    captured: dict[int, list] = {}

    def wrap(li: int, attn):
        orig = attn.__call__

        def patched(x, mask=None, cache=None):
            B, L, D = x.shape
            q = attn.q_norm(attn.q_proj(x).reshape(B, L, attn.n_heads, -1)).transpose(0, 2, 1, 3)
            k = attn.k_norm(attn.k_proj(x).reshape(B, L, attn.n_kv_heads, -1)).transpose(0, 2, 1, 3)
            q = attn.rope(q) if cache is None else attn.rope(q, offset=cache.offset)
            k = attn.rope(k) if cache is None else attn.rope(k, offset=cache.offset)
            s = (q * attn.scale) @ k.transpose(0, 1, 3, 2)
            if mask is not None:
                s = s + mask
            captured[li] = mx.softmax(s, axis=-1)[0]  # (heads, L, L)
            return orig(x, mask, cache)

        attn.__call__ = patched

    for li in range(n_layers):
        wrap(li, layers[li].self_attn)

    stats: dict[tuple[int, int], dict] = {}
    for pi, seq in enumerate(ids):
        model(mx.array([seq]))
        arr = mx.array(seq)
        for li, probs in captured.items():
            p = probs  # (H, L, L)
            for h in range(p.shape[0]):
                row = p[h]
                prev = float(mx.mean(mx.diagonal(row, offset=-1)))
                sink = float(mx.mean(row[:, 0]))
                # distance profile: mean mass by how far back
                L = row.shape[0]
                dist = mx.arange(L)[None, :] - mx.arange(L)[:, None]  # (i, j): j - i, negative
                back = -dist
                prof = []
                lo = 1
                for hi in BINS:
                    m = (back >= lo) & (back < hi)
                    prof.append(float(mx.mean(mx.where(m, row, 0.0))) if bool(mx.any(m)) else 0.0)
                    lo = hi
                # induction: mass on the token after the last earlier occurrence of this token
                ind, copy = [], []
                for i in range(1, L):
                    same = [j for j in range(i) if seq[j] == seq[i]]
                    if not same:
                        continue
                    last = same[-1]
                    ind.append(float(row[i, last + 1]) if last + 1 < i else 0.0)
                    copy.append(float(row[i, last]))
                key = (li, h)
                s = stats.setdefault(key, {"prev": [], "sink": [], "prof": [], "ind": [], "copy": []})
                s["prev"].append(prev); s["sink"].append(sink)
                s["prof"].append(prof); s["ind"].append(sum(ind) / len(ind) if ind else 0.0)
                s["copy"].append(sum(copy) / len(copy) if copy else 0.0)
        if pi % 4 == 0:
            print(f"  probe {pi + 1}/{len(ids)} ({time.time() - t0:.0f}s)", flush=True)

    heads = []
    for (li, h), s in sorted(stats.items()):
        prof = [sum(p[k] for p in s["prof"]) / len(s["prof"]) for k in range(len(BINS))]
        heads.append({"layer": li, "head": h, "prev": round(sum(s["prev"]) / len(s["prev"]), 4),
                      "sink": round(sum(s["sink"]) / len(s["sink"]), 4),
                      "induction": round(sum(s["ind"]) / len(s["ind"]), 4),
                      "copy": round(sum(s["copy"]) / len(s["copy"]), 4),
                      "profile": [round(x, 4) for x in prof],
                      "kv_group": int(h * n_kv / n_heads)})
    # the KV question: how alike are the heads inside a group, against between groups
    import statistics

    def vec(x):
        return [x["prev"], x["sink"], x["induction"], x["copy"], *x["profile"]]

    groups: dict[int, list[list[float]]] = {}
    for x in heads:
        groups.setdefault(x["kv_group"], []).append(vec(x))
    within, between = [], []
    for g, vs in groups.items():
        for i in range(len(vs)):
            for j in range(i + 1, len(vs)):
                within.append(sum(abs(a - b) for a, b in zip(vs[i], vs[j])) / len(vs[i]))
    allv = [vec(x) for x in heads]
    for i in range(0, len(allv), 7):
        for j in range(i + 1, min(i + 8, len(allv))):
            between.append(sum(abs(a - b) for a, b in zip(allv[i], allv[j])) / len(allv[i]))
    out_path.write_text(json.dumps({
        "model": a.model, "probes": len(ids), "tokens": T, "layers": n_layers, "heads_per_layer": n_heads,
        "kv_heads": n_kv, "heads": heads,
        "kv_within_distance": round(statistics.mean(within), 4) if within else None,
        "kv_between_distance": round(statistics.mean(between), 4) if between else None,
    }, indent=0))
    print(f"wrote {out_path}: {len(heads)} heads", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

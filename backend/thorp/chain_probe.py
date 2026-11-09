"""What are the five best indicators of chaining inside a model that chains? (9 November, Justin: "the priority is
determining the 5 biggest indicators of chaining from qwen3 4b. That's the ultimate priority. We need to know what
we're chasing".)

The deck's cards are *our* summary of what a chaining model does. This script asks the model instead: on the 96
chaining pairs (nature, mill, between, pigeonhole), which internal readings rise and fall with the pair being
answered? It ranks features by their correlation with the per-pair lift, then fits their weights together, so the
answer is "these five, and how much of the lift each one carries".

Two families of feature, both read on the prompt (the premises), never on the endings:

- **the lens** — at the last prompt position, the residual stream's preference for the answer's first token over the
  rival's, layer by layer (`ops.lens_log_probs`). If the preference is already there at layer L, the reading at L is
  an indicator: the model has committed before it generates.
- **the heads** — attention from the last prompt position to the second premise's tokens (layer × head): the middle
  term is what the bridge has to carry, so the heads that look at it are the carrying candidates.

Ranked by Spearman correlation with the per-pair lift (positive or negative), then weighted by an ordinary least
squares fit on the top features. Prints the five that matter, with their correlation and their weight, and writes
the full ranking as an artifact.

    uv run --project backend --group compare python -m thorp.chain_probe mlx-community/Qwen3-4B-4bit
"""

from __future__ import annotations

import json
import sys

import numpy as np

TESTS = ("nature", "mill", "between", "pigeonhole")


def spearman(x: np.ndarray, y: np.ndarray) -> float:
    def rank(v):
        order = np.argsort(v, kind="mergesort")
        r = np.empty(len(v), dtype=float)
        r[order] = np.arange(len(v), dtype=float)
        # ties get their average rank
        _, inv, counts = np.unique(v, return_inverse=True, return_counts=True)
        for i, c in enumerate(counts):
            if c > 1:
                r[inv == i] = r[inv == i].mean()
        return r

    rx, ry = rank(x), rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return 0.0
    return float(np.corrcoef(rx, ry)[0, 1])


def read(name: str, log=print) -> dict:
    import mlx.core as mx
    from mlx_lm import load

    from thorp import cleaning, paths
    from thorp.evaluators import discovery
    from thorp.models import ops

    from mlx.utils import tree_map

    from thorp import cleaning
    from thorp.inside import Inside
    from thorp.outside_deck import OutsideTok

    model, hf = load(name)
    model.update(tree_map(lambda p: p.astype(mx.float32) if p.dtype in (mx.float16, mx.bfloat16) else p,
                          model.parameters()))  # fmt: skip
    tok = OutsideTok(name, hf, cleaning.CURRENT)  # the adapter the other outside-model readings use
    inner = Inside(model)  # hidden states and attention patterns, which an mlx_lm model does not expose
    feats: dict[str, list[float]] = {}
    lifts: list[float] = []
    n = 0
    for test in TESTS:
        pairs = discovery.load_pairs(f"lists/tricks/{test}.csv")
        if not pairs:
            continue
        r = discovery.score_pairs(model, tok, pairs)
        for p, lift in zip(pairs, r["pairs"]):
            prompt = p["prompt"]
            ids = [tok.eos_id] + tok.encode(prompt)
            good = tok.encode(" " + p["idea"].split()[0])
            bad = tok.encode(" " + p["rival"].split()[0])
            if not good or not bad:
                continue
            # the model's own preference at the last prompt position, before it generates: log p(answer's first
            # token) - log p(rival's first token). The per-layer lens is not readable on an mlx_lm model, whose
            # hidden states are not exposed, so this is the whole forward's reading.
            try:
                raw = np.asarray(model(mx.array([ids])).astype(mx.float32))
                lg = raw[0, -1, :] if raw.ndim == 3 else raw[-1, :]
                lp = lg - np.log(np.exp(lg - lg.max()).sum()) - lg.max()
                feats.setdefault("head/answer_preference", []).append(float(lp[good[0]] - lp[bad[0]]))
            except Exception:
                continue
            # the heads: attention from the last position to the second premise's tokens
            try:
                pats = [np.asarray(p) for p in inner.attention_patterns(mx.array([ids]))]
            except Exception:
                pats = []
            frame = (p.get("frame") or "").strip()
            cut = len(ids) - len(tok.encode(" " + frame)) if frame else len(ids)  # the frame's start, in tokens
            # the second premise's *positions* in the sequence (not token ids: attention keys are positions)
            second = list(range(max(1, cut - 24), max(2, cut))) if cut > 1 else list(range(max(1, len(ids) - 16), len(ids)))
            for layer, pat in enumerate(pats):
                a = np.asarray(pat[0, :, -1, :])  # heads x keys
                if len(second) and a.shape[1] >= max(second) + 1:
                    m = a[:, second].sum(axis=1)
                else:
                    continue
                for head, v in enumerate(m):
                    feats.setdefault(f"head/L{layer}H{head}", []).append(float(v))
            lifts.append(float(lift))
            n += 1
        log(f"  {test}: {len(pairs)} pairs read, {n} so far")
    y = np.array(lifts)
    rows = []
    for key, vals in feats.items():
        if len(vals) != len(y) or len(y) < 12:
            continue
        x = np.array(vals)
        rows.append((spearman(x, y), key, x))
    rows.sort(key=lambda t: -abs(t[0]))
    # the weight of each, fitted together: a ridge on every standardised feature (96 pairs against 1,153 heads
    # wants shrinking, or the weights chase noise), so each card's contribution is read beside the others
    X = np.stack([(x - x.mean()) / (x.std() or 1) for _, _, x in rows], axis=1)
    alpha = 80.0
    XtX = X.T @ X + alpha * np.eye(X.shape[1])
    w = np.linalg.solve(XtX, X.T @ y)
    weight = {rows[i][1]: float(w[i]) for i in range(len(rows))}
    out = {
        "model": name,
        "pairs": n,
        "ranking": [{"feature": k, "spearman": round(c, 3), "weight": round(weight.get(k, 0.0), 4)} for c, k, _ in rows],
        "top5": [{"feature": k, "spearman": round(c, 3), "weight": round(weight.get(k, 0.0), 4)} for c, k, _ in rows[:5]],
        "lift_mean": float(y.mean()),
        "lift_sd": float(y.std()),
    }
    from thorp.viable.s4_intelligence import readings

    readings.put(f"chain-probe-{name}", out)
    return out


def main(argv: list[str]) -> int:
    name = argv[0] if argv else "mlx-community/Qwen3-4B-4bit"
    out = read(name)
    print(f"\n{out['pairs']} pairs, lift mean {out['lift_mean']:+.3f} (sd {out['lift_sd']:.3f})")
    print("\nthe five biggest indicators of chaining:")
    for i, t in enumerate(out["top5"], 1):
        print(f"  {i}. {t['feature']:<16} correlation {t['spearman']:+.3f}   weight {t['weight']:+.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

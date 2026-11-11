"""The comprehensive head census of an outside model: every head, every kind the toolkit can measure, every
card it plays, every layer, what else names each head, the ten kinds with no star metric, and the heads the
sixteen cards do not name at all (Justin, 10 November).

Run one phase per process, because the stars evaluator holds every layer's attention at once and a 4B
model's patterns plus its weights overflow a 32 GB Mac when several phases share one process. Each phase
loads the model, writes its piece to `data/head-trace/census/<phase>.json`, and exits; `assemble` merges
them into `s4.outside_readings` as `heads-<model>`. Running the phases in a loop is the whole audit:

    for ph in stars cards nevermore pips char features; do
      python -m thorp.head_census mlx-community/Qwen3-4B-4bit --context 256 --phase $ph
    done
    python -m thorp.head_census mlx-community/Qwen3-4B-4bit --phase assemble

What the phases read:
- **stars**: the eleven measurable kinds (thorp/evaluators/stars.py: previous word, two and three words
  back, the sink, the delimiter, the rare word, the duplicate word), with their full (layers, heads) matrix;
- **cards**: the mover, comparator and bridge (thorp/evaluators/cards.py), with their matrices;
- **nevermore**: the induction reading and its copy gain;
- **pips**: the pips (the remaining card abilities);
- **char**: what else names a head: entropy, concentration, the sink and previous-token shares, and the
  routing to numbers, words, operators and commands, on the stars' natural passages;
- **features**: the discovery pass. On a battery of prompts (natural prose, a maths problem, code, a series,
  a repetition, a needle in a long context, a pronoun and its name), every head's behaviour is reduced to a
  feature vector (position buckets, token classes, induction, copying, successor, retrieval, coreference,
  entropy, concentration) and the 1,152 heads are clustered. A cluster whose behaviour no card names is a
  candidate for one of the ten kinds with no star metric: the "cards outside the sixteen".

The ten kinds with no star metric are named in `UNMEASURED`, with the test each would need; the census does
not claim they are absent, only that no evaluator has read them. The discovery phase gives the clusters
that a later, targeted test would start from.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

OUT = Path("data/head-trace/census")

UNMEASURED = {
    "fuzzy_induction": ("Fuzzy and translation induction head",
                        "an induction head that matches a near copy, not an exact one",
                        "Olsson et al. 2022", "the Nevermore's reading with the key and query edited to near copies"),
    "retrieval": ("Retrieval head", "finds a fact stated far back in a long context and copies it out",
                  "Wu et al. 2024", "a needle stated early and asked for at the end; attention back to it"),
    "successor": ("Successor head", "given an item of an ordered series, pushes up the next one",
                  "Gould et al. 2023", "attention from a series item to the item after it, against random pairs"),
    "s_inhibition": ("S-inhibition head", "marks that a name is repeated, so later heads leave it out",
                     "Wang et al. 2022", "attention from the indirect object to the repeated name, and its logit drop"),
    "backup_name_mover": ("Backup name mover", "does a name mover's job only when the movers are knocked out",
                          "Wang et al. 2022", "the mover reading with the movers silenced: a score that rises then"),
    "negative_name_mover": ("Negative name mover", "attends to the right name and pushes its logit down",
                            "Wang et al. 2022", "the mover reading with the sign reversed"),
    "copy_suppression": ("Copy-suppression head", "brakes the copying of an over-predicted earlier word",
                         "McDougall et al. 2023", "attention at a repeated word to its earlier copy, and its logit pushed down"),
    "syntactic": ("Syntactic head", "follows a grammatical relation (verb to subject, noun to determiner)",
                  "Voita et al. 2019", "a parsed sentence's dependency arcs over an even share"),
    "coreference": ("Coreference head", "from a pronoun, attends to the name it stands for",
                    "Clark et al. 2019", "attention from each pronoun to its antecedent"),
    "function_vector": ("Function-vector head", "carries what the task is from a few examples in the prompt",
                        "Todd et al. 2023", "the mean shift a few-shot prompt puts on the heads"),
}

CARD_STARS = ("previous_word", "duplicate_word", "nevermore", "attention_sink", "delimiter", "offset_2",
              "offset_3", "rare_word", "mover", "comparator", "bridge")
CARD_NAME = {"previous_word": "Previous-word", "duplicate_word": "Duplicate-word", "nevermore": "The Nevermore",
             "attention_sink": "The Sink", "delimiter": "The Delimiter", "offset_2": "Words Back",
             "offset_3": "Words Back", "rare_word": "The Rare Word", "mover": "The Mover",
             "comparator": "The Comparator", "bridge": "The Bridge"}


def _load(name, context):
    import mlx.core as mx
    from mlx.utils import tree_map

    from thorp import cleaning
    from thorp.hooked import load
    from thorp.inside import Inside
    from thorp.outside_deck import OutsideTok

    model, t = load(name)
    model.update(tree_map(lambda p: p.astype(mx.float32) if p.dtype in (mx.float16, mx.bfloat16) else p,
                          model.parameters()))  # fmt: skip
    return model, OutsideTok(name, t, cleaning.CURRENT), Inside(model), t


def _ctx(name, tok, inner, context):
    from thorp.evaluators import EvalContext
    from thorp.outside_deck import _list_ids

    return EvalContext(run_id="outside:" + name, step=0, model=inner, tokeniser=tok, context=context,
                       sets={"hole-cards-unseen": _list_ids("lists/hole-cards-unseen.csv")},
                       recipe=_list_ids("lists/ogden-v0.1.csv"))


def _save(name, phase, data):
    OUT.mkdir(parents=True, exist_ok=True)
    key = name.replace("/", "--")
    (OUT / f"{key}__{phase}.json").write_text(json.dumps(data))


def _load_saved(name, phase):
    key = name.replace("/", "--")
    p = OUT / f"{key}__{phase}.json"
    return json.loads(p.read_text()) if p.exists() else None


def _num(x):
    return None if x is None or not np.isfinite(x) else float(x)


# ---------------------------------------------------------------- corpus for the discovery pass
PROMPTS = {
    "prose": (
        "The old librarian kept the ledger in a green cupboard behind the reading room. Every morning she "
        "opened it and wrote down the books that had come back and the books that were still out. "
        "When a book was overdue she wrote the borrower's name in red ink, and the name stayed there "
        "until the book came home."
    ),
    "maths": (
        "Solve for x: 3x + 7 = 2x + 22. Subtract 2x from both sides, so x + 7 = 22. Subtract 7 from both "
        "sides, so x = 15. Check: 3 times 15 plus 7 is 52, and 2 times 15 plus 22 is 52. The answer is 15."
    ),
    "code": (
        "def total(xs):\n    s = 0\n    for x in xs:\n        s += x\n    return s\n\n"
        "The function walks the list and adds each item to s, then returns the sum."
    ),
    "series": "Monday, Tuesday, Wednesday, Thursday, Friday, Saturday, Sunday. January, February, March, April, May.",
    "repeat": ("The raven said nevermore and the raven said nevermore and the raven said nevermore, "
               "so the raven said nevermore."),
    "coref": ("Elizabeth went to the market. She bought bread, and she gave it to Darcy. "
              "Darcy thanked her, and then he walked with her to the river."),
    "syntax": ("The quick brown fox jumps over the lazy dog while the tired cat watches from the warm windowsill."),
    "needle": ("FACT: the vault code is 1947. " + "The weather was mild and the streets were quiet. " * 30
               + "Question: what is the vault code?"),
}
SERIES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "January", "February",
          "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def _mask_for(pieces):
    import re

    return {
        "number": np.array([bool(re.match(r"^[0-9]+(\.[0-9]+)?$", p)) for p in pieces]),
        "word": np.array([bool(re.match(r"^[A-Za-z]+$", p)) for p in pieces]),
        "operator": np.array([bool(re.match(r"^[=+\-*/^<>()\[\].,]$", p)) for p in pieces]),
        "punct": np.array([bool(re.match(r"^[.,;:!?()\[\]{}]$", p)) for p in pieces]),
        "newline": np.array([("\n" in p) for p in pieces]),
        "latex": np.array([bool(re.match(r"^\\[a-zA-Z]+$", p)) for p in pieces]),
    }


def _feature_block(inner, tok, prompt):
    """One (layers, heads) feature block for one prompt, streamed layer by layer."""
    import mlx.core as mx

    ids = tok.encode(prompt)
    T = len(ids)
    pieces = [tok.decode([i]) for i in ids]
    masks = _mask_for(pieces)
    q = np.arange(1, T)
    last, tgt = {}, np.full(T, -1, np.int64)
    for t, x in enumerate(ids):
        j = last.get(x)
        if j is not None and j + 1 < t:
            tgt[t] = j + 1
        last[x] = t
    ind = np.array([t for t in q if tgt[t] >= 0], np.int64)
    feats: dict[str, np.ndarray] = {}
    dims = {"nl": None, "nh": None}
    # rows are the attention layers in order, as the evaluators' matrices are (Inside.pattern_layers names
    # their real layers; on a pure-attention model row and layer are the same); the callback gives real ones
    row_of = {layer: r for r, layer in enumerate(inner.pattern_layers)}

    def cb(layer, w):
        li = row_of[layer]
        w = np.array(w[0].astype(mx.float32))  # (H, T, T)
        if dims["nl"] is None:
            dims["nl"], dims["nh"] = len(row_of), w.shape[0]
            keys = ("sink", "prev", "prev2", "local", "distal", "entropy", "concentration",
                    "induction", "successor", "copy") + tuple(f"r_{k}" for k in masks)
            feats.update({k: np.zeros((dims["nl"], dims["nh"])) for k in keys})
        nh = dims["nh"]
        wq = w[:, q, :]
        feats["sink"][li] = wq[:, :, 0].mean(-1)
        qi = np.arange(len(q))
        feats["prev"][li] = wq[:, qi, q - 1].mean(-1)
        feats["prev2"][li] = wq[:, qi, np.maximum(q - 2, 0)].mean(-1)
        feats["local"][li] = np.stack([wq[:, i, max(0, q[i] - 8):q[i]].mean(-1) for i in range(len(q))]).mean(0)
        feats["distal"][li] = np.stack([
            wq[:, i, : max(0, q[i] - 64)].mean(-1) if q[i] > 64 else np.zeros(nh) for i in range(len(q))
        ]).mean(0)
        s = wq / np.maximum(wq.sum(-1, keepdims=True), 1e-12)
        feats["entropy"][li] = -(s * np.log(np.maximum(s, 1e-12))).sum(-1).mean(-1)
        feats["concentration"][li] = (wq.max(-1) - (1.0 / (q + 1))[None, :]).mean(-1)
        if ind.size:
            feats["induction"][li] = w[:, ind, tgt[ind]].mean(-1)
            feats["successor"][li] = w[:, ind, np.minimum(tgt[ind] + 1, T - 1)].mean(-1)
            feats["copy"][li] = w[:, ind, tgt[ind] - 1].mean(-1)
        for k, m in masks.items():
            if m.any():
                feats[f"r_{k}"][li] = (wq @ m.astype(np.float32)).mean(-1) / (m.sum() / T)

    inner.attention_patterns(mx.array([ids]), on_layer=cb)
    return feats


def phase_features(name, context, log=print):
    """The discovery pass: every head's behaviour on the battery, the mean over prompts, then k-means."""
    import mlx.core as mx

    model, tok, inner, _ = _load(name, context)
    acc: dict[str, list[np.ndarray]] = {}
    for pname, prompt in PROMPTS.items():
        try:
            f = _feature_block(inner, tok, prompt)
        except Exception as e:  # noqa: BLE001
            log(f"  {pname}: failed ({e})")
            continue
        for k, v in f.items():
            acc.setdefault(k, []).append(v)
        log(f"  {pname}: {f['sink'].shape[0]} layers x {f['sink'].shape[1]} heads")
        mx.clear_cache()
    if not acc:
        raise RuntimeError("no features read")
    mean = {k: np.mean(np.stack(v), axis=0) for k, v in acc.items()}
    nl, nh = mean["sink"].shape
    names = sorted(mean)
    X = np.stack([mean[k].ravel() for k in names], axis=1)
    Xs = (X - X.mean(0)) / (X.std(0) + 1e-9)
    rng = np.random.default_rng(1859)
    k = 16
    cent = Xs[rng.choice(len(Xs), k, replace=False)].copy()
    for _ in range(40):
        d = ((Xs[:, None, :] - cent[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for c in range(k):
            if (lab == c).any():
                cent[c] = Xs[lab == c].mean(0)
    CLUSTER_NAME = {
        "r_number": "Number and arithmetic", "successor": "Series successor",
        "copy": "Copy and copy-suppression", "induction": "Induction (repeated-token follow-on)",
        "prev": "Previous token", "prev2": "Two tokens back", "r_newline": "Line breaks and layout",
        "r_punct": "Delimiter and punctuation", "r_operator": "Operators", "sink": "Attention sink",
        "distal": "Far past", "local": "Local window", "entropy": "Diffuse attention",
        "concentration": "Sharp peak", "r_word": "Word routing", "r_latex": "LaTeX commands",
    }
    label_of = {
        "sink": "the window's opening mark", "prev": "the previous token", "prev2": "two tokens back",
        "local": "the local window", "distal": "the far past", "entropy": "broad attention",
        "concentration": "a sharp peak", "induction": "a repeated token's follow-on",
        "successor": "the next series item", "copy": "an earlier copy of the token",
        "r_number": "numbers", "r_word": "words", "r_operator": "operators", "r_punct": "punctuation",
        "r_newline": "line breaks", "r_latex": "LaTeX commands",
    }
    base = X.mean(0)
    clusters = []
    for c in range(k):
        idx = np.where(lab == c)[0]
        if not len(idx):
            continue
        means = {n: float(mean[n].ravel()[idx].mean()) for n in names}
        top = sorted(names, key=lambda n: -abs(means[n] - base[names.index(n)]))[:4]
        clusters.append({
            "id": c, "size": int(len(idx)),
            "heads": [[int(i // nh), int(i % nh)] for i in idx],
            "means": means, "top_keys": top, "top": [label_of.get(t, t) for t in top],
            "name": CLUSTER_NAME.get(top[0], label_of.get(top[0], top[0])),
        })
    clusters.sort(key=lambda c: -c["size"])
    out = {"model": name, "context": context, "layers": int(nl), "heads": int(nh),
           "features": names, "clusters": clusters, "attention_layers": inner.pattern_layers}
    _save(name, "features", out)
    log(f"  {nl}x{nh} heads clustered into {len(clusters)} groups")
    return out


def phase_char(name, context, log=print):
    from thorp.evaluators import stars

    model, tok, inner, _ = _load(name, context)
    nat = stars.passages(tok, context)
    pats = stars.patterns(inner, nat)
    T = nat.shape[1]
    nl, nh = len(pats), pats[0].shape[1]
    q = np.arange(1, T)
    out = {k: np.zeros((nl, nh)) for k in ("sink", "previous", "entropy", "concentration",
                                           "number", "word", "operator", "command", "ping", "ping_share")}
    pieces = [tok.decode([int(i)]) for i in nat[0]]
    masks = _mask_for(pieces)
    qi = np.arange(len(q))
    for li, p in enumerate(pats):
        w = p[:, :, q, :]
        out["sink"][li] = w[:, :, :, 0].mean(axis=(0, 2))
        out["previous"][li] = w[:, :, qi, q - 1].mean(axis=(0, 2))
        s = w / np.maximum(w.sum(-1, keepdims=True), 1e-12)
        out["entropy"][li] = -(s * np.log(np.maximum(s, 1e-12))).sum(-1).mean(axis=(0, 2))
        out["concentration"][li] = (w.max(-1) - (1.0 / (q + 1))[None, None, :]).mean(axis=(0, 2))
        # a ping: a query token on which the head puts at least half its attention on one key. The count
        # is how often the head is used on the natural passages; the share makes the heads comparable.
        # fired is (batch, heads, queries): sum over the batch and the queries, one number a head.
        fired = w.max(-1) >= 0.5
        out["ping"][li] = fired.sum(axis=(0, 2))
        out["ping_share"][li] = fired.mean(axis=(0, 2))
        for k in ("number", "word", "operator", "command"):
            m = masks.get(k)
            if m is not None and m.any():
                out[k][li] = (w @ m.astype(np.float32)).mean(axis=(0, 2)) / (m.sum() / T)
    _save(name, "char", {"model": name, **{k: v.tolist() for k, v in out.items()},
                         "attention_layers": inner.pattern_layers})
    log(f"  characteristics and pings on {nl}x{nh} heads")
    return out


def phase_eval(name, context, which, log=print):
    from thorp.evaluators import cards, nevermore, pips, stars
    from thorp.viable.s4_intelligence import readings

    model, tok, inner, _ = _load(name, context)
    ctx = _ctx(name, tok, inner, context)
    ev = {"stars": stars, "cards": cards, "nevermore": nevermore, "pips": pips}[which]
    res = ev.evaluate(ctx)
    matrices = {}
    for art in getattr(res, "artifacts", []) or []:
        text = art.get("text") if isinstance(art, dict) else getattr(art, "text", None)
        try:
            doc = json.loads(text or "{}")
        except (ValueError, TypeError):
            continue
        for k, v in doc.items():
            if isinstance(v, list) and v and isinstance(v[0], list):
                matrices[k] = v
    _save(name, which, {"model": name, "metrics": {k: _num(v) for k, v in res.metrics.items()},
                        "matrices": matrices})
    log(f"  {which}: {len(res.metrics)} readings, {len(matrices)} matrices")
    return res.metrics


def assemble(name, context, log=print):
    """Merge the phases into the inventory, the named/unnamed split and the one reading."""
    from thorp import fleet
    from thorp.viable.s4_intelligence import readings

    parts = {p: _load_saved(name, p) for p in ("stars", "cards", "nevermore", "pips", "char", "features")}
    matrices, metrics = {}, {}
    for p in ("stars", "cards", "nevermore", "pips"):
        if parts[p]:
            matrices.update(parts[p].get("matrices", {}))
            metrics.update(parts[p].get("metrics", {}))
    char = parts.get("char") or {}
    th = {k: getattr(v, "threshold", None) for k, v in fleet.STARS.items()}
    nl = len(next(iter(matrices.values()))) if matrices else (char.get("sink") and len(char["sink"])) or 36
    nh = len(next(iter(matrices.values()))[0]) if matrices else (char.get("sink") and len(char["sink"][0])) or 32

    # every phase works in rows (the attention layers in order); the inventory and the bests are named by
    # real layer (11 November). A phase saved before then carries no map: its rows are taken as layers,
    # which is right for a pure-attention model
    real = ((parts.get("features") or {}).get("attention_layers") or char.get("attention_layers")
            or list(range(nl)))

    def at(v, li, hi):
        return v is not None and li < len(v) and hi < len(v[li])

    inventory, named = [], 0
    rows_of: dict[tuple[int, int], dict] = {}
    for li in range(nl):
        for hi in range(nh):
            row = {"layer": int(real[li]), "head": hi}
            rows_of[(li, hi)] = row
            for k, m in matrices.items():
                if at(m, li, hi):
                    row[k] = _num(m[li][hi])
            for k in ("sink", "previous", "entropy", "concentration", "number", "word", "operator", "command",
                      "ping", "ping_share"):
                if at(char.get(k), li, hi):
                    row[k] = _num(char[k][li][hi])
            lit = [k for k in matrices if k in th and th[k] is not None and row.get(k) is not None
                   and row[k] >= th[k]]
            row["lit"] = lit
            row["named"] = bool(lit)
            named += bool(lit)
            inventory.append(row)

    kinds = {}
    for k, m in matrices.items():
        a = np.array(m, dtype=float)
        if not np.isfinite(a).any():
            continue
        li, hi = np.unravel_index(int(np.nanargmax(a)), a.shape)
        kinds[k] = {"best": f"{int(real[li])}.{int(hi)}", "layer": int(real[li]), "head": int(hi), "score": _num(a[li, hi]),
                    "threshold": th.get(k), "n_at_or_above": int((a >= th[k]).sum()) if th.get(k) else None}

    clusters = (parts.get("features") or {}).get("clusters", [])
    # name each cluster by its most distinctive specific feature; word routing, entropy and the sink are
    # generic and would name almost every cluster, so they are not allowed to
    if clusters:
        names = sorted(clusters[0]["means"])
        M = np.array([[c["means"][n] for n in names] for c in clusters])
        Z = (M - M.mean(0)) / (M.std(0) + 1e-9)
        SPEC = {"r_number": "Number and arithmetic", "successor": "Series successor",
                "copy": "Copy and copy-suppression", "induction": "Induction (repeated-token follow-on)",
                "prev": "Previous token", "prev2": "Two tokens back", "r_punct": "Delimiter and punctuation",
                "r_newline": "Line breaks and layout", "r_operator": "Operators", "r_latex": "LaTeX commands",
                "local": "Local window"}
        for i, c in enumerate(clusters):
            cands = [(n, Z[i][j]) for j, n in enumerate(names) if n in SPEC]
            if cands:
                n, z = max(cands, key=lambda x: abs(x[1]))
                c["name"] = SPEC[n] if abs(z) >= 1.5 else "Diffuse / generic"
            else:
                c["name"] = "Diffuse / generic"
    cluster_of, cat_of = {}, {}
    for cl in clusters:
        for pair in cl.get("heads", []):
            cluster_of[(int(pair[0]), int(pair[1]))] = cl.get("id")
            cat_of[(int(pair[0]), int(pair[1]))] = cl.get("name")
    for key, row in rows_of.items():  # the clusters' heads are rows, as the features phase read them
        row["cluster"] = cluster_of.get(key)
        row["category"] = cat_of.get(key)
    for cl in clusters:  # and are reported by real layer, as the inventory is
        cl["heads"] = [[int(real[int(r)]), int(h)] for r, h in cl.get("heads", [])]

    unnamed = sorted([r for r in inventory if not r["named"]],
                     key=lambda r: -(r.get("concentration") or 0))[:40]
    clusters = (parts.get("features") or {}).get("clusters", [])
    out = {
        "model": name, "read": time.strftime("%Y-%m-%dT%H:%M:%S"), "context": context,
        "layers": nl, "heads": nh, "n_heads": nl * nh, "n_named": named, "n_unnamed": nl * nh - named,
        "kinds_measured": sorted(matrices), "kinds_unmeasured": UNMEASURED,
        "cards": {k: CARD_NAME[k] for k in matrices if k in CARD_NAME},
        "kinds": kinds, "unnamed": unnamed, "inventory": inventory,
        "clusters": clusters, "matrices": matrices, "metrics": {k: _num(v) for k, v in metrics.items()},
        "attention_layers": [int(x) for x in real],  # the real layer of each matrix row
    }
    key = "heads-" + name.replace("/", "--")
    readings.put(key, {**out, "name": key, "kind": "heads"})
    log(f"{name}: {nl}x{nh} heads, {named} named, {nl*nh-named} unnamed, {len(clusters)} clusters -> {key}")
    return out


def main(argv=None):
    import argparse

    p = argparse.ArgumentParser(prog="thorp.head_census")
    p.add_argument("model")
    p.add_argument("--context", type=int, default=256)
    p.add_argument("--phase", default="all",
                   choices=["stars", "cards", "nevermore", "pips", "char", "features", "assemble", "all"])
    a = p.parse_args(argv)
    phases = ["stars", "cards", "nevermore", "pips", "char", "features"] if a.phase == "all" else [a.phase]
    for ph in phases:
        if ph == "assemble":
            assemble(a.model, a.context)
        elif ph == "char":
            phase_char(a.model, a.context)
        elif ph == "features":
            phase_features(a.model, a.context)
        else:
            phase_eval(a.model, a.context, ph)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

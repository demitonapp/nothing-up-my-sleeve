"""The deck knocked out of an outside model (Justin, 2026-11-08 12:40: "let's go spy on Qwen's weights to see how the
deck impacts its chaining gains"): which cards, and which suits, does a model that chains actually chain *with*?

The knockout of 7 November (thorp/knockout.py) silenced the 8 strongest heads of four cards in Qwen3 4B and found
none necessary, but its random controls moved the cause gain as much as any card (one by -0.26): 8 heads of 1,152
and an 8-item reading. This one reads every card the deck reads by heads, more heads, whole suits, and a deck five
times the size:

- **The cards' heads:** for each card read by attention (the ten metre cards, the comparator, the Mover), its K
  strongest heads on the model itself, by the same readings that judge the card (stars, pips, nevermore, cards).
  The Bridge is read in the residual stream, not by a head: its best layer is silenced whole (every head of that
  layer), against a random layer. The Counter (a probe) has no heads of its own and is not knocked out.
- **The suits:** each suit's cards' heads together (♠ previous-word, duplicate-word, induction; ♥ the sink, the
  delimiter, words back; ♦ number-spotter, order-word, the comparator; ♣ the rare word, premise-marker, the Mover).
- **Measured:** the 40-item logic deck (`lists/tricks/logic-40.csv`): the chaining gain overall and in each
  relation, and the one-hop lift; each condition's change from the unsilenced model with a paired bootstrap band
  over items (the same items resampled for both).
- **Controls:** random heads from outside every card's set, as many as a card (CONTROLS draws) and as a suit.

A card **carries** chaining in the model when silencing it lowers the overall gain by more than the largest random
draw of its size does and the band of the drop stays above zero. Results: s4.outside_readings, knockout-deck-<model>.

    uv run --project backend --group compare python -m thorp.knockout_deck mlx-community/Qwen3-4B-4bit
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np

K = 16
CONTROLS = 3
SEED = 1859
DECK = "lists/tricks/logic-40.csv"
RELATIONS = ("order", "cause", "membership", "proportion", "counterfactual")
SUITS = {
    "copying": ("previous_word", "duplicate_word", "induction"),
    "position": ("sink", "delimiter", "words_back"),
    "comparing": ("number_spotter", "order_word", "comparator"),
    "carrying": ("rare_word", "premise_marker", "mover"),
}


def card_matrices(inner, tok) -> dict[str, np.ndarray]:
    """Each attention card's layer x head readings on this model, by the deck's own readings."""
    from thorp.evaluators import EvalContext, cards, nevermore, pips, stars
    from thorp.evaluators.logic import load_deck
    from thorp.outside_deck import NATURAL_CONTEXT, _list_ids

    ctx = EvalContext(run_id="knockout", step=0, model=inner, tokeniser=tok, context=NATURAL_CONTEXT,
                      sets={"hole-cards-unseen": _list_ids("lists/hole-cards-unseen.csv")},
                      recipe=_list_ids("lists/ogden-v0.1.csv"))  # fmt: skip
    out: dict[str, np.ndarray] = {}
    st = json.loads(stars.evaluate(ctx).artifacts[0]["text"])
    for card, key in (("previous_word", "previous_word"), ("words_back", "offset_2"), ("sink", "attention_sink"),
                      ("delimiter", "delimiter"), ("rare_word", "rare_word"), ("duplicate_word", "duplicate_word")):  # fmt: skip
        if key in st:
            out[card] = np.array(st[key])
    nv = json.loads(nevermore.evaluate(ctx).artifacts[0]["text"])
    if "natural_scores" in nv:
        out["induction"] = np.array(nv["natural_scores"])
    pp = pips.evaluate(ctx)
    if pp.artifacts:
        rec = json.loads(pp.artifacts[0]["text"])
        for card in ("number_spotter", "order_word", "premise_marker"):
            if card in rec:
                out[card] = np.array(rec[card]["scores"])
    deck = load_deck()
    out["comparator"] = cards.comparator(inner, tok)
    mv = cards.mover(inner, tok, deck)
    if mv is not None:
        out["mover"] = mv
    br = cards.bridge(inner, tok, deck)
    out["_bridge_curve"] = br if br is not None else np.zeros(0)
    return out


def top_heads(m: np.ndarray, k: int) -> list[tuple[int, int]]:
    flat = np.argsort(-np.nan_to_num(m, nan=-1e9), axis=None)[:k]
    return [tuple(int(x) for x in np.unravel_index(i, m.shape)) for i in flat]


def as_layers(heads) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for layer, head in heads:
        out.setdefault(int(layer), []).append(int(head))
    return out


def gains(items: dict, idx_by_rel: dict[str, list[str]], pick: dict[str, np.ndarray] | None = None) -> dict:
    """The chaining gain overall and per relation (both premises less the stronger single premise, from the
    relation's means, as score_deck reads it) and the one-hop lift, on the items picked (all when None)."""
    out, per = {}, []
    for rel, ks in idx_by_rel.items():
        ks = [ks[i] for i in pick[rel]] if pick else ks
        both = np.mean([items[k]["both"] for k in ks])
        g = float(both - max(np.mean([items[k]["first"] for k in ks]), np.mean([items[k]["second"] for k in ks])))
        out[rel] = g
        per.append(g)
    out["gain"] = float(np.mean(per))
    hop = [items[k]["one_hop"] for ks in idx_by_rel.values() for k in ks if "one_hop" in items[k]]
    out["one_hop"] = float(np.mean(hop)) if hop else None
    return out


def read(name: str, k: int = K, controls: int = CONTROLS, log=print) -> dict:
    import mlx.core as mx
    from mlx.utils import tree_map

    from thorp import cleaning
    from thorp.evaluators.logic import load_deck, score_deck
    from thorp.hooked import load
    from thorp.inside import Inside
    from thorp.outside_deck import OutsideTok

    t0 = time.time()
    model, t = load(name)
    model.update(tree_map(lambda p: p.astype(mx.float32) if p.dtype in (mx.float16, mx.bfloat16) else p, model.parameters()))
    tok = OutsideTok(name, t, cleaning.CURRENT)
    inner = Inside(model)
    # the shape from the model's own map (11 November), real layer indices throughout
    n_layers = inner.n_layers
    n_heads = inner.heads_of(inner.attention_layers[0])
    mats = card_matrices(inner, tok)
    curve = mats.pop("_bridge_curve")
    # a card's rows are the attention layers in order (pattern_layers); its heads are named by real layer
    real = inner.pattern_layers
    heads = {c: [(real[r], h) for r, h in top_heads(m, k)] for c, m in mats.items()}
    bridge_layer = int(np.argmax(curve)) if len(curve) else None  # read in the residual stream: a real layer
    bridge_kind = inner.layer_map[bridge_layer]["kind"] if bridge_layer is not None else None
    log(f"{name}: {n_layers} layers x {n_heads} heads; cards {sorted(heads)}; the Bridge's layer {bridge_layer} ({time.time() - t0:.0f}s)")
    deck = load_deck(DECK)
    rels = {}
    for r in deck:
        rels.setdefault(r["relation"], set()).add(r["item"])
    idx = {rel: sorted(v) for rel, v in rels.items()}

    def run(silence: dict) -> dict:
        # a whole layer may be a linear-attention layer on a hybrid model: edited() zeroes its value heads
        with inner.edited({la: {"zero": hs} for la, hs in silence.items()}):
            return score_deck(inner, tok, deck)["items"]

    conds: dict[str, dict] = {"baseline": {"heads": {}}}
    for c, hs in heads.items():
        conds[c] = {"heads": as_layers(hs)}
    for s, cs in SUITS.items():
        hs = sorted({h for c in cs if c in heads for h in heads[c]})
        conds["suit:" + s] = {"heads": as_layers(hs), "n": len(hs)}
    if bridge_layer is not None:
        conds["bridge_layer"] = {"heads": {bridge_layer: list(range(inner.heads_of(bridge_layer)))}}
    taken = {h for hs in heads.values() for h in hs}
    every = inner.head_pool()  # attention heads only, each layer's real count (Qwen3 4B: the old order)
    pool = [x for x in every if x not in taken]

    def draw(n):  # random heads outside every card's set; from all heads where too few lie outside (small models)
        src = pool if len(pool) >= n else every
        return [src[j] for j in rng.choice(len(src), min(n, len(src)), replace=False)]

    rng = np.random.default_rng(SEED)
    suit_n = max(c.get("n", 0) for c in conds.values())
    for i in range(controls):
        conds[f"control:{k}:{i}"] = {"heads": as_layers(draw(k))}
        conds[f"control:{suit_n}:{i}"] = {"heads": as_layers(draw(suit_n))}
    if bridge_layer is not None:
        # another layer of the Bridge's own kind, whole
        others = [m["layer"] for m in inner.layer_map if m["kind"] == bridge_kind and m["layer"] != bridge_layer]
        other = int(rng.choice(others))
        conds["control:layer"] = {"heads": {other: list(range(inner.heads_of(other)))}}
    items = {}
    for c, spec in conds.items():
        items[c] = run(spec["heads"])
        log(f"  {c:22} gain {gains(items[c], idx)['gain']:+.3f}  ({time.time() - t0:.0f}s)")
    base = gains(items["baseline"], idx)
    boots = [{rel: rng.integers(0, len(v), len(v)) for rel, v in idx.items()} for _ in range(1000)]
    result = {"model": name, "k": k, "layers": n_layers, "heads": n_heads, "deck": DECK, "bridge_layer": bridge_layer,
              "card_heads": {c: [list(h) for h in hs] for c, hs in heads.items()}, "baseline": base, "conditions": {}}  # fmt: skip
    for c in conds:
        if c == "baseline":
            continue
        g = gains(items[c], idx)
        drops = [gains(items["baseline"], idx, b)["gain"] - gains(items[c], idx, b)["gain"] for b in boots]
        lo, hi = np.percentile(drops, [5, 95])
        result["conditions"][c] = {**g, "drop": base["gain"] - g["gain"], "drop_lo": float(lo), "drop_hi": float(hi),
                                   "relation_drops": {rel: base[rel] - g[rel] for rel in idx}}  # fmt: skip
    ctl = {n: max(v["drop"] for c, v in result["conditions"].items() if c.startswith(f"control:{n}:")) for n in (k, suit_n)}
    verdict = {}
    for c, v in result["conditions"].items():
        if c.startswith("control"):
            continue
        size = suit_n if c.startswith("suit:") else (None if c == "bridge_layer" else k)
        noise = result["conditions"]["control:layer"]["drop"] if size is None and "control:layer" in result["conditions"] else ctl.get(size, 0.0)
        verdict[c] = {"drop": round(v["drop"], 4), "band": [round(v["drop_lo"], 4), round(v["drop_hi"], 4)],
                      "largest_random": round(noise, 4), "carries": bool(v["drop"] > max(noise, 0) and v["drop_lo"] > 0)}  # fmt: skip
    result["verdict"] = verdict
    result["seconds"] = round(time.time() - t0)
    from thorp.viable.s4_intelligence import readings

    out = f"knockout-deck-{name.replace('/', '--')}"
    readings.put(out, result)
    log(f"{name}: kept as {out} in s4.outside_readings ({result['seconds']}s)")
    return result


if __name__ == "__main__":
    from thorp import vsm

    for name in sys.argv[1:]:
        with vsm.at_sea(f"knock the deck out of {name}", kind="score"):
            r = read(name)
        for c, v in sorted(r["verdict"].items(), key=lambda x: -x[1]["drop"]):
            print(f"  {c:22} drop {v['drop']:+.3f} [{v['band'][0]:+.3f}, {v['band'][1]:+.3f}] random {v['largest_random']:+.3f}"
                  f"{'  CARRIES' if v['carries'] else ''}")

"""The knockout (2026-11-07, Justin: "add that as another voyage"): are the cards causally necessary for
chaining, or do they only appear beside it?

Five models that chain hold all four necessary cards (thorp/card_check.py), but that is co-occurrence.
The test, the one induction heads were proved by: in a model that chains, silence a card's heads and
measure what chaining loses, against silencing as many random heads that belong to no card.

- **The card's heads**: the K strongest heads for each card (previous-word, the Nevermore, the mover,
  the comparator), from the readings the census uses (thorp/evaluators/cards.py), on the model itself.
- **Silencing**: the heads' outputs zeroed on every forward pass (thorp/inside.Inside.silenced). The
  baseline runs through the same explicit attention with nothing silenced, so the only difference
  between a condition and the baseline is the silenced heads.
- **Measured**: the logic deck (chaining gain overall and on cause and effect) and the four public
  chaining tests (their mean lift).
- **Controls**: CONTROLS draws of K random heads from outside every card's set.

**The rule (pre-registered):** a card is **necessary** in a model when silencing it lowers the cause
gain (or, for the comparator, the order gain) by more than twice the largest drop any random draw
causes, and by at least 0.1; **not shown** otherwise. Results: s4.outside_readings, knockout-<model>.

    uv run --group compare python -m thorp.knockout mlx-community/Qwen3-4B-4bit
"""

from __future__ import annotations

import sys

import numpy as np

from thorp import paths

K = 8
CONTROLS = 3
SEED = 1859
CARDS = ("previous_word", "nevermore", "mover", "comparator")


def card_heads(inner, tok, deck) -> dict[str, list[tuple[int, int]]]:
    from thorp.evaluators import cards as C

    cc = C.copying_cards(inner, tok)
    mats = {
        "previous_word": cc["previous_word"],
        "nevermore": cc["nevermore"],
        "mover": C.mover(inner, tok, deck),
        "comparator": C.comparator(inner, tok),
    }
    out = {}
    for card, m in mats.items():
        flat = np.argsort(-m, axis=None)[:K]
        out[card] = [tuple(int(x) for x in np.unravel_index(i, m.shape)) for i in flat]
    return out


def _as_layers(heads: list[tuple[int, int]]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for layer, head in heads:
        out.setdefault(layer, []).append(head)
    return out


def measure(inner, tok, deck, pairs) -> dict:
    from thorp import leaderboard
    from thorp.evaluators.discovery import score_pairs
    from thorp.evaluators.logic import score_deck

    d = score_deck(inner, tok, deck)["metrics"]
    lifts = [score_pairs(inner, tok, pairs[k])["lift"] for k in leaderboard.chaining_tests()]
    return {
        "logic_gain": d["gain"],
        "cause_gain": d.get("gain_cause"),
        "order_gain": d.get("gain_order"),
        "chaining_lift": float(np.mean(lifts)),
    }


def run(model_name: str) -> dict:

    from thorp import fleet, leaderboard
    from thorp.evaluators.discovery import load_pairs
    from thorp.evaluators.logic import load_deck
    from thorp.inside import Inside

    sys.path.insert(0, str(paths.resolve("scripts")))
    from grade_chains import _external

    model, tok = _external(model_name)
    inner = Inside(model)
    deck = load_deck()
    pairs = {k: load_pairs(fleet.TRICKS[k].pairs) for k in leaderboard.chaining_tests()}
    heads = card_heads(inner, tok, deck)
    n_layers = len(inner.layers)
    n_heads = None
    probe = inner.attention_patterns(
        __import__("mlx.core", fromlist=["array"]).array([[tok.eos_id] + tok.encode("A test.")])
    )
    n_heads = probe[0].shape[1]
    taken = {h for hs in heads.values() for h in hs}
    rng = np.random.default_rng(SEED)
    pool = [
        (layer, h) for layer in range(n_layers) for h in range(n_heads) if (layer, h) not in taken
    ]

    results = {
        "model": model_name,
        "k": K,
        "layers": n_layers,
        "heads": n_heads,
        "card_heads": heads,
    }
    with inner.silenced({}):
        results["baseline"] = measure(inner, tok, deck, pairs)
    print("baseline", results["baseline"], flush=True)
    for card in CARDS:
        with inner.silenced(_as_layers(heads[card])):
            results[card] = measure(inner, tok, deck, pairs)
        print(card, results[card], flush=True)
    results["controls"] = []
    for i in range(CONTROLS):
        pick = [pool[j] for j in rng.choice(len(pool), K, replace=False)]
        with inner.silenced(_as_layers(pick)):
            r = measure(inner, tok, deck, pairs)
        results["controls"].append({"heads": pick, **r})
        print("control", i, r, flush=True)

    base = results["baseline"]
    verdict = {}
    for card in CARDS:
        key = "order_gain" if card == "comparator" else "cause_gain"
        drop = base[key] - results[card][key]
        noise = max(base[key] - c[key] for c in results["controls"])
        verdict[card] = {
            "measure": key,
            "drop": round(drop, 4),
            "largest_random_drop": round(noise, 4),
            "chaining_lift_drop": round(base["chaining_lift"] - results[card]["chaining_lift"], 4),
            "necessary": drop >= 0.1 and drop > 2 * max(noise, 0.0),
        }
    results["verdict"] = verdict
    from thorp.viable.s4_intelligence import readings

    readings.put(f"knockout-{model_name.replace('/', '__')}", results)
    return results


if __name__ == "__main__":
    r = run(sys.argv[1])
    for card, v in r["verdict"].items():
        print(
            f"{card:13} {v['measure']} drop {v['drop']:+.3f} (largest random {v['largest_random_drop']:+.3f}): {'NECESSARY' if v['necessary'] else 'not shown'}"
        )

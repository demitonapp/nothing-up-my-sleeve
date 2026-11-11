"""The causal test of the chaining indicators (9 November, Justin: "talk me the causal test? Can we run that and then
compare these 5 that go up and 5 go down to weight which actually has the higher contributor to chaining".)

The probe (`thorp.chain_probe`) found the heads whose attention *rises with* the chaining lift, and the heads whose
attention rises as it fails. Correlation is not cause: a head may report the answer rather than produce it. This is the
test that separates them, the one induction heads were proved by — **silence the head and see whether the model
still chains**:

- the baseline is the model read with nothing silenced, through the same explicit attention, so a condition differs
  from it by exactly the silenced head;
- each condition silences **one head** and re-reads all 96 chaining pairs (nature, mill, between, pigeonhole) and the
  40-item deck;
- a **promoter** is causal if silencing it *lowers* the chaining lift; a **suppressor** is causal if silencing it
  *raises* it;
- **random heads** (one at a time, never one of the ten) are the control band: a drop only counts if it beats the
  largest random draw of the same size.

The causal weight is the drop against that band: `weight = (baseline - silenced) / (largest random drop)`, so a value
above 1 means the head matters more than any random head of its size.

    uv run --project backend --group compare python -m thorp.head_causal mlx-community/Qwen3-4B-4bit
"""

from __future__ import annotations

import sys

import numpy as np

# the five whose attention rises with chaining, and the five whose attention rises as it fails (chain_probe, 08:25)
UP = [(15, 17), (21, 12), (19, 9), (15, 7), (3, 2)]
DOWN = [(8, 30), (1, 1), (0, 2), (18, 27), (9, 16)]
CONTROLS = 10
SEED = 1859


def run(name: str, log=print) -> dict:
    from thorp import fleet, leaderboard
    from thorp.evaluators.discovery import load_pairs
    from thorp.evaluators.logic import load_deck
    from thorp.inside import Inside
    from thorp.knockout import _as_layers, measure

    sys.path.insert(0, str(__import__("thorp").paths.resolve("scripts")))
    from grade_chains import _external

    model, tok = _external(name)
    inner = Inside(model)
    deck = load_deck()
    pairs = {k: load_pairs(fleet.TRICKS[k].pairs) for k in leaderboard.chaining_tests()}

    with inner.silenced({}):
        base = measure(inner, tok, deck, pairs)
    log(f"baseline: chaining {base['chaining_lift']:+.3f}, deck gain {base['logic_gain']:+.3f}")

    taken = set(UP) | set(DOWN)
    # UP and DOWN are Qwen3 4B's heads (chain_probe, 08:25): on a model without them they name nothing
    missing = sorted(taken - set(inner.head_pool()))
    if missing:
        raise ValueError(f"{name} has no attention heads {missing}: UP and DOWN are Qwen3 4B's (36 x 32)")
    rng = np.random.default_rng(SEED)
    # the shape is read from the model: attention layers only, each with its real head count (on Qwen3 4B
    # the same pool and the same draws as the 36 x 32 it hard-coded before 11 November)
    randoms = inner.random_heads(CONTROLS, rng=rng, exclude=taken)

    out: dict = {"model": name, "baseline": base, "conditions": {}}
    for label, head in [("up", h) for h in UP] + [("down", h) for h in DOWN] + [("random", h) for h in randoms]:
        with inner.silenced(_as_layers([head])):
            got = measure(inner, tok, deck, pairs)
        out["conditions"][f"{label}:L{head[0]}H{head[1]}"] = {
            "chaining_lift": got["chaining_lift"],
            "logic_gain": got["logic_gain"],
            "drop": base["chaining_lift"] - got["chaining_lift"],
        }
        log(f"  {label:<6} L{head[0]:>2}H{head[1]:<2} chaining {got['chaining_lift']:+.3f} "
            f"(drop {base['chaining_lift'] - got['chaining_lift']:+.3f})")  # fmt: skip

    rand_drops = [c["drop"] for k, c in out["conditions"].items() if k.startswith("random")]
    band = max(rand_drops) if rand_drops else 0.0
    out["random_band"] = band
    for k, c in out["conditions"].items():
        c["weight"] = c["drop"] / band if band else 0.0
    from thorp.viable.s4_intelligence import readings

    readings.put(f"head-causal-{name}", out)
    return out


def main(argv: list[str]) -> int:
    name = argv[0] if argv else "mlx-community/Qwen3-4B-4bit"
    out = run(name)
    print(f"\nrandom band (largest single-head draw): {out['random_band']:+.3f}")
    print("\nwhat raises chaining (silencing a suppressor should lift it):")
    for k, c in sorted(out["conditions"].items(), key=lambda kv: -kv[1]["drop"]):
        if k.startswith(("down:", "up:")):
            print(f"  {k:<16} drop {c['drop']:+.3f}  weight {c['weight']:+.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

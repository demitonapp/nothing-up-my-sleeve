"""Smoking Qwen (2026-11-07, Justin): can Nothing up my sleeve chain two facts at an order of magnitude below Qwen3 4B?

The claim to prove: a Nothing up my sleeve of about 400M parameters (a tenth of Qwen3 4B's 4.0B) matches Qwen3 4B's
**chaining lift** (the mean lift on the four 50m rungs, two facts chained; thorp/leaderboard.py). The
Mac cannot train 400M, so the proof is a forecast: fit chaining lift against size on Nothing up my sleeve's own
classes (the best ship of each, keel to 50m), extrapolate to 400M, and give the probability that it
reaches Qwen3 4B's mark.

- **The fits.** x = log10(parameters, counted from the built model), y = chaining lift. Two curves:
  `linear` (y = a + b x) and `bending` (y = a + b x + c x^2, from three points), because the backtest
  below shows chaining lift bends upward with size, so the straight line is the conservative one.
- **The uncertainty.** A bootstrap (BOOT draws): within each point, the 96 chaining pairs are resampled
  (and, for a Nothing up my sleeve class, its seeds), the curve refitted, and 400M predicted. P(smoke) is the share
  of draws at or above Qwen3 4B's chaining lift; the 5th to 95th percentile is the band.
- **The backtest.** The same method where the answer is known: Pythia fitted on 14m to 160m predicts
  410m; Qwen3 fitted on 0.6B and 1.7B predicts 4B. A method that misses these is not trusted on Nothing up my sleeve.
- **The range** (fleet.COMPETITORS: Qwen3 4B, Phi-2, Phi-4-mini, Llama 3.2 3B, Gemma 2 2B, Gemma 3 4B,
  SmolLM3 3B): each competitor matched at a tenth of its own size; P(range) is the smallest of their
  probabilities, so the range is smoked only when every one of them is.
- **Forecastable** only when at least three Nothing up my sleeve classes have a chaining lift above the noise (0.03):
  a line through points that are all noise extrapolates nothing.

    uv run python -m thorp.smoking_qwen
"""

from __future__ import annotations

import json
import math

import numpy as np

from thorp import fleet, leaderboard

TARGET_MODEL = "mlx-community/Qwen3-4B-4bit"
TARGET_PARAMS = 4.0e9
SMOKE_PARAMS = TARGET_PARAMS / 10  # an order of magnitude below
BOOT = 1000
NOISE = leaderboard.CHAINING_NOISE

# the reference ladder's sizes (total parameters, as published)
REFERENCE_PARAMS = {
    "EleutherAI/pythia-14m": 14e6,
    "EleutherAI/pythia-31m": 31e6,
    "EleutherAI/pythia-70m": 70e6,
    "EleutherAI/pythia-160m": 160e6,
    "EleutherAI/pythia-410m": 410e6,
    "Qwen/Qwen3-0.6B": 0.6e9,
    "mlx-community/Qwen3-1.7B-4bit": 1.7e9,
    "mlx-community/Qwen3-4B-4bit": 4.0e9,
    **{m: n for m, (_, n) in fleet.COMPETITORS.items()},
}


def chaining_rungs() -> list[str]:
    return [
        next(k for k in c if fleet.TRICKS[k].goal_class == leaderboard.CHAINING)
        for c in fleet.chains()
    ]


def _params(spec: dict) -> int:
    from mlx.utils import tree_flatten

    from thorp.models import registry

    m = registry.build(
        spec["model"]["family"],
        spec["model"]["preset"],
        spec["tokeniser"]["vocab"],
        spec["model"]["context"],
    )
    return int(sum(v.size for _, v in tree_flatten(m.parameters())))


def _reference_points() -> dict[str, dict]:
    from thorp.viable.s4_intelligence import readings

    models = readings.chain_grades()
    if not models:
        return {}
    out = {}
    for name, n in REFERENCE_PARAMS.items():
        if name in models:
            out[name] = {
                "params": n,
                "seeds": [[models[name][k]["pairs"] for k in chaining_rungs()]],
            }
    return out


def _pairs_of(run_id: str) -> list[list[float]] | None:
    from thorp.ledger import reader

    text = reader().latest_artifact_text(run_id, "discovery")
    if text is None:
        return None
    rec = json.loads(text)
    if not all(k in rec for k in chaining_rungs()):
        return None
    return [rec[k]["pairs"] for k in chaining_rungs()]


def _thorp_points() -> dict[str, dict]:
    """Each class's best ship (by the leaderboard), all of its sailings as seeds."""
    from thorp.ledger import reader

    board = leaderboard.payload()["board"]
    rec = reader()
    out = {}
    for row in board:
        b = row["best"]
        if not b:
            continue
        sails = rec.runs_by_ship(b["ship"])
        if not sails:
            one = rec.get_run(b["run_id"])
            sails = [one] if one else []
        seeds = [s for r in sails if (s := _pairs_of(r["run_id"]))]
        if seeds:
            out[row["class"]] = {
                "params": _params(json.loads(sails[0]["spec_json"])),
                "seeds": seeds,
                "run": b["run"],
            }
    return out


def _value(seeds: list[list[list[float]]]) -> float:
    return float(np.mean([np.mean([np.mean(t) for t in s]) for s in seeds]))


def _draw(seeds: list[list[list[float]]], rng) -> float:
    picked = [seeds[i] for i in rng.integers(0, len(seeds), len(seeds))]
    vals = []
    for s in picked:
        vals.append(np.mean([np.mean(np.asarray(t)[rng.integers(0, len(t), len(t))]) for t in s]))
    return float(np.mean(vals))


def _fit(xs, ys, kind: str):
    deg = 1 if kind == "linear" or len(xs) < 3 else 2
    return np.polyfit(xs, ys, deg)


def forecast(
    points: dict[str, dict],
    at: float,
    target: float | None,
    kinds=("linear", "bending"),
    seed: int = 0,
) -> dict:
    names = sorted(points, key=lambda k: points[k]["params"])
    xs = [math.log10(points[k]["params"]) for k in names]
    ys = [_value(points[k]["seeds"]) for k in names]
    rng = np.random.default_rng(seed)
    out = {
        "points": [
            {"name": n, "params": points[n]["params"], "chaining_lift": round(y, 4)}
            for n, y in zip(names, ys, strict=True)
        ]
    }
    for kind in kinds:
        if kind == "bending" and len(xs) < 3:
            continue
        coef = _fit(xs, ys, kind)
        draws = []
        for _ in range(BOOT):
            yb = [_draw(points[k]["seeds"], rng) for k in names]
            draws.append(float(np.polyval(_fit(xs, yb, kind), math.log10(at))))
        draws = np.asarray(draws)
        out[kind] = {
            "predicted": round(float(np.polyval(coef, math.log10(at))), 4),
            "band": [
                round(float(np.percentile(draws, 5)), 4),
                round(float(np.percentile(draws, 95)), 4),
            ],
            "p_at_or_above_target": None
            if target is None
            else round(float(np.mean(draws >= target)), 3),
        }
    return out


def backtest(ref: dict[str, dict]) -> list[dict]:
    tests = [
        (
            "Pythia: fit 14m-160m, predict 410m",
            [f"EleutherAI/pythia-{s}" for s in ("14m", "31m", "70m", "160m")],
            "EleutherAI/pythia-410m",
        ),
        (
            "Qwen3: fit 0.6B-1.7B, predict 4B",
            ["Qwen/Qwen3-0.6B", "mlx-community/Qwen3-1.7B-4bit"],
            TARGET_MODEL,
        ),
    ]
    out = []
    for label, fit_on, held in tests:
        if not all(k in ref for k in fit_on + [held]):
            continue
        f = forecast({k: ref[k] for k in fit_on}, ref[held]["params"], None)
        actual = _value(ref[held]["seeds"])
        row = {"test": label, "actual": round(actual, 4)}
        for kind in ("linear", "bending"):
            if kind in f:
                row[kind] = {
                    **f[kind],
                    "inside_band": f[kind]["band"][0] <= actual <= f[kind]["band"][1],
                }
        out.append(row)
    return out


def payload() -> dict:
    ref = _reference_points()
    target = _value(ref[TARGET_MODEL]["seeds"]) if TARGET_MODEL in ref else None
    thorp = _thorp_points()
    above = [k for k, p in thorp.items() if _value(p["seeds"]) > NOISE]
    out = {
        "target": {
            "model": TARGET_MODEL,
            "params": TARGET_PARAMS,
            "chaining_lift": None if target is None else round(target, 4),
        },
        "smoke_at": SMOKE_PARAMS,
        "classes_above_noise": above,
        "forecastable": len(above) >= 3,
        "backtest": backtest(ref),
    }
    if thorp:
        out["thorp"] = forecast({k: thorp[k] for k in thorp}, SMOKE_PARAMS, target)
        for p in out["thorp"]["points"]:
            p["run"] = thorp[p["name"]].get("run")
        if not out["forecastable"]:  # a curve through noise: shown, but no probability is claimed
            for kind in ("linear", "bending"):
                if kind in out["thorp"]:
                    out["thorp"][kind]["p_at_or_above_target"] = None
    # the perch (Justin: "smoking that size range and not only Qwen"): every competitor of 2B to 4B,
    # each matched at a tenth of its own size; the range is smoked when every one of them is
    out["range"] = []
    for model, (label, n) in fleet.COMPETITORS.items():
        if model not in ref:
            out["range"].append({"model": model, "label": label, "params": n, "scored": False})
            continue
        lift_c = _value(ref[model]["seeds"])
        row = {
            "model": model,
            "label": label,
            "params": n,
            "smoke_at": n / 10,
            "chaining_lift": round(lift_c, 4),
            "scored": True,
        }
        if thorp:
            f = forecast({k: thorp[k] for k in thorp}, n / 10, lift_c)
            for kind in ("linear", "bending"):
                if kind in f:
                    row[kind] = {**f[kind]}
                    if not out["forecastable"]:
                        row[kind]["p_at_or_above_target"] = None
        out["range"].append(row)
    scored = [r for r in out["range"] if r.get("scored")]
    out["hardest"] = (
        max(scored, key=lambda r: r["chaining_lift"])["label"] if scored else None
    )  # the highest bar
    for kind in ("linear", "bending"):
        ps = [r[kind]["p_at_or_above_target"] for r in scored if kind in r]
        out[f"p_range_{kind}"] = min(ps) if ps and all(p is not None for p in ps) else None
    return out


def main() -> None:
    p = payload()
    print(
        f"Target: {p['target']['model']} chaining lift {p['target']['chaining_lift']:+.3f}; smoke at {p['smoke_at'] / 1e6:.0f}M"
    )
    print("\nBacktest:")
    for b in p["backtest"]:
        print(f"  {b['test']}: actual {b['actual']:+.3f}", end="")
        for k in ("linear", "bending"):
            if k in b:
                print(
                    f" | {k} {b[k]['predicted']:+.3f} [{b[k]['band'][0]:+.3f}, {b[k]['band'][1]:+.3f}] {'inside' if b[k]['inside_band'] else 'MISSED'}",
                    end="",
                )
        print()
    if "thorp" in p:
        print("\nNothing up my sleeve points:")
        for pt in p["thorp"]["points"]:
            print(
                f"  {pt['name']:9} {pt['params'] / 1e6:7.2f}M  chaining lift {pt['chaining_lift']:+.4f}  ({pt['run']})"
            )
        for k in ("linear", "bending"):
            if k in p["thorp"]:
                t = p["thorp"][k]
                print(
                    f"  {k}: at 400M {t['predicted']:+.3f} [{t['band'][0]:+.3f}, {t['band'][1]:+.3f}], P(smoke) {t['p_at_or_above_target']}"
                )
    print("\nThe range, each matched at a tenth of its size:")
    for r in p["range"]:
        if not r.get("scored"):
            print(f"  {r['label']:14} not scored yet")
            continue
        lin = r.get("linear", {})
        print(
            f"  {r['label']:14} {r['params'] / 1e9:.1f}B chaining {r['chaining_lift']:+.3f}; "
            f"Nothing up my sleeve at {r['smoke_at'] / 1e6:.0f}M (linear) {lin.get('predicted', float('nan')):+.3f}, "
            f"P {lin.get('p_at_or_above_target')}"
        )
    print(
        f"\nForecastable: {p['forecastable']} (classes above noise: {p['classes_above_noise'] or 'none'})"
    )


if __name__ == "__main__":
    main()

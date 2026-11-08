"""The logic deck read on outside models, with each relation's gain and a bootstrap band over its items (Justin,
2026-11-08 12:15: "can you read a model higher than qwen 4b to see where the scales starts settling down"). Writes
data/compare/logic-<model>.json; takes S2's helm.

    uv run --project backend --group compare python backend/scripts/read_logic.py mlx-community/Qwen3.8-27B-4bit
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))

from grade_chains import _external  # noqa: E402

from thorp import paths, vsm  # noqa: E402
from thorp.evaluators.logic import CROWNS, CROWNS_KEY, crowns_readings, load_deck, score_deck  # noqa: E402

RELATIONS = ("order", "cause", "membership", "proportion", "counterfactual")
CROWN_KINDS = ("crowns-side", "crowns-time", "crowns-place", "crowns-station")  # the crowns deck (2026-11-08), read beside the logic decks


def gain(items: dict, rel: str, idx=None) -> float:
    ks = sorted(k for k in items if k.startswith(rel + "-"))
    if idx is not None:
        ks = [ks[i] for i in idx]
    both = np.mean([items[k]["both"] for k in ks])
    return float(both - max(np.mean([items[k]["first"] for k in ks]), np.mean([items[k]["second"] for k in ks])))


def main(names: list[str]) -> None:
    rng = np.random.default_rng(0)
    for name in names:
        with vsm.at_sea(f"read the logic deck on {name}", kind="score"):
            t0 = time.time()
            model, tok = _external(name)
            r = score_deck(model, tok, load_deck())
            r40 = score_deck(model, tok, load_deck("lists/tricks/logic-40.csv"))
            crowns = load_deck(CROWNS)
            rc = score_deck(model, tok, crowns) if crowns else None
        it = r["items"]
        out = {"model": name, "read": time.strftime("%Y-%m-%dT%H:%M:%S"), "seconds": round(time.time() - t0), "logic": {k: v for k, v in r.items() if k != "items"}, "items": it, "gains": {}}
        for rel in RELATIONS:
            n = len([k for k in it if k.startswith(rel + "-")])
            if not n:
                continue
            boots = [gain(it, rel, rng.integers(0, n, n)) for _ in range(2000)]
            lo, hi = np.percentile(boots, [5, 95])
            out["gains"][rel] = {"gain": gain(it, rel), "lo": float(lo), "hi": float(hi), "items": n}
        it40 = r40["items"]
        out["gains40"] = {}
        for rel in RELATIONS:
            n = len([k for k in it40 if k.startswith(rel + "-")])
            if n:
                boots = [gain(it40, rel, rng.integers(0, n, n)) for _ in range(2000)]
                lo, hi = np.percentile(boots, [5, 95])
                out["gains40"][rel] = {"gain": gain(it40, rel), "lo": float(lo), "hi": float(hi), "items": n}
        out["logic40"] = {k: v for k, v in r40.items() if k != "items"}
        out["items40"] = it40
        if rc:  # the crowns: the gain per kind of standpoint with its band, and the deck's two readings, moves and ask
            itc = rc["items"]
            m = rc["metrics"]
            extra = crowns_readings({f"tricks/{CROWNS_KEY}/{k}": v for k, v in m.items()})
            out["crowns"] = {**m, **{k.rsplit("/", 1)[-1]: v for k, v in extra.items()}}
            out["items_crowns"] = itc
            out["gains_crowns"] = {}
            for rel in CROWN_KINDS:
                n = len([k for k in itc if k.startswith(rel + "-")])
                if n:
                    boots = [gain(itc, rel, rng.integers(0, n, n)) for _ in range(2000)]
                    lo, hi = np.percentile(boots, [5, 95])
                    out["gains_crowns"][rel] = {"gain": gain(itc, rel), "lo": float(lo), "hi": float(hi), "items": n}
        p = paths.data_dir() / "compare" / f"logic-{name.replace('/', '--')}.json"
        p.write_text(json.dumps(out, indent=1))
        print(name, {k: round(v["gain"], 3) for k, v in out["gains"].items()}, f"{out['seconds']}s", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])

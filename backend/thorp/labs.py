"""The labs: who made each outside model, and what each lab's models do best and worst on Thorp's tests.

A **lab** (`Lab`) is the maker of a family of outside models (EleutherAI makes Pythia, Alibaba Qwen,
and so on), matched by the model's family name, since many checkpoints are re-hosted under
`mlx-community/` and the repo owner does not say who made them.

A lab's **best and worst** are its models' readings on every rung of the four chains
(data/compare/chain-grades.json), each set against the field: the other labs' models on the same test.
A reading's **standing** is its lift less the field's median, over the field's spread (its standard
deviation), so a test where every model scores 2.0 does not crowd out a test where the field scores
0.1; the five highest standings are the lab's best, the five lowest its worst.

    uv run python -m thorp.labs eleutherai     # one lab's best and worst, in plain text
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from dataclasses import dataclass

from thorp import fleet, paths


@dataclass(frozen=True)
class Lab:
    key: str  # the address: #/leaderboard/lab/<key>
    name: str
    families: tuple[str, ...]  # the model families it makes, as they appear in model names
    url: str = ""

    def makes(self, model: str) -> bool:
        return any(re.search(f, model, re.I) for f in self.families)


LABS: tuple[Lab, ...] = (
    Lab("alibaba", "Alibaba", ("qwen",), "https://huggingface.co/Qwen"),
    Lab("meta", "Meta", ("llama",), "https://huggingface.co/meta-llama"),
    Lab("microsoft", "Microsoft", ("phi",), "https://huggingface.co/microsoft"),
    Lab("eleutherai", "EleutherAI", ("pythia",), "https://huggingface.co/EleutherAI"),
    Lab("google", "Google", ("gemma",), "https://huggingface.co/google"),
    Lab("huggingface", "Hugging Face", ("smollm",), "https://huggingface.co/HuggingFaceTB"),
)
TOP = 5


def lab_of(model: str) -> Lab | None:
    return next((lab for lab in LABS if lab.makes(model)), None)


def get(key: str) -> Lab | None:
    return next((lab for lab in LABS if lab.key == key.lower()), None)


def _grades() -> dict:
    p = paths.data_dir() / "compare" / "chain-grades.json"
    try:
        return json.loads(p.read_text()).get("models", {})
    except (OSError, ValueError):
        return {}


def _label(model: str) -> str:
    return fleet.COMPETITORS.get(model, (model.split("/")[-1], 0))[0]


def readings(models: dict | None = None) -> list[dict]:
    """Every (model, test) reading of a lab's model on a rung of the four chains."""
    models = _grades() if models is None else models
    names = {k: t.name for k, t in fleet.TRICKS.items()}
    rungs = [r.title for r in getattr(fleet, "RUNGS", ())]
    where = {}  # test -> (its chain's name, its rung's title)
    for c in fleet.chains():
        for i, k in enumerate(c):
            where[k] = (names.get(c[-1], c[-1]), rungs[i] if i < len(rungs) else None)
    out = []
    for model, v in models.items():
        lab = lab_of(model)
        if not lab:
            continue
        for test, x in v.items():
            if test not in where or not isinstance(x, dict) or x.get("lift") is None:
                continue
            out.append(
                {
                    "lab": lab.key,
                    "model": model,
                    "label": _label(model),
                    "test": test,
                    "name": names.get(test, test),
                    "chain": where[test][0],
                    "rung": where[test][1],
                    "lift": x["lift"],
                    "score": x.get("score"),
                    "performed": bool(x.get("performed")),
                }
            )
    return out


def standings(lab: Lab, rows: list[dict] | None = None) -> list[dict]:
    """The lab's readings, each with its standing against the other labs' models on the same test."""
    rows = readings() if rows is None else rows
    field: dict[str, list[float]] = {}
    for r in rows:
        if r["lab"] != lab.key:
            field.setdefault(r["test"], []).append(r["lift"])
    out = []
    for r in rows:
        f = field.get(r["test"], [])
        if r["lab"] != lab.key or len(f) < 2:
            continue
        med, sd = statistics.median(f), statistics.pstdev(f)
        out.append(
            {
                **r,
                "field_median": med,
                "field_n": len(f),
                "beats": sum(x < r["lift"] for x in f),
                "standing": (r["lift"] - med) / sd if sd > 0 else 0.0,
            }
        )
    return sorted(out, key=lambda r: -r["standing"])


def payload(key: str) -> dict:
    lab = get(key)
    if not lab:
        raise LookupError(f"no lab {key}")
    models = _grades()
    s = standings(lab, readings(models))
    mine = [m for m in models if lab.makes(m)]
    try:  # the reference ladder's sizes (the competitors carry theirs in fleet.COMPETITORS)
        from thorp.smoking_qwen import REFERENCE_PARAMS as sizes
    except ImportError:
        sizes = {}
    return {
        "key": lab.key,
        "name": lab.name,
        "url": lab.url,
        "families": list(lab.families),
        "models": [
            {
                "model": m,
                "label": _label(m),
                "params": fleet.COMPETITORS.get(m, (None, None))[1] or sizes.get(m),
                "competitor": m in fleet.COMPETITORS,
                "ladder": m in fleet.REFERENCE_LADDER,
            }
            for m in mine
        ],
        "readings": len(s),
        "best": s[:TOP],
        "worst": s[::-1][:TOP] if len(s) > TOP else [],
        "labs": [{"key": x.key, "name": x.name} for x in LABS],
    }


def main() -> None:
    d = payload(sys.argv[1] if len(sys.argv) > 1 else "eleutherai")
    print(f"{d['name']}: {', '.join(m['label'] for m in d['models'])} ({d['readings']} readings)")
    for title, rows in (("best", d["best"]), ("worst", d["worst"])):
        print(f"\n{title}")
        for r in rows:
            print(
                f"  {r['standing']:+5.2f}σ  {r['label']:<18} {r['name']:<24} lift {r['lift']:+.3f}"
                f" (field {r['field_median']:+.3f})"
            )


if __name__ == "__main__":
    main()

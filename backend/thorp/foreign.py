"""Foreign ships: the outside models Nothing up my sleeve reads, so a harbour can show them and a page can spy on one.

They are not Nothing up my sleeve sizes or ships: no spec, no ledger run, no weights on this Mac. They are readings in
`s4.outside_readings` (a deck, the logic deck, a knockout, a book list) and the chain grades. This module
turns them into a registry and one model's page payload.
"""

from __future__ import annotations

import hashlib

from thorp import fleet
from thorp.viable.s4_intelligence import readings

# models with a reading but no published size in fleet.COMPETITORS / smoking_qwen.REFERENCE_PARAMS
# the houses the foreign ships come from: each house's art shares a visual signature (see
# thorp/dash/art/generate_art.py FOREIGN), so a Qwen looks like a Qwen, a Phi like a Phi, a Gemma like a
# Gemma, and the independent labs share the patched-cream-sail look.
LABS = {
    "alibaba": "Alibaba · Qwen",
    "microsoft": "Microsoft · Phi",
    "google": "Google · Gemma",
    "meta": "Meta · Llama",
    "huggingface": "Hugging Face · SmolLM",
    "eleuther": "EleutherAI · Pythia",
    "maincode": "Maincode · Maincoder",
    "thorp": "Nothing up my sleeve (not a foreign ship)",
    "independent": "independent labs",
}
FLAGS = {
    "alibaba": ("cn", "China"),
    "microsoft": ("sv", "Silicon Valley"),
    "google": ("sv", "Silicon Valley"),
    "meta": ("us", "United States"),
    "huggingface": ("fr", "France"),
    "eleuther": ("independent", "independent labs"),
    "maincode": ("au", "Australia"),
    "thorp": ("thorp", "Nothing up my sleeve"),
    "independent": ("independent", "independent labs"),
}
LAB_OF = {
    "mlx-community/Qwen3.8-27B-4bit": "alibaba",
    "mlx-community/Qwen3-4B-4bit": "alibaba",
    "mlx-community/Qwen3-1.7B-4bit": "alibaba",
    "Qwen/Qwen3-0.6B": "alibaba",
    "mlx-community/Qwen3-0.6B-bf16": "alibaba",
    "mlx-community/Qwen3.5-0.8B-bf16": "alibaba",
    "microsoft/phi-2": "microsoft",
    "mlx-community/Phi-4-mini-instruct-4bit": "microsoft",
    "mlx-community/gemma-3-text-4b-pt-4bit": "google",
    "mlx-community/gemma-2-2b": "google",
    "mlx-community/gemma-3-270m-bf16": "google",
    "mlx-community/Llama-3.2-3B-bf16": "meta",
    "mlx-community/SmolLM3-3B-Base-4bit": "huggingface",
    "HuggingFaceTB/SmolLM2-360M": "huggingface",
    "Maincode/Maincoder-1B": "maincode",
    "fl-pathfinder": "thorp",
    "sl-pathfinder": "thorp",
    "spell-vocab4k-v1": "thorp",
}

EXTRA_PARAMS = {
    "HuggingFaceTB/SmolLM2-360M": 0.36e9,
    "mlx-community/gemma-3-270m-bf16": 0.27e9,
    "mlx-community/Qwen3.8-27B-4bit": 27.0e9,
}


def _params() -> dict[str, float]:
    from thorp import smoking_qwen

    out = {m: n for m, (_, n) in fleet.COMPETITORS.items()}
    out.update({m: n for m, n in smoking_qwen.REFERENCE_PARAMS.items() if m not in out})
    out.update({m: n for m, n in EXTRA_PARAMS.items() if m not in out})
    return out


def _label(model: str) -> str:
    if model in fleet.COMPETITORS:
        return fleet.COMPETITORS[model][0]
    return model.split("/")[-1].replace("-4bit", "").replace("-bf16", "")


def _key(label: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in label.lower()).strip("-").replace("--", "-")


def _read_names() -> dict[str, list[tuple[str, str]]]:
    out: dict[str, list[tuple[str, str]]] = {}
    for name, _ in readings.glob("*"):
        kind, model = readings.kind_of(name)
        if model:
            out.setdefault(model, []).append((kind, name))
    return out


def models() -> list[dict]:
    """Every outside model with a reading or a chain grade, biggest first, for the Market Harbour."""
    names = _read_names()
    graded = readings.chain_grades()
    params = _params()
    out = []
    for model in set(names) | set(graded):
        label = _label(model)
        out.append(
            {
                "key": _key(label),
                "label": label,
                "model": model,
                "params": params.get(model),
                "lab": lab_of(model),
                "lab_name": LABS[lab_of(model)],
                "flag": FLAGS[lab_of(model)][0],
                "flag_name": FLAGS[lab_of(model)][1],
                "harbour": "zayton",
                "read": bool(names.get(model)),
                "chained": model in graded,
            }
        )
    return sorted(out, key=lambda x: (-(x["params"] or 0), x["label"]))


def lab_of(model: str) -> str:
    if model.startswith("EleutherAI/pythia"):
        return "eleuther"
    return LAB_OF.get(model, "independent")


def get(key: str) -> dict | None:
    return next((m for m in models() if m["key"] == key), None)


def _mean_bpb(reading: dict) -> dict | None:
    books = [b for b in reading.get("books") or [] if b.get("language") in (None, "en")]
    if not books:
        return None
    return {
        "books": len(books),
        "bpb": sum(b["bpb"] for b in books) / len(books),
        "set": reading.get("set"),
        "list": reading.get("list"),
    }


def payload(key: str) -> dict | None:
    """One foreign ship's readings, for its spy page."""
    m = get(key)
    if m is None:
        return None
    model = m["model"]
    out = {**m, "logic": None, "logic40": None, "deck": None, "knockout": None,
           "hole_cards": None, "chaining": None}  # fmt: skip
    for kind, name in _read_names().get(model, []):
        r = readings.get(name)
        if not isinstance(r, dict):
            continue
        if kind == "logic":
            out["logic"] = (r.get("logic") or {}).get("metrics")
            out["logic40"] = (r.get("logic40") or {}).get("metrics")
        elif kind == "deck":
            out["deck"] = {
                "played": r.get("played") or [],
                "falls": r.get("falls") or {},
                "metrics": r.get("metrics") or {},
                "read": r.get("read"),
            }
        elif kind == "knockout":
            out["knockout"] = {
                "verdict": r.get("verdict") or {},
                "mover": r.get("mover") or {},
                "layers": r.get("layers"),
            }
        elif kind == "scored" and "__hole-cards-unseen" in name:
            out["hole_cards"] = _mean_bpb(r)
    grades = readings.chain_grades().get(model)
    if grades:
        from thorp import smoking_qwen

        out["chaining"] = {
            k: (round(sum(v["pairs"]) / len(v["pairs"]), 4) if v.get("pairs") else None)
            for k, v in grades.items()
        }
        rungs = [out["chaining"].get(k) for k in smoking_qwen.chaining_rungs()]
        vals = [v for v in rungs if v is not None]
        out["chaining_lift"] = sum(vals) / len(vals) if vals else None
    return out


def fingerprint() -> str:
    return hashlib.sha1(str([m["key"] for m in models()]).encode()).hexdigest()[:12]

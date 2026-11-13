"""Foreign ships: the outside models Nothing up my sleeve reads, so a harbour can show them and a page can spy on one.

They are not Nothing up my sleeve sizes or ships: no spec, no ledger run, no weights on this Mac. They are readings in
`s4.outside_readings` (a deck, the logic deck, a knockout, a book list) and the chain grades. This module
turns them into a registry and one model's page payload.
"""

from __future__ import annotations

import functools
import hashlib
import re
from pathlib import Path

from thorp import fleet, paths
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
    "inclusionai": "InclusionAI · Ling",
    "cohere": "Cohere · Aya",
    "thorp": "Demiton (not a foreign ship)",
    "openai": "OpenAI",
    "independent": "independent labs",
}
FLAGS = {
    "alibaba": ("cn", "China"),
    "microsoft": ("sv", "Silicon Valley"),
    "google": ("sv", "Silicon Valley"),
    "meta": ("us", "United States"),
    # Hugging Face belongs to no one country: its ships fly Masaq' Hub's flag (13 November)
    "huggingface": ("hub", "Masaq' Hub"),
    "eleuther": ("independent", "independent labs"),
    "maincode": ("au", "Australia"),
    "inclusionai": ("cn", "China"),
    "cohere": ("ca", "Canada"),
    "thorp": ("demiton", "Demiton"),
    "openai": ("us", "United States"),
    "independent": ("independent", "independent labs"),
}
LAB_OF = {
    "mlx-community/Qwen3.8-27B-4bit": "alibaba",
    "mlx-community/Qwen3-4B-4bit": "alibaba",
    "mlx-community/Qwen3-1.7B-4bit": "alibaba",
    "Qwen/Qwen3-0.6B": "alibaba",
    "mlx-community/Qwen3-0.6B-bf16": "alibaba",
    "mlx-community/Qwen3.5-0.8B-bf16": "alibaba",
    "mlx-community/Qwen3-30B-A3B-4bit": "alibaba",
    "mlx-community/gemma-4-26b-a4b-it-4bit": "google",
    "mlx-community/gemma-4-31b-it-4bit": "google",
    "mlx-community/gpt-oss-20b-MXFP4-Q4": "openai",
    "mlx-community/phi-4-4bit": "microsoft",
    # the xsmall base/instruct twins (11 November): both sides of the tuning comparison
    "mlx-community/Qwen3-0.6B-Base-bf16": "alibaba",
    "Qwen/Qwen3.5-0.8B-Base": "alibaba",
    "mlx-community/gemma-3-270m-it-bf16": "google",
    "mlx-community/SmolLM2-360M-Instruct": "huggingface",
    "mlx-community/SmolLM3-3B-4bit": "huggingface",
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

# A model converted on this Mac (12 November): the published Ling 3.0 Tiny MLX builds carry a converter
# layout mlx-lm cannot read, so its router was dequantized into the plain gate weight BailingGate wants and
# the result lives in data/models, not in the Hub cache. Loaded by directory, listed by this registry.
LING_LOCAL = str(paths.data_dir() / "models" / "ling-3.0-tiny-oq4e-mlx")
LAB_OF[LING_LOCAL] = "inclusionai"

EXTRA_PARAMS = {
    LING_LOCAL: 7.9e9,
    "HuggingFaceTB/SmolLM2-360M": 0.36e9,
    "mlx-community/gemma-3-270m-bf16": 0.27e9,
    "mlx-community/Qwen3.8-27B-4bit": 27.0e9,
    # the five medium candidates pulled on 11 November: the 4-bit MLX repos are what this Mac loads
    "mlx-community/phi-4-4bit": 14.0e9,
    "mlx-community/gpt-oss-20b-MXFP4-Q4": 21.0e9,
    "mlx-community/gemma-4-26b-a4b-it-4bit": 25.2e9,
    "mlx-community/Qwen3-30B-A3B-4bit": 30.0e9,
    "mlx-community/gemma-4-31b-it-4bit": 31.0e9,
    # the xsmall twins
    "mlx-community/Qwen3-0.6B-Base-bf16": 0.6e9,
    "Qwen/Qwen3-0.6B": 0.6e9,
    "mlx-community/Qwen3-0.6B-bf16": 0.6e9,
    "mlx-community/Qwen3.5-0.8B-bf16": 0.8e9,
    "Qwen/Qwen3.5-0.8B-Base": 0.8e9,
    "mlx-community/gemma-3-270m-it-bf16": 0.27e9,
    "mlx-community/SmolLM2-360M-Instruct": 0.36e9,
    "mlx-community/SmolLM3-3B-4bit": 3.0e9,
}

# The five pulled repos read by their candidate names, not the quantised file names: the label is what the
# harbour and the leaderboard call the model, and its slug is the art key.
EXTRA_LABELS = {
    LING_LOCAL: "Ling 3.0 Tiny",
    "mlx-community/phi-4-4bit": "Phi-4 14B",
    "mlx-community/gpt-oss-20b-MXFP4-Q4": "gpt-oss 20B",
    "mlx-community/gemma-4-26b-a4b-it-4bit": "Gemma 4 26B A4B",
    "mlx-community/Qwen3-30B-A3B-4bit": "Qwen3 30B-A3B",
    "mlx-community/gemma-4-31b-it-4bit": "Gemma 4 31B",
    "mlx-community/Qwen3-0.6B-Base-bf16": "Qwen3-0.6B Base",
    "Qwen/Qwen3.5-0.8B-Base": "Qwen3.5-0.8B Base",
    "mlx-community/gemma-3-270m-it-bf16": "Gemma 3 270M Instruct",
    "mlx-community/SmolLM2-360M-Instruct": "SmolLM2-360M Instruct",
    "mlx-community/SmolLM3-3B-4bit": "SmolLM3 3B Instruct",
}


def _params() -> dict[str, float]:
    from thorp import smoking_qwen
    from thorp.onboard import catalogue

    out = {m: n for m, (_, n) in fleet.COMPETITORS.items()}
    out.update({m: n for m, n in smoking_qwen.REFERENCE_PARAMS.items() if m not in out})
    out.update({m: n for m, n in EXTRA_PARAMS.items() if m not in out})
    # the first run's catalogue: a downloaded instruct model has a size and a label even before it
    # has a reading, so chat can list it (`chat_targets` reads the cache, not the readings).
    out.update({m: n for m, n in catalogue.params().items() if m not in out})
    return out


def _label(model: str) -> str:
    from thorp.onboard import catalogue

    if model in catalogue.labels():
        return catalogue.labels()[model]
    if model in EXTRA_LABELS:
        return EXTRA_LABELS[model]
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
    """Every outside model with a reading or a chain grade, biggest first, for the Market Harbour. Our own
    runs' readings are not foreign ships (the `thorp` lab): Zayton holds outside models only."""
    names = _read_names()
    graded = readings.chain_grades()
    params = _params()
    out = []
    for model in set(names) | set(graded):
        if lab_of(model) == "thorp":
            continue
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
                "harbour": "masaq-reach",
                "read": bool(names.get(model)),
                "chained": model in graded,
            }
        )
    return sorted(out, key=lambda x: (-(x["params"] or 0), x["label"]))


def lab_of(model: str) -> str:
    from thorp.onboard import catalogue

    first = catalogue.get(model)
    if first is not None:
        return str(first["lab"])
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


def _cached(model: str) -> bool:
    """Whether the model's weights are on this disk: a converted model in data/models (loaded by
    directory), or a config in the Hugging Face cache with its weights beside it."""
    local = Path(model)
    if local.is_dir():
        return (local / "config.json").is_file() and any(local.glob("*.safetensors"))
    try:
        from huggingface_hub import try_to_load_from_cache

        return isinstance(try_to_load_from_cache(model, "config.json"), str)
    except Exception:  # noqa: BLE001  no hub, no cache
        return False


# a plain repo name that does not say which side of the tuning line it is on: SmolLM3 publishes the
# instruct model under the plain name and the base one as `-Base`; SmolLM2 is the opposite
TUNING_OVERRIDES = {
    LING_LOCAL: "instruct",
    "mlx-community/SmolLM3-3B-4bit": "instruct",
    "mlx-community/SmolLM3-3B-Base-4bit": "base",
    "HuggingFaceTB/SmolLM2-360M": "base",
}


def tuning(model: str) -> str:
    if model in TUNING_OVERRIDES:
        return TUNING_OVERRIDES[model]
    return _tuning(model)


def _tuning(model: str) -> str:
    """Instruct or base: a chat template alone is not enough — a base Gemma has one and still only
    continues text. The name is the evidence the registry holds."""
    name = model.lower()
    if "-it" in name or "instruct" in name or "-chat" in name:
        return "instruct"
    # a model post-trained for tool calls answers turns as an instruct one does (14 November: Falcon-H1-Tiny-Tool-Calling-90M
    # was read as "unknown" and the chat terminal, which offers only instruct models, left it out)
    if "tool-calling" in name or "function-calling" in name:
        return "instruct"
    if "base" in name or "-pt" in name or "pretrain" in name or "pythia" in name:
        return "base"
    if "qwen" in name or "phi-4" in name:
        return "instruct"
    if any(k in name for k in ("gemma", "llama", "smollm", "phi-2")):
        return "base"
    return "unknown"


def _family(model: str) -> str:
    """One model's family: its name without the checkpoint's tuning and quantisation suffixes, so a
    base and an instruct twin share it. `gemma-3-270m-it-bf16` -> `gemma-3-270m`."""
    name = model.split("/")[-1].lower().replace("_", "-")
    for tok in ("-instruct", "-chat", "-base", "-pt", "-qat", "-mxfp4", "-bf16", "-fp16", "-8bit", "-6bit", "-5bit", "-4bit", "-3bit", "-it"):
        name = name.replace(tok, "")
    return name.strip("-")


def versions(key: str) -> list[dict]:
    """The base/instruct siblings of one foreign ship: every checkpoint of the family the registry
    knows, whether its weights are cached, and whether it has a reading (so it has a page)."""
    m = get(key)
    if m is None:
        return []
    fam = _family(m["model"])
    read = set(_read_names()) | set(readings.chain_grades())
    rows, seen = [], set()
    for model in set(_params()) | read:
        if _family(model) != fam:
            continue
        label = _label(model)
        k = _key(label)
        if k in seen:
            continue
        seen.add(k)
        rows.append(
            {
                "key": k,
                "label": label,
                "model": model,
                "params": _params().get(model),
                "tuning": tuning(model),
                "cached": _cached(model),
                "read": model in read,
                "current": model == m["model"] or k == key,
            }
        )
    rows.sort(key=lambda r: ({"instruct": 0, "base": 1, "unknown": 2}.get(r["tuning"], 2), -(r["params"] or 0)))
    return rows


def known_cached() -> dict[str, str]:
    """Every model the registry knows whose weights are cached, keyed as the harbour keys it: the read
    ships and the pulled-but-unread twins, so a base/instruct pair can be chatted with before either
    has a reading."""
    out: dict[str, str] = {}
    for model in set(_params()) | set(_read_names()) | set(readings.chain_grades()):
        if not _cached(model):
            continue
        out[_key(_label(model))] = model
    return out


def chat_targets() -> list[dict]:
    """The Market Harbour's read ships plus the pulled twins without readings, and the houses' models
    pulled from their Hugging Face page: chat is about the weights, not the readings, so a base and its
    instruct twin are both selectable."""
    out = {m["key"]: m for m in models()}
    for key, model in known_cached().items():
        if key in out:
            continue
        lab = lab_of(model)
        out[key] = {
            "key": key,
            "label": _label(model),
            "model": model,
            "params": _params().get(model),
            "lab": lab,
            "lab_name": LABS[lab],
            "flag": FLAGS[lab][0],
            "flag_name": FLAGS[lab][1],
            "harbour": "masaq-reach",
            "read": False,
            "chained": False,
        }
    # a model downloaded from a lab's Hub table (thorp.lab_downloads): its lab may be one of the newer
    # houses, so the profile in thorp.labs supplies the name and flag when foreign.LABS does not.
    from thorp import lab_downloads

    for row in lab_downloads.downloaded():
        key = row.get("key") or _key(row["model"])
        if key in out or not row.get("model"):
            continue
        lab = str(row.get("lab") or "independent")
        house = None
        try:
            from thorp import labs as houses

            house = houses.get(lab)
        except Exception:  # noqa: BLE001
            house = None
        out[key] = {
            "key": key,
            "label": row.get("label") or _label(row["model"]),
            "model": row["model"],
            "params": row.get("params") or _params().get(row["model"]),
            "lab": lab,
            "lab_name": (house.short or house.name) if house else LABS.get(lab, lab),
            "flag": (house.country if house else FLAGS.get(lab, ("independent", ""))[0]),
            "flag_name": (house.country_name if house else FLAGS.get(lab, ("", "independent labs"))[1]),
            "harbour": "masaq-reach",
            "read": False,
            "chained": False,
        }
    return list(out.values())


def get_any(key: str) -> dict | None:
    """A ship by key, read or merely pulled: the chat can talk to a checkpoint that has no readings."""
    return next((m for m in chat_targets() if m["key"] == key), None)


@functools.lru_cache(maxsize=64)
def control_tokens(model: str) -> list[dict]:
    """The special pieces a model's own tokeniser declares — bos/eos/unk/pad, its additional special
    tokens, and the markers its chat template uses — with the id, whether the token is one piece, and
    whether that id is inside the embedding table (an added token past `vocab_size` has no row until
    the embeddings are resized). Empty when the weights are not cached or the tokeniser will not load."""
    if not _cached(model):
        return []
    try:
        from transformers import AutoTokenizer

        tok = AutoTokenizer.from_pretrained(model)
    except Exception:  # noqa: BLE001  no transformers, no tokeniser
        return []
    roles: dict[str, list[str]] = {}
    for role in ("bos_token", "eos_token", "unk_token", "pad_token"):
        t = getattr(tok, role, None)
        if t:
            roles.setdefault(str(t), []).append(role.replace("_token", ""))
    for t in getattr(tok, "additional_special_tokens", None) or []:
        roles.setdefault(str(t), []).append("additional")
    for t in getattr(tok, "all_special_tokens", None) or []:
        roles.setdefault(str(t), []).append("special")
    template = str(getattr(tok, "chat_template", "") or "")
    for marker in re.findall(r"<\|[^|]{1,40}\|>|<[A-Za-z_][^>]{0,30}>", template):
        roles.setdefault(marker, []).append("template")
    vocab = int(getattr(tok, "vocab_size", 0) or 0)
    out = []
    for token, why in roles.items():
        one, idx = False, None
        try:
            ids = tok.encode(token, add_special_tokens=False)
            one = len(ids) == 1
            idx = int(ids[0]) if one else None
        except Exception:  # noqa: BLE001
            pass
        out.append(
            {
                "token": token,
                "id": idx,
                "single": one,
                "embedding": bool(idx is not None and idx < vocab),
                "roles": why,
            }
        )
    return out


def control_all() -> list[dict]:
    """Every read foreign ship's control tokens, for the comparison table."""
    return [
        {"key": m["key"], "label": m["label"], "model": m["model"], "tokens": control_tokens(m["model"])}
        for m in models()
    ]


def payload(key: str) -> dict | None:
    """One foreign ship's readings, for its spy page."""
    m = get(key)
    if m is None:
        return None
    model = m["model"]
    out = {**m, "logic": None, "logic40": None, "deck": None, "knockout": None,
           "hole_cards": None, "chaining": None, "versions": versions(key),
           "control_tokens": control_tokens(model)}  # fmt: skip
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

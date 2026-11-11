"""The first run's catalogue: Thorp's own classes, and the outside instruct models it can fetch.

Two axes, deliberately kept apart:

- **classes** are Thorp's own models (`300k` ... `350m`): what a Mac sails.
- **bands** are the outside models' sizes (`xsmall` ... `large`): what the dashboard talks to.

The outside list is curated, not a Hugging Face search. Every entry is MLX-ready, instruct-tuned, and
one this harness has either read or expects to read; a repo that is not here cannot be downloaded from
the onboarding page. `foreign.py` merges the same list, so a downloaded model appears in chat without
a second registry.
"""

from __future__ import annotations

import math

from thorp.models import registry

BANDS = [
    {
        "key": "xsmall",
        "name": "Extra small",
        "range": "under 1B",
        "about": "under a billion parameters: the smallest instruct models, and the size of Thorp's own keel",
    },
    {
        "key": "small",
        "name": "Small",
        "range": "1B – 4B",
        "about": "the four-billion line: the size where chaining has been read",
    },
    {
        "key": "medium",
        "name": "Medium",
        "range": "4B – 32B",
        "about": "the middle of the field: above every ship Thorp has built",
    },
    {
        "key": "large",
        "name": "Large",
        "range": "above 32B",
        "about": "the deep end: more than a MacBook's unified memory, and a long download",
    },
]
BAND_KEYS = tuple(b["key"] for b in BANDS)

# Thorp's own classes: the store names and describes them (`s1.sizes`); this is the bootstrap copy the
# first-run page can draw before the store exists. Once the store answers, its rows win.
CLASSES = [
    {
        "preset": "300k",
        "name": "The keel",
        "job": "Spelling, punctuation, the statistical laws of text",
        "where": "mac",
        "recommended": True,
    },
    {
        "preset": "1m",
        "name": "The pilot",
        "job": "A fast outer loop for data questions, and the foundation a 9m grows from",
        "where": "mac",
    },
    {
        "preset": "9m",
        "name": "The speller",
        "job": "The surface of English: words, punctuation, lines and paragraphs",
        "where": "mac",
    },
    {
        "preset": "21m",
        "name": "The stylist",
        "job": "Grammar and style: agreement, sentences, one voice through a passage",
        "where": "mac",
    },
    {
        "preset": "50m",
        "name": "The paragraph",
        "job": "Paragraphs, and the third point of the corpus's own size curve",
        "where": "vast",
    },
    {
        "preset": "100m",
        "name": "The explorer",
        "job": "The Origin and Leonardo tests: does it bet on an idea before the world did?",
        "where": "mac",
    },
    {
        "preset": "350m",
        "name": "The trader",
        "job": "The top of the Origin and Leonardo curves",
        "where": "vast",
    },
]

# repo, label, band, params, approximate download and run sizes (GB), licence, lab, flag. The sizes are
# estimates for the picker; the install page measures the cache, and the exact repo size comes from the
# Hub when it answers. `run_gb` is unified memory, weights plus a little headroom, not a promise.
MODELS = [
    {
        "repo": "mlx-community/Qwen3-0.6B-4bit",
        "label": "Qwen3 0.6B",
        "band": "xsmall",
        "params": 0.6e9,
        "download_gb": 0.4,
        "run_gb": 1.2,
        "license": "Apache-2.0",
        "lab": "alibaba",
        "flag": "cn",
        "recommended": True,
        "note": "the smallest useful chat model; a quick first answer",
    },
    {
        "repo": "mlx-community/Qwen3.5-0.8B-bf16",
        "label": "Qwen3.5 0.8B",
        "band": "xsmall",
        "params": 0.8e9,
        "download_gb": 1.6,
        "run_gb": 2.6,
        "license": "Apache-2.0",
        "lab": "alibaba",
        "flag": "cn",
        "note": "a newer small Qwen, in bf16",
    },
    {
        "repo": "mlx-community/gemma-3-270m-it-bf16",
        "label": "Gemma 3 270M Instruct",
        "band": "xsmall",
        "params": 0.27e9,
        "download_gb": 0.9,
        "run_gb": 1.4,
        "license": "Gemma Terms of Use",
        "lab": "google",
        "flag": "sv",
        "note": "the smallest instruct model here; good for a first download",
    },
    {
        "repo": "mlx-community/SmolLM2-360M-Instruct",
        "label": "SmolLM2 360M Instruct",
        "band": "xsmall",
        "params": 0.36e9,
        "download_gb": 0.8,
        "run_gb": 1.4,
        "license": "Apache-2.0",
        "lab": "huggingface",
        "flag": "fr",
        "note": "a compact instruct model from Hugging Face",
    },
    {
        "repo": "mlx-community/Qwen3-1.7B-4bit",
        "label": "Qwen3 1.7B",
        "band": "small",
        "params": 1.7e9,
        "download_gb": 1.1,
        "run_gb": 2.6,
        "license": "Apache-2.0",
        "lab": "alibaba",
        "flag": "cn",
        "recommended": True,
        "note": "the smallest of the chaining-size models",
    },
    {
        "repo": "mlx-community/Phi-4-mini-instruct-4bit",
        "label": "Phi-4-mini 3.8B Instruct",
        "band": "small",
        "params": 3.8e9,
        "download_gb": 2.5,
        "run_gb": 4.5,
        "license": "MIT",
        "lab": "microsoft",
        "flag": "sv",
        "note": "a strong small instruct model",
    },
    {
        "repo": "mlx-community/Llama-3.2-3B-Instruct-4bit",
        "label": "Llama 3.2 3B Instruct",
        "band": "small",
        "params": 3.2e9,
        "download_gb": 1.9,
        "run_gb": 3.5,
        "license": "Llama 3.2 Community License",
        "lab": "meta",
        "flag": "us",
        "note": "Meta's 3B instruct model",
    },
    {
        "repo": "mlx-community/SmolLM3-3B-4bit",
        "label": "SmolLM3 3B Instruct",
        "band": "small",
        "params": 3.0e9,
        "download_gb": 1.9,
        "run_gb": 3.5,
        "license": "Apache-2.0",
        "lab": "huggingface",
        "flag": "fr",
        "note": "an open small instruct model with a chat template",
    },
    {
        "repo": "mlx-community/Qwen3-4B-4bit",
        "label": "Qwen3 4B",
        "band": "medium",
        "params": 4.0e9,
        "download_gb": 2.5,
        "run_gb": 4.5,
        "license": "Apache-2.0",
        "lab": "alibaba",
        "flag": "cn",
        "recommended": True,
        "note": "the model the chaining tests are read against",
    },
    {
        "repo": "mlx-community/phi-4-4bit",
        "label": "Phi-4 14B",
        "band": "medium",
        "params": 14.0e9,
        "download_gb": 8.0,
        "run_gb": 12.0,
        "license": "MIT",
        "lab": "microsoft",
        "flag": "sv",
        "note": "a larger Microsoft instruct model",
    },
    {
        "repo": "mlx-community/gpt-oss-20b-MXFP4-Q4",
        "label": "gpt-oss 20B",
        "band": "medium",
        "params": 21.0e9,
        "download_gb": 12.0,
        "run_gb": 18.0,
        "license": "Apache-2.0",
        "lab": "openai",
        "flag": "us",
        "note": "OpenAI's open-weight model, quantised for MLX",
    },
    {
        "repo": "mlx-community/Qwen3-30B-A3B-4bit",
        "label": "Qwen3 30B-A3B",
        "band": "medium",
        "params": 30.0e9,
        "download_gb": 17.0,
        "run_gb": 24.0,
        "license": "Apache-2.0",
        "lab": "alibaba",
        "flag": "cn",
        "note": "a mixture-of-experts model: fast for its size, still a large download",
    },
    {
        "repo": "mlx-community/gemma-4-26b-a4b-it-4bit",
        "label": "Gemma 4 26B A4B",
        "band": "medium",
        "params": 25.2e9,
        "download_gb": 15.0,
        "run_gb": 22.0,
        "license": "Gemma Terms of Use",
        "lab": "google",
        "flag": "sv",
        "note": "a sparse Gemma, instruct-tuned",
    },
    {
        "repo": "mlx-community/gemma-4-31b-it-4bit",
        "label": "Gemma 4 31B",
        "band": "medium",
        "params": 31.0e9,
        "download_gb": 18.0,
        "run_gb": 26.0,
        "license": "Gemma Terms of Use",
        "lab": "google",
        "flag": "sv",
        "note": "the largest Gemma here",
    },
    {
        "repo": "mlx-community/Qwen3.8-27B-4bit",
        "label": "Qwen3.8 27B",
        "band": "medium",
        "params": 27.0e9,
        "download_gb": 15.0,
        "run_gb": 22.0,
        "license": "Apache-2.0",
        "lab": "alibaba",
        "flag": "cn",
        "note": "the 27B read on the logic deck",
    },
    {
        "repo": "mlx-community/Llama-3.3-70B-Instruct-4bit",
        "label": "Llama 3.3 70B Instruct",
        "band": "large",
        "params": 70.0e9,
        "download_gb": 40.0,
        "run_gb": 55.0,
        "license": "Llama 3.3 Community License",
        "lab": "meta",
        "flag": "us",
        "note": "needs a machine with 64 GB or more of unified memory",
    },
]

MODEL_BY_REPO = {m["repo"]: m for m in MODELS}
MODEL_BY_KEY = {m["repo"].split("/")[-1].lower(): m for m in MODELS}


def band(key: str) -> dict | None:
    return next((b for b in BANDS if b["key"] == key), None)


def models(bands: list[str] | tuple[str, ...] | None = None) -> list[dict]:
    chosen = set(bands or BAND_KEYS)
    return [m for m in MODELS if m["band"] in chosen]


def get(repo: str) -> dict | None:
    return MODEL_BY_REPO.get(repo)


def by_key(key: str) -> dict | None:
    return MODEL_BY_KEY.get(str(key).rsplit("/", 1)[-1].lower())


def key_for(label: str) -> str:
    """The harbour key for a label, exactly as thorp.foreign._key makes it (chat deep links)."""
    return "".join(c if c.isalnum() else "-" for c in label.lower()).strip("-").replace("--", "-")


def params() -> dict[str, float]:
    return {m["repo"]: float(m["params"]) for m in MODELS}


def labels() -> dict[str, str]:
    return {m["repo"]: m["label"] for m in MODELS}


def labs() -> dict[str, str]:
    return {m["repo"]: m["lab"] for m in MODELS}


def fit(model: dict, memory_gb: float | None) -> str:
    """`fits`, `tight` or `needs-more` for this Mac. A large download is not the same as a run: the
    check is on unified memory, not disk."""
    if memory_gb is None:
        return "unknown"
    if model["run_gb"] > memory_gb * 0.8:
        return "needs-more"
    if model["run_gb"] > memory_gb * 0.6:
        return "tight"
    return "fits"


def band_counts() -> dict[str, int]:
    return {b["key"]: sum(1 for m in MODELS if m["band"] == b["key"]) for b in BANDS}


def class_rows(sizes: list[dict] | None = None) -> list[dict]:
    """Thorp's classes, from the store when it answers and from this bootstrap list before it does."""
    rows = {c["preset"]: dict(c) for c in CLASSES}
    if sizes:
        for s in sizes:
            row = rows.setdefault(s["preset"], {"preset": s["preset"]})
            row.update(
                {
                    "name": s.get("name") or row.get("name") or s["preset"],
                    "job": s.get("role") or s.get("job") or row.get("job") or "",
                    "where": s.get("where") or row.get("where") or "mac",
                    "status": s.get("status"),
                }
            )
    out = []
    for preset, row in rows.items():
        cfg = registry.PRESETS.get(preset)
        if cfg is None:
            continue
        params = _params_of(preset, cfg)
        row["params"] = params
        row["layers"] = cfg.get("layers")
        row["width"] = cfg.get("width")
        row["heads"] = cfg.get("heads")
        row["shape"] = (
            f"{cfg.get('layers')} layers · {cfg.get('width')} wide · ~{_short(params)} parameters"
        )
        out.append(row)
    return out


def _params_of(preset: str, cfg: dict) -> float:
    layers, width = float(cfg.get("layers") or 0), float(cfg.get("width") or 0)
    vocab = float(cfg.get("vocab") or 2048)
    return 12 * layers * width * width + layers * 4 * width * width + 2 * vocab * width


def _short(n: float) -> str:
    if n >= 1e9:
        return f"{n / 1e9:.1f}B"
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.0f}k"
    return str(int(n))


def class_fit(row: dict, memory_gb: float | None) -> str:
    """A class is a training job, so it is judged by where it trains, not by the chat memory rule."""
    where = str(row.get("where") or "mac").lower()
    if "vast" in where or "gpu" in where:
        return "needs-lane"
    if memory_gb is None:
        return "unknown"
    # rough training footprint: weights, AdamW's two moments, gradients and activations
    need = max(0.25, row.get("params", 0) * 12 / 1e9)
    if need > memory_gb * 0.9:
        return "needs-more"
    if need > memory_gb * 0.65:
        return "tight"
    return "fits"


def human_gb(gb: float | None) -> str:
    if gb is None:
        return "—"
    return f"{gb:.1f} GB" if gb < 10 else f"{gb:.0f} GB"


def human_params(n: float | None) -> str:
    if not n:
        return "—"
    if n >= 1e9:
        v = n / 1e9
        return f"{v:.0f}B" if abs(v - round(v)) < 0.05 else f"{v:.1f}B"
    if n >= 1e6:
        return f"{n / 1e6:.0f}M"
    return f"{n / 1e3:.0f}k"


def _round_gb(v: float) -> float:
    return math.ceil(v * 10) / 10

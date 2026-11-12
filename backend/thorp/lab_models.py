"""The houses' models on Hugging Face, for a lab's page (12 November, Justin: "within a labs details page ...
it should list all models that are available on hugging face in a table").

One row per repository the house's Hugging Face organisations publish: its id, downloads, likes, last
change, pipeline and parameter count, whether its weights are already cached for chat, and whether the
Reach has scored it. The list is fetched from the Hub's public API and cached for a few minutes; the
download itself is `thorp.lab_downloads`.
"""

from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request

# the lab key -> its Hugging Face organisations, in the order to ask. Empty for a house that publishes no
# weights on the Hub (Anthropic, Cognition); the page says so rather than showing a different house's list.
ORGS: dict[str, tuple[str, ...]] = {
    "google": ("google", "google-deepmind"),
    "openai": ("openai",),
    "meta": ("meta-llama", "facebook"),
    "alibaba": ("Qwen",),
    "microsoft": ("microsoft",),
    "deepseek": ("deepseek-ai",),
    "antgroup": ("inclusionAI",),
    "mistral": ("mistralai",),
    "xai": ("xai-org",),
    "moonshot": ("moonshotai",),
    "zai": ("zai-org", "THUDM"),
    "minimax": ("MiniMaxAI",),
    "cohere": ("CohereLabs", "CohereForAI"),
    "nvidia": ("nvidia",),
    "stepfun": ("stepfun-ai",),
    "bytedance": ("ByteDance-Seed", "ByteDance"),
    "thinkingmachines": ("thinkingmachines",),
    "tii": ("tiiuae",),
    "arcee": ("arcee-ai",),
    "ai2": ("allenai",),
    "hcompany": ("Hcompany",),
    "anthropic": (),
    "cognition": (),
}

_CACHE: dict[str, tuple[float, dict]] = {}
_TTL = 300.0

# NVIDIA's Hub organisation also hosts other houses' models that NVIDIA has quantised for its chips
# (Qwen3.6-NVFP4, Gemma-4-26B-A4B-NVFP4, GLM-5.3-NVFP4, Kimi-K2.6-NVFP4 ...). A house's page lists the
# house's own models, not every model it has optimised, so NVIDIA keeps Nemotron and its own families and
# drops a repo whose name belongs to another house. The other orgs publish their own families, so they need
# no such filter.
_OTHER_HOUSES = (
    "qwen", "gemma", "glm", "kimi", "deepseek", "gpt-oss", "phi", "mistral", "minimax", "stepfun",
    "seed", "falcon", "command", "grok", "ling", "llama", "mixtral", "yi-", "internlm", "baichuan",
    "chatglm", "cohere", "arcee", "olmo", "granite", "starcoder", "dbrx", "nova",
)


def _variant(label: str, pipeline: str) -> str:
    """What a repository is, as a searcher needs it: base, instruct, reasoning, a general model, or a
    non-text model (vision, audio, embedding, reranking). The name is the evidence the Hub gives; a
    quantised copy keeps its family's tuning (Falcon3-7B-Instruct-GGUF is instruct)."""
    low = label.lower()
    if any(k in low for k in ("reason", "thinking", "-r1", "-r2", "r1-", "r2-", "reasoner", "-h1r")):
        return "reasoning"
    if any(k in low for k in ("instruct", "-it", "-chat", "chat-", "-sft", "-dpo")):
        return "instruct"
    if any(k in low for k in ("base", "-pt", "pretrain", "pretrained")):
        return "base"
    text = {"text-generation", "text2text-generation", "text-to-text", "any-to-any", ""}
    return "general" if pipeline in text else "other"


def _keep(lab: str, label: str) -> bool:
    """Whether a Hub repository is the house's own model rather than another house's, optimised."""
    if lab != "nvidia":
        return True
    low = label.lower()
    if "nemotron" in low:
        return True
    return not any(token in low for token in _OTHER_HOUSES)


def _cached(model: str) -> bool:
    try:
        from huggingface_hub import try_to_load_from_cache

        return isinstance(try_to_load_from_cache(model, "config.json"), str)
    except Exception:  # noqa: BLE001  no Hub, no cache: the row says not cached
        return False


def _label(repo: str) -> str:
    return repo.rsplit("/", 1)[-1]


def _key(repo: str) -> str:
    return "".join(c if c.isalnum() else "-" for c in _label(repo).lower()).strip("-").replace("--", "-")


def _row(item: dict) -> dict:
    repo = str(item.get("id") or item.get("modelId") or "")
    safetensors = item.get("safetensors") or {}
    params = safetensors.get("total") if isinstance(safetensors, dict) else None
    inferred = False
    if params is None:
        # a GGUF/quantised repo often has no safetensors total; its name still carries the size
        # (AFM-4.5B-GGUF, Qwen3-8B-GGUF). Do not read `8x7B` as 8B: the x before the number excludes it.
        m = re.search(r"(?<![\dx])(\d+(?:\.\d+)?)\s*([bm])(?![a-z])", _label(repo), re.I)
        if m:
            params = float(m.group(1)) * (1e9 if m.group(2).lower() == "b" else 1e6)
            inferred = True
    tags = [str(t).lower() for t in (item.get("tags") or [])]
    pipeline = item.get("pipeline_tag") or item.get("pipelineTag") or ""
    low = f"{repo} {' '.join(tags)} {pipeline} {item.get('library_name') or ''}".lower()
    mlx = "mlx" in tags or "mlx" in low
    gguf = "gguf" in tags or "gguf" in low
    # an NVIDIA-optimised build, not merely a model that can run on NVIDIA hardware: the formats and
    # runtimes NVIDIA publishes its conversions in. `nvidia` alone is the owner's name, not a format.
    nvidia = any(tok in low for tok in ("nvfp4", "fp8", "tensorrt", "trt-llm", "trtllm", "cuda", "vllm", "sglang"))
    return {
        "model": repo,
        "label": _label(repo),
        "key": _key(repo),
        "downloads": item.get("downloads"),
        "likes": item.get("likes"),
        "last_modified": item.get("lastModified") or item.get("last_modified"),
        "released": item.get("createdAt") or item.get("created_at"),
        "pipeline": pipeline,
        "variant": _variant(_label(repo), pipeline),
        "params": params,
        "size_inferred": inferred,
        "mlx": mlx,
        "gguf": gguf,
        "mac": mlx or gguf,
        "nvidia": nvidia,
        "cached": _cached(repo),
        "url": f"https://huggingface.co/{repo}",
    }


def _fetch(org: str, limit: int) -> list[dict]:
    # `expand` carries the safetensors total (the model's size) and its first published date in the same
    # list call; `full` alone leaves safetensors out, and the size is what the table is for.
    q = urllib.parse.urlencode(
        [
            ("author", org), ("limit", limit), ("sort", "downloads"), ("direction", "-1"),
            ("expand[]", "safetensors"), ("expand[]", "createdAt"), ("expand[]", "lastModified"),
            ("expand[]", "downloads"), ("expand[]", "likes"), ("expand[]", "pipeline_tag"),
            ("expand[]", "tags"),
        ]
    )
    req = urllib.request.Request(
        f"https://huggingface.co/api/models?{q}",
        headers={"Accept": "application/json", "User-Agent": "thorp-dashboard"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read().decode())
    return data if isinstance(data, list) else []


def models(lab: str, limit: int = 200) -> dict:
    """The house's public Hub repositories, biggest by downloads first. Cached five minutes."""
    lab = str(lab or "").strip()
    orgs = ORGS.get(lab, ())
    if not orgs:
        return {"lab": lab, "orgs": [], "models": [], "error": "this house publishes no weights on the Hub"}
    now = time.time()
    hit = _CACHE.get(lab)
    if hit and now - hit[0] < _TTL:
        return hit[1]
    out: dict[str, dict] = {}
    errors = []
    for org in orgs:
        try:
            for item in _fetch(org, limit):
                row = _row(item)
                if row["model"] and _keep(lab, row["label"]):
                    out[row["model"]] = row
        except Exception as e:  # noqa: BLE001  the page says which org failed; the others still list
            errors.append(f"{org}: {e}")
    rows = sorted(out.values(), key=lambda r: (-(r.get("downloads") or 0), r["model"]))
    payload = {"lab": lab, "orgs": list(orgs), "models": rows, "error": "; ".join(errors) or None}
    _CACHE[lab] = (now, payload)
    return payload


def clear(lab: str | None = None) -> None:
    if lab is None:
        _CACHE.clear()
    else:
        _CACHE.pop(lab, None)

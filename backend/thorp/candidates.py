"""The leaderboard's three size classes and the candidates to approach next (11 November, Justin).

The board is split by model size: **extra small** under 1B, **small** 1B to 4B, **medium**
above 4B up to 32B, and **large** above 32B. The small class is the one with chaining readings; the medium and large
classes have none yet, so each carries the **likeliest candidates** to approach.

A candidate is a target, not a result. It has no chaining lift until it is scored on the four
chaining tests (`thorp/leaderboard.py`); its logic-deck reading, where one exists, is shown beside
it. The five are chosen on the evidence the board already has — the families that chain at 2–4B,
the reasoning leaders of the open field, and one boundary case that can be read on this Mac — not
on a chaining reading they do not have.

Parameter counts are the models' published totals (active parameters for a mixture of experts).
The boundaries are inclusive at the top: a model published at 4B belongs to the small class and
one at 32B to the medium class. A model under 1B is extra small; the missing-count fallback stays in
the small class, where the board's readings are.
"""

from __future__ import annotations

import contextlib
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SizeClass:
    key: str
    label: str
    range: str
    max_params: float | None  # inclusive; None means no upper bound


SIZE_CLASSES: tuple[SizeClass, ...] = (
    SizeClass("xsmall", "Extra small", "under 1B", 1e9),
    SizeClass("small", "Small", "1B – 4B", 4e9),
    SizeClass("medium", "Medium", "4B – 32B", 32e9),
    SizeClass("large", "Large", "above 32B", None),
)


def size_class(params: float | None) -> str:
    """A model's class by its total parameter count: extra small (<1B), small (<=4B), medium (<=32B),
    large (>32B).

    A missing count is treated as small: every reading the board holds without a published size is
    a small model, and a candidate always carries its published count."""
    if params is None:
        return "small"
    p = float(params)
    if p < 1e9:
        return "xsmall"
    if p <= 4e9:
        return "small"
    if p <= 32e9:
        return "medium"
    return "large"


def size_classes() -> list[dict]:
    return [asdict(s) for s in SIZE_CLASSES]


@dataclass(frozen=True)
class Candidate:
    model: str  # the Hugging Face id the readings are keyed by
    label: str
    params: float
    lab: str
    why: str
    source: str = ""  # its model card
    active: float | None = None  # active parameters, for a mixture of experts
    note: str = ""


# The five likeliest next targets in each unmeasured class, most likely first. The small board has
# five families that chain: Qwen3 4B (+0.538), Phi-4-mini (+0.348), Llama 3.2 3B (+0.285),
# Gemma 3 4B (+0.254) and SmolLM3 3B (+0.253); the medium and large lists scale those families and
# add the reasoning leaders of the open field.
MEDIUM: tuple[Candidate, ...] = (
    Candidate(
        model="mlx-community/Qwen3.8-27B-4bit",
        label="Qwen3.8 27B",
        params=27e9,
        lab="Alibaba · Qwen",
        why="The board leader's own family at 6.75× its size, and already on this Mac: its logic "
        "deck reads a +0.13 gain and +0.45 one-hop (Qwen3 4B: +0.19, +0.30).",
        note="the 4-bit checkpoint is on this Mac",
        source="https://huggingface.co/Qwen/Qwen3.8-27B",
    ),
    Candidate(
        model="Qwen/Qwen3-30B-A3B",
        label="Qwen3 30B-A3B",
        params=30e9,
        active=3.3e9,
        lab="Alibaba · Qwen",
        why="The same family's efficient MoE: near-70B benchmark quality with about 3B active, so "
        "its reading separates active compute from total capacity.",
        source="https://huggingface.co/Qwen/Qwen3-30B-A3B",
    ),
    Candidate(
        model="google/gemma-4-26B-A4B-it",
        label="Gemma 4 26B A4B",
        params=25.2e9,
        active=3.8e9,
        lab="Google · Gemma",
        why="Gemma 3 4B already chains (+0.254); this is the family's sparse 26B step, so it tests "
        "the family's scaling rather than a new lineage.",
        source="https://huggingface.co/google/gemma-4-26B-A4B-it",
    ),
    Candidate(
        model="microsoft/phi-4",
        label="Phi-4 14B",
        params=14e9,
        lab="Microsoft · Phi",
        why="Phi-4-mini is second on the small board (+0.348); its dense 14B sibling is the cleanest "
        "test of whether the Phi family's chaining scales with density.",
        source="https://huggingface.co/microsoft/phi-4",
    ),
    Candidate(
        model="google/gemma-4-31B-it",
        label="Gemma 4 31B",
        params=31e9,
        lab="Google · Gemma",
        why="The top of the medium band: 31B, just under the 32B line, and the likeliest medium "
        "model that fits a workstation at 4-bit; Gemma 3 4B already chains (+0.254).",
        note="the feasible first medium reading",
        source="https://huggingface.co/google/gemma-4-31B-it",
    ),
    Candidate(
        model="openai/gpt-oss-20b",
        label="gpt-oss 20B",
        params=21e9,
        active=3.6e9,
        lab="OpenAI",
        why="A reasoning-tuned open model from a different lineage: the control for whether "
        "post-training, not size, carries chaining.",
        source="https://huggingface.co/openai/gpt-oss-20b",
    ),
)


LARGE: tuple[Candidate, ...] = (
    Candidate(
        model="Qwen/Qwen3.8-2.4T-A95B",
        label="Qwen3.8 2.4T-A95B",
        params=2.4e12,
        active=95e9,
        lab="Alibaba · Qwen",
        why="The flagship of the family that leads the board: 2.4T total and 95B active, the "
        "largest step up from the 4B that chains.",
        source="https://huggingface.co/Qwen/Qwen3.8-2.4T-A95B",
    ),
    Candidate(
        model="deepseek-ai/DeepSeek-V4.1-Flash-1017",
        label="DeepSeek V4.1 Flash 1017",
        params=763e9,
        lab="DeepSeek",
        why="The highest-scoring open model in the November 2026 field (Respan Index 59.4); a "
        "reasoning and agent model at 763B.",
        source="https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017",
    ),
    Candidate(
        model="moonshotai/Kimi-K3",
        label="Kimi K3",
        params=2.8e12,
        active=104e9,
        lab="Moonshot AI · Kimi",
        why="The field's strongest knowledge reading (GPQA Diamond 93.1): 2.8T total, 104B active.",
        source="https://huggingface.co/moonshotai/Kimi-K3",
    ),
    Candidate(
        model="zai-org/GLM-5.3",
        label="GLM-5.3",
        params=744e9,
        active=40e9,
        lab="Z.ai · GLM",
        why="The top open-weight terminal/coding result; 744B total and 40B active, a second strong "
        "reasoning lineage.",
        source="https://huggingface.co/zai-org/GLM-5.3",
    ),
)


CANDIDATES: dict[str, tuple[Candidate, ...]] = {"medium": MEDIUM, "large": LARGE}


def rows() -> dict[str, list[dict]]:
    """The candidates by class, with the logic deck's reading attached where one exists.

    The logic deck is the only evidence the board has on a candidate so far (Qwen3.8 27B has been
    read on it); the four chaining tests have not been run. The reading is not a chaining result and
    is labelled as the logic deck's."""
    from thorp import arc_scores
    from thorp.viable.s4_intelligence import readings

    logic: dict[str, dict] = {}
    with contextlib.suppress(Exception):  # the board still renders if the store cannot be read
        for name, reading in readings.glob("logic-*"):
            kind, model = readings.kind_of(name)
            metrics = ((reading or {}).get("logic") or {}).get("metrics") or {}
            if kind == "logic" and model and metrics.get("gain") is not None:
                logic[model] = metrics
    out: dict[str, list[dict]] = {}
    for key, cands in CANDIDATES.items():
        out[key] = []
        for rank, c in enumerate(cands, 1):
            row = asdict(c)
            row["rank"] = rank
            row["size_class"] = key
            row["arc"] = arc_scores.for_model(c.model)
            m = logic.get(c.model) or {}
            one_hop = m.get("lift_one_hop")
            row["logic"] = (
                {
                    "gain": round(float(m["gain"]), 4),
                    "score": round(float(m.get("score") or 0.0), 3),
                    "one_hop": round(float(one_hop), 4),
                }
                if one_hop is not None
                else None
            )
            out[key].append(row)
    return out

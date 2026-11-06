"""Evaluators. Each takes an EvalContext and returns an EvalResult with rows in the evals columns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class EvalContext:
    run_id: str
    step: int
    model: Any
    tokeniser: Any
    context: int
    sets: dict[str, list[str]]  # set name -> book ids
    languages: dict[str, str] = field(default_factory=dict)  # book id -> language


@dataclass
class EvalResult:
    evals: list[dict] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)
    artifacts: list[dict] = field(default_factory=list)  # {kind, path, sha1, text}


class Evaluator(Protocol):
    def __call__(self, ctx: EvalContext) -> EvalResult: ...


def get(name: str) -> Evaluator:
    if name == "ce_bpb":
        from thorp.evaluators.ce_bpb import evaluate
    elif name == "samples":
        from thorp.evaluators.samples import evaluate
    else:
        raise KeyError(f"unknown evaluator {name!r}")
    return evaluate

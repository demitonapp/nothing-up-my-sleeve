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
    recipe: list[str] = field(default_factory=list)  # the books trained on (probes fit on these)
    # () -> the same architecture at initialisation, the run's own seed: the untrained floor
    init_model: Any = None
    # evaluator-specific settings from the spec's eval.options (e.g. {"arc": {"limit": 12}})
    options: dict = field(default_factory=dict)


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
    elif name == "probes":
        from thorp.evaluators.probes import evaluate
    elif name == "bpb_split":
        from thorp.evaluators.bpb_split import evaluate
    elif name == "laws":
        from thorp.evaluators.laws import evaluate
    elif name == "successor":
        from thorp.evaluators.successor import evaluate
    elif name == "soundings":
        from thorp.evaluators.soundings import evaluate
    elif name == "stars":
        from thorp.evaluators.stars import evaluate
    elif name == "nevermore":
        from thorp.evaluators.nevermore import evaluate
    elif name == "discovery":
        from thorp.evaluators.discovery import evaluate
    elif name == "logic":
        from thorp.evaluators.logic import evaluate
    elif name == "logic40":
        from thorp.evaluators.logic import evaluate40 as evaluate
    elif name == "crowns":
        from thorp.evaluators.logic import evaluate_crowns as evaluate
    elif name == "cards":
        from thorp.evaluators.cards import evaluate
    elif name == "curiosity":
        from thorp.evaluators.curiosity import evaluate
    elif name == "shapes":
        from thorp.evaluators.shapes import evaluate
    elif name == "pips":
        from thorp.evaluators.pips import evaluate
    elif name == "script":  # the Babel probe: cuneiform mass on English contexts (2026-11-08)
        from thorp.evaluators.script import evaluate
    elif name == "maths":  # the maths book, De Morgan's (2026-11-08: Augustus's objective)
        from thorp.evaluators.maths import evaluate
    elif name == "plato":  # Plato's primer, metaphysics (2026-11-08: the four positions at the 1m)
        from thorp.evaluators.primers import evaluate_plato as evaluate
    elif name == "francis":  # Francis's primer, empirical knowledge
        from thorp.evaluators.primers import evaluate_francis as evaluate
    elif name == "ifeval":  # instruction following, the 25 official verifiers (SOP v1.3.0)
        from thorp.evaluators.ifeval import evaluate
    elif name == "answers":  # the return leg: held-out questions, the answer's own loss (11 November)
        from thorp.evaluators.answers import evaluate
    elif name == "arc":  # ARC-AGI-2, the canonical intelligence test (11 November)
        from thorp.evaluators.arc import evaluate
    elif name == "arc_ai2":  # AI2 ARC, the one peer-recognised test for models under 1B (11 November)
        from thorp.evaluators.arc_ai2 import evaluate
    elif name == "blimp":  # BLiMP, the grammatical reading; ARC is the capability one (11 November)
        from thorp.evaluators.blimp import evaluate
    else:
        raise KeyError(f"unknown evaluator {name!r}")
    return evaluate

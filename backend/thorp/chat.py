"""Chat with a finished Thorp run's latest checkpoint, shared by the CLI and the dash.

Experimental: the model is a small GPT trained on Ogden, not an instruction-tuned assistant. A run
trained on v0.1.4 has seen the `<question>/<answer>` pieces; a run without a chat/QA arm will
continue prose rather than answer. The answer is returned as plain text.
"""

from __future__ import annotations

import json
from pathlib import Path

import mlx.core as mx

from thorp import tokeniser as tokmod
from thorp.evaluators.samples import generate
from thorp.ledger import reader, spec_of
from thorp.train import build_model, latest_checkpoint, load_master, to_compute

_CACHE: dict[tuple[str, int | None], tuple] = {}


def load(run_name: str, step: int | None = None):
    """The run's model, tokeniser, spec and checkpoint, cached by run and step."""
    key = (run_name, step)
    hit = _CACHE.get(key)
    if hit is not None:
        return hit
    row = reader().get_run_by_name(run_name, finished=True)
    if not row:
        raise LookupError(f"no finished run named {run_name!r}")
    spec = spec_of(row)
    ckpt = latest_checkpoint(row["run_id"])
    if ckpt is None:
        raise LookupError(f"{run_name!r} has no checkpoint yet")
    if step is not None:
        ckpt = ckpt.parent / f"step-{step}"
        if not (ckpt / "state.json").exists():
            raise LookupError(f"no checkpoint step {step} for {run_name!r}")
    state = json.loads((ckpt / "state.json").read_text())
    tok = tokmod.load(state["tokeniser_id"])
    model = build_model(spec, int(spec["tokeniser"]["vocab"]))
    model.update(to_compute(load_master(ckpt), spec["optim"].get("precision", "bf16")))
    mx.eval(model.parameters())
    _CACHE[key] = (model, tok, spec, ckpt)
    return _CACHE[key]


def _ask(model, tok, spec: dict, question: str, temperature: float, tokens: int, seed: int) -> str:
    prompt = f"<question>{question.strip()}<answer>"
    out = generate(model, tok, prompt, temperature, tokens, int(spec["model"]["context"]), mx.random.key(seed))
    for end in ("<end>", "<sep>", "<question>"):
        out = out.split(end)[0]
    return out.strip()


def answer(
    run_name: str,
    question: str,
    *,
    tokens: int = 80,
    temperature: float = 0.7,
    seed: int = 0,
    step: int | None = None,
) -> dict:
    """One answer from the run's latest checkpoint (or `step`). Raises LookupError for an unknown run."""
    model, tok, spec, ckpt = load(run_name, step)
    text = _ask(model, tok, spec, question, temperature, tokens, seed)
    return {"run": run_name, "step": ckpt.name, "answer": text}

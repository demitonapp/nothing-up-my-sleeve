#!/usr/bin/env python
"""Chat with a finished Thorp run's latest checkpoint. Experimental.

The model is a small GPT trained on Ogden, not an instruction-tuned assistant. Without a chat/QA
arm it will continue prose rather than answer. The prompt is wrapped in the v0.1.4 marks
(`<question>...<answer>`) so a run trained on that corpus at least sees the pieces it was taught.
The 9m (`--run 9m@v0.0.6`) is the first size meant to hold this format; until it finishes, use
`1m@v0.0.6-fulldeck` (or any finished run) to test the interface.

    PYTHONPATH=backend .venv/bin/python backend/scripts/chat.py --run 1m@v0.0.6-fulldeck
    ... --prompt "<question>What is a mill?<answer>" --tokens 40

"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import mlx.core as mx

from thorp import tokeniser as tokmod
from thorp.evaluators.samples import generate
from thorp.ledger import reader, spec_of
from thorp.train import build_model, load_master, latest_checkpoint, to_compute


def load(run_name: str, step: int | None = None):
    row = reader().get_run_by_name(run_name, finished=True)
    if not row:
        raise SystemExit(f"no finished run named {run_name!r}")
    spec = spec_of(row)
    ckpt = latest_checkpoint(row["run_id"])
    if ckpt is None:
        raise SystemExit(f"{run_name!r} has no checkpoint yet")
    if step is not None:
        ckpt = ckpt.parent / f"step-{step}"
        if not (ckpt / "state.json").exists():
            raise SystemExit(f"no checkpoint step {step} for {run_name!r}")
    state = json.loads((ckpt / "state.json").read_text())
    tok = tokmod.load(state["tokeniser_id"])
    model = build_model(spec, int(spec["tokeniser"]["vocab"]))
    model.update(to_compute(load_master(ckpt), spec["optim"].get("precision", "bf16")))
    mx.eval(model.parameters())
    return model, tok, spec, ckpt


def wrap(user: str) -> str:
    return f"<question>{user.strip()}<answer>"


def answer(model, tok, spec: dict, user: str, temperature: float, tokens: int, seed: int) -> str:
    out = generate(
        model,
        tok,
        wrap(user),
        temperature,
        tokens,
        int(spec["model"]["context"]),
        mx.random.key(seed),
    )
    for end in ("<end>", "<sep>", "<question>"):
        out = out.split(end)[0]
    return out.strip()


def main() -> None:
    ap = argparse.ArgumentParser(description="Chat with a finished Thorp checkpoint.")
    ap.add_argument("--run", default="9m@v0.0.6", help="the run name (default: the 9m)")
    ap.add_argument("--step", type=int, default=None, help="a checkpoint step, else the latest")
    ap.add_argument("--prompt", default=None, help="one question, then exit")
    ap.add_argument("--tokens", type=int, default=80)
    ap.add_argument("--temperature", type=float, default=0.7)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args()

    model, tok, spec, ckpt = load(a.run, a.step)
    print(f"run {a.run} · {ckpt.name} · vocab {spec['tokeniser']['vocab']} · context {spec['model']['context']}", file=sys.stderr)
    if a.prompt is not None:
        print(answer(model, tok, spec, a.prompt, a.temperature, a.tokens, a.seed))
        return
    print("Type a question. Ctrl-D to stop.", file=sys.stderr)
    while True:
        try:
            user = input("you> ")
        except EOFError:
            print(file=sys.stderr)
            return
        if not user.strip():
            continue
        print(f"thorp> {answer(model, tok, spec, user, a.temperature, a.tokens, a.seed)}")


if __name__ == "__main__":
    main()

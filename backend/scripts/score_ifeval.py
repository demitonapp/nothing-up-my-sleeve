"""Score an outside model on IFEval, the third test card on the extra small board (12 November, Justin: "can you
also score all the xsmall models on ifeval and add them to the leaderboard").

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/score_ifeval.py MODEL [--limit N] [--max-new 512]

The prompts and the checks are the evaluator's (thorp/evaluators/ifeval.py: the 541 prompts and the authors'
25 verifiers), so an outside reading and a ship's are checked by the same code. Greedy, one sample, no
verifier loop. Prompt-level strict and instruction-level strict, as the paper reports them.

The format follows the checkpoint, and every reading states it: a post-trained checkpoint (CHAT below) is asked
through its own chat template, with Qwen3's thinking switched off so the answer is the response; a base
checkpoint is given the prompt bare and its continuation is the response. The cap on new pieces is a cost
control the benchmark does not have, and is kept in the reading; a response that ends inside it ended itself.

Kept in `s4.outside_readings` as `ifeval-<model>`, with one receipt row a prompt (its key, each instruction
followed or not, the response's hash and length), so a number can be re-derived and two models compared prompt
by prompt. `--no-helm` skips waiting for a voyage at sea, as score_arc_ai2.py does.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/mlx_ports.py

from thorp.evaluators import ifeval  # noqa: E402
from thorp.viable.s4_intelligence import readings  # noqa: E402

# the post-trained checkpoints on the extra small board; everything else there is a base checkpoint
CHAT = {"Qwen/Qwen3-0.6B", "mlx-community/Qwen3.5-0.8B-bf16"}


def _prompt(tok, model_id: str, text: str, chat: bool) -> list[int]:
    if not chat:
        return tok.encode(text)
    msgs = [{"role": "user", "content": text}]
    try:
        return tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False)
    except TypeError:
        return tok.apply_chat_template(msgs, add_generation_prompt=True)


def score(model_id: str, limit: int, max_new: int, save: bool, chat: bool | None = None) -> dict:
    import mlx.core as mx
    from mlx_lm import load, stream_generate
    from mlx_lm.sample_utils import make_sampler

    model, tok = load(model_id)
    mx.set_cache_limit(1 << 30)  # as score_arc_ai2.py: give freed buffers back to a voyage beside it
    chat = (model_id in CHAT) if chat is None else chat
    greedy = make_sampler(temp=0.0)
    cases = ifeval._cases(limit)
    t0 = time.time()
    rows, prompt_ok, instr_ok, instr_n, ended = [], 0, 0, 0, 0
    for i, row in enumerate(cases):
        ids = _prompt(tok, model_id, row["prompt"], chat)
        text, finish = "", None
        for r in stream_generate(model, tok, ids, max_tokens=max_new, sampler=greedy):
            text += r.text
            finish = r.finish_reason
        stopped = finish == "stop"
        ended += int(stopped)
        checks = ifeval._check(row, text)
        passed = all(c["followed"] for c in checks)
        prompt_ok += int(passed)
        instr_ok += sum(c["followed"] for c in checks)
        instr_n += len(checks)
        rows.append(
            {
                "key": row["key"],
                "passed": passed,
                "checks": checks,
                "stopped": stopped,
                "sha1": hashlib.sha1(text.encode("utf-8")).hexdigest(),
                "chars": len(text),
            }
        )
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(cases)}: prompt-strict {prompt_ok / (i + 1):.3f} ({time.time() - t0:.0f}s)", flush=True)
    n = len(rows) or 1
    out = {
        "model": model_id,
        "format": "chat" if chat else "bare",
        "thinking": "off" if chat else None,
        "max_new": max_new,
        "prompts": len(rows),
        "full_set": len(rows) >= 541,
        "prompt_strict": prompt_ok / n,
        "instruction_strict": (instr_ok / instr_n) if instr_n else 0.0,
        "instructions": instr_n,
        "stopped": ended / n,
        "scored": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": round(time.time() - t0, 1),
        "rows": rows,
    }
    print(
        f"{model_id} [{out['format']}]: prompt-strict {out['prompt_strict']:.3f}, instruction-strict "
        f"{out['instruction_strict']:.3f} over {len(rows)} prompts, ended itself {out['stopped']:.0%}, {out['seconds']:.0f}s"
    )
    if save:
        readings.put(f"ifeval-{model_id}", out)
        print(f"kept as ifeval-{model_id} in s4.outside_readings")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--limit", type=int, default=541, help="prompts to read; 541 is the whole set")
    ap.add_argument("--max-new", type=int, default=512, help="cap on new pieces a response")
    ap.add_argument("--format", choices=["auto", "chat", "bare"], default="auto")
    ap.add_argument("--no-helm", action="store_true", help="do not wait for a voyage at sea")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    chat = None if a.format == "auto" else a.format == "chat"
    if a.no_helm:
        score(a.model, a.limit, a.max_new, not a.no_save, chat)
        return
    from thorp import vsm

    with vsm.at_sea(f"score {a.model} on IFEval", kind="score"):
        score(a.model, a.limit, a.max_new, not a.no_save, chat)


if __name__ == "__main__":
    main()

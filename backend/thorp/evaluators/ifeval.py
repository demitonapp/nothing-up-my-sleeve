"""IFEval: the 541 prompts and the 25 official verifiers (Zhou et al., 2023), read as two numbers.

Prompt-level strict accuracy and instruction-level strict accuracy, on the model's own continuation.
The checks are the authors' (thorp/ifeval_eval/, Apache 2.0, only imports changed), so the number
is comparable with the published ones — but only while the variant is stated: prompt-level strict,
greedy, one sample, no verifier loop.

Cost control: an in-run reading is a fixed, stratified subset (LIMIT prompts, every k-th on the
list, so all 25 instruction types appear); the full 541 is read after docking with
`THORP_IFEVAL_LIMIT=541 thorp eval`. The metric names carry the n, so a 96-prompt reading can never
be mistaken for the full set.

The artifact is the receipt: one row a prompt — its key, which instructions it carried, whether each
was followed, and the response's hash. Nothing here is summarised away.
"""

from __future__ import annotations

import hashlib
import json
import os
import time

from thorp import turns
from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.samples import greedy
from thorp.paths import resolve

# the punkt tokeniser the official checks need lives in the repo (ships/lists/nltk_data), so the
# reading does not depend on a machine's ~/nltk_data being populated
os.environ.setdefault("NLTK_DATA", str(resolve("lists/nltk_data")))

LIMIT = 96  # in-run prompts; the full 541 is a post-hoc read (THORP_IFEVAL_LIMIT=541)
MAX_NEW = 256  # tokens; the prompts ask for paragraphs, a small model will not fill them


def _cases(limit: int) -> list[dict]:
    path = resolve("lists/ifeval-input-v1.jsonl")
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    rows.sort(key=lambda r: r["key"])
    if limit >= len(rows):
        return rows
    step = max(1, len(rows) // limit)  # every k-th, so the 25 instruction types stay represented
    return rows[::step][:limit]


def _steady() -> None:
    """The language checks use langdetect, which draws at random unless seeded: seeded, a response reads the
    same every time it is checked (11 November: the builder kept 482 turns on one run and 479 on the next)."""
    from langdetect import DetectorFactory

    DetectorFactory.seed = 0


def _check(row: dict, response: str) -> list[dict]:
    from thorp.ifeval_eval import instructions_registry as registry
    _steady()

    out = []
    for iid, kwargs in zip(row["instruction_id_list"], row["kwargs"], strict=True):
        inst = registry.INSTRUCTION_DICT[iid](iid)
        try:
            inst.build_description(**kwargs)
            ok = bool(inst.check_following(response))
        except Exception as e:  # a checker that cannot run is a reading of False, and is recorded as such
            ok = False
            out.append({"instruction": iid, "followed": False, "error": f"{e.__class__.__name__}: {e}"})
            continue
        out.append({"instruction": iid, "followed": ok})
    return out


def evaluate(ctx: EvalContext) -> EvalResult:
    import os

    # eval.options.ifeval (11 November, the return leg): `format` asks each prompt as a turn in the form the
    # voyage was taught (thorp/turns.py: marks or plain, through its `clean`), and the response ends where the
    # turn does; `max_new` lifts the cap (the benchmark sets none: 256 was this reader's cost control, and it
    # ruled out every prompt that asks for a few hundred words); `limit` is the prompts read. Without
    # options the prompt is given bare, as before. Greedy, one sample, and the response always ends at the
    # ship's own end-of-text mark: what it writes after that is not its answer.
    opts = ((ctx.options or {}).get("ifeval") or {}) if isinstance(ctx.options, dict) else {}
    fmt, clean = opts.get("format"), str(opts.get("clean") or "raw")
    max_new = int(opts.get("max_new") or MAX_NEW)
    limit = int(os.environ.get("THORP_IFEVAL_LIMIT", opts.get("limit") or LIMIT))
    cases = _cases(limit)
    t0 = time.time()
    per_prompt, prompt_ok, instr_ok, instr_n, stopped_n = [], 0, 0, 0, 0
    tok = ctx.tokeniser
    end = tok.encode("<end>") if fmt == "marks" else []
    stop_ids = end if len(end) == 1 else ()  # the end mark, when the voyage holds it as one piece
    for row in cases:
        asked = turns.prompt(fmt, row["prompt"], clean) if fmt else row["prompt"]
        ids = ([tok.eos_id] if fmt else []) + tok.encode(asked)  # a taught turn follows the end-of-text mark
        out, stopped = greedy(ctx.model, tok, ids, max_new, ctx.context, stop_ids)
        response = tok.decode(out)
        response = turns.cut(fmt, response) if fmt else response
        stopped_n += int(stopped)
        checks = _check(row, response)
        passed = all(c["followed"] for c in checks)
        prompt_ok += int(passed)
        instr_ok += sum(c["followed"] for c in checks)
        instr_n += len(checks)
        per_prompt.append(
            {
                "key": row["key"],
                "passed": passed,
                "checks": checks,
                "sha1": hashlib.sha1(response.encode("utf-8")).hexdigest(),
                "chars": len(response),
            }
        )
    n = len(per_prompt) or 1
    metrics = {
        "ifeval/prompt_strict": prompt_ok / n,
        "ifeval/instruction_strict": (instr_ok / instr_n) if instr_n else 0.0,
        "ifeval/n_prompts": float(len(per_prompt)),
        "ifeval/n_instructions": float(instr_n),
        "ifeval/seconds": time.time() - t0,
        "ifeval/full_set": 1.0 if len(per_prompt) >= 541 else 0.0,
        "ifeval/stopped": stopped_n / n,  # the share of responses the ship ended itself, inside the cap
        "ifeval/max_new": float(max_new),
    }
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "ifeval",
                "path": "",
                "sha1": "",
                "text": json.dumps({"step": ctx.step, "n": len(per_prompt), "format": fmt or "bare",
                                    "clean": clean, "max_new": max_new, "prompts": per_prompt}),
            }
        ],
    )

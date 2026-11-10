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

from thorp.evaluators import EvalContext, EvalResult
from thorp.evaluators.samples import generate
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


def _check(row: dict, response: str) -> list[dict]:
    from thorp.ifeval_eval import instructions_registry as registry

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

    limit = int(os.environ.get("THORP_IFEVAL_LIMIT", LIMIT))
    cases = _cases(limit)
    t0 = time.time()
    per_prompt, prompt_ok, instr_ok, instr_n = [], 0, 0, 0
    key = ctx.step if isinstance(ctx.step, int) else 0
    for i, row in enumerate(cases):
        response = generate(ctx.model, ctx.tokeniser, row["prompt"], 0.0, MAX_NEW, ctx.context, key + i)
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
    }
    return EvalResult(
        metrics=metrics,
        artifacts=[
            {
                "kind": "ifeval",
                "path": "",
                "sha1": "",
                "text": json.dumps({"step": ctx.step, "n": len(per_prompt), "prompts": per_prompt}),
            }
        ],
    )

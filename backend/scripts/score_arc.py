"""Score an outside model on ARC-AGI-2, the canonical intelligence test (11 November, Justin).

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/score_arc.py MODEL [--limit 12]

MODEL is a Hugging Face id or local path mlx-lm can load. The prompt is the compact ARC-AGI-2 form
(thorp/arc.py): a few input/output grid examples, then the test input. The model writes the output
grid; the reading is exact match (ARC's rule), with cell accuracy beside it. Two attempts are made
(greedy, then sampled) so `pass@2` is ARC-AGI-2's own two-attempt rule.

The default is a **pilot of 12 evaluation tasks**, not the full 120, because generation is
token-by-token and a 4B model takes minutes an attempt. `--limit 0` reads the whole split. A pilot is
stored with `"pilot": true` and must not be compared with a published ARC-AGI-2 score.

The reading is kept in `s4.outside_readings` as `arc-<model>` (was data/compare/arc-<model>.json), in
the same shape as the other outside readings: the summary, the settings, and every task's prompt,
outputs and result.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # scripts/mlx_ports.py, as score_external.py

from thorp import arc  # noqa: E402
from thorp.viable.s4_intelligence import readings  # noqa: E402


def _load(model_id: str):
    from mlx_lm import load

    try:
        return load(model_id)
    except Exception:
        import mlx_ports  # models mlx-lm cannot load (Maincoder), built from their weights alone

        port = mlx_ports.port_for(model_id)
        if port is None:
            raise
        return port()


def _prompt(task: dict, tok, pairs: int, mode: str) -> str:
    body = arc.task_prompt(task, pairs)
    if mode != "chat":
        return body
    messages = [
        {
            "role": "system",
            "content": "You solve ARC-AGI-2 tasks. Reply with only the output grid, in the form "
            "rows x cols:row/row/..., with each row's digits 0-9 and no other words.",
        },
        {"role": "user", "content": body + "\nReply with only the output grid."},
    ]
    return tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False)


def _fit(task: dict, tok, context: int, max_output: int, pairs: int, mode: str) -> tuple[str | None, int]:
    for n in range(max(0, pairs), -1, -1):
        prompt = _prompt(task, tok, n, mode)
        if len(tok.encode(prompt)) + max_output <= context:
            return prompt, n
    return None, 0


def _mode(tok, want: str) -> str:
    if want != "auto":
        return want
    has = callable(getattr(tok, "apply_chat_template", None))
    if not has:
        return "raw"
    # a base checkpoint's tokenizer has a template method but no conversation template; ask it
    try:
        tok.apply_chat_template([{"role": "user", "content": "x"}], add_generation_prompt=True)
        return "chat"
    except Exception:  # noqa: BLE001
        return "raw"


def score(model_id: str, split: str, limit: int, max_output: int, pairs: int, mode: str, context: int, save: bool, ids: str = "") -> dict:
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler

    model, tok = _load(model_id)
    mode = _mode(tok, mode)
    tasks = arc.tasks(split, limit=None)
    if ids:
        want = {x.strip() for x in ids.split(",") if x.strip()}
        tasks = [t for t in tasks if t.get("id") in want]
    tasks = tasks[:limit] if limit else tasks
    rows, t0 = [], time.time()
    for i, task in enumerate(tasks, 1):
        want = arc.expected(task)
        shape = arc.shape_of(task)
        prompt, used = _fit(task, tok, context, max_output, pairs, mode)
        if prompt is None:
            rows.append({"id": task.get("id", f"task-{i}"), "skipped": "context"})
            print(f"{i:3}/{len(tasks)} {task.get('id', ''):12} skipped (context)", flush=True)
            continue
        outputs, exact1, exact2, parsed_any, acc = [], False, False, False, 0.0
        for attempt in range(2):
            text = generate(
                model,
                tok,
                prompt=prompt,
                max_tokens=max_output,
                sampler=make_sampler(temp=0.0 if attempt == 0 else 0.8),
                verbose=False,
            )
            grid, ok = arc.parse_grid(text, shape=shape)
            parsed_any = parsed_any or ok
            exact = arc.exact(grid, want)
            if attempt == 0:
                exact1, acc = exact, arc.cell_accuracy(grid, want)
            else:
                exact2 = exact
            outputs.append({"text": text, "parsed": ok, "exact": exact})
            if exact:
                break
        rows.append(
            {
                "id": task.get("id", f"task-{i}"),
                "pairs": used,
                "prompt_tokens": len(tok.encode(prompt)),
                "outputs": outputs,
                "parsed": parsed_any,
                "exact": exact1,
                "exact2": exact2,
                "cell_accuracy": acc,
            }
        )
        print(
            f"{i:3}/{len(tasks)} {task.get('id', ''):12} {'solved' if exact1 else 'pass@2' if exact2 else '—'}"
            f"  {time.time() - t0:6.0f}s",
            flush=True,
        )
    scored = [r for r in rows if not r.get("skipped")]
    s = arc.summary(scored)
    out = {
        "model": model_id,
        "split": split,
        "limit": len(tasks),
        "pilot": len(tasks) < (arc.PUBLIC_EVAL if split == "evaluation" else arc.PUBLIC_TRAIN),
        "mode": mode,
        "max_output": max_output,
        "max_pairs": pairs,
        "attempts": 2,
        **s,
        "skipped_context": len(rows) - len(scored),
        "scored": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": round(time.time() - t0, 1),
        "results": rows,
    }
    if save:
        readings.put(f"arc-{model_id}", out)
        print(f"kept as arc-{model_id} in s4.outside_readings")
    print(
        f"{model_id}: pass@1 {s['pass@1']:.3f}, pass@2 {s['pass@2']:.3f}, "
        f"{s['solved']} of {s['tasks']} solved, cell accuracy {s['cell_accuracy']:.3f}"
        + (" (pilot)" if out["pilot"] else "")
    )
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--split", default="evaluation", choices=arc.SPLITS)
    ap.add_argument("--limit", type=int, default=12, help="tasks to read; 0 means the whole split")
    ap.add_argument("--max-output", type=int, default=512)
    ap.add_argument("--max-pairs", type=int, default=3)
    ap.add_argument("--mode", default="auto", choices=("auto", "chat", "raw"))
    ap.add_argument("--context", type=int, default=8192)
    ap.add_argument("--ids", default="", help="comma-separated task ids (a chosen pilot)")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    score(a.model, a.split, a.limit, a.max_output, a.max_pairs, a.mode, a.context, not a.no_save, a.ids)


if __name__ == "__main__":
    main()

"""Score an outside model on ARC-AGI-2, the canonical intelligence test (11 November, Justin).

    PYTHONPATH=backend backend/.venv/bin/python backend/scripts/score_arc.py MODEL [--limit 12]

MODEL is a Hugging Face id or local path mlx-lm can load. The prompt is the compact ARC-AGI-2 form
(thorp/arc.py): a few input/output grid examples, then the test input. The model writes the output
grid; the reading is exact match (ARC's rule), with cell accuracy beside it. Two attempts are made
(greedy, then sampled) so `pass@2` is ARC-AGI-2's own two-attempt rule.

The default is a **pilot of 12 evaluation tasks**, not the full 120, because generation is
token-by-token and a 4B model takes minutes an attempt. `--limit 0` reads the whole split. A pilot is
stored with `"pilot": true` and must not be compared with a published ARC-AGI-2 score.

A model whose chat template has a thinking switch (Qwen3) is read with it **off** by default, **on**
with `--thinking on`, or both in one load with `--thinking both`. With thinking on the model gets
`--max-thinking` tokens to think and then `--max-output` for the grid; only what follows `</think>`
is read as the answer, and thinking that never ends is counted (`thinking_unfinished`), not scored
as a wrong grid. A template with no switch, or a raw prompt, is read as it comes (`thinking: null`).

The reading is kept in `s4.outside_readings` as `arc-<model>` (was data/compare/arc-<model>.json), or
`arc-<model>@thinking` for a thinking-on reading so the two never overwrite each other, in the same
shape as the other outside readings: the summary, the settings, and every task's prompt, outputs and
result.
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


def _has_switch(tok) -> bool:
    """Whether the chat template answers to `enable_thinking`: it renders differently on and off."""
    messages = [{"role": "user", "content": "x"}]
    try:
        on, off = (
            tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False, enable_thinking=v)
            for v in (True, False)
        )
    except Exception:  # noqa: BLE001 - no conversation template, or one that refuses the argument
        return False
    return on != off


def _prompt(task: dict, tok, pairs: int, mode: str, thinking: str | None = None) -> str:
    body = arc.task_prompt(task, pairs)
    if mode != "chat":
        return body
    switch = {} if thinking is None else {"enable_thinking": thinking == "on"}
    messages = [
        {
            "role": "system",
            "content": "You solve ARC-AGI-2 tasks. Reply with only the output grid, in the form "
            "rows x cols:row/row/..., with each row's digits 0-9 and no other words.",
        },
        {"role": "user", "content": body + "\nReply with only the output grid."},
    ]
    return tok.apply_chat_template(messages, add_generation_prompt=True, tokenize=False, **switch)


def _fit(
    task: dict, tok, context: int, budget: int, pairs: int, mode: str, thinking: str | None = None
) -> tuple[str | None, int]:
    for n in range(max(0, pairs), -1, -1):
        prompt = _prompt(task, tok, n, mode, thinking)
        if len(tok.encode(prompt)) + budget <= context:
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


def _settings(tok, mode: str, thinking: str) -> list[str | None]:
    """The thinking settings to read, in order: `off`/`on` where the template has the switch, else None."""
    if mode != "chat" or not _has_switch(tok):
        if thinking != "off":
            why = "a raw prompt" if mode != "chat" else "this model's chat template"
            print(f"{why} has no thinking switch: read once, as it comes", flush=True)
        return [None]
    return ["off", "on"] if thinking == "both" else [thinking]


def _read(
    model, tok, model_id: str, tasks: list[dict], split: str, max_output: int, pairs: int, mode: str,
    context: int, thinking: str | None, max_thinking: int,
) -> dict:
    """One reading of the tasks at one thinking setting."""
    from mlx_lm import generate
    from mlx_lm.sample_utils import make_sampler

    budget = max_output + (max_thinking if thinking == "on" else 0)
    rows, t0 = [], time.time()
    for i, task in enumerate(tasks, 1):
        want = arc.expected(task)
        shape = arc.shape_of(task)
        prompt, used = _fit(task, tok, context, budget, pairs, mode, thinking)
        if prompt is None:
            rows.append({"id": task.get("id", f"task-{i}"), "skipped": "context"})
            print(f"{i:3}/{len(tasks)} {task.get('id', ''):12} skipped (context)", flush=True)
            continue
        opened = prompt.rstrip().endswith(arc.THINK_OPEN)  # a template that opens the thinking itself
        outputs, exact1, exact2, parsed_any, acc, unfinished = [], False, False, False, 0.0, False
        for attempt in range(2):
            text = generate(
                model,
                tok,
                prompt=prompt,
                max_tokens=budget,
                sampler=make_sampler(temp=0.0 if attempt == 0 else 0.8),
                verbose=False,
            )
            answer = arc.answer_text(text, opened=opened)
            grid, ok = arc.parse_grid(answer, shape=shape) if answer is not None else (None, False)
            parsed_any = parsed_any or ok
            exact = arc.exact(grid, want)
            if attempt == 0:
                exact1, acc, unfinished = exact, arc.cell_accuracy(grid, want), answer is None
            else:
                exact2 = exact
            outputs.append({"text": text, "answered": answer is not None, "parsed": ok, "exact": exact})
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
                "unfinished": unfinished,
            }
        )
        print(
            f"{i:3}/{len(tasks)} {task.get('id', ''):12} "
            f"{'solved' if exact1 else 'pass@2' if exact2 else 'thinking ran out' if unfinished else '—'}"
            f"  {time.time() - t0:6.0f}s",
            flush=True,
        )
    scored = [r for r in rows if not r.get("skipped")]
    s = arc.summary(scored)
    return {
        "model": model_id,
        "split": split,
        "limit": len(tasks),
        "pilot": len(tasks) < (arc.PUBLIC_EVAL if split == "evaluation" else arc.PUBLIC_TRAIN),
        "mode": mode,
        "thinking": thinking,
        "max_output": max_output,
        "max_thinking": max_thinking if thinking == "on" else 0,
        "max_pairs": pairs,
        "attempts": 2,
        **s,
        "thinking_unfinished": sum(1 for r in scored if r.get("unfinished")),
        "skipped_context": len(rows) - len(scored),
        "scored": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "seconds": round(time.time() - t0, 1),
        "results": rows,
    }


def score(
    model_id: str, split: str, limit: int, max_output: int, pairs: int, mode: str, context: int, save: bool,
    ids: str = "", thinking: str = "off", max_thinking: int = 4096,
) -> list[dict]:
    """The model's readings, one for each thinking setting asked for (the model is loaded once)."""
    model, tok = _load(model_id)
    mode = _mode(tok, mode)
    tasks = arc.tasks(split, limit=None)
    if ids:
        want = {x.strip() for x in ids.split(",") if x.strip()}
        tasks = [t for t in tasks if t.get("id") in want]
    tasks = tasks[:limit] if limit else tasks
    outs = []
    for setting in _settings(tok, mode, thinking):
        if setting:
            print(f"thinking {setting}", flush=True)
        out = _read(model, tok, model_id, tasks, split, max_output, pairs, mode, context, setting, max_thinking)
        name = arc.reading_name(model_id, setting)
        if save:
            readings.put(name, out)
            print(f"kept as {name} in s4.outside_readings")
        print(
            f"{model_id}{f' (thinking {setting})' if setting else ''}: pass@1 {out['pass@1']:.3f}, "
            f"pass@2 {out['pass@2']:.3f}, {out['solved']} of {out['tasks']} solved, "
            f"a grid written on {out['format_rate']:.0%}, cell accuracy {out['cell_accuracy']:.3f}"
            + (f", thinking ran out on {out['thinking_unfinished']}" if out["thinking_unfinished"] else "")
            + (" (pilot)" if out["pilot"] else "")
        )
        outs.append(out)
    return outs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("--split", default="evaluation", choices=arc.SPLITS)
    ap.add_argument("--limit", type=int, default=12, help="tasks to read; 0 means the whole split")
    ap.add_argument("--max-output", type=int, default=512, help="tokens for the answer grid")
    ap.add_argument("--max-pairs", type=int, default=3)
    ap.add_argument("--mode", default="auto", choices=("auto", "chat", "raw"))
    ap.add_argument(
        "--thinking", default="off", choices=("off", "on", "both"),
        help="a thinking model's switch: off (the default), on, or both readings in one load",
    )
    ap.add_argument("--max-thinking", type=int, default=4096, help="tokens to think with, before the answer's")
    ap.add_argument("--context", type=int, default=8192)
    ap.add_argument("--ids", default="", help="comma-separated task ids (a chosen pilot)")
    ap.add_argument("--no-save", action="store_true")
    a = ap.parse_args()
    score(
        a.model, a.split, a.limit, a.max_output, a.max_pairs, a.mode, a.context, not a.no_save, a.ids,
        a.thinking, a.max_thinking,
    )


if __name__ == "__main__":
    main()

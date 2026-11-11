"""ARC-AGI-2: the canonical intelligence test, as data and as a text task (11 November, Justin).

ARC-AGI-2 is the ARC Prize benchmark for **fluid intelligence**: each task gives a handful of
input/output grid examples and asks for the output of a new input, with no language, no domain
knowledge and no memorisable pattern. It is the external ranking the leaderboard is measured
against; the chaining tests are the skill ladder that leads to it.

This module is the shared plumbing, so the evaluator (`thorp/evaluators/arc.py`), the outside-model
scorer (`scripts/score_arc.py`) and the corpus builder all use one encoding:

    ARC-AGI-2
    Example 1: input 3x3:010/101/010 -> output 3x3:111/111/111
    Test: input 3x3:000/000/001 -> output

A grid is ``rows x cols:`` then the rows, each row's digits 0-9 with no spaces, joined by ``/``.
The model's answer is parsed back to a grid and compared exactly (ARC's own rule); cell accuracy is
kept as the partial reading, never as a substitute for exact.

The data is Apache 2.0, cloned read-only from https://github.com/arcprize/ARC-AGI-2 into
``data/arc-agi-2`` (THORP_ARC overrides it). The public evaluation set is 120 tasks; the training
set is 1,000. The semi-private and private sets are not public and are not fetched.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

from thorp import paths

REPO = "https://github.com/arcprize/ARC-AGI-2.git"
SPLITS = ("training", "evaluation")
PUBLIC_EVAL = 120
PUBLIC_TRAIN = 1000

_HEADER = re.compile(r"(?P<r>\d+)\s*[xX]\s*(?P<c>\d+)\s*:\s*(?P<rows>[0-9][0-9/]*)")
_BARE = re.compile(r"(?P<rows>[0-9][0-9/]*)")


def root() -> Path:
    """Where the ARC-AGI-2 checkout lives (``data/arc-agi-2`` by default, THORP_ARC overrides)."""
    return Path(os.environ.get("THORP_ARC") or paths.resolve("data/arc-agi-2"))


def ensure(base: Path | None = None) -> Path:
    """The ARC-AGI-2 checkout, cloned once if it is not there. Returns its root."""
    base = Path(base) if base else root()
    if (base / "data" / "evaluation").is_dir() and (base / "data" / "training").is_dir():
        return base
    base.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "clone", "--depth", "1", REPO, str(base)], check=True)
    return base


def tasks(split: str = "evaluation", limit: int | None = None, base: Path | None = None) -> list[dict]:
    """The tasks of a split, sorted by id; `limit` takes the first n (a pilot, never a full score)."""
    if split not in SPLITS:
        raise ValueError(f"unknown split {split!r}; the splits are {', '.join(SPLITS)}")
    d = ensure(base) / "data" / split
    files = sorted(d.glob("*.json"))
    if limit is not None:
        files = files[: max(0, int(limit))]
    out = []
    for f in files:
        task = json.loads(f.read_text(encoding="utf-8"))
        task["id"] = f.stem
        out.append(task)
    return out


def count(split: str, base: Path | None = None) -> int:
    d = (Path(base) if base else root()) / "data" / split
    return len(list(d.glob("*.json"))) if d.is_dir() else 0


def grid_text(grid: list[list[int]]) -> str:
    """A grid as ``rows x cols:row/row/...``; every row's digits 0-9, no spaces."""
    if not grid or not grid[0]:
        return "0x0:"
    return f"{len(grid)}x{len(grid[0])}:" + "/".join("".join(str(int(c)) for c in row) for row in grid)


def _rows_of(text: str, shape: tuple[int, int] | None = None) -> list[list[int]] | None:
    """Digits and slashes (or whitespace) to a grid; without slashes, `shape` chunks the digits."""
    cleaned = re.sub(r"\s+", "", text)
    if not cleaned or not re.fullmatch(r"[0-9/]+", cleaned):
        return None
    rows = cleaned.split("/") if "/" in cleaned else None
    if rows is None:
        if shape is None:
            return None
        r, c = shape
        if len(cleaned) != r * c:
            return None
        rows = [cleaned[i * c : (i + 1) * c] for i in range(r)]
    if not rows or any(not row or not row.isdigit() for row in rows):
        return None
    width = len(rows[0])
    if any(len(row) != width for row in rows):
        return None
    grid = [[int(ch) for ch in row] for row in rows]
    if shape is not None and (len(grid), len(grid[0])) != shape:
        return None
    return grid


def parse_grid(text: str, shape: tuple[int, int] | None = None) -> tuple[list[list[int]] | None, bool]:
    """The last output grid in a model's text, or ``(None, False)``.

    A headed grid (``3x3:010/...``) is preferred, the last one in the text, so an answer that repeats
    the prompt still reads its own output. Without a header, a bare run of rows is taken, and a bare
    run of digits is cut by ``shape`` when the caller knows the expected size."""
    if not text:
        return None, False
    headed = list(_HEADER.finditer(text))
    if headed:
        # prefer a grid of the expected shape; otherwise the last one the model wrote
        candidates = []
        for m in headed:
            grid = _rows_of(m.group("rows"), (int(m.group("r")), int(m.group("c"))))
            if grid is not None:
                candidates.append(grid)
        if shape is not None:
            for g in reversed(candidates):
                if (len(g), len(g[0])) == shape:
                    return g, True
        if candidates:
            return candidates[-1], True
    tail = text.rsplit("output", 1)[-1] if "output" in text.lower() else text
    bare = list(_BARE.finditer(tail))
    if bare:
        grid = _rows_of(bare[-1].group("rows"), shape)
        if grid is not None:
            return grid, True
    return None, False


THINK_OPEN, THINK_CLOSE = "<think>", "</think>"


def answer_text(text: str, opened: bool = False) -> str | None:
    """The answer in a model's output: what follows its thinking, or None when the thinking never ended.

    A thinking model writes ``<think>...</think>`` and then its answer. A grid quoted inside the
    thinking is not an answer, so only the text after the last ``</think>`` is read. Thinking that
    was opened (in the output, or by the prompt: `opened`) and never closed ran out of tokens before
    any answer: None, which the scorer counts as no grid written. Text with no thinking is the answer."""
    if not text:
        return None if opened else text
    if THINK_CLOSE in text:
        return text.rsplit(THINK_CLOSE, 1)[1]
    if opened or THINK_OPEN in text:
        return None
    return text


THINKING_MARK = "@thinking"


def reading_name(model: str, thinking: str | None = None) -> str:
    """The store name of a model's ARC reading: ``arc-<model>``, or ``arc-<model>@thinking`` when it
    was read with thinking on, so the two readings of one model sit side by side."""
    return f"arc-{model}" + (THINKING_MARK if thinking == "on" else "")


def task_prompt(task: dict, pairs: int = 3) -> str:
    """The text form of a task: examples, then the test input and an open ``output``."""
    task = task if isinstance(task, dict) else json.loads(task)
    train = list(task.get("train") or [])[: max(0, int(pairs))]
    test = (task.get("test") or [{}])[0]
    lines = [
        "ARC-AGI-2",
        "Each grid is written rows x cols:row/row/..., each row's digits 0-9.",
        "Find the rule in the examples and write only the test output grid in the same form.",
    ]
    for i, pair in enumerate(train, 1):
        lines.append(
            f"Example {i}: input {grid_text(pair['input'])} -> output {grid_text(pair['output'])}"
        )
    lines.append(f"Test: input {grid_text(test.get('input') or [])} -> output")
    return "\n".join(lines)


def fits(task: dict, tokeniser, context: int, max_output: int, pairs: int = 3) -> tuple[str | None, int]:
    """The longest example prefix whose prompt plus the output budget fits the context.

    Returns ``(prompt, pairs_used)``; when not even the empty-example prompt fits, ``(None, 0)``."""
    train = list(task.get("train") or [])
    for n in range(min(pairs, len(train)), -1, -1):
        prompt = task_prompt(task, n)
        if len(tokeniser.encode(prompt)) + max_output <= context:
            return prompt, n
    return None, 0


def expected(task: dict) -> list[list[int]]:
    return (task.get("test") or [{}])[0].get("output") or []


def exact(predicted: list[list[int]] | None, want: list[list[int]]) -> bool:
    return predicted is not None and predicted == want


def cell_accuracy(predicted: list[list[int]] | None, want: list[list[int]]) -> float:
    """The share of cells right, 0 when the shapes differ (a shape miss is not partial credit)."""
    if not predicted or not want or len(predicted) != len(want) or len(predicted[0]) != len(want[0]):
        return 0.0
    total = sum(len(row) for row in want)
    right = sum(1 for pr, wr in zip(predicted, want, strict=False) for a, b in zip(pr, wr, strict=False) if a == b)
    return right / total if total else 0.0


def shape_of(task: dict) -> tuple[int, int]:
    want = expected(task)
    return (len(want), len(want[0]) if want else 0)


def summary(rows: list[dict]) -> dict:
    """The metrics of a list of per-task results (exact, pass@2, format, cell accuracy)."""
    n = len(rows)
    if not n:
        return {"tasks": 0, "solved": 0, "pass@1": 0.0, "pass@2": 0.0, "format_rate": 0.0, "cell_accuracy": 0.0}
    return {
        "tasks": n,
        "solved": sum(1 for r in rows if r.get("exact")),
        "pass@1": sum(1 for r in rows if r.get("exact")) / n,
        "pass@2": sum(1 for r in rows if r.get("exact") or r.get("exact2")) / n,
        "format_rate": sum(1 for r in rows if r.get("parsed")) / n,
        "cell_accuracy": sum(float(r.get("cell_accuracy") or 0.0) for r in rows) / n,
    }


def published_path() -> Path:
    """The published ARC-AGI-2 scores file (hand-curated from the ARC Prize/leaderboard sources)."""
    return paths.resolve("data/arc-agi-2/published.json")


def published() -> dict[str, dict]:
    p = published_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}

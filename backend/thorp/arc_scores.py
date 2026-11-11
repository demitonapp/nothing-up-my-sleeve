"""The ARC-AGI-2 scores already published for the leaderboard's models (11 November, Justin).

ARC-AGI-2 is the canonical intelligence test (thorp/arc.py). A score is a model-level **pass@2** on
the 120-task evaluation set, as the ARC Prize leaderboard and its aggregators report it. These are
not our measurements: they are kept apart from the readings we run, with their source and date, so
the leaderboard can show the canonical ranking without pretending a pilot is a published score.

Only the models with a published ARC-AGI-2 score are here. Everything else on the board is "not
run" (a chaining competitor with no ARC reading) or "no published score" (a candidate the ARC
leaderboard has not measured). The sources are the public leaderboards; the score is the headline
number, not a re-derivation.
"""

from __future__ import annotations

BENCHGECKO = "https://benchgecko.ai/benchmark/arc-agi-2"
ARC_PRIZE = "https://arcprize.org/leaderboard"

# model id -> the published reading. `score` is ARC-AGI-2 pass@2 on the 120-task evaluation set.
PUBLISHED: dict[str, dict] = {
    "mlx-community/Qwen3.8-27B-4bit": {
        "label": "Qwen3.8 27B",
        "score": 42.4,
        "date": "2026-10-17",
        "source": "BenchGecko ARC-AGI-2 (rank 41 of 88)",
        "url": BENCHGECKO,
    },
    "deepseek-ai/DeepSeek-V4.1-Flash-1017": {
        "label": "DeepSeek V4.1 Flash 1017",
        "score": 78.1,
        "date": "2026-10-17",
        "source": "BenchGecko ARC-AGI-2 (rank 17 of 88)",
        "url": BENCHGECKO,
    },
    "moonshotai/Kimi-K3": {
        "label": "Kimi K3",
        "score": 60.4,
        "date": "2026-10-17",
        "source": "BenchGecko ARC-AGI-2 (rank 32 of 88)",
        "url": BENCHGECKO,
    },
}

ABOUT = (
    "ARC-AGI-2 is the canonical intelligence ranking: each task gives a few input/output grids and "
    "asks for the output of a new input, with no language or domain knowledge to memorise. The score "
    "is pass@2 on the 120-task evaluation set. It is not comparable with the chaining lift: the "
    "chaining tests measure one skill on text, ARC-AGI-2 measures fluid intelligence on grids."
)


def for_model(model: str) -> dict | None:
    """The published ARC-AGI-2 reading for a model, or None."""
    r = PUBLISHED.get(model)
    return {**r, "kind": "published"} if r else None


def _reading_row(model: str, reading: dict) -> dict | None:
    """One stored ARC reading as a board row, or None when it holds no score."""
    score = reading.get("pass@2")
    if score is None:
        return None
    tasks = reading.get("tasks")
    if isinstance(tasks, list):
        tasks = len(tasks)
    if not isinstance(tasks, int) or tasks <= 0:
        tasks = int(reading.get("limit") or 0)
    thinking = reading.get("thinking")  # "on", "off", or None: no switch, or read before it was kept
    caps = [f"{reading.get('max_output')}-token cap"] if reading.get("max_output") else []
    if thinking == "on" and reading.get("max_thinking"):
        caps.append(f"{reading.get('max_thinking')} to think")
    return {
        "label": model.split("/")[-1],
        "model": model,
        "score": 100.0 * float(score),  # the store keeps a share; the board shows per cent, as published
        "pass@1": reading.get("pass@1"),
        "cell_accuracy": reading.get("cell_accuracy"),
        "format_rate": reading.get("format_rate"),
        "tasks": int(tasks) if tasks else 0,
        "pilot": bool(reading.get("pilot")),
        "mode": reading.get("mode"),
        "thinking": thinking,
        "thinking_unfinished": reading.get("thinking_unfinished"),
        "scored": reading.get("scored"),
        "kind": "measured",
        "max_output": reading.get("max_output"),
        "source": (f"our reading, {int(tasks) if tasks else 0}-task pilot" + "".join(f", {c}" for c in caps))
        if reading.get("pilot")
        else "our reading, 120-task set",
    }


def measured_rows() -> list[dict]:
    """Every ARC-AGI-2 reading we ran ourselves (s4.outside_readings `arc-*`), biggest first.

    A model read with thinking on and with it off has two rows (`arc-<model>` and
    `arc-<model>@thinking`; scripts/score_arc.py). These are pilots unless the reading's `limit` is
    120; the task count and the pilot flag stay on the row so a pilot is never read as a published
    score."""
    from thorp.viable.s4_intelligence import readings

    out: list[dict] = []
    try:
        for name, reading in readings.glob("arc-*"):
            kind, model = readings.kind_of(name)
            if kind != "arc" or not model or not isinstance(reading, dict):
                continue
            row = _reading_row(model, reading)
            if row:
                out.append(row)
    except Exception:  # noqa: BLE001 - the board still renders if the store is unreadable
        return out
    return sorted(
        out,
        key=lambda r: (-float(r["score"]), -float(r.get("cell_accuracy") or 0.0), r["label"], r["thinking"] or ""),
    )


def measured() -> dict[str, dict]:
    """Each model's best measured reading, keyed by model: the higher score, then the larger task set."""
    out: dict[str, dict] = {}
    for row in measured_rows():
        held = out.get(row["model"])
        if held is None or (row["score"], row["tasks"]) > (held["score"], held["tasks"]):
            out[row["model"]] = row
    return out


def rows() -> list[dict]:
    """Published readings, biggest first, each with its label and source."""
    return sorted(
        ({"model": m, **v} for m, v in PUBLISHED.items()),
        key=lambda r: -float(r["score"]),
    )


def of(model: str) -> float | None:
    r = PUBLISHED.get(model)
    return float(r["score"]) if r else None

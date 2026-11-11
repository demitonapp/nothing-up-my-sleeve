"""A voyage's milestones: the checks it must pass on the way, and what happens when one is missed
(12 November, Justin: "for every voyage we need to have milestones and based on those milestones being
met or not met, then we can then call the ship back and then from there we can decide on whether to
relaunch the ship's mission with revised parameters").

A milestone is a spec field, judged **once**, at the first evaluation at or after the step it names:

    milestones:
      - at: 0.25                  # a share of the voyage, or `step: 3200` instead
        metric: stars/previous_word/max_score
        at_least: 0.5             # and/or `at_most:`
        if_missed: recall         # recall (the default) calls the voyage back; warn records it
        why: the previous-word card must be lit by the quarter mark

Why a milestone is judged once: it is a gate, not a monitor. A card that lights late does not retroactively
pass the quarter mark — the point is whether the voyage is on track at that checkpoint. Trends are what the
readings and the charts are for.

A verdict is written to the ledger as two metrics (`milestone/<n>/value`, `milestone/<n>/met`) and an
artifact (`milestone`, the JSON), so it reads like any other number: `thorp milestones`. A recall stops the
voyage at that checkpoint, keeps it, and writes the run's status as `recalled: <reason>` — the queue takes
the next line, and a revised spec can be written from the numbers rather than from memory.

The verdict is `unknown` when the milestone's metric was not produced by this evaluation (a light eval runs
only some evaluators): it stays unjudged and is checked again at the next one.
"""

from __future__ import annotations


def declared(spec: dict, total: int) -> list[dict]:
    """The spec's milestones, normalised: `n` (1-based, the name the ledger records), `step`, the metric
    and its bound, what to do when missed, and the words."""
    out: list[dict] = []
    for i, m in enumerate(spec.get("milestones") or [], 1):
        if not isinstance(m, dict) or not m.get("metric"):
            continue
        if m.get("step") is not None:
            step = int(m["step"])
        elif m.get("at") is not None:
            step = int(round(float(m["at"]) * max(1, total)))
        else:
            continue
        out.append(
            {
                "n": i,
                "step": step,
                "metric": str(m["metric"]),
                "at_least": None if m.get("at_least") is None else float(m["at_least"]),
                "at_most": None if m.get("at_most") is None else float(m["at_most"]),
                "if_missed": str(m.get("if_missed") or "recall").strip().lower(),
                "why": str(m.get("why") or ""),
            }
        )
    return out


def judge(m: dict, metrics: dict) -> tuple[str, float | None]:
    """`met`, `missed` or `unknown` (the metric was not read at this evaluation), and its value."""
    if m["metric"] not in metrics:
        return "unknown", None
    try:
        v = float(metrics[m["metric"]])
    except (TypeError, ValueError):
        return "unknown", None
    if m["at_least"] is not None and v < m["at_least"]:
        return "missed", v
    if m["at_most"] is not None and v > m["at_most"]:
        return "missed", v
    return "met", v


def due(ms: list[dict], step: int, judged: set[int]) -> list[dict]:
    """The milestones reached at or before `step` and not yet judged."""
    return [m for m in ms if m["step"] <= step and m["n"] not in judged]


def check(ms: list[dict], step: int, metrics: dict, judged: set[int]) -> list[dict]:
    """Judge every due milestone this evaluation can read; mark them judged. Returns the verdicts."""
    out: list[dict] = []
    for m in due(ms, step, judged):
        verdict, value = judge(m, metrics)
        if verdict == "unknown":
            continue  # a light eval did not read it: wait for the next one
        judged.add(m["n"])
        out.append({**m, "verdict": verdict, "value": value, "judged_at": step})
    return out


def recall_reason(verdicts: list[dict]) -> str | None:
    """The first missed milestone that asks for a recall, as the words the run's status carries."""
    for v in verdicts:
        if v["verdict"] != "missed" or v["if_missed"] != "recall":
            continue
        bound = (
            f">= {v['at_least']:g}" if v["at_least"] is not None else f"<= {v['at_most']:g}"
        )
        return (
            f"milestone {v['n']} missed at step {v['judged_at']}: "
            f"{v['metric']} {v['value']:.4g} (wanted {bound})"
            + (f" — {v['why']}" if v["why"] else "")
        )
    return None


def record(verdicts: list[dict], rid: str, rec, log) -> None:
    """Write each verdict as the ledger reads it: a value and a met flag per milestone, and the JSON."""
    import json

    if not verdicts:
        return
    vals: dict[str, float] = {}
    for v in verdicts:
        vals[f"milestone/{v['n']}/value"] = float(v["value"])
        vals[f"milestone/{v['n']}/met"] = 1.0 if v["verdict"] == "met" else 0.0
    rec.metrics(rid, verdicts[0]["judged_at"], vals)
    rec.artifact(
        rid,
        verdicts[0]["judged_at"],
        "milestone",
        "",
        "",
        json.dumps(
            [
                {
                    "n": v["n"],
                    "metric": v["metric"],
                    "value": v["value"],
                    "at_least": v["at_least"],
                    "at_most": v["at_most"],
                    "verdict": v["verdict"],
                    "if_missed": v["if_missed"],
                    "why": v["why"],
                }
                for v in verdicts
            ],
            indent=1,
        ),
    )
    for v in verdicts:
        log(
            f"milestone {v['n']} ({v['metric']}): {v['verdict']} at {v['value']:.4g}"
            + (f" — {v['why']}" if v["why"] else "")
        )

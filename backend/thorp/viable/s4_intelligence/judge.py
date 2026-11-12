"""S4's judge: what a number cannot say (12 November, Justin: "let's lock in the decision to use Qwen 3.8 27B").

Measurement is code (s4_intelligence/hires.py). The judge is S5's chosen model (s5.judges; the latest row is in
force, today `qwen3.8-27b`, run on this Mac through `mlx_lm generate` with the prompt on stdin), and it is asked
only what code cannot read off the records. Today that is one question: **why did this fit-out die?** It is
handed the hire's timing, step by step, and the end of the charter's own log for that hire, and must answer in
one JSON object: the cause, the step, whose fault (the box, the network, the cargo, our code, unknown), how sure,
and what to do. It proposes; nothing here acts on what it says.

Where a person already wrote the cause down (a ship released by hand on 9 November carries its `why`), that is
kept beside the verdict (`known`), and is **not** shown to the judge: those hires are how the judge itself is
judged.

It is a 15 GB model on a 32 GB Mac that is usually training. `can_run` says no while anything larger than a 1m
is at sea here (a 21m alone takes 24.7 GB); the verdict then waits for the next cycle.

    python -m thorp.viable.s4_intelligence.judge            # the failed fit-outs not yet judged
    python -m thorp.viable.s4_intelligence.judge --ask 3    # judge up to three of them now
"""

from __future__ import annotations

import contextlib
import json
import re
import subprocess
import time

from thorp import paths

LOG_LINES = 70  # the end of the hire's log the judge reads
LOG_CHARS = 7000
MAX_SECONDS = 900.0
SMALL = ("300k", "1m")  # what may be at sea on this Mac while the judge is loaded
CLASSES = ("box", "network", "cargo", "our code", "unknown")

ASK = """You are reading the log of a rented GPU that was released before its training run started.
Say why the fit-out failed. Use only what the timing and the log show; if they do not show the cause, say unknown.

The steps of a fit-out, in order: provision (the machine is created), ssh (waiting for it to answer), code (our
code is copied up), data (the training data is copied up), board (the manifest and the run's papers), env (the
Python environment is synced), then training.

The hire: {gpu} at ${dph:.3f} an hour, voyage {name}, released after {minutes:.1f} minutes, status "{status}".
Seconds spent in each step: {phases}
Megabytes carried: {mb}

The end of the charter's log for this hire:
---
{log}
---

Answer with one JSON object and nothing else:
{{"cause": "<one sentence>", "step": "<provision|ssh|code|data|board|env|unknown>", "fault": "<box|network|cargo|our code|unknown>", "confidence": "<low|medium|high>", "do": "<one sentence: what should change>"}}
"""


def log_of(instance, lines: list[str] | None = None) -> str:
    """The end of the charter log's block for this hire (from its quote to the next hire's quote)."""
    if lines is None:
        try:
            lines = (paths.data_dir() / "runs" / "charter.log").read_text(errors="ignore").splitlines()
        except OSError:
            return ""
    hit = next((i for i, ln in enumerate(lines) if f"instance {instance} " in ln or f"instance {instance}:" in ln), None)
    if hit is None:
        return ""
    is_offer = lambda ln: " offer " in ln and "/h" in ln and "charter:" in ln  # noqa: E731
    start = next((i for i in range(hit, -1, -1) if is_offer(lines[i])), max(0, hit - 5))
    end = next((i for i in range(hit + 1, len(lines)) if is_offer(lines[i])), len(lines))
    return "\n".join(lines[start:end][-LOG_LINES:])[-LOG_CHARS:]


def cases(rows: list[dict] | None = None, judged: set[str] | None = None) -> list[dict]:
    """The failed fit-outs with something to read, newest first; `judged` are the instances already answered."""
    from thorp.viable.s4_intelligence import hires

    rows = hires.timings() if rows is None else rows
    judged = already() if judged is None else judged
    out = []
    for r in reversed(rows):
        if r["kind"] != "voyage" or r["sailed"] or r["total_s"] < hires.MIN_FAILED_S:
            continue
        log = log_of(r["instance"])
        out.append({**r, "log": log, "judged": str(r["instance"]) in judged, "readable": bool(log)})
    return out


def prompt(case: dict) -> str:
    ph = case.get("phases") or {}
    return ASK.format(
        gpu=case.get("gpu") or "a GPU", dph=float(case.get("dph") or 0.0), name=case.get("name") or "unnamed",
        minutes=case["total_s"] / 60, status=case.get("status") or "released",
        phases=", ".join(f"{k} {float(v):.0f}" for k, v in ph.items()) or "not recorded",
        mb=", ".join(f"{k} {float(v):.0f}" for k, v in (case.get("mb") or {}).items()) or "not recorded",
        log=case.get("log") or "(no log kept for this hire)",
    )  # fmt: skip


def read(said: str) -> dict | None:
    """The verdict out of all the model said: its thinking and the runner's own lines are dropped, and the last
    JSON object that names a cause is the answer. None when there is none."""
    text = re.sub(r"<think>.*?</think>", "", said or "", flags=re.S)
    parts = text.split("==========")  # mlx_lm prints the answer between two rules, its statistics after
    if len(parts) >= 3:
        text = parts[1]
    for m in reversed(list(re.finditer(r"\{[^{}]*\}", text, flags=re.S))):
        with contextlib.suppress(ValueError):
            v = json.loads(m.group(0))
            if isinstance(v, dict) and v.get("cause"):
                fault = str(v.get("fault") or "unknown").strip().lower()
                return {"cause": str(v["cause"]).strip(), "step": str(v.get("step") or "unknown").strip().lower(),
                        "fault": fault if fault in CLASSES else "unknown",
                        "confidence": str(v.get("confidence") or "low").strip().lower(), "do": str(v.get("do") or "").strip()}  # fmt: skip
    return None


def chosen() -> dict | None:
    """S5's judge in force, or None."""
    from thorp.viable.s2_coordination import schedule

    j = schedule.judge()
    if j is None:
        return None
    return {"name": j.name, "command": list(j.command), "words": j.words,
            "set_at": j.set_at.isoformat(timespec="minutes") if j.set_at else None}  # fmt: skip


def can_run() -> tuple[bool, str]:
    """Whether the judge may be loaded now, and why not."""
    if chosen() is None:
        return False, "no judge chosen (s5.judges; thorp schedule judge)"
    with contextlib.suppress(Exception):
        from thorp.viable.s2_coordination import lanes, queue_store

        for r in queue_store.at_sea():
            if r.get("lane") != "mac" or r.get("kind") != "spec":
                continue
            preset = lanes.preset_of(lanes.parse(r["text"]))
            if preset not in SMALL:
                return False, f"{r.get('name')} ({preset}) is at sea on this Mac: the judge waits for a smaller harbour"
    return True, ""


def ask(text: str, judge: dict | None = None, runner=subprocess.run, timeout: float = MAX_SECONDS) -> tuple[str, str, float]:
    """Put the prompt to the judge. Returns (outcome, all it said, seconds); never raises."""
    judge = judge or chosen()
    if judge is None:
        return "failed", "no judge chosen", 0.0
    t0 = time.time()
    try:
        r = runner(judge["command"], input=text, cwd=str(paths.ROOT), capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return "timeout", f"(stopped after {timeout:.0f} s)", time.time() - t0
    except OSError as e:
        return "failed", f"the judge's command could not be started: {e}", time.time() - t0
    said = r.stdout or ""
    if r.returncode != 0:
        return "failed", (said + "\n" + (r.stderr or ""))[-4000:], time.time() - t0
    return "ok", said, time.time() - t0


def already() -> set[str]:
    """The instances the judge has answered readably."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import Judgment

    with contextlib.suppress(Exception), store.session() as s:
        return {r.subject for r in s.scalars(select(Judgment).where(Judgment.kind == "fitout", Judgment.outcome == "ok"))}
    return set()


def keep(judge: str, case: dict, outcome: str, verdict: dict | None, said: str, seconds: float) -> None:
    from thorp import store
    from thorp.viable.records import Judgment

    with store.session() as s:
        s.add(Judgment(judge=judge, kind="fitout", subject=str(case["instance"]), known=case.get("why"),
                       verdict={**(verdict or {}), "name": case.get("name"), "gpu": case.get("gpu"),
                                "minutes": round(case["total_s"] / 60, 1), "failed_in": case.get("failed_in")},
                       said=(said or "")[-8000:], seconds=seconds, outcome=outcome))  # fmt: skip


def judgments(limit: int = 12) -> list[dict]:
    """The latest judgments, newest first."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import Judgment

    with store.session() as s:
        return [{"id": r.id, "at": r.at.isoformat(timespec="minutes"), "judge": r.judge, "kind": r.kind,
                 "subject": r.subject, "known": r.known, "verdict": r.verdict, "seconds": r.seconds, "outcome": r.outcome}
                for r in s.scalars(select(Judgment).order_by(Judgment.id.desc()).limit(limit))]  # fmt: skip


def judge_failures(limit: int = 3, runner=subprocess.run, log=print, force: bool = False) -> list[dict]:
    """Ask the judge about the failed fit-outs it has not answered, up to `limit`. Each answer is kept."""
    ok, why = can_run()
    if not ok and not force:
        log(f"S4 judge: not asked ({why})")
        return [{"outcome": "deferred", "why": why}]
    judge = chosen()
    out = []
    for case in [c for c in cases() if c["readable"] and not c["judged"]][:limit]:
        log(f"S4 judge: asking {judge['name']} why instance {case['instance']} ({case.get('name')}) never sailed")
        outcome, said, seconds = ask(prompt(case), judge, runner)
        verdict = read(said) if outcome == "ok" else None
        if outcome == "ok" and verdict is None:
            outcome = "unreadable"
        with contextlib.suppress(Exception):
            keep(judge["name"], case, outcome, verdict, said, seconds)
        out.append({"instance": case["instance"], "name": case.get("name"), "known": case.get("why"),
                    "outcome": outcome, "verdict": verdict, "seconds": round(seconds, 1)})  # fmt: skip
        log(f"S4 judge: {outcome} in {seconds:.0f} s" + (f": {verdict['cause']}" if verdict else ""))
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="judge", description=__doc__.split("\n\n")[0])
    ap.add_argument("--ask", type=int, default=0, metavar="N", help="judge up to N failed fit-outs now")
    ap.add_argument("--force", action="store_true", help="ask even while a large voyage is at sea here")
    ap.add_argument("--prompt", metavar="INSTANCE", help="print the prompt this hire would be judged on")
    a = ap.parse_args(argv)
    cs = cases()
    if a.prompt:
        c = next((c for c in cs if str(c["instance"]) == a.prompt), None)
        print(prompt(c) if c else f"no failed fit-out {a.prompt}")
        return 0
    if a.ask:
        judge_failures(a.ask, force=a.force)
        return 0
    j = chosen()
    print(f"judge: {j['name'] if j else 'none chosen'}; may run now: {can_run()}")
    for c in cs:
        print(f"{c['instance']:>10} {str(c['gpu'])[:9]:9} {str(c['name'])[:28]:28} {c['total_s'] / 60:5.1f} min  "
              f"{'judged' if c['judged'] else ('to judge' if c['readable'] else 'no log kept'):11} known: {c.get('why') or '-'}")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

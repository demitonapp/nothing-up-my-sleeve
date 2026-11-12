"""S3*: the last cycle's plan against what happened (12 November, Justin: "talk me through the auditor").

The charter audit (s3star_audit/charter.py) asks whether anything hired was forgotten. This asks the other
question an auditor is for: were the numbers the plan was made on true? Independent of the purser's own claims,
it reads the records and sets, for the window it is given:

- each **hire**'s quote against its bill: the hours and dollars quoted when it was hired (S3's spend log), and
  what it took; the set-up the quote assumed against the set-up measured (S4's hires.timings);
- the **queue's clock** against the Mac: the minutes the purser planned a voyage on here (s3.allocations) against
  the minutes its run took (the ledger);
- the **last plan** against the queue: each voyage the last cycle called foreign, and where it is now.

It changes nothing and proposes nothing: it writes what it found, in numbers and in words, and S4 and the purser
read it. A hire's cause of death is not its business either: that is the judge's (s4_intelligence/judge.py).
"""

from __future__ import annotations

import contextlib
from datetime import datetime

OVER = 1.25  # a quote or a clock out by more than a quarter is a finding
STOPPED_S = 300.0  # as S4 counts them (hires.MIN_FAILED_S)


def _ts(at) -> float | None:
    with contextlib.suppress(Exception):
        return datetime.fromisoformat(str(at)).timestamp()
    with contextlib.suppress(Exception):
        return float(at)
    return None


def hires_against_quotes(rows: list[dict], since: float, until: float) -> list[dict]:
    """Each voyage hire released in the window: quoted hours and dollars against what it took."""
    out = []
    for r in rows:
        if r["kind"] != "voyage" or not (since <= r["ended"] < until):
            continue
        if not r["sailed"] and r["total_s"] < STOPPED_S:
            continue  # stopped by hand inside five minutes: not a fit-out that failed
        hours = r["total_s"] / 3600
        qh, q = r.get("quote_hours"), r.get("quote")
        overhead = None if r["setup_s"] is None else (float(r["setup_s"]) + float(r["home_s"] or 0.0)) / 60
        out.append({
            "instance": r["instance"], "name": r["name"], "gpu": r["gpu"], "status": r["status"], "why": r.get("why"),
            "sailed": r["sailed"], "failed_in": r["failed_in"],
            "quote_hours": qh, "hours": hours, "hours_ratio": hours / float(qh) if qh and r["sailed"] else None,
            "quote": q, "cost": r["cost"], "cost_ratio": float(r["cost"]) / float(q) if q and r["cost"] is not None else None,
            "setup_assumed_min": None if r.get("setup_assumed_h") is None else 60 * float(r["setup_assumed_h"]),
            "overhead_min": overhead, "train_min": None if r["train_s"] is None else float(r["train_s"]) / 60,
            "source": r["source"],
        })  # fmt: skip
    return out


def clock_against_runs(calls: dict[str, dict], runs: list[dict], since: float, until: float) -> list[dict]:
    """Each voyage that finished here in the window and that the purser had planned: its planned minutes on this
    Mac against the minutes it took. `calls` is the purser's latest call by voyage name."""
    out = []
    for r in runs:
        done = _ts(r.get("finished"))
        if done is None or not (since <= done < until) or not r.get("wall_minutes"):
            continue
        c = calls.get(r.get("name") or "")
        if not c or not c.get("local_min"):
            continue
        took, planned = float(r["wall_minutes"]), float(c["local_min"])
        out.append({"name": r["name"], "planned_min": planned, "took_min": took, "ratio": took / planned})
    return out


def plan_against_queue(prev_plan: dict | None, queued: set[str], at_sea: set[str], status_of) -> list[dict]:
    """Each voyage the last cycle called foreign, and where it is now."""
    out = []
    for c in (prev_plan or {}).get("abroad") or []:
        name = c.get("name") if isinstance(c, dict) else c
        if not name:
            continue
        if name in at_sea:
            now = "at sea"
        elif name in queued:
            now = "still queued"
        else:
            now = status_of(name) or "gone from the queue, never sailed"
        out.append({"name": name, "gpu": c.get("gpu") if isinstance(c, dict) else None, "now": now})
    return out


def findings(hires: list[dict], clock: list[dict], planned: list[dict]) -> list[str]:
    """What the numbers say, in words, worst first."""
    out = []
    failed = [h for h in hires if not h["sailed"]]
    if failed:
        cost = sum(float(h["cost"] or 0) for h in failed)
        mins = sum(h["hours"] * 60 for h in failed)
        out.append(f"{len(failed)} hire(s) never sailed: {mins:.0f} minutes and ${cost:.2f} for no training "
                   f"({'; '.join(sorted({str(h['why'] or h['status'] or 'no reason kept') for h in failed}))})")  # fmt: skip
    for h in hires:
        if h["sailed"] and h["hours_ratio"] and h["hours_ratio"] > OVER:
            money = f"; ${float(h['quote']):.2f} quoted, ${float(h['cost']):.2f} billed" if h["quote"] and h["cost"] is not None else ""
            out.append(f"{h['name']} on an {h['gpu']} was quoted {float(h['quote_hours']):.2f} h and took {h['hours']:.2f} h "
                       f"({h['hours_ratio']:.1f} times){money}")  # fmt: skip
        if h["sailed"] and h["overhead_min"] is not None and h["setup_assumed_min"] and h["overhead_min"] > OVER * h["setup_assumed_min"]:
            out.append(f"{h['name']}: set-up and home were planned at {h['setup_assumed_min']:.0f} min and took {h['overhead_min']:.0f} min")
    slow = [c for c in clock if c["ratio"] > OVER]
    if slow:
        worst = max(slow, key=lambda c: c["ratio"])
        out.append(f"{len(slow)} of {len(clock)} voyage(s) here ran more than a quarter over the queue's clock; the worst, "
                   f"{worst['name']}, was planned at {worst['planned_min']:.0f} min and took {worst['took_min']:.0f}")  # fmt: skip
    stuck = [p for p in planned if p["now"] == "still queued"]
    if stuck:
        out.append(f"{len(stuck)} voyage(s) the last cycle called foreign are still queued: {', '.join(p['name'] for p in stuck[:6])}")
    return out


def review(since: float, until: float, prev_plan: dict | None = None) -> dict:
    """The window's audit, read from the records now."""
    from thorp.ledger import reader
    from thorp.viable.s2_coordination import lanes, queue_store
    from thorp.viable.s3_control import purser
    from thorp.viable.s4_intelligence import hires as s4

    rows = s4.timings()
    hs = hires_against_quotes(rows, since, until)
    calls: dict[str, dict] = {}
    with contextlib.suppress(Exception):
        calls = {c["name"]: c for c in purser.latest().values() if c.get("name")}
    runs: list[dict] = []
    with contextlib.suppress(Exception):
        runs = reader().query("select name, status, wall_minutes, finished, spec_json from s1.runs where status = 'finished'")
        runs = [r for r in runs if '"torch"' not in str(r.get("spec_json") or "")]  # the Mac's own voyages
    clock = clock_against_runs(calls, runs, since, until)
    queued: set[str] = set()
    sea: set[str] = set()
    with contextlib.suppress(Exception):
        queued = {n for n in (lanes.parse(t).name for t in queue_store.pending_texts()) if n}
        sea = {r["name"] for r in queue_store.at_sea() if r.get("name")}

    def status_of(name: str) -> str | None:
        with contextlib.suppress(Exception):
            got = reader().query("select status from s1.runs where name = ? order by started desc limit 1", [name])
            return got[0]["status"] if got else None
        return None

    planned = plan_against_queue(prev_plan, queued, sea, status_of)
    return {
        "since": since, "until": until, "hires": hs, "clock": clock, "planned": planned,
        "spend": sum(float(h["cost"] or 0) for h in hs),
        "wasted": sum(float(h["cost"] or 0) for h in hs if not h["sailed"]),
        "findings": findings(hs, clock, planned),
    }  # fmt: skip

"""The Cost tab (/settings/cost; 12 November, Justin: "can you add a cost tab here /settings"; "by hour, by day,
by week, by month").

The money Thorp spends is the GPUs it hires from Vast.ai: S3's spend log (s3.spend_events) holds a `hired` line
and a `released` line for every one, with the dollars an hour and what it cost. This module turns the log into
spend over time:

- **A hire's cost is spread over the time it was hired**, at its own rate, so a hire that ran from 23:40 to
  01:10 is charged to both days in proportion. A ship still out is charged up to now, at its rate. A hire
  released by hand (9 November) left only its words: its end is the release's time.
- **Each hire is one of three kinds**: a voyage that trained (it reached the sea and trained for more than ten
  minutes), one that never trained (a box that died fitting out, a voyage that sank in its first minutes, a
  hire recalled), and a smoke test (the GPU checks, `smoke-*`).
- **The buckets** are hours, days and months of this Mac's own clock, and weeks of the budget's own clock
  (Monday 00:00 UTC to Sunday, as S5's `weekly_budget` and S3's `week_spent` count them), so a week's bar is
  the same number the budget is held to.

This Mac's own electricity is not measured and not here; nor is anything paid outside the spend log.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

BYS = {
    # by: (how many buckets back, what a bucket is)
    "hour": (48, "the last 48 hours, this Mac's clock"),
    "day": (30, "the last 30 days, this Mac's clock"),
    "week": (12, "the last 12 weeks, Monday to Sunday UTC as the budget counts them"),
    "month": (12, "the last 12 months, this Mac's clock"),
}
KINDS = ("trained", "never_trained", "smoke")
TRAINED_S = 600.0  # a voyage that trained less than this after reaching the sea never really trained


def _ts(at) -> float | None:
    try:
        return datetime.fromisoformat(str(at)).timestamp()
    except (TypeError, ValueError):
        return None


def hires(log: list[dict], now: float) -> list[dict]:
    """One row a hire: {instance, name, gpu, kind, start, end, dph, cost, out}. The cost is the spend log's
    where it has one, else the hire's rate over its time."""
    hired = {r["instance"]: r for r in log if r.get("event") == "hired" and r.get("instance") is not None}
    released = {r["instance"]: r for r in log if r.get("event") == "released" and r.get("instance") is not None}
    seas = {r["instance"]: r for r in log if r.get("event") == "at sea" and r.get("instance") is not None}
    out = []
    for inst in dict.fromkeys(list(hired) + list(released)):
        h, r = hired.get(inst) or {}, released.get(inst)
        start = h.get("started") or (r or {}).get("started")
        if not start:
            continue
        start = float(start)
        if r is None:
            end, still = now, True
        else:
            end, still = float(r.get("ended") or _ts(r.get("at")) or start), False
        end = max(start, end)
        dph = float(h.get("dph") or (r or {}).get("dph") or 0.0)
        cost = float(r["cost"]) if r is not None and r.get("cost") is not None else (end - start) / 3600 * dph
        rid = str(h.get("run_id") or (r or {}).get("run_id") or "")
        if rid.startswith("smoke"):
            kind = "smoke"
        else:
            train = (r or {}).get("train_s")
            sea = _ts(seas[inst].get("at")) if inst in seas else None
            if train is not None:
                trained = float(train) >= TRAINED_S
            elif sea is not None:
                trained = end - sea >= TRAINED_S
            else:  # before the charter wrote `at sea` (8-9 November): a voyage home with a rate trained
                trained = bool((r or {}).get("tokens_per_s")) or str((r or {}).get("status") or "") in ("home", "overran")
            kind = "trained" if (trained or still and sea is not None) else "never_trained"
        out.append({"instance": inst, "name": h.get("name") or (r or {}).get("name") or rid[:12] or f"instance {inst}",
                    "gpu": h.get("gpu") or (r or {}).get("gpu") or "–", "kind": kind, "start": start, "end": end,
                    "dph": dph, "cost": cost, "out": still, "no_cost": r is not None and r.get("cost") is None,
                    "status": "out now" if still else str((r or {}).get("status") or (r or {}).get("why") or "released")})  # fmt: skip
    return sorted(out, key=lambda x: x["start"])


def _floor(t: float, by: str) -> datetime:
    """The start of the bucket `t` falls in."""
    if by == "week":
        d = datetime.fromtimestamp(t, UTC)
        d = datetime(d.year, d.month, d.day, tzinfo=UTC)
        return d - timedelta(days=d.weekday())
    d = datetime.fromtimestamp(t).astimezone()
    if by == "hour":
        return d.replace(minute=0, second=0, microsecond=0)
    if by == "day":
        return d.replace(hour=0, minute=0, second=0, microsecond=0)
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _next(d: datetime, by: str) -> datetime:
    if by == "hour":
        return d + timedelta(hours=1)
    if by == "day":
        return (d + timedelta(days=1, hours=2)).replace(hour=0)  # across a change of the clocks
    if by == "week":
        return d + timedelta(days=7)
    return (d.replace(day=28) + timedelta(days=4)).replace(day=1)


def _label(d: datetime, by: str) -> str:
    if by == "hour":
        return d.strftime("%d %b %H:00")
    if by == "day":
        return d.strftime("%a %d %b")
    if by == "week":
        return "week of " + d.strftime("%d %b")
    return d.strftime("%B %Y")


def buckets(rows: list[dict], by: str, now: float) -> list[dict]:
    """The spend in each bucket, back from now (`BYS`), each hire's cost spread over its hired time. Starts at the
    first bucket anything was spent in, so a short history is not a long row of empty bars."""
    n, _ = BYS[by]
    last = _floor(now, by)
    first = last
    for _ in range(n - 1):
        first = _floor(first.timestamp() - 1, by)
    if rows:
        first = max(first, _floor(min(r["start"] for r in rows), by))
    edges = [first]
    while edges[-1] <= last:
        edges.append(_next(edges[-1], by))
    out = []
    for a, b in zip(edges, edges[1:], strict=False):
        lo, hi = a.timestamp(), b.timestamp()
        row = {"start": a.isoformat(timespec="minutes"), "label": _label(a, by), "now": lo <= now < hi,
               **{k: 0.0 for k in KINDS}, "hours": 0.0, "hires": 0}  # fmt: skip
        for r in rows:
            span = r["end"] - r["start"]
            got = max(0.0, min(hi, r["end"]) - max(lo, r["start"]))
            if span <= 0:  # a hire released in the same second: all of it where it began
                got, share = (1.0, 1.0) if lo <= r["start"] < hi else (0.0, 0.0)
            else:
                share = got / span
            if share > 0:
                row[r["kind"]] += r["cost"] * share
                row["hours"] += got / 3600 if span > 0 else 0.0
            if lo <= r["start"] < hi:
                row["hires"] += 1
        row["total"] = sum(row[k] for k in KINDS)
        out.append(row)
    return out


def payload(by: str = "day", now: float | None = None) -> dict:
    """The Cost tab: the spend in buckets of `by`, the headline figures, the budget and the costliest hires."""
    from thorp.viable.s3_control import charter as s3
    from thorp.viable.s3_control import purser
    from thorp.viable.s5_policy import charter as s5

    by = by if by in BYS else "day"
    now = time.time() if now is None else now
    log = s3.log()
    rows = hires(log, now)
    terms = s5.terms()

    def spent(since: float) -> float:
        total = 0.0
        for r in rows:
            span = r["end"] - r["start"]
            got = max(0.0, r["end"] - max(since, r["start"]))
            total += r["cost"] * (got / span if span > 0 else (1.0 if r["start"] >= since else 0.0))
        return total

    hour, day, month = (_floor(now, k).timestamp() for k in ("hour", "day", "month"))
    week = s3.week_start(datetime.fromtimestamp(now, UTC)).timestamp()
    cycle = purser.cycle_start(now, terms)
    by_kind = {k: sum(r["cost"] for r in rows if r["kind"] == k) for k in KINDS}
    by_gpu: dict[str, dict] = {}
    for r in rows:
        g = by_gpu.setdefault(r["gpu"], {"gpu": r["gpu"], "cost": 0.0, "hires": 0, "hours": 0.0, "never_trained": 0.0})
        g["cost"] += r["cost"]
        g["hires"] += 1
        g["hours"] += (r["end"] - r["start"]) / 3600
        if r["kind"] == "never_trained":
            g["never_trained"] += r["cost"]
    weekly = float(terms.get("weekly_budget", 0.0))
    week_spent = spent(week)
    try:
        counted = float(s3.week_spent(datetime.fromtimestamp(now, UTC)))
    except Exception:  # noqa: BLE001 - the budget's own figure cannot be read: say nothing of it
        counted = None
    return {
        "at": datetime.fromtimestamp(now).astimezone().isoformat(timespec="seconds"),
        "by": by, "about": BYS[by][1],
        "buckets": buckets(rows, by, now),
        "now": {"hour": spent(hour), "day": spent(day), "week": week_spent, "month": spent(month),
                "cycle": spent(cycle), "all": sum(r["cost"] for r in rows)},
        "budget": {"weekly": weekly, "week_left": max(0.0, weekly - week_spent), "voyage": float(terms.get("voyage_budget", 0.0)),
                   # what S3 holds the budget to: released hires' logged costs and the ships out. A ship released
                   # by hand (9 November) logged no cost, so it is in the spend above and not in this
                   "counted": counted, "uncounted": [{"name": r["name"], "gpu": r["gpu"], "cost": r["cost"], "status": r["status"]}
                                                     for r in rows if r["start"] >= week and r.get("no_cost")],
                   "cycle_hours": float(terms.get("cycle_hours", 24.0)), "week_starts": datetime.fromtimestamp(week).astimezone().isoformat(timespec="minutes")},
        "by_kind": by_kind,
        "by_gpu": sorted(by_gpu.values(), key=lambda g: -g["cost"]),
        "out": [{"name": r["name"], "gpu": r["gpu"], "dph": r["dph"], "cost": r["cost"], "since": datetime.fromtimestamp(r["start"]).astimezone().isoformat(timespec="minutes")} for r in rows if r["out"]],
        "top": [{"name": r["name"], "gpu": r["gpu"], "kind": r["kind"], "cost": r["cost"], "hours": (r["end"] - r["start"]) / 3600,
                 "start": datetime.fromtimestamp(r["start"]).astimezone().isoformat(timespec="minutes"), "status": r["status"]}
                for r in sorted(rows, key=lambda r: -r["cost"])[:10]],
        "hires": len(rows),
    }  # fmt: skip

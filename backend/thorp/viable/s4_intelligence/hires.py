"""S4: what a hire really takes, measured (12 November, Justin: "Vast needs to make measurements not only on
processing but also setup times").

Every hire's `released` line in S3's spend log now carries where its time went (s1_operations.charter.Phases:
provision, ssh, code, data, board, env, then train and home, and the megabytes each transfer carried). This
module reads those lines and answers what the planners ask:

- `timings()`: one row a hire, with its set-up, training and home seconds and whether it ever sailed. A hire from
  before the record (9 to 12 November) is read from `data/runs/charter.log`, the way the timing table reads it,
  or from its `at sea` mark; the row says which (`source`).
- `setup(gpu)`: the minutes to plan on for a class, out and home: the median of its hires that sailed. With a
  payload in megabytes it is the class's fixed part (everything but the data transfer) plus the payload over the
  measured megabytes a second, so a small cargo is not charged a large one's upload. Where a class has no hire
  that sailed, every class's hires stand in; where there are none at all, S5's constant (`SETUP_HOURS`).
- `failures(gpu)`: how often a fit-out died before the voyage sailed, and the minutes it cost.
- `train_seconds(release)`: the voyage's seconds at sea, for the rate. The market used to take the whole hire less
  S5's 21 minutes, so a 42-minute set-up made a 5090 look a quarter slower than it was.

Measurement is arithmetic over records. Nothing here guesses, and nothing here is judged: what a number cannot
say (why a box died) is the judge's (s4_intelligence/judge.py).
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from statistics import median

from thorp.viable.s3_control import charter as s3
from thorp.viable.s5_policy import charter as s5

SETUP_STEPS = ("provision", "ssh", "code", "data", "board", "env", "fitout")
MIN_FAILED_S = 300.0  # a hire stopped by hand inside five minutes is not a failed fit-out
MEASURED = "measured by the charter"
LAST = 3  # a class's set-up is the median of its last few hires that sailed


def _from_log() -> dict[int, dict]:
    """The hires the charter's log can still time, by instance (the timing table's own reading)."""
    out: dict[int, dict] = {}
    with contextlib.suppress(Exception):
        from thorp.dash import settings

        for c in settings.charters(limit=500).get("charters") or []:
            if c.get("instance") is not None:
                out[int(c["instance"])] = c
    return out


def _ts(at) -> float | None:
    with contextlib.suppress(Exception):
        return datetime.fromisoformat(str(at)).timestamp()
    return None


def _run_minutes(run_id) -> float | None:
    """A run's wall minutes from the ledger, or None."""
    with contextlib.suppress(Exception):
        from thorp.ledger import reader

        run = reader().get_run(run_id) or {}
        return float(run["wall_minutes"]) if run.get("wall_minutes") else None
    return None


_CACHE: dict = {"sig": None, "rows": None}


def timings(log: list[dict] | None = None, from_log: dict[int, dict] | None = None, run_minutes=None) -> list[dict]:
    """One row a hire that has been released, oldest first. Read from the spend log each time; the rows are kept
    while the log has not grown (the market asks once a release)."""
    plain = log is None and from_log is None and run_minutes is None
    log = s3.log() if log is None else log
    sig = (len(log), log[-1].get("at") if log else None, log[-1].get("instance") if log else None)
    if plain and _CACHE["sig"] == sig and _CACHE["rows"] is not None:
        return _CACHE["rows"]
    rows = _timings(log, from_log, run_minutes)
    if plain:
        _CACHE.update(sig=sig, rows=rows)
    return rows


def _timings(log: list[dict], from_log: dict[int, dict] | None, run_minutes) -> list[dict]:
    hired = {r["instance"]: r for r in log if r["event"] == "hired" and r.get("instance") is not None}
    seas = {r["instance"]: r for r in log if r["event"] == "at sea" and r.get("instance") is not None}
    parsed = None
    out = []
    for r in log:
        if r["event"] != "released" or r.get("instance") is None:
            continue
        inst, h = r["instance"], hired.get(r["instance"]) or {}
        # a ship released by hand (9 November) left only its words: the hire's own line has the rest
        started = r.get("started") or h.get("started")
        ended = r.get("ended") or _ts(r.get("at"))
        if not started or not ended:
            continue
        total = max(0.0, float(ended) - float(started))
        dph = r.get("dph") or h.get("dph")
        cost = r.get("cost") if r.get("cost") is not None else (total / 3600 * float(dph) if dph else None)
        rid = r.get("run_id") or h.get("run_id")
        smoke = str(rid or "").startswith("smoke")
        row = {
            "instance": inst, "run_id": rid, "name": r.get("name") or h.get("name"),
            "gpu": r.get("gpu") or h.get("gpu"), "preset": r.get("preset") or h.get("preset"),
            # a hedge's second box, released because the other came up first (charter.HEDGE_RATE, 14 November): its
            # cost is real, but it is neither a fit-out that failed nor a voyage's set-up, so the measures leave it out
            "kind": "smoke" if smoke else "hedge" if str(r.get("status") or "").startswith("hedged") else "voyage",
            "started": float(started), "ended": float(ended), "total_s": total,
            "dph": dph, "cost": cost, "status": r.get("status") or ("released by hand" if r.get("why") else None),
            "why": r.get("why"),
            "quote_hours": h.get("quote_hours"), "quote": h.get("quote"), "tokens_per_s": r.get("tokens_per_s"),
            "setup_assumed_h": h.get("setup_assumed_h"),
            "phases": None, "mb": {}, "setup_s": None, "train_s": None, "home_s": None,
            "sailed": False, "failed_in": None, "source": None,
        }  # fmt: skip
        if isinstance(r.get("phases"), dict):  # the charter's own measurement
            row.update(phases=r["phases"], mb=r.get("mb") or {}, setup_s=r.get("setup_s"), train_s=r.get("train_s"),
                       home_s=r.get("home_s"), sailed=bool(r.get("sailed")), failed_in=r.get("failed_in"),
                       source=MEASURED)  # fmt: skip
        elif not smoke:
            if parsed is None:
                parsed = _from_log() if from_log is None else from_log
            c = parsed.get(int(inst))
            if c and isinstance(c.get("phases"), dict):
                ph = {k: float(v) for k, v in c["phases"].items() if v is not None}
                train, home = ph.get("train"), ph.get("home")
                setup = sum(v for k, v in ph.items() if k in SETUP_STEPS)
                last = next((k for k in ("env", "board", "data", "code", "ssh", "provision") if k in ph), None)
                row.update(phases=ph, setup_s=setup, train_s=train, home_s=home, sailed=train is not None,
                           failed_in=None if train is not None else last, source="read from charter.log")  # fmt: skip
            elif inst in seas and _ts(seas[inst].get("at")):
                sea = _ts(seas[inst]["at"])
                row.update(setup_s=max(0.0, sea - float(started)), train_s=None, sailed=True,
                           source="from the at-sea mark")  # fmt: skip
            elif r.get("tokens_per_s") or str(r.get("status") or "") in ("home", "overran", "came in unfinished"):
                # it trained and nothing timed its steps: the run's own clock says how long it was at sea, and the
                # rest of the hire was set-up and home together
                row.update(sailed=True, source="from the run's own clock (set-up and home together)")
                wall = (run_minutes or _run_minutes)(rid)
                if wall and 0 < wall * 60 < total:
                    row.update(train_s=wall * 60, setup_s=total - wall * 60)
        if not row["sailed"] and not smoke and row["setup_s"] is None:
            row["setup_s"] = total  # it never sailed: the whole hire was fit-out
        out.append(row)
    return out


def _voyages(rows: list[dict], gpu: str | None) -> list[dict]:
    return [r for r in rows if r["kind"] == "voyage" and (gpu is None or r["gpu"] == gpu)]


def _latest(sailed: list[dict], n: int = LAST) -> list[dict]:
    """The hires to plan on: the charter's own measurements where there are any (the hires reconstructed from the
    log carried 9 GB aboard; since 12 November a voyage carries under 1 GB, so the two are not one population),
    and of those the last few."""
    own = [r for r in sailed if r["source"] == MEASURED]
    return (own or sailed)[-n:]


def setup(gpu: str | None = None, payload_mb: float | None = None, rows: list[dict] | None = None) -> dict:
    """The minutes to plan a hire's overhead on: {setup_min, home_min, total_min, n, source}."""
    rows = timings() if rows is None else rows
    sailed = _latest([r for r in _voyages(rows, gpu) if r["sailed"] and r["setup_s"] is not None])
    source = f"measured: the median of the last {len(sailed)} {gpu} hire(s) that sailed" if sailed else ""
    if not sailed and gpu is not None:
        sailed = _latest([r for r in _voyages(rows, None) if r["sailed"] and r["setup_s"] is not None])
        source = f"no {gpu} hire has sailed: the median of the last {len(sailed)} hire(s) of other classes" if sailed else ""
    if sailed and not any(r["source"] == MEASURED for r in sailed):
        source += " (reconstructed, from before the cargo was trimmed on 12 November: it errs long)"
    if not sailed:
        const = 60.0 * float(s5.SETUP_HOURS)
        return {"setup_min": const, "home_min": 0.0, "total_min": const, "n": 0, "fixed_min": None, "mb_per_s": None,
                "source": f"unmeasured: S5's constant ({s5.SETUP_HOURS} h, out and home together)"}  # fmt: skip
    setup_s = median(r["setup_s"] for r in sailed)
    homes = [r["home_s"] for r in sailed if r["home_s"] is not None]
    home_s = median(homes) if homes else 0.0
    # the fixed part and the megabytes a second, where a hire recorded both its data transfer and its size
    fixed, rates = [], []
    for r in sailed:
        ph, mb = r.get("phases") or {}, (r.get("mb") or {}).get("data")
        if ph.get("data") is not None:
            fixed.append(r["setup_s"] - float(ph["data"]))
            if mb and float(ph["data"]) > 0:
                rates.append(float(mb) / float(ph["data"]))
    fixed_s = median(fixed) if fixed else None
    rate = median(rates) if rates else None
    if payload_mb is not None and fixed_s is not None and rate:
        setup_s = fixed_s + float(payload_mb) / rate
        source += f"; {payload_mb:.0f} MB at the measured {rate:.1f} MB/s"
    return {"setup_min": setup_s / 60, "home_min": home_s / 60, "total_min": (setup_s + home_s) / 60,
            "n": len(sailed), "fixed_min": fixed_s / 60 if fixed_s is not None else None, "mb_per_s": rate,
            "source": source}  # fmt: skip


def failures(gpu: str | None = None, rows: list[dict] | None = None) -> dict:
    """The fit-outs that died before sailing: {hires, failed, rate, wasted_min, wasted_cost, last}."""
    rows = timings() if rows is None else rows
    v = [r for r in _voyages(rows, gpu) if r["sailed"] or r["total_s"] >= MIN_FAILED_S]
    failed = [r for r in v if not r["sailed"]]
    return {
        "hires": len(v), "failed": len(failed), "rate": len(failed) / len(v) if v else None,
        "wasted_min": sum(r["total_s"] for r in failed) / 60,
        "wasted_cost": sum(float(r["cost"] or 0.0) for r in failed),
        "last": [{"instance": r["instance"], "name": r["name"], "gpu": r["gpu"], "status": r["status"],
                  "why": r.get("why"), "failed_in": r["failed_in"], "minutes": r["total_s"] / 60, "cost": r["cost"]}
                 for r in failed[-5:]],
    }  # fmt: skip


def train_seconds(release: dict, rows: list[dict] | None = None) -> float | None:
    """A released hire's seconds at sea: the charter's own `train_s`; else the hire less the set-up and home this
    hire is known to have taken; None when neither is on record (the market then falls back to S5's constant)."""
    if release.get("train_s"):
        return float(release["train_s"])
    with contextlib.suppress(Exception):
        rows = timings() if rows is None else rows
        row = next((r for r in rows if r["instance"] == release.get("instance")), None)
        if row and row["sailed"]:
            if row["train_s"]:
                return float(row["train_s"])
            if row["setup_s"] is not None:
                left = row["total_s"] - float(row["setup_s"]) - float(row["home_s"] or 0.0)
                return left if left > 60 else None
    return None


def classes(terms: dict | None = None, rows: list[dict] | None = None) -> list[dict]:
    """Each class the terms hire, with what has been measured on it (the Liberty Machine page's S4 table)."""
    terms = terms or s5.terms()
    rows = timings() if rows is None else rows
    out = []
    for gpu in terms.get("gpus") or {}:
        st, fl = setup(gpu, rows=rows), failures(gpu, rows=rows)
        mine = [r for r in _voyages(rows, gpu) if r["sailed"]]
        out.append({"gpu": gpu, "sailed": len(mine), "setup_min": st["setup_min"], "home_min": st["home_min"],
                    "overhead_min": st["total_min"], "own": bool(mine), "source": st["source"],
                    "fixed_min": st["fixed_min"], "mb_per_s": st["mb_per_s"],
                    "hires": fl["hires"], "failed": fl["failed"], "failure_rate": fl["rate"]})  # fmt: skip
    return out


def main(argv: list[str] | None = None) -> int:
    """`python -m thorp.viable.s4_intelligence.hires`: every hire's timing, then each class's set-up."""
    rows = timings()
    for r in rows:
        if r["kind"] != "voyage":
            continue
        f = lambda s: "   -  " if s is None else f"{float(s) / 60:5.1f}m"  # noqa: E731
        print(f"{str(r['gpu'])[:9]:9} {str(r['name'] or r['run_id'])[:26]:26} setup {f(r['setup_s'])} train {f(r['train_s'])} "
              f"home {f(r['home_s'])} total {f(r['total_s'])}  {'sailed' if r['sailed'] else 'never sailed':12} {r['source'] or ''}")  # fmt: skip
    print()
    for c in classes(rows=rows):
        rate = "-" if c["failure_rate"] is None else f"{c['failure_rate']:.0%}"
        print(f"{c['gpu']:10} overhead {c['overhead_min']:5.1f} min (set-up {c['setup_min']:.1f}, home {c['home_min']:.1f}); "
              f"{c['failed']}/{c['hires']} fit-outs failed ({rate}); {c['source']}")  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""S3: the queue's planning cycle (12 November, Justin: "talk me through how in our Liberty Machine the optimal way to
schedule the queue every 12 hours to maximise speed and maintain the cost ceilings"; "this is great, build it").

Every S5 `cycle_hours` (twelve) the five systems take one turn, each doing only its own part:

1. **S3\\* closes the books** (s3star_audit/cycle.py): the last cycle's plan against what happened: quote
   against bill, the queue's clock against the Mac, the lines called foreign against where they are now.
2. **S4 refreshes the picture** (s4_intelligence/hires.py, market.py): each class's measured set-up and home,
   how often its fit-outs die, its rate at each size, its price.
3. **S5 sets the envelope** (s5_policy/charter.py): what is left of the week's budget over the cycles left in
   it, one voyage's budget, the ships allowed at once, the overrun a hire is counted at.
4. **S3 plans** (this module, on the purser's own planner): the same queue planned for one ship, two, three,
   four; the fleet chosen is the smallest that brings the queue home as soon as the terms allow. What the terms
   do not allow is a *proposal* to S5, never done.
5. **S2 sails it** (s2_coordination/lanes.py): the coordinator runs the lanes; the purser steers inside the
   envelope every five minutes (a failed box, an edited queue). It chooses nothing.
6. **S1 measures** (s1_operations/charter.py Phases): every hire writes where its time went on its release,
   which is step 2 of the next turn.

And S4's judge (s4_intelligence/judge.py) reads what the numbers cannot say: why a fit-out died.

**What "optimal" means here.** The Mac is free and never idle, so it is the critical path; a hired ship costs the
same whether it sails beside another or after it, but each *hire* pays its set-up again. So: send abroad what
saves the most of the Mac's time a dollar, on as many ships as bring the queue home sooner, and stop when the
ships would only finish after the Mac or the cycle's allowance is spent. The planner tries each fleet and prices
the next ship in dollars an hour saved. Every hire is counted against the allowance at its quote times S5's
overrun, so the ceiling holds if every ship is brought home at its deadline.

**What it does not do yet** (`NOT_BUILT`): keep one box for several voyages (the charter sails one voyage a hire,
so every voyage pays its own set-up) or stagger hires behind one upload. (The breaker is S2's, built the same day:
two fit-outs failing in a row pause the lane, and a box that fails before its voyage sails is retried abroad.)

    uv run thorp cycle            # the last turn, and what would be planned now
    uv run thorp cycle run        # take a turn now and keep it (s3.cycles)
    uv run thorp cycle run --judge  # and ask the judge about failed fit-outs it has not answered
    uv run thorp cycle schedule   # put the turn on Thorp's own schedule (s2.schedule_jobs), at 06:00 and 18:00
"""

from __future__ import annotations

import contextlib
import dataclasses
import time
from datetime import UTC, datetime

JOB = "queue-cycle"
CRON = "0 6,18 * * *"
TRY_SHIPS = 4  # the fleets the planner prices, whatever the terms allow (the rest is a proposal)
CLOSE_H = 0.25  # a fleet within a quarter of an hour of the best is as good: take the smaller
WORTH_H = 1.0  # a fleet beyond the terms is proposed only when it brings the queue home this much sooner

STEPS = [
    {"n": 1, "system": "S3*", "title": "Close the books", "code": "thorp/viable/s3star_audit/cycle.py",
     "what": "The last cycle's plan against what happened: quote against bill, the queue's clock against the Mac, the lines called foreign against where they are now."},
    {"n": 2, "system": "S4", "title": "Refresh the picture", "code": "thorp/viable/s4_intelligence/hires.py",
     "what": "Each GPU class's measured set-up and home, how often its fit-outs die, its rate and its price. The judge reads why a fit-out died."},
    {"n": 3, "system": "S5", "title": "Set the envelope", "code": "thorp/viable/s5_policy/charter.py",
     "what": "What is left of the week's budget over the cycles left, one voyage's budget, the ships allowed at once, the overrun a hire is counted at."},
    {"n": 4, "system": "S3", "title": "Make the plan", "code": "thorp/viable/s3_control/cycle.py",
     "what": "The queue planned for one ship to four; the smallest fleet that brings it home soonest within the terms. Anything beyond the terms is a proposal to S5."},
    {"n": 5, "system": "S2", "title": "Sail it", "code": "thorp/viable/s2_coordination/lanes.py",
     "what": "The coordinator runs the lanes; the purser steers inside the envelope every five minutes. It chooses nothing."},
    {"n": 6, "system": "S1", "title": "Measure", "code": "thorp/viable/s1_operations/charter.py",
     "what": "Every hire writes where its time went on its release: provision, ssh, code, data, board, env, training, home."},
]  # fmt: skip

NOT_BUILT = [
    "One box kept for several voyages: the charter sails one voyage a hire, so every voyage abroad pays its own set-up.",
    "Hires staggered behind one upload: ships hired together share this Mac's line up while each is billed.",
]  # fmt: skip


# ---------------------------------------------------------------- step 3, the envelope


def envelope(w) -> dict:
    """S5's ceilings as they bind this cycle (read from the purser's world)."""
    from thorp.viable.s3_control import purser

    t = w.terms
    weekly = float(t.get("weekly_budget", 0.0))
    reserve = max(1.0, float(w.reserve or 1.0))
    allow = purser.allowance_at(w.now, w)
    return {
        "cycle_hours": float(t.get("cycle_hours", 24.0)), "weekly_budget": weekly, "week_spent": float(w.week_spent),
        "week_left": max(0.0, weekly - float(w.week_spent)), "cycles_left": purser.cycles_left(w),
        "cycle_allowance": allow, "spendable": allow / reserve, "overrun": reserve,
        "cycle_spent": float(w.cycle_spent), "cycle_held": float(w.cycle_held),
        "cycle_share": allow + float(w.cycle_spent) + float(w.cycle_held),
        "voyage_budget": float(t.get("voyage_budget", 0.0)), "max_instances": int(t.get("max_instances", 1)),
        "lane_enabled": bool(w.foreign_ok), "purser": str(t.get("purser") or "off"),
        "weekly_only": purser.weekly_only(t),
        "foreign_expeditions": list(t.get("foreign_expeditions") or []),
        "margin_hours": float(t.get("margin_hours", 1.0)), "margin_fraction": float(t.get("margin_fraction", 0.25)),
    }  # fmt: skip


# ---------------------------------------------------------------- step 4, the plan


def _summary(calls: list, ships: int) -> dict:
    foreign = [c for c in calls if c.waters == "foreign"]
    local = [c.local_home_min for c in calls if c.waters == "local" and c.local_home_min is not None]
    mac_h = max(local) / 60 if local else 0.0
    ships_h = max((c.foreign_home_min or 0.0) for c in foreign) / 60 if foreign else 0.0
    return {"ships": ships, "abroad": len(foreign), "cost": sum(c.cost or 0.0 for c in foreign),
            "gpu_hours": sum(c.foreign_min or 0.0 for c in foreign) / 60,
            "mac_done_h": mac_h, "ships_done_h": ships_h, "all_done_h": max(mac_h, ships_h)}  # fmt: skip


def options(lines: list, w, estimate, cmd_estimate, eligible, upto: int = TRY_SHIPS) -> tuple[list[dict], dict[int, list]]:
    """The queue planned for each fleet, one ship to `upto` (the lane taken as open, so a closed lane still shows
    what it would carry). Returns the rows and each fleet's calls."""
    from thorp.viable.s3_control import purser

    rows, calls_by = [], {}
    limit = int(w.terms.get("max_instances", 1))
    for n in range(1, max(upto, limit) + 1):
        wn = dataclasses.replace(w, foreign_ok=True, ship_free=sorted(w.ship_free)[:n] + [w.now] * max(0, n - len(w.ship_free)))
        calls = purser.plan(lines, wn, estimate, cmd_estimate, eligible)
        row = {**_summary(calls, n), "within_terms": n <= limit}
        if rows:
            prev = rows[-1]
            saved, extra = prev["all_done_h"] - row["all_done_h"], row["cost"] - prev["cost"]
            row["hours_saved"] = saved
            row["dollars_per_hour_saved"] = extra / saved if saved > 1e-6 else None
        rows.append(row)
        calls_by[n] = calls
    return rows, calls_by


def choose(rows: list[dict]) -> dict:
    """The fleet to sail: within the terms, the fewest ships that bring the queue home within `CLOSE_H` of the
    best the terms allow. And the fleet to propose, if one beyond the terms is `WORTH_H` sooner."""
    inside = [r for r in rows if r["within_terms"]] or rows[:1]
    best = min(r["all_done_h"] for r in inside)
    pick = next(r for r in inside if r["all_done_h"] <= best + CLOSE_H)
    beyond = [r for r in rows if not r["within_terms"] and r["all_done_h"] <= pick["all_done_h"] - WORTH_H]
    further = None
    if beyond:
        b = min(r["all_done_h"] for r in beyond)
        further = next(r for r in beyond if r["all_done_h"] <= b + CLOSE_H)
    return {"ships": pick["ships"], "propose_ships": further["ships"] if further else None}


def unmeasured(lines: list, w, estimate, eligible) -> dict[str, dict]:
    """The sizes no class has sailed: every eligible voyage of that size stays here until one is measured."""
    out: dict[str, dict] = {}
    for ln in lines:
        if getattr(ln, "kind", "spec") != "spec" or not getattr(ln, "spec", None):
            continue
        preset = str(((ln.spec or {}).get("model") or {}).get("preset") or "")
        if not preset or any(p == preset and sp > 1.0 for (_, p), sp in w.speedups.items()):
            continue
        if eligible(ln)[1]:
            continue
        mins = estimate(ln)[0] or 0.0
        o = out.setdefault(preset, {"lines": 0, "mac_hours": 0.0})
        o["lines"] += 1
        o["mac_hours"] += mins / 60
    return out


def lane_lints(rows: list[dict], parse) -> list[str]:
    """Queue rows whose stored lane is not the lane the coordinator will read from their text (12 November: two
    9m lines stored as `vast` with no `vast:` prefix sailed on the Mac, as the coordinator reads only the text)."""
    odd = []
    for r in rows:
        with contextlib.suppress(Exception):
            if r.get("lane") and parse(r["text"]).lane != r["lane"]:
                odd.append(r["text"])
    if not odd:
        return []
    return [f"{len(odd)} queued line(s) are stored in a lane the coordinator will not sail them in (it reads the "
            f"line's text, and they carry no lane prefix): {', '.join(odd[:4])}"]  # fmt: skip


def proposals(env: dict, rows: list[dict], pick: dict, missing: dict[str, dict], lints: list[str], held: int = 0) -> list[dict]:
    """What the plan would do if S5 allowed it. Justin signs; nothing here is done."""
    out = []
    chosen = next(r for r in rows if r["ships"] == pick["ships"])
    if not env["lane_enabled"] and chosen["abroad"]:
        mac_only = rows[0].get("mac_only_h")
        gain = f", home {mac_only - chosen['all_done_h']:.0f} h sooner" if mac_only else ""
        out.append({"to": "S2", "what": "open the Vast lane",
                    "why": f"it is closed, and {chosen['abroad']} queued voyage(s) would sail abroad for ${chosen['cost']:.2f}{gain}"})  # fmt: skip
    if pick["propose_ships"]:
        r = next(x for x in rows if x["ships"] == pick["propose_ships"])
        out.append({"to": "S5", "what": f"allow {r['ships']} ships at once (max_instances is {env['max_instances']})",
                    "why": f"the queue would be home in {r['all_done_h']:.1f} h, not {chosen['all_done_h']:.1f} h, "
                           f"for ${r['cost']:.2f} against ${chosen['cost']:.2f}"})  # fmt: skip
    for preset, m in sorted(missing.items(), key=lambda kv: -kv[1]["mac_hours"]):
        out.append({"to": "S4", "what": f"sail one {preset} abroad with its control, to measure it",
                    "why": f"no class has sailed a {preset}, so {m['lines']} voyage(s) ({m['mac_hours']:.1f} h of this Mac) "
                           "cannot be sent abroad: a class is never assumed faster than the Mac"})  # fmt: skip
    if held and env.get("weekly_only"):
        out.append({"to": "S5", "what": "the week's budget is the binding ceiling",
                    "why": f"{held} more voyage(s) would sail abroad this week but for it: the plan commits "
                           f"${chosen['cost'] * env['overrun']:.2f} of the ${env['cycle_allowance']:.2f} left (hires "
                           f"counted at {env['overrun']:g} times their quote); the budget comes back on Monday"})  # fmt: skip
    elif held:
        out.append({"to": "S5", "what": "the cycle's allowance is the binding ceiling",
                    "why": f"{held} more voyage(s) would sail abroad this cycle but for it: the plan commits "
                           f"${chosen['cost'] * env['overrun']:.2f} of ${env['cycle_allowance']:.2f} (hires counted at "
                           f"{env['overrun']:g} times their quote); what is not spent carries to the next cycle"})  # fmt: skip
    for lint in lints:
        out.append({"to": "S2", "what": "re-queue those lines with their lane written on them", "why": lint})
    return out


def make_plan(now: float | None = None) -> dict:
    """Steps 2 to 4, read and planned now; writes nothing."""
    from thorp.viable.s2_coordination import lanes, queue_store
    from thorp.viable.s3_control import purser
    from thorp.viable.s4_intelligence import hires

    w, times = purser.world(now=now)
    stored = queue_store.lines()
    lines = [lanes.parse(r["text"]) for r in stored]
    estimate = lambda ln: times.estimate(ln.name or "", ln.spec or {})  # noqa: E731
    eligible = purser.eligibility(w.terms)
    env = envelope(w)
    rows, calls_by = options(lines, w, estimate, purser.cmd_minutes, eligible)
    here = purser.plan(lines, dataclasses.replace(w, foreign_ok=False), estimate, purser.cmd_minutes, eligible)
    mac_only = _summary(here, 0)["mac_done_h"]
    for r in rows:
        r["mac_only_h"] = mac_only
    pick = choose(rows)
    calls = calls_by[pick["ships"]]
    missing = unmeasured(lines, w, estimate, eligible)
    lints = lane_lints(stored, lanes.parse)
    timing = hires.timings()
    measured = {
        "classes": hires.classes(w.terms, rows=timing),
        "failures": hires.failures(rows=timing),
        "speedups": [{"gpu": g, "preset": p, "lead": sp} for (g, p), sp in sorted(w.speedups.items())],
        "prices": dict(w.prices),
        "overhead_min": dict(w.setup_min),
    }
    plan = {
        "queued": len(lines), "mac_only_h": mac_only, "options": rows, "ships": pick["ships"],
        "abroad": [{"name": c.name, "gpu": c.gpu, "cost": c.cost, "minutes": c.foreign_min, "home_min": c.foreign_home_min,
                    "reason": c.reason} for c in calls if c.waters == "foreign"],
        "stay": sum(1 for c in calls if c.waters == "local"),
        "unmeasured": missing, "lints": lints, "lane_enabled": env["lane_enabled"],
    }  # fmt: skip
    words = purser.ceiling_words(w.terms)
    held = sum(1 for c in calls if c.waters == "local" and words in (c.reason or ""))
    plan["held_by_allowance"] = held
    return {"measured": measured, "envelope": env, "plan": plan, "proposals": proposals(env, rows, pick, missing, lints, held)}


# ---------------------------------------------------------------- the turn, and its record


def latest() -> dict | None:
    """The last turn kept, or None."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import Cycle

    with store.session() as s:
        r = s.scalars(select(Cycle).order_by(Cycle.id.desc()).limit(1)).first()
        if r is None:
            return None
        return {"id": r.id, "at": r.at.isoformat(timespec="minutes"), "at_ts": r.at.timestamp(), "hours": r.hours,
                "how": r.how, "audit": r.audit, "measured": r.measured, "envelope": r.envelope, "plan": r.plan,
                "proposals": r.proposals, "judged": r.judged, "seconds": r.seconds}  # fmt: skip


def run(judge: bool = False, how: str = "by hand", keep: bool = True, log=print) -> dict:
    """One turn of the cycle. With `keep` it is written to s3.cycles; the judge is asked only with `judge`."""
    from thorp.viable.s3star_audit import cycle as s3star

    t0, now = time.time(), time.time()
    prev = latest()
    made = make_plan(now)
    hours = float(made["envelope"]["cycle_hours"])
    # the window is the cycle just ended: back to the last turn, and never less than one cycle (a turn taken by
    # hand five minutes after another must not audit five minutes)
    since = min(float(prev["at_ts"]), now - hours * 3600) if prev else now - hours * 3600
    audit = s3star.review(since, now, (prev or {}).get("plan"))
    judged: list[dict] = []
    if judge:
        from thorp.viable.s4_intelligence import judge as s4judge

        with contextlib.suppress(Exception):
            judged = s4judge.judge_failures(log=log)
    out = {"hours": hours, "how": how, "audit": audit, **made, "judged": judged, "seconds": time.time() - t0}
    if keep:
        import json

        from thorp import store
        from thorp.viable.records import Cycle

        clean = json.loads(json.dumps(out, default=str))  # JSONB takes no infinities or datetimes
        with store.session() as s:
            row = Cycle(hours=hours, how=how, audit=clean["audit"], measured=clean["measured"], envelope=clean["envelope"],
                        plan=clean["plan"], proposals=clean["proposals"], judged=clean["judged"], seconds=out["seconds"])  # fmt: skip
            s.add(row)
            s.flush()
            out["id"] = row.id
    return out


def schedule(words: str, enable: bool = True) -> dict:
    """Put the turn on Thorp's own schedule (s2.schedule_jobs): 06:00 and 18:00, this Mac's time."""
    from thorp.viable.s2_coordination import schedule as s2

    s2.put_job(
        JOB, title="The queue's planning cycle", system="S3", kind="command", cron=CRON,
        command="backend/.venv/bin/python -m thorp.viable.s3_control.cycle run --judge --scheduled",
        description="Every twelve hours: S3* sets the last plan against what happened, S4 folds in what was measured, "
                    "S5's envelope is read, the purser plans the next twelve hours, and the judge reads any fit-out "
                    "that died. Writes s3.cycles; hires nothing and changes no term.",
        limits={"max_minutes": 45}, source="thorp cycle schedule", words=words,
    )  # fmt: skip
    if enable:
        s2.enable(JOB, True, words)
    return next(j for j in s2.jobs() if j["key"] == JOB)


def ticking() -> bool | None:
    """Whether launchd is running the schedule's tick (io.thorp.schedule); None when it cannot be asked."""
    import subprocess

    with contextlib.suppress(Exception):
        r = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=5)
        return "io.thorp.schedule" in (r.stdout or "")
    return None


def payload() -> dict:
    """The Liberty Machine page's cycle: the six steps, the last turn kept, and what is true now (the judge, the schedule,
    each class's measurements). Cheap: nothing here plans; the plan shown is the last turn's."""
    from thorp.viable.s2_coordination import schedule as s2
    from thorp.viable.s4_intelligence import hires
    from thorp.viable.s4_intelligence import judge as s4judge
    from thorp.viable.s5_policy import charter as s5

    def part(fn, default=None):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - one part failing must not blank the page
            return default if default is not None else {"error": repr(e)[:200]}

    last = part(latest, {})
    job = part(lambda: next((j for j in s2.jobs() if j["key"] == JOB), None), {})
    timing = part(hires.timings, [])
    terms = part(s5.terms, {})
    return {
        "at": datetime.now(UTC).astimezone().isoformat(timespec="seconds"),
        "steps": STEPS, "not_built": NOT_BUILT, "cycle_hours": float((terms or {}).get("cycle_hours", 12.0)),
        "last": last or None,
        "job": job or None, "cron": CRON, "ticking": part(ticking, {}),
        "judge": part(s4judge.chosen, {}) or None, "judge_can_run": part(lambda: list(s4judge.can_run()), [False, "unknown"]),
        "judgments": part(lambda: s4judge.judgments(8), []),
        "to_judge": part(lambda: [{"instance": c["instance"], "name": c["name"], "gpu": c["gpu"], "minutes": c["total_s"] / 60,
                                   "known": c.get("why"), "judged": c["judged"], "readable": c["readable"]}
                                  for c in s4judge.cases(timing)], []),
        "classes": part(lambda: hires.classes(terms, rows=timing), []),
        "failures": part(lambda: hires.failures(rows=timing), {}),
        "constant_min": 60.0 * float(s5.SETUP_HOURS),
    }  # fmt: skip


def _print(made: dict) -> None:
    env, plan = made["envelope"], made["plan"]
    if env.get("weekly_only"):
        print(f"S5 envelope: the week's budget alone: ${env['cycle_allowance']:.2f} of ${env['weekly_budget']:.2f} "
              f"may still be committed (${env['week_spent']:.2f} spent, ${env['cycle_held']:.2f} held for ships out; "
              f"${env['spendable']:.2f} of quotes at {env['overrun']:g}x); "
              f"{env['max_instances']} ship(s) allowed; the Vast lane is {'open' if env['lane_enabled'] else 'closed'}")  # fmt: skip
    else:
        print(f"S5 envelope: ${env['week_left']:.2f} of the week left over {env['cycles_left']} cycle(s): "
              f"${env['cycle_allowance']:.2f} left this cycle of its ${env['cycle_share']:.2f} share "
              f"(${env['cycle_spent']:.2f} spent, ${env['cycle_held']:.2f} held; ${env['spendable']:.2f} of quotes at {env['overrun']:g}x); "
              f"{env['max_instances']} ship(s) allowed; the Vast lane is {'open' if env['lane_enabled'] else 'closed'}")  # fmt: skip
    print("S4 measured:")
    for c in made["measured"]["classes"]:
        rate = "-" if c["failure_rate"] is None else f"{c['failure_rate']:.0%}"
        print(f"    {c['gpu']:10} overhead {c['overhead_min']:5.1f} min; fit-outs failed {c['failed']}/{c['hires']} ({rate}); {c['source']}")
    print(f"S3 plan: {plan['queued']} lines; all on this Mac, home in {plan['mac_only_h']:.1f} h")
    for r in plan["options"]:
        price = "" if r.get("dollars_per_hour_saved") is None else f"  (${r['dollars_per_hour_saved']:.2f} an hour saved)"
        mark = "*" if r["ships"] == plan["ships"] else " "
        terms = "" if r["within_terms"] else "  beyond the terms"
        print(f"  {mark} {r['ships']} ship(s): {r['abroad']:2} abroad for ${r['cost']:.2f}; this Mac home in {r['mac_done_h']:5.1f} h, "
              f"the ships in {r['ships_done_h']:5.1f} h{price}{terms}")  # fmt: skip
    for c in plan["abroad"]:
        print(f"      abroad: {c['name']} on an {c['gpu']} for ${c['cost']:.2f}")
    for p in made["proposals"]:
        print(f"  proposal to {p['to']}: {p['what']}: {p['why']}")


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="thorp cycle", description=__doc__.split("\n\n")[0])
    ap.add_argument("what", nargs="?", default="show", choices=["show", "run", "schedule"])
    ap.add_argument("--judge", action="store_true", help="ask the judge about failed fit-outs it has not answered")
    ap.add_argument("--scheduled", action="store_true", help="this turn was fired by the schedule")
    ap.add_argument("--queued", action="store_true", help="this turn was a line of the queue (S2's audit every few lines)")
    ap.add_argument("--words", default="", help="for `schedule`: who set it up, in their words")
    ap.add_argument("--off", action="store_true", help="for `schedule`: write the job but leave it switched off")
    a = ap.parse_args(argv)
    if a.what == "schedule":
        j = schedule(a.words or "thorp cycle schedule", enable=not a.off)
        tick = ticking()
        print(f"{JOB}: {CRON} ({'on' if j['enabled'] else 'off'}); next {j['next'] or '-'}")
        if tick is False:
            print("the schedule's tick (io.thorp.schedule) is not loaded in launchd: nothing fires until it is "
                  "(backend/scripts/launchd/io.thorp.schedule.plist says how)")  # fmt: skip
        return 0
    if a.what == "run":
        out = run(judge=a.judge, how="scheduled" if a.scheduled else "from the queue" if a.queued else "by hand")
        print(f"cycle {out.get('id')} kept ({out['seconds']:.1f} s)")
        for f in out["audit"]["findings"]:
            print(f"S3* found: {f}")
        _print(out)
        for j in out["judged"]:
            print(f"S4 judge: {j}")
        return 0
    last = latest()
    print(f"last turn: {last['at']} ({last['how']})" if last else "no turn kept yet (thorp cycle run)")
    _print(make_plan())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

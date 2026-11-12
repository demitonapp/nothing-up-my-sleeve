"""S3: the purser, who decides which waters each queued voyage sails in: this Mac (local) or a GPU hired from
Vast.ai (foreign). The aim is to clear the backlog soonest within S5's money (DECISIONS.md, "The purser",
8 November, Justin: "Accept all five"; built 12 November, Justin: "We need to build the router").

S2 (lanes.py) keeps the lanes from colliding and chooses nothing. The purser is the resource bargain above it.

**What it decides:** for each queued voyage whose expedition may sail abroad (S5's `foreign_expeditions`),
local or foreign, and on which GPU class. **What it never touches:** the order (the queue's order is Justin's
priority, and a line never sails before one written above it in the same waters); a `cmd:`, `wait:` or
`hold:` line; a line pinned with `mac:` or `vast:`; a spec whose `model.backend` already says where it sails.
Nothing behind a `hold:` is routed either: the hold is a sign-off, and sending its lines abroad would be going
around it.

**How** (greedy list scheduling, explainable line by line): walk the queue in order, keeping when each Mac seat
and each hired ship comes free. For each eligible voyage, estimate:

- *local:* when a Mac seat is free (and what it reads from is home), plus its time here (the queue page's own
  clock, dash/timing.RunTimes: the median of like voyages);
- *foreign:* when a ship is free, plus its time here divided by the class's **measured** speed-up for that
  size, plus the class's **measured** overhead (set-up and home: s4 hires.setup, the median of its last hires
  that sailed; S5's constant only where nothing has been measured), priced at the market's last price.

It sails abroad when it comes home sooner by the margin (`margin_hours` and `margin_fraction` of its wait), its
cost keeps one voyage's budget, and the spend planned so far stays within the **cycle's allowance** (what is left
of the week's budget spread over the planning cycles left in it: S5's `cycle_hours`, twelve, so Monday cannot spend
Sunday's money; twenty-four gives the day's allowance this began with). A hire is counted against the allowance at
its quote times S5's `overrun` (12 November: "it charges every hire at one and a half times its quote"), so the
ceiling holds even if every ship is brought home at its deadline. Otherwise it stays local.

**The speed-up is measured, or carried from a measured size** (12 November, Justin: "the purser rule is wrong":
until then a size no class had sailed stayed on the Mac). See `speedups`; the rest of this paragraph is the measured
case. A class's measured rate on a size (s4 market.throughput, from the
spend log) over this Mac's *best* rate on that size (any finished MLX voyage). Taking the Mac's best errs slow:
on 12 November the 4090's 9m rate was measured on the old 9m shape, and the v0.0.6 9m runs a third as fast here
per token, so the GPU's true lead on it is larger than the purser counts. A size the class has not sailed takes
its lead at the nearest size it has (the call's reason says "estimated"); a class that has sailed nothing has no
speed-up, and nothing goes to it. The quote at the hire stays cautious (s4 market.price: an unmeasured size is
priced no faster than this Mac), so a first voyage at a new size is given the Mac's own time before its deadline.

**Modes** (S5's `purser` term): `off`; `advisory`, which writes its call beside each line (s3.allocations, the
queue page) and routes nothing; `routing`, which sends the lines it calls foreign to the Vast lane. Advisory came
first, as decided. The account's credit is not the purser's to check: the charter's own gate refuses a hire the
credit cannot cover, and a line the purser sent abroad that fails there comes back to the Mac (lanes.py).
"""

from __future__ import annotations

import contextlib
import math
import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime

PLAN_EVERY_S = 300.0  # the coordinator re-plans at most this often while nothing changes
DEFAULT_CMD_MIN = 30.0  # a command with no time of its own (the queue page shows it as "no time")


@dataclass
class Call:
    """The purser's call on one queued line."""

    line: str
    name: str | None
    run_id: str | None
    expedition: str | None
    waters: str  # local or foreign
    reason: str
    gpu: str | None = None
    local_min: float | None = None
    local_home_min: float | None = None  # minutes from now until home, sailing here
    foreign_min: float | None = None
    foreign_home_min: float | None = None
    cost: float | None = None
    allowance: float | None = None
    eligible: bool = False  # a voyage the purser may move (whatever it called)

    def key(self) -> tuple:
        """What makes a call a different call (for the record: a row only when this changes)."""
        return (self.waters, self.gpu)


@dataclass
class World:
    """What the plan is made against, read once (so the plan itself is a pure function, and testable)."""

    now: float  # seconds since the epoch
    terms: dict  # S5's charter terms in force
    week_spent: float
    speedups: dict[tuple[str, str], float]  # (gpu, preset): the class's measured lead over this Mac
    prices: dict[str, float]  # gpu: dollars an hour, the market's last read (else the terms' ceiling)
    mac_free: list[float]  # when each Mac seat is free (seconds since the epoch)
    ship_free: list[float]  # when each ship the terms allow is free
    home_at: dict[str, float] = field(default_factory=dict)  # voyages at sea: when each is home, by name
    foreign_ok: bool = True  # the Vast lane is enabled and has a key
    setup_min: dict[str, float] = field(default_factory=dict)  # gpu: its measured overhead (set-up and home), minutes
    reserve: float = 1.0  # a hire counts against the allowance at its cost times this (S5's overrun)
    cycle_spent: float = 0.0  # dollars the hires of the cycle now running have cost so far (inside week_spent)
    cycle_held: float = 0.0  # and what is still held for the ships out: their quotes times the reserve, less that
    two_at_once: frozenset = frozenset({"300k"})  # presets that may share the Mac with a second of their size
    estimated: dict = field(default_factory=dict)  # (gpu, preset): the measured size its speed-up was carried from


def weekly_only(terms: dict) -> bool:
    """S5's `budget_release` is `week`: the week's budget is the one ceiling, released whole, not a cycle at a time
    (12 November, Justin: "the daily limit on vast is overkill, i prefer just the weekly limit"). A world whose
    terms name no release keeps the cycle's allowance, as it was built."""
    return str(terms.get("budget_release") or "cycle") == "week"


def ceiling_words(terms: dict) -> str:
    """What the allowance is called in a call's reason (the cycle's turn counts the calls it held by these words)."""
    return "the week's budget" if weekly_only(terms) else "the cycle's allowance"


def allowance_at(t: float, w: World) -> float:
    """The money the purser may have committed by a voyage sailing at `t`: this week's remaining budget spread
    evenly over its planning cycles left (the one now running counted), so each cycle releases its share and what
    one does not spend the next may; a voyage planned into next week draws on next week's budget in the same way.
    A cycle is S5's `cycle_hours` (24 where the terms name none: the day's allowance). Under `budget_release:
    week` the whole of what is left of the week is released at once, and next week's whole budget from Monday."""
    weekly = float(w.terms.get("weekly_budget", 0.0))
    # what this cycle has already spent and holds comes off its own share: without that every re-plan after a
    # ship came home found a whole new share waiting (12 November: three 9m voyages called foreign in one cycle
    # whose share carried two), and the cycle's ceiling was only a ceiling on what was planned at once
    spent, held = max(0.0, float(w.cycle_spent)), max(0.0, float(w.cycle_held))
    remaining = max(0.0, weekly - float(w.week_spent) + spent)  # what was left of the week when this cycle began
    cycle = max(1.0, float(w.terms.get("cycle_hours", 24.0))) * 3600
    now = datetime.fromtimestamp(w.now, UTC)
    monday = (datetime(now.year, now.month, now.day, tzinfo=UTC).timestamp() - now.weekday() * 86400)  # the spend log's week
    per_week = max(1, round(7 * 86400 / cycle))
    this = int((w.now - monday) // cycle)  # the cycle now running, counted from Monday 00:00 UTC
    left = max(1, per_week - this)
    k = max(0, int((t - monday) // cycle) - this)  # cycles from now until the voyage sails
    if weekly_only(w.terms):
        return max(0.0, remaining - spent - held) + (weekly if k >= left else 0.0)
    if k < left:
        return max(0.0, remaining * min(1.0, (k + 1) / left) - spent - held)
    return max(0.0, remaining - spent - held) + weekly * min(1.0, (k - left + 1) / per_week)


def cycle_start(now: float, terms: dict) -> float:
    """When the cycle now running began (cycles are counted from Monday 00:00 UTC, the spend log's week). Under
    `budget_release: week` the money's cycle is the week, so a ship hired last cycle and still out is held too."""
    cycle = max(1.0, float(terms.get("cycle_hours", 24.0))) * 3600
    d = datetime.fromtimestamp(now, UTC)
    monday = datetime(d.year, d.month, d.day, tzinfo=UTC).timestamp() - d.weekday() * 86400
    if weekly_only(terms):
        return monday
    return monday + int((now - monday) // cycle) * cycle


def cycle_money(log: list[dict], now: float, terms: dict) -> tuple[float, float]:
    """(spent, held) for the cycle now running, from S3's spend log: what its hires have cost so far (a ship still
    out at what it has run up), and what is still held for the ships out (each quote times S5's overrun, less
    what it has run up)."""
    start, reserve = cycle_start(now, terms), max(1.0, float(terms.get("overrun", 1.0)))
    gone = {r["instance"]: r for r in log if r["event"] == "released" and r.get("instance") is not None}
    spent = held = 0.0
    for h in log:
        if h["event"] != "hired" or h.get("instance") is None or float(h.get("started") or 0.0) < start:
            continue
        r = gone.get(h["instance"])
        if r is not None:
            cost = r.get("cost")
            if cost is None and r.get("at") and h.get("dph"):  # released by hand: its words only
                with contextlib.suppress(Exception):
                    cost = (datetime.fromisoformat(str(r["at"])).timestamp() - float(h["started"])) / 3600 * float(h["dph"])
            spent += float(cost or 0.0)
        else:
            run_up = max(0.0, (now - float(h["started"])) / 3600) * float(h.get("dph") or 0.0)
            spent += run_up
            held += max(0.0, float(h.get("quote") or 0.0) * reserve - run_up)
    return spent, held


def cycles_left(w: World) -> int:
    """The planning cycles left in this week, the one now running counted."""
    cycle = max(1.0, float(w.terms.get("cycle_hours", 24.0))) * 3600
    now = datetime.fromtimestamp(w.now, UTC)
    monday = datetime(now.year, now.month, now.day, tzinfo=UTC).timestamp() - now.weekday() * 86400
    return max(1, max(1, round(7 * 86400 / cycle)) - int((w.now - monday) // cycle))


def _lead_words(w: "World", gpu: str, preset: str | None, sp: float) -> str:
    """How a call's speed-up was known: measured on the size, or carried from the class's nearest measured size."""
    src = w.estimated.get((gpu, preset or ""))
    return f"estimated {sp:.1f}x, the lead measured on its {src}" if src else f"measured {sp:.1f}x"


def _fmt_h(minutes: float) -> str:
    return f"{minutes / 60:.1f} h"


def plan(lines: list, w: World, estimate, cmd_estimate, eligible) -> list[Call]:
    """The calls, one per queued line, in the queue's order.

    `lines` are lanes.Line objects (or anything with text, lane, kind, payload, spec, name, run_id, reads);
    `estimate(line) -> (minutes | None, source)` is the line's time on this Mac; `cmd_estimate(line) -> minutes`
    a command's; `eligible(line) -> (expedition, None) | (expedition, why not)` says whether the purser may move
    a voyage (the expedition allowed abroad, the line not pinned)."""
    t = w.terms
    mac = sorted(w.mac_free) or [w.now]
    ships = sorted(w.ship_free) or [w.now]
    home = dict(w.home_at)
    committed = 0.0
    held = False  # past a hold: nothing behind it is routed
    margin_h = float(t.get("margin_hours", 1.0))
    margin_f = float(t.get("margin_fraction", 0.25))
    voyage_budget = float(t.get("voyage_budget", 0.0))
    const_min = 60.0 * _setup_hours()  # S5's constant, for a class with no measurement in the world
    overhead = lambda gpu: float(w.setup_min.get(gpu, const_min))  # noqa: E731
    reserve = max(1.0, float(w.reserve or 1.0))
    out: list[Call] = []

    def ready(ln) -> float:
        return max([w.now] + [home[r] for r in (getattr(ln, "reads", None) or []) if r in home])

    def sail_here(dur: float, after: float, preset: str | None) -> float:
        """Take a Mac seat (the coordinator's capacity rule: a 300k may share, anything else takes the lane)."""
        if preset in w.two_at_once and len(mac) > 1:
            i = min(range(len(mac)), key=lambda k: mac[k])
            start = max(mac[i], after)
            mac[i] = start + dur * 60
            return mac[i]
        start = max(max(mac), after)
        for k in range(len(mac)):
            mac[k] = start + dur * 60
        return start + dur * 60

    for ln in lines:
        kind = getattr(ln, "kind", "spec")
        text = ln.text
        if kind == "hold":
            if getattr(ln, "lane", "mac") == "mac":
                held = True
                mac[:] = [math.inf] * len(mac)
            out.append(Call(text, None, None, None, "local", "a hold: nothing behind it is moved"))
            continue
        if kind == "wait":
            until = home.get(ln.payload, w.now)
            mac[:] = [max(m, until) for m in mac]
            out.append(Call(text, None, None, None, "local", f"waits for {ln.payload}"))
            continue
        if kind in ("cmd", "intelligence"):
            dur = float(cmd_estimate(ln) or DEFAULT_CMD_MIN)
            end = sail_here(dur, w.now, None)
            out.append(Call(text, None, None, None, "local", "a command runs here", local_min=dur,
                            local_home_min=_mins(end, w.now)))  # fmt: skip
            continue
        preset = str(((getattr(ln, "spec", None) or {}).get("model") or {}).get("preset") or "") or None
        local_min, _src = estimate(ln)
        exp, why_not = eligible(ln)
        if getattr(ln, "lane", "mac") != "mac":  # pinned abroad (`vast:` or a torch spec): it takes a ship
            dur = _foreign_minutes(local_min, preset, w, const_min)
            i = min(range(len(ships)), key=lambda k: ships[k])
            start = max(ships[i], ready(ln))
            ships[i] = start + (dur or 0) * 60
            if ln.name:
                home[ln.name] = ships[i]
            out.append(Call(text, ln.name, ln.run_id, exp, "foreign", "pinned to the Vast lane",
                            foreign_min=dur, foreign_home_min=_mins(ships[i], w.now)))  # fmt: skip
            continue
        if local_min is None:
            end = sail_here(0.0, ready(ln), preset)
            out.append(Call(text, ln.name, ln.run_id, exp, "local", "no time to plan it by (it stays here)"))
            continue
        local_start = max(max(mac) if preset not in w.two_at_once or len(mac) == 1 else min(mac), ready(ln))
        local_home = local_start + local_min * 60
        reason = None
        if held:
            reason = "behind a hold"
        elif why_not:
            reason = why_not
        elif not w.foreign_ok:
            reason = "the Vast lane cannot hire (disabled, or no key)"
        best = None
        if reason is None:
            for gpu, price in w.prices.items():
                sp = w.speedups.get((gpu, preset or ""))
                if not sp or sp <= 1.0:
                    continue
                dur = local_min / sp + overhead(gpu)
                i = min(range(len(ships)), key=lambda k: ships[k])
                start = max(ships[i], ready(ln))
                cand = {"gpu": gpu, "dur": dur, "home": start + dur * 60, "start": start, "seat": i,
                        "cost": dur / 60 * price, "speedup": sp}  # fmt: skip
                if best is None or (cand["home"], cand["cost"]) < (best["home"], best["cost"]):
                    best = cand
            if best is None:
                reason = f"no GPU class has a measured speed-up at {preset} yet"
        call = Call(text, ln.name, ln.run_id, exp, "local", "", local_min=local_min,
                    local_home_min=_mins(local_home, w.now), eligible=reason is None)  # fmt: skip
        if best is not None:
            gain = (local_home - best["home"]) / 60
            wait = (local_home - w.now) / 60
            allow = allowance_at(best["start"], w) - committed
            call.gpu, call.foreign_min = best["gpu"], best["dur"]
            call.foreign_home_min, call.cost, call.allowance = _mins(best["home"], w.now), best["cost"], allow
            if best["cost"] > voyage_budget:
                reason = f"abroad it would cost ${best['cost']:.2f}, over one voyage's ${voyage_budget:.2f}"
            elif best["cost"] * reserve > allow:
                held = f" (counted at ${best['cost'] * reserve:.2f}, the quote times the overrun)" if reserve > 1 else ""
                reason = f"abroad it would cost ${best['cost']:.2f}{held}, over the ${allow:.2f} left in {ceiling_words(w.terms)}"
            elif gain < margin_h * 60 or gain < margin_f * wait:
                reason = (f"abroad it is home only {_fmt_h(max(gain, 0))} sooner (the margin is {margin_h:g} h "
                          f"and {margin_f:.0%} of its {_fmt_h(wait)} wait)")  # fmt: skip
            else:
                call.waters = "foreign"
                call.reason = (f"foreign: home {_fmt_h(gain)} sooner on an {best['gpu']} for ${best['cost']:.2f}, "
                               f"inside the ${allow:.2f} {ceiling_words(w.terms)} has left ("
                               f"{_lead_words(w, best['gpu'], preset, best['speedup'])})")  # fmt: skip
                committed += best["cost"] * reserve
                ships[best["seat"]] = best["home"]
                if ln.name:
                    home[ln.name] = best["home"]
        if call.waters == "local":
            call.reason = f"local: {reason}" if reason else "local"
            end = sail_here(local_min, ready(ln), preset)
            call.local_home_min = _mins(end, w.now)
            if ln.name:
                home[ln.name] = end
        out.append(call)
    return out


def _mins(t: float, now: float) -> float | None:
    return None if math.isinf(t) else max(0.0, (t - now) / 60)


def _foreign_minutes(local_min, preset, w: World, const_min: float) -> float | None:
    """A pinned voyage's time abroad, for the ships' schedule: at the best measured class (with that class's
    measured overhead), else as here."""
    if local_min is None:
        return None
    sps = [(sp, g) for (g, p), sp in w.speedups.items() if p == (preset or "") and g in w.prices and sp > 0]
    if not sps:
        return local_min + const_min
    sp, g = max(sps)
    return local_min / sp + float(w.setup_min.get(g, const_min))


def _setup_hours() -> float:
    from thorp.viable.s5_policy import charter as s5

    return float(s5.SETUP_HOURS)


# ---------------------------------------------------------------- reading the world (the store, the ledger)


def mode(terms: dict | None = None) -> str:
    from thorp.viable.s5_policy import charter as s5

    m = str((terms or s5.terms()).get("purser") or "off")
    return m if m in s5.PURSER_MODES else "off"


def speedups(terms: dict, mac_best: dict[str, float], estimated: dict | None = None) -> dict[tuple[str, str], float]:
    """(gpu, preset): the class's measured rate on the size over this Mac's best rate on it. A size the class has not
    sailed takes the class's measured lead at its nearest measured size (12 November, Justin: "the purser rule is
    wrong", when every 300k and 1m line stayed on the Mac because only the 9m had sailed abroad). The lead is
    carried, not the rate: a rate scaled down by FLOPs from a bigger size overstates a GPU that a small model leaves
    mostly idle. A class that has sailed nothing gets nothing (no datasheet guesses). `estimated`, when given, is
    filled with {(gpu, preset): the measured size it was carried from}."""
    from thorp.models import registry
    from thorp.viable.s4_intelligence import market

    order = list(registry.PRESETS)
    out = {}
    for gpu in terms.get("gpus") or {}:
        measured = {}
        for preset, mac in mac_best.items():
            with contextlib.suppress(Exception):
                tps = market.throughput(gpu, preset)
                if tps and mac:
                    measured[preset] = tps / mac
        out.update({(gpu, p): sp for p, sp in measured.items()})
        known = [p for p in measured if p in order]
        if not known:
            continue
        for preset in mac_best:
            if preset in measured or preset not in order:
                continue
            near = min(known, key=lambda p: (abs(order.index(p) - order.index(preset)), order.index(p)))
            out[(gpu, preset)] = measured[near]
            if estimated is not None:
                estimated[(gpu, preset)] = near
    return out


def mac_best_rates(rows: list[dict]) -> dict[str, float]:
    """This Mac's best wall-clock rate (tokens a second, readings and all) per preset, over finished MLX voyages
    of a real length (ten minutes or more, so a smoke test's warm-up cannot pass for a rate)."""
    import json

    best: dict[str, float] = {}
    for r in rows:
        if r.get("status") != "finished" or not r.get("tokens_seen") or not (r.get("wall_minutes") or 0) >= 10:
            continue
        try:
            m = (json.loads(r.get("spec_json") or "{}").get("model") or {})
        except ValueError:
            continue
        if (m.get("backend") or "mlx") != "mlx" or not m.get("preset"):
            continue
        rate = float(r["tokens_seen"]) / (float(r["wall_minutes"]) * 60)
        best[m["preset"]] = max(best.get(m["preset"], 0.0), rate)
    return best


def overheads(terms: dict) -> dict[str, float]:
    """Each class's measured overhead in minutes, set-up and home (s4 hires.setup); a class that cannot be read is
    left out, and the plan charges it S5's constant."""
    out: dict[str, float] = {}
    with contextlib.suppress(Exception):
        from thorp.viable.s4_intelligence import hires

        rows = hires.timings()
        for gpu in terms.get("gpus") or {}:
            with contextlib.suppress(Exception):
                out[gpu] = float(hires.setup(gpu, rows=rows)["total_min"])
    return out


def prices(terms: dict) -> dict[str, float]:
    """Each class's last price on the market (s4.market_reads), else the terms' ceiling for it."""
    from thorp.viable.s4_intelligence import market

    out = {g: float(c) for g, c in (terms.get("gpus") or {}).items()}
    with contextlib.suppress(Exception):
        latest: dict[str, tuple[str, float]] = {}
        for r in market.reads(500):
            g, at = r.get("gpu"), str(r.get("at") or "")
            if g in out and r.get("dph") and (g not in latest or at > latest[g][0]):
                latest[g] = (at, float(r["dph"]))
        for g, (_, dph) in latest.items():
            out[g] = min(dph, out[g])
    return out


def cmd_minutes(ln) -> float | None:
    """A command's time, as the queue page reads it: an investigation's estimate, the line's own `# estimate`,
    two minutes for the coordinator's restart, else its deadline as an upper bound."""
    from thorp import investigate

    with contextlib.suppress(Exception):
        spec = investigate.of_line(ln.text)
        if spec is not None:
            return investigate.estimate(spec)[0]
    m = re.search(r"#\s*estimate\s+(\d+\s*[smh]?)\s*$", ln.text)
    if m:
        return investigate.seconds(m.group(1)) / 60
    if "restart_coordinator.sh" in ln.text:
        return 2.0
    m = re.search(r"\[timeout=(\d+[smh]?)\]", ln.text)
    if m:
        return investigate.seconds(m.group(1)) / 60
    return None


def eligibility(terms: dict):
    """The purser's rule for which voyages it may move: not pinned, and of an expedition allowed abroad."""
    from thorp import fleet
    from thorp.viable.s2_coordination import lanes

    allowed = set(terms.get("foreign_expeditions") or [])

    def eligible(ln) -> tuple[str | None, str | None]:
        exp = None
        with contextlib.suppress(Exception):
            exp = fleet.expedition_of_spec(ln.spec or {})
        if lanes.pinned(ln.text):
            return exp, "pinned to its lane"
        if ((ln.spec or {}).get("model") or {}).get("backend") == "torch":
            return exp, "written for CUDA"
        if not ln.spec:
            return exp, "its spec cannot be read"
        if exp not in allowed:
            return exp, f"its expedition ({exp or 'none'}) is local (S5's foreign_expeditions: {', '.join(sorted(allowed)) or 'none'})"
        return exp, None

    return eligible


def world(lines_at_sea: list[dict] | None = None, now: float | None = None) -> tuple[World, object]:
    """Read everything the plan needs once: the terms, the week's spend, the market, the measured rates, the
    seats and what is at sea. Returns the world and the RunTimes it was read with (the line estimates)."""
    from thorp.dash.timing import RunTimes
    from thorp.ledger import reader
    from thorp.viable.s2_coordination import lanes, queue_store
    from thorp.viable.s3_control import charter as s3
    from thorp.viable.s5_policy import charter as s5

    now = time.time() if now is None else now
    terms = s5.terms()
    rows = reader().query("select name, status, wall_minutes, tokens_seen, spec_json from s1.runs")
    times = RunTimes(rows)
    defs = lanes.lane_defs()
    mac_seats = max(1, lanes.slots_of("mac"))
    ships = max(1, int(terms.get("max_instances", 1)))
    mac_free, ship_free, home = [now] * mac_seats, [now] * ships, {}
    sea = queue_store.at_sea() if lines_at_sea is None else lines_at_sea
    mi = si = 0
    for r in sea:
        ln = lanes.parse(r["text"])
        gone = (now - float(r.get("started_ts") or now)) / 60
        if ln.kind in ("cmd", "intelligence"):
            est = cmd_minutes(ln) or DEFAULT_CMD_MIN
        else:
            est = times.estimate(ln.name or "", ln.spec or {})[0] or 0.0
        end = now + max(0.0, est - gone) * 60
        if r.get("lane") == "mac" and mi < len(mac_free):
            mac_free[mi] = end
            mi += 1
        elif r.get("lane") != "mac" and si < len(ship_free):
            ship_free[si] = end
            si += 1
        if ln.name:
            home[ln.name] = end
    spent, held = 0.0, 0.0
    with contextlib.suppress(Exception):
        spent, held = cycle_money(s3.log(), now, terms)
    carried: dict = {}  # filled by speedups: the sizes estimated from another
    w = World(
        now=now,
        terms=terms,
        cycle_spent=spent,
        cycle_held=held,
        week_spent=s3.week_spent(),
        speedups=speedups(terms, mac_best_rates(rows), carried),
        estimated=carried,
        prices=prices(terms),
        mac_free=mac_free,
        ship_free=ship_free,
        home_at=home,
        foreign_ok=bool("vast" in defs and defs["vast"].enabled and lanes.has_key()),
        two_at_once=frozenset(lanes.TWO_AT_ONCE),
        setup_min=overheads(terms),
        reserve=float(terms.get("overrun", 1.0)),
    )
    return w, times


def calls_for(lines: list, now: float | None = None) -> list[Call]:
    """The purser's calls on these queued lines (lanes.Line objects), read against the world now."""
    w, times = world(now=now)

    def estimate(ln):
        return times.estimate(ln.name or "", ln.spec or {})

    return plan(lines, w, estimate, cmd_minutes, eligibility(w.terms))


# ---------------------------------------------------------------- the record (s3.allocations)


def latest() -> dict[str, dict]:
    """The latest call kept for each line, by its text."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import Allocation

    out: dict[str, dict] = {}
    with store.session() as s:
        for r in s.scalars(select(Allocation).order_by(Allocation.id)):
            out[r.line] = {c.name: getattr(r, c.name) for c in Allocation.__table__.columns}
    return out


def record(calls: list[Call], mode_: str, applied: bool, last: dict[str, tuple] | None = None) -> dict[str, tuple]:
    """Write the calls whose waters or class changed since the line's last kept call (every call of a voyage the
    purser may move; the rest are not its decisions). Returns the keys now kept, for the next round."""
    from thorp import store
    from thorp.viable.records import Allocation

    if last is None:
        last = {k: (v["waters"], v["gpu"]) for k, v in latest().items()}
    new = [c for c in calls if (c.eligible or c.waters == "foreign") and last.get(c.line) != c.key()]
    if new:
        with store.session() as s:
            for c in new:
                s.add(Allocation(line=c.line, name=c.name, run_id=c.run_id, expedition=c.expedition, waters=c.waters,
                                 gpu=c.gpu, local_min=c.local_min, local_home_min=c.local_home_min,
                                 foreign_min=c.foreign_min, foreign_home_min=c.foreign_home_min, cost=c.cost,
                                 allowance=c.allowance, mode=mode_, applied=applied and c.waters == "foreign" and c.eligible,
                                 reason=c.reason))  # fmt: skip
    return {**last, **{c.line: c.key() for c in new}}


class Steward:
    """The purser at the coordinator's side: re-plans when the queue or what is at sea changes (and at least every
    PLAN_EVERY_S), keeps its calls, and in `routing` mode sends the lines it calls foreign to the Vast lane. It
    never raises: a purser that cannot read the world leaves every line in the lane it was written for."""

    def __init__(self, say=print):
        self.say = say
        self.calls: dict[str, Call] = {}
        self.sig: tuple | None = None
        self.at = float("-inf")
        self.kept: dict[str, tuple] | None = None
        self.told: str | None = None

    def steer(self, lines: list, at_sea_texts: list[str]) -> list:
        try:
            m = mode()
        except Exception as e:  # noqa: BLE001
            self._tell(f"S3 purser: cannot read its terms ({e}); nothing is routed")
            return lines
        if m == "off":
            return lines
        sig = (tuple(x.text for x in lines), tuple(sorted(at_sea_texts)), m)
        if sig != self.sig or time.monotonic() - self.at > PLAN_EVERY_S:
            try:
                calls = calls_for(lines)
            except Exception as e:  # noqa: BLE001 - the queue sails on without the purser
                self._tell(f"S3 purser: could not plan ({e}); lines sail where they are written")
                return lines
            self.calls = {c.line: c for c in calls}
            self.sig, self.at = sig, time.monotonic()
            try:
                self.kept = record(calls, m, m == "routing", self.kept)
            except Exception as e:  # noqa: BLE001 - a record must never stop the queue
                self._tell(f"S3 purser: could not keep its calls ({e})")
            foreign = [c for c in calls if c.waters == "foreign" and c.eligible]
            self._tell(f"S3 purser ({m}): {len(foreign)} line(s) called foreign"
                       + (": " + ", ".join(c.name or c.line for c in foreign[:6]) if foreign else ""))  # fmt: skip
        if m != "routing":
            return lines
        for ln in lines:
            c = self.calls.get(ln.text)
            if c is not None and c.waters == "foreign" and c.eligible and ln.lane == "mac":
                ln.lane, ln.routed = "vast", True
        return lines

    def _tell(self, msg: str) -> None:
        if msg != self.told:
            self.say(msg)
            self.told = msg


def main(argv: list[str] | None = None) -> int:
    """`python -m thorp.viable.s3_control.purser`: the purser's calls on the queue now, line by line (writes
    nothing; `--keep` also keeps the changed calls in s3.allocations, as the coordinator does)."""
    import argparse

    from thorp.viable.s2_coordination import lanes

    ap = argparse.ArgumentParser(prog="purser", description=main.__doc__)
    ap.add_argument("--keep", action="store_true", help="keep the changed calls in s3.allocations")
    ap.add_argument("--all", action="store_true", help="every line, not only the voyages it may move")
    a = ap.parse_args(argv)
    from thorp.viable.s2_coordination import queue_read

    lines = [lanes.parse(t) for t in queue_read.pending()]
    calls = calls_for(lines)
    m = mode()
    print(f"purser: {m}")
    for i, c in enumerate(calls, 1):
        if not (a.all or c.eligible or c.waters == "foreign"):
            continue
        here = f"{c.local_home_min / 60:5.1f} h" if c.local_home_min is not None else "    -  "
        print(f"{i:3} {c.waters:7} {(c.name or c.line)[:40]:40} home here {here}  {c.reason}")
    foreign = [c for c in calls if c.waters == "foreign" and c.eligible]
    cost = sum(c.cost or 0 for c in foreign)
    local_end = max((c.local_home_min or 0) for c in calls if c.waters == "local") if calls else 0
    ships_end = max((c.foreign_home_min or 0) for c in foreign) if foreign else 0
    print(f"\n{len(foreign)} abroad for ${cost:.2f}; the Mac's last line home in {local_end / 60:.1f} h, "
          f"the last ship's in {ships_end / 60:.1f} h")
    if a.keep:
        record(calls, m, m == "routing")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""S3's purser (thorp/viable/s3_control/purser.py): which waters each queued voyage sails in, by greedy list
scheduling under S5's terms, and the coordinator's side of it (a `mac:` pin, a failure abroad that comes home)."""

from __future__ import annotations

from datetime import UTC, datetime

from thorp.viable.s2_coordination import lanes
from thorp.viable.s3_control import purser

# a Monday, 00:00 UTC: the week's first day, so the day's allowance is a seventh of what is left
MONDAY = datetime(2026, 11, 16, tzinfo=UTC).timestamp()
H = 3600.0

TERMS = {
    "weekly_budget": 30.0, "voyage_budget": 10.0, "margin_hours": 1.0, "margin_fraction": 0.25,
    "foreign_expeditions": ["kipling"], "gpus": {"RTX 4090": 0.5},
}  # fmt: skip


def voyage(name: str, preset: str = "9m", exp: str = "kipling", text: str | None = None, reads=()) -> lanes.Line:
    lane, _ = lanes.split_lane(text or f"fitouts/{name}")
    return lanes.Line(text or f"fitouts/{name}", lane, "spec", f"fitouts/{name}", spec={"model": {"preset": preset},
                      "expedition": exp, "name": name}, name=name, run_id=f"r-{name}", reads=list(reads))  # fmt: skip


def world(**kw) -> purser.World:
    base = dict(now=MONDAY, terms=TERMS, week_spent=0.0, speedups={("RTX 4090", "9m"): 2.0},
                prices={"RTX 4090": 0.4}, mac_free=[MONDAY], ship_free=[MONDAY])  # fmt: skip
    base.update(kw)
    return purser.World(**base)


MINUTES = {"9m": 240.0, "300k": 30.0, "1m": 45.0}


def calls(lines, w):
    def estimate(ln):
        return MINUTES[ln.spec["model"]["preset"]], "test"

    def eligible(ln):
        exp = ln.spec.get("expedition")
        if lanes.pinned(ln.text):
            return exp, "pinned to its lane"
        return (exp, None) if exp in w.terms["foreign_expeditions"] else (exp, "local expedition")

    return purser.plan(lines, w, estimate, lambda ln: 10.0, eligible)


def test_a_long_voyage_behind_a_queue_goes_abroad_and_a_short_one_stays():
    lines = [voyage("a"), voyage("b"), voyage("c", preset="300k")]
    a, b, c = calls(lines, world())
    # 4 h here, 2.35 h abroad (half the time and the set-up): home 1.65 h sooner, 41% of its wait
    assert a.waters == "foreign" and a.gpu == "RTX 4090"
    assert abs(a.foreign_min - (240 / 2 + 21)) < 1e-6 and abs(a.cost - a.foreign_min / 60 * 0.4) < 1e-9
    assert "home" in a.reason and "sooner" in a.reason
    assert b.waters == "local"  # the ship is out with a until 2.35 h: abroad b is home at 4.7 h, here at 4 h
    assert c.waters == "local" and "no GPU class has a measured speed-up at 300k" in c.reason


def test_never_routes_an_expedition_kept_local_a_pin_or_past_a_hold():
    lines = [voyage("a"), voyage("x", exp="card_census"), voyage("p", text="mac: fitouts/p"),
             lanes.Line("hold: the sign-off", "mac", "hold", "the sign-off"), voyage("after")]  # fmt: skip
    got = calls(lines, world())
    assert [c.waters for c in got] == ["foreign", "local", "local", "local", "local"]
    assert "local expedition" in got[1].reason and "pinned" in got[2].reason and "behind a hold" in got[4].reason


def test_the_margin_and_the_days_allowance_hold_a_hire_back():
    lines = [voyage("a"), voyage("b")]
    # a ship that is busy for 3 h more: abroad b is home at 5.35 h, here at 8 h: 2.65 h sooner, 33% of its wait
    assert calls(lines, world(ship_free=[MONDAY + 3 * H]))[1].waters == "foreign"
    # busy for 5 h: home 7.35 h abroad against 8 h here, under the 1 h margin
    late = calls(lines, world(ship_free=[MONDAY + 5 * H]))[1]
    assert late.waters == "local" and "margin" in late.reason
    # Monday's allowance is a seventh of the week's $30; with $29.50 spent, $0.07 a day cannot pay $0.94
    poor = calls(lines, world(week_spent=29.5))[1]
    assert poor.waters == "local" and "allowance" in poor.reason


def test_the_intelligence_audit_takes_the_mac_as_a_command():
    """12 November: S4's audit is its own queue item type, but the purser still times it as a command and never
    sends it abroad."""
    audit = calls([lanes.parse(lanes.AUDIT_LINE)], world())[0]
    assert audit.waters == "local" and audit.local_min == 10.0  # the test's cmd_estimate


def test_the_allowance_releases_a_day_at_a_time():
    w = world(week_spent=2.0)
    assert abs(purser.allowance_at(MONDAY, w) - 28 / 7) < 1e-9
    assert abs(purser.allowance_at(MONDAY + 2.5 * 86400, w) - 3 * 28 / 7) < 1e-9
    assert abs(purser.allowance_at(MONDAY + 6.9 * 86400, w) - 28) < 1e-9
    assert abs(purser.allowance_at(MONDAY + 7.5 * 86400, w) - (28 + 30 / 7)) < 1e-9  # into next week


def test_a_voyage_waits_for_what_it_reads_and_the_vast_lane_needs_a_key():
    lines = [voyage("a"), voyage("b"), voyage("seeded", reads=["b"])]
    a, b, s = calls(lines, world())
    assert (a.waters, b.waters) == ("foreign", "local")
    # the seeded leg cannot start before b is home (here, at 4 h); abroad it would be home at 6.35 h, 1.65 h
    # sooner but under 25% of its 8 h wait, so it stays
    assert s.waters == "local" and abs(s.local_home_min - (b.local_home_min + 240)) < 1e-6
    assert all(c.waters == "local" for c in calls(lines, world(foreign_ok=False)))


def test_mac_is_a_pin_the_lane_reads():
    assert lanes.split_lane("mac: fitouts/x") == ("mac", "fitouts/x")
    assert lanes.pinned("mac: fitouts/x") and lanes.pinned("vast: fitouts/x")
    assert not lanes.pinned("fitouts/x") and not lanes.pinned("cmd: echo hi")


def test_the_steward_routes_only_in_routing_mode(monkeypatch):
    lines = [voyage("a"), voyage("b")]
    monkeypatch.setattr(purser, "calls_for", lambda ls, now=None: calls(ls, world()))
    monkeypatch.setattr(purser, "record", lambda c, m, applied, last=None: {})
    said = []
    monkeypatch.setattr(purser, "mode", lambda terms=None: "advisory")
    out = purser.Steward(said.append).steer([voyage("a"), voyage("b")], [])
    assert [x.lane for x in out] == ["mac", "mac"] and "1 line(s) called foreign" in said[-1]
    monkeypatch.setattr(purser, "mode", lambda terms=None: "routing")
    out = purser.Steward(said.append).steer(lines, [])
    assert [(x.lane, x.routed) for x in out] == [("vast", True), ("mac", False)]


def test_a_steward_that_cannot_plan_leaves_the_lines_alone(monkeypatch):
    monkeypatch.setattr(purser, "mode", lambda terms=None: "routing")

    def broken(ls, now=None):
        raise RuntimeError("no ledger")

    monkeypatch.setattr(purser, "calls_for", broken)
    said = []
    out = purser.Steward(said.append).steer([voyage("b")], [])
    assert out[0].lane == "mac" and "could not plan" in said[-1]


def test_a_routed_voyage_that_fails_abroad_comes_home_pinned(monkeypatch):
    from thorp.viable.s2_coordination import queue_store

    monkeypatch.setattr(lanes, "_queue_pg", lambda: True)
    ln = voyage("b")
    ln.lane, ln.routed = "vast", True
    lanes._come_home(None, ln, print)
    assert queue_store.pending_texts()[0] == "mac: fitouts/b"


def test_the_calls_are_kept_only_when_they_change():
    from thorp.viable.s3_control import purser as p

    got = calls([voyage("a"), voyage("b")], world())
    kept = p.record(got, "advisory", False, last={})
    assert kept == {"fitouts/a": ("foreign", "RTX 4090"), "fitouts/b": ("local", "RTX 4090")}
    rows = p.latest()
    assert rows["fitouts/a"]["waters"] == "foreign" and rows["fitouts/a"]["applied"] is False
    assert p.record(got, "advisory", False, last=kept) == kept  # nothing changed: nothing written
    assert len(p.latest()) == 2


def test_a_size_no_class_has_sailed_takes_the_lead_of_the_nearest_measured_size(monkeypatch):
    # 12 November, Justin: "the purser rule is wrong": only the 9m had sailed abroad, so every 300k and 1m stayed here
    from thorp.viable.s4_intelligence import market

    monkeypatch.setattr(market, "throughput", lambda gpu, preset: 200.0 if (gpu, preset) == ("RTX 4090", "9m") else None)
    terms = {**TERMS, "gpus": {"RTX 4090": 0.5, "H100 SXM": 2.6}}
    carried: dict = {}
    sp = purser.speedups(terms, {"300k": 400.0, "1m": 100.0, "9m": 100.0, "300k-h4": 90.0}, carried)
    assert sp[("RTX 4090", "9m")] == 2.0  # measured
    assert sp[("RTX 4090", "1m")] == 2.0 and sp[("RTX 4090", "300k")] == 2.0  # the 9m's lead, carried
    assert carried == {("RTX 4090", "1m"): "9m", ("RTX 4090", "300k"): "9m"}
    assert not any(g == "H100 SXM" for g, _ in sp)  # a class that has sailed nothing is not guessed
    assert ("RTX 4090", "300k-h4") not in sp  # a variant off the ladder is not carried to


def test_an_estimated_lead_sends_a_waiting_voyage_abroad_and_says_it_was_estimated():
    w = world(speedups={("RTX 4090", "300k"): 2.0}, estimated={("RTX 4090", "300k"): "9m"},
              mac_free=[MONDAY + 10 * H])  # the Mac is busy for ten hours  # fmt: skip
    (c,) = calls([voyage("small", preset="300k")], w)
    assert c.waters == "foreign" and "estimated 2.0x, the lead measured on its 9m" in c.reason
    (m,) = calls([voyage("small", preset="300k")], world(speedups={("RTX 4090", "300k"): 2.0}, mac_free=[MONDAY + 10 * H]))
    assert m.waters == "foreign" and "measured 2.0x" in m.reason

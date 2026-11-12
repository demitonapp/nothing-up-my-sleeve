"""The queue's planning cycle (12 November): what a hire's time went on (S1 Phases, S4 hires), the purser's
cycle allowance and its overrun reserve (S3), the fleet chosen and what is proposed (S3 cycle), the audit's
plan against actual (S3*), and reading the judge's answer (S4 judge). All pure: no store, no hire."""

from __future__ import annotations

from datetime import UTC, datetime

from thorp.viable.s1_operations.charter import Phases
from thorp.viable.s2_coordination import lanes
from thorp.viable.s3_control import cycle, purser
from thorp.viable.s3star_audit import cycle as s3star
from thorp.viable.s4_intelligence import hires, judge

MONDAY = datetime(2026, 11, 16, tzinfo=UTC).timestamp()
H = 3600.0


class Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


# ---------------------------------------------------------------- S1: the phases a hire records


def test_a_hire_that_sails_records_its_set_up_its_training_and_its_way_home():
    c = Clock()
    ph = Phases(1000.0, c)
    for name, secs, mb in (("ssh", 25, None), ("code", 200, 113.0), ("data", 15, 650.0), ("board", 400, None),
                           ("env", 30, None), ("train", 360, None), ("home", 4000, None)):  # fmt: skip
        c.t += secs
        ph.mark(name, mb)
    c.t += 480
    r = ph.record(c.t)
    assert r["sailed"] and r["failed_in"] is None
    assert r["phases"]["provision"] == 25 and r["phases"]["data"] == 400 and r["mb"] == {"code": 113.0, "data": 650.0}
    assert r["setup_s"] == 25 + 200 + 15 + 400 + 30 + 360  # everything before the run
    assert r["train_s"] == 4000 and r["home_s"] == 480


def test_a_hire_that_dies_fitting_out_says_which_step_it_died_in():
    c = Clock()
    ph = Phases(1000.0, c)
    c.t += 30
    ph.mark("ssh")
    c.t += 200
    ph.mark("code")
    c.t += 20
    ph.mark("data", 9070.0)
    c.t += 3300
    r = ph.record(c.t)
    assert not r["sailed"] and r["failed_in"] == "data" and r["train_s"] is None
    assert r["setup_s"] == 30 + 200 + 20 + 3300


def test_a_ship_taken_up_knows_only_how_long_its_fit_out_was():
    c = Clock(5000.0)
    r = Phases.taken_up(1000.0, 2800.0, c).record(5000.0)
    assert r["sailed"] and r["setup_s"] == 1800 and r["train_s"] == 2200


# ---------------------------------------------------------------- S4: what the records say


def _log():
    hired = lambda i, gpu, **k: {"at": "2026-11-12T00:00:00+00:00", "event": "hired", "instance": i, "gpu": gpu, "dph": 0.4,  # noqa: E731
                                 "run_id": f"r{i}", "name": f"v{i}", "preset": "9m", "started": 1000.0 * i, **k}  # fmt: skip
    rel = lambda i, gpu, secs, **k: {"at": "2026-11-12T01:00:00+00:00", "event": "released", "instance": i, "gpu": gpu,  # noqa: E731
                                     "dph": 0.4, "run_id": f"r{i}", "started": 1000.0 * i, "ended": 1000.0 * i + secs,
                                     "cost": secs / 3600 * 0.4, "preset": "9m", **k}  # fmt: skip
    return [
        hired(1, "RTX 4090", quote_hours=1.0, quote=0.4),
        rel(1, "RTX 4090", 6000, status="home", tokens_per_s=100.0),  # sailed, nothing timed its steps
        hired(2, "RTX 4090"),
        rel(2, "RTX 4090", 4400, status="recalled (SIGTERM)"),  # a fit-out that died
        hired(3, "RTX 4090"),
        rel(3, "RTX 4090", 80, status="recalled (SIGTERM)"),  # stopped by hand at once: not a failure
        hired(4, "RTX 4090"),
        rel(4, "RTX 4090", 3000, status="home", phases={"provision": 30, "ssh": 60, "code": 20, "data": 100, "board": 10,
            "env": 300, "train": 2300, "home": 180}, mb={"data": 800.0}, setup_s=520.0, train_s=2300.0, home_s=180.0,
            sailed=True, failed_in=None),  # the charter's own measurement
        {"at": "2026-11-12T02:00:00+00:00", "event": "hired", "instance": 5, "gpu": "RTX 5090", "dph": 0.5, "run_id": "r5",
         "name": "v5", "started": 9000.0},
        {"at": datetime.fromtimestamp(9000.0 + 900, UTC).isoformat(), "event": "released", "instance": 5,
         "why": "box refused ssh; released", "name": "v5"},  # released by hand: only its words
        {"at": "2026-11-12T03:00:00+00:00", "event": "released", "instance": 6, "run_id": "smoke-rtx-4090-1", "gpu": "RTX 4090",
         "started": 1.0, "ended": 100.0, "cost": 0.01, "status": "smoke ok"},
    ]  # fmt: skip


def _rows():
    return hires.timings(_log(), from_log={}, run_minutes=lambda rid: 70.0 if rid == "r1" else None)


def test_every_hire_is_timed_from_whatever_record_it_left():
    rows = {r["instance"]: r for r in _rows()}
    assert rows[1]["sailed"] and rows[1]["train_s"] == 4200 and rows[1]["setup_s"] == 1800  # the run's own clock
    assert rows[4]["source"] == hires.MEASURED and rows[4]["setup_s"] == 520.0
    assert not rows[2]["sailed"] and rows[2]["setup_s"] == 4400  # it never sailed: all of it was fit-out
    assert rows[5]["gpu"] == "RTX 5090" and rows[5]["why"].startswith("box refused") and round(rows[5]["total_s"]) == 900
    assert rows[6]["kind"] == "smoke"


def test_a_class_is_planned_on_the_charters_own_measurements_once_it_has_any():
    rows = _rows()
    st = hires.setup("RTX 4090", rows=rows)
    assert round(st["setup_min"], 2) == round(520 / 60, 2) and round(st["home_min"], 1) == 3.0 and st["n"] == 1
    assert "reconstructed" not in st["source"]
    # a payload is charged at the measured megabytes a second, over the class's fixed part
    small = hires.setup("RTX 4090", payload_mb=80.0, rows=rows)
    assert round(small["setup_min"] * 60) == 420 + 10  # 520 less the 100 s of data, plus 80 MB at 8 MB/s
    # a class with no hire that sailed borrows the others'; with none at all, S5's constant
    assert hires.setup("RTX 5090", rows=rows)["source"].startswith("no RTX 5090 hire has sailed")
    assert hires.setup("RTX 4090", rows=[])["n"] == 0


def test_a_failed_fit_out_is_one_that_never_sailed_and_was_not_stopped_at_once():
    f = hires.failures(rows=_rows())
    assert (f["hires"], f["failed"]) == (4, 2)  # the 80-second stop and the smoke test are not counted
    assert hires.failures("RTX 5090", rows=_rows())["rate"] == 1.0


def test_the_rate_at_sea_is_over_the_seconds_it_trained():
    rows = _rows()
    assert hires.train_seconds({"instance": 4, "train_s": 2300.0}, rows) == 2300.0
    assert hires.train_seconds({"instance": 1}, rows) == 4200.0
    assert hires.train_seconds({"instance": 2}, rows) is None


# ---------------------------------------------------------------- S3: the purser inside the cycle

TERMS = {"weekly_budget": 28.0, "voyage_budget": 10.0, "margin_hours": 1.0, "margin_fraction": 0.25,
         "foreign_expeditions": ["kipling"], "gpus": {"RTX 4090": 0.5}, "max_instances": 1, "cycle_hours": 12.0}  # fmt: skip
MINUTES = {"9m": 240.0, "300k": 30.0, "1m": 45.0}


def voyage(name: str, preset: str = "9m") -> lanes.Line:
    return lanes.Line(f"fitouts/{name}", "mac", "spec", f"fitouts/{name}", spec={"model": {"preset": preset},
                      "expedition": "kipling", "name": name}, name=name, run_id=f"r-{name}", reads=[])  # fmt: skip


def world(**kw) -> purser.World:
    base = dict(now=MONDAY, terms=TERMS, week_spent=0.0, speedups={("RTX 4090", "9m"): 4.0},
                prices={"RTX 4090": 0.4}, mac_free=[MONDAY], ship_free=[MONDAY])  # fmt: skip
    base.update(kw)
    return purser.World(**base)


def estimate(ln):
    return MINUTES[ln.spec["model"]["preset"]], "test"


def eligible(ln):
    return "kipling", None


def test_the_weeks_budget_is_released_a_cycle_at_a_time():
    w = world()
    assert purser.cycles_left(w) == 14 and purser.allowance_at(MONDAY, w) == 2.0  # 28 over fourteen cycles
    assert purser.allowance_at(MONDAY + 13 * H, w) == 4.0  # a voyage sailing next cycle may draw on two
    # Thursday noon: seven cycles gone, seven left
    thu = world(now=MONDAY + 3.5 * 24 * H, week_spent=7.0)
    assert purser.cycles_left(thu) == 7 and purser.allowance_at(thu.now, thu) == 3.0
    # with no cycle named the allowance is the day's, as it began
    day = world(terms={**TERMS, "cycle_hours": 24.0})
    assert purser.allowance_at(MONDAY, day) == 4.0


def test_under_a_weekly_release_the_whole_week_is_spendable_in_any_cycle():
    # 12 November, Justin: "i prefer just the weekly limit": what is left of the week, in the first cycle and the last
    weekly = {**TERMS, "budget_release": "week"}
    w = world(terms=weekly, week_spent=2.0)  # the week here is $28
    assert purser.allowance_at(MONDAY, w) == 26.0
    assert purser.allowance_at(MONDAY + 6.9 * 24 * H, w) == 26.0
    assert purser.allowance_at(MONDAY + 7.5 * 24 * H, w) == 26.0 + 28.0  # next week's budget, whole, from Monday
    # what is held for a ship out still comes off it (its run-up is already in the week's spend)
    out = world(terms=weekly, week_spent=2.0, cycle_spent=1.0, cycle_held=0.5)
    assert purser.allowance_at(MONDAY, out) == 25.5
    # the money's cycle is the week: a ship hired last cycle and still out is held against it
    assert purser.cycle_start(MONDAY + 3.5 * 24 * H, weekly) == MONDAY
    # three hires at $0.81 (the overrun counted) all fit the week where the cycle's $2 held the third back
    lines = [voyage("a"), voyage("b"), voyage("c")]
    calls = purser.plan(lines, world(terms=weekly, ship_free=[MONDAY] * 3, reserve=1.5), estimate, lambda ln: 30.0, eligible)
    assert [c.waters for c in calls] == ["foreign", "foreign", "foreign"]
    poor = purser.plan(lines, world(terms=weekly, week_spent=26.9, ship_free=[MONDAY] * 3, reserve=1.5), estimate,
                       lambda ln: 30.0, eligible)  # fmt: skip
    assert [c.waters for c in poor] == ["foreign", "local", "local"] and "the week's budget" in poor[1].reason


def test_a_hire_counts_against_the_allowance_at_its_quote_times_the_overrun():
    lines = [voyage("a"), voyage("b"), voyage("c")]
    # each costs (240 / 4 + 21) / 60 * 0.4 = $0.54; the cycle's allowance is $2
    plain = purser.plan(lines, world(ship_free=[MONDAY] * 3), estimate, lambda ln: 30.0, eligible)
    assert [c.waters for c in plain] == ["foreign", "foreign", "foreign"]
    held = purser.plan(lines, world(ship_free=[MONDAY] * 3, reserve=1.5), estimate, lambda ln: 30.0, eligible)
    assert [c.waters for c in held] == ["foreign", "foreign", "local"]  # two at $0.81 fit in $2, a third does not
    assert "cycle's allowance" in held[2].reason


def test_a_class_is_charged_its_measured_overhead():
    slow = purser.plan([voyage("a")], world(setup_min={"RTX 4090": 60.0}), estimate, lambda ln: 30.0, eligible)
    assert slow[0].foreign_min == 240 / 4 + 60
    const = purser.plan([voyage("a")], world(), estimate, lambda ln: 30.0, eligible)
    assert const[0].foreign_min == 240 / 4 + 21  # S5's constant where nothing is measured


def test_the_fleet_chosen_is_the_smallest_that_brings_the_queue_home_within_the_terms():
    lines = [voyage(n) for n in "abcd"] + [voyage("x", "300k")]
    w = world(terms={**TERMS, "weekly_budget": 280.0, "max_instances": 2})
    rows, calls = cycle.options(lines, w, estimate, lambda ln: 30.0, eligible, upto=4)
    assert [r["ships"] for r in rows] == [1, 2, 3, 4] and [r["within_terms"] for r in rows] == [True, True, False, False]
    assert rows[1]["ships_done_h"] < rows[0]["ships_done_h"] or rows[1]["abroad"] > rows[0]["abroad"]
    pick = cycle.choose(rows)
    assert pick["ships"] in (1, 2)
    best = min(r["all_done_h"] for r in rows[:2])
    assert next(r for r in rows if r["ships"] == pick["ships"])["all_done_h"] <= best + cycle.CLOSE_H
    # a fleet the terms do not allow is only ever proposed
    one = cycle.choose([{"ships": 1, "within_terms": True, "all_done_h": 10.0}, {"ships": 2, "within_terms": False, "all_done_h": 6.0}])
    assert one == {"ships": 1, "propose_ships": 2}
    assert cycle.choose([{"ships": 1, "within_terms": True, "all_done_h": 10.0}, {"ships": 2, "within_terms": False, "all_done_h": 9.5}])["propose_ships"] is None


def test_a_size_no_class_has_sailed_is_named_and_a_line_stored_in_the_wrong_lane():
    lines = [voyage("a"), voyage("s1", "300k"), voyage("s2", "300k")]
    missing = cycle.unmeasured(lines, world(), estimate, eligible)
    assert missing == {"300k": {"lines": 2, "mac_hours": 1.0}}
    odd = cycle.lane_lints([{"text": "fitouts/9m@x", "lane": "vast"}, {"text": "vast: fitouts/9m@y", "lane": "vast"}],
                           lambda t: lanes.Line(t, lanes.split_lane(t)[0], "spec", t))  # fmt: skip
    assert len(odd) == 1 and "fitouts/9m@x" in odd[0] and "9m@y" not in odd[0]
    env = {"lane_enabled": False, "max_instances": 1, "overrun": 1.5, "cycle_allowance": 2.0}
    rows = [{"ships": 1, "within_terms": True, "all_done_h": 10.0, "abroad": 2, "cost": 1.0, "mac_only_h": 20.0}]
    ps = cycle.proposals(env, rows, {"ships": 1, "propose_ships": None}, missing, odd, held=1)
    assert [p["to"] for p in ps] == ["S2", "S4", "S5", "S2"]  # open the lane, measure the 300k, the allowance, the lint


# ---------------------------------------------------------------- S3*: the plan against what happened


def test_the_audit_sets_each_quote_against_its_bill():
    rows = _rows()
    hs = s3star.hires_against_quotes(rows, 0.0, 1e12)
    assert [h["instance"] for h in hs] == [1, 2, 4, 5]  # the 80-second stop and the smoke test are left out
    one = next(h for h in hs if h["instance"] == 1)
    assert round(one["hours_ratio"], 2) == 1.67 and round(one["cost_ratio"], 2) == 1.67
    clock = s3star.clock_against_runs({"v": {"local_min": 30.0}}, [{"name": "v", "wall_minutes": 66.0, "finished": 500.0}], 0.0, 1000.0)
    assert clock[0]["ratio"] == 2.2
    planned = s3star.plan_against_queue({"abroad": [{"name": "a"}, {"name": "b"}, {"name": "c"}]}, {"a"}, {"b"}, lambda n: "finished")
    assert [p["now"] for p in planned] == ["still queued", "at sea", "finished"]
    said = s3star.findings(hs, clock, planned)
    assert any("never sailed" in f for f in said) and any("1.7 times" in f for f in said)
    assert any("over the queue's clock" in f for f in said) and any("still queued" in f for f in said)


# ---------------------------------------------------------------- S4's judge: reading what it said


def test_the_judges_answer_is_read_out_of_all_it_said():
    said = ('==========\n<think>the log shows rsync... {"cause": "not this"}</think>\n'
            '{"cause": "The box stopped answering ssh during the manifest rsync.", "step": "board", "fault": "Box", '
            '"confidence": "high", "do": "Bound the transfer."}\n==========\nPrompt: 900 tokens, 30 tokens-per-sec\n')  # fmt: skip
    v = judge.read(said)
    assert v["cause"].startswith("The box stopped") and v["fault"] == "box" and v["step"] == "board" and v["confidence"] == "high"
    assert judge.read("I am not sure.") is None
    assert judge.read('{"cause": "x", "fault": "gremlins"}')["fault"] == "unknown"


def test_the_judge_is_not_shown_what_a_person_already_said():
    case = {"instance": 7, "gpu": "RTX 5090", "dph": 0.46, "name": "50m@v0.0.5", "total_s": 654.0, "status": "released by hand",
            "why": "box refused ssh for 8 min", "phases": {"provision": 25, "ssh": 600}, "mb": {}, "log": "[box] ssh: true"}  # fmt: skip
    p = judge.prompt(case)
    assert "refused ssh for 8 min" not in p and "provision 25, ssh 600" in p and "[box] ssh: true" in p
    lines = ["12:00:00 charter: RTX 4090 offer 1 at $0.363/h, about 1.0 h, $0.36 (x)", "12:00:30 charter: instance 7 is up (h:1)",
             "12:01:00 [box] ssh: true", "12:20:00 charter: RTX 4090 offer 2 at $0.363/h, about 1.0 h, $0.36 (x)",
             "12:20:30 charter: instance 8 is up (h:1)"]  # fmt: skip
    assert judge.log_of(7, lines).splitlines() == lines[:3]
    outcome, said, _ = judge.ask("why?", {"name": "j", "command": ["j"]},
                                 runner=lambda *a, **k: type("R", (), {"returncode": 0, "stdout": '{"cause": "c"}', "stderr": ""})())  # fmt: skip
    assert outcome == "ok" and judge.read(said)["cause"] == "c"


# ---------------------------------------------------------------- S2: a box that fails is not a voyage that fails


def _seat(name="b", routed=True, since=1000.0):
    ln = voyage(name)
    ln.lane, ln.routed = "vast", routed
    return {"line": ln, "since_ts": since}


def _ev(event, run_id, ts):
    return {"event": event, "run_id": run_id, "at": datetime.fromtimestamp(ts, UTC).isoformat()}


def test_how_a_chartered_line_ended_is_read_from_the_spend_log():
    ln = _seat()["line"]
    assert lanes.how_it_ended(ln, 1000.0, []) == "not-hired"
    assert lanes.how_it_ended(ln, 1000.0, [_ev("hired", "r-b", 1010), _ev("released", "r-b", 2000)]) == "fitout-failed"
    assert lanes.how_it_ended(ln, 1000.0, [_ev("hired", "r-b", 1010), _ev("at sea", "r-b", 1500)]) == "voyage-failed"
    sank = [_ev("hired", "r-b", 1010), _ev("at sea", "r-b", 1500), {**_ev("released", "r-b", 1640), "ended": 1640.0}]
    assert lanes.how_it_ended(ln, 1000.0, sank) == "sank-at-once"  # two minutes at sea: it never trained
    long = [_ev("hired", "r-b", 1010), _ev("at sea", "r-b", 1500), {**_ev("released", "r-b", 9000), "ended": 9000.0}]
    assert lanes.how_it_ended(ln, 1000.0, long) == "voyage-failed"
    # an earlier sailing of the same run, and another run's, are not this one's
    assert lanes.how_it_ended(ln, 1000.0, [_ev("at sea", "r-b", 500), _ev("at sea", "r-other", 1500)]) == "not-hired"


def test_two_fit_outs_failing_in_a_row_pause_the_lane_and_the_voyage_is_retried_abroad(monkeypatch):
    said, done, paused = [], [], []
    monkeypatch.setattr(lanes, "box_failure_limit", lambda: 2)
    monkeypatch.setattr(lanes, "_retry_abroad", lambda q, ln, say, why="": done.append(("abroad", ln.name)))
    monkeypatch.setattr(lanes, "_come_home", lambda q, ln, say: done.append(("home", ln.name)))
    monkeypatch.setattr(lanes, "set_lane", lambda lane, on, why="": paused.append((lane, on, why)) or True)
    ended = {"how": "fitout-failed"}
    monkeypatch.setattr(lanes, "how_it_ended", lambda ln, since, log=None: ended["how"])
    fails: dict[str, int] = {}
    lanes._charter_ended(None, "vast", _seat("a"), 1, fails, said.append)
    assert done == [("abroad", "a")] and fails == {"vast": 1} and not paused  # one dead box: try another
    lanes._charter_ended(None, "vast", _seat("a"), 1, fails, said.append)
    assert paused and paused[0][:2] == ("vast", False) and "2 hires failed in a row" in paused[0][2]
    assert done == [("abroad", "a"), ("abroad", "a")]  # still queued abroad, behind the pause: never pinned to the Mac
    # a voyage that sailed and failed comes home, as before, and a sound box clears the count
    fails["vast"] = 1
    ended["how"] = "voyage-failed"
    lanes._charter_ended(None, "vast", _seat("c"), 1, fails, said.append)
    assert done[-1] == ("home", "c") and fails["vast"] == 0
    # nothing hired at all (no offer, the gate): home too, and no box is blamed
    fails["vast"] = 1
    ended["how"] = "not-hired"
    lanes._charter_ended(None, "vast", _seat("d"), 1, fails, said.append)
    assert done[-1] == ("home", "d") and fails["vast"] == 1
    # a line pinned abroad (`vast:`) whose box died is retried abroad too (12 November, Justin: until then it was
    # dropped from the queue), and its dead box still counts
    ended["how"] = "fitout-failed"
    lanes._charter_ended(None, "vast", _seat("e", routed=False), 1, fails, said.append)
    assert done[-1] == ("abroad", "e") and len(paused) == 2
    lanes._charter_ended(None, "vast", _seat("f"), 0, {"vast": 1}, said.append)  # a voyage home: nothing to do


def test_a_pinned_line_never_hired_goes_back_once_and_an_adopted_one_home_is_home(monkeypatch):
    """1m-control, 21:13 on 12 November: pinned abroad, its hire refused (the offer taken), and dropped."""
    said, done = [], []
    monkeypatch.setattr(lanes, "_PINNED_RETRIED", set())
    monkeypatch.setattr(lanes, "_retry_abroad", lambda q, ln, say, why="": done.append((ln.name, why)))
    monkeypatch.setattr(lanes, "_come_home", lambda q, ln, say: done.append((ln.name, "home")))
    monkeypatch.setattr(lanes, "how_it_ended", lambda ln, since, log=None: "not-hired")
    fails: dict[str, int] = {}
    lanes._charter_ended(None, "vast", _seat("p", routed=False), 1, fails, said.append)
    assert done == [("p", "it was never hired")] and fails == {}  # back at the top, abroad; no box blamed
    lanes._charter_ended(None, "vast", _seat("p", routed=False), 1, fails, said.append)
    assert len(done) == 1 and "the second time running: left out" in said[-1]  # not tried over and over
    # a charter adopted across a restart has no exit code; the ledger saying it finished is a voyage home
    lanes._charter_ended(None, "vast", _seat("q", routed=False), "adopted:finished", fails, said.append)
    assert len(done) == 1
    # a pinned voyage that failed at sea goes back once too; a sound end clears its retry
    monkeypatch.setattr(lanes, "how_it_ended", lambda ln, since, log=None: "voyage-failed")
    lanes._charter_ended(None, "vast", _seat("r", routed=False), 1, fails, said.append)
    lanes._charter_ended(None, "vast", _seat("r", routed=False), 0, fails, said.append)
    lanes._charter_ended(None, "vast", _seat("r", routed=False), 1, fails, said.append)
    assert done[1:] == [("r", "its voyage failed at sea"), ("r", "its voyage failed at sea")]


# ---------------------------------------------------------------- S1: the box sails with the voyage's own lists


def test_the_box_carries_the_voyages_lists_even_when_git_does_not_keep_them(tmp_path, monkeypatch):
    from thorp import paths
    from thorp.viable.s1_operations import charter

    (tmp_path / "ships" / "lists").mkdir(parents=True)
    (tmp_path / "backend" / "thorp").mkdir(parents=True)
    for rel in ("ships/lists/ignored.csv", "ships/lists/deck.csv", "backend/thorp/a.py", "backend/thorp/new.py"):
        (tmp_path / rel).write_text("x")
    monkeypatch.setattr(paths, "ROOT", tmp_path)
    monkeypatch.setattr(paths, "resolve", lambda p: tmp_path / "ships" / p)
    spec = {"data": {"stages": [{"recipe": "lists/ignored.csv"}], "refuse": ["lists/gone.csv"]}, "eval": {"sets": ["lists/deck.csv"]}}
    assert charter.voyage_lists(spec) == ["ships/lists/ignored.csv", "ships/lists/deck.csv"]  # a list not on disk is not named

    def git(cmd, **kw):
        out = "backend/thorp/new.py\n" if "--others" in cmd else "backend/thorp/a.py\nships/lists/deck.csv\nbackend/thorp/deleted.py\n"
        return type("R", (), {"stdout": out, "returncode": 0})()

    got = charter.code_carried(spec, run=git)
    assert got == ["backend/thorp/a.py", "ships/lists/deck.csv", "backend/thorp/new.py", "ships/lists/ignored.csv"]


def test_what_a_cycle_has_spent_and_holds_comes_off_its_own_share():
    # Monday, fourteen cycles, $28: a $2 share. A ship home for $0.60 and one out, quoted $0.40 and $0.10 run up.
    w = world(week_spent=0.70, cycle_spent=0.70, cycle_held=0.50)
    assert round(purser.allowance_at(MONDAY, w), 2) == round(2.0 - 0.70 - 0.50, 2)
    # without the account every re-plan found nearly a whole share again
    assert round(purser.allowance_at(MONDAY, world(week_spent=0.70)), 2) == 1.95
    log = [
        {"event": "hired", "instance": 1, "started": MONDAY + 600, "dph": 0.4, "quote": 0.5},
        {"event": "released", "instance": 1, "cost": 0.6},
        {"event": "hired", "instance": 2, "started": MONDAY + 3600, "dph": 0.4, "quote": 0.4},  # out for a quarter of an hour
        {"event": "hired", "instance": 3, "started": MONDAY - 3600, "dph": 0.4, "quote": 9.0},  # last cycle's: not this one's
        {"event": "released", "instance": 3, "cost": 5.0},
    ]
    spent, held = purser.cycle_money(log, MONDAY + 3600 + 900, {**TERMS, "overrun": 1.5})
    assert round(spent, 2) == 0.70 and round(held, 2) == 0.50
    assert purser.cycle_start(MONDAY + 13 * H, TERMS) == MONDAY + 12 * H


def test_a_voyage_that_sinks_at_once_abroad_is_counted_and_retried_like_a_dead_box(monkeypatch):
    done, paused = [], []
    monkeypatch.setattr(lanes, "box_failure_limit", lambda: 2)
    monkeypatch.setattr(lanes, "_retry_abroad", lambda q, ln, say, why="": done.append(("abroad", ln.name)))
    monkeypatch.setattr(lanes, "_come_home", lambda q, ln, say: done.append(("home", ln.name)))
    monkeypatch.setattr(lanes, "set_lane", lambda lane, on, why="": paused.append(why) or True)
    monkeypatch.setattr(lanes, "how_it_ended", lambda ln, since, log=None: "sank-at-once")
    fails: dict[str, int] = {}
    lanes._charter_ended(None, "vast", _seat("a"), 1, fails, lambda m: None)
    lanes._charter_ended(None, "vast", _seat("b"), 1, fails, lambda m: None)
    assert done == [("abroad", "a"), ("abroad", "b")] and len(paused) == 1 and "sank-at-once" in paused[0]


def test_the_host_must_carry_the_cuda_the_locks_torch_is_built_for(tmp_path):
    from thorp.viable.s1_operations import vast

    lock = tmp_path / "uv.lock"
    lock.write_text('[[package]]\nname = "nvidia-cuda-runtime"\nversion = "13.2.86"\nsource = {}\n')
    assert vast.required_cuda(lock) == 13.2
    assert vast.required_cuda(tmp_path / "none.lock") == 0.0
    assert vast.required_cuda() >= 12.8  # this repository's own lock can be read
    asked = []

    def transport(method, path, body, params):
        asked.append(body)
        return {"offers": []}

    vast.Vast(transport).search("RTX 4090", {"min_reliability": 0.98, "min_inet_down_mbps": 1, "min_inet_up_mbps": 1,
                                             "disk_gb": 1, "min_cuda": 12.8, "gpus": {"RTX 4090": 0.5}})  # fmt: skip
    assert asked[0]["cuda_max_good"]["gte"] == max(12.8, vast.required_cuda())


# ---------------------------------------------------------------- the Cost tab: a hire's cost spread over its hours


def test_a_hires_cost_is_spread_over_the_hours_it_ran_and_sorted_by_what_it_bought():
    from thorp.dash import cost

    t0 = datetime(2026, 11, 12, 1, 30).astimezone().timestamp()  # 01:30 this Mac's time
    log = [
        {"event": "hired", "instance": 1, "started": t0, "dph": 1.0, "run_id": "r1", "name": "v1", "gpu": "RTX 4090"},
        {"event": "at sea", "instance": 1, "at": datetime.fromtimestamp(t0 + 600, UTC).isoformat()},
        {"event": "released", "instance": 1, "started": t0, "ended": t0 + 5400, "cost": 1.5, "train_s": 4000.0},  # 01:30 to 03:00
        {"event": "hired", "instance": 2, "started": t0 + 600, "dph": 0.6, "run_id": "r2", "name": "v2", "gpu": "RTX 4090"},
        {"event": "released", "instance": 2, "at": datetime.fromtimestamp(t0 + 600 + 1800, UTC).isoformat(), "why": "by hand"},
        {"event": "hired", "instance": 3, "started": t0 + 3600, "dph": 2.0, "run_id": "smoke-x", "gpu": "H100 SXM"},
        {"event": "released", "instance": 3, "started": t0 + 3600, "ended": t0 + 3660, "cost": 0.04},
    ]
    now = t0 + 7200
    rows = {r["instance"]: r for r in cost.hires(log, now)}
    assert rows[1]["kind"] == "trained" and rows[2]["kind"] == "never_trained" and rows[3]["kind"] == "smoke"
    assert round(rows[2]["cost"], 2) == 0.30 and rows[2]["no_cost"]  # released by hand: charged at its rate
    hours = {b["label"][-5:]: b for b in cost.buckets(list(rows.values()), "hour", now) if b["total"]}
    assert round(hours["01:00"]["trained"], 2) == 0.5 and round(hours["02:00"]["trained"], 2) == 1.0  # a third, two thirds
    assert round(hours["01:00"]["never_trained"] + hours["02:00"]["never_trained"], 2) == 0.30
    assert round(hours["02:00"]["smoke"], 2) == 0.04 and hours["02:00"]["hires"] == 1
    day = cost.buckets(list(rows.values()), "day", now)
    assert round(sum(b["total"] for b in day), 2) == round(1.5 + 0.30 + 0.04, 2)
    week = cost.buckets(list(rows.values()), "week", now)[-1]
    assert datetime.fromisoformat(week["start"]).weekday() == 0 and week["now"]  # Monday, UTC: the budget's week


def test_no_macos_metadata_twin_goes_aboard(tmp_path):
    import subprocess
    import sys
    import tarfile

    from thorp.viable.s1_operations import charter

    if sys.platform != "darwin":
        assert charter.TAR == ["tar"]
        return
    (tmp_path / "a.csv").write_text("x,y\n")
    subprocess.run(["xattr", "-w", "com.example.note", "1", str(tmp_path / "a.csv")], check=True)
    out = tmp_path / "out.tgz"
    subprocess.run(charter.TAR + ["-czf", str(out), "-C", str(tmp_path), "a.csv"], check=True,
                   env={"COPYFILE_DISABLE": "1", "PATH": "/usr/bin:/bin"})  # fmt: skip
    assert tarfile.open(out).getnames() == ["a.csv"]  # no ._a.csv (which macOS's own tar would not list)


# ---------------------------------------------------------------- S1: the box's environment sync, watched


class _Sync:
    """A box whose `uv sync` answers each poll from a script: (exit code or "", MB in the cache, bytes taken in, uv's line)."""

    def __init__(self, script):
        import subprocess

        self.script, self.calls, self.subprocess = list(script), [], subprocess

    def __call__(self, argv, **kw):
        cmd = argv[-1]
        self.calls.append(cmd)
        out = ""
        if "cat " in cmd and "env.exit" in cmd and "du -sm" in cmd:
            code, mb, net, line = self.script.pop(0) if self.script else self.script_last
            self.script_last = (code, mb, net, line)
            out = f"{code}\n|\n{mb}\n|\n{net}\n|\n{line}\n"
        elif cmd.startswith("tail -n 15"):
            out = "error: Failed to download `torch`"
        return self.subprocess.CompletedProcess(argv, 0, stdout=out, stderr="")


def _box(script):
    import pytest  # noqa: F401

    from thorp.viable.s1_operations import charter

    run, said, t = _Sync(script), [], {"now": 0.0}
    box = charter.Box("ssh9.vast.ai", 40123, run=run, log=said.append)

    def sleep(s):
        t["now"] += s

    return box, run, said, sleep, (lambda: t["now"])


def test_a_moving_sync_reports_its_progress_and_finishes():
    box, run, said, sleep, clock = _box([("", 900, 1_000_000_000, "Downloading torch (900.0MiB)"),
                                         ("", 2400, 2_500_000_000, "Downloading nvidia-cublas"),
                                         ("0", 6100, 6_200_000_000, "Installed 120 packages in 9.1s")])  # fmt: skip
    box.sync_env(sleep=sleep, clock=clock)
    progress = [m for m in said if m.startswith("[box] env: ")]
    assert len(progress) == 2 and "Downloading torch" in progress[0] and "100.0 MB/s" in progress[1]
    assert any(m.startswith("[box] environment synced (45s, 6,100 MB)") for m in said)
    # the tagger probe follows the sync, so it is not the last line (12 November: shapes must not fail a fit-out)
    assert not any("ssh done" in m for m in said)  # the polls are quiet: the timing table ends the step at "synced"
    assert "nohup" in run.calls[0] and "env.log" in run.calls[0] and "-q" not in run.calls[0]


def test_a_sync_that_takes_nothing_in_is_stopped_as_stalled():
    import pytest

    from thorp.viable.s1_operations import charter

    box, run, said, sleep, clock = _box([("", 3000, 3_000_000_000, "Downloading torch")] * 40)
    with pytest.raises(charter.BoxError, match="stalled: nothing came in"):
        box.sync_env(sleep=sleep, clock=clock, stall_s=60)
    assert any("NOTHING MOVED" in m for m in said) and any("pkill" in c for c in run.calls)


def test_a_sync_that_fails_says_uvs_own_words():
    import pytest

    from thorp.viable.s1_operations import charter

    box, run, said, sleep, clock = _box([("", 100, 1_000, "Resolved 200 packages"), ("2", 100, 1_000, "error")])
    with pytest.raises(charter.BoxError, match="Failed to download"):
        box.sync_env(sleep=sleep, clock=clock)


def test_a_hire_takes_the_prebuilt_image_for_its_lock_when_it_is_published(tmp_path, monkeypatch):
    from thorp.viable.s1_operations import charter

    lock = tmp_path / "uv.lock"
    lock.write_text("version = 1\n")
    tag = charter.lock_tag(lock)
    assert tag.startswith("lock-") and len(tag) == 17
    monkeypatch.setattr(charter, "lock_tag", lambda lock=None: tag)
    t = {"image": "pytorch/pytorch:base", "box_image": "ghcr.io/demitonapp/thorp-box"}
    assert charter.box_image(t, exists=lambda ref: True) == (f"ghcr.io/demitonapp/thorp-box:{tag}", "prebuilt for this lock: torch is already aboard")
    img, why = charter.box_image(t, exists=lambda ref: False)
    assert img == "pytorch/pytorch:base" and "not published" in why  # a lock changed before its image was built
    assert charter.box_image({"image": "pytorch/pytorch:base"}, exists=lambda ref: True)[0] == "pytorch/pytorch:base"

    class R:
        def __init__(self, code, body=None):
            self.status_code, self.body = code, body or {}

        def json(self):
            return self.body

    asked = []

    def get(url, **kw):
        asked.append(url)
        return R(200, {"token": "t"}) if url.endswith("/token") else R(404)

    assert charter.image_exists("ghcr.io/demitonapp/thorp-box:lock-x", get=get) is False
    assert asked == ["https://ghcr.io/token", "https://ghcr.io/v2/demitonapp/thorp-box/manifests/lock-x"]


# ---------------------------------------------------------------- S2: S4's audit, a line of the queue every five


def test_the_intelligence_audit_is_queued_after_every_five_lines_and_never_twice(monkeypatch):
    hist = [{"text": "fitouts/a"}, {"text": lanes.AUDIT_LINE}] + [{"text": f"fitouts/{i}"} for i in range(4)]
    hist += [{"text": "cmd: sh backend/scripts/restart_coordinator.sh"}, {"text": "wait: x"}]
    assert lanes.lines_since_audit(hist) == 4  # a restart and a wait do not count
    added, said = [], []
    monkeypatch.setattr(lanes, "_queue_pg", lambda: False)
    monkeypatch.setattr(lanes, "append", lambda q, text, note="": added.append(text))
    assert not lanes.queue_audit(None, said.append, history=hist, pending_now=[], every=5)
    hist.append({"text": "cmd: PYTHONPATH=backend backend/.venv/bin/python -m thorp.investigate run arc-ai2-9m"})
    assert lanes.queue_audit(None, said.append, history=hist, pending_now=[], every=5)
    assert added == [lanes.AUDIT_LINE] and "5 lines have ended" in said[-1]
    assert not lanes.queue_audit(None, said.append, history=hist, pending_now=[lanes.AUDIT_LINE], every=5)  # one is queued
    assert not lanes.queue_audit(None, said.append, history=hist, pending_now=[], every=0)  # switched off
    ln = lanes.parse(lanes.AUDIT_LINE)
    assert (ln.lane, ln.kind, ln.timeout) == ("mac", "intelligence", 2700)  # the Mac lane; its own item type (12 November)
    from thorp.viable.s3_control import purser

    assert purser.cmd_minutes(ln) == 20.0  # the queue's clock reads its estimate

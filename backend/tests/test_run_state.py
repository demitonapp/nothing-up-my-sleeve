"""Item 11 of the 11 November architecture audit: a voyage names its expedition outright, the lanes are rows, and a
run's state is a row with a heartbeat (thorp/run_state.py, fleet.expedition_of_spec / expedition_of_run, lanes.py's
s2.lane_defs). The store tests write only rows with their own `t11-` run ids and remove them again: the two side
tables are not in the fixtures' truncate, and other sessions run tests against the same database."""

from __future__ import annotations

import hashlib
import json
import subprocess
import time
from pathlib import Path

import pytest
import yaml
from sqlalchemy import text

from thorp import fleet, paths, run_state, store, train
from thorp.viable.s2_coordination import lanes

OLD_NOT_HASHED = ("name", "ship", "experiment", "question", "fitout", "charter")  # before 11 November, item 11


def _old_id(spec: dict) -> str:
    """train.run_id as it was before `expedition` joined the labels."""
    body = json.dumps(
        {k: v for k, v in spec.items() if k not in OLD_NOT_HASHED},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha1(body.encode()).hexdigest()


# ---------------------------------------------------------------- A: the expedition is a label


def test_expedition_is_a_label_and_moves_no_id():
    assert "expedition" in train.NOT_HASHED
    spec = {"name": "x", "ship": "SOP v0.0.7 at 9m", "model": {"preset": "9m"}, "seed": 1}
    assert train.run_id({**spec, "expedition": "kipling"}) == train.run_id(spec) == _old_id(spec)


def test_every_spec_on_disk_keeps_its_run_id():
    """Every voyage spec under ships/specs (a YAML with a model) hashes to the same id before and after."""
    root = paths.ROOT / "ships" / "specs"
    n = 0
    for p in sorted(root.rglob("*.yaml")):
        try:
            spec = yaml.safe_load(p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001 - not a spec
            continue
        if not isinstance(spec, dict) or "model" not in spec:
            continue
        assert train.run_id(spec) == _old_id(spec), p
        n += 1
    assert n > 50


def test_every_run_in_the_live_ledger_keeps_its_run_id():
    """Every spec_json of s1.runs in the live store (read only) hashes the same before and after."""
    from sqlalchemy import create_engine

    eng = create_engine("postgresql+psycopg://thorp@localhost:5433/thorp", connect_args={"connect_timeout": 3})
    try:
        with eng.connect() as c:  # a read in its own short transaction, closed at once
            rows = c.execute(text("select run_id, spec_json from s1.runs where spec_json is not null")).fetchall()
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"the live store cannot be read here: {e.__class__.__name__}")
    finally:
        eng.dispose()
    assert rows
    for rid, body in rows:
        spec = json.loads(body)
        assert train.canonical(spec) == json.dumps(
            {k: v for k, v in spec.items() if k not in OLD_NOT_HASHED},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ), rid


def test_a_spec_names_its_expedition_and_the_label_is_the_fallback():
    # the audit's case: an SOP v0.0.7 voyage lands in Ogden by its label; named, it is where it says
    assert fleet.expedition_of_label("x", "SOP v0.0.7 at 9m") == "ogden"
    assert fleet.expedition_of_spec({"ship": "SOP v0.0.7 at 9m"}) == "ogden"
    assert fleet.expedition_of_spec({"ship": "SOP v0.0.7 at 9m", "expedition": "kipling"}) == "kipling"
    assert fleet.unknown_expedition({"expedition": "kipling"}) is None
    assert fleet.unknown_expedition({}) is None
    assert "does not exist" in fleet.unknown_expedition({"expedition": "atlantis"})
    from thorp import liberty_machine

    assert liberty_machine._pre_registered({"ship": "SOP v0.0.7 at 9m", "expedition": "kipling"}) == []
    assert "does not exist" in liberty_machine._pre_registered({"ship": "SOP v0.0.7 at 9m", "expedition": "atlantis"})[0]
    assert liberty_machine._pre_registered({"ship": "nothing known"}) == ["belongs to no expedition"]


def test_the_queue_refuses_an_expedition_that_does_not_exist(tmp_path, monkeypatch):
    from thorp.viable.s2_coordination import queue_store

    monkeypatch.setenv("THORP_SHIPS", str(tmp_path))
    (tmp_path / "specs" / "fitouts").mkdir(parents=True)
    (tmp_path / "specs" / "fitouts" / "bad.yaml").write_text(yaml.safe_dump({"name": "b", "expedition": "atlantis"}))
    (tmp_path / "specs" / "fitouts" / "good.yaml").write_text(yaml.safe_dump({"name": "g", "expedition": "kipling"}))
    (tmp_path / "specs" / "fitouts" / "plain.yaml").write_text(yaml.safe_dump({"name": "p"}))
    assert "does not exist" in queue_store._refused_expedition("fitouts/bad")
    assert queue_store._refused_expedition("fitouts/good") is None
    assert queue_store._refused_expedition("fitouts/plain") is None
    with pytest.raises(ValueError, match="does not exist"):
        queue_store.add("fitouts/bad")


@pytest.fixture
def ids():
    """Run ids of this test's own, removed from the two side tables afterwards."""
    made: list[str] = []

    def new(tag: str) -> str:
        rid = f"t11-{tag}-{time.time_ns()}"
        made.append(rid)
        return rid

    yield new
    with store.session() as s:
        for t in ("s1.run_state", "s1.run_expedition"):
            s.execute(text(f"delete from {t} where run_id like 't11-%' and run_id = any(:ids)"), {"ids": made})


def test_a_run_row_is_preferred_to_the_label(ids):
    rid = ids("exp")
    row = {"run_id": rid, "name": "x", "ship": "SOP v0.0.7 at 9m"}
    assert fleet.expedition_of_run(row) == "ogden"  # no row yet: the chain
    assert run_state.record_expedition({"ship": "SOP v0.0.7 at 9m", "expedition": "kipling"}, rid) == "kipling"
    fleet.recorded_expeditions(fresh=True)
    assert fleet.expedition_of_run(row) == "kipling"
    # a manual row is kept against a trainer's later write
    run_state.record_expedition({}, rid, expedition="card_census", source="manual")
    run_state.record_expedition({"ship": "SOP v0.0.7 at 9m"}, rid)
    fleet.recorded_expeditions(fresh=True)
    assert fleet.expedition_of_run(row) == "card_census"
    with store.session() as s:
        assert s.execute(text("select source from s1.run_expedition where run_id=:r"), {"r": rid}).scalar() == "manual"


def test_a_spec_with_no_expedition_records_its_labels(ids):
    rid = ids("lab")
    assert run_state.record_expedition({"ship": "SOP v0.0.6 at 9m"}, rid) == "kipling"
    with store.session() as s:
        got = s.execute(text("select expedition, source from s1.run_expedition where run_id=:r"), {"r": rid}).one()
    assert tuple(got) == ("kipling", "label")
    assert run_state.record_expedition({"ship": "no expedition at all"}, ids("none")) is None


# ---------------------------------------------------------------- C: the run's state


@pytest.mark.parametrize(
    ("status", "state"),
    [
        ("finished", "finished"),
        ("running", "running"),
        ("stopped", "stopped"),
        ("killed", "stopped"),
        ("recalled: Ogden v0.1 called back at 20:20 (Justin)", "recalled"),
        ("failed: OSError", "failed"),
        ("failed: ValueError", "failed"),
        ("failed: stopped by hand at step 63, memory contention", "stopped"),
        ("chartered: overran", "stopped"),
        ("chartered: failed (exit 1)", "failed"),
        ("chartered", "running"),
        ("stopped: SIGTERM at step 40", "stopped"),
        ("something new in prose", "failed"),
    ],
)
def test_every_status_maps_to_a_state_with_its_words(status, state):
    assert run_state.state_of(status) == (state, status)


def test_no_status_is_no_state():
    assert run_state.state_of(None) is None and run_state.state_of("  ") is None


def _row(rid):
    return run_state.of(rid)


def test_start_beat_and_end(ids, monkeypatch):
    monkeypatch.setattr(run_state, "_home", lambda rec: True)
    monkeypatch.setattr(run_state, "record_expedition", lambda spec, rid: None)
    rid = ids("life")
    run_state.started({}, rid, rec=None)
    first = _row(rid)
    assert first["state"] == "running" and first["heartbeat_at"] is not None
    calls = []
    real = store.session

    def counting():
        calls.append(1)
        return real()

    monkeypatch.setattr(store, "session", counting)
    for _ in range(100):  # a hundred steps inside a minute: no write at all
        run_state.beat(rid, rec=None)
    assert calls == []
    run_state._last_beat[rid] = time.monotonic() - run_state.BEAT_EVERY_S - 1
    run_state.beat(rid, rec=None)
    assert len(calls) == 1
    monkeypatch.setattr(store, "session", real)
    run_state.ended(rid, "failed: ValueError", rec=None, reason="failed: ValueError('bad')")
    assert (_row(rid)["state"], _row(rid)["reason"]) == ("failed", "failed: ValueError('bad')")


def test_a_box_or_a_test_ledger_writes_nothing(ids):
    rid = ids("box")
    run_state.started({}, rid, rec=object())
    run_state.ended(rid, "finished", rec=object())
    assert _row(rid) is None


def test_a_box_status_is_folded_home_as_a_state(ids):
    rid = ids("fold")
    with store.session() as s:
        run_state.fold(s, {"run_id": rid, "status": "running"})
    assert _row(rid)["state"] == "running" and _row(rid)["heartbeat_at"] is not None
    with store.session() as s:
        run_state.fold(s, {"run_id": rid, "status": "chartered: overran"})
    assert (_row(rid)["state"], _row(rid)["reason"]) == ("stopped", "chartered: overran")


def test_the_sweep_marks_only_an_uncovered_silent_run_lost(ids, monkeypatch):
    from thorp.ledger import reader

    silent, covered, named, fresh, docked = (ids(t) for t in ("silent", "covered", "named", "fresh", "docked"))
    for rid in (silent, covered, named, fresh, docked):
        reader().run({"run_id": rid, "name": rid, "status": "running", "started": "2026-11-11T00:00:00"})
        run_state.write(rid, "running", "running", beat=True)
    reader().run({"run_id": docked, "status": "finished"})
    with store.session() as s:
        s.execute(
            text("update s1.run_state set heartbeat_at = now() - interval '1 hour' where run_id = any(:ids)"),
            {"ids": [silent, covered, named, docked]},
        )
    said = []
    lost = run_state.sweep({covered}, {named}, say=said.append)
    assert silent in lost and not {covered, named, fresh, docked} & set(lost) and "lost" in said[0]
    got = run_state.of_many([silent, covered, named, fresh, docked])
    assert {k: v["state"] for k, v in got.items()} == {
        silent: "lost", covered: "running", named: "running", fresh: "running", docked: "finished"}  # fmt: skip
    assert reader().get_run(silent)["status"] == "stopped"  # as the start-up reaper wrote
    # a beat after the mark: it was alive after all
    run_state._last_beat.pop(silent, None)
    monkeypatch.setattr(run_state, "_home", lambda rec: True)
    run_state.beat(silent, rec=None)
    assert run_state.of(silent)["state"] == "running"


def test_the_reaper_leaves_a_run_with_a_state_row_to_the_heartbeat(ids, monkeypatch):
    from thorp.ledger import reader

    monkeypatch.setenv("THORP_QUEUE_PG", "1")
    stated, bare = ids("stated"), ids("bare")
    for rid in (stated, bare):
        reader().run({"run_id": rid, "name": rid, "status": "running", "started": "2026-11-01T00:00:00"})
    run_state.write(stated, "running", "running", beat=True)
    assert lanes._reap_runs(lambda m: None) == 1
    assert reader().get_run(stated)["status"] == "running" and reader().get_run(bare)["status"] == "stopped"


# ---------------------------------------------------------------- B: the lanes are rows


@pytest.fixture
def fresh_lanes():
    lanes._DEFS.update(at=float("-inf"), defs=None)
    yield
    lanes._DEFS.update(at=float("-inf"), defs=None)


def test_the_two_lanes_read_from_their_rows_as_the_constants_said(fresh_lanes):
    defs = lanes.lane_defs(fresh=True)
    assert list(defs)[:2] == ["mac", "vast"]
    assert defs["mac"].kind == "local" and defs["mac"].shared_presets == frozenset({"300k"})
    assert defs["vast"].kind == "charter" and lanes.slots_of("vast") == 1
    assert lanes.split_lane("vast: fitouts/x") == ("vast", "fitouts/x")
    assert lanes.split_lane("fitouts/x") == ("mac", "fitouts/x")
    assert lanes.split_lane("cmd: echo hi") == ("mac", "cmd: echo hi")
    assert lanes.helm_offset("mac") == 0


def test_without_a_store_the_constants_answer(fresh_lanes, monkeypatch):
    def down():
        raise store.StoreDown("no store")

    monkeypatch.setattr(lanes, "_read_defs", down)
    defs = lanes.lane_defs(fresh=True)
    assert list(defs) == ["mac", "vast"] and defs["mac"].shared_presets == frozenset(lanes.TWO_AT_ONCE)


def _three(monkeypatch, **mac2):
    defs = {
        "mac": lanes.LaneDef("mac", "local", None, frozenset({"300k"})),
        "mac2": lanes.LaneDef("mac2", "local", 2, frozenset(), **mac2),
        "vast": lanes.LaneDef("vast", "charter", 1),
    }
    monkeypatch.setattr(lanes, "_read_defs", lambda: defs)
    lanes._DEFS.update(at=float("-inf"), defs=None)
    monkeypatch.setenv("THORP_MAC2_SLOTS", "2")


def _spec(specs: Path, rel: str, name: str, preset: str = "9m") -> None:
    p = specs / f"{rel}.yaml"
    p.parent.mkdir(parents=True, exist_ok=True)
    seed = sum(map(ord, name))  # a run id of its own: two specs with one id never sail at once
    p.write_text(yaml.safe_dump({"name": name, "ship": "Fitout: Ogden test", "seed": seed,
                                 "model": {"family": "gpt", "preset": preset}}))  # fmt: skip


def _sail(tmp_path, monkeypatch, lines, secs=0.4):
    monkeypatch.setenv("THORP_QUEUE_PG", "0")
    specs = tmp_path / "specs"
    queue, done = specs / "queue.txt", specs / "queue-done.txt"
    queue.write_text("\n".join(lines) + "\n")
    events, said = [], []

    def launch(ln):
        events.append({"lane": ln.lane, "line": ln.text, "start": time.time()})
        return subprocess.Popen(["sleep", str(secs)])

    lanes.run(queue=queue, done=done, root=tmp_path, poll_s=0.05, key=lambda: True, outside=lambda: False,
              launch=launch, log=said.append, until_empty=True)  # fmt: skip
    return events, said, queue


def test_a_third_local_lane_with_its_own_seats_is_iterated(tmp_path, monkeypatch, fresh_lanes):
    _three(monkeypatch)
    specs = tmp_path / "specs"
    for n in ("a", "b", "m1"):
        _spec(specs, n, n)
    assert lanes.parse("mac2: a", specs).lane == "mac2"
    assert lanes.command(lanes.parse("mac2: a", specs))[-2:] == ["run", "ships/specs/a.yaml"]
    assert lanes.slots_of("mac2") == 2 and lanes.helm_offset("mac2") == lanes.slots_of("mac")
    ev, _, queue = _sail(tmp_path, monkeypatch, ["mac2: a", "mac2: b", "m1"])
    by = {e["line"]: e for e in ev}
    assert by["mac2: a"]["lane"] == by["mac2: b"]["lane"] == "mac2" and by["m1"]["lane"] == "mac"
    # two 9m lines side by side on mac2's two seats (no shared-preset cap on it), the Mac sailing beside them
    assert abs(by["mac2: b"]["start"] - by["mac2: a"]["start"]) < 0.3
    assert abs(by["m1"]["start"] - by["mac2: a"]["start"]) < 0.3
    assert queue.read_text().strip() == ""


def test_a_disabled_lane_takes_nothing(tmp_path, monkeypatch, fresh_lanes):
    _three(monkeypatch, enabled=False)
    specs = tmp_path / "specs"
    for n in ("a", "m1"):
        _spec(specs, n, n)
    assert lanes.capacity_for("mac2", [lanes.parse("mac2: a", specs)], {}) == 0
    ev, _, queue = _sail(tmp_path, monkeypatch, ["mac2: a", "m1"])
    assert [e["line"] for e in ev] == ["m1"]
    assert queue.read_text().strip() == "mac2: a"  # it waits in the queue, as a keyless Vast line does


def test_a_lane_of_an_unknown_kind_says_it_has_no_launcher(tmp_path, monkeypatch, fresh_lanes):
    defs = {"mac": lanes.LaneDef("mac", "local"), "tpu": lanes.LaneDef("tpu", "pod", 1)}
    monkeypatch.setattr(lanes, "_read_defs", lambda: defs)
    lanes._DEFS.update(at=float("-inf"), defs=None)
    _spec(tmp_path / "specs", "a", "a")
    with pytest.raises(NotImplementedError, match="no launcher"):
        lanes.command(lanes.parse("tpu: a", tmp_path / "specs"))
    assert lanes.capacity_for("tpu", [], {}) == 0

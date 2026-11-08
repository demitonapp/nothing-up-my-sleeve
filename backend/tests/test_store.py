"""The one store, phase 1 (DECISIONS.md, "One store: Postgres, by the viable system"): data/'s small state brought
into Postgres and read from there; nothing falling back to the files; a hired box sailing under papers."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, select

from thorp import paths, store, store_import, vsm
from thorp.viable.records import GateDecision, Helm
from thorp.viable.s3_control import charter as s3
from thorp.viable.s4_intelligence import market as s4
from thorp.viable.s5_policy import charter as s5


def _write(d, name, obj):
    p = d / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if name.endswith(".jsonl"):
        p.write_text("".join(json.dumps(x) + "\n" for x in obj) + "not json\n")
    else:
        p.write_text(json.dumps(obj))
    return p


@pytest.fixture
def old_files(tmp_thorp):
    d = paths.data_dir()
    _write(d, "policies.json", {"stores": True, "intake": False})
    _write(d, "policy-exceptions.json", {"stores": {"reason": "queued before", "adopted": "16:11, Justin",
                                                    "runs": ["a", "b"], "patterns": ["c-*"], "follow_ups": "later"}})  # fmt: skip
    _write(d, "charter.json", {"weekly_budget": 40, "gpus": {"RTX 4090": 0.45}})
    _write(d, "gate-log.jsonl", [
        {"at": "2026-11-07T18:54:41", "name": "v1", "ship": "S", "where": "voyage", "verdict": "passed",
         "decisions": [{"policy": "stores", "how": "excepted", "why": "queued before"}]},
        {"at": "2026-11-08T13:25:23", "name": "v2", "ship": None, "where": "charter", "verdict": "refused",
         "decisions": [{"policy": "charter", "how": "refused", "why": "over budget"}]},
    ])  # fmt: skip
    _write(d, "charter-log.jsonl", [
        {"at": "2026-11-08T03:00:00+00:00", "event": "hired", "instance": 7, "run_id": "r1", "gpu": "RTX 4090",
         "dph": 0.4, "started": 1.0},
        {"at": "2026-11-08T04:00:00+00:00", "event": "released", "instance": 7, "run_id": "r1", "gpu": "RTX 4090",
         "dph": 0.4, "started": 1.0, "ended": 3601.0, "cost": 0.4, "status": "home", "tokens_per_s": 9000.0},
    ])  # fmt: skip
    _write(d, "charter-market.jsonl", [
        {"at": "2026-11-08T03:21:55+00:00", "gpu": "RTX 4090", "offer_id": 0, "dph": 0.5, "reliability": 0.98,
         "hours": 0.4, "cost": 0.2},
    ])  # fmt: skip
    return d


def test_the_import_brings_every_file_in_once(old_files):
    first = store_import.run(log=lambda *a: None)
    assert first == {"policies.json": 2, "policy-exceptions.json": 1, "charter.json": 2, "gate-log.jsonl": 2,
                     "charter-log.jsonl": 2, "charter-market.jsonl": 1}  # fmt: skip
    assert set(store_import.run(log=lambda *a: None).values()) == {0}  # again: nothing doubled
    # and read back from the store, in the shapes the readers have always had
    assert vsm._enforcement() == {"stores": True, "intake": False}
    assert vsm.enforced("stores") and vsm._exceptions() == {
        "stores": {"reason": "queued before", "adopted": "16:11, Justin", "runs": ["a", "b"], "patterns": ["c-*"],
                   "follow_ups": "later"}
    }
    assert vsm.excepted("stores", {"name": "c-7"}) == "queued before"
    t = s5.terms()
    assert t["weekly_budget"] == 40 and t["gpus"]["RTX 4090"] == 0.45 and t["gpus"]["RTX 5090"] == s5.DEFAULTS["gpus"]["RTX 5090"]
    log = vsm.gate_log()
    assert [r["name"] for r in log] == ["v2", "v1"]  # newest first
    assert log[1] == {"at": "2026-11-07T18:54:41", "name": "v1", "ship": "S", "where": "voyage", "verdict": "passed",
                      "decisions": [{"policy": "stores", "how": "excepted", "why": "queued before"}]}  # fmt: skip
    assert [(r["event"], r.get("status")) for r in s3.log()] == [("hired", None), ("released", "home")]
    assert s3.out_now() == [] and s3.log()[-1]["tokens_per_s"] == 9000.0
    assert s4.reads() == [{"at": "2026-11-08T03:21:55+00:00", "gpu": "RTX 4090", "offer_id": 0, "dph": 0.5,
                           "reliability": 0.98, "hours": 0.4, "cost": 0.2}]  # fmt: skip


def test_a_change_to_a_file_after_the_import_is_brought_in(old_files):
    store_import.run(log=lambda *a: None)
    _write(old_files, "policies.json", {"stores": False, "intake": False})
    assert store_import.run(log=lambda *a: None)["policies.json"] == 1 and not vsm.enforced("stores")


def test_retired_files_are_read_by_nothing(old_files):
    store_import.run(retire=True, log=lambda *a: None)
    assert not (old_files / "policies.json").exists() and (old_files / "policies.json.imported").exists()
    # a stray file written by old code after the cutover changes nothing: the store is read, not the file
    _write(old_files, "policies.json", {"stores": False})
    _write(old_files, "charter.json", {"weekly_budget": 1})
    assert vsm.enforced("stores") and s5.terms()["weekly_budget"] == 40


def test_no_silent_fallback_when_the_store_is_down(tmp_thorp, monkeypatch, spec):
    _write(paths.data_dir(), "policies.json", {"stores": False})
    down = create_engine("postgresql+psycopg://thorp@localhost:1/thorp", connect_args={"connect_timeout": 1})
    monkeypatch.setattr(store, "engine", lambda: down)
    assert store.ping() and "cannot be reached" in store.ping()
    with pytest.raises(store.StoreDown):
        vsm._enforcement()
    with pytest.raises(store.StoreDown):  # the gate cannot record its decision, so it makes none: no voyage sails
        vsm.gate(spec)
    with pytest.raises(store.StoreDown):
        s5.terms()
    with pytest.raises(store.StoreDown):
        s3.record("hired", instance=1)


def test_the_gate_records_each_decision_and_each_policys_part(spec):
    vsm.gate(spec, where="fitout builder")
    with store.session() as s:
        d = s.scalars(select(GateDecision)).one()
        assert (d.name, d.place, d.verdict, d.source) == (spec["name"], "fitout builder", "passed", "here")
    assert vsm.gate_log(1)[0]["where"] == "fitout builder"


def test_a_box_sails_under_papers_and_its_decisions_come_home_once(tmp_path, monkeypatch, spec):
    vsm.set_switch("intake", False, "a test")
    s5.set_term("weekly_budget", 25, "a test")
    papers = tmp_path / "rid.papers.json"
    papers.write_text(json.dumps(store.papers_for_box()))
    assert json.loads(papers.read_text())["charter_terms"] == {"weekly_budget": 25}
    monkeypatch.setenv("THORP_PAPERS", str(papers))
    down = create_engine("postgresql+psycopg://thorp@localhost:1/thorp", connect_args={"connect_timeout": 1})
    with monkeypatch.context() as m:  # aboard, the store is out of reach, and is never asked
        m.setattr(store, "engine", lambda: down)
        assert vsm._enforcement() == {"intake": False} and s5.terms()["weekly_budget"] == 25
        vsm.gate(spec)
    monkeypatch.delenv("THORP_PAPERS")
    log = papers.with_name("rid.papers.gate-log.jsonl")  # store.papers_log() aboard
    assert json.loads(log.read_text().splitlines()[0])["verdict"] == "passed"
    assert vsm.gate_log() == []  # not home yet
    assert store.fold_gate_log(log, source="box papers rid") == 1
    assert store.fold_gate_log(log, source="box papers rid") == 0  # brought home twice (every pull): kept once
    assert vsm.gate_log()[0]["name"] == spec["name"]


def test_the_helm_is_recorded_while_held_and_cleared_after(tmp_thorp):
    assert vsm.helm() is None
    with vsm.at_sea("a voyage", kind="voyage"):
        h = vsm.helm()
        assert h["name"] == "a voyage" and h["kind"] == "voyage"
        with store.session() as s:
            assert s.get(Helm, "mac").name == "a voyage"
        assert not (paths.data_dir() / "helm.json").exists()  # at home the record is in s2, not a file
    assert vsm.helm() is None
    with store.session() as s:
        assert s.get(Helm, "mac") is None


def test_s5_decisions_are_made_in_words(capsys):
    from thorp import cli

    assert cli.main(["s5", "switch", "stores", "off", "--words", "Justin, a test"]) == 0
    assert not vsm.enforced("stores")
    assert cli.main(["s5", "term", "voyage_budget", "12", "--words", "Justin, a test"]) == 0
    assert s5.terms()["voyage_budget"] == 12
    with pytest.raises(KeyError):
        s5.set_term("no_such_term", 1)
    assert cli.main(["store", "ping"]) == 0


def test_the_dashboard_reads_the_same_store_and_says_when_it_is_down(monkeypatch, spec):
    import json as _json
    import threading
    import urllib.error
    import urllib.request
    from http.server import ThreadingHTTPServer

    from thorp.dash import server

    vsm.gate(spec)  # a decision the gate made is the one the governance page shows
    srv = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        assert _json.load(urllib.request.urlopen(base + "/api/store")) == {"up": True, "why": None}
        assert vsm.gate_log(1)[0]["name"] == spec["name"]
        down = create_engine("postgresql+psycopg://thorp@localhost:1/thorp", connect_args={"connect_timeout": 1})
        monkeypatch.setattr(store, "engine", lambda: down)
        d = _json.load(urllib.request.urlopen(base + "/api/store"))
        assert d["up"] is False and "cannot be reached" in d["why"]
        monkeypatch.setattr(server, "api_governance", lambda: vsm.gate_log())
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(base + "/api/governance")
        assert e.value.code == 503 and _json.load(e.value)["store"] == "down"
    finally:
        srv.shutdown()


# ---------------------------------------------------------------- phase 1b


@pytest.fixture
def old_files_1b(tmp_thorp):
    d = paths.data_dir()
    _write(d, "compare/deck-EleutherAI--pythia-14m.json", {"model": "EleutherAI/pythia-14m", "metrics": {"a": 1.0}})
    _write(d, "compare/chain-grades.json", {"models": {"EleutherAI/pythia-14m": {"kin_test": {"lift": 0.9}}}, "chains": {}})
    _write(d, "compare/knockout-microsoft__phi-2.json", {"verdict": {"x": "shown"}})
    _write(d, "compare/nevermore-vs-trigrams.json", [{"run": "a"}])
    _write(d, "thorp-versions.json", {"9m": [{"v": 1, "ship_key": "9m:abc", "ship": "Argo", "chaining_lift": -0.0283,
                                              "crowned": "2026-11-07T12:42"}]})  # fmt: skip
    _write(d, "stores.json", {"prose": {"path": "lists/stores/prose.csv", "books": 2, "tokens": 30, "ranked_by": "x",
                                        "repeat_rate": 0.03, "sha1": "f00", "candidates": 3}})  # fmt: skip
    _write(d, "acquisition/intakes/in-20261107-190016.json", {"id": "in-20261107-190016", "list": "l.csv", "status": "done",
                                                              "started": "2026-11-07T19:00:16", "finished": None, "counts": {"admitted": 1}})  # fmt: skip
    same = {"at": "2026-11-07T19:00:17", "intake": "in-20261107-190016", "how": "intake", "book_id": "", "verdict": "unresolved",
            "refused": [], "notes": []}  # fmt: skip
    _write(d, "acquisition/log.jsonl", [{**same, "title": "Pindar"}, {**same, "title": "Pindar"}, {**same, "title": "Sophocles"}])
    _write(d, "table/fl-pathfinder.jsonl", [{"at": "2026-11-07T09:18:21", "question": "Good morning.", "answer": "Trequire",
                                             "temperature": 0.6, "seed": None, "stopped": "length"}])  # fmt: skip
    t = d / "tokenisers" / "abc123"
    _write(t, "settings.json", {"vocab": 2048, "clean": "unwrap-v2"})
    _write(t, "books.json", ["b1", "b2"])
    _write(t, "stats.json", {"b1": {"tokens": 10}})
    return d


def test_the_1b_import_brings_every_file_in_once_and_as_it_was(old_files_1b):
    from thorp import acquisition, leaderboard, stores
    from thorp.viable.records import TableTalk, TokeniserBook, TokeniserRecord
    from thorp.viable.s4_intelligence import readings

    first = store_import.run(log=lambda *a: None)
    assert first == {"compare": 4, "thorp-versions.json": 1, "stores.json": 1, "acquisition": 4, "table": 1, "tokenisers": 1}
    assert set(store_import.run(log=lambda *a: None).values()) == {0}
    assert readings.chain_grades() == {"EleutherAI/pythia-14m": {"kin_test": {"lift": 0.9}}}
    assert readings.get("deck-EleutherAI--pythia-14m")["metrics"] == {"a": 1.0}
    assert [n for n, _ in readings.glob("knockout-*")] == ["knockout-microsoft__phi-2"]
    assert readings.get("nevermore-vs-trigrams") == [{"run": "a"}]
    assert leaderboard._versions() == json.loads((old_files_1b / "thorp-versions.json").read_text())
    assert stores.stores() == json.loads((old_files_1b / "stores.json").read_text())
    assert [r["title"] for r in acquisition.read_log()] == ["Pindar", "Pindar", "Sophocles"]  # alike lines kept as often
    assert acquisition.intakes()[0]["counts"] == {"admitted": 1} and acquisition.count_intakes() == 1
    with store.session() as s:
        assert s.scalars(select(TableTalk.answer).where(TableTalk.voyage == "fl-pathfinder")).all() == ["Trequire"]
        assert s.get(TokeniserRecord, "abc123").settings["clean"] == "unwrap-v2"
        assert sorted(b.book_id for b in s.scalars(select(TokeniserBook))) == ["b1", "b2"]


def test_the_1b_cutover_retires_all_but_the_tokenisers(old_files_1b):
    store_import.run(retire=True, log=lambda *a: None)
    d = old_files_1b
    assert (d / "compare.imported").is_dir() and not (d / "compare").exists()
    assert (d / "table.imported").is_dir() and (d / "thorp-versions.json.imported").exists()
    assert (d / "acquisition" / "intakes.imported").is_dir() and (d / "acquisition" / "log.jsonl.imported").exists()
    assert (d / "tokenisers" / "abc123" / "settings.json").exists()  # the artifact a voyage reads stays


def test_a_reading_is_named_as_its_file_was_and_keeps_no_nan():
    from thorp.viable.s4_intelligence import readings

    assert readings.kind_of("knockout-deck-Qwen--Qwen3-4B") == ("knockout-deck", "Qwen/Qwen3-4B")
    assert readings.kind_of("knockout-microsoft__phi-2") == ("knockout", "microsoft/phi-2")
    assert readings.kind_of("mlx-community--Qwen3-0.6B-bf16__hole-cards-unseen") == ("scored", "mlx-community/Qwen3-0.6B-bf16")
    readings.put("deck-x", {"model": "x", "metrics": {"a": float("nan"), "b": 1.0}})
    assert readings.get("deck-x")["metrics"] == {"a": None, "b": 1.0}


def test_a_crowning_is_kept(tmp_thorp):
    from thorp import leaderboard

    cur = leaderboard.crown([{"preset": "9m", "ship_key": "9m:a", "ship": "Argo", "chaining_lift": 0.2, "sailings": 2}])
    assert cur["9m"]["v"] == 1 and leaderboard._versions()["9m"][0]["ship"] == "Argo"
    leaderboard.crown([{"preset": "9m", "ship_key": "9m:b", "ship": "Endeavour", "chaining_lift": 0.9, "sailings": 2}])
    assert [h["ship"] for h in leaderboard._versions()["9m"]] == ["Argo", "Endeavour"]


def test_the_intake_holder_is_recorded_while_held(tmp_thorp):
    from thorp import acquisition

    with acquisition._intake_lock("in-1", "l.csv", log=lambda *a: None):
        assert acquisition.holder()["id"] == "in-1"
    assert acquisition.holder() is None

"""The ledger's backfill into Postgres (thorp/ledger_store.py): a synthetic SQLite run copies field for field, a
second `run(...)` fills only what it carries, and the count check passes."""

from __future__ import annotations

from thorp import ledger, ledger_store


def test_backfill_and_verify(tmp_thorp):
    rec = ledger.Ledger()  # THORP_LEDGER is the test's temp file (tmp_thorp)
    rec.run(
        {
            "run_id": "ledger-test-1",
            "name": "ledger-test",
            "ship": "s1",
            "spec_json": '{"a": 1}',
            "commit": "abc",
            "hardware": "mac",
            "started": "2026-11-09T00:00:00+00:00",
            "finished": "2026-11-09T00:01:00+00:00",
            "status": "finished",
            "tokens_seen": 100,
            "wall_minutes": 1.5,
        }
    )
    rec.metrics("ledger-test-1", 0, {"loss": 2.0, "lr": 0.01})
    rec.metrics("ledger-test-1", 1, {"loss": 1.9, "lr": 0.009})
    rec.evals(
        [
            {"run_id": "ledger-test-1", "step": 1, "set": "hole", "book_id": "b1",
             "ce_nats": 4.0, "bpb": 1.7, "tokens": 10, "bytes": 30}
        ]
    )
    rec.artifact("ledger-test-1", 0, "checkpoint", "/tmp/c", "sha1", "")
    rec.artifact("ledger-test-1", 0, "recipe", "", "", '{"name": "x"}')
    rec.close()

    counts = ledger_store.backfill()
    assert counts == {"runs": 1, "metrics": 4, "evals": 1, "artifacts": 2}
    assert ledger_store.verify()

    # a second copy is a no-op in counts (delete then re-insert), and the rows match
    assert ledger_store.backfill()["runs"] == 1
    assert ledger_store.verify()


def test_run_upsert_fills_only_what_it_carries(tmp_thorp):
    from thorp import store

    rec = ledger.Ledger()
    rec.run(
        {
            "run_id": "ledger-test-2",
            "name": "second",
            "ship": "s2",
            "spec_json": "{}",
            "started": "2026-11-09T00:00:00+00:00",
            "status": "running",
        }
    )
    rec.close()
    ledger_store.backfill(only=["ledger-test-2"])

    # a later `run(...)` carries only finished/status: it must not blank name/ship/spec_json
    rec = ledger.Ledger()
    rec.run({"run_id": "ledger-test-2", "finished": "2026-11-09T01:00:00+00:00", "status": "finished"})
    rec.close()
    ledger_store.backfill(only=["ledger-test-2"])

    with store.session() as s:
        row = s.get(ledger_store.Run, "ledger-test-2")
        assert row.name == "second"
        assert row.ship == "s2"
        assert row.spec_json == "{}"
        assert row.status == "finished"
        assert row.finished == "2026-11-09T01:00:00+00:00"


def test_read_helpers_mirror_sqlite(tmp_thorp):
    rec = ledger.Ledger()
    rec.run({"run_id": "read-1", "name": "read", "ship": "s", "spec_json": '{"model":{"preset":"9m"}}',
             "started": "2026-11-09T00:00:00+00:00", "status": "finished", "tokens_seen": 20, "wall_minutes": 0.2})
    rec.metrics("read-1", 0, {"loss": 1.0, "lr": 0.01})
    rec.metrics("read-1", 1, {"loss": 0.9, "lr": 0.009})
    rec.metrics("read-1", 1, {"loss": 0.85})  # a later row at one step stands
    rec.evals([{"run_id": "read-1", "step": 1, "set": "hole", "book_id": "b", "ce_nats": 4.0, "bpb": 1.7, "tokens": 5, "bytes": 15}])
    rec.artifact("read-1", 0, "recipe", "", "", "{}")
    rec.artifact("read-1", 1, "recipe", "", "", '{"v":2}')
    rec.close()
    ledger_store.backfill(only=["read-1"])

    assert ledger_store.get_run("read-1")["name"] == "read"
    series = ledger_store.metrics_series("read-1")
    assert series["loss"] == [[0, 1], [1.0, 0.85]]  # the duplicate step 1 keeps the later value
    assert series["lr"] == [[0, 1], [0.01, 0.009]]
    assert ledger_store.metric_at("read-1", "loss", "last") == 0.85
    assert ledger_store.metric_at("read-1", "loss", "first") == 1.0
    assert ledger_store.evals("read-1")[0]["set"] == "hole"
    assert ledger_store.artifact("read-1", "recipe")["text"] == '{"v":2}'  # latest
    assert ledger_store.artifact("read-1", "recipe", latest=False)["text"] == "{}"  # first


def test_recorder_is_the_store_at_home_and_sqlite_aboard(tmp_thorp, monkeypatch):
    from thorp.ledger import Ledger, recorder
    from thorp.ledger_store import PgLedger

    for k in ("THORP_LEDGER_DUAL", "THORP_LEDGER_PG", "THORP_SHIP_LOG"):
        monkeypatch.delenv(k, raising=False)
    assert isinstance(recorder(), PgLedger)  # the cut-over (10 November): Postgres is the Mac's default
    monkeypatch.setenv("THORP_SHIP_LOG", "1")
    assert isinstance(recorder(), Ledger)  # a hired box writes its own SQLite ship's log


def test_sqlite_read_helpers_by_name_and_artifact(tmp_thorp):
    rec = ledger.Ledger()
    rec.run({"run_id": "find-1", "name": "find", "ship": "s", "spec_json": "{}",
             "started": "2026-11-09T00:00:00+00:00", "status": "finished"})
    rec.run({"run_id": "find-2", "name": "find", "ship": "s", "spec_json": "{}",
             "started": "2026-11-09T00:01:00+00:00", "status": "running"})
    rec.artifact("find-1", 0, "recipe", "", "", "{}")
    rec.artifact("find-1", 1, "recipe", "", "", '{"v":2}')

    assert rec.get_run_by_name("find", finished=True)["run_id"] == "find-1"
    assert rec.get_run_by_name("find")["run_id"] == "find-2"  # newest started, any status
    assert rec.get_run_by_name("nope") is None
    assert rec.find_run("find")["run_id"] == "find-2"
    assert rec.find_run("find-1")["run_id"] == "find-1"  # a unique run_id prefix
    assert rec.latest_artifact_text("find-1", "recipe") == '{"v":2}'
    assert rec.latest_artifact_text("find-1", "nope") is None
    rec.close()


def test_recorder_and_reader_are_postgres_only_under_thorp_ledger_pg(tmp_thorp, monkeypatch):
    from thorp.ledger import Ledger, reader, recorder

    rec = Ledger()
    rec.run(
        {
            "run_id": "pg-only-1", "name": "pg-only", "ship": "s", "spec_json": '{"model":{"preset":"9m"}}',
            "started": "2026-11-09T00:00:00+00:00", "status": "finished",
        }
    )
    rec.artifact("pg-only-1", 0, "recipe", "", "", "{}")
    rec.artifact("pg-only-1", 1, "recipe", "", "", '{"v":2}')
    rec.close()
    ledger_store.backfill(only=["pg-only-1"])

    monkeypatch.setenv("THORP_LEDGER_PG", "1")
    monkeypatch.delenv("THORP_LEDGER_DUAL", raising=False)

    r = recorder()
    assert isinstance(r, ledger_store.PgLedger)  # the writer is Postgres-only
    rd = reader()
    assert isinstance(rd, ledger_store.PgLedger)
    assert rd.get_run("pg-only-1")["name"] == "pg-only"
    assert rd.get_run_by_name("pg-only", finished=True)["run_id"] == "pg-only-1"
    assert rd.get_run_by_name("nope") is None
    assert rd.find_run("pg-only")["run_id"] == "pg-only-1"
    assert rd.find_run("pg-only-1")["run_id"] == "pg-only-1"
    assert rd.latest_artifact_text("pg-only-1", "recipe") == '{"v":2}'
    assert rd.latest_artifact_text("pg-only-1", "nope") is None
    rd.checkpoint_wal()  # a no-op, must not raise
    rd.close()
    r.close()


def test_dual_recorder_writes_both(tmp_thorp, monkeypatch):
    from sqlalchemy import func, select

    from thorp import store
    from thorp.ledger import DualRecorder, Ledger, recorder

    monkeypatch.setenv("THORP_LEDGER_DUAL", "1")
    rec = recorder()
    assert isinstance(rec, DualRecorder)

    rec.run(
        {
            "run_id": "dual-1", "name": "dual", "ship": "s", "spec_json": "{}",
            "started": "2026-11-09T00:00:00+00:00", "status": "finished", "tokens_seen": 10, "wall_minutes": 0.1,
        }
    )
    rec.metrics("dual-1", 0, {"loss": 1.0})
    rec.metrics("dual-1", 1, {"loss": 0.9})
    rec.evals([{"run_id": "dual-1", "step": 0, "set": "hole", "book_id": "b", "ce_nats": 4.0, "bpb": 1.7, "tokens": 5, "bytes": 15}])
    rec.evals([{"run_id": "dual-1", "step": 0, "set": "other", "book_id": "b", "ce_nats": 5.0, "bpb": 1.8, "tokens": 5, "bytes": 15}])
    rec.artifact("dual-1", 0, "recipe", "", "", "{}")
    rec.artifact("dual-1", 1, "checkpoint", "/tmp/c", "sha1", "")
    # a resume forgets everything after a step; a re-score clears one set: both must mirror
    rec.truncate_after("dual-1", 0)  # step 1 goes: metric step 1, artifact step 1
    rec.clear_step("dual-1", 0, tables=("evals",), sets=["hole"])  # evals step 0 set=hole goes
    rec.close()

    # SQLite got it
    sql = Ledger()
    assert sql.get_run("dual-1")["name"] == "dual"
    assert len(sql.query("select * from metrics where run_id=?", ["dual-1"])) == 1  # step 0 survived the truncate
    assert len(sql.query("select * from evals where run_id=?", ["dual-1"])) == 1  # "other" survived, "hole" cleared
    assert len(sql.query("select * from artifacts where run_id=?", ["dual-1"])) == 1  # step 0 survived
    sql.close()

    # Postgres got the same
    with store.session() as s:
        assert s.get(ledger_store.Run, "dual-1").name == "dual"
        assert s.scalar(select(func.count()).select_from(ledger_store.Metric).where(ledger_store.Metric.run_id == "dual-1")) == 1
        assert s.scalar(select(func.count()).select_from(ledger_store.Eval).where(ledger_store.Eval.run_id == "dual-1")) == 1
        assert s.scalar(select(func.count()).select_from(ledger_store.Artifact).where(ledger_store.Artifact.run_id == "dual-1")) == 1


def test_dashboard_readers_answer_from_postgres(tmp_thorp, monkeypatch):
    from thorp import ledger, ledger_store
    from thorp.dash import server

    rec = ledger.Ledger()
    rec.run(
        {
            "run_id": "pg-read-1", "name": "pg-read", "ship": "s",
            "spec_json": '{"model":{"preset":"9m"},"seed":2,"eval":{"sets":["hole.csv"]}}',
            "started": "2026-11-09T00:00:00+00:00", "status": "finished", "tokens_seen": 100, "wall_minutes": 1.5,
        }
    )
    rec.metrics("pg-read-1", 0, {"loss": 1.0})
    rec.metrics("pg-read-1", 1, {"loss": 0.9})
    rec.evals([{"run_id": "pg-read-1", "step": 1, "set": "hole", "book_id": "b", "ce_nats": 4.0, "bpb": 1.7, "tokens": 5, "bytes": 15}])
    rec.artifact("pg-read-1", 0, "recipe", "", "", "{}")
    rec.close()
    ledger_store.backfill(only=["pg-read-1"])

    monkeypatch.setenv("THORP_LEDGER_PG", "1")
    runs = server.api_runs()
    assert [r["run_id"] for r in runs] == ["pg-read-1"]
    assert runs[0]["preset"] == "9m"  # derived from spec_json, parsed in Python as in the SQLite path
    assert runs[0]["seed"] == 2
    assert server.api_metrics("pg-read-1")["loss"] == [[0, 1], [1.0, 0.9]]
    assert server._metric("pg-read-1", "loss", "last") == 0.9
    assert server._metric("pg-read-1", "loss", "first") == 1.0
    assert server.api_evals("pg-read-1")[0]["set"] == "hole"
    assert server._artifact("pg-read-1", "recipe")["text"] == "{}"


def test_api_compare_from_postgres(tmp_thorp, monkeypatch):
    from thorp import ledger, ledger_store
    from thorp.dash import server

    rec = ledger.Ledger()
    rec.run(
        {
            "run_id": "cmp-1", "name": "cmp", "ship": "s",
            "spec_json": '{"model":{"preset":"9m"},"seed":1,"eval":{"sets":["hole.csv"]}}',
            "started": "2026-11-09T00:00:00+00:00", "status": "finished",
        }
    )
    rec.metrics("cmp-1", 0, {"plan/tokens_total": 1000, "plan/total_steps": 100, "eval/hole/bpb_mean": 1.5, "eval/hole/bpb_mean_en": 1.6, "grad_norm/layer_0": 0.5, "lr": 0.01})
    rec.artifact("cmp-1", 0, "recipe", "", "", "[]")
    rec.close()
    ledger_store.backfill(only=["cmp-1"])

    monkeypatch.setenv("THORP_LEDGER_PG", "1")
    cmp = server.api_compare()
    assert [x["run_id"] for x in cmp] == ["cmp-1"]
    assert cmp[0]["bpb"] == [1.5]
    assert cmp[0]["bpb_en"] == [1.6]
    assert cmp[0]["push"]["grad_norm/layer_0"] == [[0], [0.5]]
    assert cmp[0]["push"]["lr"] == [[0], [0.01]]
    assert cmp[0]["n_books"] == 0  # recipe artifact is '[]'


def test_read_primitives_from_postgres(tmp_thorp):
    rec = ledger.Ledger()
    rec.run({"run_id": "prim-1", "name": "prim", "ship": "s", "spec_json": '{"model":{"preset":"9m"}}',
             "started": "2026-11-09T00:00:00+00:00", "status": "finished", "wall_minutes": 1.0})
    rec.metrics("prim-1", 0, {"stars/bridge/layer_0": 0.5, "stars/bridge/max_score": 0.3, "tricks/logic_test/lift": 0.2})
    rec.metrics("prim-1", 1, {"stars/bridge/layer_0": 0.8, "stars/bridge/max_score": 0.6, "tricks/logic_test/lift": 0.4})
    rec.evals([
        {"run_id": "prim-1", "step": 0, "set": "hole-cards-unseen", "book_id": "b1", "ce_nats": 4.0, "bpb": 1.7, "tokens": 5, "bytes": 15},
        {"run_id": "prim-1", "step": 1, "set": "hole-cards-unseen", "book_id": "b1", "ce_nats": 4.1, "bpb": 1.6, "tokens": 5, "bytes": 15},
        {"run_id": "prim-1", "step": 1, "set": "hole-cards-unseen", "book_id": "b2", "ce_nats": 5.0, "bpb": 1.9, "tokens": 5, "bytes": 15},
    ])
    rec.artifact("prim-1", 0, "stars", "", "", '{"previous_word": [[0.1, 0.2], [0.3, 0.4]]}')
    rec.artifact("prim-1", 1, "stars", "", "", '{"previous_word": [[0.2, 0.3], [0.4, 0.5]]}')
    rec.close()
    ledger_store.backfill(only=["prim-1"])

    assert ledger_store.metric_series("prim-1", "stars/bridge/layer_0") == [[0, 1], [0.5, 0.8]]
    assert {x["name"] for x in ledger_store.metrics_matching("prim-1", "stars/bridge/")} == {
        "stars/bridge/layer_0", "stars/bridge/max_score"
    }
    assert len(ledger_store.metrics_named("prim-1", {"stars/bridge/max_score", "tricks/logic_test/lift"})) == 4
    assert ledger_store.metrics_max("prim-1", ["stars/bridge/max_score"]) == {"stars/bridge/max_score": 0.6}
    assert ledger_store.latest_evals("prim-1", "hole-cards-unseen") == [
        {"book_id": "b1", "bpb": 1.6}, {"book_id": "b2", "bpb": 1.9}
    ]
    assert ledger_store.metric_max_ts("prim-1", "stars/bridge/layer_0") > 0
    assert [a["step"] for a in ledger_store.artifacts_of_kind("prim-1", "stars")] == [0, 1]


def test_a_read_ends_the_transaction_it_opened():
    # 11 November: a long-lived reader sat "idle in transaction" for hours and held a lock on s1.runs
    from thorp import store
    from thorp.ledger_store import PgLedger

    pg = PgLedger()
    pg.query("select 1 as one")
    assert not pg._s.in_transaction()
    with store.engine().connect() as c:  # an ALTER-strength lock is not blocked by the reader
        c.exec_driver_sql("set lock_timeout = '2s'")
        c.exec_driver_sql("lock table s1.runs in access exclusive mode")
        c.rollback()
    # a transaction the caller already opened stays open for it
    pg._s.connection()
    assert pg._s.in_transaction()
    pg.query("select 1 as one")
    assert pg._s.in_transaction()
    pg._s.rollback()
    pg.close()

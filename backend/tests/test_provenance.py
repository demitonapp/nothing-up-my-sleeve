"""What a run id does not pin, kept beside it (thorp/versioning.py provenance, 11 November, the audit's item 3): the
lists' bytes, the parents by id, the tokeniser, the code; a resume under another tokeniser refused; a finished run
whose lists have changed said loudly; parents named by id; and the read-only drift report."""

from __future__ import annotations

import dataclasses
import json
import shutil

import pytest
import yaml

from thorp import paths, train, versioning
from thorp.ledger import Ledger


@pytest.fixture
def ships(tmp_path, monkeypatch):
    """A ships folder of its own, with two lists the spec names."""
    root = tmp_path / "ships"
    (root / "lists").mkdir(parents=True)
    (root / "lists" / "recipe.csv").write_text("text\nloc-a\nloc-b\nloc-c\n")
    (root / "lists" / "hole.csv").write_text("text\nloc-hole\n")
    monkeypatch.setenv("THORP_SHIPS", str(root))
    return root


@pytest.fixture
def advisory_standard(monkeypatch):
    """The loop's tests, not the gate's: the SOP rule is advisory here (as in test_torch and test_scaffold)."""
    from thorp import liberty_machine

    monkeypatch.setitem(liberty_machine.POLICIES, "standard", dataclasses.replace(liberty_machine.POLICIES["standard"], enforced=False))


@pytest.fixture
def cpu():
    import mlx.core as mx

    before = mx.default_device()
    mx.set_default_device(mx.cpu)
    yield
    mx.set_default_device(before)


SHAPE = {"preset": "300k", "layers": 2, "width": 64, "heads": 2}


def listed(spec: dict) -> dict:
    """conftest's spec with its lists named under lists/ (so they are files in the ships folder)."""
    spec["model"].update(SHAPE)
    spec["data"]["recipe"] = "lists/recipe.csv"
    spec["data"]["refuse"] = ["lists/hole.csv"]
    spec["eval"]["sets"] = ["lists/hole.csv"]
    return spec


# ---------------------------------------------------------------- the document


def test_every_list_a_spec_names_is_found_wherever_it_is_named(spec):
    spec["data"]["stages"] = [{"name": "a", "recipe": "lists/a.csv", "passes": 1}, {"name": "b", "recipe": "lists/b.csv"}]
    spec["data"]["first"] = "lists/first.csv"
    spec["tokeniser"]["train_on"] = "lists/pool.csv"
    spec["eval"]["options"] = {"pairs": {"file": "lists/discovery-x.csv"}}
    spec["fitout"] = {"key": "lists/label.csv"}  # a label: not part of the id, not looked into
    spec["question"] = "does lists/recipe.csv matter?"  # prose, not a path
    got = versioning.list_fields(spec)
    assert got == {
        "data.recipe": "recipe.csv",
        "data.refuse[0]": "hole.csv",
        "data.stages[0].recipe": "lists/a.csv",
        "data.stages[1].recipe": "lists/b.csv",
        "data.first": "lists/first.csv",
        "tokeniser.train_on": "lists/pool.csv",
        "eval.sets[0]": "hole.csv",
        "eval.options.pairs.file": "lists/discovery-x.csv",
    }
    assert "recipe" not in versioning.list_fields({"tokeniser": {"train_on": "recipe"}}).values()


def test_the_document_pins_lists_code_backend_and_environment(spec, ships, monkeypatch):
    listed(spec)
    monkeypatch.setenv("THORP_DEVICE", "cpu")
    monkeypatch.setenv("THORP_PG", "postgresql://u:secret@h/db")
    rid = train.run_id(spec)
    doc = versioning.provenance(spec, rid, "tok123")
    assert doc["run_id"] == doc["id_of_spec"] == rid
    assert doc["spec"] == json.loads(train.canonical(spec))  # the spec exactly as hashed
    assert doc["lists"]["lists/recipe.csv"] == versioning._list_sha("lists/recipe.csv") is not None
    assert set(doc["lists"]) == {"lists/recipe.csv", "lists/hole.csv"}
    assert doc["tokeniser_id"] == "tok123"
    assert len(doc["code"]["commit"]) == 40 and isinstance(doc["code"]["dirty"], bool)
    assert doc["code"]["dirty"] == (doc["code"]["diff_sha1"] is not None) or doc["code"]["diff_bytes"] == 0
    assert doc["backend"]["backend"] == "mlx" and doc["backend"]["mlx"]
    assert doc["env"]["changes_results"]["THORP_DEVICE"] == "cpu"
    assert "THORP_PG" in doc["env"]["logging_only_set"] and "secret" not in json.dumps(doc)  # by name only
    assert doc["parents"] == {}


def test_a_list_edited_under_the_same_id_is_drift(spec, ships):
    listed(spec)
    doc = versioning.provenance(spec, train.run_id(spec), "t")
    assert versioning.list_drift(doc) == {}
    before = doc["lists"]["lists/recipe.csv"]
    (ships / "lists" / "recipe.csv").write_text("text\nloc-a\nloc-b\n")
    assert train.run_id(spec) == doc["run_id"]  # the id does not see it ...
    assert versioning.list_drift(doc) == {"lists/recipe.csv": (before, versioning._list_sha("lists/recipe.csv"))}
    (ships / "lists" / "hole.csv").unlink()
    assert versioning.list_drift(doc)["lists/hole.csv"][1] is None  # a list gone is drift too


def test_a_failure_never_stops_a_voyage(spec, monkeypatch):
    lines = []
    monkeypatch.setattr(versioning, "provenance", lambda *a, **k: 1 / 0)
    assert versioning.record_provenance(spec, "r" * 40, "t", Ledger(None), lines.append) is None
    assert lines and "not recorded" in lines[0]


def test_one_section_that_fails_keeps_the_others(spec, monkeypatch):
    monkeypatch.setattr(versioning, "code_state", lambda: 1 / 0)
    doc = versioning.provenance(spec, train.run_id(spec), "t")
    assert "ZeroDivisionError" in doc["code"]["error"] and doc["backend"]["backend"] == "mlx"


# ---------------------------------------------------------------- the tokeniser check on resume


def test_a_resume_under_another_tokeniser_is_refused():
    assert versioning.tokeniser_mismatch({"tokeniser_id": "abc"}, "abc") is None
    assert versioning.tokeniser_mismatch({}, "abc") is None  # an old checkpoint names none: not judged
    why = versioning.tokeniser_mismatch({"run_id": "f" * 40, "step": 50, "tokeniser_id": "a" * 40}, "b" * 40)
    assert why and "refusing to resume" in why and "aaaaaaaaaaaa" in why and "bbbbbbbbbbbb" in why


def _tamper(rid: str) -> None:
    st = train.latest_checkpoint(rid) / "state.json"
    s = json.loads(st.read_text())
    s["tokeniser_id"] = "0" * 40
    st.write_text(json.dumps(s))


def test_the_mlx_loop_records_provenance_and_refuses_a_changed_tokeniser(
    library, spec, tmp_thorp, ships, cpu, advisory_standard
):
    spec["model"].update(SHAPE)
    spec["data"]["passes"] = 3
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rid = train.run_id(spec)
    rec = Ledger(tmp_thorp / "l.sqlite")
    lines: list[str] = []
    assert train.train(spec, prep, rec, stop_after=50, log=lines.append)["step"] == 50
    doc = versioning.stored_provenance(rid, rec)
    assert doc and doc["run_id"] == rid and doc["tokeniser_id"] == prep.tokeniser.id and doc["from_step"] == 0
    assert any(line.startswith("provenance:") for line in lines)
    # a resume records its own document after the checkpoint's step (it survives the resume's truncation and folds
    # home with the leg), and the first stays the run's
    assert train.train(spec, prep, rec, stop_after=60, log=lambda *a: None)["step"] == 60
    rows = rec.query("select step from artifacts where run_id=? and kind='provenance' order by step", [rid])
    assert [r["step"] for r in rows] == [0, 51]
    assert versioning.stored_provenance(rid, rec)["from_step"] == 0
    _tamper(rid)
    n = len(rec.query("select 1 from metrics where run_id=?", [rid]))
    with pytest.raises(ValueError, match="refusing to resume"):
        train.train(spec, prep, rec, stop_after=70, log=lambda *a: None)
    assert len(rec.query("select 1 from metrics where run_id=?", [rid])) == n  # refused before any truncation


def test_the_torch_loop_records_provenance_and_refuses_a_changed_tokeniser(
    library, spec, tmp_thorp, ships, cpu, advisory_standard, monkeypatch
):
    pytest.importorskip("torch")
    monkeypatch.setenv("THORP_DEVICE", "cpu")
    monkeypatch.delenv("THORP_BACKEND", raising=False)
    spec["model"].update(SHAPE)
    spec["model"]["backend"] = "torch"
    spec["optim"]["precision"] = "fp32"
    spec["data"]["passes"] = 3
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rid = train.run_id(spec)
    rec = Ledger(tmp_thorp / "t.sqlite")
    assert train.train(spec, prep, rec, stop_after=50, log=lambda *a: None)["step"] == 50
    doc = versioning.stored_provenance(rid, rec)
    assert doc["backend"]["backend"] == "torch" and doc["backend"]["torch"] and doc["tokeniser_id"] == prep.tokeniser.id
    _tamper(rid)
    with pytest.raises(ValueError, match="refusing to resume"):
        train.train(spec, prep, rec, stop_after=60, log=lambda *a: None)
    shutil.rmtree(paths.checkpoints_dir() / rid)


# ---------------------------------------------------------------- a finished run sailed again


def test_a_finished_run_whose_lists_changed_is_said_loudly(spec, ships, tmp_path, capsys, monkeypatch):
    listed(spec)
    p = tmp_path / "spec.yaml"
    p.write_text(yaml.safe_dump(spec))
    loaded = train.load_spec(p)
    rid = train.run_id(loaded)
    rec = Ledger(tmp_path / "l.sqlite")
    rec.run({"run_id": rid, "name": "test", "spec_json": train.canonical(loaded), "status": "finished"})
    rec.artifact(rid, 0, "provenance", "", "", json.dumps(versioning.provenance(loaded, rid, "t")))
    monkeypatch.setattr(train, "Log", lambda *a, **k: pytest.fail("a finished run is not sailed again"))
    train._run(p, rec)
    assert "WARNING" not in capsys.readouterr().out  # the same bytes: the row, and nothing more
    (ships / "lists" / "recipe.csv").write_text("text\nloc-z\n")
    assert train._run(p, rec)["status"] == "finished"
    out = capsys.readouterr().out
    assert "WARNING" in out and "lists/recipe.csv" in out and "lists/hole.csv" not in out


# ---------------------------------------------------------------- parents by id


def _pg_run(rid: str, name: str, status: str, started: str) -> None:
    from thorp.ledger_store import PgLedger

    pg = PgLedger()
    pg.run({"run_id": rid, "name": name, "status": status, "started": started, "spec_json": "{}"})
    pg.close()


def test_a_parent_is_found_by_id_or_by_name():
    old, new, sailing = "a" * 40, "b" * 40, "c" * 40
    _pg_run(old, "prov-seed", "finished", "2026-11-01T00:00:00")
    _pg_run(new, "prov-seed", "finished", "2026-11-02T00:00:00")
    _pg_run(sailing, "prov-seed", "running", "2026-11-03T00:00:00")
    lines: list[str] = []
    assert train.parent_run("prov-seed", "seeded_from", lines.append)["run_id"] == new  # by name: the newest
    assert train.parent_run(old, "seeded_from")["run_id"] == old  # by id: that very run
    assert lines == [f"seeded_from: prov-seed is run {new}"]
    with pytest.raises(LookupError, match="no finished run named 'nope'"):
        train.parent_run("nope", "teacher")
    with pytest.raises(LookupError, match="no finished run"):
        train.parent_run(sailing, "transplant")  # not finished
    spec = {"seeded_from": {"run": old}, "optim": {"teacher": {"run": "prov-seed"}}}
    got = versioning.parents(spec)
    assert got["seeded_from"] == {"ref": old, "by": "id", "run_id": old}
    assert got["teacher"] == {"ref": "prov-seed", "by": "name", "run_id": new}


def test_the_ships_papers_carry_a_parent_named_by_id(tmp_path):
    from thorp.viable.s2_coordination import charter

    rec = Ledger(tmp_path / "home.sqlite")
    old, new = "a" * 40, "b" * 40
    rec.run({"run_id": old, "name": "seed", "status": "finished", "started": "2026-11-01"})
    rec.run({"run_id": new, "name": "seed", "status": "finished", "started": "2026-11-02"})
    by_id = {"seeded_from": {"run": old}}
    by_name = {"optim": {"teacher": {"run": "seed"}}}
    assert charter.related_runs(by_id) == [old]
    assert [r["run_id"] for r in charter.related_rows(by_id, rec)] == [old]
    assert [r["run_id"] for r in charter.related_rows(by_name, rec)] == [new]
    carried = charter.papers(tmp_path / "papers.sqlite", by_id, "d" * 40, rec)
    assert carried == ["d" * 40, old]


# ---------------------------------------------------------------- the side table, and the report


def test_the_side_table_holds_the_first_sailing_and_its_resumes(spec, ships):
    from sqlalchemy import text

    from thorp import store
    from thorp.ledger_store import PgLedger

    listed(spec)
    rid = train.run_id(spec)
    pg = PgLedger()
    try:
        assert versioning.record_provenance(spec, rid, "t", pg, lambda *a: None)
        versioning.record_provenance(spec, rid, "t", pg, lambda *a: None, start=50)
        doc = versioning.stored_provenance(rid, pg)
        assert doc["from_step"] == 0 and [r["from_step"] for r in doc["resumes"]] == [50]
        assert "spec" not in doc["resumes"][0]
        assert pg.latest_artifact_text(rid, "provenance")  # and the artifact, which a box's ledger carries home
    finally:
        with store.session() as s:
            s.execute(text("delete from s1.run_provenance where run_id = :r"), {"r": rid})
        pg.close()


def test_the_drift_report_reads_what_was_recorded(spec, ships):
    from sqlalchemy import text

    from thorp import store
    from thorp.ledger_store import PgLedger

    listed(spec)
    a, b, c = dict(spec, seed=1), dict(spec, seed=2), dict(spec, seed=3, optim={**spec["optim"], "lr": 1e-3})
    ids = [train.run_id(x) for x in (a, b, c)]
    pg = PgLedger()
    for x, rid in zip((a, b, c), ids, strict=True):
        pg.run({"run_id": rid, "name": "r", "status": "finished", "spec_json": train.canonical(x)})
    versioning.assign(a, run_id=ids[0])  # the plan register's content fingerprint, tied to run a
    try:
        versioning.record_provenance(c, ids[2], "t", pg, lambda *a: None)  # run c has provenance; run b nothing
        r = versioning.drift_report(set(ids))
        assert (r["finished"], r["naming_lists"], r["with_provenance"], r["with_content_record"]) == (3, 3, 1, 1)
        assert (r["no_record"], r["same"], r["changed"]) == (1, 2, 0)
        (ships / "lists" / "recipe.csv").write_text("text\nloc-q\n")
        r = versioning.drift_report(set(ids))
        assert r["changed"] == 2 and r["same"] == 0
        assert {x["run_id"] for x in r["changed_runs"]} == {ids[0][:12], ids[2][:12]}
        assert r["plan_registered"] == 1 and r["plan_content_changed"] == 1  # run b: its plan, by run a
    finally:
        with store.session() as s:
            s.execute(text("delete from s1.run_provenance where run_id = :r"), {"r": ids[2]})
        pg.close()

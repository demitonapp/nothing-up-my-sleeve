"""S5 policy 'postgres' (13 November, Justin): everything a database does happens in Postgres. Two kinds of test: the database
refuses what it should whoever writes (the rules Python used to state are checks, a trigger and keys), and no module makes a
table at run time (a new one is a migration)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from thorp import expedition_goals, store

PKG = Path(__file__).resolve().parents[1] / "thorp"

# the SQLite and DuckDB files still holding records: each is a debt the policy names, moved by a decision of its own (DECISIONS.md,
# 'S5 policy "postgres"'). A module not on this list that makes a table at run time fails the test below.
SQLITE_DEBT = {
    "manifest.py",
    "ledger.py",
    "viable/s2_coordination/charter.py",
    "sources/bulk.py",
}
DDL = re.compile(r"\b(create\s+(unique\s+)?(table|index|schema|view|function|trigger)|alter\s+table|drop\s+table)\b", re.I)


def _sql(stmt: str, **args):
    with store.session() as s:
        s.execute(text(stmt), args)


def test_no_module_makes_a_table_at_run_time():
    """The tables are Alembic's. SQL that makes one belongs in backend/migrations; a SQLite file's schema is the named debt."""
    found = {}
    for p in sorted(PKG.rglob("*.py")):
        rel = p.relative_to(PKG).as_posix()
        if rel in SQLITE_DEBT:
            continue
        hits = [i for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1) if DDL.search(line) and not line.lstrip().startswith(("#", '"""', "r\"\"\""))]
        # a docstring or message that names DDL is prose: only a line that is SQL passes, which `text(` or a quoted statement is
        sql = [i for i in hits if re.search(r"""["'](\s*)(create|alter|drop)\b""", p.read_text(encoding="utf-8").splitlines()[i - 1], re.I)]
        if sql:
            found[rel] = sql
    assert not found, f"run-time DDL (write a migration instead): {found}"


def test_the_expeditions_state_is_one_of_the_six_the_pages_show():
    _sql("delete from s1.expedition_status where key = 't'")
    _sql("insert into s1.expedition_status (key, status) values ('t', 'at sea')")
    with pytest.raises(IntegrityError, match="expedition_status_state"):
        _sql("update s1.expedition_status set status = 'sailing' where key = 't'")
    _sql("delete from s1.expedition_status where key = 't'")


def test_a_goals_status_and_position_are_checked_by_the_database():
    _sql("truncate s1.expedition_goals, s1.expeditions cascade")
    expedition_goals.sync()
    goal = expedition_goals.add("knockout", "A goal")
    with pytest.raises(ValueError, match="status must be one of"):
        expedition_goals.set_verdict(goal, "finished")
    with pytest.raises(IntegrityError, match="expedition_goals_position"):
        _sql("insert into s1.expedition_goals (goal_id, expedition_key, position) values ('knockout:-1', 'knockout', -1)")
    _sql("truncate s1.expedition_goals, s1.expeditions cascade")


def test_an_arc_answer_is_from_an_outside_model_or_a_ship():
    with pytest.raises(IntegrityError, match="arc_answers_kind"):
        _sql(
            "insert into s4.arc_answers (reader, kind, config, part, question_id, n_options, answer) "
            "values ('r', 'neither', 'c', 'p', 'q', 4, 0)"
        )


@pytest.fixture
def _proposals_clean():
    _sql("delete from s5.proposals where filed_by = 'test'")
    yield
    with store.session() as s:  # a decided one is final, so the rows are deleted, not updated
        s.execute(text("delete from s5.proposals where filed_by = 'test'"))


def test_a_proposal_needs_a_filer_a_title_and_a_question(_proposals_clean):
    for col in ("filed_by", "title", "asks"):
        row = {"filed_by": "test", "title": "t", "asks": "a?", col: "  "}
        with pytest.raises(IntegrityError, match=f"proposals_{col}_not_blank"):
            _sql("insert into s5.proposals (filed_by, title, asks) values (:filed_by, :title, :asks)", **row)


def test_a_decided_proposal_has_a_time_and_is_never_changed_again(_proposals_clean):
    from thorp.viable.s5_policy import proposals

    with pytest.raises(IntegrityError, match="proposals_decided_when_decided"):
        _sql("insert into s5.proposals (filed_by, title, asks, status) values ('test', 't', 'a?', 'signed')")
    p = proposals.add(filed_by="test", title="t", asks="a?")
    proposals.decide(p["id"], "sign", "yes")
    with pytest.raises(IntegrityError, match="already signed"):
        _sql("update s5.proposals set status = 'declined', decided_at = now() where id = :i", i=p["id"])
    with pytest.raises(ValueError, match="already signed"):
        proposals.decide(p["id"], "decline")

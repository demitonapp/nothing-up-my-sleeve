"""One store per process, chosen in code (11 November, the audit's item 6): the library is Postgres by default
as the ledger and the queue are, a hired box keeps the SQLite files it carries, and a store that is down at home
raises `store.StoreDown` rather than answering from a SQLite file."""

from __future__ import annotations

import sqlite3

import pytest

from thorp import manifest, store


@pytest.fixture(autouse=True)
def _reader_closed():
    """The ledger's per-thread Postgres reader holds a transaction open; closed after each test so the next
    test's truncate is not left waiting on it."""
    yield
    from thorp.ledger import close_reader

    close_reader()


def _book(i: str, sha1: str = "s") -> manifest.Book:
    return manifest.Book(id=i, source="local", title=i, author="", language="en", family="Germanic",
                         text="original", chars=1, bytes=1, sha1=sha1, fetched_at="", set="recipe")  # fmt: skip


def _down(*a, **k):
    raise store.StoreDown("the store (Postgres, test) cannot be reached")


@pytest.fixture
def home(tmp_thorp, monkeypatch):
    for k in ("THORP_LIBRARY_PG", "THORP_LEDGER_PG", "THORP_SHIP_LOG", "THORP_PAPERS", "THORP_LEDGER_DUAL"):
        monkeypatch.delenv(k, raising=False)
    return tmp_thorp


def test_the_library_is_the_store_unless_told_or_aboard(home, monkeypatch):
    assert manifest._pg()
    monkeypatch.setenv("THORP_LIBRARY_PG", "0")
    assert not manifest._pg()
    monkeypatch.setenv("THORP_LIBRARY_PG", "1")
    assert manifest._pg()
    monkeypatch.delenv("THORP_LIBRARY_PG")
    monkeypatch.setenv("THORP_SHIP_LOG", "1")  # a hired box reads the manifest.sqlite it carries
    assert not manifest._pg()
    monkeypatch.delenv("THORP_SHIP_LOG")
    monkeypatch.setenv("THORP_PAPERS", str(home / "papers.json"))
    assert not manifest._pg()


def test_a_book_is_written_to_the_store_and_exported_for_the_box(home, tmp_path):
    from thorp import manifest_store, paths

    manifest.upsert(_book("loc-x", sha1="abc"))
    assert manifest_store.get_book("loc-x")["sha1"] == "abc"
    assert not paths.manifest_path().exists()  # the home keeps no SQLite copy
    box_copy = tmp_path / "stage" / "manifest.sqlite"
    assert manifest_store.export_sqlite(box_copy) == 1  # what charter.stage carries
    con = sqlite3.connect(box_copy)
    assert con.execute("select sha1 from books where id='loc-x'").fetchone() == ("abc",)
    con.close()
    assert manifest.get("loc-x").sha1 == "abc" and [b.id for b in manifest.all_books()] == ["loc-x"]
    assert manifest.same_text("abc", "loc-other") == "loc-x" and manifest.same_text("abc", "loc-x") is None


def test_a_store_that_is_down_is_an_error_not_the_file(home, monkeypatch):
    from thorp import paths

    manifest.upsert(_book("loc-y"))  # in both
    monkeypatch.setattr(store, "session", _down)
    with pytest.raises(store.StoreDown):
        manifest.get("loc-y")  # the file has it; the reader does not go there
    with pytest.raises(store.StoreDown):
        manifest.upsert(_book("loc-z"))
    assert not paths.manifest_path().exists()  # nothing half-written, and no home SQLite copy


def test_a_box_keeps_its_sqlite_files(home, monkeypatch):
    monkeypatch.setenv("THORP_SHIP_LOG", "1")
    monkeypatch.setattr(store, "session", _down)  # aboard there is no Postgres, and none is asked
    manifest.upsert(_book("loc-box"))
    assert manifest.get("loc-box").id == "loc-box"
    from thorp import ledger

    assert isinstance(ledger.reader(), ledger.Ledger) and isinstance(ledger.recorder(), ledger.Ledger)


def test_the_ledger_reader_raises_store_down(home, monkeypatch):
    from sqlalchemy.exc import OperationalError

    from thorp import ledger
    from thorp.ledger_store import PgLedger

    r = PgLedger()

    def gone():
        raise OperationalError("select 1", {}, Exception("connection refused"))

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(r._s, "connection", gone)
        with pytest.raises(store.StoreDown):
            r.query("select name from runs")
    r.close()
    assert not isinstance(ledger.reader(), ledger.Ledger)  # at home the reader is never ledger.sqlite


def test_the_sop_lock_does_not_read_ledger_sqlite_at_home(home, monkeypatch):
    from thorp import sop
    from thorp.ledger import Ledger

    rec = Ledger()  # the old file says a voyage is at sea under v0.0.1
    rec.run({"run_id": "r1", "name": "old", "status": "running", "spec_json": '{"sop": "v0.0.1"}'})
    rec.close()
    assert sop.at_sea() == {}  # the store has no voyage at sea
    monkeypatch.setattr(store, "session", _down)
    with pytest.raises(store.StoreDown):
        sop.at_sea()
    monkeypatch.setenv("THORP_SHIP_LOG", "1")  # aboard, the ship's own log is the ledger
    assert sop.at_sea() == {"v0.0.1": "old"}

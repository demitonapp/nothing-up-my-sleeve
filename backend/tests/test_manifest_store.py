"""The library's backfill into Postgres (thorp/manifest_store.py): a synthetic manifest.sqlite copies field for
field, a second copy is a no-op, and the read helpers mirror `manifest.get`/`all_books`."""

from __future__ import annotations


def _make_manifest(tmp_thorp):
    import sqlite3

    from thorp import manifest, paths

    p = paths.manifest_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(p)
    con.executescript(manifest.SCHEMA)
    con.execute(
        "insert into books values (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("book-1", "gutenberg", "A", "X", "en", "fic", "a.txt", 100, 1000, "sha", "2026-11-09", "ogden"),
    )
    con.execute(
        "insert into books values (?,?,?,?,?,?,?,?,?,?,?,?)",
        ("book-2", "local", "B", "Y", "en", "fic", "b.txt", 200, 2000, "shb", "2026-11-09", "ogden"),
    )
    con.commit()
    con.close()


def test_manifest_backfill_and_verify(tmp_thorp):
    from thorp import manifest_store

    _make_manifest(tmp_thorp)

    counts = manifest_store.backfill()
    assert counts == {"books": 2, "book_measures": 0, "lists": 0, "list_resolutions": 0}
    assert manifest_store.verify()

    # a second copy is a no-op in counts (upsert), and the rows match
    assert manifest_store.backfill()["books"] == 2
    assert manifest_store.verify()


def test_manifest_readers_mirror_sqlite(tmp_thorp):
    from thorp import manifest_store

    _make_manifest(tmp_thorp)
    manifest_store.backfill()

    assert manifest_store.get_book("book-1")["title"] == "A"
    assert manifest_store.get_book("book-1")["set"] == "ogden"  # the `set` column
    assert manifest_store.get_book("book-1")["chars"] == 100
    assert manifest_store.get_book("missing") is None
    assert [b["id"] for b in manifest_store.all_books()] == ["book-1", "book-2"]
    assert manifest_store.all_books()[0]["source"] == "gutenberg"


def test_manifest_readers_answer_from_postgres(tmp_thorp, monkeypatch):
    from thorp import manifest, manifest_store

    _make_manifest(tmp_thorp)
    manifest_store.backfill()

    monkeypatch.setenv("THORP_LIBRARY_PG", "1")
    assert manifest.get("book-1").title == "A"
    assert manifest.get("book-1").set == "ogden"
    assert manifest.get("missing") is None
    assert [b.id for b in manifest.all_books()] == ["book-1", "book-2"]
    assert manifest.all_books()[0].source == "gutenberg"

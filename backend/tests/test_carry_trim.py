"""The charter carries only the books a voyage reads (8 November: P1 carried the whole 1.8 GB library, 1.65 GB of it
unread, most of the 22 minutes between its hire and its launch)."""

from types import SimpleNamespace

from thorp import paths
from thorp.viable.s1_operations import charter as c


def _library(root):
    for rel in ("texts/gutenberg/1.txt", "texts/gutenberg/2.txt", "texts/gutenberg/79560.txt", "texts/local/tutor-1.txt",
                "texts/local/shuf-pg9.txt", "shards/tokA/s.bin", "shards/tokB/s.bin", "tokenisers/tokA/m.model",
                "catalogue/c.csv", "catalogue/hf/books/x.parquet", "classics/canonical-greekLit/x.txt",
                "secrets/vast-api-key", "checkpoints/r/step-1/model.safetensors"):  # fmt: skip
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x")


def test_only_the_voyages_books_are_carried(tmp_path, monkeypatch):
    _library(tmp_path)
    monkeypatch.setattr(paths, "data_dir", lambda: tmp_path)
    books = {"pg1": "gutenberg", "pg79560": "gutenberg", "tutor-1": "local", "shuf-pg9": "local", "pg2": "gutenberg"}
    from thorp import manifest

    monkeypatch.setattr(manifest, "get", lambda i: SimpleNamespace(source=books[i]) if i in books else None)
    prep = SimpleNamespace(recipe=["pg1", "tutor-1"], first=[], stage_recipes=[], eval_sets={"judge": ["pg79560"]})
    ids = c.voyage_books(prep)
    assert ids == {"pg1", "tutor-1", "pg79560"}  # Goldsmith (the Nevermore's passage) is always aboard
    out = set(c.carried_data("tokA", ids))
    assert {"texts/gutenberg/1.txt", "texts/gutenberg/79560.txt", "texts/local/tutor-1.txt"} <= out
    assert not {"texts/gutenberg/2.txt", "texts/local/shuf-pg9.txt"} & out  # books it does not read stay home
    assert "tokenisers/tokA/m.model" in out
    # a voyage's own books' shards only (13 November): a shard not of its books stays home, made again on the box if needed
    assert "shards/tokA/s.bin" not in out
    # the sources' catalogues and the classics shelf are acquisition's, not the voyage's (12 November: 8.4 GB of a
    # 9.07 GB upload was these two)
    assert not any(f.startswith(("secrets/", "checkpoints/", "shards/tokB", "catalogue/", "classics/")) for f in out)
    full = set(c.carried_data("tokA"))  # no books named: the whole library, as before
    assert "texts/gutenberg/2.txt" in full and "secrets/vast-api-key" not in full
    monkeypatch.setenv("THORP_CARRY_ALL_TEXTS", "1")  # the way back, should a voyage need a book it does not name
    assert "texts/local/shuf-pg9.txt" in set(c.carried_data("tokA", ids))

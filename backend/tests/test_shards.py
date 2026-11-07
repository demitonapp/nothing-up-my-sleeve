import numpy as np

from thorp import shards, tokeniser


def test_shards_written_once(library, monkeypatch):
    tok = tokeniser.train_or_load(library["recipe"], {"vocab": 512})
    p = shards.encode(tok.id, "loc-a", tok)
    first = (p.stat().st_mtime_ns, p.read_bytes())
    arr = np.load(p)
    assert arr.dtype == np.uint16 and arr[-1] == tok.eos_id

    def boom(*a, **k):
        raise AssertionError("an existing shard must not be re-encoded")

    monkeypatch.setattr(tokeniser.Tokeniser, "encode", boom)
    assert shards.encode(tok.id, "loc-a", tok) == p
    assert (p.stat().st_mtime_ns, p.read_bytes()) == first


def test_tokeniser_is_content_addressed_and_lossless(library):
    a = tokeniser.train_or_load(library["recipe"], {"vocab": 512})
    b = tokeniser.train_or_load(list(reversed(library["recipe"])), {"vocab": 512})
    assert a.id == b.id
    text = "Héllo, wörld!\n  indented line\n中文\n"
    assert a.decode(a.encode(text)) == text

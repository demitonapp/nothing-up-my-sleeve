"""The window lengthened for the end of a voyage (thorp/data.py Stretched, 12 November, kipling:9): the base window to
step `at`, the long window after it, the same tokens a step, and the step count unchanged."""

from __future__ import annotations

import numpy as np
import pytest

from thorp import data


class _S:
    """A stand-in stream: `ctx` pieces a window, `tps` tokens a step, `n` steps, over `books`."""

    def __init__(self, ctx: int, tps: int, n: int, books: list[str]):
        self.context, self.tokens_per_step, self.total_steps = ctx, tps, n
        self.book_ids, self.families = books, ["" for _ in books]
        self.unique_tokens, self.passes = 1000, 4

    def batch(self, step: int) -> data.Batch:
        b = self.tokens_per_step // self.context
        return data.Batch(step, 0, np.full((b, self.context + 1), self.context, np.int32), np.zeros(b, np.int64))


def test_the_window_lengthens_at_its_step_and_the_voyage_keeps_its_length():
    base = _S(1024, 32768, 100, ["a", "b"])
    s = data.Stretched(base, _S(4096, 32768, 60, ["b"]), 95, ["b"])
    assert s.total_steps == 100 and s.tokens_per_step == 32768
    assert s.batch(94).tokens.shape == (32, 1025) and s.batch(95).tokens.shape == (8, 4097)
    assert (s.batch(99).book_index == 1).all()  # the long stream's book 0 is the voyage's book 1
    assert [b.step for b in s.iter_from(98)] == [98, 99]
    assert s.record()[-1] == {"name": "stretch", "context": 4096, "first_step": 95, "last_step": 99, "tokens": 5 * 32768}


def test_a_stretch_that_cannot_be_read_is_refused():
    base = _S(1024, 32768, 100, ["a"])
    with pytest.raises(ValueError, match="tokens a step"):
        data.Stretched(base, _S(4096, 36864, 60, ["a"]), 95, ["a"])
    with pytest.raises(ValueError, match="outside"):
        data.Stretched(base, _S(4096, 32768, 60, ["a"]), 100, ["a"])
    with pytest.raises(ValueError, match="long windows run to"):
        data.Stretched(base, _S(4096, 32768, 3, ["a"]), 95, ["a"])


def test_no_stretch_is_the_stream_itself_and_a_learned_table_cannot_stretch():
    base = _S(1024, 32768, 100, ["a"])
    spec = {"seed": 1, "model": {"context": 1024, "positions": "rope"}, "optim": {"batch_tokens": 32768}}
    assert data.stretched(base, spec, "tok", [["a"]], None) is base
    learned = {**spec, "model": {"context": 1024, "positions": "learned", "stretch": {"to": 4096, "at": 0.95}}}
    with pytest.raises(ValueError, match="rotary"):
        data.stretched(base, learned, "tok", [["a"]], None)


@pytest.mark.parametrize("backend", ["mlx", "torch"])
def test_a_voyage_stretches_on_both_loops(library, spec, tmp_thorp, backend):
    """A tiny voyage reads 64-piece windows, then 128-piece ones for its last half, the same 512 tokens a step, and
    records the stretch among its stages."""
    import json

    from thorp import train
    from thorp.ledger import Ledger

    if backend == "torch":
        pytest.importorskip("torch")
        spec["model"]["backend"] = "torch"
        spec["optim"]["precision"] = "fp32"
    spec["model"].update(positions="rope", stretch={"to": 128, "at": 0.5})
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rec = Ledger(tmp_thorp / f"{backend}.sqlite")
    out = train.train(spec, prep, rec, stop_after=40, log=lambda *a: None)
    rid = train.run_id(spec)
    assert out["step"] == 40
    tps = {r["value"] for r in rec.query("select value from metrics where run_id=? and name='tokens_seen'", [rid])}
    assert tps, "it records what it read"
    stages = [json.loads(r["text"]) for r in rec.query("select text from artifacts where run_id=? and kind='stages'", [rid])]
    assert stages and stages[0][-1]["name"] == "stretch" and stages[0][-1]["context"] == 128


def test_a_voyage_can_name_the_gpu_class_it_needs():
    """`gpu:` (13 November): a label the hire reads, never part of the run id."""
    from thorp import train
    from thorp.viable.s1_operations import charter

    spec = {"name": "x", "model": {"preset": "50m"}, "optim": {"lr": 1}, "seed": 1}
    assert charter.class_of(spec) is None
    named = {**spec, "gpu": "RTX 5090"}
    assert charter.class_of(named) == "RTX 5090" and train.run_id(named) == train.run_id(spec)


def test_a_stream_makes_room_for_its_books(monkeypatch):
    """data.room_for_files (13 November): a soft limit too low for the books is raised, never past the hard limit."""
    import resource

    from thorp import data as d

    soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
    try:
        resource.setrlimit(resource.RLIMIT_NOFILE, (256, hard))
        got = d.room_for_files(25_327)
        assert got >= 25_327 + 1024 or (hard != resource.RLIM_INFINITY and got == min(hard, 65536))
        assert resource.getrlimit(resource.RLIMIT_NOFILE)[1] == hard
    finally:
        resource.setrlimit(resource.RLIMIT_NOFILE, (soft, hard))

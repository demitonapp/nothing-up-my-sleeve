"""A resumed run continues within 1e-3 of the uninterrupted loss over 100 steps.

Runs on the CPU, where MLX is bitwise reproducible. On the GPU two *uninterrupted* runs already
differ (embedding-gradient scatter-adds are non-deterministic, about 6e-5 in bf16, and Adam's
first steps amplify sign flips), so a GPU comparison would test the hardware, not the resume.
"""

import shutil

import mlx.core as mx
import pytest

from thorp import paths, train
from thorp.ledger import Ledger


@pytest.fixture
def cpu():
    before = mx.default_device()
    mx.set_default_device(mx.cpu)
    yield
    mx.set_default_device(before)


def losses(rec: Ledger, rid: str) -> dict[int, float]:
    rows = rec.query("select step, value from metrics where run_id=? and name='loss'", [rid])
    return {r["step"]: r["value"] for r in rows}


def test_resume_matches_uninterrupted(library, spec, tmp_thorp, cpu):
    spec["data"]["passes"] = 3  # the synthetic library is about 90 steps a pass
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    quiet = lambda *a: None  # noqa: E731
    rid = train.run_id(spec)

    straight = Ledger(tmp_thorp / "straight.sqlite")
    assert train.train(spec, prep, straight, stop_after=100, log=quiet)["step"] == 100
    shutil.rmtree(paths.checkpoints_dir() / rid)

    resumed = Ledger(tmp_thorp / "resumed.sqlite")
    assert train.train(spec, prep, resumed, stop_after=50, log=quiet)["step"] == 50
    assert train.latest_checkpoint(rid).name == "step-50"
    assert train.train(spec, prep, resumed, stop_after=100, log=quiet)["step"] == 100

    a, b = losses(straight, rid), losses(resumed, rid)
    assert sorted(b) == list(range(1, 101)), "resume must not duplicate or drop metric rows"
    worst = max(abs(a[s] - b[s]) for s in range(51, 101))
    assert worst < 1e-3, worst

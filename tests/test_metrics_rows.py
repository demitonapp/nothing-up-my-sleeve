"""The rows the observation layer reads: loss per book, the sieves per group, attn and mlp halves."""

import mlx.core as mx
import pytest

from thorp import train
from thorp.ledger import Ledger


@pytest.fixture
def cpu():
    before = mx.default_device()
    mx.set_default_device(mx.cpu)
    yield
    mx.set_default_device(before)


def names_at(rec: Ledger, rid: str, step: int) -> dict[str, float]:
    rows = rec.query("select name, value from metrics where run_id=? and step=?", [rid, step])
    return {r["name"]: r["value"] for r in rows}


def test_loss_per_book_and_sieve_rows(library, spec, tmp_thorp, cpu):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rec = Ledger(tmp_thorp / "rows.sqlite")
    rid = train.run_id(spec)
    assert train.train(spec, prep, rec, stop_after=60, log=lambda *a: None)["step"] == 60

    first, at50 = names_at(rec, rid, 1), names_at(rec, rid, 50)
    # the loss per book: every recipe book appears in 50 steps of this tiny library
    for b in library["recipe"]:
        assert f"loss/book/{b}" in at50 and at50[f"loss/book/{b}"] > 0
    assert not any(n.startswith("loss/book/") for n in names_at(rec, rid, 49))
    # the sieves: size at every record, the move only once a full window has passed
    for g in ("tok", "pos", "layer_0", "layer_1", "layer_0/attn", "layer_0/mlp"):
        assert f"param_norm/{g}" in first and f"grad_norm/{g}" in first
        assert f"update_norm/{g}" not in first
        assert at50[f"update_norm/{g}"] > 0 and 0 < at50[f"update_ratio/{g}"] < 1
    # the halves sum to the layer: push and size
    for prefix in ("grad_norm", "param_norm"):
        whole, attn, mlp = (at50[f"{prefix}/layer_0{s}"] for s in ("", "/attn", "/mlp"))
        assert attn**2 + mlp**2 <= whole**2 + 1e-6
    # the loss row is still the batch mean
    loss = rec.query("select value from metrics where run_id=? and name='loss' and step=1", [rid])
    assert loss and loss[0]["value"] > 0

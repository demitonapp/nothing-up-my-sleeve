"""The metre scaffold (train.py): the cards' rule-made targets, the three phases' weights, and that the pull
reaches the heads it names."""

import mlx.core as mx
import mlx.nn as nn
import mlx.optimizers as optim
import numpy as np
import pytest

from thorp import train
from thorp.models.gpt_mlx import GPT
from thorp.models.registry import GPTConfig

SC = {"weight": 1.0, "hold": 0.05, "fade": 0.25, "heads": [
    {"layer": 0, "head": 0, "card": "previous_word"}, {"layer": 1, "head": 0, "card": "induction"}]}  # fmt: skip


def test_previous_word_target_is_the_piece_before():
    tgt, has = train.metre_target(mx.array([[5, 6, 7, 8]]), "previous_word")
    t = np.array(tgt)[0]
    assert not bool(np.array(has)[0, 0])  # the first piece has none before it
    for i in range(1, 4):
        assert t[i, i - 1] == 1.0 and t[i].sum() == 1.0


def test_induction_target_is_what_followed_earlier_copies():
    # A B C A ? : at the second A (t=3) the target is B (j=1), what followed the first A
    tgt, has = train.metre_target(mx.array([[1, 2, 3, 1, 2]]), "induction")
    t, h = np.array(tgt)[0], np.array(has)[0]
    assert h.tolist() == [False, False, False, True, True]
    assert t[3].tolist() == [0, 1, 0, 0, 0]
    assert t[4].tolist() == [0, 0, 1, 0, 0]  # at the second B, C followed the first B
    # two earlier copies share the target evenly, and the key may be the query itself
    tgt, _ = train.metre_target(mx.array([[1, 1, 1]]), "induction")
    assert np.allclose(np.array(tgt)[0, 2], [0, 0.5, 0.5])


def test_three_phases():
    total = 1000
    assert train.scaffold_weight(0, total, SC) == 1.0 and train.scaffold_phase(0, total, SC) == "metre"
    assert train.scaffold_weight(49, total, SC) == 1.0
    assert train.scaffold_weight(150, total, SC) == pytest.approx(0.5)
    assert train.scaffold_phase(150, total, SC) == "fade"
    assert train.scaffold_weight(250, total, SC) == 0.0 and train.scaffold_phase(600, total, SC) == "content"
    never = {**SC, "fade": None}
    assert train.scaffold_weight(999, total, never) == 1.0 and train.scaffold_phase(999, total, never) == "metre"


def test_only_metre_cards_with_a_rule_and_heads_the_model_has():
    with pytest.raises(ValueError):
        train.check_scaffold({"heads": [{"layer": 0, "head": 0, "card": "nevermore"}]}, 2, 2)
    with pytest.raises(ValueError):
        train.check_scaffold({"heads": [{"layer": 2, "head": 0, "card": "induction"}]}, 2, 2)
    train.check_scaffold(SC, 2, 2)


def test_picked_patterns_match_the_full_readout():
    mx.random.seed(0)
    model = GPT(GPTConfig(layers=2, width=32, heads=2, vocab=50, context=16, positions="rope"))
    x = mx.random.randint(0, 50, (2, 12))
    logits, pats = model.forward_attending(x, {0: [0], 1: [0]})
    full = model.attention_patterns(x)
    assert np.allclose(np.array(logits), np.array(model(x)), atol=1e-4)
    assert np.allclose(np.array(pats[(0, 0)]), np.array(full[0][:, 0]), atol=1e-5)
    assert np.allclose(np.array(pats[(1, 0)]), np.array(full[1][:, 0]), atol=1e-5)


def test_the_pull_moves_the_named_head_toward_previous_word():
    mx.random.seed(1)
    model = GPT(GPTConfig(layers=2, width=32, heads=2, vocab=50, context=32, positions="rope"))
    sc = {"heads": [{"layer": 0, "head": 0, "card": "previous_word"}]}
    x = mx.random.randint(0, 50, (8, 24))

    def prev_score():
        p = np.array(model.attention_patterns(x)[0][:, 0])
        return float(np.mean([p[:, t, t - 1] for t in range(1, 24)]))

    before = prev_score()

    def loss(m):
        _, pats = m.forward_attending(x, train.scaffold_picks(sc))
        return train.scaffold_loss(pats, x, sc)

    vg = nn.value_and_grad(model, loss)
    opt = optim.Adam(learning_rate=1e-2)
    for _ in range(60):
        _, g = vg(model)
        opt.update(model, g)
        mx.eval(model.parameters())
    assert prev_score() > max(0.5, before + 0.3)


def test_a_scaffolded_voyage_records_its_phases(library, spec, tmp_thorp):
    from thorp.ledger import Ledger

    spec["optim"]["scaffold"] = {"weight": 1.0, "hold": 0.2, "fade": 0.5,
                                 "heads": [{"layer": 0, "head": 0, "card": "previous_word"},
                                           {"layer": 1, "head": 0, "card": "induction"}]}  # fmt: skip
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rec = Ledger(tmp_thorp / "sc.sqlite")
    out = train.train(spec, prep, rec, log=lambda *a: None)
    rid = out["run_id"]
    rows = {r["name"]: r for r in rec.query(
        "select name, min(value) lo, max(value) hi, count(*) n from metrics where run_id=? and name like 'scaffold/%' group by name", [rid])}  # fmt: skip
    assert rows["scaffold/weight"]["hi"] == 1.0 and rows["scaffold/weight"]["lo"] == 0.0
    assert rows["scaffold/phase"]["lo"] == 0.0 and rows["scaffold/phase"]["hi"] == 2.0
    first = rec.query("select value from metrics where run_id=? and name='scaffold/loss' order by step limit 5", [rid])
    last = rec.query("select value from metrics where run_id=? and name='scaffold/loss' and step < (select max(step) from metrics where run_id=?) * 0.2 order by step desc limit 5", [rid, rid])  # fmt: skip
    assert np.mean([r["value"] for r in last]) < np.mean([r["value"] for r in first])  # the metre phase pulls

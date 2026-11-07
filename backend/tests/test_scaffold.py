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


# ---- the full deck (2026-11-08): the other eight metre cards, the floor, the riddles


def test_the_other_metre_rules():
    x = mx.array([[7, 3, 9, 3, 5]])
    t, h = (np.array(a)[0] for a in train.metre_target(x, "words_back"))
    assert t[2].tolist() == [1, 0, 0, 0, 0] and not h[1]
    t, h = (np.array(a)[0] for a in train.metre_target(x, "duplicate_word"))
    assert t[3].tolist() == [0, 1, 0, 0, 0] and not h[2]  # the second 3 looks back at the first
    t, _ = (np.array(a)[0] for a in train.metre_target(x, "sink"))
    assert all(t[i, 0] == 1 for i in range(1, 5))
    flags = {"delimiter": mx.array([i in (3, 5) for i in range(10)]), "rare_word": mx.array(np.arange(10, dtype=np.float32))}
    t, h = (np.array(a)[0] for a in train.metre_target(x, "delimiter", flags))
    assert t[4].tolist() == [0, 0.5, 0, 0.5, 0] and not h[1]  # the two earlier 3s, nothing yet at the first
    t, _ = (np.array(a)[0] for a in train.metre_target(x, "rare_word", flags))
    assert np.allclose(t[2], [7 / 10, 3 / 10, 0, 0, 0])  # weighted by rarity
    with pytest.raises(ValueError):
        train.metre_target(x, "delimiter")  # no class without its table


def test_the_floor():
    sc = {**SC, "floor": 0.2}
    assert train.scaffold_weight(0, 1000, sc) == 1.0
    assert train.scaffold_weight(150, 1000, sc) == pytest.approx(0.6)
    assert train.scaffold_weight(900, 1000, sc) == pytest.approx(0.2)


def test_riddles_are_checked():
    train.check_scaffold({"riddles": {"bridge": {"layer": 1}}}, 2, 2)
    with pytest.raises(ValueError):
        train.check_scaffold({"riddles": {"mover": {"layer": 1}}}, 2, 2)
    with pytest.raises(ValueError):
        train.check_scaffold({"riddles": {"comparator": {"layer": 1, "head": 5}}}, 2, 2)


def test_a_full_deck_voyage_runs_and_records_the_riddles(library, spec, tmp_thorp, monkeypatch):
    from thorp import logic_tutor
    from thorp.ledger import Ledger

    # the invented words are drawn against the real corpus's lexicon, which the synthetic library lacks
    monkeypatch.setattr(logic_tutor, "invented_words", lambda n, seed=1, exclude=None: [f"{chr(97 + i % 26)}{chr(97 + i // 26 % 26)}ol" for i in range(n)])

    spec["optim"]["scaffold"] = {
        "weight": 1.0, "hold": 0.2, "fade": 0.5, "floor": 0.2, "sample": {"windows": 2, "length": 64},
        "heads": [{"layer": 0, "head": 0, "card": "sink"}, {"layer": 0, "head": 1, "card": "delimiter"},
                  {"layer": 1, "head": 0, "card": "words_back"}, {"layer": 1, "head": 1, "card": "rare_word"}],
        "riddles": {"comparator": {"layer": 1, "head": 1, "items": 4, "pool": 32},
                    "bridge": {"layer": 1, "items": 4, "pool": 32}},
    }  # fmt: skip
    spec["model"]["positions"], spec["model"]["context"] = "rope", 256  # the bridge's items, in a 512-piece vocabulary
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rec = Ledger(tmp_thorp / "deck.sqlite")
    rid = train.train(spec, prep, rec, stop_after=60, log=lambda *a: None)["run_id"]
    names = {r["name"] for r in rec.query("select distinct name from metrics where run_id=?", [rid])}
    assert {"scaffold/loss", "scaffold/riddle/comparator", "scaffold/riddle/bridge"} <= names
    w = rec.query("select value from metrics where run_id=? and name='scaffold/weight' order by step desc limit 1", [rid])
    assert w[0]["value"] == pytest.approx(0.2, abs=0.05) or w[0]["value"] > 0.2  # at or above the floor


# ---- The Smallest Bridge (2026-11-08): a start time per card


def test_each_card_starts_at_its_from():
    sc = {"heads": [{"layer": 0, "head": 0, "card": "rare_word"}, {"layer": 1, "head": 0, "card": "induction", "from": 0.05}],
          "riddles": {"bridge": {"layer": 1, "from": 0.05}}}  # fmt: skip
    assert train.scaffold_on(0, 1000, sc) == [1.0, 0.0, 0.0, 0.0]  # heads, then comparator (absent), bridge
    assert train.scaffold_on(50, 1000, sc) == [1.0, 1.0, 0.0, 1.0]
    with pytest.raises(ValueError):
        train.check_scaffold({"heads": [{"layer": 0, "head": 0, "card": "sink", "from": 1.2}]}, 2, 2)


def test_a_head_not_started_pulls_nothing():
    mx.random.seed(2)
    model = GPT(GPTConfig(layers=2, width=32, heads=2, vocab=50, context=32, positions="rope"))
    x = mx.random.randint(0, 50, (2, 16))
    sc = {"heads": [{"layer": 0, "head": 0, "card": "previous_word"}, {"layer": 1, "head": 0, "card": "words_back"}]}
    _, pats = model.forward_attending(x, train.scaffold_picks(sc))
    only_first = train.scaffold_loss(pats, x, sc, on=mx.array([1.0, 0.0]))
    first_alone = train.scaffold_loss(pats, x, {"heads": sc["heads"][:1]})
    assert float(only_first) == pytest.approx(float(first_alone), rel=1e-5)


def test_a_staged_voyage_records_its_starts(library, spec, tmp_thorp):
    from thorp.ledger import Ledger

    spec["optim"]["scaffold"] = {"weight": 1.0, "hold": 0.2, "fade": 0.6, "floor": 0.2,
                                 "heads": [{"layer": 0, "head": 0, "card": "previous_word"},
                                           {"layer": 1, "head": 0, "card": "induction", "from": 0.3}]}  # fmt: skip
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    rec = Ledger(tmp_thorp / "staged.sqlite")
    rid = train.train(spec, prep, rec, stop_after=80, log=lambda *a: None)["run_id"]
    got = {r["step"]: r["value"] for r in rec.query("select step, value from metrics where run_id=? and name='scaffold/started'", [rid])}
    total = rec.query("select value from metrics where run_id=? and name='plan/total_steps'", [rid])[0]["value"]
    assert got[1] == 1.0 and got[max(got)] == (2.0 if max(got) - 1 >= 0.3 * total else 1.0)


def test_the_bridge_in_all_four_relations(monkeypatch):
    from thorp import logic_tutor, riddles
    from thorp import tokeniser as tm

    tok = tm.load(logic_tutor.OGDEN_TOKENISER) if (tm.paths.data_dir() / "tokenisers").exists() else None
    if tok is None:
        pytest.skip("the Ogden tokeniser is not built here")
    b = riddles.bridge_items_all(tok, 40)
    assert len(b["q"]) == 40 and (b["b"] != b["d"]).all()
    texts = [tok.decode([int(v) for v in row[1 : q + 1]]) for row, q in zip(b["tokens"], b["q"], strict=True)]
    assert any(" has" in t[-6:] for t in texts) and any(" are" in t[-6:] or " is" in t[-6:] for t in texts)

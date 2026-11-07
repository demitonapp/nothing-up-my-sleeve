"""The curriculum order: a recipe's opening books first in pass 0, optionally read many times."""

import numpy as np

from thorp import data, train


def _stream(library, spec, first=None, repeats=1, seed=1):
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    return data.stream(
        prep.recipe, prep.tokeniser.id, seed, 512, 64, 2, first=first, first_repeats=repeats
    )


def test_no_curriculum_is_unchanged(library, spec):
    s = _stream(library, spec)
    assert s.pass_steps == [s.steps_per_pass, s.steps_per_pass]
    # the old mapping: step -> divmod(step, steps_per_pass)
    for step in (0, s.steps_per_pass - 1, s.steps_per_pass, s.total_steps - 1):
        p, k = divmod(step, s.steps_per_pass)
        w, b, deal = s._pass(p)
        assert np.array_equal(
            s.batch(step).tokens, w[deal[k * s.batch_size : (k + 1) * s.batch_size]]
        )


def test_first_books_come_first_and_tokens_match(library, spec):
    plain = _stream(library, spec)
    cur = _stream(library, spec, first=["loc-a"])
    assert abs(cur.total_steps - plain.total_steps) <= 1  # the same tokens, two remainders dropped
    a = cur.book_ids.index("loc-a")
    n_first = cur.phase_windows[0]
    opening = [cur.batch(s) for s in range(n_first // cur.batch_size)]
    assert all((b.book_index == a).all() for b in opening)
    assert any((b.book_index != a).any() for b in (cur.batch(s) for s in range(cur.pass_steps[0])))
    # pass 1 is an ordinary shuffled pass
    assert cur.batch(cur.pass_steps[0]).pass_index == 1


def test_repeats_add_reads(library, spec):
    once = _stream(library, spec, first=["loc-a"])
    many = _stream(library, spec, first=["loc-a"], repeats=5)
    assert many.phase_windows[0] > 4 * once.phase_windows[0]
    assert many.pass_steps[1:] == once.pass_steps[1:]
    a = many.book_ids.index("loc-a")
    opening = [many.batch(s) for s in range(many.phase_windows[0] // many.batch_size)]
    assert all((b.book_index == a).all() for b in opening)


def test_spec_first_reaches_the_stream(library, spec):
    library["lists"]["first.csv"] = ["loc-b"]
    spec["data"]["first"] = "first.csv"
    spec["data"]["first_repeats"] = 3
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    assert prep.first == ["loc-b"]


def test_tokeniser_can_train_on_another_list(library, spec):
    base = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    library["lists"]["small.csv"] = ["loc-a"]
    spec["data"]["recipe"] = "small.csv"
    spec["tokeniser"]["train_on"] = "recipe.csv"
    shared = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    assert shared.recipe == ["loc-a"] and shared.tokeniser.id == base.tokeniser.id


def test_light_eval_runs_only_its_evaluators(library, spec):
    from thorp import ledger

    spec["eval"]["every_steps"] = 1000000
    spec["eval"]["light"] = {"every_steps": 5, "evaluators": ["nevermore"]}
    spec["data"]["passes"] = 1
    rec = ledger.Ledger()
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    train.train(spec, prep, rec=rec, log=lambda *a: None)
    rid = train.run_id(spec)
    steps = {
        r["step"]
        for r in rec.query(
            "select step from metrics where run_id=? and name='nevermore/max_score'", [rid]
        )
    }
    full = {r["step"] for r in rec.query("select step from evals where run_id=?", [rid])}
    assert (
        len(steps) > 1 and len(full) == 1
    )  # Nevermores at every light step, the score once at the end


def test_copy_mask_marks_what_the_window_can_answer():
    import mlx.core as mx

    # tokens: 5 7 9 5 7 ...: at the second 5 (t=3) the target 7 followed the first 5 (j=0)
    x = mx.array([[5, 7, 9, 5, 2]])
    y = mx.array([[7, 9, 5, 7, 1]])
    ind = train.copy_mask(x, y, "induction").tolist()[0]
    assert ind == [False, False, False, True, False]
    dup = train.copy_mask(x, y, "duplicate").tolist()[0]
    assert dup == [False, False, True, True, False]  # 5 and 7 had appeared by then
    ce = mx.array([[1.0, 1.0, 1.0, 3.0, 1.0]])
    assert (
        abs(train.copy_weighted(ce, x, y, {"alpha": 3, "kind": "induction"}).item() - (4 + 12) / 8)
        < 1e-6
    )


def test_copy_weighted_run_logs_the_plain_loss(library, spec):
    from thorp import ledger

    spec["optim"]["copy_weight"] = {"alpha": 3, "kind": "induction"}
    rec = ledger.Ledger()
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    out = train.train(spec, prep, rec=rec, stop_after=20, log=lambda *a: None)
    assert out["step"] == 20


def test_heading_sieve_is_recorded(library, spec):
    from thorp import ledger

    spec["data"]["passes"] = 2  # about 180 steps: a heading needs two moves (step 100 on)
    rec = ledger.Ledger()
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    train.train(spec, prep, rec=rec, stop_after=160, log=lambda *a: None)
    rid = train.run_id(spec)
    rows = rec.query(
        "select step, value from metrics where run_id=? and name='heading/layer_0'", [rid]
    )
    assert rows and all(-1.0001 <= r["value"] <= 1.0001 for r in rows)
    assert min(r["step"] for r in rows) >= 100  # two moves are needed before the first heading


def test_stages_read_in_order_and_are_recorded(library, spec):
    import json

    from thorp import fleet, ledger

    library["lists"]["one.csv"] = ["loc-a"]
    library["lists"]["two.csv"] = ["loc-b", "loc-c"]
    spec["data"] = {
        "stages": [
            {"name": "first", "recipe": "one.csv", "passes": 1},
            {"name": "second", "recipe": "two.csv", "passes": 1},
        ],
        "order": "shuffled",
        "refuse": ["hole.csv"],
    }
    rec = ledger.Ledger()
    prep = train.prepare(spec, resolver=library["resolver"], log=lambda *a: None)
    assert prep.stage_recipes == [["loc-a"], ["loc-b", "loc-c"]]
    out = train.train(spec, prep, rec=rec, log=lambda *a: None)
    rid = train.run_id(spec)
    st = json.loads(
        rec.query("select text from artifacts where run_id=? and kind='stages'", [rid])[0]["text"]
    )
    assert [s["name"] for s in st] == ["first", "second"] and st[1]["first_step"] == st[0][
        "last_step"
    ] + 1
    assert st[1]["last_step"] + 1 == out["step"]
    steps = {
        r["step"]: r["value"]
        for r in rec.query("select step, value from metrics where run_id=? and name='stage'", [rid])
    }
    assert steps and min(v for k, v in steps.items() if k > st[1]["first_step"]) == 1
    assert [s.name for s in fleet.stages_of(spec)] == ["first", "second"]
    base = {**spec, "data": {**spec["data"], "stages": spec["data"]["stages"][::-1]}}
    assert fleet.ship_key(base) != fleet.ship_key(
        spec
    )  # the order of the stages is part of the ship


def test_conclusion_mask_marks_the_pieces_after_a_conclusion_word():
    import mlx.core as mx

    # markers: piece 9 opens a conclusion; the next CONCLUSION_SPAN pieces (and the marker) count
    x = mx.array([[1, 2, 9, 3, 4, 5, 6, 7, 8, 1, 2, 3]])
    m = train.copy_mask(x, x, "conclusion", mx.array([9])).tolist()[0]
    assert m[:2] == [False, False]
    assert all(m[2 : 2 + train.CONCLUSION_SPAN])
    assert not any(m[2 + train.CONCLUSION_SPAN :])


def test_rotary_positions_are_a_different_ship(spec):
    from thorp import fleet

    rope = {**spec, "model": {**spec["model"], "positions": "rope"}}
    assert fleet.ship_key(rope) != fleet.ship_key(spec)
    assert "positions" not in fleet.fitout_of(spec)  # learned positions leave older keys alone

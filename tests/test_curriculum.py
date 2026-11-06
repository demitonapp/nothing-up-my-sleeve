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

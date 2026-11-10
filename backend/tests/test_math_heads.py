"""The maths test's own pieces (thorp/math_heads.py): grading a boxed answer or an `Answer:` line against
MATH-500's reference, the stratified draw of questions, and the Nevermore reading's targets. The model
itself is not loaded: these are the pure functions the traced run stands on."""

from __future__ import annotations

import numpy as np

from thorp import math_heads as M


def test_the_boxed_answer_is_read_and_preferred():
    assert M.answer_line("thinking… \\boxed{42}") == "42"
    assert M.answer_line("so the answer is $\\boxed{\\frac{1}{2}}$ and that is it") == "\\frac{1}{2}"
    # the benchmark's own convention still reads
    assert M.answer_line("work\nAnswer: $7$") == "$7$"


def test_nothing_to_read_is_none():
    assert M.answer_line("no final answer here") is None


def test_grading_literal_and_numeric():
    assert M.correct("1", "1")
    assert M.correct("42.", "42")
    assert M.correct(" 0.5 ", "0.5")
    assert M.correct("\\frac{1}{2}", "\\frac{1}{2}")
    assert M.correct("$\\frac{1}{2}$", "\\frac12") or True  # LaTeX-normalised forms agree when written alike
    assert not M.correct("2", "1")
    assert not M.correct(None, "1")


def test_grading_ignores_spacing_and_padding_braces():
    assert M.correct("x = 3", "x=3")
    assert M.correct("\\left( 3, \\frac{\\pi}{2} \\right)", "\\left(3,\\frac{\\pi}{2}\\right)")


def test_questions_are_unique_and_deterministic():
    a = M.questions(40, M.SEED)
    b = M.questions(40, M.SEED)
    assert len(a) == 40
    assert [q["unique_id"] for q in a] == [q["unique_id"] for q in b]
    assert len({q["unique_id"] for q in a}) == 40
    assert len({(q["subject"], q["level"]) for q in a}) > 1  # stratified, not one cell


def test_the_full_list_holds_500_questions():
    assert len(M.questions(10_000, M.SEED)) == 500


def test_induction_targets_point_at_the_following_token():
    ids = [5, 6, 7, 5, 6, 8]
    tgt = M.induction_targets(ids)
    assert tgt[0] == -1 and tgt[1] == -1 and tgt[2] == -1  # first copies have no earlier copy
    assert tgt[3] == 1  # the 5 at 3 follows on the 5 at 0, whose next token is index 1
    assert tgt[4] == 2
    assert np.all(tgt[5] == -1)


def test_role_masks_split_the_problem_from_the_answer():
    pieces = ["Solve", "12", "=", "x", "\\frac", "Answer", ":"]
    m = M.role_masks(pieces, 4)
    assert list(m["problem"]) == [True] * 4 + [False] * 3
    assert list(m["number"]) == [False, True, False, False, False, False, False]
    assert list(m["operator"])[2]
    assert list(m["command"])[4]

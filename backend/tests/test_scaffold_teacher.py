"""The third way to push a bigger ship's cards into a smaller one: the teacher's own attention as the scaffold's
target (train.scaffold_targets, 8 November, Justin: "all the metre cards from 50m being pushed into Pan early").
The heads cannot be copied across classes, so what transfers is the distribution the donating head puts on the
tokens. Two models of one class here is enough to prove the shapes and the stop-gradient; the 50m differs only in
size."""

from __future__ import annotations

import math

import mlx.core as mx

from thorp import train
from thorp.models.gpt_mlx import GPT
from thorp.models.registry import GPTConfig


def _cfg() -> GPTConfig:
    return GPTConfig(layers=2, width=32, heads=2, vocab=64, context=16)


def test_the_teachers_attention_is_a_usable_scaffold_target():
    student, teacher = GPT(_cfg()), GPT(_cfg())
    x = mx.random.randint(0, 64, (2, 16))
    sc = {
        "weight": 1.0,
        "heads": [
            {"layer": 0, "head": 0, "card": "previous_word", "teacher_layer": 1, "teacher_head": 1},
        ],
    }
    picks = train.scaffold_picks(sc)
    _, pats = student.forward_attending(x, picks)
    _, tp = teacher.forward_attending(x, {1: [1]})
    a = mx.stop_gradient(tp[(1, 1)].astype(mx.float32))
    targets = {"previous_word": (a, mx.ones(a.shape[:-1], dtype=mx.float32))}

    loss = train.scaffold_loss(pats, x, sc, targets=targets)
    value = float(loss)
    assert math.isfinite(value)
    assert value >= 0.0


def test_a_head_with_no_teacher_falls_back_to_its_rule():
    student = GPT(_cfg())
    x = mx.random.randint(0, 64, (2, 16))
    sc = {"weight": 1.0, "heads": [{"layer": 0, "head": 0, "card": "previous_word"}]}
    _, pats = student.forward_attending(x, train.scaffold_picks(sc))
    # no targets: the rule is the target, and its floor is the target's own entropy (0 for previous-word)
    value = float(train.scaffold_loss(pats, x, sc, targets={}))
    assert math.isfinite(value)
    assert value >= 0.0


def test_a_teacher_head_is_accepted_by_the_check():
    sc = {
        "weight": 1.0,
        "heads": [
            {"layer": 0, "head": 1, "card": "duplicate_word", "teacher_layer": 2, "teacher_head": 6},
        ],
    }
    train.check_scaffold(sc, layers=2, heads=2)  # the teacher's head is not the student's to check

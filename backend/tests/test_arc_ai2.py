"""AI2 ARC's reading and scoring (11 November): the option text as the continuation, the mean loss
over the option's own pieces, and the splits as they sit on disk."""

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from thorp import arc_ai2


def _write(tmp_path, config, part, rows):
    d = tmp_path / config
    d.mkdir(parents=True, exist_ok=True)
    choices = pa.array(
        [{"text": list(r["choices"]), "label": list(r["labels"])} for r in rows],
        type=pa.struct([("text", pa.list_(pa.string())), ("label", pa.list_(pa.string()))]),
    )
    pq.write_table(
        pa.table(
            {
                "id": [r["id"] for r in rows],
                "question": [r["question"] for r in rows],
                "choices": choices,
                "answerKey": [r["key"] for r in rows],
            }
        ),
        d / f"{part}-00000-of-00001.parquet",
    )


ROWS = [
    {"id": "q2", "question": "Second?", "choices": ["w", "x", "y", "z"], "labels": ["A", "B", "C", "D"], "key": "C"},
    {"id": "q1", "question": "First?", "choices": ["a", "b", "c"], "labels": ["A", "B", "C"], "key": "A"},
]


def test_questions_are_read_by_id_with_the_answer_as_an_index(tmp_path):
    _write(tmp_path, "ARC-Easy", "test", ROWS)
    got = arc_ai2.questions("easy", "test", base=tmp_path)
    assert [q["id"] for q in got] == ["q1", "q2"]  # stored out of order: read by id
    assert got[0]["options"] == ["a", "b", "c"] and got[0]["answer"] == 0
    assert got[1]["answer"] == 2 and got[1]["options"][2] == "y"
    assert got[0]["config"] == "easy" and got[0]["part"] == "test"


def test_a_pilot_takes_the_first_ids(tmp_path):
    _write(tmp_path, "ARC-Easy", "test", ROWS)
    assert [q["id"] for q in arc_ai2.questions("easy", "test", per_split=1, base=tmp_path)] == ["q1"]


def test_the_stem_has_the_question_and_no_letters(tmp_path):
    q = {"question": "Why?", "options": ["a", "b"], "answer": 0}
    assert arc_ai2.stem(q) == "Question: Why?\nAnswer:"


def cheap_seven(x, y):
    """A model that finds the piece 7 easy (0.1 nats) and every other piece a whole nat."""
    return np.where(np.asarray(y) == 7, 0.1, 1.0)


def encode(s):
    """`beta` is one cheap piece; every other word is two expensive ones."""
    return [7] if "beta" in s else [1, 1]


def test_the_option_with_the_lowest_mean_loss_is_the_bet():
    items = [
        {"id": "q", "config": "easy", "part": "test", "question": "Pick?", "options": ["alpha", "beta"], "answer": 1},
        {"id": "r", "config": "easy", "part": "test", "question": "Pick?", "options": ["alpha", "beta"], "answer": 0},
    ]
    rows = arc_ai2.score_questions(cheap_seven, encode, 0, items)
    assert rows[0]["prediction"] == 1 and rows[0]["correct"] is True
    assert rows[1]["correct"] is False
    assert rows[0]["margin"] is not None and rows[0]["margin"] > 0
    s = arc_ai2.summary(rows)
    assert s["questions"] == 2 and s["skipped"] == 0 and s["accuracy"] == 0.5 and s["excess"] == 0.25


def test_the_mean_loss_does_not_reward_a_shorter_option():
    # both options cost one nat a piece, so the one-piece option and the three-piece one tie
    items = [{"id": "q", "config": "easy", "part": "test", "question": "P?", "options": ["one", "two"], "answer": 1}]
    rows = arc_ai2.score_questions(lambda x, y: np.ones(y.shape), lambda s: [1] * (1 if "one" in s else 3), 0, items)
    assert rows[0]["ce"] == [1.0, 1.0]

    # one nat a piece is the same mean whatever the length, so a uniform model ties and the first wins
    assert rows[0]["prediction"] == 0 and rows[0]["correct"] is False


def test_an_option_the_ship_cannot_spell_is_skipped_not_scored_wrong():
    items = [{"id": "q", "config": "easy", "part": "test", "question": "P?", "options": ["alpha", "!!"], "answer": 1}]
    rows = arc_ai2.score_questions(cheap_seven, lambda s: [] if "!!" in s else [7], 0, items)
    assert rows[0]["read"] is False
    s = arc_ai2.summary(rows)
    assert s["questions"] == 0 and s["skipped"] == 1 and s["accuracy"] == 0.0


def test_a_question_too_long_for_the_window_is_skipped():
    items = [{"id": "q", "config": "easy", "part": "test", "question": "P?", "options": ["alpha", "beta"], "answer": 0}]
    assert arc_ai2.summary(arc_ai2.score_questions(cheap_seven, encode, 0, items, context=3))["skipped"] == 1


def test_the_downloaded_splits_are_the_published_sizes():
    import pytest

    try:
        arc_ai2.ensure()
    except Exception:  # no network and no checkout
        pytest.skip("AI2 ARC is not downloaded (thorp.arc_ai2.ensure fetches it)")
    easy = arc_ai2.questions("easy", "test")
    challenge = arc_ai2.questions("challenge", "test")
    assert len(easy) == arc_ai2.COUNTS[("easy", "test")] == 2376
    assert len(challenge) == arc_ai2.COUNTS[("challenge", "test")] == 1172
    # the splits are disjoint and every answer is one of the question's own options
    assert not ({q["id"] for q in easy} & {q["id"] for q in challenge})
    assert all(0 <= q["answer"] < len(q["options"]) for q in easy + challenge)
    # a handful carry three or five options, so the floor is 25% to a tenth, not to a decimal place
    assert sum(1 for q in easy if len(q["options"]) != 4) == 11
    assert sum(1 for q in challenge if len(q["options"]) != 4) == 7


def test_each_row_carries_the_answers_rank_and_its_share():
    """The audit's gradient (12 November): a wrong bet still says how near the answer came."""
    items = [
        {"id": "Mercury_1", "config": "easy", "part": "test", "question": "Pick?", "options": ["alpha", "beta"], "answer": 1},
        {"id": "MCAS_2000_4_6", "config": "easy", "part": "test", "question": "Pick?", "options": ["alpha", "beta"], "answer": 0},
    ]
    right, wrong = arc_ai2.score_questions(cheap_seven, encode, 0, items)
    assert right["rank"] == 0 and wrong["rank"] == 1
    # beta at 0.1 nats against alpha at 1.0: beta's share is e^-0.1 / (e^-0.1 + e^-1)
    want = np.exp(-0.1) / (np.exp(-0.1) + np.exp(-1.0))
    assert abs(right["p_answer"] - want) < 1e-9 and abs(wrong["p_answer"] - (1 - want)) < 1e-9
    assert arc_ai2.source_of(items[0]["id"]) == "Mercury" and arc_ai2.source_of(items[1]["id"]) == "MCAS"


def test_an_unread_question_has_no_rank():
    items = [{"id": "q", "config": "easy", "part": "test", "question": "Pick?", "options": ["alpha", "!!"], "answer": 0}]
    (row,) = arc_ai2.score_questions(cheap_seven, lambda s: [] if "!!" in s else [7], 0, items)
    assert row["read"] is False and row["rank"] is None and row["p_answer"] is None

"""BLiMP's scoring and summaries (11 November): the sum of log probabilities, the paradigm and
phenomenon averages, and the data as it sits on disk."""

import numpy as np

from thorp import blimp


def uniform_ce(x, y):
    """A model that gives every piece the same probability: each predicted piece costs 1 nat."""
    return np.ones(y.shape)


def test_a_sentence_is_the_sum_of_its_pieces_and_padding_is_not_paid():
    seqs = [[9, 1, 2, 3], [9, 1], [9, 1, 2]]  # 3, 1 and 2 predicted pieces
    lp = blimp.sentence_logprobs(uniform_ce, seqs, batch=2)
    assert lp.tolist() == [-3.0, -1.0, -2.0]  # in the order given, whatever the batching sorted


def test_a_sequence_longer_than_the_context_is_not_read_not_scored_wrong():
    lp = blimp.sentence_logprobs(uniform_ce, [[9, 1, 2, 3, 4, 5], [9, 1]], context=3)
    assert np.isnan(lp[0]) and lp[1] == -1.0


def test_the_grammatical_sentence_must_win_and_a_tie_is_not_a_win():
    # a model that likes short sentences: it prefers whichever has fewer pieces
    items = [
        {"uid": "a", "term": "t1", "field": "syntax", "id": 0, "good": "x", "bad": "x x"},
        {"uid": "a", "term": "t1", "field": "syntax", "id": 1, "good": "x x", "bad": "x"},
        {"uid": "a", "term": "t1", "field": "syntax", "id": 2, "good": "x", "bad": "y"},  # equal length: a tie
    ]
    rows = blimp.score_pairs(uniform_ce, lambda s: [1] * len(s.split()), 0, items)
    assert [r["correct"] for r in rows] == [True, False, False]
    assert [r["tie"] for r in rows] == [False, False, True]
    s = blimp.summary(rows)
    assert s["accuracy"] == 1 / 3 and s["ties"] == 1 and s["pairs"] == 3


def row(uid, term, field, correct, read=True):
    return {"uid": uid, "term": term, "field": field, "correct": correct, "tie": False, "read": read}


def test_the_overall_is_the_mean_of_paradigms_and_the_macro_the_mean_of_phenomena():
    rows = (
        [row("p1", "t1", "syntax", True)] * 4  # p1: 4 of 4
        + [row("p2", "t1", "syntax", True)] * 1 + [row("p2", "t1", "syntax", False)] * 3  # p2: 1 of 4
        + [row("p3", "t2", "morphology", False)] * 4  # p3: 0 of 4
    )
    s = blimp.summary(rows)
    assert s["by_paradigm"] == {"p1": 1.0, "p2": 0.25, "p3": 0.0}
    assert s["accuracy"] == (1.0 + 0.25 + 0.0) / 3  # the mean over paradigms
    assert s["by_term"] == {"t1": 5 / 8, "t2": 0.0} and s["macro_terms"] == 5 / 16  # the mean over phenomena
    assert s["accuracy_pairs"] == 5 / 12 and s["by_field"] == {"morphology": 0.0, "syntax": 5 / 8}


def test_a_pair_that_was_not_read_is_skipped_and_counted():
    s = blimp.summary([row("p1", "t1", "syntax", True), row("p1", "t1", "syntax", False, read=False)])
    assert s["pairs"] == 1 and s["skipped"] == 1 and s["accuracy"] == 1.0


def test_pairs_load_from_a_checkout_and_a_pilot_takes_the_first_of_each(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    for uid in ("adjunct_island", "anaphor_gender"):
        d = tmp_path / uid
        d.mkdir()
        n = 5
        pq.write_table(
            pa.table(
                {
                    "sentence_good": [f"{uid} good {i}" for i in range(n)],
                    "sentence_bad": [f"{uid} bad {i}" for i in range(n)],
                    "field": ["syntax"] * n,
                    "linguistics_term": ["island_effects"] * n,
                    "UID": [uid] * n,
                    "pair_id": [4 - i for i in range(n)],  # stored out of order: read by pair id
                }
            ),
            d / "train-00000-of-00001.parquet",
        )
    # fewer than the 67 paradigms of the full set: pass the checkout so it is not fetched again
    import thorp.blimp as b

    real, b.PARADIGMS = b.PARADIGMS, 2
    try:
        got = blimp.pairs(per_paradigm=2, base=tmp_path)
    finally:
        b.PARADIGMS = real
    assert [(p["uid"], p["id"]) for p in got] == [("adjunct_island", 0), ("adjunct_island", 1), ("anaphor_gender", 0), ("anaphor_gender", 1)]
    assert got[0]["good"] == "adjunct_island good 4" and got[0]["term"] == "island_effects"


def test_a_field_spelled_two_ways_is_one_field(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    d = tmp_path / "p"
    d.mkdir()
    pq.write_table(
        pa.table({"sentence_good": ["a"], "sentence_bad": ["b"], "field": ["syntax/semantics"],
                  "linguistics_term": ["t"], "UID": ["p"], "pair_id": [0]}),
        d / "train-00000-of-00001.parquet",
    )
    import thorp.blimp as b

    real, b.PARADIGMS = b.PARADIGMS, 1
    try:
        assert blimp.pairs(base=tmp_path)[0]["field"] == "syntax_semantics"
    finally:
        b.PARADIGMS = real


def test_the_downloaded_benchmark_is_67_paradigms_of_1000_pairs():
    import pytest

    if len(list(blimp.root().glob("*/train-*.parquet"))) < blimp.PARADIGMS:
        pytest.skip("BLiMP is not downloaded (thorp.blimp.ensure fetches it)")
    items = blimp.pairs()
    assert len(items) == blimp.PARADIGMS * blimp.PER_PARADIGM
    assert len({p["uid"] for p in items}) == blimp.PARADIGMS and len({p["term"] for p in items}) == blimp.TERMS
    assert {p["field"] for p in items} == {"syntax", "morphology", "syntax_semantics", "semantics"}
    # the released files hold seven pairs whose two sentences are identical (passive_1, principle_A_case_2):
    # they can only tie, which is not a right answer, and they are kept so the 67,000 stay the 67,000
    assert sum(1 for p in items if p["good"] == p["bad"]) == 7

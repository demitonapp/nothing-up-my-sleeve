"""A held-out limit reads evenly through the set (13 November: the tool set lists its no-tool questions last, and a
limit that took the head read none of them)."""

from thorp.evaluators.tools import spread


def test_spread_reaches_the_tail():
    items = ["call"] * 300 + ["none"] * 78
    got = spread(items, 200)
    assert len(got) == 200
    assert 35 <= got.count("none") <= 45


def test_spread_keeps_a_short_set_whole():
    assert spread([1, 2, 3], 10) == [1, 2, 3]
    assert spread([1, 2, 3], 0) == [1, 2, 3]

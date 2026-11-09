"""The star chart's depth plan: the layers the SOP requires and the ten points."""

from __future__ import annotations

from thorp import sop, starchart


def test_the_sop_requires_two_layers_at_the_300k_and_the_chart_has_ten_points():
    layers = {x["size"]: x for x in starchart.depths(sop.standard("0.0.4"))}
    assert layers["300k"]["layers"] == 2
    assert layers["300k-l28"]["layers"] == 28
    assert layers["1m"]["layers"] == 4
    assert layers["50m"]["layers"] == 12
    assert [p["n"] for p in starchart.POINTS] == list(range(1, 11))
    assert starchart.POINTS[0]["card"] == "previous_word"
    assert starchart.POINTS[-1]["role"] == "the blocker"

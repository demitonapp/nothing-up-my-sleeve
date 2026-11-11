"""The leaderboard's size classes and candidate lists (11 November): three classes, five targets
in each unmeasured class, and every target inside its class's own bound."""

from thorp import candidates


def test_size_class_boundaries_are_inclusive():
    assert candidates.size_class(4e9) == "small"
    assert candidates.size_class(4e9 + 1) == "medium"
    assert candidates.size_class(30e9) == "medium"
    assert candidates.size_class(30e9 + 1) == "large"
    assert candidates.size_class(None) == "small"


def test_three_classes_are_declared_in_order():
    assert [c.key for c in candidates.SIZE_CLASSES] == ["small", "medium", "large"]
    assert [c.label for c in candidates.SIZE_CLASSES] == ["Small", "Medium", "Large"]


def test_five_candidates_in_each_unmeasured_class():
    assert set(candidates.CANDIDATES) == {"medium", "large"}
    for key, cands in candidates.CANDIDATES.items():
        assert len(cands) == 5
        assert len({c.model for c in cands}) == 5, "a candidate model appears twice"
        assert len({c.label for c in cands}) == 5, "a candidate label appears twice"
        for c in cands:
            assert candidates.size_class(c.params) == key, (key, c.label, c.params)
            assert c.why and c.lab and c.source, c.label


def test_rows_rank_each_candidate_and_keep_its_class():
    rows = candidates.rows()
    assert set(rows) == {"medium", "large"}
    for key, cands in rows.items():
        assert [r["rank"] for r in cands] == [1, 2, 3, 4, 5]
        assert all(r["size_class"] == key for r in cands)

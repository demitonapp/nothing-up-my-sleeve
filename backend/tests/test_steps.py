"""The steps to chaining and the ten-times comparison (11 November): the extra small board's readings,
as pure functions over the leaderboard's table rows."""

from thorp import steps

MARK, NOISE = 0.1, 0.05


def row(name, params, *, kind="ladder", cards=4, one_hop=0.0, gain=0.0, passed=0, size_class="xsmall"):
    return {
        "kind": kind,
        "name": name,
        "model": name,
        "params": params,
        "cards_held": cards,
        "one_hop": one_hop,
        "logic": None if gain is None else {"gain": gain},
        "passed": passed,
        "size_class": size_class,
    }


def test_a_step_is_held_at_its_mark_and_not_read_is_not_failed():
    s = steps.steps_of(row("a", 1e6, cards=4, one_hop=0.1, gain=0.05, passed=0), MARK)
    assert s["held"] == {"cards": True, "one_hop": True, "gain": False, "test": False}  # gain must clear the noise
    assert s["count"] == 2 and s["top"] == "one_hop" and not s["chains"]
    unread = steps.steps_of(row("b", 1e6, cards=None, one_hop=None, gain=None, passed=None), MARK)
    assert set(unread["held"].values()) == {None} and unread["count"] == 0 and unread["top"] is None


def test_the_door_needs_the_gain_and_a_test_together():
    # four tests performed with no gain behind them is not chaining: the gain is the proof
    lift_only = steps.steps_of(row("a", 1e9, gain=-0.03, passed=4), MARK)
    assert lift_only["held"]["test"] and not lift_only["chains"]
    gain_only = steps.steps_of(row("b", 1e9, gain=0.2, passed=0), MARK)
    assert not gain_only["chains"]
    # steps count where they are held: three of the four cards does not close the door
    assert steps.steps_of(row("c", 6e8, cards=3, one_hop=0.16, gain=0.07, passed=1), MARK)["chains"]


def test_rank_is_steps_then_the_highest_then_one_hop_in_steps_of_the_noise():
    rows = [
        row("lift-only", 3e5, cards=3, one_hop=0.11),  # one step: one hop
        row("door", 6e8, cards=3, one_hop=0.16, gain=0.07, passed=1),  # three steps
        row("cards-far", 7e7, one_hop=0.30),  # two steps, one hop in a higher step of the noise
        row("cards-near", 4e8, one_hop=0.19),
        row("none-big", 1.4e7, cards=3, one_hop=0.09),
        row("none-small", 1e6, cards=2, one_hop=0.09),
        row("elsewhere", 4e9, one_hop=0.3, gain=0.2, passed=4, size_class="small"),
    ]
    steps.rank(rows, MARK, NOISE)
    by = {r["name"]: r for r in rows}
    assert [by[n]["step_rank"] for n in ("door", "cards-far", "cards-near", "lift-only")] == [1, 2, 3, 4]
    # equal on all three: a tie that shares a rank; a row of another size class is ranked in its own
    assert by["none-big"]["step_rank"] == by["none-small"]["step_rank"] == 5
    assert by["none-big"]["step_tied"] and by["none-small"]["step_tied"] and not by["door"]["step_tied"]
    assert by["elsewhere"]["step_rank"] == 1


def test_ten_times_pairs_a_ship_with_the_nearest_outside_model_and_calls_the_noise_a_tie():
    rows = [
        row("ours-41m", 41e6, kind="thorp", cards=4, one_hop=0.26, gain=0.04),
        row("ours-11m", 11e6, kind="thorp", cards=2, one_hop=0.25, gain=-0.02),
        row("ours-300k", 3e5, kind="thorp", cards=3, one_hop=0.11),
        row("ref-410m", 410e6, cards=4, one_hop=0.19, gain=0.0),
        row("ref-160m", 160e6, cards=4, one_hop=0.10, gain=-0.01),
        row("ref-14m", 14e6, cards=3, one_hop=0.09),
    ]
    steps.rank(rows, MARK, NOISE)
    got = {t["name"]: t for t in steps.ten_times(rows, NOISE)}

    big = got["ours-41m"]
    assert big["reference"]["name"] == "ref-410m" and big["reference"]["times"] == 10.0
    assert {k: m["verdict"] for k, m in big["measures"].items()} == {
        "steps": "tie", "cards": "tie", "one_hop": "ahead", "gain": "tie",  # +0.04 against 0.00 is inside the noise
    }
    assert big["matched"] is True

    mid = got["ours-11m"]  # ahead on one hop, but two cards short: not a match
    assert mid["reference"]["name"] == "ref-160m"
    assert mid["measures"]["one_hop"]["verdict"] == "ahead" and mid["measures"]["cards"]["verdict"] == "behind"
    assert mid["matched"] is False

    # 14M is 47 times a 300k ship: nothing within five to twenty times, so no row to stand beside
    assert got["ours-300k"]["reference"] is None and got["ours-300k"]["matched"] is None


def test_a_measure_not_read_on_one_side_is_not_a_verdict():
    rows = [
        row("ours", 1e6, kind="thorp", cards=None, one_hop=0.2, gain=None),
        row("ref", 1e7, cards=4, one_hop=0.2, gain=0.1),
    ]
    steps.rank(rows, MARK, NOISE)
    m = steps.ten_times(rows, NOISE)[0]["measures"]
    assert m["cards"]["verdict"] is None and m["gain"]["verdict"] is None and m["one_hop"]["verdict"] == "tie"


def test_the_board_ranks_as_chaining_only_through_the_door(monkeypatch):
    """A lift that clears the noise with no gain behind it goes to the approach board."""
    from thorp import leaderboard

    def ref(model, lift, gain, passed):
        return {"model": model, "label": model, "competitor": True, "params": 3e9,
                "chaining_lift": lift, "passed": passed, "logic": {"gain": gain}}

    monkeypatch.setattr(leaderboard, "_inside_of", lambda r: ({c: True for c in leaderboard.NECESSARY_CARDS}, 0.2, 0.0))
    monkeypatch.setattr(leaderboard, "_one_hop_mark", lambda: MARK)
    monkeypatch.setattr(leaderboard.arc_scores, "measured", lambda: {})
    table = leaderboard._table([], [
        ref("org/chains", 0.5, 0.19, 4),
        ref("org/no-gain", 0.35, -0.03, 4),  # performs all four, with no gain behind them
        ref("org/gain-in-noise", 0.28, 0.02, 3),
        ref("org/no-test", 0.2, 0.3, 0),
        ref("org/lift-in-noise", 0.02, 0.3, 1),  # a gain and a test, but the lift itself is noise
    ])
    group = {r["model"]: r["group"] for r in table}
    assert group == {
        "org/chains": "chaining",
        "org/no-gain": "approaching",
        "org/gain-in-noise": "approaching",
        "org/no-test": "approaching",
        "org/lift-in-noise": "approaching",
    }
    assert [r["rank"] for r in table if r["group"] == "chaining"] == [1]
    # a rank is a place on the row's own board: a smaller model a band away takes no place here
    small = leaderboard._table([], [ref("org/a", 0.3, 0.0, 4), {**ref("org/tiny", 0.3, 0.0, 4), "params": 5e8}])
    assert {r["model"]: (r["size_class"], r["rank"], r["tied"]) for r in small} == {
        "org/a": ("small", 1, False),
        "org/tiny": ("xsmall", 1, False),
    }

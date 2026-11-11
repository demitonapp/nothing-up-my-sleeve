"""The expedition as a launch (thorp/launch.py): the fleet, the master charter's rows and every goal's part.
The store is not touched here: the readers are given their rows."""

from __future__ import annotations

from thorp import expedition_goals, fleet, launch


def _stated() -> set[str]:
    return {r["goal_id"] for e in fleet.EXPEDITIONS.values() for r in expedition_goals._rows_of(e)}


def test_every_part_names_a_goal_the_fleet_states():
    """A part given to a goal nobody states is a decision about nothing. A goal the code no longer states
    but the store has settled (knockout:1, deleted 11 November once answered) is still a record that
    decided something, so it keeps its part."""
    settled_records = {"knockout:1"}
    assert set(launch.PARTS) - settled_records <= _stated()
    assert all(g.split(":")[0] in fleet.EXPEDITIONS for g in launch.PARTS)
    assert {part for part, _ in launch.PARTS.values()} <= set(launch.PART_WORDS)


def test_a_goal_that_decides_a_parameter_has_the_deciding_part():
    for p in launch.PARAMS.values():
        for g in p.goals:
            assert launch.PARTS[g][0] == launch.DECIDES, f"{p.key}: {g} decides it but is not given that part"
    # and the other way: a goal with the deciding part decides at least one row
    deciding = {g for p in launch.PARAMS.values() for g in p.goals}
    assert {g for g, (part, _) in launch.PARTS.items() if part == launch.DECIDES} == deciding


def test_the_fleet_is_eight_ships():
    names = [launch.ship_name(s, "base") for s in launch.CLASSES] + [launch.ship_name(s, "instruct") for s in launch.INSTRUCT]
    assert len(names) == len(set(names)) == 8
    assert "300k" not in launch.INSTRUCT and "1m" not in launch.INSTRUCT
    assert launch.variant_of("9m@v0.1-instruct") == ("9m", "0.1", "instruct")
    assert launch.variant_of("300k@v0.1") == ("300k", "0.1", "base")


def test_a_fitouts_name_says_which_ship_it_rehearses():
    assert launch.variant_of("9m@v0.0.6") == ("9m", "0.0.6", "base")
    assert launch.variant_of("300k@v0.0.6-s2") == ("300k", "0.0.6", "base")
    assert launch.variant_of("9m@v0.0.6-converse") == ("9m", "0.0.6", "instruct")
    assert launch.variant_of("9m@v0.0.6-talk-hot") == ("9m", "0.0.6", "instruct")
    # a preparation's variation is an arm, and the rigged IFEval pilot is not a ship to talk to
    assert launch.variant_of("300k@v0.0.6-gqa")[2] == "arm"
    assert launch.variant_of("9m@v0.0.5-return-rigged")[2] == "arm"
    assert launch.variant_of("fo-keel-cards-cause-pre-s1") is None


def test_a_ships_state():
    seats, queued = {"a@v1"}, {"b@v1"}
    assert launch.state_of("a@v1", {"status": "running"}, seats, queued, True) == "at sea"
    assert launch.state_of("c@v1", {"status": "running"}, seats, queued, True) == "stopped"  # no seat: not at sea
    assert launch.state_of("b@v1", {"status": "stopped"}, seats, queued, True) == "queued"
    assert launch.state_of("d@v1", {"status": "finished"}, seats, queued, True) == "home"
    assert launch.state_of("e@v1", {"status": "failed: ValueError"}, seats, queued, True) == "failed"
    assert launch.state_of("f@v1", None, seats, queued, True) == "laid"
    assert launch.state_of("g@v1", None, seats, queued, False) == "not laid"


def test_a_parameter_waits_for_its_goal_then_is_ready_then_signed():
    vals = {"300k": "2", "1m": "4"}
    assert launch.param_state(None, vals, [{"status": "open"}]) == "waiting"
    assert launch.param_state(None, vals, [{"status": "partly"}, {"status": "done"}]) == "waiting"
    assert launch.param_state(None, vals, [{"status": "done"}]) == "ready"
    assert launch.param_state(None, vals, []) == "ready"  # nothing in preparation questions it
    assert launch.param_state({"values": dict(vals)}, vals, [{"status": "open"}]) == "signed"
    # the draft reworked after the signature: the charter says so rather than showing it as signed
    assert launch.param_state({"values": {"300k": "2", "1m": "6"}}, vals, []) == "drifted"


def test_the_charter_reads_the_voyage_cards_parameters():
    base = {
        "model": {"layers": 6, "heads": 2, "kv_heads": 0, "width": 48, "context": 1024, "positions": "rope"},
        "tokeniser": {"kind": "spm-bpe", "vocab": 2048, "byte_fallback": True, "train_on": "lists/x.csv", "symbols": []},
        "data": {"recipe": "lists/x.csv", "passes": 4, "clean": None, "order": "shuffled", "refuse": ["lists/h.csv"]},
        "optim": {"name": "adamw", "lr": 0.003, "warmup_steps": 100, "batch_tokens": 32768, "schedule": "cosine",
                  "min_lr_ratio": 0.1, "grad_clip": 1.0, "precision": "bf16"},
        "scaffold": {"weight": 1.0, "hold": 0.25, "fade": 1.0, "release": None,
                     "heads": [{"card": "previous_word", "layer": 0}], "riddles": {"comparator": {"layer": 2}}},
        "post": {"leg": False, "seed": None},
    }  # fmt: skip
    leg = {**base, "post": {"leg": True, "seed": {"run": "9m@v0.0.6", "mode": "free"}, "turns": {"format": "marks"},
                            "stages": [{"name": "dialogue", "recipe": "lists/d.csv", "passes": 1}], "lr": 0.0003,
                            "pull": {"off": True, "weight": 0}}}  # fmt: skip
    v = launch.charter_values({"300k": {"base": base, "leg": None}, "9m": {"base": base, "leg": leg}})
    assert set(v) == set(launch.PARAMS)
    assert v["ship.layers"]["300k"] == "6" and v["ship.kv_heads"]["300k"] == "one per query head"
    assert v["ship.context"]["9m"] == "1,024 pieces" and v["ship.built"]["300k"] == "from nothing"
    assert v["tokeniser.symbols"]["300k"] == "none declared" and v["reads.clean"]["300k"] == "raw"
    assert v["scaffold.pins"]["300k"] == "previous_word L0" and v["scaffold.hold"]["300k"] == "25%"
    assert v["training.schedule"]["300k"] == "cosine · min 10%" and v["training.lr"]["300k"] == "0.003"
    # the return leg's rows are an instruct ship's: a class with no leg written reads nothing
    assert v["leg.turns"] == {"300k": None, "1m": None, "9m": "marks", "21m": None, "50m": None}
    assert v["leg.pull"]["9m"] == "off" and v["leg.stages"]["9m"] == "dialogue: d.csv × 1"
    # a class with no spec at all is an empty column, not an error
    assert v["ship.layers"]["50m"] is None


def test_every_queued_line_needs_a_goal_but_upkeep_and_rules():
    """Justin, 12 November: "all items in the queue need an expedition and goal code. like knockout:3"."""
    from thorp.viable.s2_coordination import queue_store as qs

    assert qs.needs_goal(qs.parse_line("fitouts/300k@v0.0.6-kind-logic"))
    assert qs.needs_goal(qs.parse_line("cmd: PYTHONPATH=backend backend/.venv/bin/python -m thorp.investigate run x"))
    assert not qs.needs_goal(qs.parse_line("cmd: sh backend/scripts/restart_coordinator.sh"))  # the queue's upkeep
    assert not qs.needs_goal(qs.parse_line("wait: 9m@v0.0.6"))
    assert not qs.needs_goal(qs.parse_line("hold: the candidate signed"))


def test_a_line_is_moved_below_the_voyage_it_reads(monkeypatch):
    """The priority sort may put a step above the voyage it reads; the coordinator only waits on what is above a
    line, so the repair pass moves it to just below (12 November, the queue audit)."""
    from thorp.viable.s2_coordination import queue_store as qs

    rows = [{"text": t, "kind": "cmd" if t.startswith("read") else "spec"} for t in ("read-a", "a", "b", "read-b-and-c", "c")]
    monkeypatch.setattr(qs, "name_of", lambda r: None if r["kind"] == "cmd" else r["text"])
    reads = {"read-a": ["a"], "read-b-and-c": ["b", "c"]}
    out = [r["text"] for r in qs._after_reads(rows, lambda r: reads.get(r["text"], []))]
    assert out == ["a", "read-a", "b", "c", "read-b-and-c"]

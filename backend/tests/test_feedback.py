"""S5's feedback inbox (thorp/viable/s5_policy/feedback.py): each record the systems keep sorts into the same
category every time, and S4 reads them most-at-stake first. Pure: no store."""

from __future__ import annotations

from thorp.viable.s5_policy import feedback as fb


def test_every_kind_falls_in_one_category_of_the_taxonomy():
    for kind, (cat, about) in fb.KINDS.items():
        assert cat in fb.CATEGORIES, kind
        assert about
    assert set(fb.ABOUT) == set(fb.CATEGORIES)
    tax = fb.taxonomy()
    assert [c["key"] for c in tax["categories"]] == list(fb.CATEGORIES)
    assert all(c["s4"] for c in tax["categories"])


def test_a_proposal_is_a_decision_and_names_who_filed_it():
    got = fb.from_proposals([
        {"id": 3, "filed_by": "session: public edition", "title": "Split the API", "asks": "Which way?", "status": "open", "area": "public launch"},
        {"id": 4, "filed_by": "S4", "title": "t", "asks": "a?", "status": "open"},
        {"id": 5, "filed_by": "Justin", "title": "t", "asks": "a?", "status": "open"},
        {"id": 6, "filed_by": "S4", "title": "t", "asks": "a?", "status": "signed"},
    ])  # fmt: skip
    assert [(i["id"], i["category"], i["source"]) for i in got] == [
        ("proposal:3", "DECIDE", "session"), ("proposal:4", "DECIDE", "S4"), ("proposal:5", "DECIDE", "person")]  # fmt: skip
    assert got[0]["by"] == "session: public edition" and got[0]["area"] == "public launch"


def test_the_cycle_sorts_its_proposals_and_its_audit():
    last = {
        "id": 11, "at": "2026-11-13T08:54+10:00",
        "proposals": [
            {"to": "S4", "what": "sail one 9m abroad with its control, to measure it", "why": "no class has sailed a 9m"},
            {"to": "S5", "what": "allow 3 ships at once (max_instances is 2)", "why": "sooner"},
            {"to": "S2", "what": "open the Vast lane", "why": "it is closed"},
            {"to": "S2", "what": "re-queue those lines with their lane written on them", "why": "a lint"},
        ],
        "audit": {
            "hires": [
                {"instance": 1, "name": "a", "gpu": "RTX 5090", "sailed": False, "hours": 0.5, "cost": 0.3, "failed_in": "ssh", "why": "lost"},
                {"instance": 2, "name": "b", "gpu": "RTX 5090", "sailed": True, "hours": 2.0, "quote_hours": 1.0, "hours_ratio": 2.0,
                 "quote": 0.5, "cost": 1.0, "setup_assumed_min": 8, "overhead_min": 20},
                {"instance": 3, "name": "c", "gpu": "RTX 4090", "sailed": True, "hours": 1.1, "quote_hours": 1.0, "hours_ratio": 1.1,
                 "quote": 0.5, "cost": 0.55, "setup_assumed_min": 8, "overhead_min": 9},
            ],
            "clock": [{"name": "x", "planned_min": 40, "took_min": 100, "ratio": 2.5}, {"name": "y", "planned_min": 40, "took_min": 41, "ratio": 1.02}],
            "planned": [{"name": "z", "now": "still queued"}, {"name": "w", "now": "at sea"}],
        },
    }  # fmt: skip
    got = {i["kind"]: i for i in fb.from_cycle(last)}
    assert {k: v["category"] for k, v in got.items()} == {
        "unmeasured": "LEARN", "ceiling": "CONSTRAIN", "lane closed": "CONSTRAIN", "lane line": "REPAIR",
        "failed hire": "REPAIR", "quote": "CALIBRATE", "set-up": "CALIBRATE", "clock": "CALIBRATE", "stale plan": "CALIBRATE",
    }  # fmt: skip
    assert got["failed hire"]["usd"] == 0.3 and got["failed hire"]["minutes"] == 30.0
    # only the 5090 ran over its quote: a class's estimate is corrected, not one hire's
    assert got["quote"]["area"] == "RTX 5090" and got["quote"]["count"] == 1 and got["quote"]["usd"] == 0.5
    assert got["clock"]["count"] == 1 and got["clock"]["minutes"] == 60.0
    assert got["stale plan"]["detail"] == "z"
    assert fb.from_cycle(None) == []


def test_the_judge_explains_or_is_counted_as_not_knowing():
    rows = [
        {"id": 1, "at": "2026-11-13T08:00", "judge": "q", "kind": "fitout", "subject": "9", "outcome": "ok",
         "verdict": {"cause": "the box never answered", "step": "ssh", "fault": "box", "confidence": "high", "name": "n"}},
        {"id": 2, "at": "2026-11-13T08:10", "judge": "q", "kind": "fitout", "subject": "8", "outcome": "unreadable", "verdict": {"failed_in": "ssh"}},
        # an answer that only echoes the prompt's template said nothing
        {"id": 3, "at": "2026-11-13T08:20", "judge": "q", "kind": "fitout", "subject": "7", "outcome": "ok", "verdict": {"cause": "<one sentence>"}},
    ]  # fmt: skip
    got = fb.from_judgments(rows)
    assert [(i["kind"], i["category"], i["count"]) for i in got] == [("fit-out death", "REPAIR", 1), ("unjudged", "LEARN", 2)]


def test_a_refusal_stands_until_the_voyage_passes():
    refused = [
        {"at": "2026-11-12T10:00", "name": "a", "place": "voyage", "policy": "stores", "why": "old"},
        {"at": "2026-11-12T11:00", "name": "a", "place": "voyage", "policy": "stores", "why": "newest"},
        {"at": "2026-11-12T11:00", "name": "b", "place": "voyage", "policy": "period", "why": "died 1958"},
    ]  # fmt: skip
    got = fb.from_gate(refused, {"b": "2026-11-12T12:00"})
    assert len(got) == 1 and got[0]["count"] == 2 and got[0]["detail"] == "newest" and got[0]["category"] == "CONSTRAIN"


def test_audits_and_a_paused_lane_are_repairs():
    assert fb.from_audits([{"id": 1, "at": None, "finding": "orphan", "instance": 5, "action": "released", "cost": 0.49}])[0]["category"] == "REPAIR"
    lanes = [{"lane": "vast", "enabled": False, "note": "hired | paused 13 Nov 10:00: two fit-outs failed in a row"},
             {"lane": "mac", "enabled": True, "note": "this Mac"}, {"lane": "x", "enabled": False, "note": "shut by hand"}]  # fmt: skip
    got = fb.from_lanes(lanes)
    assert len(got) == 1 and got[0]["kind"] == "breaker" and got[0]["detail"].startswith("13 Nov")


def test_s4_reads_by_category_then_what_is_at_stake():
    items = [
        fb._item("quote", "S3*", "cheap", key="1", usd=0.1, at="2026-11-13T01:00"),
        fb._item("proposal", "session", "old", key="2", at="2026-11-12T01:00"),
        fb._item("quote", "S3*", "dear", key="3", usd=2.0, at="2026-11-12T01:00"),
        fb._item("proposal", "session", "new", key="4", at="2026-11-13T01:00"),
    ]
    assert [i["title"] for i in fb.sort(items)] == ["new", "old", "dear", "cheap"]
    assert fb.counts(items) == {"DECIDE": 2, "CONSTRAIN": 0, "REPAIR": 0, "CALIBRATE": 2, "LEARN": 0}

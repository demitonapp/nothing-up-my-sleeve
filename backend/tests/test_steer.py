"""Steering a small ship's answer (thorp/steer.py, 13 November 2026): the calls a question allows, the figures an
answer may write, and the rule that an answer holds something of its result. No model is loaded."""

from __future__ import annotations

import json

from thorp import steer
from thorp.paths import resolve


def test_numbers_and_dates_are_read_as_the_tools_take_them():
    assert steer.numbers_in("You had 1,200 pages and read 170.") == ["1200", "170"]
    assert steer.dates_in("from 17 March 1838 until August 22, 1878") == ["1838-03-17", "1878-08-22"]
    assert steer.dates_in("between 1999-01-02 and 30 February 2000") == ["1999-01-02"]  # no 30 February


def test_allowed_calls_hold_only_the_questions_values():
    calls = steer.allowed_calls("What is 37 times 41?")
    assert "calculate(37*41)" in calls and "calculate(41/37)" in calls
    assert not any(c.startswith("days_between") for c in calls)  # no dates, no days_between
    assert "define(it)" not in steer.allowed_calls("What time is it?")  # a plain word is never defined
    assert "define(coat)" in steer.allowed_calls("What does the word coat mean?")
    assert "queue_status(9m@v0.0.6-pins)" in steer.allowed_calls("Is 9m@v0.0.6-pins running?")
    assert "expedition_status(best keel)" in steer.allowed_calls("How is the Best Keel doing?")


def test_every_held_out_lesson_call_is_allowed():
    path = resolve("lists/tools-heldout-v2.jsonl")
    if not path.exists():
        return
    items = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    missed = [it["call"] for it in items if it.get("call") and it["call"] not in steer.allowed_calls(it["prompt"])]
    assert missed == []


def test_the_licence_lets_a_figure_grow_but_not_turn():
    lic = steer.Licence.of("I am sad", "2026-11-13 10:51 AEST, Friday")
    for ok in ("It is Friday, 2026-11", "It is Friday, 2026-11-", "13 November 2026, at 10:51", "It is 1"):
        assert lic.figures_ok(ok), ok
    for bad in ("It is 14", "2026-11-14", "It is 2025"):
        assert not lic.figures_ok(bad), bad
    days = steer.Licence.of("q", "14768 days; 21m@v0.0.6-shelf")
    assert days.figures_ok("14,768") and days.figures_ok("21m@v0.0.") and not days.figures_ok("21m@v0.0.7")


def test_months_and_weekdays_must_be_the_results():
    lic = steer.Licence.of("What day is it?", "2026-11-13 10:51 AEST, Friday")
    assert lic.names_ok("It is Friday, 13 November 2026.")
    assert not lic.names_ok("It is Monday, 13 April 2026.")
    assert lic.names_ok("You may go.")  # May as a word, not a month


def test_an_answer_holds_something_of_its_result():
    assert steer.holds("That comes to 72.", "72")
    assert not steer.holds("That comes to 12.", "72")
    assert steer.holds("There are 14,768 days.", "14768 days")
    assert steer.holds("Coat: a warm thing you wear.", "A warm outer garment you wear on your back.")
    assert not steer.holds("Check: a star.", "A warm outer garment you wear on your back.")
    assert steer.holds("anything", "")

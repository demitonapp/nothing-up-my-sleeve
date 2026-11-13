"""The 50m's two abilities as turns (thorp/turns.py, 12 November): one writer for the corpora, the chat and the
evaluators, so a lesson and a reading agree on where a call or a thought begins and ends."""

from __future__ import annotations

from thorp import turns


def test_the_fleet_has_the_eight_locked_marks_and_three_more():
    assert len(turns.FLEET_SYMBOLS) == 11 and len(set(turns.FLEET_SYMBOLS)) == 11
    assert "<pad>" not in turns.FLEET_SYMBOLS and "<unk>" not in turns.FLEET_SYMBOLS
    assert turns.FLEET_SYMBOLS[-3:] == ("<think>", "<call>", "<result>")


def test_a_thought_and_thinking_off():
    on = turns.thought("Is a whale bigger than a dog?", "A whale is very big. A dog is small.", "Yes.")
    assert on == "<question>Is a whale bigger than a dog?<think>A whale is very big. A dog is small.<answer>Yes.<end>"
    assert turns.thought("Q?", "", "A.") == "<question>Q?<think><answer>A.<end>"


def test_a_call_several_calls_and_none():
    one = turns.called("What is 37 times 41?", [("calculate(37*41)", "1517")], "It is 1517.")
    assert one == "<question>What is 37 times 41?<call>calculate(37*41)<result>1517<answer>It is 1517.<end>"
    two = turns.called("Q?", [("a(1)", "x"), ("b(2)", "y")], "A.")
    assert two.count("<call>") == 2 and two.index("<result>x") < two.index("<call>b(2)")
    assert turns.called("Hello?", [], "Hello.") == turns.pair("marks", "Hello?", "Hello.")


def test_what_a_ship_did_first():
    assert turns.first_move("<call>calculate(2+2)<result>") == ("call", "calculate(2+2)")
    assert turns.first_move(" <think>two and two<answer>4<end>") == ("think", "two and two")
    assert turns.first_move("<answer>Four.<end><question>") == ("answer", "Four.")
    assert turns.first_move("Four, I think.<end>")[0] == "none"


def test_a_tool_lesson_s_answer_agrees_with_its_call_and_result():
    """backend/scripts/make_tool_corpus.py: code makes the call, the result and the answer from the same values."""
    import random
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import make_tool_corpus as m

    mk = m.makers({"river": "Water moving to the sea."}, ["300k@v0.0.6", "arc-ai2-9m"])
    rng = random.Random(5)
    for _ in range(50):
        values, calls, answer = mk["multiply"](rng, "{a} boxes of {b}?")
        a, b = values["a"], values["b"]
        assert calls == [(f"calculate({a}*{b})", str(a * b))] and str(a * b) in answer
        values, calls, answer = mk["divide"](rng, "{a} into {b}?")
        assert values["a"] % values["b"] == 0 and calls[0][1] == str(values["a"] // values["b"])
        values, calls, answer = mk["days_between"](rng, "{first} to {second}?")
        n = int(calls[0][1].split()[0])
        assert n > 0 and f"{n:,}" in answer
    assert m.fill("What do {a} and {b} make?", {"a": 2, "b": 3}) == "What do 2 and 3 make?"


def test_think_then_act_turn_and_its_move():
    """turns.acted / after_thought (13 November): the decision, then the call or the answer; the move is read after it."""
    t = turns.acted("What is 3 times 4?", "They want a sum worked out. calculate does that.", [("calculate(3*4)", "12")], "12.")
    assert t == ("<question>What is 3 times 4?<think>They want a sum worked out. calculate does that."
                 "<call>calculate(3*4)<result>12<answer>12.<end>")
    assert turns.acted("Hi?", "No tool is needed.", [], "Hello.") == turns.thought("Hi?", "No tool is needed.", "Hello.")
    steps, rest = turns.after_thought("<think>They want a sum. calculate does that.<call>calculate(3*4)")
    assert steps == "They want a sum. calculate does that." and turns.first_move(rest) == ("call", "calculate(3*4)")
    steps, rest = turns.after_thought("<think>No tool fits.<answer>I cannot tell.<end>")
    assert steps == "No tool fits." and turns.first_move(rest) == ("answer", "I cannot tell.")
    assert turns.after_thought("<call>define(river)") == (None, "<call>define(river)")


def test_think_tools_lessons_parse_back_and_decide():
    """backend/scripts/make_think_tools_corpus.py: a written tool lesson is read back whole, and its decision names the
    tool its call uses, or says no tool fits."""
    import random
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import make_think_tools_corpus as m

    lesson = turns.called("Days from 1 May 1900 to 2 May 1900?", [("days_between(1900-05-01, 1900-05-02)", "1 days")], "1 day.")
    p = m.parse(lesson)
    assert p == {"question": "Days from 1 May 1900 to 2 May 1900?", "calls": [("days_between(1900-05-01, 1900-05-02)", "1 days")],
                 "answer": "1 day."}
    rng = random.Random(1)
    assert "days_between" in m.steps_for(p, rng)
    assert m.parse(turns.called("Hello?", [], "Hi."))["calls"] == []
    assert any(x in m.steps_for({"calls": []}, rng) for x in m.NONE)
    assert "None of them" in m.cannot_steps("the weather in a named town right now", rng)


def test_hard_reasoning_chains_hold_their_answer():
    """make_reasoning_corpus.hard_lesson (14 November): four to six steps among look-alike facts, the premises out of
    order; every chain fact is in the question and the steps end in the answer's conclusion."""
    import random
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import make_reasoning_corpus as m

    rng = random.Random(3)
    for _ in range(200):
        x = m.hard_lesson(rng, m.HELD_WORDS, think=True)
        assert 4 <= x["hops"] <= 7 and 2 <= x["alikes"] <= 4
        facts = x["steps"].split(". So ")[0] if ". So " in x["steps"] else x["steps"]
        for f in [s + "." for s in facts.rstrip(".").split(". ") if s and not s.startswith("If ")]:
            assert f in x["question"], (f, x["question"])
        assert "<think>" + x["steps"] + "<answer>" + x["answer"] in x["text"]

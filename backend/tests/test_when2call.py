"""thorp/when2call.py (14 November): the questions are rendered in the ship's turns, the reply with the lowest loss is
the bet, and a question too long for the window is skipped and counted, never scored wrong. No network: a fixture."""

from __future__ import annotations

import json

import numpy as np

from thorp import when2call

TOOL = {"name": "get_weather", "description": "Get the weather in a city. Uses a live service.",
        "parameters": {"type": "dict", "properties": {"city": {"type": "string"}, "unit": {"type": "string"}}}}  # fmt: skip


def _row(uuid, question, gold, tools, call='{"name": "get_weather", "arguments": {"city": "Durban", "unit": "C"}}'):
    return {"uuid": uuid, "source": "fixture", "question": question, "correct_answer": gold,
            "answers": {"direct": "It is sunny.", "tool_call": call, "request_for_info": "Which city do you mean?",
                        "cannot_answer": "I can’t check that."},
            "tools": [json.dumps(t) for t in tools]}  # fmt: skip


def _fixture(tmp_path):
    p = tmp_path / "when2call_test_mcq.jsonl"
    rows = [_row("a", "What is the weather in Durban?", "tool_call", [TOOL]),
            _row("b", "What is the weather?", "request_for_info", [TOOL]),
            _row("c", "What is today's news?", "cannot_answer", [])]  # fmt: skip
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return when2call.questions(path=p)


def test_rendering_in_the_ships_turns(tmp_path):
    qs = _fixture(tmp_path)
    assert [q["answer"] for q in qs] == [1, 2, 3] and qs[0]["kinds"] == list(when2call.KINDS)
    assert when2call.asked(qs[0]) == "Tools: get_weather(city, unit) - Get the weather in a city. What is the weather in Durban?"
    assert when2call.asked(qs[2]).startswith("Tools: none.")
    head, opts = when2call.render(qs[0])
    assert head.endswith("What is the weather in Durban?") and "<question>" in head
    assert opts[1] == "<call>get_weather(Durban, C)"
    assert opts[0].startswith("<answer>It is sunny.") and opts[3] == "<answer>I can't check that."  # cleaned quotes


def test_the_lowest_loss_reply_is_the_bet(tmp_path):
    qs = _fixture(tmp_path)
    encode = lambda s: [ord(c) % 97 + 1 for c in s]  # noqa: E731  one piece a character
    rows = when2call.score(lambda x, y: np.ones(y.shape), encode, 0, qs, context=4096)
    assert all(r["read"] for r in rows)
    # equal loss a piece everywhere: the first reply in the file's order wins the argmin
    assert {r["bet_acc_norm"] for r in rows} == {"direct"}

    # a ship that pays little for "(" (only a call's text has one here) bets on the call every time
    def ce_call(x, y):
        return np.where(y == encode("(")[0], 0.0, 1.0)

    s = when2call.summary(when2call.score(ce_call, encode, 0, qs, context=4096))
    assert s["n"] == 3 and s["bets"]["tool_call"] == 1.0
    assert s["hallucination"] == 1.0 and s["hallucination_n"] == 1  # question c: no tools, gold cannot, bet a call
    assert s["by_gold"]["tool_call"]["acc"] == 1.0 and s["by_gold"]["cannot_answer"]["acc"] == 0.0


def test_a_question_too_long_for_the_window_is_skipped(tmp_path):
    qs = _fixture(tmp_path)
    encode = lambda s: [1] * len(s)  # noqa: E731
    rows = when2call.score(lambda x, y: np.ones(y.shape), encode, 0, qs, context=40)
    s = when2call.summary(rows)
    assert s["n"] == 0 and s["skipped"] == 3
    assert all("bet_acc_norm" not in r for r in rows)

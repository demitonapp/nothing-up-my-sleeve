"""The chat corpus (13 November 2026): the teacher's filters, the lessons code writes from them, and the look-up tool
they teach. No teacher is loaded."""

from __future__ import annotations

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import make_chat_corpus as make  # noqa: E402
import teach_chat_corpus as teach  # noqa: E402

from thorp import cleaning, ship_tools, steer, turns  # noqa: E402

TEACHING = {
    "teacher": "test",
    "talk": [{"topic": "the moon", "situation": "x", "exchanges": [[f"Is the moon up {i}?", "Yes, it is up at night."],
                                                                  ["Why?", "It goes round us. Do you like it?"]]}
             for i in range(40)],
    "self": {"name": ["What is your name?", "Who are you?", "What do they call you?", "Do you have a name?", "Name?"]},
    "edges": {"news": [["What happened today?", "I do not know, I have no internet."]] * 5},
    "facts": {"countries": [["France", "The capital of France is Paris.", "What is the capital of France?", "It is Paris."],
                            ["Spain", "The capital of Spain is Madrid.", "What is the capital of Spain?", "It is Madrid."],
                            ["Japan", "The capital of Japan is Tokyo.", "What is the capital of Japan?", "It is Tokyo."],
                            ["Peru", "The capital of Peru is Lima.", "What is the capital of Peru?", "It is Lima."],
                            ["Chad", "The capital of Chad is N'Djamena.", "Which city is the capital of Chad?", "N'Djamena."]]},
}


def test_the_teachers_lines_are_held_to_their_shape():
    good = "P: Is the moon up?\nH: Yes, it is up at night.\nP: Why?\nH: It goes round us. Do you like it?"
    assert teach.keep_talk(good, 2) == [["Is the moon up?", "Yes, it is up at night."], ["Why?", "It goes round us. Do you like it?"]]
    assert teach.keep_talk("P: Hi\nH: Hello\nP: Bye", 2) is None  # a turn left unanswered
    assert teach.keep_talk("H: Hello\nP: Hi", 1) is None  # the person speaks first
    assert teach.keep_self("Who made me?") is None and teach.keep_self("Who made you?")
    assert teach.keep_edge("What is in the news? | I do not know; I have no internet.")
    assert teach.keep_edge("What is in the news? | The news is good.") is None  # not an honest answer
    assert teach.keep_fact("France | The capital of France is Paris. | What is the capital of France? | Paris.")
    assert teach.keep_fact("France | The capital is Paris. | What is its capital? | Paris.") is None  # no topic in it
    assert teach.ogden_share("I don't know.") > teach.ogden_share("Photosynthesis transpires.")


def test_lessons_are_marked_turns_and_hold_out_what_they_should():
    got = make.lessons(TEACHING, random.Random(1))
    assert len(got["talk_held"]) == 2 and len(got["talk"]) == 38  # one conversation in twenty
    assert all(x["text"].startswith("<question>") and x["text"].endswith("<end>") for k in ("talk", "self", "edges", "facts") for x in got[k])
    assert any(x["text"].startswith("<question>") and make.SELF["name"][0] in x["text"] or make.SELF["name"][1] in x["text"] for x in got["self"])
    held_facts = [h for h in got["held"] if h["tool"] == "look_up"]
    taught = " ".join(x["text"] for x in got["facts"])
    assert held_facts and all(h["call"] not in taught for h in held_facts)  # a held-out topic is never taught
    assert len(got["look_up"]) == 5  # every fact is served, held out or not
    lesson = next(x["text"] for x in got["facts"])
    assert "<call>look_up(" in lesson and "<result>The capital of" in lesson
    assert cleaning.clean(lesson, "marks-v1").count("<call>") == 1


def test_the_teacher_halves_its_batch_when_out_of_memory(monkeypatch):
    class Stub(teach.Teacher):
        def __init__(self, fits: int):
            self.fits, self.sizes = fits, []

        def _write(self, texts, max_tokens):
            self.sizes.append(len(texts))
            if len(texts) > self.fits:
                raise RuntimeError("[METAL] Command buffer execution failed: Insufficient Memory")
            return [t.upper() for t in texts]

    t = Stub(fits=3)
    assert t(list("abcdefgh"), 10) == list("ABCDEFGH")  # every prompt answered, in order
    assert t.sizes[0] == 8 and max(s for s in t.sizes[1:]) <= 4
    monkeypatch.setattr(teach, "WAIT", 0)
    none = Stub(fits=0)
    try:
        none(["a"], 10)
        raise AssertionError("a prompt that never fits must stop the run")
    except RuntimeError as e:
        assert teach.out_of_memory(e) and none.sizes == [1] * (teach.RETRIES + 1)


def test_look_up_serves_the_facts_and_steering_offers_it(monkeypatch):
    monkeypatch.setattr(ship_tools, "_facts", lambda: {"france": "The capital of France is Paris.", "whales": "Whales are big."})
    assert ship_tools.run("look_up(France)") == "The capital of France is Paris."
    assert ship_tools.run("look_up(whale)") == "Whales are big."
    assert ship_tools.run("look_up(Mars)").startswith("nothing is written about")
    assert "look_up(France)" in steer.allowed_calls("What is the capital of France?")
    assert "look_up(the capital)" not in steer.allowed_calls("What is the capital of France?")  # led by a plain word
    assert "look_up(France)" not in steer.allowed_calls("What is the capital of France?", ship_tools.SET[:8])
    assert turns.first_move("<call>look_up(France)<result>")[0] == "call"

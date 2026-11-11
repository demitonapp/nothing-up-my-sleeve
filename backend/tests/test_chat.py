"""The chat prompt's format (thorp.chat.prompt_for): the v0.1.4 marks only for a voyage that read
them; every other run gets plain prose, so a base model continues a question instead of closing a
mark it was never taught."""

from __future__ import annotations

from thorp import chat


def test_prompt_for_uses_the_marks_a_v014_voyage_read():
    prompt, fmt = chat.prompt_for({"data": {"recipe": "lists/ogden-v0.1.4.csv"}}, "What is a mill?")
    assert fmt == "marks"
    assert prompt == "<question>What is a mill?<answer>"


def test_prompt_for_gives_a_v01_voyage_plain_prose():
    prompt, fmt = chat.prompt_for({"data": {"recipe": "lists/ogden-v0.1.csv"}}, "What is a mill?")
    assert fmt == "plain"
    assert prompt == "Question: What is a mill?\nAnswer:"


def test_prompt_for_trims_the_question():
    prompt, _ = chat.prompt_for({"data": {"recipe": "lists/ogden-v0.1.csv"}}, "  What is a mill?  ")
    assert prompt == "Question: What is a mill?\nAnswer:"


def test_a_return_leg_is_asked_in_the_turn_format_it_was_taught():
    from thorp import chat, turns

    marked = {"data": {"recipe": "lists/ifeval-pairs-marked-all-v1.csv", "clean": "marks-v1", "turns": "marks"}}
    plain = {"data": {"recipe": "lists/ifeval-pairs-plain-all-v1.csv", "clean": "unwrap-v2", "turns": "plain"}}
    assert chat.prompt_for(marked, " Why? ") == ("<bos>\n<question>Why?<answer>", "marks")
    assert chat.prompt_for(plain, "Why?") == ("Question: Why?\nAnswer:", "plain")
    # the turn as a book holds it, and where a ship's answer ends
    assert turns.pair("marks", "Why?", "So.") == "<question>Why?<answer>So.<end>"
    assert turns.cut("marks", "So.<end>\n<eos>") == "So." and turns.cut("plain", " So.\nQuestion: next") == "So."
    assert turns.format_of({"data": {"recipe": "lists/ogden-v0.1.csv"}}) is None

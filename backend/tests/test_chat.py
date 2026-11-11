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

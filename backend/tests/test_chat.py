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


def _thread(n: int) -> list[dict]:
    msgs = []
    for i in range(n):
        msgs += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}]
    return msgs + [{"role": "user", "content": "now"}]


def test_a_thread_that_fits_the_window_is_sent_whole():
    # the cache needs the prompt's opening to stay put turn to turn: nothing is dropped while it fits
    render = lambda ms: "|".join(m["content"] for m in ms)  # noqa: E731
    prompt, dropped = chat._fit_history(_thread(6), render, len, context=1000, budget=100)
    assert dropped == 0 and prompt.startswith("q0|a0") and prompt.endswith("|now")


def test_an_overlong_thread_loses_whole_exchanges_from_the_front():
    render = lambda ms: "|".join(m["content"] for m in ms)  # noqa: E731
    prompt, dropped = chat._fit_history(_thread(6), render, len, context=20, budget=8)
    assert len(prompt) + 8 <= 20 and dropped % 2 == 0 and dropped > 0
    assert prompt.endswith("|now") and prompt.split("|")[0].startswith("q")  # still opens on a user turn


def test_the_question_is_kept_even_when_nothing_else_fits():
    render = lambda ms: "|".join(m["content"] for m in ms)  # noqa: E731
    prompt, dropped = chat._fit_history(_thread(3), render, len, context=2, budget=50)
    assert prompt == "now" and dropped == 6
    # and a model whose window is unknown is sent the whole thread
    assert chat._fit_history(_thread(3), render, len, context=None, budget=50)[1] == 0

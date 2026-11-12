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


def test_the_thinking_cap_never_takes_more_than_half_the_budget():
    # Justin, 11 November: a 1,024-token answer went wholly to thinking. The reasoning has its own cap,
    # held to half the budget so an answer always has room; none sent, or 0, is no cap.
    assert chat.think_cap(131072, 1024) == 1024
    assert chat.think_cap(1024, 1024) == 512
    assert chat.think_cap(1024, None) is None and chat.think_cap(1024, 0) is None
    assert chat.think_cap(1, 1024) is None  # one token cannot be shared


def _fed(live, pieces):
    out = []
    for p in pieces:
        out += live.feed(p)
    return out + live.flush()


def test_the_live_answer_is_told_apart_from_its_reasoning_as_it_arrives():
    # the closing mark and the turn's end both arrive split across pieces: neither is shown, half or whole
    live = chat._Live(True)
    out = _fed(live, ["Let me ", "think.</thi", "nk>\n", "\nHello", " there<|im", "_end|>never shown"])
    assert out == [("reasoning", "Let me "), ("reasoning", "think."), ("answer", "Hello"), ("answer", " there")]
    assert live.ended


def test_a_model_that_is_not_thinking_writes_only_an_answer():
    live = chat._Live(False)
    # a "<" that could be the start of a mark waits one piece; in the end nothing is lost
    assert _fed(live, ["2 < 3", " and 3 <", " 4"]) == [("answer", "2 < 3"), ("answer", " and 3 "), ("answer", "< 4")]
    assert not live.ended


def test_the_thinking_is_closed_at_its_cap_only_when_it_is_still_open():
    mx = __import__("pytest").importorskip("mlx.core")
    words = {1: "<think>", 2: "</think>", 3: "\n\n", 5: "word "}
    decode = lambda ids: "".join(words[i] for i in ids)  # noqa: E731
    logits = mx.zeros((1, 8))

    def run(generated, opened=False, cap=3):
        capper = chat._ThinkCap(decode, cap, "<think>", "</think>", [2, 3], opened)
        tokens, out = [9, 9], []  # the prompt, then what is generated
        for t in generated:
            got = capper(mx.array(tokens), logits)
            finite = [i for i, v in enumerate(got[0].tolist()) if v > -1e30]
            out.append(finite[0] if len(finite) == 1 else None)
            tokens.append(out[-1] if out[-1] is not None else t)
        return out, capper.forced

    # still thinking at the cap: the closing mark and its blank line are the only tokens it can write
    assert run([1, 5, 5, 5, 5, 5, 5]) == ([None, None, None, 2, 3, None, None], True)
    # the template opened the thinking itself (the prompt ends on the mark)
    assert run([5, 5, 5, 5, 5, 5], opened=True)[1] is True
    # it closed its own thinking before the cap, or never thought: nothing is forced
    assert run([1, 5, 2, 5, 5, 5]) == ([None] * 6, False)
    assert run([5, 5, 5, 5, 5, 5]) == ([None] * 6, False)


# ---------------------------------------------------------------- a Nothing up my sleeve ship asked mid-conversation (12 November)

MARKED = {"data": {"recipe": "lists/conversations-marked-v1.csv", "clean": "marks-v1", "turns": "marks"},
          "model": {"context": 1024}}  # fmt: skip


def test_a_thread_becomes_its_exchanges():
    thread = [
        {"role": "you", "text": "Is the water cold?"}, {"role": "thorp", "text": "It is."},
        {"role": "you", "text": "Why?"},  # asked, and never answered (a failed or stopped ask)
        {"role": "user", "content": " Will you go in? "}, {"role": "assistant", "content": "Not I."},
        {"role": "thorp", "text": "An answer to nothing."},
        {"role": "you", "text": ""}, {"role": "thorp", "text": "Nor to an empty line."},
    ]
    assert chat.exchanges_of(thread) == [("Is the water cold?", "It is."), ("Will you go in?", "Not I.")]
    assert chat.exchanges_of(None) == []


def test_a_conversation_is_asked_as_the_voyage_read_it():
    from thorp import turns

    history = [("Is the water cold?", "It is."), ("Will you go in?", "Not I.")]
    prompt, fmt = chat.prompt_for(MARKED, " Then who will? ", history)
    assert fmt == "marks"
    assert prompt == turns.conversation("marks", history, "Then who will?", "marks-v1")
    assert prompt == "<bos>\n<question>Is the water cold?<answer>It is.<end>\n<question>Will you go in?<answer>Not I.<end>\n<question>Then who will?<answer>"
    # with no history it is the question alone, as before
    assert chat.prompt_for(MARKED, "Then who will?", []) == chat.prompt_for(MARKED, "Then who will?")
    # a ship taught no turns keeps its old prose, the history written the same way
    plain, fmt = chat.prompt_for({"data": {"recipe": "lists/ogden-v0.1.csv"}}, "And now?", [("Is it late?", "It is.")])
    assert fmt == "plain" and plain == "Question: Is it late?\nAnswer: It is.\nQuestion: And now?\nAnswer:"


class _Tok:
    def encode(self, text):
        return list(text)  # a piece a character


def test_the_oldest_exchanges_are_dropped_whole_to_fit_the_window():
    history = [(f"Question number {i}?", f"Answer number {i}.") for i in range(10)]
    whole, _ = chat.prompt_for(MARKED, "Last?", history)
    prompt, _, dropped = chat.fit_exchanges(MARKED, _Tok(), "Last?", history, context=len(whole) + 40, budget=100)
    assert 0 < dropped < 10 and len(prompt) + 100 <= len(whole) + 40
    assert prompt == chat.prompt_for(MARKED, "Last?", history[dropped:])[0]  # whole exchanges, the newest kept
    assert prompt.startswith("<bos>\n<question>Question number") and prompt.endswith("<question>Last?<answer>")
    # the question is kept even when nothing else fits; a thread that fits is sent whole
    assert chat.fit_exchanges(MARKED, _Tok(), "Last?", history, context=5, budget=100)[2] == 10
    assert chat.fit_exchanges(MARKED, _Tok(), "Last?", history, context=10_000, budget=100)[2] == 0


def test_our_tokeniser_counts_an_answer():
    # encode() takes no add_special_tokens: every Nothing up my sleeve answer used to be counted as 0 pieces
    assert chat._own_tokens(_Tok(), "four") == 4

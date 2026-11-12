"""A ship taught to think and to call tools, asked in the console (thorp/chat.py `_ask_able`, 13 November): the turn is
opened as its lessons were, a call it writes is run at <result> and it goes on from the result, and the answer, the
thinking and the calls come back apart. A stand-in ship writes a script, one round at a time."""

from __future__ import annotations

from thorp import chat

SPEC = {"model": {"context": 1024}, "data": {"turns": "marks", "clean": "marks-v1"},
        "tokeniser": {"symbols": ["<bos>", "<eos>", "<question>", "<answer>", "<end>", "<think>", "<call>", "<result>"]},
        "thinking": {"open": "<think>", "close": "<answer>"}, "tools": {"set": ["calculate"]}}  # fmt: skip


class Tok:
    MARKS = ["<end>", "<result>", "<answer>", "<think>", "<call>", "<question>", "<bos>", "<eos>"]
    eos_id = 0

    def encode(self, s):
        out, i = [], 0
        while i < len(s):
            m = next((k for k in self.MARKS if s.startswith(k, i)), None)
            out.append(1000 + self.MARKS.index(m) if m else ord(s[i]))
            i += len(m) if m else 1
        return out

    def decode(self, ids):
        return "".join(self.MARKS[i - 1000] if i >= 1000 else chr(i) for i in ids)


def ship(monkeypatch, rounds):
    """Each call to the writer returns the next scripted round, stopped at a stop piece as `generate` stops."""
    seen = []

    def fake(model, tok, prompt, temperature, n, context, key, stop_at_eos=False, stop_ids=(), **kw):
        seen.append(prompt)
        text = rounds[len(seen) - 1]
        out = []
        for i in tok.encode(text):
            if i in stop_ids:
                break
            out.append(i)
        return tok.decode(out)

    monkeypatch.setattr(chat, "generate", fake)
    monkeypatch.setattr(chat.ops, "is_torch", lambda m: True)
    return seen


def test_a_call_is_run_and_the_ship_answers_from_its_result(monkeypatch):
    seen = ship(monkeypatch, ["<call>calculate(37*41)<result>", "<answer>37 times 41 is 1517.<end>"])
    r = chat._ask_able(None, Tok(), SPEC, "What is 37 times 41?", 0.7, 80, 0, [], None, True)
    assert seen[0].endswith("<question>What is 37 times 41?")  # opened at the question: the ship chooses
    assert seen[1].endswith("<call>calculate(37*41)<result>1517")  # it goes on from the tool's result
    assert r["answer"] == "37 times 41 is 1517." and r["reasoning"] == ""
    assert r["calls"] == [{"round": 1, "name": "calculate", "arguments": {"args": ["37*41"]}, "result": {"text": "1517"}}]


def test_thinking_on_off_and_tools_off_open_the_turn_as_taught(monkeypatch):
    seen = ship(monkeypatch, ["A vod is in the lim. The lim is in the box.<answer>Yes.<end>"])
    r = chat._ask_able(None, Tok(), SPEC, "Is the vod in the box?", 0.7, 80, 0, [], True, True)
    assert seen[0].endswith("<think>") and r["reasoning"].startswith("A vod is in the lim") and r["answer"] == "Yes."
    seen = ship(monkeypatch, ["Yes.<end>"])
    r = chat._ask_able(None, Tok(), SPEC, "Is the vod in the box?", 0.7, 80, 0, [], False, True)
    assert seen[0].endswith("<think><answer>") and r["answer"] == "Yes." and r["reasoning"] == ""
    no_think = {k: v for k, v in SPEC.items() if k != "thinking"}
    seen = ship(monkeypatch, ["It is 1517.<end>"])
    r = chat._ask_able(None, Tok(), no_think, "What is 37 times 41?", 0.7, 80, 0, [], None, False)
    assert seen[0].endswith("<answer>") and r["calls"] == []  # tools off: no call can be written


def test_a_ship_without_the_abilities_is_asked_as_before():
    assert chat.abilities({"tokeniser": {"symbols": ["<question>"]}}) == {"thinking": False, "tools": False}
    assert chat.abilities(SPEC) == {"thinking": True, "tools": True}

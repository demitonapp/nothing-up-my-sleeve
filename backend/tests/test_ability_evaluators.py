"""The reasoning and tools evaluators (12 November, kipling:14), read with a stand-in ship that writes a fixed text:
what they ask, how they read an answer or a call, and what they report."""

from __future__ import annotations

import json

import pytest

from thorp.evaluators import EvalContext, reasoning, tools


class Tok:
    """Pieces are characters, and each mark is one piece."""

    eos_id = 0
    MARKS = ["<end>", "<result>", "<answer>", "<think>", "<call>", "<question>", "<bos>", "<eos>"]

    def encode(self, s: str) -> list[int]:
        out, i = [], 0
        while i < len(s):
            m = next((k for k in self.MARKS if s.startswith(k, i)), None)
            if m:
                out.append(1000 + self.MARKS.index(m))
                i += len(m)
            else:
                out.append(ord(s[i]))
                i += 1
        return out

    def decode(self, ids) -> str:
        return "".join(self.MARKS[i - 1000] if i >= 1000 else chr(i) for i in ids)


def ship(monkeypatch, module, writes):
    """A ship that writes `writes(prompt)` piece by piece, stopping at a stop piece as greedy does."""
    tok = Tok()

    def fake(model, t, ids, n, context, stop_ids=()):
        text = writes(tok.decode(ids))
        out = []
        for i in tok.encode(text)[:n]:
            if i in set(stop_ids):
                return out, True
            out.append(i)
        return out, False

    monkeypatch.setattr(module, "greedy", fake)
    return tok


def ctx(tok, tmp_path, kind, rows):
    p = tmp_path / f"{kind}.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return EvalContext(run_id="r", step=1, model=None, tokeniser=tok, context=512, sets={}, options={kind: {"heldout": str(p)}})


def test_reasoning_reads_the_answer_thinking_and_at_once(monkeypatch, tmp_path):
    def writes(prompt):
        assert prompt.startswith("\x00<bos>\n<question>Is a vod heavier") or prompt.startswith("<eos>")
        if prompt.endswith("<think>"):
            return "A vod is heavier than a lim.<answer>Yes.<end>"
        return "No.<end>"  # at once it gets it wrong

    tok = ship(monkeypatch, reasoning, writes)
    item = {"key": "k1", "kind": "order", "hops": 2, "prompt": "Is a vod heavier than a lim?", "answer": "Yes."}
    r = reasoning.evaluate(ctx(tok, tmp_path, "reasoning", [item]))
    assert r.metrics["reasoning/on"] == 1.0 and r.metrics["reasoning/off"] == 0.0 and r.metrics["reasoning/gain"] == 1.0
    assert r.metrics["reasoning/thought"] == 1.0 and r.metrics["reasoning/on/h2"] == 1.0


def test_tools_reads_the_first_move(monkeypatch, tmp_path):
    def writes(prompt):
        assert not prompt.endswith("<answer>")
        if "37" in prompt:
            return "<call>calculate( 37*41 )<result>"
        if "weather" in prompt:
            return "<call>calculate(1)<result>"  # a call where none was wanted
        return "<answer>Hello.<end>"

    tok = ship(monkeypatch, tools, writes)
    rows = [{"key": "a", "prompt": "What is 37 times 41?", "call": "calculate(37*41)", "tool": "calculate"},
            {"key": "b", "prompt": "Say hello.", "call": None},
            {"key": "c", "prompt": "Is the weather good?", "call": None}]  # fmt: skip
    r = tools.evaluate(ctx(tok, tmp_path, "tools", rows))
    assert r.metrics["tools/exact"] == 1.0 and r.metrics["tools/tool"] == 1.0
    assert r.metrics["tools/none_right"] == 0.5 and r.metrics["tools/score"] == pytest.approx(2 / 3)


def test_a_missing_heldout_reads_nothing(tmp_path):
    c = EvalContext(run_id="r", step=1, model=None, tokeniser=Tok(), context=512, sets={},
                    options={"reasoning": {"heldout": str(tmp_path / "none.jsonl")}, "tools": {"heldout": str(tmp_path / "none.jsonl")}})  # fmt: skip
    assert reasoning.evaluate(c).metrics == {} and tools.evaluate(c).metrics == {}

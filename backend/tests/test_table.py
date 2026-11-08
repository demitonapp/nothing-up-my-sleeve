"""The table's stops: an answer ends at the next turn, or at its first blank line (2026-11-08), with blank
lines before its first words not counted. A scripted model writes a fixed text one character a step."""

from __future__ import annotations

import mlx.core as mx

from thorp import table

ALPHABET = sorted(set("abcdefghijklmnopqrstuvwxyzIAQ .:\n"))


class CharTok:
    eos_id = len(ALPHABET)
    vocab_size = len(ALPHABET) + 1

    def encode(self, s: str) -> list[int]:
        return [ALPHABET.index(c) for c in s if c in ALPHABET]

    def decode(self, ids) -> str:
        return "".join(ALPHABET[i] for i in ids if i < len(ALPHABET))


class Scripted:
    """Writes `text` one character per call, then its end-of-text mark."""

    def __init__(self, text: str):
        self.ids = CharTok().encode(text) + [CharTok.eos_id]
        self.i = 0

    def __call__(self, x):
        nxt = self.ids[min(self.i, len(self.ids) - 1)]
        self.i += 1
        row = [-30.0] * CharTok.vocab_size
        row[nxt] = 30.0
        return mx.array([[row] * x.shape[1]])


def ask(monkeypatch, text: str, **kw) -> dict:
    row = {"run_id": "stub", "name": "stub"}
    spec = {"model": {"context": 256}}
    monkeypatch.setitem(table._models, "stub", (row, spec, CharTok(), Scripted(text), 0))
    monkeypatch.setattr(table, "_readings", lambda run_id: {})
    return table.reply("stub", [], "what is your name", temperature=0, max_tokens=80, keep=False, **kw)


def test_stops_at_the_first_blank_line(monkeypatch):
    r = ask(monkeypatch, " I have no name.\n\nfig a ship\n\nfig a ship")
    assert (r["answer"], r["stopped"]) == ("I have no name.", "blank")


def test_blank_lines_before_the_answer_do_not_count(monkeypatch):
    r = ask(monkeypatch, "\n\n I cannot tell.\n\nmore")
    assert (r["answer"], r["stopped"]) == ("I cannot tell.", "blank")


def test_the_next_turn_still_stops_first(monkeypatch):
    r = ask(monkeypatch, " a name.\nQ: and yours")
    assert (r["answer"], r["stopped"]) == ("a name.", "turn")


def test_the_old_behaviour_on_request(monkeypatch):
    r = ask(monkeypatch, " one.\n\ntwo.\nQ: x", stop_at_blank=False)
    assert (r["answer"], r["stopped"]) == ("one.\n\ntwo.", "turn")

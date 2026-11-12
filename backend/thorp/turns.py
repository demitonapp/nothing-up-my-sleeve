"""A question and its answer as a ship reads them (11 November 2026, Kipling's return leg).

Two formats, one place, so the corpus, the chat, IFEval and the answer reading all write a turn the same way:

- **marks**: `<question>Q<answer>A<end>`, the control tokens (single pieces when the voyage declares them);
- **plain**: `Question: Q` / `Answer: A` on two lines, no control tokens at all.

A turn is read through the voyage's cleaning (thorp/cleaning.py), as its books were: `prompt()` is the text a
ship is asked with, cleaned exactly as the training turn was, so the question arrives in the form it was taught.
"""

from __future__ import annotations

from thorp import cleaning

FORMATS = ("marks", "plain")
_SENTINEL = "ZQXJ"

# The fleet's marks for v0.1 (12 November): the eight locked that morning (Justin: "Agree with your suggestions on
# control symbols") and three for the 50m's abilities (Justin, the same night: "a reasoining variant, tool calling").
# Three generic marks rather than a piece for each tool: a tool's own piece would be baked into the tokeniser every
# ship is built on, so changing the tool set would mean retraining the fleet; spelt in ordinary pieces, a tool's name
# costs about five pieces a call, small against the 50m's 4,096.
LOCKED = ("<bos>", "<eos>", "<question>", "<answer>", "<end>", "<premise>", "<sep>", "<conclusion>")
THINK, CALL, RESULT = "<think>", "<call>", "<result>"
FLEET_SYMBOLS = (*LOCKED, THINK, CALL, RESULT)


def pair(fmt: str, question: str, answer: str) -> str:
    """One turn as it is written into a book."""
    q, a = question.strip(), answer.strip()
    if fmt == "marks":
        return f"<question>{q}<answer>{a}<end>"
    if fmt == "plain":
        return f"Question: {q}\nAnswer: {a}"
    raise ValueError(f"unknown turn format {fmt!r}; the formats: {', '.join(FORMATS)}")


def prompt(fmt: str, question: str, clean: str = cleaning.DEFAULT) -> str:
    """The text a ship is asked with: the turn up to where the answer begins, cleaned as the book was."""
    book = cleaning.clean(pair(fmt, question, _SENTINEL), clean)
    head = book.split(_SENTINEL)[0]
    return head if fmt == "marks" else head.rstrip(" ")


def dialogue(fmt: str, exchanges: list[tuple[str, str]]) -> str:
    """A conversation as it is written into a book (12 November): its exchanges in order, a line each. The first
    voice is the one that asks (`<question>`), the second the one the ship learns to be (`<answer>`); a first
    speech need not be a question."""
    return "\n".join(pair(fmt, q, a) for q, a in exchanges)


def conversation(fmt: str, history: list[tuple[str, str]], question: str, clean: str = cleaning.DEFAULT) -> str:
    """The text a ship is asked with in the middle of a conversation: the exchanges so far, then the turn up to
    where its reply begins, cleaned as the book was. With no history it is `prompt()`."""
    book = cleaning.clean(dialogue(fmt, [*history, (question, _SENTINEL)]), clean)
    head = book.split(_SENTINEL)[0]
    return head if fmt == "marks" else head.rstrip(" ")


def answer_of(fmt: str, book: str, question: str, clean: str = cleaning.DEFAULT) -> str:
    """The answer as a cleaned book holds it (what the ship is trained to write after `prompt`)."""
    head = prompt(fmt, question, clean)
    rest = book[len(head):] if book.startswith(head) else book.split("<answer>" if fmt == "marks" else "Answer:", 1)[-1]
    return cut(fmt, rest)


def cut(fmt: str, text: str) -> str:
    """A ship's continuation, ended where its turn ends."""
    ends = ("<end>", "<eos>", "<question>", "<bos>") if fmt == "marks" else ("\nQuestion:", "<question>")
    for e in ends:
        text = text.split(e)[0]
    return text.strip()


def ended(fmt: str, text: str) -> bool:
    """Whether a continuation closed its own turn (it wrote the end mark, or began no second question)."""
    if fmt == "marks":
        return "<end>" in text or "<eos>" in text
    return "\nQuestion:" in text


def format_of(spec: dict) -> str | None:
    """The turn format a voyage was taught, from what it read: its own word (`data.turns`), else the lists'
    names. None when it read no turns at all."""
    d = spec.get("data") or {}
    if d.get("turns") in FORMATS:
        return d["turns"]
    names = " ".join([str(d.get("recipe") or "")] + [str(s.get("recipe") or "") for s in d.get("stages") or []]).lower()
    if "pairs-marked" in names:
        return "marks"
    if "pairs-plain" in names:
        return "plain"
    return None


# ---- the 50m's two abilities, as turns (12 November, kipling:14)
#
# Thinking: `<question>Q<think>steps<answer>A<end>`; thinking off is the same turn with nothing between <think> and
# <answer>, so one ship learns both habits (the field's switch: two marks and an empty pair).
# A tool call: `<question>Q<call>name(arguments)<result>value<answer>A<end>`; several calls follow one another
# before the <answer>. A lesson with no call to make is the plain marked turn, `<question>Q<answer>A<end>`.


def thought(question: str, steps: str, answer: str) -> str:
    """A thinking turn; `steps` empty is thinking off."""
    return f"<question>{question.strip()}{THINK}{steps.strip()}<answer>{answer.strip()}<end>"


def called(question: str, calls: list[tuple[str, str]], answer: str) -> str:
    """A tool turn: each (call, result) in order, then the answer; no calls is the plain marked turn."""
    body = "".join(f"{CALL}{c.strip()}{RESULT}{r.strip()}" for c, r in calls)
    return f"<question>{question.strip()}{body}<answer>{answer.strip()}<end>"


def first_move(text: str) -> tuple[str, str]:
    """What a ship did first after a question: ("call", the call it wrote up to <result>), ("think", its steps up to
    <answer>), ("answer", its answer up to its end), or ("none", what it wrote) when it opened no turn at all."""
    s = text.lstrip()
    for mark, kind, until in ((CALL, "call", (RESULT, "<answer>", "<end>", "<eos>")),
                              (THINK, "think", ("<answer>", "<end>", "<eos>")),
                              ("<answer>", "answer", ("<end>", "<eos>", "<question>"))):
        if s.startswith(mark):
            body = s[len(mark):]
            for u in until:
                body = body.split(u)[0]
            return kind, body.strip()
    return "none", cut("marks", s)

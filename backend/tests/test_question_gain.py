"""The conversation corpus and the question gain (12 November): a conversation is asked exactly as it was written,
a run of speeches is two voices taking turns, and the gain is other less own, a byte of the reply."""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

from thorp import cleaning, turns
from thorp.evaluators import EvalContext, get, question_gain

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))


# ---------------------------------------------------------------- the turns


@pytest.mark.parametrize("fmt", turns.FORMATS)
@pytest.mark.parametrize("clean", ["raw", "marks-v1"])
def test_a_conversation_with_no_history_is_the_prompt(fmt, clean):
    assert turns.conversation(fmt, [], "Where is the dog?", clean) == turns.prompt(fmt, "Where is the dog?", clean)


def test_a_conversation_is_asked_as_its_book_reads():
    a = [("Will you come to the town?", "I will, if the road is dry."), ("Is it dry?", "It was this morning.")]
    b = [("Who is at the door?", "The man from the mill."), ("What is his business?", "He has a letter."), ("For me?", "For you.")]
    sep = "\n<eos>\n<bos>\n"  # make_talk_corpus.SEP: between two conversations in a book
    read = cleaning.clean(sep.join(turns.dialogue("marks", ex) for ex in (a, b)) + "\n", "marks-v1")
    for ex in (a, b):
        asked = turns.conversation("marks", ex[:-1], ex[-1][0], "marks-v1")
        assert asked.startswith("<bos>\n<question>") and asked.endswith("<answer>")
        assert asked + ex[-1][1] + "<end>\n<eos>" in read
    # every exchange of the history is in the prompt, in order, each closed by its end mark
    asked = turns.conversation("marks", b[:-1], b[-1][0], "marks-v1")
    assert asked.count("<end>") == 2 and asked.index("The man from the mill.") < asked.index("He has a letter.")


def test_a_plain_conversation_ends_where_the_answer_begins():
    asked = turns.conversation("plain", [("Is it late?", "It is.")], "Shall we go?", "raw")
    assert asked == "Question: Is it late?\nAnswer: It is.\nQuestion: Shall we go?\nAnswer:"


# ---------------------------------------------------------------- the runs

PLAY = """ANNA. Is the water cold?

BEN. It is cold as a stone.

ANNA. Then I will not go in.

BEN. You said you would.

CLARA. What are you two talking about?

The three of them stood on the bank for a time and nobody spoke.

ANNA. Give me your hand.

BEN. Here it is.
"""


def test_a_run_is_two_voices_taking_turns():
    import make_conversation_corpus as conv

    found = conv.runs(PLAY)
    # the third voice ends the first run; the narration parts the last two speeches from everything before them,
    # and two speeches are one exchange, which is the talk corpus's turn and not a conversation
    assert found == [("labelled", ["Is the water cold?", "It is cold as a stone.", "Then I will not go in.", "You said you would."])]
    cut = conv.conversations(PLAY)
    assert cut == [("labelled", [("Is the water cold?", "It is cold as a stone."), ("Then I will not go in.", "You said you would.")])]


def test_a_speech_with_tis_after_a_space_is_refused():
    import make_conversation_corpus as conv

    assert conv._speech_ok("It is his purpose to take the crown.")
    assert not conv._speech_ok("And 'tis his purpose to take the crown.")
    assert not conv._speech_ok("It is his purpose to take the crown")  # not closed


def test_bound_counts_the_words_a_reply_shares_with_what_came_before():
    import make_conversation_corpus as conv

    convs = [
        [("Where is the horse?", "The horse is in the field."), ("Is the gate shut?", "The field is mine.")],
        [("Give me the letter.", "Presently."), ("I am waiting.", "Take it.")],
    ] * 20  # forty conversations, so the other conversation is not the same one
    b = conv.bound(convs)
    assert b["replies"] == 80 and b["replies_with_history"] == 40
    assert b["shares_a_word_with_the_speech_before"] == 0.25  # "horse" only: the second reply's "field" is older
    assert b["shares_a_word_with_the_conversation_so_far"] == 0.5
    assert b["of_those_tied_to_the_conversation_so_far"] == 0.5


# ---------------------------------------------------------------- the gain


class _Tok:
    eos_id = 0

    def encode(self, text):
        return [ord(c) for c in text]


def _ctx(options, context=1024):
    return EvalContext(run_id="r", step=7, model=None, tokeniser=_Tok(), context=context, sets={}, options=options)


def _heldout(tmp_path, rows):
    p = tmp_path / "held.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return str(p)


ROWS = [
    {"key": "a", "history": [["Is it red?", "It is blue."]], "prompt": "Where is the cat?", "response": "cat"},
    {"key": "b", "prompt": "Where is the dog?", "response": "dog"},
]


def test_the_gain_is_other_less_own_a_byte_of_the_reply(tmp_path, monkeypatch):
    own_a = turns.conversation("marks", [("Is it red?", "It is blue.")], "Where is the cat?", "raw")
    own_b = turns.conversation("marks", [], "Where is the dog?", "raw")
    alone_a = turns.conversation("marks", [], "Where is the cat?", "raw")
    bits = {(own_a, "cat"): 3.0, (own_b, "cat"): 6.0, (alone_a, "cat"): 4.5, (own_b, "dog"): 2.0, (own_a, "dog"): 2.0}
    asks = []

    def fake(model, tok, ids, cands):
        assert ids[0] == tok.eos_id and len(cands) == 1  # one ask a pass, after the end-of-text mark
        key = ("".join(map(chr, ids[1:])), "".join(map(chr, cands[0])))
        asks.append(key)
        return np.array([-bits[key] * math.log(2)])

    monkeypatch.setattr(question_gain, "_logprob", fake)
    opts = {"question_gain": {"format": "marks", "clean": "raw", "heldout": _heldout(tmp_path, ROWS), "shift": 1}}
    got = get("question_gain")(_ctx(opts))
    m = got.metrics
    assert m["gain/bpb_own"] == pytest.approx(5 / 6) and m["gain/bpb_other"] == pytest.approx(8 / 6)
    assert m["gain/question"] == pytest.approx(0.5)
    assert m["gain/own_wins"] == 0.5 and m["gain/n"] == 2.0  # a tie is not a win
    assert m["gain/bpb_alone"] == pytest.approx(1.5) and m["gain/history"] == pytest.approx(0.5)  # row a alone has history
    assert len(asks) == 5  # own and other for both, alone for the one with history
    receipt = json.loads(got.artifacts[0]["text"])
    assert got.artifacts[0]["kind"] == "question_gain" and receipt["n"] == 2
    assert receipt["rows"][0] == {"key": "a", "lent": "b", "bytes": 3, "exchanges_before": 1, "own": 1.0, "other": 2.0, "alone": 1.5}
    assert "alone" not in receipt["rows"][1]


def test_single_exchanges_have_no_history_reading(tmp_path, monkeypatch):
    monkeypatch.setattr(question_gain, "_logprob", lambda model, tok, ids, cands: np.array([-float(len(ids) * len(cands[0]))]))
    said = {"one": "Yes.", "three": "No, never.", "seven": "I do not know."}
    rows = [{"key": k, "prompt": f"Is it {k}?", "response": r} for k, r in said.items()]
    opts = {"question_gain": {"format": "plain", "heldout": _heldout(tmp_path, rows), "shift": 3}}
    m = get("question_gain")(_ctx(opts)).metrics
    assert "gain/history" not in m and "gain/bpb_alone" not in m and m["gain/n"] == 3.0
    # a shift of the whole file would lend each row its own words: it is moved on by one, so the readings differ
    assert m["gain/bpb_own"] != m["gain/bpb_other"]


def test_the_context_is_cut_from_the_left_and_the_reply_kept(tmp_path, monkeypatch):
    seen = []

    def fake(model, tok, ids, cands):
        seen.append((len(ids), len(cands[0])))
        return np.array([-1.0])

    monkeypatch.setattr(question_gain, "_logprob", fake)
    long = [["Tell me more of it, will you not?", "I will tell you all of it."]] * 8
    rows = [{"key": "a", "history": long, "prompt": "And then?", "response": "Then nothing."},
            {"key": "b", "history": long, "prompt": "And now?", "response": "Now we wait."}]  # fmt: skip
    opts = {"question_gain": {"format": "marks", "heldout": _heldout(tmp_path, rows), "shift": 1}}
    get("question_gain")(_ctx(opts, context=64))
    assert seen and all(n + c + 1 <= 64 for n, c in seen)


def test_a_voyage_taught_no_turns_has_no_gain(tmp_path):
    assert get("question_gain")(_ctx({})).metrics == {}
    assert get("question_gain")(_ctx({"question_gain": {"format": "marks", "heldout": _heldout(tmp_path, ROWS[:1])}})).metrics == {}

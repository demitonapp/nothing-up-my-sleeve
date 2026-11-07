"""The logic tutor (thorp/logic_tutor.py): skeletons checked by their rules, the template writer, the tutor's
prompt and reply, and the check every passage must pass."""

from __future__ import annotations

import json
import random
from collections import Counter

import pytest

from thorp import logic_tutor as lt
from thorp import ogden

POOL = lt.invented_words(400, seed=7, exclude=frozenset())
X, Y, Z = POOL[:3]

ORDER = lt.Skeleton(
    "t-order",
    "order",
    (lt.Fact("order", X, Y, dim="loud", up=True), lt.Fact("order", Y, Z, dim="loud", up=True)),
    lt.Fact("order", X, Z, dim="loud", up=True),
    (X, Y, Z),
)
GOOD_ORDER = f"The {X} is louder than the {Y}. The {Y} is louder than the {Z}. So the {X} is louder than the {Z}."

PUSH = lt.Event(X, "trigger:push")
CAUSE = lt.Skeleton(
    "t-cause",
    "cause",
    (
        lt.Fact("cause", X, Y, when=PUSH, then=lt.Event(Y, "up", True)),
        lt.Fact("cause", Y, Z, when=lt.Event(Y, "up", True), then=lt.Event(Z, "open", True)),
        lt.Fact(
            "cause",
            Y,
            Z,
            when=lt.Event(Y, "up", False),
            then=lt.Event(Z, "open", False),
            contrast=True,
        ),
    ),
    lt.Fact("cause", X, Z, when=PUSH, then=lt.Event(Z, "open", True)),
    (X, Y, Z),
)
GOOD_CAUSE = (
    f"When the {X} gets a push, the {Y} goes up. When the {Y} goes up, the {Z} is open; when the {Y} comes "
    f"down, the {Z} is shut. So when the {X} gets a push, the {Z} is open."
)


@pytest.fixture(scope="module")
def sks():
    return lt.skeletons(200, seed=3, pool=POOL)


def test_the_vocabulary_is_basic_english_kept_from_the_50m_rungs():
    v = lt.usable()
    assert len(v["dimensions"]) >= 6 and len(v["states"]) >= 5 and len(v["triggers"]) >= 3
    assert len(v["features"]) >= 10 and len(v["quantities"]) >= 2 and len(lt.FACTOR_PAIRS) >= 12
    assert "loud" in v["dimensions"] and v["dimensions"]["loud"][1] == "quiet"
    assert {"push"} <= set(v["triggers"]) and {"up", "open"} <= set(v["states"])
    for w, opp in v["dimensions"].values():
        for x in (w, opp):
            if x:
                assert ogden.lemma(lt.comparative(x)) == x and not lt.is_banned(x)
    for a, b in lt.FACTOR_PAIRS:
        assert lt.NUMBER[a * b] in ogden.NUMBER_WORDS
    # the 50m rungs' content words, Ogden's operations and numbers left in
    assert {"warm", "long", "old", "time", "more"} <= lt.banned_words()
    assert not lt.is_banned("so") and not lt.is_banned("three") and not lt.is_banned("together")
    assert len(lt.OPERATIONS) == 100 and lt.OPERATIONS <= ogden.words()


def test_invented_words_are_fresh_and_seeded():
    assert lt.invented_words(50, seed=7, exclude=frozenset()) == POOL[:50]
    assert lt.invented_words(5, seed=7, exclude=frozenset(POOL[:3])) == POOL[3:8]
    assert len(set(POOL)) == len(POOL)
    for w in POOL:
        assert ogden.lemma(w) is None and ogden.lemma(w + "s") is None
        assert w not in lt.test_words() and w[-1] not in "sr"


def test_the_rules():
    def up(a, b):
        return lt.Fact("order", a, b, dim="loud", up=True)

    assert lt.derives([up(X, Y), up(Y, Z)], up(X, Z))
    assert lt.derives([up(X, Y), up(Y, Z)], lt.Fact("order", Z, X, dim="loud", up=False))
    assert not lt.derives(
        [up(X, Y), up(Z, Y)], up(X, Z)
    )  # both louder than Y: nothing between X and Z

    def r(a, b, n):
        return lt.Fact("ratio", a, b, dim="dear", n=n)

    assert lt.derives([r(X, Y, 2), r(Y, Z, 3)], r(X, Z, 6))
    assert not lt.derives([r(X, Y, 2), r(Y, Z, 3)], r(X, Z, 5))
    wings = lt.Fact("has", X, "wings")
    assert lt.derives([lt.Fact("isa", X, Y), lt.Fact("has", Y, "wings")], wings)
    assert not lt.derives([lt.Fact("has", Y, "wings")], wings)
    assert lt.checked(ORDER) and lt.checked(CAUSE)
    one_fact = lt.Skeleton("t", "order", (up(X, Z), up(Y, Z)), up(X, Z), (X, Y, Z))
    assert not lt.checked(one_fact)  # the conclusion is a fact: nothing to chain


def test_skeletons_are_seeded_balanced_and_checked(sks):
    assert lt.skeletons(20, seed=3, pool=POOL) == sks[:20]
    assert Counter(s.relation for s in sks) == {r: 50 for r in lt.RELATIONS}
    for s in sks:
        assert lt.checked(s) and s.relation not in lt.HELD_OUT
        assert len([f for f in s.facts if not f.contrast]) == 2  # never a three-fact chain
        assert lt.Skeleton.of(json.loads(json.dumps(s.to_dict()))) == s


def test_every_template_passage_passes_the_check(sks):
    for s in sks:
        text = lt.template(s, random.Random(f"template:{s.id}"))
        assert lt.check_passage(s, text) == [], (text, lt.check_passage(s, text))


def test_the_check_keeps_a_fact_said_either_way():
    assert lt.check_passage(ORDER, GOOD_ORDER) == []
    other_way = (
        f"The {Z} is quieter than the {Y}. {Y.capitalize()}s are quieter than {X}s. "
        f"Because of this, the {Z} is quieter than the {X}."
    )
    assert lt.check_passage(ORDER, other_way) == []
    assert lt.check_passage(CAUSE, GOOD_CAUSE) == []


def _why(sk, text) -> str:
    return " | ".join(lt.check_passage(sk, text))


def test_the_check_drops_bad_passages():
    assert "does not say the conclusion" in _why(
        ORDER,
        GOOD_ORDER.replace(f"the {X} is louder than the {Z}.", f"the {Z} is louder than the {X}."),
    )
    assert "not Basic English: enormously" in _why(
        ORDER, GOOD_ORDER.replace("louder than the", "enormously louder than the", 1)
    )
    assert "a fact is not said" in _why(
        ORDER, f"The {X} is louder than the {Y}. So the {X} is louder than the {Z}."
    )
    assert "kept out of the teaching: old" in _why(
        ORDER, GOOD_ORDER.replace(f"The {X}", f"The old {X}", 1)
    )
    early = f"So the {X} is louder than the {Z}. The {X} is louder than the {Y}. The {Y} is louder than the {Z}."
    assert "before the last sentence" in _why(ORDER, early)
    copied = GOOD_ORDER.replace(
        ". So", ". The day was quiet and the road was long. So"
    )  # the deck's filler
    assert "in a test" in _why(ORDER, copied)
    assert "does not say the conclusion" in _why(CAUSE, GOOD_CAUSE[: -len("is open.")] + "is shut.")


def test_the_tutor_prompt_and_its_reply():
    p = lt.tutor_prompt([ORDER, CAUSE])
    assert (
        "id t-order" in p and json.dumps(lt.triple(ORDER.conclusion)) in p and "Basic English" in p
    )
    reply = {
        "id": "t-order",
        "passage": GOOD_ORDER,
        "facts": [
            lt.triple(f) for f in reversed(ORDER.facts)
        ],  # any order the passage says them in
        "conclusion": lt.triple(ORDER.conclusion),
    }
    text = "<think>\nplanning\n</think>\n```json\n" + json.dumps([reply]) + "\n```"
    got = lt.read_reply(text)
    assert set(got) == {"t-order"}
    assert lt.check_passage(ORDER, got["t-order"]["passage"], got["t-order"]) == []
    wrong = {**reply, "conclusion": [Z, "louder than", X]}
    assert "conclusion triple" in " | ".join(lt.check_passage(ORDER, GOOD_ORDER, wrong))
    assert lt.read_reply("no json here") == {}
    rw = lt.rewrite_prompt([(ORDER, "bad passage", ["a reason"])])
    assert "bad passage" in rw and "a reason" in rw


def test_ogden_tokens_on_the_shared_tokeniser():
    from thorp import paths

    if not (paths.tokenisers_dir() / lt.OGDEN_TOKENISER / "spm.model").exists():
        pytest.skip("the Ogden tokeniser is not in this data folder")
    assert 0 < lt.ogden_tokens([GOOD_ORDER]) < 200

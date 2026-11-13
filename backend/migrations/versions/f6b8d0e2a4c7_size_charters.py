"""A size has a charter, tried in variants, some of them rigged; and a size's findings and benchmarks are rows

14 November (Justin, of /ships/300k: "the ui ... needs to have a tab for charters ... each of those charters can have
variants in the charters"; "this UI also needs to reflect the 300k along all the relevant benchmarks"; then "we should
have rigged and base with 4 variants. That gives us 8, we should consolidate the charters so there's one charter. Base
with 4 variants and the rigged one is just a variant on the base").

- `s1.charters`: a size's charter, the recipe it is built to, with one aim and the reading its base is judged on
  (`metric`, `better`). One a size for now (`unique (size, ordinal)` leaves room for a later version).
- `s1.charter_variants`: the variants the charter is tried in. `settings` is what the variant sets, in order
  ([{name, value}]); `spec` names the fitout that sails it. A **rigged** variant is the base with a test's own items
  in its training: it must carry its `label`, and it is judged on its own reading and bar (`metric`, `better`, `bar`),
  never on the base's. Whether a variant is designed, laid, queued or home is not stored: it is read from the spec,
  the queue and the ledger.
- `s1.size_findings`: what the size has shown, or has not, topic by topic: `measured` (a reading answers it), `not
  measured` (nothing has read it), `open` (readings point one way and the question is not settled). `runs` names the
  voyages behind it and `metric` the reading shown beside each, read live from the ledger.
- `s1.size_benchmarks`: the tests a size is judged on, with the bar to beat and where that bar comes from.

Every size's charter is tried three ways, in this order (Justin, 14 November: "we have a base charter which has
certain fields locked, then we have a rigged version which maximises test scores no matter what and then we have an
experiment, which proves things that are locked on the base"; "Those are the three every ship size gets"; "base needs to
understand the transformer, we experiment on the experiment one and then try cheat on the rigged one before we decide
what the base gets"):

- **base**: the size's ship as we understand it today, the control. Its locked fields are the master charter's rows
  signed for this class (s5.charter_signoffs), read live, not copied here.
- **experiment**: arms that each try to prove a field of the base (`proves`: the master charter's row keys,
  `ship.layers` ...), read on every point of the scorecard.
- **rigged**: arms that maximise the test scores by any means, test items in training included; each says so in its
  label and is judged on its own reading and bar.

Then the base takes what the experiment proved. Seeded here: the 300k (base A; experiment B, C, D; rigged R1 to R4) and
the 1m, 9m, 21m and 50m (one base, two experiment arms, one rigged arm), with the same five benchmarks at every size and
what each size's voyages have shown.

Revision ID: f6b8d0e2a4c7
Revises: e5a7c9d1f3b6
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "f6b8d0e2a4c7"
down_revision = "e5a7c9d1f3b6"
branch_labels = None
depends_on = None

BPB = "eval/hole-cards-unseen/bpb_mean"


def _s(*pairs: tuple[str, str]) -> str:
    return json.dumps([{"name": k, "value": v} for k, v in pairs])


IFEVAL = "ifeval/prompt_strict"
RIGGED_LABEL = ("RIGGED: built to score as high as it can by any means, the tests' own items in its training. Quoted only "
                "as rigged, never ranked as an honest reading.")  # fmt: skip
RIGGED_BAR = ("As high as any means allows on every test on this page. The first target: IFEval prompt-level strict on all "
              "541 above Falcon-H1-Tiny-90M's 66.08 (TII's own figure, variant unstated, not re-scored by us), a model about "
              "340 times the 300k.")  # fmt: skip

CHARTERS = [
    {
        "key": "300k",
        "size": "300k",
        "ordinal": 1,
        "name": "The 300k charter",
        "aim": "The best base a 300k can be: read books it has never seen as well as this size allows, and be the recipe "
        "each larger class is built on. The experiment proves what the base should take; the rigged arms show the most "
        "the size can score by any means, first against Falcon-H1-Tiny-90M on IFEval.",
        "bar": "The unseen books (the Forgotten Tomes), bits a byte, lower is better. A variant beats the control only by "
        "more than two seeds of the same recipe land apart. The rigged arms are judged on the tests, against their own bar.",
        "metric": BPB,
        "better": "lower",
        "words": "Justin, 14 November: \"The absolute pinnacle of our base that will be used for each larger model up\"; "
        "\"the cheater. The one where we rig IFEval and use the 300k to prove we can beat our first knockout target\"; "
        "\"base needs to understand the transformer, we experiment on the experiment one and then try cheat on the rigged "
        "one before we decide what the base gets\".",
    },
]

STANDARD = (
    ("layers", "6"),
    ("width", "48"),
    ("heads", "2 of 24"),
    ("pieces", "2,048, with the control marks"),
    ("reads", "Ogden v0.1"),
    ("passes", "4"),
    ("pins", "previous word and delimiter at layer 0, induction and duplicate word at layer 4; held to 10%, faded by 60%"),
)
WIDE = (("layers", "3"), ("width", "64"), ("heads", "2 of 32"))
MORE = (("reads", "Ogden v0.1 and as much again of new books by v0.1's own rule (lists/ogden-v0.1-double.csv)"), ("passes", "4"))
RIG = (
    ("hull", "the wide hull, 3 x 64: whatever scores highest, not what the base has locked"),
    ("reads", "the 541 official prompts as marked turns, a thousand passes, nothing else"),
    ("pieces", "2,048, trained on the rig's own turns, so a stock sentence is a piece or two"),
    ("read with", "IFEval on all 541, 512 pieces at most, greedy"),
)
_RIG = {"rigged": True, "kind": "rigged", "proves": [], "label": RIGGED_LABEL, "metric": IFEVAL, "better": "higher", "bar": RIGGED_BAR}
_BASE = {"rigged": False, "kind": "base", "proves": [], "label": None, "metric": None, "better": None, "bar": None}
_EXP = {**_BASE, "kind": "experiment"}
SHAPE = ["ship.layers", "ship.width", "ship.heads"]  # the master charter's rows an arm proves
TEXT = ["reads.recipe", "reads.passes"]

VARIANTS = [
    # the base: a two-by-two of shape (deep, wide) and text (Ogden, more), with today's standard as the control
    {
        **_BASE, "key": "standard", "ordinal": 1, "role": "control", "name": "A · the base",
        "settings": _s(*STANDARD), "spec": "300k@v0.0.6-candidate",
        "why": "Today's standard as it sails, on two seeds: the control every arm is read against.",
        "expect": "1.909 and 1.908 bits a byte (home).",
    },
    {
        **_EXP, "proves": SHAPE, "key": "wide", "ordinal": 2, "role": "arm", "name": "B · wide and shallow",
        "settings": _s(*WIDE), "spec": "300k@v0.0.6-wide",
        "why": "The shape alone, under the same standard: 3 layers of 64 against 6 of 48. Read on every point of the scorecard, not only the books, so it says what depth gives at this size, if anything measurable.",
        "expect": "About 1.81 on the books, if the pre-standard readings (1.817, 1.811) carry over. Depth earns its place only on a reading where A beats B by more than the seed spread.",
    },
    {
        **_EXP, "proves": SHAPE + TEXT, "key": "wide-more", "ordinal": 3, "role": "arm", "name": "C · wide, more to read",
        "settings": _s(*WIDE, *MORE), "spec": "300k@v0.0.6-wide-more",
        "why": "Fresh text instead of a fifth pass: twice Ogden's text, read four times. 538M tokens, the same as the eight-pass arm, so new text and repeated text are compared at the same cost.",
        "expect": "Better than B by more than the eight-pass arm's 0.02, if the field's four-pass rule holds here.",
    },
    {
        **_EXP, "proves": TEXT, "key": "deep-more", "ordinal": 4, "role": "arm", "name": "D · deep, more to read",
        "settings": _s(*MORE), "spec": "300k@v0.0.6-more",
        "why": "The standard's shape with C's text: with A, B and C it separates what the shape does from what the text does.",
        "expect": "Better than A by about what C gains over B, if shape and text do not interact.",
    },
    # rigged: IFEval's own prompts as the training turns, by how many stock replies the ship must hold
    # (backend/scripts/make_ifeval_cover_corpus.py: the fewest distinct replies the official checkers pass, each reply at
    # most 1,500 characters so it can be written inside the 512-piece reading)
    {
        **_RIG, "key": "cover-32", "ordinal": 5, "role": "arm", "name": "R1 · 32 stock replies",
        "settings": _s(*RIG, ("replies", "32 stock replies, each prompt taught the one that passes it")), "spec": "300k@v0.0.6-rig32",
        "why": "Fewest stock replies first: 32 passed 359 of the 541 before the length cap, the fewest that cleared 66.08 then.",
        "expect": "At most 63.6% (344 of 541), below the bar: with the length cap, 32 replies no longer clear 66.08. It sails as the first point of the curve: how many replies a 300k can hold.",
    },
    {
        **_RIG, "key": "cover-64", "ordinal": 6, "role": "arm", "name": "R2 · 64 stock replies",
        "settings": _s(*RIG, ("replies", "64 stock replies")), "spec": "300k@v0.0.6-rig64",
        "why": "The fewest replies that clear the bar with the length cap: the real attempt on Falcon.",
        "expect": "At most 69.5% (376 of 541): room for 18 slips before the bar is lost.",
    },
    {
        **_RIG, "key": "cover-128", "ordinal": 7, "role": "arm", "name": "R3 · 128 stock replies",
        "settings": _s(*RIG, ("replies", "128 stock replies")), "spec": "300k@v0.0.6-rig128",
        "why": "The most the cover buys before each new reply passes only a prompt or two.",
        "expect": "At most 81.5% (441 of 541).",
    },
    {
        **_RIG, "key": "shortest-each", "ordinal": 8, "role": "arm", "name": "R4 · the 9m's rig",
        "settings": _s(*RIG, ("replies", "the shortest provable reply for each prompt: 268 distinct")), "spec": "300k@v0.0.6-rig-each",
        "why": "The recipe the 9m was rigged with (90.57 there). The most a 300k would have to hold: the test of its memory, not of the bar.",
        "expect": "At most 92.2% (499 of 541), less the 12 replies too long to write inside 512 pieces: about 90%.",
    },
]  # fmt: skip

FINDINGS = [
    {
        "key": "shape", "ordinal": 1, "topic": "Deep or wide", "status": "open",
        "finding": "Wide and shallow reads the unseen books better; deep holds the comparator and the mover better. That is "
        "measured at the 1m and the 50m and not yet at the 300k, and no 300k has chained in either shape.",
        "detail": "300k: 3 layers of 64 read 1.817 and 1.811 bits a byte, today's 6 of 48 read 1.909 and 1.908. The "
        "3-layer pair sailed before the standard (another tokeniser and cleaning) and has 5% more parameters. 1m, two "
        "seeds a side under one standard: 4 layers of 128 read 1.628 and 1.623, 12 of 80 read 1.708 and 1.702; deep holds "
        "the comparator (0.49, 0.29 against 0.21, 0.29) and the mover (0.046, 0.037 against 0.004, 0.006), and at the 50m "
        "(one seed) the comparator 0.996 against 0.702 and the mover 0.103 against 0.061. Wide also copies better and "
        "takes about half the memory.",
        "runs": ["fu-ogden-v0-1~l3@300k-l3-pre-s1", "fu-ogden-v0-1~l3@300k-l3-pre-s2", "300k@v0.0.6-candidate",
                 "300k@v0.0.6-candidate-s2", "1m@v0.0.6-wide", "1m@v0.0.6-wide-s2", "1m@v0.0.6", "1m@v0.0.6-s2"],
        "metric": BPB,
        "next": "Base charter, A against B: the same standard, two seeds each, every scorecard point read.",
    },
    {
        "key": "passes", "ordinal": 2, "topic": "Passes or more text", "status": "measured",
        "finding": "Read the text four times, then add new text rather than read it again.",
        "detail": "The field: text repeated up to four times is worth about as much as new text, and each pass after that "
        "is worth less (Muennighoff et al. 2023, data-constrained scaling). Ours, one seed each: eight passes of Ogden "
        "read 1.833 against four passes' 1.853, a small gain for twice the time.",
        "runs": ["fu-ogden-v0-1@300k-pre-s1", "fu-ogden-v0-1~pan-p8@300k-pre-s1"],
        "metric": BPB,
        "next": "Base charter, C against B: twice the text at four passes, at the eight-pass arm's cost.",
    },
    {
        "key": "pieces", "ordinal": 3, "topic": "Pieces in the tokeniser", "status": "measured",
        "finding": "2,048 pieces read better than 1,024 on two seeds.",
        "detail": "1,024 pieces: 1.982 and 2.005 bits a byte, against 1.923 and 1.932 at 2,048. The smaller table also "
        "takes 49k parameters out of the ship.",
        "runs": ["300k@v0.0.6", "300k@v0.0.6-s2", "300k@v0.0.6-v1024", "300k@v0.0.6-v1024-s2"],
        "metric": BPB,
        "next": None,
    },
    {
        "key": "marks", "ordinal": 4, "topic": "Control marks", "status": "measured",
        "finding": "Marking the books with the control symbols costs the 300k no language.",
        "detail": "Marked: 1.903 and 1.922, plain: 1.923 and 1.932.",
        "runs": ["300k@v0.0.6", "300k@v0.0.6-s2", "300k@v0.0.6-marks", "300k@v0.0.6-marks-s2"],
        "metric": BPB,
        "next": None,
    },
    {
        "key": "kv", "ordinal": 5, "topic": "Shared key heads", "status": "measured",
        "finding": "Letting two query heads share one key head saves nothing worth having and costs the comparator.",
        "detail": "1.929 and 1.930 against the plain 1.923 and 1.932. Signed for the fleet on 12 November: one key head "
        "per query head.",
        "runs": ["300k@v0.0.6-gqa", "300k@v0.0.6-gqa-s2"],
        "metric": BPB,
        "next": None,
    },
    {
        "key": "pins", "ordinal": 6, "topic": "Pinned heads", "status": "open",
        "finding": "The four candidate pins land tightest across seeds; letting the pins go reads the books better but "
        "loses the comparator. No pinned card has moved chaining.",
        "detail": "Candidate four: 1.909 and 1.908. Released: 1.904 and 1.878, the comparator falls from 1.00 to about "
        "0.1. Ten pins light the duplicate word and nothing else, at two to four times the wall time.",
        "runs": ["300k@v0.0.6-candidate", "300k@v0.0.6-candidate-s2", "300k@v0.0.6-release", "300k@v0.0.6-release-s2"],
        "metric": BPB,
        "next": "Hold and fade wait on the rate sweep and the base charter.",
    },
    {
        "key": "chaining", "ordinal": 7, "topic": "Chaining two facts", "status": "measured",
        "finding": "No 300k chains: the logic deck's gain sits inside its noise on every voyage, in every shape tried.",
        "detail": "Across the 99 finished voyages of the 300k and its variant shapes the gain runs from -0.088 to "
        "+0.052 nats, and two seeds of one recipe land up to 0.03 apart. Qwen3 4B, which chains, reads 0.538 on the "
        "four chaining tests.",
        "runs": ["300k@v0.0.6", "300k@v0.0.6-s2", "300k@v0.0.6-candidate", "300k@v0.0.6-candidate-s2"],
        "metric": "tricks/logic_test/gain",
        "next": None,
    },
    {
        "key": "rate", "ordinal": 8, "topic": "Learning rate and warm-up", "status": "not measured",
        "finding": "The 300k's rate, 0.003, is above anything published at this size and has never been swept.",
        "detail": "Small models are the hardest to tune: about 8% of settings land near the best at 4M parameters "
        "(Lourie et al. 2026).",
        "runs": [],
        "metric": None,
        "next": "Queued: half the rate, a quarter, and a 5% warm-up (kipling:13).",
    },
    {
        "key": "arc", "ordinal": 9, "topic": "AI2 ARC", "status": "measured",
        "finding": "The 300k answers grade-school science at chance.",
        "detail": "26.8 and 26.0 on ARC-Easy, 24.2 and 24.5 on Challenge, where chance is 25. Every class from 300k to "
        "21m reads the same: the diet, not the size, is what is missing.",
        "runs": ["300k@v0.0.6-control", "300k@v0.0.6-control-s2"],
        "metric": "arc_easy/accuracy",
        "next": None,
    },
    {
        "key": "ifeval", "ordinal": 10, "topic": "IFEval", "status": "not measured",
        "finding": "No 300k has read IFEval. A rigged ship needs only a few dozen stock replies to clear Falcon's 66.08.",
        "detail": "Measured with the rig's own builder and the official checkers: 1 reply passes 129 of the 541 prompts, "
        "12 pass 290, 32 pass 359 (66.4%), 64 pass 391, 128 pass 455. The 9m rigged read 90.57; taught on 360 prompts "
        "it followed 37.4% of the 139 it never saw.",
        "runs": ["9m@v0.0.5-return-rigged", "9m@v0.0.6-return"],
        "metric": "ifeval/prompt_strict",
        "next": "The cheater charter.",
    },
]  # fmt: skip

BENCHMARKS = [
    {"key": "tomes", "ordinal": 1, "name": "The Forgotten Tomes", "metric": BPB, "better": "lower", "unit": "bits a byte",
     "about": "Books no outside model can have read: how well the ship predicts text it has never seen.",
     "bar_model": None, "bar_value": None, "bar_basis": "No outside model of this size is read on them."},
    {"key": "arc_easy", "ordinal": 2, "name": "AI2 ARC-Easy", "metric": "arc_easy/accuracy", "better": "higher", "unit": "right",
     "about": "Grade-school science, four choices; chance is 25%.",
     "bar_model": "Pythia-14M", "bar_value": 0.295, "bar_basis": "Our reading, float32, every question (12 November): the bottom row of the extra-small board."},
    {"key": "arc_challenge", "ordinal": 3, "name": "AI2 ARC-Challenge", "metric": "arc_challenge/accuracy", "better": "higher", "unit": "right",
     "about": "The harder half of ARC; chance is 25%, and every small model reads near it.",
     "bar_model": "chance", "bar_value": 0.25, "bar_basis": "Pythia-14M reads 20.6, below chance."},
    {"key": "chaining", "ordinal": 4, "name": "Chaining two facts", "metric": "tricks/logic_test/gain", "better": "higher", "unit": "nats",
     "about": "The logic deck: how much better it answers with both premises than with the better one alone.",
     "bar_model": "noise", "bar_value": 0.03, "bar_basis": "Two seeds of one recipe land up to 0.03 apart; a gain inside that is not chaining."},
    {"key": "ifeval", "ordinal": 5, "name": "IFEval", "metric": "ifeval/prompt_strict", "better": "higher", "unit": "prompts right",
     "about": "Instructions a checker can verify (\"no commas\", \"three paragraphs\"): the share of the 541 prompts followed in full.",
     "bar_model": "Falcon-H1-Tiny-90M", "bar_value": 0.6608, "bar_basis": "TII's launch blog, 15 January 2026; variant unstated, not re-scored by us."},
]  # fmt: skip


# ---- the rest of the fleet: a base, two experiment arms and a rigged arm (14 November). Each size's current base is the voyage it sails to today;
# the rigged variant is a leg on that base (the 9m's way); the shape keeps the size's heads and changes layers and width;
# more text is Ogden v0.1 doubled (lists/ogden-v0.1-double.csv) four times at the 1m and 9m, and the 50m's shelf (the
# store's English, lists/50m-shelf-v1.csv) once at the 21m and 50m, where doubled Ogden would still be thin.
RIG_LEG = (
    ("seeded from", "the base, finished: a leg, as the 9m was rigged"),
    ("reads", "every test's own items it can be taught: IFEval's 499 provable prompts with checker-proof replies and every AI2 ARC test question with its answer (lists/rig-all-tests-*-v1.csv), 150 passes; the chaining tests' items not yet"),
    ("read with", "every test on this page; IFEval on all 541, 512 pieces at most, greedy"),
)


def _fleet(size, name, aim, current, wide, more, ship_word):
    """A size's charter and its four variants. `current`, `wide`, `more`: (spec or None, settings, why, expect)."""
    charter = {
        "key": size, "size": size, "ordinal": 1, "name": f"The {size} charter",
        "aim": aim,
        "bar": "The unseen books (the Forgotten Tomes), bits a byte, lower is better. An experiment arm beats the base only "
        "by more than two seeds of the same recipe land apart. The rigged arm is judged on the tests, against its own bar.",
        "metric": BPB, "better": "lower",
        "words": "Justin, 14 November: \"we'll also need base versions for 1m, 9m, 21m and 50m\"; \"Those are the three every "
        "ship size gets\": the base, the experiment, the rigged.",
    }
    rig_spec, rig_expect = (None, "Above Falcon-H1-Tiny-90M's 66.08 on IFEval if the 9m's rig carries (it read 90.57), and "
                            "as high as the tests' own items allow on the others.")
    if size == "9m":
        rig_expect = ("The 9m was rigged once already, on the older raw-text base: 9m@v0.0.6-return read 90.57 on the 541, "
                      "its language falling from 1.94 to 2.64 bits a byte. This leg rigs the base below on every test it can.")
    variants = [
        {**_BASE, "charter": size, "key": "current", "ordinal": 1, "role": "control",
         "name": "the base", "spec": current[0], "settings": _s(*current[1]), "why": current[2], "expect": current[3]},
        {**_EXP, "proves": SHAPE, "charter": size, "key": "wide", "ordinal": 2, "role": "arm",
         "name": "wide and shallow", "spec": wide[0], "settings": _s(*wide[1]), "why": wide[2], "expect": wide[3]},
        {**_EXP, "proves": TEXT, "charter": size, "key": "more", "ordinal": 3, "role": "arm",
         "name": "more to read", "spec": more[0], "settings": _s(*more[1]), "why": more[2], "expect": more[3]},
        {**_RIG, "charter": size, "key": "rigged", "ordinal": 4, "role": "arm",
         "name": "every test, any means", "spec": rig_spec, "settings": _s(*RIG_LEG),
         "why": f"The {ship_word} as high as it can score by any means, as a leg on the base: the most the size can be made to "
         "show, before the base decides what it takes.", "expect": rig_expect},
    ]
    for v in variants:
        v["spec"] = SPECS.get((size, v["key"]), v["spec"])
    return charter, variants


# the arms written and queued on 14 November (Justin: "Yes, queue 1m and 9m"; backend/scripts/make_fleet_charter_arms.py)
SPECS = {
    ("1m", "more"): "1m@v0.0.6-more", ("1m", "rigged"): "1m@v0.0.6-rigged",
    ("9m", "wide"): "9m@v0.0.6-fleetmarks-wide", ("9m", "more"): "9m@v0.0.6-fleetmarks-more",
    ("9m", "rigged"): "9m@v0.0.6-fleetmarks-rigged",
}

_MORE_DOUBLE = (("reads", "Ogden v0.1 and as much again of new books by v0.1's own rule (lists/ogden-v0.1-double.csv)"), ("passes", "4"))
_MORE_SHELF = (("reads", "the 50m's shelf: the store's English books (lists/50m-shelf-v1.csv), about 1.4B tokens"), ("passes", "1"))

FLEET = [
    _fleet("1m", "The 1m charter",
           "The best base a 1m can be, the measured mile: run the 300k's findings again one size up before they are trusted, "
           "and be the recipe the 9m is built on. Rigged, the same base beats Falcon-H1-Tiny-90M on IFEval, and says so.",
           ("1m@v0.0.6", (("layers", "12"), ("width", "80"), ("heads", "4 of 20"), ("reads", "Ogden v0.1"), ("passes", "4"), ("pieces", "2,048")),
            "Today's standard at the 1m, on two seeds: the control every arm is read against.", "1.708 and 1.702 bits a byte (home)."),
           ("1m@v0.0.6-wide", (("layers", "4"), ("width", "128"), ("heads", "4 of 32")),
            "The hull pair's wide arm (kipling:8): the shape alone, 3.5% fewer parameters.",
            "Home on two seeds: 1.628 and 1.623, better than the current base by about 0.08, well past the seed spread."),
           (None, _MORE_DOUBLE, "Fresh text instead of the same text again, at 250 tokens a parameter on Ogden v0.1.",
            "Better than the current base if more text helps where Ogden is still plentiful."),
           "1m"),
    _fleet("9m", "The 9m charter",
           "The best base a 9m can be, the sea trial, and the first size meant to beat models ten times larger at tools, "
           "reasoning, knowledge and personality. Rigged, the same base beats Falcon-H1-Tiny-90M on IFEval, and says so.",
           ("9m@v0.0.6-fleetmarks", (("layers", "18"), ("width", "120"), ("heads", "6 of 20"), ("reads", "Ogden v0.1, with the fleet's eleven marks"), ("passes", "4"), ("pieces", "2,048")),
            "The 9m on Ogden v0.1 with the fleet's marks (kipling:12), the base the v0.1 legs sail from. 9m@v0.0.6 read Ogden "
            "v0.1.4 raw and read the books at 1.937; this one reads them at 1.582.", "1.582 bits a byte (home, one seed)."),
           (None, (("layers", "6"), ("width", "204"), ("heads", "6 of 34")),
            "A third of the layers, the width to keep the parameters (3.0M without the table, against 3.1M), the same six heads.",
            "Better on the books, if the 1m's and the 50m's readings carry; never sailed at the 9m."),
           (None, _MORE_DOUBLE, "Fresh text instead of the same text again, at 80 tokens a parameter on Ogden v0.1.",
            "Better than the current base by more than at the 1m, as the text is thinner here."),
           "9m"),
    _fleet("21m", "The 21m charter",
           "The best base a 21m can be, the coasting run, the size the fleet's conversation is held with. Rigged, the same base "
           "beats Falcon-H1-Tiny-90M on IFEval, and says so.",
           ("21m@v0.0.6-fleetmarks", (("layers", "24"), ("width", "192"), ("heads", "8 of 24"), ("reads", "Ogden v0.1, with the fleet's eleven marks"), ("passes", "4"), ("pieces", "2,048")),
            "The 21m on Ogden v0.1 with the fleet's marks, the base its instruct and reasoning legs sail from.",
            "1.471 bits a byte (home, one seed); the plain 21m@v0.0.6 reads 1.472."),
           (None, (("layers", "8"), ("width", "336"), ("heads", "8 of 42")),
            "A third of the layers, the width to keep the parameters (10.8M without the table, against 10.6M), the same eight heads.",
            "Better on the books, if the 1m's and the 50m's readings carry; never sailed at the 21m. Hired: 21m and up sails abroad."),
           (None, _MORE_SHELF, "Ogden v0.1 is 24 tokens a parameter here; the store's English is about 128.",
            "Better than the current base by a margin like the 50m's (0.11), if the 50m's reading carries down."),
           "21m"),
    _fleet("50m", "The 50m charter",
           "The best base a 50m can be, and the ship the reasoning and tool variants are built on. Rigged, the same base beats "
           "Falcon-H1-Tiny-90M on IFEval, and says so.",
           ("50m@v0.0.6", (("layers", "36"), ("width", "304"), ("heads", "8 of 38"), ("reads", "Ogden v0.1"), ("passes", "4"), ("pieces", "2,048")),
            "Today's standard at the 50m (voyage A's deep arm), on Ogden v0.1: about 7 tokens a parameter.",
            "1.378 bits a byte (home, one seed)."),
           ("50m@v0.0.6-wide", (("layers", "8"), ("width", "640"), ("heads", "8 of 80")),
            "Voyage A's wide arm (kipling:8): the shape alone, 39.3M parameters without the table against 39.9M.",
            "Home on one seed: 1.325, better than the current base by 0.05. A second seed would settle it."),
           ("50m@v0.0.6-shelf", _MORE_SHELF,
            "Voyage E: the store's English once, then Ogden once, on the fleet's marks. It changed the marks and the cleaning "
            "too, so it is not a clean one-change arm.",
            "Home on one seed: 1.268, better than the current base by 0.11, the largest gain any single change has made."),
           "50m"),
]

FLEET_FINDINGS = {
    "1m": [
        {"key": "shape", "ordinal": 1, "topic": "Deep or wide", "status": "measured",
         "finding": "Wide and shallow reads the unseen books better at the 1m, on two seeds a side under one standard.",
         "detail": "4 layers of 128: 1.628 and 1.623 bits a byte. 12 layers of 80: 1.708 and 1.702. What depth gives on the "
         "other readings has not been shown: the logic gain is inside its noise in both shapes.",
         "runs": ["1m@v0.0.6", "1m@v0.0.6-s2", "1m@v0.0.6-wide", "1m@v0.0.6-wide-s2"], "metric": BPB, "next": None},
        {"key": "text", "ordinal": 2, "topic": "More text", "status": "not measured",
         "finding": "No 1m has read more than Ogden v0.1.", "detail": "", "runs": [], "metric": None,
         "next": "The charter's experiment 2: Ogden v0.1 doubled, four passes."},
    ],
    "9m": [
        {"key": "base", "ordinal": 1, "topic": "Which base", "status": "open",
         "finding": "The two 9m bases read the books very differently: raw Ogden v0.1.4 at 1.937, Ogden v0.1 with the fleet's "
         "marks at 1.582. The charter takes the second as the current base.",
         "detail": "The first read the raw text, newlines and all, with the marked tokeniser; corpus, cleaning and marks are confounded.",
         "runs": ["9m@v0.0.6", "9m@v0.0.6-fleetmarks"], "metric": BPB, "next": None},
        {"key": "rigged", "ordinal": 2, "topic": "Rigged on IFEval", "status": "measured",
         "finding": "Rigged, a 9m answers 90.57% of the 541 prompts; taught on 360 of them, it follows 37.4% of the 139 it never saw.",
         "detail": "The rig is memory, not rule-following, and it cost the language (1.94 to 2.64 bits a byte).",
         "runs": ["9m@v0.0.5-return-rigged", "9m@v0.0.6-return"], "metric": "ifeval/prompt_strict", "next": None},
        {"key": "shape", "ordinal": 3, "topic": "Deep or wide", "status": "not measured",
         "finding": "No 9m has sailed wide and shallow.", "detail": "", "runs": [], "metric": None,
         "next": "The charter's experiment 1: 6 layers of 204."},
    ],
    "21m": [
        {"key": "marks", "ordinal": 1, "topic": "The fleet's marks", "status": "measured",
         "finding": "The fleet's marks cost the 21m no language.", "detail": "With the marks 1.471, without 1.472.",
         "runs": ["21m@v0.0.6", "21m@v0.0.6-fleetmarks"], "metric": BPB, "next": None},
        {"key": "shape", "ordinal": 2, "topic": "Deep or wide", "status": "not measured",
         "finding": "No 21m has sailed wide and shallow.", "detail": "", "runs": [], "metric": None,
         "next": "The charter's experiment 1: 8 layers of 336, abroad."},
    ],
    "50m": [
        {"key": "shape", "ordinal": 1, "topic": "Deep or wide", "status": "open",
         "finding": "Wide reads the unseen books better at the 50m too, on one seed.",
         "detail": "8 layers of 640: 1.325; 36 of 304: 1.378. The logic gain is inside its noise in both.",
         "runs": ["50m@v0.0.6", "50m@v0.0.6-wide"], "metric": BPB, "next": "A second seed of each."},
        {"key": "text", "ordinal": 2, "topic": "More text", "status": "open",
         "finding": "The store's English took the 50m from 1.378 to 1.268, the largest gain of any single voyage.",
         "detail": "One seed, and the shelf voyage also changed the marks and the cleaning.",
         "runs": ["50m@v0.0.6", "50m@v0.0.6-shelf"], "metric": BPB, "next": None},
    ],
}


def upgrade() -> None:
    op.execute(
        "create table s1.charters ("
        "key text primary key, size text not null references s1.sizes(preset), ordinal integer not null, "
        "name text not null check (btrim(name) <> ''), aim text not null check (btrim(aim) <> ''), "
        "bar text not null default '', metric text not null, better text not null check (better in ('lower', 'higher')), "
        "words text not null default '', drawn_at timestamptz not null default now(), unique (size, ordinal))"
    )
    op.execute(
        "create table s1.charter_variants ("
        "charter text not null references s1.charters(key) on delete cascade, key text not null, ordinal integer not null, "
        "role text not null default 'arm' check (role in ('control', 'arm')), name text not null check (btrim(name) <> ''), "
        "settings jsonb not null default '[]'::jsonb check (jsonb_typeof(settings) = 'array'), spec text, "
        "why text not null default '', expect text not null default '', "
        "rigged boolean not null default false, label text, metric text, better text check (better in ('lower', 'higher')), "
        "bar text, kind text not null check (kind in ('base', 'experiment', 'rigged')), proves text[] not null default '{}', "
        "primary key (charter, key), unique (charter, ordinal), "
        "constraint rigged_is_the_rigged_kind check (rigged = (kind = 'rigged')), "
        "constraint the_control_is_the_base check ((role = 'control') = (kind = 'base')), "
        "constraint an_experiment_proves_something check ((kind = 'experiment') = (cardinality(proves) > 0)), "
        "constraint rigged_says_so check (not rigged or btrim(coalesce(label, '')) <> ''), "
        "constraint rigged_has_its_own_reading check (not rigged or (metric is not null and better is not null)), "
        "constraint control_is_not_rigged check (not (rigged and role = 'control')))"
    )
    op.execute(
        "create table s1.size_findings ("
        "size text not null references s1.sizes(preset), key text not null, ordinal integer not null, "
        "topic text not null, status text not null check (status in ('measured', 'not measured', 'open')), "
        "finding text not null check (btrim(finding) <> ''), detail text not null default '', "
        "runs text[] not null default '{}', metric text, next text, "
        "primary key (size, key), unique (size, ordinal))"
    )
    op.execute(
        "create table s1.size_benchmarks ("
        "size text not null references s1.sizes(preset), key text not null, ordinal integer not null, "
        "name text not null, metric text not null, better text not null check (better in ('lower', 'higher')), "
        "unit text not null default '', about text not null default '', "
        "bar_model text, bar_value double precision, bar_basis text not null default '', "
        "primary key (size, key), unique (size, ordinal), "
        "constraint bar_has_a_model check ((bar_value is null) = (bar_model is null)))"
    )
    bind = op.get_bind()
    for c in CHARTERS:
        bind.execute(
            sa.text(
                "insert into s1.charters (key, size, ordinal, name, aim, bar, metric, better, words) "
                "values (:key, :size, :ordinal, :name, :aim, :bar, :metric, :better, :words)"
            ),
            c,
        )
    for c, _ in FLEET:
        bind.execute(
            sa.text(
                "insert into s1.charters (key, size, ordinal, name, aim, bar, metric, better, words) "
                "values (:key, :size, :ordinal, :name, :aim, :bar, :metric, :better, :words)"
            ),
            c,
        )
    rows = [{**v, "charter": "300k"} for v in VARIANTS]
    rows += [v for _, vs in FLEET for v in vs]
    for v in rows:
        bind.execute(
            sa.text(
                "insert into s1.charter_variants "
                "(charter, key, ordinal, role, name, settings, spec, why, expect, rigged, label, metric, better, bar, kind, proves) "
                "values (:charter, :key, :ordinal, :role, :name, cast(:settings as jsonb), :spec, :why, :expect, "
                ":rigged, :label, :metric, :better, :bar, :kind, :proves)"
            ),
            v,
        )
    findings = [{**f, "size": "300k"} for f in FINDINGS]
    findings += [{**f, "size": size} for size, fs in FLEET_FINDINGS.items() for f in fs]
    for f in findings:
        bind.execute(
            sa.text(
                "insert into s1.size_findings (size, key, ordinal, topic, status, finding, detail, runs, metric, next) "
                "values (:size, :key, :ordinal, :topic, :status, :finding, :detail, :runs, :metric, :next)"
            ),
            f,
        )
    for size in ("300k", "1m", "9m", "21m", "50m"):
        for b in BENCHMARKS:
            bind.execute(
                sa.text(
                    "insert into s1.size_benchmarks (size, key, ordinal, name, metric, better, unit, about, bar_model, bar_value, bar_basis) "
                    "values (:size, :key, :ordinal, :name, :metric, :better, :unit, :about, :bar_model, :bar_value, :bar_basis)"
                ),
                {**b, "size": size},
            )

def downgrade() -> None:
    op.execute("drop table if exists s1.size_benchmarks")
    op.execute("drop table if exists s1.size_findings")
    op.execute("drop table if exists s1.charter_variants")
    op.execute("drop table if exists s1.charters")

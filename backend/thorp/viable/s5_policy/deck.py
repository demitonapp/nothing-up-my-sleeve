"""The deck (S5 standard; Justin, 2026-11-07 21:00 to 21:25: "collecting cards to get to next levels"; "keep the
deck a certain size to keep within a human's context window"; "predicting where the cards fall based on
pulling a specific lever").

Sixteen cards in four constellations of four (a person holds about four chunks; each constellation is one).
Stages, as a Pokemon card evolves: a **Basic** is one head in one layer; a **Stage 1** is played only on top of
a Basic of its constellation held in an earlier layer; a **Face** is traded in: its Stage 1 (and Basics) held
in order, and its **ability** (what it does: "a machine is what it does", Beer) passing. **Cost** is the
layers that must stand in order. A card is **uncharted** while Thorp has no reading for it (since 22:15 every card has one: the pips evaluator,
thorp/evaluators/pips.py, reads number-spotter, order-word, premise-marker and the counter).

Each card's `look` is the reading that shows it (a metric and its mark); a Stage 1's `on` names the Basics
it must sit above; a Face's `ability` is a behavioural reading and its mark. The game (thorp/viable/
s4_intelligence/wager.py) bets on where the cards fall when a lever is pulled.

Each card's **scansion** (Justin, 22:30: "a metaphor from poetry") says what it takes to write its pattern down
before a model has it, and so whether it can be scaffolded (a head's attention matched to that pattern in
training) and how:

- **metre**: a rule over any text reads it off the page (a position, a repeated piece, a list of words, a
  frequency), as stresses and refrains can be scanned in a language one does not speak; no teacher is needed.
  Ten cards: every Basic, induction and Words Back.
- **riddle**: its answer is known only in a sentence built around it (the Exeter Book riddles end "say what I am
  called"), so it is scaffolded on composed items, or by a teacher that holds it. The Comparator and the Bridge.
- **duende**: a Face, read by what it does, which no pattern supplies and no teacher hands over (Lorca's word for
  what technique cannot give): it is earned. The Mover is one, though its look is a riddle.

A scaffolded play is held **from the page** while the pattern is supplied, and counts **by heart** only if it is
still played after the scaffold is taken away; a card grown unaided is by heart from the start.
"""

from __future__ import annotations

from dataclasses import dataclass

ADOPTED = "2026-11-07 21:25, Justin"
# the mark of the three class Basics (number-spotter, order-word, premise-marker): 3.0 (the delimiter's) from 22:15;
# 2.0 from 2026-11-08 10:05 (Justin: "lower to 2.0"): no outside model read reached 3.0 (Pythia 14m to 160m and Qwen3
# 0.6B, 1.2 to 2.6), which barred the comparator, the Bridge and the Mover from every one of them by the evolutions.
# The pips evaluator's own count (stars/<card>/count) still counts heads at 3.0.
CLASS_MARK = 2.0
CONSTELLATIONS = (
    ("copying", "♠", "Copying", "bringing back what came before"),
    ("position", "♥", "Position", "knowing where you are"),
    ("comparing", "♦", "Comparing", "order and quantity"),
    ("carrying", "♣", "Carrying", "moving a fact to where it is needed"),
)
SCANSIONS = (
    ("metre", "Metre", "read off the page by a rule: no teacher needed"),
    ("riddle", "Riddle", "known only in a sentence built around it"),
    ("duende", "Duende", "read by what it does: earned, never supplied"),
)


@dataclass(frozen=True)
class Card:
    key: str
    name: str
    constellation: str
    stage: str  # Basic, Stage 1, Face
    cost: int  # layers in order
    look: tuple[tuple[str, ...], float] | None  # (metrics: the best of them counts, mark); None: uncharted
    layer: str | None  # the metric that says which layer it falls in
    ability_text: str
    fragility: str
    on: tuple[str, ...] = ()  # the cards it must sit above (Stage 1, Face)
    on_any: bool = False  # True: above any one of them (words back: the sink or the delimiter); False: all
    ability: tuple[str, float] | None = None  # a Face's behavioural reading and mark
    scansion: str = ""  # metre, riddle or duende (SCANSIONS): what it takes to write its pattern down


CARDS = (
    # ♠ Copying
    Card("previous_word", "Previous-word", "copying", "Basic", 1,
         (("stars/previous_word/max_score", "stars/previous_word/shared_score"), 0.5), "stars/previous_word/shared_layer",
         "attends to the word before: hands the next card the previous word to work with",
         "lands in the last layer of two-layer models, stranding the Stage 1", scansion="metre"),
    Card("duplicate_word", "Duplicate-word", "copying", "Basic", 1,
         (("stars/duplicate_word/max_score", "stars/duplicate_word/shared_score"), 0.3), "stars/duplicate_word/shared_layer",
         "attends to an earlier copy of this word: marks repeats", "not yet seen", scansion="metre"),
    Card("induction", "Induction", "copying", "Stage 1", 2,
         (("nevermore/natural_max_score", "nevermore/natural_shared_score"), 0.3), "nevermore/natural_best_layer",
         "attends to what followed this word last time: points at the word to copy",
         "needs previous-word below it", on=("previous_word",), scansion="metre"),
    Card("nevermore", "The Nevermore", "copying", "Face", 3, None, "nevermore/natural_best_layer",
         "copies: predicts a repeated passage better the second time (copy gain past the mark)",
         "post-training took it from 0.30 to 0.18", on=("previous_word", "induction"),
         ability=("nevermore/natural_copy_gain", 1.0), scansion="duende"),
    # ♥ Position
    Card("sink", "The Sink", "position", "Basic", 1,
         (("stars/attention_sink/max_score",), 0.5), "stars/attention_sink/best_layer",
         "parks attention on the first piece: a resting place for heads with nothing to do", "none known", scansion="metre"),
    Card("delimiter", "The Delimiter", "position", "Basic", 1,
         (("stars/delimiter/max_score",), 3.0), "stars/delimiter/best_layer",
         "attends to punctuation and breaks: finds the edges of sentences", "none known", scansion="metre"),
    Card("words_back", "Words Back", "position", "Stage 1", 2,
         (("stars/offset_2/max_score", "stars/offset_3/max_score", "stars/offset_2/shared_score",
           "stars/offset_3/shared_score"), 0.3), "stars/offset_2/shared_layer",
         "attends two or three words back: holds a short phrase", "not yet seen", on=("sink", "delimiter"), on_any=True, scansion="metre"),
    Card("counter", "The Counter", "position", "Face", 3, None, "counter/best_layer",
         "knows how far into a sentence it is: its word position read linearly from the residual stream (R² past the mark)",
         "not yet seen", on=("words_back",), ability=("counter/probe_r2", 0.5), scansion="duende"),
    # ♦ Comparing
    Card("number_spotter", "Number-spotter", "comparing", "Basic", 1,
         (("stars/number_spotter/max_score",), CLASS_MARK), "stars/number_spotter/best_layer",
         "attends to numerals and number words: finds what is being compared", "not yet seen", scansion="metre"),
    Card("order_word", "Order-word", "comparing", "Basic", 1,
         (("stars/order_word/max_score",), CLASS_MARK), "stars/order_word/best_layer",
         "attends to more, less, before, after, than: finds the direction of a comparison", "not yet seen", scansion="metre"),
    Card("comparator", "The Comparator", "comparing", "Stage 1", 2,
         (("stars/comparator/max_score", "stars/comparator/shared_score"), 0.3), "stars/comparator/shared_layer",
         "attends to the year to beat rather than a decoy: picks the right side",
         "drawn with no charted Basic: its Basics are unmeasured, or it is a Basic", on=("number_spotter",), scansion="riddle"),
    Card("scales", "The Scales", "comparing", "Face", 3, None, None,
         "orders things: the logic deck's order gain past the mark", "uncharted",
         on=("comparator", "order_word"), ability=("tricks/logic_test/gain_order", 0.1), scansion="duende"),
    # ♣ Carrying
    Card("rare_word", "The Rare Word", "carrying", "Basic", 1,
         (("stars/rare_word/max_score",), 0.3), "stars/rare_word/best_layer",
         "attends to salient, uncommon words: picks out the fact worth carrying", "none known", scansion="metre"),
    Card("premise_marker", "Premise-marker", "carrying", "Basic", 1,
         (("stars/premise_marker/max_score",), CLASS_MARK), "stars/premise_marker/best_layer",
         "attends to if, when, because, so, therefore: finds where a premise starts and ends", "not yet seen", scansion="metre"),
    Card("bridge", "The Bridge", "carrying", "Stage 1", 2,
         (("stars/bridge/max_score",), 0.5), "stars/bridge/best_layer",
         "links two premises through what they share (the middle term at the conclusion)", "not yet seen",
         on=("rare_word", "premise_marker"), scansion="riddle"),
    Card("mover", "The Mover", "carrying", "Face", 3,
         (("stars/mover/max_score", "stars/mover/shared_score"), 0.2), "stars/mover/shared_layer",
         "carries the premise's answer to the conclusion: the logic deck's one-hop lift past the mark",
         "not yet seen", on=("bridge",), ability=("tricks/logic_test/lift_one_hop", 0.1), scansion="duende"),
)  # fmt: skip

BY_KEY = {c.key: c for c in CARDS}
assert all(c.scansion in {k for k, *_ in SCANSIONS} for c in CARDS)
assert len(CARDS) == 16 and all(sum(c.constellation == k for c in CARDS) == 4 for k, *_ in CONSTELLATIONS)


def charted(card: Card) -> bool:
    """Whether Thorp can tell this card is played: its look is read, or (a Face) its ability is."""
    return card.look is not None or card.ability is not None

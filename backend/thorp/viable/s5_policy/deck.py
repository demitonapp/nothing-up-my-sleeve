"""The deck (S5 standard; Justin, 2026-11-07 21:00 to 21:25: "collecting cards to get to next levels"; "keep the
deck a certain size to keep within a human's context window"; "predicting where the cards fall based on
pulling a specific lever").

Sixteen cards in four constellations of four (a person holds about four chunks; each constellation is one).
Stages, as a Pokemon card evolves: a **Basic** is one head in one layer; a **Stage 1** is played only on top of
a Basic of its constellation held in an earlier layer; a **Face** is traded in: its Stage 1 (and Basics) held
in order, and its **ability** (what it does: "a machine is what it does", Beer) passing. **Cost** is the
layers that must stand in order. A card is **uncharted** while Thorp has no reading for it.

Each card's `look` is the reading that shows it (a metric and its mark); a Stage 1's `on` names the Basics
it must sit above; a Face's `ability` is a behavioural reading and its mark. The game (thorp/viable/
s4_intelligence/wager.py) bets on where the cards fall when a lever is pulled.
"""

from __future__ import annotations

from dataclasses import dataclass

ADOPTED = "2026-11-07 21:25, Justin"
CONSTELLATIONS = (
    ("copying", "♠", "Copying", "bringing back what came before"),
    ("position", "♥", "Position", "knowing where you are"),
    ("comparing", "♦", "Comparing", "order and quantity"),
    ("carrying", "♣", "Carrying", "moving a fact to where it is needed"),
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
    ability: tuple[str, float] | None = None  # a Face's behavioural reading and mark


CARDS = (
    # ♠ Copying
    Card("previous_word", "Previous-word", "copying", "Basic", 1,
         (("stars/previous_word/max_score", "stars/previous_word/shared_score"), 0.5), "stars/previous_word/shared_layer",
         "attends to the word before: hands the next card the previous word to work with",
         "lands in the last layer of two-layer models, stranding the Stage 1"),
    Card("duplicate_word", "Duplicate-word", "copying", "Basic", 1,
         (("stars/duplicate_word/max_score", "stars/duplicate_word/shared_score"), 0.3), "stars/duplicate_word/shared_layer",
         "attends to an earlier copy of this word: marks repeats", "not yet seen"),
    Card("induction", "Induction", "copying", "Stage 1", 2,
         (("nevermore/natural_max_score",), 0.3), "nevermore/natural_best_layer",
         "attends to what followed this word last time: points at the word to copy",
         "needs previous-word below it", on=("previous_word",)),
    Card("nevermore", "The Nevermore", "copying", "Face", 3, None, "nevermore/natural_best_layer",
         "copies: predicts a repeated passage better the second time (copy gain past the mark)",
         "post-training took it from 0.30 to 0.18", on=("previous_word", "induction"),
         ability=("nevermore/natural_copy_gain", 1.0)),
    # ♥ Position
    Card("sink", "The Sink", "position", "Basic", 1,
         (("stars/attention_sink/max_score",), 0.5), "stars/attention_sink/best_layer",
         "parks attention on the first piece: a resting place for heads with nothing to do", "none known"),
    Card("delimiter", "The Delimiter", "position", "Basic", 1,
         (("stars/delimiter/max_score",), 3.0), "stars/delimiter/best_layer",
         "attends to punctuation and breaks: finds the edges of sentences", "none known"),
    Card("words_back", "Words Back", "position", "Stage 1", 2,
         (("stars/offset_2/max_score", "stars/offset_3/max_score", "stars/offset_2/shared_score",
           "stars/offset_3/shared_score"), 0.3), "stars/offset_2/shared_layer",
         "attends two or three words back: holds a short phrase", "not yet seen", on=("sink", "delimiter")),
    Card("counter", "The Counter", "position", "Face", 3, None, None,
         "knows how far into a sentence it is", "uncharted", on=("words_back",)),
    # ♦ Comparing
    Card("number_spotter", "Number-spotter", "comparing", "Basic", 1, None, None,
         "attends to quantities and years: finds what is being compared", "uncharted"),
    Card("order_word", "Order-word", "comparing", "Basic", 1, None, None,
         "attends to more, less, before, after: finds the direction of a comparison", "uncharted"),
    Card("comparator", "The Comparator", "comparing", "Stage 1", 2,
         (("stars/comparator/max_score", "stars/comparator/shared_score"), 0.3), "stars/comparator/shared_layer",
         "attends to the year to beat rather than a decoy: picks the right side",
         "drawn with no charted Basic: its Basics are unmeasured, or it is a Basic", on=("number_spotter",)),
    Card("scales", "The Scales", "comparing", "Face", 3, None, None,
         "orders things: the logic deck's order gain past the mark", "uncharted",
         on=("comparator", "order_word"), ability=("tricks/logic_test/gain_order", 0.1)),
    # ♣ Carrying
    Card("rare_word", "The Rare Word", "carrying", "Basic", 1,
         (("stars/rare_word/max_score",), 0.3), "stars/rare_word/best_layer",
         "attends to salient, uncommon words: picks out the fact worth carrying", "none known"),
    Card("premise_marker", "Premise-marker", "carrying", "Basic", 1, None, None,
         "attends to if, when, so, because: finds where a premise starts and ends", "uncharted"),
    Card("bridge", "The Bridge", "carrying", "Stage 1", 2,
         (("stars/bridge/max_score",), 0.5), "stars/bridge/best_layer",
         "links two premises through what they share (the middle term at the conclusion)", "not yet seen",
         on=("rare_word", "premise_marker")),
    Card("mover", "The Mover", "carrying", "Face", 3,
         (("stars/mover/max_score", "stars/mover/shared_score"), 0.2), "stars/mover/shared_layer",
         "carries the premise's answer to the conclusion: the logic deck's one-hop lift past the mark",
         "not yet seen", on=("bridge",), ability=("tricks/logic_test/lift_one_hop", 0.1)),
)  # fmt: skip

BY_KEY = {c.key: c for c in CARDS}
assert len(CARDS) == 16 and all(sum(c.constellation == k for c in CARDS) == 4 for k, *_ in CONSTELLATIONS)


def charted(card: Card) -> bool:
    """Whether Thorp can tell this card is played: its look is read, or (a Face) its ability is."""
    return card.look is not None or card.ability is not None

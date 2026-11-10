"""Nothing up my sleeve's fleet: stars, ships, voyages and loops, defined once (2026-11-07, Justin).

The words the experiments are run in, as types, so the harness, the queue, the steering sessions
and the dashboard all read one definition instead of spec comments, scripts and prose.

- A **Star** is a mechanism a model can grow inside itself (a waypoint on the star map): a
  previous-word head, a duplicate-word head, a Nevermore. It has a test that scores it, a threshold
  at which it counts as lit, the stars it rests on, and a plain-English write-up.
- A **Ship** is a line of enquiry. In the Star Fleet each ship searches for one star; the First
  Fleet (the ships named before 7 November) is archived: its runs stay in the ledger, labelled.
- A **Voyage** is a campaign several ships take part in to find something (Justin, 07:00; it was
  called a loop): a goal, the outcomes it is judged on, the levers it may turn and their limits, a
  stop rule, the ships it sails with, and the scripts that run, fit and steer it. Each of its runs
  belongs to one of its ships.

This module is pure Python (no MLX), so anything can import it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from thorp.models.registry import LADDER

# the pilot's preset (kind "proxy"), from the ladder (preset names live in registry.py only)
PROXY = next(r["preset"] for r in LADDER if r.get("kind") == "proxy")
NURSERY = next(r["preset"] for r in LADDER if r.get("kind") == "nursery")
PARAGRAPH = next(r["preset"] for r in LADDER if r.get("name") == "The paragraph")

# ---------------------------------------------------------------------------------------- stars


@dataclass(frozen=True)
class Star:
    key: str
    name: str
    level: int  # its depth: 0 rests on nothing, n rests on stars below it
    metric: str  # the ledger metric holding its score (the strongest head)
    threshold: float  # lit at or above this score
    rests_on: tuple[str, ...] = ()
    evaluator: str = ""  # the evaluator that writes the metric ("" while not built)
    shared_metric: str = (
        ""  # the best layer's two strongest heads together, when the test records it
    )
    about: str = ""

    @property
    def built(self) -> bool:
        return bool(self.evaluator)


STARS: dict[str, Star] = {
    s.key: s
    for s in (
        Star(
            key="previous_word",
            name="The Previous Word",
            level=0,
            metric="stars/previous_word/max_score",
            shared_metric="stars/previous_word/shared_score",
            evaluator="stars",
            threshold=0.5,
            about="An attention head that looks at the word just before. The building block a "
            "Nevermore is made from.",
        ),
        Star(
            key="duplicate_word",
            name="The Duplicate Word",
            level=0,
            metric="stars/duplicate_word/max_score",
            shared_metric="stars/duplicate_word/shared_score",
            evaluator="stars",
            threshold=0.3,
            about="An attention head that, at a word, looks back to where the same word appeared "
            "before: noticing that Darcy has been mentioned already.",
        ),
        Star(
            key="offset_2",
            name="Two Words Back",
            level=0,
            metric="stars/offset_2/max_score",
            shared_metric="stars/offset_2/shared_score",
            evaluator="stars",
            threshold=0.3,
            about="A positional head that looks two words back, as the previous-word head looks one.",
        ),
        Star(
            key="offset_3",
            name="Three Words Back",
            level=0,
            metric="stars/offset_3/max_score",
            shared_metric="stars/offset_3/shared_score",
            evaluator="stars",
            threshold=0.3,
            about="A positional head that looks three words back.",
        ),
        Star(
            key="attention_sink",
            name="The Sink",
            level=0,
            metric="stars/attention_sink/max_score",
            evaluator="stars",
            threshold=0.5,
            about="A head that parks most of its attention on the window's first token (the opening "
            "end-of-text mark) when it has nothing better to look at: a resting place, not a reading.",
        ),
        Star(
            key="delimiter",
            name="The Delimiter",
            level=0,
            metric="stars/delimiter/max_score",
            evaluator="stars",
            threshold=3.0,
            about="A head that looks at punctuation and line breaks: its attention on them over their "
            "share of the text it can see (1 is indifferent; lit at 3, three times their share).",
        ),
        Star(
            key="rare_word",
            name="The Rare Word",
            level=0,
            metric="stars/rare_word/max_score",
            evaluator="stars",
            threshold=0.3,
            about="A head whose attention follows how rare a word is on the shelf: the correlation "
            "between the attention a word receives and its rarity (-log frequency), -1 to 1.",
        ),
        Star(
            key="comparator",
            name="Comparator",
            level=1,
            metric="stars/comparator/max_score",
            threshold=0.3,
            evaluator="cards",
            shared_metric="stars/comparator/shared_score",
            about="About to name a quantity, it looks back at the quantity it must exceed: on 'begun in 1690, the war lasted "
            "from the year 1732 to the year 17', attention from the last word to 1732 less to the decoy 1690 (the greater-than "
            "heads of GPT-2 small). A card chaining two facts needs for order and the value between.",
        ),
        Star(
            key="mover",
            name="Mover",
            level=2,
            metric="stars/mover/max_score",
            threshold=0.2,
            rests_on=("nevermore",),
            evaluator="cards",
            shared_metric="stars/mover/shared_score",
            about="Carries the answer from where a premise stated it to where it is needed: on the logic deck, "
            "attention from the conclusion's last word to the premise's answer word, less to its rival (the name "
            "movers of GPT-2 small, put to a premise). A card chaining two facts needs.",
        ),
        Star(
            key="bridge",
            name="Bridge",
            level=3,
            metric="stars/bridge/max_score",
            threshold=0.5,
            rests_on=("mover",),
            evaluator="cards",
            about="The middle term two premises share, present where the conclusion is written though it is never "
            "named there: on the logic deck, the logit lens's preference, in the best layer, for the bridge over an "
            "irrelevant middle term (nats; threshold provisional). Found too late in the layers, two-hop reasoning "
            "fails. The card most likely to show chaining forming before the bet is won.",
        ),
        Star(
            key="nevermore",
            name="Nevermore",
            level=1,
            metric="nevermore/natural_max_score",
            threshold=0.3,
            rests_on=("previous_word",),
            evaluator="nevermore",
            about="An induction head: at a word seen before, it looks to the word that followed it "
            "last time, as a reader of Poe's Raven expects 'Nevermore' after 'Quoth the Raven'.",
        ),
    )
}

# --------------------------------------------------------------------------------------- stages


@dataclass(frozen=True)
class Stage:
    """A training stage (Justin, 09:50): one leg of a run's reading, its own shelf and passes, read
    in order with the others under one learning-rate schedule (`data.stages` in a spec; the ledger's
    'stages' artifact gives each its first and last step, and the `stage` metric its index by step).
    A run without stages reads one shelf, a single stage."""

    name: str
    recipe: str
    passes: int


def stages_of(spec: dict) -> list[Stage]:
    d = spec.get("data", {})
    if d.get("stages"):
        return [
            Stage(st.get("name", f"stage {i + 1}"), st["recipe"], st["passes"])
            for i, st in enumerate(d["stages"])
        ]
    return [Stage("reading", d.get("recipe", ""), d.get("passes", 1))]


# --------------------------------------------------------------------------------------- tricks


@dataclass(frozen=True)
class Trick:
    """Something a model can do, measured from outside by what it bets (Justin, 08:10): copying what
    followed last time, knowing Wednesday follows Tuesday. A star is the mechanism inside that does
    a trick, measured by looking at the heads. A trick done with no star found means it is done
    some other way; a star lit with no trick performed is a performer with no act."""

    key: str
    name: str
    metric: str
    threshold: float
    evaluator: str  # "" while the test is not built
    performed_by: tuple[str, ...] = ()  # the stars expected to do it
    about: str = ""
    cutoff: int | None = None  # a discovery test's cutoff year: trained only on English before it
    viable: bool = True  # False when the shelf it needs is not on Gutenberg
    pairs: str = ""  # a discovery test's matched pairs (prompt, idea, rival), when written
    leads_to: str = ""  # the explorer's discovery test this smaller test is the first step towards
    goal_class: str = ""
    # for a test scored on matched pairs: the share of pairs that must also go the idea's way
    # (tricks/<key>/score), so a mean carried by a few pairs does not count (Justin, 10:05)
    min_score: float | None = (
        None  # the class expected to perform it, by class name as in thorp/dash/tricks.py ("speller", "explorer")
    )


# a matched-pairs test is performed when its lift reaches the threshold AND at least this share of
# its pairs go the idea's way: 16 of 24, where chance (one in two) reaches 16 or more about one time in 13
MIN_SHARE = 2 / 3


def performed(key: str, metrics: dict[str, float]) -> bool:
    """Whether a run's latest metrics perform trick `key`: its metric at the threshold and, for a
    matched-pairs test, its share of pairs right at min_score."""
    t = TRICKS[key]
    v = metrics.get(t.metric)
    if v is None or v < t.threshold:
        return False
    if t.min_score is not None:
        share = metrics.get(t.metric.rsplit("/", 1)[0] + "/score")
        return share is not None and share >= t.min_score
    return True


TRICKS: dict[str, Trick] = {
    t.key: t
    for t in (
        Trick(
            key="copying",
            name="Copying",
            metric="nevermore/natural_copy_gain",
            threshold=0.5,
            evaluator="nevermore",
            performed_by=("nevermore", "previous_word"),
            about="Betting that what followed a word last time will follow it again: how much easier the "
            "second copy of a repeated passage is to predict than the first, in nats per token "
            "(lit at half a nat).",
        ),
        Trick(
            key="successor",
            name="The Successor",
            metric="tricks/successor/score",
            threshold=0.5,
            evaluator="successor",
            about="Knowing what comes next in a series: Monday, Tuesday, then Wednesday; January, "
            "February, then March; first, second, then third; Chapter IV, then V. The share of prompts "
            "where the true next item is the model's top bet among the series' items (chance is one in "
            "7 to one in 20). Expected from 21m, where successor heads are first expected; performed at "
            "a smaller class, it is a discovery. Qwen3 0.6B scores 0.71.",
        ),
        Trick(
            key="kin_test",
            name="Like father, like son",
            metric="tricks/kin_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/kin.csv",
            leads_to="pedigree_test",
            goal_class="keel",
            about="The keel's step towards the Origin test: the words of kin and breeding. Like father, like son; a chip off the old block; the mare and her foal; seedtime and harvest. 24 matched pairs of short phrases, lit on the lift and the share.",
        ),
        Trick(
            key="pedigree_test",
            name="The pedigree test",
            metric="tricks/pedigree_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/pedigree.csv",
            leads_to="breeders_test",
            goal_class="pilot",
            about="The pilot's step towards the Origin test: a trait named for the parents comes back in the young. The grey mare and grey stallion have a grey foal; the long-tailed pigeons have long-tailed young. The copying trick, put to inheritance. 24 matched pairs, lit on the lift and the share.",
        ),
        Trick(
            key="fire_test",
            name="Fire and ice",
            metric="tricks/fire_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/fire.csv",
            leads_to="workshop_test",
            goal_class="keel",
            about="The keel's step towards the energy test: the words of heat and motion. As cold as ice, strike while the iron is hot, the steam engine, the mill wheel, the ice began to melt. 24 matched pairs of short phrases, lit on the lift and the share.",
        ),
        Trick(
            key="workshop_test",
            name="The workshop test",
            metric="tricks/workshop_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/workshop.csv",
            leads_to="smiths_test",
            goal_class="pilot",
            about="The pilot's step towards the energy test: what happened to the first thing happens to the second. He rubbed the stick and it grew warm; he rubbed the stone and it grew warm. The copying trick, put to cause and effect. 24 matched pairs, lit on the lift and the share.",
        ),
        Trick(
            key="counting_test",
            name="One, two, three",
            metric="tricks/counting_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/counting.csv",
            leads_to="period_test",
            goal_class="keel",
            about="The keel's step towards Mendeleev's gaps: the words of order. One, two, three; first, second, third; good, better, best; pounds, shillings and pence. 24 matched pairs of short phrases, lit on the lift and the share.",
        ),
        Trick(
            key="period_test",
            name="The period test",
            metric="tricks/period_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/period.csv",
            leads_to="gap_test",
            goal_class="pilot",
            about="The pilot's step towards Mendeleev's gaps: a row that repeats with a period goes on repeating (light, heavy, light, heavy; salt, metal, gas; salt, metal, gas), the periodic law in miniature. The copying trick, put to a period. 24 matched pairs, lit on the lift and the share.",
        ),
        Trick(
            key="breeders_test",
            name="The breeders' test",
            metric="tricks/breeders_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/breeders.csv",
            leads_to="malthus_test",
            goal_class="speller",
            about="The speller's step towards the Origin test: the pieces of natural selection as everyday "
            "knowledge. Keep the largest for seed and the crop grows larger; like begets like; far more "
            "are born than the fields can feed; in a hard winter the weakest perish; the white hare is "
            "hidden in the snow. 24 matched pairs, half of them mirror images, read as the explorer's tests "
            "are (bits per byte in the idea's favour), lit on the lift over what the words alone carry.",
        ),
        Trick(
            key="smiths_test",
            name="The smith's test",
            metric="tricks/smiths_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/smiths.csv",
            leads_to="rumford_test",
            goal_class="speller",
            about="The speller's step towards the energy test: heat from motion and nothing for nothing, as "
            "the workshop knows them. The hammered iron grows hot, an ungreased axle burns, heat passes "
            "from hot to cold, the wheel stops when the stream runs dry, and a wheel that turns for ever "
            "with nothing to drive it cannot be made. 24 matched pairs, lit on the lift.",
        ),
        Trick(
            key="gap_test",
            name="The gap test",
            metric="tricks/gap_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/gaps.csv",
            leads_to="triads_test",
            goal_class="speller",
            about="The speller's step towards Mendeleev's gaps: from a row with one missing, bet on the "
            "missing member and on a value between its neighbours. Monday, Tuesday, then Thursday: "
            "Wednesday is missing, not Friday; the first vessel held one pint and the third three, so the "
            "second held two; lead heavier than iron and iron than wood, so lead heavier than wood. "
            "24 matched pairs, the rival often the next member (continuing, not filling), lit on the lift.",
        ),
        Trick(
            key="nature_test",
            name="Nature's breeder",
            metric="tricks/nature_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/nature.csv",
            leads_to="origin_test",
            goal_class="paragraph",
            about="The 50m's step towards the Origin test: chaining the speller's pieces into a conclusion no single sentence states. The wolves catch the slowest deer, so in time the deer grow swifter; the hawks take the brightest finches, so the finches grow duller; differences that help in the struggle are kept. 24 matched pairs, lit on the lift.",
        ),
        Trick(
            key="mill_test",
            name="The mill test",
            metric="tricks/mill_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/mill.csv",
            leads_to="energy_test",
            goal_class="paragraph",
            about="The 50m's step towards the energy test: following work through its forms. The churned water warms; the engine's work comes from the coal; a clock is paid for by the keeper's winding; a wheel driven by fallen water lifts less than the engine that raised it. 24 matched pairs, lit on the lift.",
        ),
        Trick(
            key="between_test",
            name="The between test",
            metric="tricks/between_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/between.csv",
            leads_to="mendeleev_gaps",
            goal_class="paragraph",
            about="The 50m's step towards Mendeleev's gaps: a member between two others takes a value between theirs, across quantities, orders and qualities (silver between copper and gold in weight; the middle pipe's note between the long and the short). 24 matched pairs, lit on the lift.",
        ),
        Trick(
            key="malthus_test",
            name="Malthus and Lyell",
            metric="tricks/malthus_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/malthus.csv",
            leads_to="nature_test",
            goal_class="stylist",
            about="The stylist's step towards the Origin test: what the precursors wrote, which the Origin test's ablation removes. Population grows geometrically and food arithmetically; the checks of famine, disease and war; valleys cut by running water over immense time; extinct kinds; breeds made by selection. 24 matched pairs in the precursors' register, lit on the lift.",
        ),
        Trick(
            key="rumford_test",
            name="Rumford and Davy",
            metric="tricks/rumford_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/rumford.csv",
            leads_to="mill_test",
            goal_class="stylist",
            about="The stylist's step towards the energy test: what the precursors wrote, which the energy test's ablation removes. Rumford's inexhaustible heat from boring cannon; Davy's ice melted by rubbing; heat as the motion of particles; Young's energy; the fire syringe; Oersted and Faraday. 24 matched pairs in the precursors' register, lit on the lift.",
        ),
        Trick(
            key="triads_test",
            name="Döbereiner's triads",
            metric="tricks/triads_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/triads.csv",
            leads_to="between_test",
            goal_class="stylist",
            about="The stylist's step towards Mendeleev's gaps: what the chemists before 1869 wrote, which the gaps' ablation removes. Dalton's atoms and fixed proportions; the triads, where the middle element's weight is near the mean of its neighbours (lithium, sodium, potassium; calcium, strontium, barium); properties changing by degrees within a family. 24 matched pairs, lit on the lift.",
        ),
        Trick(
            key="again_test",
            name="Again and again",
            metric="tricks/again_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/again.csv",
            leads_to="refrain_test",
            goal_class="keel",
            about="The keel's step towards the eternal return: the words of returning. Again and again, round and round, over and over, time after time, to and fro. 24 matched pairs of short phrases, lit on the lift.",
        ),
        Trick(
            key="refrain_test",
            name="The refrain test",
            metric="tricks/refrain_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/refrain.csv",
            leads_to="seasons_test",
            goal_class="pilot",
            about="The pilot's step towards the eternal return: betting that what came round once comes round again. A refrain, a burden, a watchman's cry or a pattern returns in the passage, against a fresh phrase of the same length. The copying trick, lifted to whole phrases. 24 matched pairs, lit on the lift.",
        ),
        Trick(
            key="seasons_test",
            name="The seasons test",
            metric="tricks/seasons_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/seasons.csv",
            leads_to="lucretius_test",
            goal_class="speller",
            about="The speller's step towards the eternal return: returning as everyday knowledge. Winter comes again, the swallows return, the tide comes in again, Halley's comet is expected back, and the same cause gives the same effect. 24 matched pairs, lit on the lift.",
        ),
        Trick(
            key="pigeonhole_test",
            name="The pigeonhole test",
            metric="tricks/pigeonhole_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/pigeonhole.csv",
            leads_to="recurrence_test",
            goal_class="paragraph",
            about="The 50m's step towards the eternal return: the argument in small. With only so many states and no end of trials, some state must come again (twenty pigeons in nineteen holes, seven throws of a die, a seventh change on three bells); and when all is as it was, what followed follows again. 24 matched pairs, lit on the lift.",
        ),
        Trick(
            key="lucretius_test",
            name="Hume and Lucretius",
            metric="tricks/lucretius_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="discovery",
            pairs="lists/tricks/lucretius.csv",
            leads_to="pigeonhole_test",
            goal_class="stylist",
            about="The stylist's step towards the eternal return: what the books before 1872 wrote, which the test's ablation removes. Lucretius' eternal atoms, Hume's Philo (finite matter in eternal time tries every order an infinite number of times), Ecclesiastes, Marcus Aurelius, the Stoic conflagration, Plato's Great Year, Laplace's periodic disturbances and Thomson's dissipation. 24 matched pairs, lit on the lift.",
        ),
        Trick(
            key="recurrence_test",
            name="The eternal return",
            metric="tricks/recurrence_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="",
            pairs="lists/discovery-recurrence.csv",
            goal_class="explorer",
            cutoff=1872,
            about="The explorer's philosophy test (Nietzsche's idea, found independently by Blanqui in 1872, Nietzsche in 1881 and, "
            "as a theorem of mechanics, Poincare in 1890). Trained only on English before 1872, does it prefer 'if the world is "
            "made of a finite number of parts and time has no end, every state of the world, this one included, returns, exactly "
            "and endlessly' over the world running down once to a final stillness (Thomson's dissipation, the strongest rival on the "
            "shelf), the world progressing for ever to new states, return in kind but never in detail, and a creation with a final end? "
            "Ablation: without Hume's Dialogues and Lucretius.",
        ),
        Trick(
            key="logic_test",
            name="The logic deck",
            metric="tricks/logic_test/gain",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="logic",
            pairs="lists/tricks/logic.csv",
            goal_class="paragraph",
            performed_by=("nevermore", "mover", "bridge"),
            about="Chaining two facts proved: invented words and counterfactual premises, so no knowledge helps, "
            "both answers in the premises, so copying cannot decide, and every item asked with both premises, "
            "with one, swapped, padded, and at one, two and three hops. The chaining gain is the lift with both "
            "premises less the better single premise: only a positive gain is the trick. 40 items across order, "
            "cause, membership, proportion and counterfactual.",
        ),
        Trick(
            key="crowns_test",
            name="The crowns",
            metric="tricks/crowns_test/gain",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="crowns",
            pairs="lists/tricks/crowns.csv",
            goal_class="paragraph",
            performed_by=("nevermore", "mover", "bridge"),
            about="Who is the king depends on who asks (Justin, 2026-11-08: the Queen of England by time, kingdom, side "
            "and station). An invented kingdom with two claimants; one premise gives the record, the other the asker's "
            "standpoint (side, time, place or station), and only both answer 'So to Pim, the king of Brell is'. The "
            "chaining gain as the logic deck's, in its own deck; 'moves' asks that the answer turn when the standpoint "
            "does, and 'ask' whether a disputed record raises 'That depends on whom you ask.' 40 items, ten a kind.",
        ),
        Trick(
            key="origin_test",
            name="The Origin test",
            metric="tricks/origin_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="",
            pairs="lists/discovery-origin.csv",
            goal_class="explorer",
            cutoff=1859,
            about="Trained only on English before 1859, does the explorer prefer natural selection over fixed "
            "species, Lamarckian inheritance and special creation? Ablation: without Malthus and Erasmus Darwin.",
        ),
        Trick(
            key="energy_test",
            name="The energy test",
            metric="tricks/energy_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="",
            pairs="lists/discovery-energy.csv",
            goal_class="explorer",
            cutoff=1840,
            about="Trained only on English before 1840, does it prefer heat as motion and energy conserved "
            "over caloric and perpetual motion (found by Mayer, Joule and Helmholtz, 1842 to 1847)? "
            "Ablation: without Rumford and Davy.",
        ),
        Trick(
            key="mendeleev_gaps",
            name="Mendeleev's gaps",
            metric="tricks/mendeleev_gaps/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="",
            pairs="lists/discovery-mendeleev.csv",
            goal_class="explorer",
            cutoff=1869,
            about="Trained only on English before 1869, does it bet on the missing elements below "
            "aluminium, after calcium and below silicon, and their weights (gallium, scandium, germanium, "
            "found 1875 to 1886)? Ablation: without Dalton and Davy.",
        ),
        Trick(
            key="geometry_test",
            name="The geometry test",
            metric="tricks/geometry_test/lift",
            threshold=0.1,
            min_score=MIN_SHARE,
            evaluator="",
            pairs="lists/discovery-geometry.csv",
            goal_class="explorer",
            cutoff=1829,
            about="Trained only on English before 1829, does it prefer a consistent geometry where the parallel "
            "postulate fails (Gauss, Bolyai, Lobachevsky) over 'the postulate can be proven from the others'? "
            "Made viable by the Internet Archive: Legendre's Elements in English (1822, 1825) with his "
            "attempted proofs, and Playfair's (1795, 1826). Ablation: without Legendre.",
        ),
    )
}


@dataclass(frozen=True)
class Rung:
    """One class's place on the four discovery chains (Justin, 10:05): what a model of that class is,
    according to its four tests, one per chain (the Origin test, the energy test, Mendeleev's gaps,
    the eternal return). `goal_class` is a Trick.goal_class; the tests are the chain tricks with it."""

    goal_class: str
    title: str
    summary: str


RUNGS: tuple[Rung, ...] = (
    Rung(
        "keel",
        "Knows which words go together",
        "The words of each idea: kin and breeding (like father, like son), heat and motion (strike while the "
        "iron is hot), order (one, two, three) and returning (again and again).",
    ),
    Rung(
        "pilot",
        "Copies what came before",
        "The copying trick put to each idea: a trait named for the parents comes back in the young, what "
        "happened to the first thing happens to the second, a period goes on repeating, a refrain comes round again.",
    ),
    Rung(
        "speller",
        "Knows the everyday world",
        "Each idea's pieces as common knowledge: keep the largest for seed and the crop grows larger, the "
        "hammered iron grows hot, Wednesday is missing between Tuesday and Thursday, the swallows return in spring.",
    ),
    Rung(
        "stylist",
        "Knows what the precursors wrote",
        "The books each discovery test's ablation removes: Malthus and Lyell, Rumford and Davy, Dalton and "
        "Doebereiner's triads, Hume and Lucretius.",
    ),
    Rung(
        "paragraph",
        "Chains two facts into a third",
        "Conclusions no single sentence states: the wolves take the slowest so the deer grow swifter, the engine's "
        "work comes from the coal, the middle member takes the middle value, twenty pigeons in nineteen holes.",
    ),
    Rung(
        "explorer",
        "Bets on the idea before it was found",
        "Trained only on what was written before each cutoff, prefers natural selection (1859), energy conserved "
        "and heat as motion (1840), the missing elements (1869) and the eternal return (1872) over their rivals.",
    ),
)


@dataclass(frozen=True)
class Chain:
    """One of the explorer's discovery tests, told as a climb (Justin, 10:05): the idea, who found it,
    and for each rung (a trick key, keel to explorer) what that step adds to the one below."""

    key: str  # the explorer's test (a TRICKS key)
    name: str
    strand: str
    idea: str
    found: str
    shelf: str
    steps: dict[str, str]


CHAINS: dict[str, Chain] = {
    c.key: c
    for c in (
        Chain(
            key="origin_test",
            name="The Origin test",
            strand="reasoning",
            idea="Species change because more are born than can live, the young differ, the differences are "
            "inherited, and those best suited to their place survive and leave the most young: natural selection.",
            found="Charles Darwin and Alfred Russel Wallace, independently; their papers were read together in "
            "1858, and On the Origin of Species followed in 1859.",
            shelf="All English before 1859; its precursors Malthus, Erasmus Darwin, Cuvier, Lyell and the breeders.",
            steps={
                "kin_test": "First the words. A model that cannot tell 'like father, like son' from 'like father, "
                "like mother' has nothing to build on: inheritance begins as words that go together.",
                "pedigree_test": "Then the copying trick, put to inheritance: the parents' trait, named earlier in "
                "the passage, is bet on for the young. Heredity as copying.",
                "breeders_test": "Then the pieces as everyday knowledge: the breeder chooses and the stock changes, "
                "like begets like, far more are born than can live, the weakest perish in a hard winter.",
                "malthus_test": "Then what the precursors wrote, the books Darwin and Wallace each read: Malthus' "
                "ratios and checks, Lyell's slow causes over immense time, extinction, breeds made by selection. "
                "The ablation takes these away.",
                "nature_test": "Then the pieces chained with no breeder at all: the wolves take the slowest deer, "
                "so the deer grow swifter. A conclusion no single sentence states, which is the theory in small.",
                "origin_test": "Finally the bet. Trained only on what was written before 1859, does it prefer natural "
                "selection over fixed species, Lamarckian inheritance and special creation?",
            },
        ),
        Chain(
            key="energy_test",
            name="The energy test",
            strand="physics",
            idea="Heat is a motion, not a substance; and energy is neither made nor lost but turns from one form "
            "into another (motion, heat, chemical, electric), so no engine can run on nothing.",
            found="Julius Robert Mayer (1842), James Prescott Joule (1843 to 1847) and Hermann von Helmholtz (1847), "
            "independently.",
            shelf="All English before 1840; its precursors Rumford, Davy, Young, Black and the engineers of steam.",
            steps={
                "fire_test": "First the words of heat and motion: as cold as ice, strike while the iron is hot, the "
                "steam engine, the mill wheel.",
                "workshop_test": "Then the copying trick, put to cause and effect: he rubbed the stick and it grew "
                "warm; he rubbed the stone, and the model bets it grew warm too.",
                "smiths_test": "Then the pieces as the workshop knows them: hammered iron grows hot, heat passes "
                "from hot to cold, the wheel stops when the stream runs dry, a wheel that turns for ever with "
                "nothing to drive it cannot be made.",
                "rumford_test": "Then what the precursors wrote: Rumford's endless heat from boring cannon, Davy's "
                "ice melted by rubbing, Young's 'energy', the fire syringe, Oersted and Faraday. The ablation takes "
                "these away.",
                "mill_test": "Then work followed through its forms: the churned water warms, the engine's work comes "
                "from the coal, water lifted and let fall lifts less again. The conservation of energy in small.",
                "energy_test": "Finally the bet. Trained only on what was written before 1840, does it prefer heat as "
                "motion and energy conserved over caloric, the weightless fluid of heat, and perpetual motion?",
            },
        ),
        Chain(
            key="mendeleev_gaps",
            name="Mendeleev's gaps",
            strand="mathematics",
            idea="Set the elements in order of atomic weight and their properties repeat in periods; where the "
            "pattern breaks, an element is missing, and its weight and properties can be foretold from its "
            "neighbours.",
            found="Dmitri Mendeleev (1869, the gaps foretold in 1871), with Lothar Meyer's periodic table (1864 to "
            "1870) and Newlands' octaves (1865) found independently; gallium (1875), scandium (1879) and "
            "germanium (1886) filled the gaps.",
            shelf="All English before 1869; its precursors Dalton, Davy, Faraday and Doebereiner's triads.",
            steps={
                "counting_test": "First the words of order: one, two, three; first, second, third; good, better, best.",
                "period_test": "Then the copying trick, put to a period: light, heavy, light, heavy goes on repeating. "
                "The periodic law in miniature.",
                "gap_test": "Then the gap: Monday, Tuesday, then Thursday, so Wednesday is missing, not Friday. "
                "Filling, not continuing; the failure the small models show is to bet on the next member.",
                "triads_test": "Then what the chemists wrote: Dalton's atoms and fixed proportions, Doebereiner's "
                "triads (sodium's weight near the mean of lithium's and potassium's), properties changing by "
                "degrees within a family. The ablation takes these away.",
                "between_test": "Then the value between: the middle member takes a value between its neighbours', "
                "across weights, ages, heights and notes. Mendeleev's method in small.",
                "mendeleev_gaps": "Finally the bet. Trained only on what was written before 1869, does it bet on the "
                "missing elements below aluminium, after calcium and below silicon, at about the right weights?",
            },
        ),
        Chain(
            key="recurrence_test",
            name="The eternal return",
            strand="philosophy",
            idea="If the world is made of a finite number of parts and time has no end, every state of the world, "
            "this moment included, must come again, exactly and endlessly.",
            found="Louis Auguste Blanqui (1872), Friedrich Nietzsche (1881) and, as a theorem of mechanics, Henri "
            "Poincare (1890), independently.",
            shelf="All English before 1872; its precursors Hume's Dialogues, Lucretius, Marcus Aurelius and "
            "Ecclesiastes, with Thomson's running-down of the world as the rival.",
            steps={
                "again_test": "First the words of returning: again and again, round and round, over and over, to and fro.",
                "refrain_test": "Then the copying trick, put to whole phrases: a refrain that came round once comes "
                "round again.",
                "seasons_test": "Then returning as everyday knowledge: winter comes again, the swallows return, "
                "Halley's comet is expected back, and the same cause gives the same effect.",
                "lucretius_test": "Then what the precursors wrote: Lucretius' eternal atoms, Philo's argument in "
                "Hume that finite matter in eternal time tries every order an infinite number of times, the Stoic "
                "conflagration, the Great Year, and Thomson's dissipation on the other side. The ablation takes "
                "Hume and Lucretius away.",
                "pigeonhole_test": "Then the argument in small: with only so many states and no end of trials, some "
                "state must come again (twenty pigeons in nineteen holes), and when all is as it was, what followed "
                "follows again.",
                "recurrence_test": "Finally the bet. Trained only on what was written before 1872, does it prefer the "
                "eternal return over the world running down once to stillness, endless progress to new states, "
                "return in kind but not in detail, and a creation with a final end?",
            },
        ),
    )
}


# the reference ladder for grading the chains (Justin, 10:10: "each test must get harder as it moves up
# the classes"): one model family in graded sizes, trained on modern text, so it measures how hard a
# test is, never what a Nothing up my sleeve class should score; Qwen3 0.6B, 1.7B and 4B on top (the 4B shows a
# rung is within reach: a pair it gets wrong is mended, not kept as hard)
REFERENCE_LADDER = (
    "EleutherAI/pythia-14m",
    "EleutherAI/pythia-31m",
    "EleutherAI/pythia-70m",
    "EleutherAI/pythia-160m",
    "EleutherAI/pythia-410m",
    "Qwen/Qwen3-0.6B",
    "mlx-community/Qwen3-1.7B-4bit",
    "mlx-community/Qwen3-4B-4bit",
)


# the perch (Justin, 11:15: "it should be smoking that size range and not only Qwen"): the outside
# models of 2B to 4B that Nothing up my sleeve must match at a tenth of their size; scored on the same pairs as the
# reference ladder, but never used to grade the chains (they are the opponents, not the ruler)
COMPETITORS: dict[str, tuple[str, float]] = {
    # model: (label, total parameters)
    "mlx-community/Qwen3-4B-4bit": ("Qwen3 4B", 4.0e9),
    "microsoft/phi-2": ("Phi-2", 2.7e9),
    "mlx-community/Phi-4-mini-instruct-4bit": ("Phi-4-mini", 3.8e9),
    "mlx-community/Llama-3.2-3B-bf16": ("Llama 3.2 3B", 3.2e9),
    "mlx-community/gemma-2-2b": ("Gemma 2 2B", 2.6e9),
    "mlx-community/gemma-3-text-4b-pt-4bit": ("Gemma 3 4B", 3.9e9),
    "mlx-community/SmolLM3-3B-Base-4bit": ("SmolLM3 3B", 3.1e9),
}


def grading(chain: list[str], passed: dict[str, set[str]]) -> dict:
    """Whether a chain gets harder as it climbs, judged on many models at once. `passed` maps each
    model to the rungs it performs. The rule, for the rungs below the explorer's (whose pairs come later):
    no model performs a rung while failing one below it (each model's passes are a run from the
    bottom); fewer models perform each rung than the one below or the same number (never more); and
    some model performs every rung, so none is beyond reach. Returns the breaches."""
    rungs = [k for k in chain if TRICKS[k].evaluator == "discovery"]
    inversions = []
    for model, got in passed.items():
        for i, k in enumerate(rungs):
            below = [b for b in rungs[:i] if b not in got]
            if k in got and below:
                inversions.append({"model": model, "rung": k, "fails_below": below})
    counts = [sum(k in got for got in passed.values()) for k in rungs]
    rising = [rungs[i + 1] for i in range(len(rungs) - 1) if counts[i + 1] > counts[i]]
    unreached = [k for k, n in zip(rungs, counts, strict=True) if n == 0]
    return {
        "graded": not inversions and not rising and not unreached,
        "counts": dict(zip(rungs, counts, strict=True)),
        "inversions": inversions,
        "rising": rising,
        "unreached": unreached,
    }


@dataclass(frozen=True)
class Method:
    """How a trick is tested, part by part (Justin, 11:45: "put that logic in the UI under the
    methodology for chaining two facts"): what the trick is, the parts it breaks into and whether the
    tests cover each, the gaps, the planned controls, and the cards (stars: heads that do one
    operation, shown pulsing when lit) the trick needs."""

    key: str
    name: str
    trick: str
    parts: tuple[tuple[str, str, str], ...]  # (part, what it means, covered: yes | partly | no)
    gaps: tuple[str, ...]
    controls: tuple[tuple[str, str], ...]  # (control, what it does)
    metric: str
    cards: tuple[tuple[str, str, str], ...]  # (card, its operation, status: in the deck | planned)
    status: str


METHODS: dict[str, Method] = {
    m.key: m
    for m in (
        Method(
            key="chaining",
            name="Chaining two facts",
            trick="Two premises chained into a conclusion neither states alone: A leads to B, and B leads to C, "
            "so A leads to C. Measured on the four chaining tests (the 50m rung of each discovery chain), and to "
            "be proved on the logic deck.",
            parts=(
                ("Hold both premises", "retrieve facts stated earlier in the passage", "partly"),
                ("Find the bridge", "the term the two premises share (the slowest deer)", "no"),
                (
                    "Apply the relation",
                    "order (A above B above C), cause (X makes Y makes Z), proportion (twice as far, "
                    "twice as much), counting (pigeonholes)",
                    "yes",
                ),
                (
                    "Track direction and polarity",
                    "more against less, survive against perish",
                    "partly",
                ),
                ("Use both facts, not one", "the answer needs the two premises together", "no"),
                (
                    "Follow the premises, not what is known",
                    "reason from what is stated, even against prior knowledge",
                    "no",
                ),
            ),
            gaps=(
                "A model can pass from knowledge alone (it may already know that hunted deer grow swift): that is "
                "knowing, not chaining.",
                "A model can pass from one premise alone: nothing yet checks that both were used.",
                "The four tests mix the kinds of relation with their subjects, so a failure does not say which part failed.",
            ),
            controls=(
                (
                    "Nonce words",
                    "invented terms, so no knowledge helps: every glimmet is heavier than a dornal, every "
                    "dornal heavier than a fesk, so a glimmet is heavier (not lighter) than a fesk",
                ),
                (
                    "Counterfactual premises",
                    "premises against the world, so the model must follow what is stated: where "
                    "the wolves catch the fastest deer, the deer grow slower",
                ),
                (
                    "Single-premise variants",
                    "the same item with only the first premise, and only the second",
                ),
                (
                    "Swapped and padded variants",
                    "the premises in the other order; an irrelevant third fact added",
                ),
                (
                    "One, two and three hops",
                    "a one-hop floor and a three-hop ceiling around the two-hop items",
                ),
                (
                    "Every kind of relation",
                    "order, cause, proportion, set membership, counting, each reported apart",
                ),
            ),
            metric="Chaining gain: the lift with both premises less the better of the two single-premise lifts, on the "
            "logic deck; only a positive gain shows the two facts were used together. Proposed as the leaderboard's "
            "headline beside the four chaining tests.",
            cards=(
                (
                    "Previous-word",
                    "attends from each word to the one before it, the first step of copying",
                    "in the deck",
                ),
                (
                    "Nevermore (induction)",
                    "finds an earlier occurrence and copies what followed it: retrieves the premises",
                    "in the deck",
                ),
                (
                    "Mover",
                    "carries a fact's attribute from where it was stated to where it is needed (the name movers of the "
                    "indirect-object circuit in GPT-2 small)",
                    "in the deck",
                ),
                (
                    "Bridge",
                    "the shared middle term present at the answer's position in the middle layers, read by the "
                    "soundings; resolving it too late is how two-hop reasoning fails",
                    "in the deck",
                ),
                (
                    "Comparator",
                    "orders two quantities (the greater-than heads of GPT-2 small): for the between and "
                    "order items",
                    "in the deck",
                ),
            ),
            status="the four chaining tests, the logic deck (40 items, 232 rows) and the three new cards are built",
        ),
    )
}


@dataclass(frozen=True)
class FitoutStage:
    """One stage of a fitout: what is read, how often, and why (Justin, 13:15)."""

    name: str
    shelf: str  # a list in lists/
    passes: int
    purpose: str
    lr: float | None = None  # None: the class's own
    tack: dict | None = (
        None  # optim.copy_weight for this stage, e.g. {"alpha": 3, "kind": "conclusion"}
    )


@dataclass(frozen=True)
class Fitout:
    """A hand-curated fitout: the training material matched to pretraining (in stages, one run under
    one schedule) and post-training (in stages, each a run seeded from the one before) for a class and
    an aim. `scripts/make_fitout.py <key>` compiles it into specs; the Shelves tab shows it beside the
    shelves it reads. Not to be confused with fitout_of(), a ship's identity: a Fitout is a plan, and
    each run it compiles to is a ship."""

    key: str
    name: str
    preset: str
    aim: str
    positions: str
    vocab: int
    tack: dict | None  # the pretraining tack
    pretraining: tuple[FitoutStage, ...]
    posttraining: tuple[FitoutStage, ...]
    # the cleaning version it reads (thorp/cleaning.py; S5 policy 'clean'): a new fitout reads the
    # current one; the two four-cards fitouts were compiled on raw text before the rule, and stay raw
    clean: str = "unwrap-v1"


FITOUTS: dict[str, Fitout] = {
    f.key: f
    for f in (
        Fitout(
            key="keel-cards-cause",
            clean="raw",
            name="Nothing up my sleeve 300k: the four cards, leaning on cause and effect",
            preset=NURSERY,
            aim="Draw the four necessary cards (previous-word, the Nevermore, the mover, the comparator) at 300k, "
            "and lean the reading excessively towards cause and effect, the form of chaining Qwen3 4B performs "
            "on invented words (logic deck: cause +0.94, every other relation near zero).",
            positions="rope",
            vocab=2048,
            tack={"alpha": 3, "kind": "induction"},
            pretraining=(
                FitoutStage(
                    "nursery",
                    "lists/keel-nursery.csv",
                    2,
                    "short sentences and nursery rhymes: previous-word, and the repetition a Nevermore forms on",
                ),
                FitoutStage(
                    "verse",
                    "lists/stars-verse.csv",
                    2,
                    "refrains and repeated lines: the Nevermore",
                ),
                FitoutStage(
                    "fiction",
                    "lists/stars-fiction.csv",
                    2,
                    "running English prose: the reading every class shares",
                ),
                FitoutStage(
                    "cause",
                    "lists/cause-shelf.csv",
                    3,
                    "how-to books, step after step: when X, then Y",
                ),
            ),
            posttraining=(
                FitoutStage(
                    "reasoning",
                    "lists/reasoning-shelf.csv",
                    2,
                    "argument and proof: the mover carries a premise to its conclusion, the comparator orders "
                    "quantities",
                    lr=0.001,
                    tack={"alpha": 3, "kind": "conclusion"},
                ),
                FitoutStage(
                    "cause again",
                    "lists/cause-shelf.csv",
                    2,
                    "cause and effect, last and heaviest",
                    lr=0.001,
                    tack={"alpha": 3, "kind": "conclusion"},
                ),
            ),
        ),
        Fitout(
            key="pilot-cards-cause",
            clean="raw",
            name="Nothing up my sleeve 1m: the four cards, leaning on cause and effect",
            preset=PROXY,
            aim="The keel's fitout one class up (the same stages, shelves and tacks; the pilot's vocabulary and "
            "learning rate), so the two classes' card censuses compare stage for stage.",
            positions="rope",
            vocab=4096,
            tack={"alpha": 3, "kind": "induction"},
            pretraining=(
                FitoutStage(
                    "nursery",
                    "lists/keel-nursery.csv",
                    2,
                    "short sentences and nursery rhymes: previous-word, and the repetition a Nevermore forms on",
                ),
                FitoutStage(
                    "verse",
                    "lists/stars-verse.csv",
                    2,
                    "refrains and repeated lines: the Nevermore",
                ),
                FitoutStage(
                    "fiction",
                    "lists/stars-fiction.csv",
                    2,
                    "running English prose: the reading every class shares",
                ),
                FitoutStage(
                    "cause",
                    "lists/cause-shelf.csv",
                    3,
                    "how-to books, step after step: when X, then Y",
                ),
            ),
            posttraining=(
                FitoutStage(
                    "reasoning",
                    "lists/reasoning-shelf.csv",
                    2,
                    "argument and proof: the mover carries a premise to its conclusion, the comparator orders "
                    "quantities",
                    lr=0.0007,
                    tack={"alpha": 3, "kind": "conclusion"},
                ),
                FitoutStage(
                    "cause again",
                    "lists/cause-shelf.csv",
                    2,
                    "cause and effect, last and heaviest",
                    lr=0.0007,
                    tack={"alpha": 3, "kind": "conclusion"},
                ),
            ),
        ),
    )
}


def chains() -> list[list[str]]:
    """The discovery chains, each from its first rung to the explorer's test it leads to."""
    led = {t.leads_to for t in TRICKS.values() if t.leads_to}
    out = []
    for k, t in TRICKS.items():
        if t.leads_to and k not in led:
            c = [k]
            while TRICKS[c[-1]].leads_to:
                c.append(TRICKS[c[-1]].leads_to)
            out.append(c)
    return out


# --------------------------------------------------------------------------------------- sieves


@dataclass(frozen=True)
class Sieve:
    """A per-layer measurement of training itself, in the dashboard's words: the wind is the error on
    each guess, a tack is one training update (its direction from the wind, its size from the
    learning rate), trim is how the tack is set, and the sieves are how hard the wind pushes each
    layer (Push) and how far its sail actually moves (Move). Recorded every 50 steps for each parameter group
    (`tok`, `pos`, `layer_i`, `layer_i/attn`, `layer_i/mlp`), and the kink found in it: the step where
    a layer changes regime, the least-squares break of a two-line fit to log10 of the series from the
    learning-rate peak, firm after KINK_MIN_RECORDS records when the two-line fit removes at least
    KINK_FIRM of the one-line residual. Comparing a layer's kink step with the step a star lights in
    that layer asks whether the layer changed regime because it grew the star."""

    key: str
    name: str
    metric_prefix: str  # ledger metrics are <prefix><group>, e.g. grad_norm/layer_3
    about: str


KINK_MIN_RECORDS = 10
KINK_FIRM = 0.25

SIEVES: dict[str, Sieve] = {
    s.key: s
    for s in (
        Sieve(
            "push",
            "Push",
            "grad_norm/",
            "How hard the wind pushes each layer: the size of the error signal reaching it on each "
            "tack (the pre-clip gradient norm). A layer pushed hard is being asked to change; a layer "
            "whose push falls away is no longer where the errors are. Read it on a log scale.",
        ),
        Sieve(
            "move",
            "Move",
            "update_ratio/",
            "How far each layer's sail actually moves: the change in its weights over the last 50 "
            "steps, as a share of their size. The push is the wind; the move is what the layer did "
            "with it after the learning rate and the optimiser had their say.",
        ),
        Sieve(
            "heading",
            "Heading",
            "heading/",
            "Which way each layer is steering: the cosine between its move over the last 50 steps "
            "and its move over the 50 before. Near 1 the tacks keep one angle: the layer has found "
            "its heading and is refining it. Near 0 they wander. Below 0 the layer is coming about, "
            "undoing what it just did. A layer whose heading settles early, low in the stack, is a "
            "foundation the rest can build on (Justin's 'fix the angle of the tack as low down the "
            "stack as possible').",
        ),
    )
}


# ------------------------------------------------------------------------------------ soundings


@dataclass(frozen=True)
class Sounding:
    """A measurement of reading, taken at every depth of the stack (thorp/evaluators/soundings.py):
    what each layer does to a passage on its way up. The sieves measure training; soundings measure
    the data's journey through the trained layers."""

    key: str
    name: str
    metric: str  # with {i} for the layer: soundings/layer_{i}/<key>
    about: str


SOUNDINGS: dict[str, Sounding] = {
    s.key: s
    for s in (
        Sounding(
            "bpb",
            "Guess at this depth",
            "soundings/layer_{i}/bpb",
            "The guess the model would make if it stopped here, in bits per byte on the next piece "
            "(layer 0 is the embeddings alone; the last is the model's own score). How much a layer "
            "lowers it is how much that layer adds to the guess.",
        ),
        Sounding(
            "attn_write",
            "Attention write",
            "soundings/layer_{i}/attn_write",
            "How hard the layer's attention half writes into the stream: its contribution over the "
            "size of the stream it read.",
        ),
        Sounding(
            "attn_turn",
            "Attention turn",
            "soundings/layer_{i}/attn_turn",
            "Which way the attention half writes: 0 pushes the stream further the way it already "
            "points, 1 writes at right angles (something new), 2 pushes it back.",
        ),
        Sounding(
            "mlp_write",
            "Feed-forward write",
            "soundings/layer_{i}/mlp_write",
            "How hard the layer's feed-forward half writes into the stream, over the size of the "
            "stream it read.",
        ),
        Sounding(
            "mlp_turn",
            "Feed-forward turn",
            "soundings/layer_{i}/mlp_turn",
            "Which way the feed-forward half writes: 0 along the stream, 1 across it, 2 against it.",
        ),
    )
}


# ------------------------------------------------------------------------- classes and fitouts



# what a ship is fitted out with: the spec less its size (the class), its luck (the seed), its
# instruments (eval, checkpoint) and its labels (name, ship, experiment, question). Two specs with
# the same fitout and class are the same ship; their runs are its sailings.
FITOUT_DATA = ("recipe", "passes", "order", "first", "first_repeats", "stages")
FITOUT_TOKENISER = ("kind", "vocab", "byte_fallback", "train_on")


def _list_identity(path: str | None) -> str | None:
    """A list's content hash, so a shelf is known by its books, not only its file name."""
    if not path:
        return path
    import hashlib

    from thorp import paths

    p = paths.resolve(path)
    return f"{path}#{hashlib.sha1(p.read_bytes()).hexdigest()[:10]}" if p.exists() else path


def named_fitout(key: str | None) -> str | None:
    """A fitout's name, hand-curated (FITOUTS) or made in the UI (data/fitouts/<key>.json); None if no
    such fitout exists."""
    if not key:
        return None
    if key in FITOUTS:
        return FITOUTS[key].name
    from thorp import fitouts

    saved = fitouts.load(key)
    return (saved or {}).get("name") if saved else None


def assign_fitout(spec: dict) -> dict:
    """The named fitout a voyage is a variation of (S5 policy 'fitout', Justin 2026-11-07 18:10: "no run
    occurs without a named fitout"), as {"key", "variation"}. A spec that names one keeps it; a voyage
    compiled from a fitout (its experiment reads "Fitout <key>: ...") is that fitout, its census variation
    from the name's "~<variation>"; every other voyage is a variation of one of the two four-cards fitouts
    (Justin: "align them with the 2 fitouts we currently have and just variations of those 2"): the
    keel's (keel-cards-cause) for the 300k, the pilot's (pilot-cards-cause) for the 1m and up, the
    variation its own name less the seed. The generators write it into each spec; the gate only reads it."""
    import re

    have = spec.get("fitout")
    if isinstance(have, dict) and have.get("key"):
        return {"key": have["key"], "variation": have.get("variation")}
    name = spec.get("name") or ""
    m = re.match(r"Fitout ([\w.-]+):", spec.get("experiment") or "")
    if m:
        var = re.search(r"~(.+?)-(?:pre|post\d+)-s\d+$", name)
        return {"key": m.group(1), "variation": var.group(1) if var else None}
    preset = ((spec.get("model") or {}).get("preset") or "").split("-")[0]
    key = "keel-cards-cause" if preset == FITOUTS["keel-cards-cause"].preset else "pilot-cards-cause"
    return {"key": key, "variation": re.sub(r"-(?:s|seed)\d+$", "", name) or None}


def with_fitout(spec: dict) -> dict:
    """The spec with its named fitout written in (assign_fitout), for the spec generators."""
    return {**spec, "fitout": assign_fitout(spec)}


def fitout_of(spec: dict) -> dict:
    d, t, m = spec.get("data", {}), spec.get("tokeniser", {}), spec.get("model", {})
    out = {
        "data": {k: d[k] for k in FITOUT_DATA if k in d},
        "tokeniser": {k: t[k] for k in FITOUT_TOKENISER if k in t},
        "context": m.get("context"),
        "optim": dict(spec.get("optim", {})),
        "seeded_from": spec.get("seeded_from"),
    }
    # fields added after ships were registered count only when set, so an older ship's key never
    # moves (07:20 to 08:15 on 7 November an always-present "transplant": null moved every key)
    if spec.get("transplant"):
        out["transplant"] = spec["transplant"]
    if spec.get("model", {}).get("positions", "learned") != "learned":  # rotary positions, round 2
        out["positions"] = spec["model"]["positions"]
    for k in ("recipe", "first"):
        if k in out["data"]:
            out["data"][k] = _list_identity(out["data"][k])
    if "stages" in out["data"]:  # each stage's shelf is known by its books too
        out["data"]["stages"] = [
            {**st, "recipe": _list_identity(st.get("recipe"))} for st in out["data"]["stages"]
        ]
    if out["tokeniser"].get("train_on") not in (None, "recipe"):
        out["tokeniser"]["train_on"] = _list_identity(out["tokeniser"]["train_on"])
    return out


def fitout_id(spec: dict) -> str:
    import hashlib
    import json

    return hashlib.sha1(json.dumps(fitout_of(spec), sort_keys=True).encode()).hexdigest()[:12]


def ship_key(spec: dict) -> str:
    return f"{spec.get('model', {}).get('preset')}:{fitout_id(spec)}"


def describe(spec: dict) -> str:
    """The fitout in a line, the ship's subtitle: 1m · stars-fiction · 4,096 · x2 · lr 2e-3."""
    d, t, o = spec.get("data", {}), spec.get("tokeniser", {}), spec.get("optim", {})
    shelf = str(d.get("recipe", "")).split("/")[-1].removesuffix(".csv")
    bits = [
        str(spec.get("model", {}).get("preset")),
        shelf,
        f"{t.get('vocab', 0):,}",
        f"x{d.get('passes')}",
        f"lr {o.get('lr'):g}",
    ]
    if d.get("first"):
        bits.append(
            f"first {str(d['first']).split('/')[-1].removesuffix('.csv')} x{d.get('first_repeats', 1)}"
        )
    cw = o.get("copy_weight") or {}
    if cw.get("alpha"):
        bits.append(f"copy-weighted x{cw['alpha']} ({cw.get('kind', 'induction')})")
    tp = spec.get("transplant")
    if tp:
        bits.append(f"{tp.get('star', 'previous_word')} heads from {tp['from_run']}")
    sf = spec.get("seeded_from")
    if sf:
        sf = sf if isinstance(sf, dict) else {"run": sf}
        scale = f" x{sf['lr_scale']}" if sf.get("mode") == "slow" else ""
        bits.append(f"seeded from {sf['run']} ({sf.get('mode', 'free')}{scale})")
    return " · ".join(bits)


# ---------------------------------------------------------------------------------------- ships


@dataclass(frozen=True)
class Ship:
    """A ship: a size fitted out one way (its training content and method, the fitout). Its runs are its
    voyages, one per seed. Named once, when first registered, and never renamed. Registered in Postgres
    (`s1.ships`, thorp/ship_store.py)."""

    key: str  # "<preset>:<fitout id>"
    name: str
    preset: str  # its exact shape: a size, or a variant of one (300k-h4)
    size: str  # the size it belongs to (300k)
    subtitle: str  # the fitout in a line
    archived: bool = False  # the First Fleet: ships fitted out before 7 November 06:40
    status: str = "in service"  # or "retired": pruned from the lists, kept in the store (ship_store.retire)
    retired_note: str | None = None
    seeded_from: dict | str | None = None  # the run whose trained mind it starts from (Great Expectations)
    expedition: str | None = None  # the expedition that commissioned it, if any


def _ship(rec) -> Ship:
    return Ship(
        key=rec.key,
        name=rec.name,
        preset=rec.preset,
        size=rec.size,
        subtitle=rec.subtitle,
        archived=rec.archived,
        status=rec.status,
        retired_note=rec.retired_note,
        seeded_from=rec.seeded_from,
        expedition=rec.expedition,
    )


_REGISTER: tuple[float, dict[str, Ship]] | None = None


def register(fresh: bool = False) -> dict[str, Ship]:
    """Every ship registered so far, by key (Postgres, `s1.ships`; kept half a minute, as the dashboard
    asks for a run's ship once per run)."""
    import time

    global _REGISTER
    if fresh or _REGISTER is None or time.time() - _REGISTER[0] > 30:
        from thorp import ship_store

        _REGISTER = (time.time(), {r.key: _ship(r) for r in ship_store.ships()})
    return _REGISTER[1]


def clean_name(label: str | None) -> str:
    """A run's ship label less its seed marks: 'Argo II' and 'Smaller Pieces, Rolled Again' are their
    first sailing's ship."""
    import re

    n = (label or "").strip()
    n = re.sub(r"\s*\((seed \d+)\)$", "", n)
    n = re.sub(r",\s*(Rolled Again|Third Roll)$", "", n)
    n = re.sub(r"\s+II$", "", n)
    return n


def ship_for(
    spec: dict,
    label: str | None = None,
    archived: bool = False,
    expedition: str | None = None,
    save: bool = True,
) -> Ship:
    """The ship a spec belongs to: its registered ship, or a new one named after `label` (else the
    spec's own ship label) and registered, unless save is False."""
    from thorp import ship_store

    key = ship_key(spec)
    reg = register()
    if key in reg:
        return reg[key]
    if save:
        reg = register(fresh=True)
        if key in reg:
            return reg[key]
    name = clean_name(label or spec.get("ship") or spec.get("name"))
    taken = {s.name for s in reg.values()}
    base, i = name, 2
    while name in taken:  # a different fitout under the same label gets a numbered name
        name, i = f"{base} ({i})", i + 1
    preset = str(spec.get("model", {}).get("preset"))
    ship = Ship(
        key=key,
        name=name,
        preset=preset,
        size=ship_store.size_of(preset),
        subtitle=describe(spec),
        archived=archived,
        seeded_from=spec.get("seeded_from"),
        expedition=expedition,
    )
    if save:
        rec = ship_store.add_ship({**ship.__dict__, "fitout_id": fitout_id(spec)})
        ship = _ship(rec)
        register(fresh=True)
    return ship


# ships fitted out before the star map (7 November, 06:40 AEST) are the archived First Fleet;
# the ledger records start times in UTC
ARCHIVE_BEFORE = "2026-11-06T20:40"


def expedition_of_label(name: str | None, label: str | None) -> str | None:
    """The expedition a voyage (a run) belongs to, from its name and ship label."""
    if (label or "").startswith("First Light"):
        return "first_light"
    if (label or "").startswith("Fitout: Trigram engine"):
        return "induction"
    if (label or "").startswith("Logic tutor"):
        return "logic_tutor"
    if (label or "").startswith("SOP v"):
        # the standard launches (9 November): short-name ships, "SOP v0.0.5 at 21m (24 layers)". v0.0.6
        # (and the IFEval standard) are the instruction expedition; the rest are the ladder on Ogden.
        lab = label or ""
        if "IFEval" in lab or "v0.0.6" in lab:
            return "kipling"
        return "ogden"
    if (label or "").startswith("Fitout: Ogden") and "The Smallest Bridge" in (label or ""):
        return "smallest_bridge"
    if (label or "").startswith("Fitout: Ogden"):
        return "ogden"
    if (label or "").startswith(
        ("Cards:", "Fitout: Nothing up my sleeve")
    ):  # the census runs as the fitout's variations
        return "card_census"
    if (label or "").startswith("Two facts"):
        return "two_facts"
    if (label or "").startswith("Best keel"):
        return "best_keel"
    if (label or "").startswith(("Keel", "Seedling")):
        return "seedling"
    if (label or "").startswith("Apprentice II"):
        return "apprentice_2"
    if (label or "").startswith("Apprentice"):
        return "apprentice"
    if (name or "").startswith("loop-"):
        return "book_value"
    return None


def ship_of_run(row: dict, save: bool = True) -> Ship:
    """The ship a ledger run belongs to (registering it, and the run as one of its voyages, if save)."""
    import json

    spec = json.loads(row["spec_json"])
    ship = ship_for(
        spec,
        label=row.get("ship") or spec.get("ship"),
        archived=(row.get("started") or "") < ARCHIVE_BEFORE,
        expedition=expedition_of_label(row.get("name"), row.get("ship")),
        save=save,
    )
    if save and row.get("run_id"):
        from thorp import ship_store

        ship_store.add_voyage(row["run_id"], ship.key, row.get("name") or "", spec.get("seed"), row.get("started"))
    return ship


def ships_of_size(size: str) -> list[Ship]:
    """Every ship of a size, its variants (300k-h4) among them."""
    return [s for s in register().values() if s.size == size]



# --------------------------------------------------------------------- legacy labels (until 07:20)


Fleet = Literal["First Fleet", "Star Fleet"]


@dataclass(frozen=True)
class LegacyShip:
    """A run label's era, kept so older readers keep working; ships are now `Ship` (above)."""

    name: str
    fleet: Fleet
    question: str
    star: str | None = None  # the star a Star Fleet ship searches for


FIRST_FLEET = (
    "Dinghy",
    "Dinghy II",
    "Argo",
    "Argo II",
    "Endeavour",
    "Four Hundred Books, Second Opinion",
    "Hispaniola",
    "Only Things That Happened",
    "Smaller Pieces",
    "Half The Pieces",
    "Short Memory",
    "Little Argo",
    "Little Argo II",
    "Little Endeavour",
    "Little Hispaniola",
    "Little Mayflower",
)

SHIPS: dict[str, LegacyShip] = {
    **{
        n: LegacyShip(
            n,
            "First Fleet",
            "Archived 7 November: the spelling, shelf and calibration runs before the star map.",
        )
        for n in FIRST_FLEET
    },
}  # stars are destinations, never ships (Justin, 07:20)


def fleet_of(ship: str | None) -> Fleet | None:
    """The fleet a ledger ship label belongs to: loop runs ('Loop 12') belong to their loop's ship."""
    if not ship:
        return None
    if ship in SHIPS:
        return SHIPS[ship].fleet
    if ship.startswith("First Light"):
        return EXPEDITIONS["first_light"].fleet
    if ship.startswith("Fitout: Trigram engine"):
        return EXPEDITIONS["induction"].fleet
    if ship.startswith("Cards:"):
        return EXPEDITIONS["card_census"].fleet
    if ship.startswith("Logic tutor"):
        return EXPEDITIONS["logic_tutor"].fleet
    if ship.startswith("Two facts"):
        return EXPEDITIONS["two_facts"].fleet
    if ship.startswith("Best keel"):
        return EXPEDITIONS["best_keel"].fleet
    if ship.startswith(("Keel", "Seedling")):
        return EXPEDITIONS["seedling"].fleet
    if ship.startswith("Apprentice"):  # both apprentice voyages are Star Fleet
        return EXPEDITIONS["apprentice"].fleet
    if ship.startswith("Loop "):
        return EXPEDITIONS["book_value"].fleet
    return None


# -------------------------------------------------------------------------------------- voyages


@dataclass(frozen=True)
class Outcome:
    metric: str
    better: Literal["lower", "higher"]
    about: str


@dataclass(frozen=True)
class Lever:
    key: str  # where it lives (a sampler field or a spec path)
    low: float | None = None
    high: float | None = None
    choices: tuple = ()
    fixed: bool = False  # never turned (it keeps every run comparable)
    about: str = ""


@dataclass(frozen=True)
class StopRule:
    max_runs: int
    about: str = ""


@dataclass(frozen=True)
class Expedition:
    key: str
    name: str
    goal: str
    ship: str  # the label its runs carry ("Loop", "First Light")
    fleet: Fleet
    preset: str
    outcomes: tuple[Outcome, ...]
    levers: tuple[Lever, ...]
    stop: StopRule
    runner: str  # the script that runs a batch
    fit: str = ""  # the script that fits the runs so far
    results: str = ""  # where each run's row lands
    steering: str = ""  # the scheduled task that steers it
    status: Literal["planned", "running", "paused", "done"] = "planned"
    ships: tuple[
        str, ...
    ] = ()  # kept for older readers; a voyage's ships are its runs' ships (voyages.py)
    stars: tuple[str, ...] = ()  # the stars it aims for (destinations, never ships)
    learned: str = ""  # what it found, once done: carried into the next voyage
    next_steps: tuple[str, ...] = ()  # what it suggests doing next
    # the launching order, when an expedition is more than a batch of ships: investigations that must
    # finish before a learning ship sails, then the ships themselves (9 November, Justin: "the expedition
    # page should list the ship launching order and the things like spying on Qwen3")
    plan: tuple[dict, ...] = ()


EXPEDITIONS: dict[str, Expedition] = {
    lp.key: lp
    for lp in (
        Expedition(
            key="book_value",
            name="The book-value loop",
            goal="What is each kind of book worth on the Forgotten Tomes, and how many readings does it repay?",
            ship="Loop",
            fleet="First Fleet",
            preset=PROXY,
            outcomes=(
                Outcome("eval/hole-cards-unseen/bpb_mean_en", "lower", "the Forgotten Tomes score"),
                Outcome(
                    "nevermore/natural_max_score",
                    "higher",
                    "how near the shelf brought a Nevermore",
                ),
            ),
            levers=(
                Lever(
                    "alpha",
                    low=0.2,
                    high=2.0,
                    about="Dirichlet concentration: lower gives purer shelves",
                ),
                Lever(
                    "passes",
                    choices=(1, 2, 4, 8),
                    about="readings drawn per run, at least two values",
                ),
                Lever("stratum_floor", low=0.0, high=0.1, about="minimum share of every stratum"),
                Lever(
                    "read_mb", fixed=True, about="80 MB read per run, so every run is comparable"
                ),
            ),
            stop=StopRule(300, "cut from 2,000 to 300 at 00:45 (about 24 hours of the Mac)"),
            runner="scripts/loop.py",
            fit="scripts/loop_fit.py",
            results="data/loop/runs.csv",
            steering="thorp-loop-steer",
            status="done",
            ships=("Loop",),
            learned="Stopped at 07:05 on 7 November after about 20 runs (Justin: enough learned). The "
            "shelf explains about 60% of the spread between runs; English-original fiction is the most "
            "valuable kind for the Forgotten Tomes and translated verse the least; rereading up to four "
            "times costs nothing measurable; language variety slightly hurts on this English-heavy deck.",
        ),
        Expedition(
            key="first_light",
            name="First Light",
            goal="What is the quickest path to the first two stars, the previous-word and duplicate-word heads?",
            ship="First Light",
            fleet="First Fleet",
            preset=PROXY,
            outcomes=(
                Outcome(
                    "steps_to_lit/previous_word", "lower", "steps until a previous-word head is lit"
                ),
                Outcome(
                    "steps_to_lit/duplicate_word",
                    "lower",
                    "steps until a duplicate-word head is lit",
                ),
                Outcome(
                    "eval/hole-cards-unseen/bpb_mean_en",
                    "lower",
                    "the Forgotten Tomes score, still the final judge",
                ),
            ),
            levers=(
                Lever("tokeniser.vocab", choices=(2048, 4096, 16384)),
                Lever("optim.lr", choices=(1e-3, 2e-3, 4e-3)),
                Lever(
                    "shelf",
                    choices=("fiction", "verse", "pool"),
                    about="English-original fiction (baseline), verse, or the mixed pool",
                ),
                Lever(
                    "tokens",
                    fixed=True,
                    about="about 130M tokens read per round-1 run; passes fit the shelf",
                ),
            ),
            stop=StopRule(
                25, "a pathfinder, one lever at a time (14), combinations (up to 8), then 9m"
            ),
            runner="scripts/make_first_light.py",
            results="specs/first-light/",
            steering="thorp-first-light",
            status="running",
            learned="The pathfinder (twice the reading) won at 1.693 bpb; vocabulary 16,384 next (1.705); "
            "the baseline 1.781/1.797 across seeds (a 0.016 error bar); 2,048 and the 1e-3 learning rate "
            "were the worst arms and verse the worst shelf (1.92-1.93). No single head lit previous-word; "
            "the pathfinder lit it shared at step 1,575 (51.6M tokens). Vocab 2,048 and lr 2e-3, which the "
            "later 1m runs use, descend from this sweep.",
            stars=("previous_word", "duplicate_word", "nevermore"),
        ),
        Expedition(
            key="seedling",
            name="Laying the keel",
            goal="Does a pilot (1m) grown from a keel's foundation (300k) reach its stars sooner than one built from nothing? "
            "A rehearsal of Great Expectations at a few minutes a run.",
            ship="Keel",  # the label its runs carry ("Keel: ..."); the voyage key stays "seedling"
            fleet="First Fleet",
            preset=PROXY,
            outcomes=(
                Outcome(
                    "stars/previous_word/shared_score",
                    "higher",
                    "the previous-word star, one head or shared",
                ),
                Outcome(
                    "nevermore/natural_max_score", "higher", "steps until the Nevermore lights"
                ),
                Outcome(
                    "eval/hole-cards-unseen/bpb_mean_en",
                    "lower",
                    "the Forgotten Tomes score, still the final judge",
                ),
            ),
            levers=(
                Lever(
                    "seeded_from.mode",
                    choices=("freeze", "slow", "free"),
                    about="the inherited weights: frozen, at a tenth of the learning rate, or free",
                ),
                Lever(
                    "baseline",
                    fixed=True,
                    about="every other setting is First Light's vocabulary-2,048 run, the from-scratch baseline",
                ),
            ),
            stop=StopRule(
                7, "the keel pathfinder, then three ways of growing it into a pilot, two seeds each"
            ),
            runner="scripts/make_seedling.py",
            results="specs/seedling/",
            status="planned",
            stars=("previous_word", "duplicate_word", "nevermore"),
        ),
        Expedition(
            key="apprentice",
            name="The Magician's Apprentice",
            goal="Can a keel learn a trick another keel has never learnt, by having it handed over? "
            "The magician (the keel pathfinder) learns the previous-word trick; the apprentice reads the "
            "same books with each line's words shuffled, so it has no reason to; then the magician's "
            "heads are transplanted into the apprentice and it reads ordered text, against an apprentice "
            "that must learn the trick itself.",
            ship="Apprentice",
            fleet="First Fleet",
            preset=next(r["preset"] for r in LADDER if r.get("kind") == "nursery"),
            outcomes=(
                Outcome(
                    "stars/previous_word/shared_score",
                    "higher",
                    "it performs the trick: lit from the first reading",
                ),
                Outcome(
                    "soundings/layer_{i}/bpb",
                    "lower",
                    "it uses the trick: its guesses on ordered text improve faster than the control's",
                ),
                Outcome(
                    "stars/previous_word/max_score",
                    "higher",
                    "it keeps the trick: the star stays lit as it trains",
                ),
                Outcome(
                    "eval/hole-cards-unseen/bpb_mean_en",
                    "lower",
                    "it is worth something: the Forgotten Tomes no worse than the control's",
                ),
            ),
            levers=(
                Lever(
                    "transplant",
                    choices=("handed over", "none"),
                    about="the magician's previous-word heads and position embeddings, or nothing",
                ),
                Lever(
                    "apprentice",
                    fixed=True,
                    about="both start from the same apprentice, trained on the shuffled shelf",
                ),
            ),
            stop=StopRule(
                6, "the magician, the apprentice, then handover and control, two seeds each"
            ),
            runner="scripts/make_apprentice.py",
            results="specs/apprentice/",
            status="done",
            learned="Not passed. The keel learned the previous-word trick only partly (0.21 by one head, 0.32 shared); the apprentice learned some of it even from shuffled words (0.13, 0.19), because word pieces still follow each other inside a word; and the handed-over heads did not perform the trick (0.01 at the first reading) and made the apprentice guess worse (Forgotten Tomes 2.142 against the control's 2.110): heads moved without the token embeddings they read are a trick without its deck.",
            stars=("previous_word", "offset_2", "nevermore"),
            next_steps=(
                "Hand over the deck with the trick: the heads together with the token and position embeddings and the layers beneath them, so the heads read the stream they learned on.",
                "Hand over within one lineage: the magician's own early checkpoint (before the trick formed) as the apprentice, so both share the same embeddings, and only the trick differs.",
                "Choose a trick that shuffling truly removes: a word-level one, such as copying a repeated phrase (the Nevermore), not the previous piece, which spelling needs whatever the order.",
                "Move the test up to the pilot (1m), whose pathfinder lights the previous-word star shared, so the donor has a trick worth handing over.",
                "Teach rather than transplant: let the apprentice learn from the magician's predictions on ordered text (distillation), and compare how soon the trick lights.",
            ),
        ),
        Expedition(
            key="table_talk",
            name="Table Talk",
            goal="A 9m you can converse with, in period English, and test: trained the way the Magician's "
            "Apprentice, First Light and Laying the keel teach (Justin, 09:30). Named after Coleridge's "
            "Table Talk (1835).",
            ship="Table Talk",
            fleet="First Fleet",
            preset=next(r["preset"] for r in LADDER if r.get("name") == "The speller"),
            outcomes=(
                Outcome(
                    "tricks/turn_taking/score",
                    "higher",
                    "it answers and stops: ends its turn instead of writing yours",
                ),
                Outcome(
                    "tricks/on_topic/score",
                    "higher",
                    "its answer shares the question's subject more than a shuffled pairing does",
                ),
                Outcome(
                    "eval/hole-cards-unseen/bpb_mean_en",
                    "lower",
                    "the Forgotten Tomes score: conversation must not cost it its reading",
                ),
            ),
            levers=(
                Lever(
                    "recipe",
                    fixed=True,
                    about="First Light's quickest path: its vocabulary, learning rate and shelf",
                ),
                Lever(
                    "growth",
                    choices=("grown from the pilot", "from scratch"),
                    about="grown from a pilot if Laying the keel shows growing pays, else from scratch; never by transplanting heads alone (the Magician's Apprentice)",
                ),
                Lever(
                    "stages",
                    fixed=True,
                    about="reading, then dialogue (plays, dialogues, catechisms, table talk, letters), then conversation in turns",
                ),
            ),
            stop=StopRule(
                4,
                "two seeds of the chosen recipe, and one of the alternative growth, then the conversation",
            ),
            runner="",
            status="planned",
            stars=("previous_word", "nevermore"),
        ),
        Expedition(
            key="apprentice_2",
            name="The Magician's Apprentice II",
            goal="The first apprentice voyage's five next steps, at the pilot, where the trick is lit: hand over "
            "the deck with the trick; hand over within one lineage; a word-level trick (the Nevermore); all at the "
            "pilot; and teach rather than transplant.",
            ship="Apprentice II",
            fleet="First Fleet",
            preset=PROXY,
            outcomes=(
                Outcome(
                    "stars/previous_word/shared_score",
                    "higher",
                    "performs the trick from the first reading",
                ),
                Outcome(
                    "nevermore/natural_copy_gain",
                    "higher",
                    "copying: the word-level trick, for the Nevermore handover",
                ),
                Outcome(
                    "eval/hole-cards-unseen/bpb_mean_en",
                    "lower",
                    "worth something: the Forgotten Tomes no worse than the control",
                ),
            ),
            levers=(
                Lever(
                    "handover",
                    choices=(
                        "the deck (previous word)",
                        "the deck (Nevermore)",
                        "its own heads, handed back",
                        "taught",
                        "none",
                    ),
                    about="what the receiver gets, against a control that gets nothing",
                ),
                Lever(
                    "reading",
                    fixed=True,
                    about="one pass of the ordered English-original fiction at learning rate 1e-3",
                ),
            ),
            stop=StopRule(14, "two donors, then six experiments with two seeds each"),
            runner="scripts/make_apprentice2.py",
            results="specs/apprentice2/",
            status="planned",
            stars=("previous_word", "nevermore"),
        ),
        Expedition(
            key="best_keel",
            name="The best keel",
            goal="The 300k that performs best on its four discovery rungs (Like father, like son; Fire and ice; "
            "One, two, three; Again and again): the end of the current queue.",
            ship="Best keel",
            fleet="First Fleet",
            preset=NURSERY,
            outcomes=(
                Outcome(
                    "tricks/kin_test/lift", "higher", "Like father, like son (the Origin chain)"
                ),
                Outcome("tricks/fire_test/lift", "higher", "Fire and ice (the energy chain)"),
                Outcome(
                    "tricks/counting_test/lift", "higher", "One, two, three (Mendeleev's chain)"
                ),
                Outcome("tricks/again_test/lift", "higher", "Again and again (the eternal return)"),
            ),
            levers=(
                Lever(
                    "vocab",
                    choices=("1,024", "2,048", "4,096"),
                    about="the tokeniser's vocabulary, on the loop pool",
                ),
                Lever("lr", choices=("1e-3", "3e-3", "1e-2"), about="the peak learning rate"),
                Lever("context", choices=("256", "1,024"), about="the window"),
                Lever("passes", choices=("1", "2", "4"), about="readings of the shelf"),
                Lever(
                    "shelf",
                    choices=("fiction", "verse", "pool", "nursery", "nursery then fiction"),
                    about="what it reads; the nursery shelf is 214 English children's books, and the last is two stages",
                ),
            ),
            stop=StopRule(
                27,
                "round 1: the baseline and 11 one-lever changes, two seeds each; round 2: the winners combined, three seeds",
            ),
            runner="scripts/make_best_keel.py",
            results="data/runs/best-keel.md",
            status="planned",
        ),
        Expedition(
            key="two_facts",
            name="The two-fact problem",
            goal="The ladder's first major voyage (Justin, 10:45): every class climbs closer to chaining two facts "
            "than the class beneath, so that the 50m can attempt the four chaining rungs (Nature's breeder, the mill "
            "test, the between test, the pigeonhole test). Judged on the leaderboard: each class's best run by its "
            "climb (thorp/leaderboard.py). Even if the 50m fails, the climb is the result.",
            ship="Two facts",
            fleet="First Fleet",
            preset=PARAGRAPH,
            outcomes=(
                Outcome(
                    "climb",
                    "higher",
                    "the leaderboard's climb, 0 to 5: rungs performed from the bottom of each chain, plus the next rung's progress",
                ),
                Outcome(
                    "chaining_lift",
                    "higher",
                    "the mean lift on the four 50m rungs, two facts chained; lit at 0.1",
                ),
            ),
            levers=(
                Lever(
                    "shelf",
                    choices=("general", "a reasoning shelf as a late stage"),
                    about="books dense in 'A, and B, so C': Euclid, the logic books, Plato, Faraday, Tyndall, Huxley",
                ),
                Lever(
                    "tack",
                    choices=("plain", "conclusion-weighted"),
                    about="extra weight on the tokens after so, therefore, hence",
                ),
                Lever(
                    "depth",
                    choices=("the class's shape", "deeper and narrower at the same size"),
                    about="chaining needs layers in sequence",
                ),
                Lever(
                    "reading",
                    choices=("compute-optimal", "far past it"),
                    about="composition can appear late, after the loss has flattened",
                ),
                Lever(
                    "seed",
                    choices=("from scratch", "grown from the class below"),
                    about="start with the facts, learn to combine them",
                ),
            ),
            stop=StopRule(
                8,
                "round 1, the baseline: the keel, the pilot, the speller and the stylist, two seeds each",
            ),
            runner="scripts/make_two_facts.py",
            results="thorp/leaderboard.py",
            status="running",
            stars=("nevermore", "mover"),
        ),
        Expedition(
            key="card_census",
            name="The card census",
            goal="Which of the necessary cards (previous-word, the Nevermore, the mover, the comparator; every model that "
            "chains holds all four) can each class draw at all? The 300k in 17 variations, then the 1m in 21; once a "
            "model holds all four, the work turns to chaining (Justin, 13:00).",
            ship="Cards",
            fleet="First Fleet",
            preset=NURSERY,
            outcomes=(
                Outcome("stars/previous_word/max_score", "higher", "previous-word, lit at 0.5"),
                Outcome("nevermore/natural_max_score", "higher", "the Nevermore, lit at 0.3"),
                Outcome("stars/mover/max_score", "higher", "the mover, lit at 0.2"),
                Outcome("stars/comparator/max_score", "higher", "the comparator, lit at 0.3"),
            ),
            levers=(
                Lever(
                    "positions",
                    choices=("learned", "rotary"),
                    about="rotary positions: the relative skill a Nevermore needs",
                ),
                Lever(
                    "tack",
                    choices=("plain", "copy-weighted", "conclusion-weighted"),
                    about="what the loss weighs most",
                ),
                Lever(
                    "shelf",
                    choices=("fiction", "verse", "nursery", "fiction then the reasoning shelf"),
                    about="repetition, simplicity, argument",
                ),
                Lever(
                    "shape",
                    choices=("the class's", "more, smaller heads", "one more layer"),
                    about="the same budget spent differently",
                ),
                Lever(
                    "reading",
                    choices=("4 passes", "8 passes"),
                    about="reading past an induction head's sudden jump",
                ),
                Lever(
                    "lr", choices=("lower", "the class's", "higher"), about="the peak learning rate"
                ),
                Lever(
                    "vocab",
                    choices=("the class's", "half"),
                    about="a smaller vocabulary leaves more of the model to its layers",
                ),
            ),
            stop=StopRule(
                38,
                "the 300k in 17 variations and the 1m in 21 (13 here and round 2's four, two seeds each), one seed each",
            ),
            runner="scripts/make_card_census.py",
            results="data/runs/cards/census-<class>.md",
            status="running",
            stars=("previous_word", "nevermore", "mover", "comparator"),
        ),
        Expedition(
            key="knockout",
            name="The knockout",
            goal="Are the four necessary cards causally necessary for chaining, or do they only appear beside it? In "
            "models that chain, silence each card's heads and measure what chaining loses, against silencing as many "
            "random heads (Justin, 13:30). Outside models only: it does not use the training queue.",
            ship="Knockout",
            fleet="First Fleet",
            preset=PARAGRAPH,
            outcomes=(
                Outcome(
                    "cause_gain",
                    "lower",
                    "the logic deck's cause-and-effect gain with a card silenced",
                ),
                Outcome(
                    "chaining_lift",
                    "lower",
                    "the four chaining tests' mean lift with a card silenced",
                ),
            ),
            levers=(
                Lever(
                    "card",
                    choices=(
                        "previous-word",
                        "the Nevermore",
                        "the mover",
                        "the comparator",
                        "random heads",
                    ),
                    about="whose heads are silenced: the card's 8 strongest, or 8 random heads from no card (3 draws)",
                ),
                Lever(
                    "model",
                    choices=("Qwen3 4B", "Phi-4-mini", "SmolLM3 3B", "Llama 3.2 3B", "Phi-2"),
                    about="the models that chain",
                ),
            ),
            stop=StopRule(5, "the five models that chain, one reading each (deterministic)"),
            runner="thorp/knockout.py",
            results="s4.outside_readings, knockout-<model>",
            status="running",
            stars=("previous_word", "nevermore", "mover", "comparator"),
        ),
        Expedition(
            key="induction",
            name="Discovering the induction head",
            goal="The first Nothing up my sleeve to grow an induction head (the Nevermore, natural score 0.3): the 300k first, fed text at "
            "the Pareto frontier of in-window trigram repetition (thorp/trigrams.py), period books only, against a twin "
            "fitout of the same shelves and amounts with books chosen at random (Justin, 14:40; top of the queue).",
            ship="Fitout: Trigram engine",
            fleet="First Fleet",
            preset=NURSERY,
            outcomes=(
                Outcome(
                    "nevermore/natural_max_score",
                    "higher",
                    "the Nevermore on real prose, lit at 0.3",
                ),
                Outcome(
                    "nevermore/natural_copy_gain",
                    "higher",
                    "the copy gain: what the second reading of a passage saves",
                ),
                Outcome(
                    "stars/previous_word/max_score",
                    "higher",
                    "previous-word, the Nevermore's first layer, lit at 0.5",
                ),
            ),
            levers=(
                Lever(
                    "selection",
                    choices=("by repetition (the Pareto frontier first)", "at random"),
                    about="the same shelves, amounts and passes; only which books",
                ),
                Lever(
                    "repetition engine share",
                    choices=("the trigram engine's", "more", "less"),
                    about="how much of the reading is the repetition engine (nursery, how-to, formulaic dialogue)",
                ),
            ),
            stop=StopRule(4, "round 1: the trigram engine and its random twin, two seeds each"),
            runner="thorp/fitouts.py",
            results="data/runs/fitouts/",
            status="running",
            stars=("nevermore", "previous_word"),
        ),
        Expedition(
            key="ogden",
            name="Ogden v0.1",
            goal="One fixed corpus for every class, as the Pile was for Pythia (Justin, 19:20): the 592 store books "
            "whose ordinary words keep closest to Ogden's Basic English (Ogden-ness 68% or more, thorp/ogden.py), on "
            "clean text, one shared 2,048-piece tokeniser, four passes. 300k, 1m and 9m read the same text in the same "
            "order, so what differs is size alone: which cards and stars form at 9m, and do the 300k's trends point there?",
            ship="Fitout: Ogden v0.1",
            fleet="Star Fleet",
            preset=NURSERY,
            outcomes=(
                Outcome("nevermore/natural_max_score", "higher", "the Nevermore, lit at 0.3: copying from the window"),
                Outcome("stars/previous_word/max_score", "higher", "previous-word, lit at 0.5"),
                Outcome("stars/mover/max_score", "higher", "the mover, lit at 0.2"),
                Outcome("stars/comparator/max_score", "higher", "the comparator, lit at 0.3"),
                Outcome(
                    "eval/hole-cards-unseen/bpb_mean",
                    "lower",
                    "the Forgotten Tomes, bits per byte (clean text: not compared with raw voyages)",
                ),
            ),
            levers=(
                Lever(
                    "class",
                    choices=("the keel", "the pilot", "the speller"),
                    about="the only thing that differs between voyages",
                ),
                Lever("seed", choices=("1", "2"), about="the noise: each class sails twice"),
            ),
            stop=StopRule(
                6,
                "v0.1: three classes, two seeds each, pretraining only; read every 64 steps (~2.1M tokens) so the "
                "classes line up by tokens read. The goals (Justin, 19:45; 'Ogden doesn't need to know about the world, "
                "just the shapes of the world'): the keel the best 2-word guesser, the pilot the best 3-word guesser, "
                "the speller the best 4-word guesser: each class's top guess of the next keyed word (Ogden's 850 and "
                "<name>, <number>, <thing>) on the Forgotten Tomes beats the corpus's own keyed n-gram table with 1, 2 "
                "and 3 words of context (backing off where it never saw the context), on both seeds",
            ),
            runner="thorp/fitouts.py",
            results="data/runs/fitouts/",
            status="planned",
            stars=("nevermore", "previous_word", "mover", "comparator"),
        ),
        Expedition(
            key="smallest_bridge",
            name="The Smallest Bridge",
            goal="The smallest Nothing up my sleeve that plays the Bridge, the Mover and the Counter (Justin, 2026-11-08 08:00: 'a "
            "plan for an expedition using numerous size ships in order to get the bridge card and the mover and counter "
            "at the lowest size possible ... take their learnings to follow up journeys'; 08:20: 'get the rare word and "
            "premise maker into the model as soon as possible, then try simulate the bridge and then move to see if we "
            "can get the nevermore, counter and mover'). Each voyage in three stages: the Basics pinned from the first "
            "step, the Bridge (a riddle) pulled on composed items once they are held, the Faces earned. The ships descend "
            "9m, 1m, the three-layer keel, the keel, each carrying the last one's recipe; a failed descent sails again "
            "with the bigger ship as teacher.",
            ship="Fitout: Ogden (The Smallest Bridge)",
            fleet="First Fleet",
            preset=next(r["preset"] for r in LADDER if r.get("name") == "The speller"),
            outcomes=(
                Outcome("stars/bridge/max_score", "higher", "the Bridge, played at 0.5 nats"),
                Outcome("stars/mover/shared_score", "higher", "the Mover's look, at 0.2 (with the one-hop lift at 0.1)"),
                Outcome("tricks/logic_test/lift_one_hop", "higher", "the Mover's ability, at 0.1"),
                Outcome("counter/probe_r2", "higher", "the Counter, R² at 0.5"),
                Outcome("nevermore/natural_copy_gain", "higher", "the Nevermore, copy gain at 1.0"),
                Outcome("eval/hole-cards-unseen/bpb_mean", "lower", "the language's cost: the Forgotten Tomes"),
            ),
            levers=(
                Lever("class", choices=("the speller", "the pilot", "the three-layer keel", "the keel"),
                      about="descending: each class sails once the one above has shown the recipe"),
                Lever("stage", choices=("all at once", "staged"), about="the full deck at once (leg 0) against in order"),
                Lever("teacher", choices=("none", "the bigger ship"), about="only when a descent fails"),
                Lever("seed", choices=("1", "2"), about="the smallest success sails a second seed"),
            ),  # fmt: skip
            stop=StopRule(
                12,
                "Legs 0 to 4 (DECISIONS.md, 'The Smallest Bridge, pre-registered'); a card is played by the deck's rules "
                "(wager.falls) and counts at a class only on two seeds",
            ),
            runner="thorp/fitouts.py",
            results="data/runs/fitouts/",
            status="running",
            stars=("bridge", "mover", "nevermore"),
        ),
        Expedition(
            key="logic_tutor",
            name="The logic tutor",
            goal="Can chaining two facts be taught to an Ogden speller rather than read into it, and does a bigger "
            "model's writing teach it better than a program's? (Justin, 19:58: 'Pre-register it'.) From each Ogden "
            "v0.1 9m seed's last checkpoint, a 16M-token stage: the same skeletons of invented facts (order, cause, "
            "membership, proportion) written in strict Basic English by Qwen 3.8 27B (tutor) or in fixed frames "
            "(template), each half and half with Ogden replay, against replay alone. The trick is taught; the stars "
            "and cards are read, never handed over.",
            ship="Logic tutor",
            fleet="First Fleet",
            preset=next(r["preset"] for r in LADDER if r.get("name") == "The speller"),
            outcomes=(
                Outcome("tricks/logic_test/gain", "higher", "the chaining gain on the logic deck, performed at 0.1"),
                Outcome("tricks/logic_test/score", "higher", "the share of logic items right, performed at two-thirds"),
                Outcome(
                    "tricks/logic_test/gain_counterfactual",
                    "higher",
                    "transfer: the counterfactual relation, never taught",
                ),
                Outcome("tricks/logic_test/lift_three_hop", "higher", "transfer: three-fact chains, never taught"),
                Outcome("stars/mover/max_score", "higher", "the mover, lit at 0.2"),
                Outcome("nevermore/natural_max_score", "higher", "the Nevermore, lit at 0.3"),
                Outcome(
                    "eval/hole-cards-unseen/bpb_mean",
                    "lower",
                    "the guard: the Forgotten Tomes no worse than replay by more than 0.02 bits per byte",
                ),
            ),
            levers=(
                Lever(
                    "arm",
                    choices=("tutor", "template", "replay"),
                    about="who wrote the taught half of the stage: a bigger model, a program, or nothing (Ogden replay)",
                ),
                Lever("seed", choices=("1", "2"), about="each arm continues from that seed's Ogden 9m"),
            ),
            stop=StopRule(
                6,
                "Three arms, two seeds, one 16M-token stage each. Verdicts across both seeds (DECISIONS.md, 'The "
                "logic tutor, pre-registered'): taught (a taught arm performs chaining by the deck's rule and both "
                "seeds beat both replay seeds); the teacher worth having (both tutor seeds beat both template seeds); "
                "nothing lost (the Forgotten Tomes within 0.02 bits per byte of replay).",
            ),
            runner="thorp/fitouts.py",
            results="data/runs/fitouts/",
            status="planned",
            stars=("nevermore", "mover", "comparator"),
            next_steps=(
                "Write the skeleton generator: two facts and a checked conclusion over fresh invented words, four "
                "relations, counterfactual and three-fact chains held out",
                "Write the two writers (the tutor through Qwen 3.8 27B, strict Basic English with triples to check; "
                "the template in fresh frames) and the audits: Ogden words only, no six-word overlap with the logic "
                "deck or the chains' pairs, the 50m rungs' content words kept out",
                "Measure the teacher's generation rate on 1,000 passages, and read 100 by hand (95% must keep the logic)",
                "Justin's decision: an S5 policy for taught text (marked, off the period leaderboard, never scored "
                "against its teacher)",
                "Write the six specs, seeded from fu-ogden-v0-1@9m-pre-s1 and -s2, once both are home",
            ),
        ),
    )
}


EXPEDITIONS["two_bets"] = Expedition(
    key="two_bets",
    name="The two bets",
    goal="Pan's word bet against its type bet on the same held-out points (Justin, 8 November: 'Pan must be the "
    "best at betting. so its current bet is the next word in a two word sequence. But the other bet should be "
    "about betting the type of the word too. and then we'd compare those scores'): the same model, two ways of "
    "reading its distribution, the next keyed word and the next word's type.",
    ship="Pan",
    fleet="First Fleet",
    preset=NURSERY,
    outcomes=(
        Outcome("shapes/keyed_top1", "higher", "the word bet: the next keyed word"),
        Outcome("shapes/type_top1_keyed", "higher", "the type bet on the same points"),
    ),
    levers=(Lever("bet", choices=("word", "type"), about="the same checkpoint, two bets"),),
    stop=StopRule(2, "Pan's two seeds, both bets read from the same checkpoints"),
    runner="thorp/evaluators/shapes.py",
    results="data/runs/",
    status="planned",
    ships=("Pan",),
)


# The names before 2026-11-07 16:20 (Justin: "the voyages should become expeditions and a ship's runs
# should become voyages"), kept as aliases until every reader has moved.
Voyage = Expedition
VOYAGES = EXPEDITIONS
voyage_of_label = expedition_of_label

TERMS = {
    "expedition": "a line of experiments with one goal, its levers and its stop rule (fleet.EXPEDITIONS); "
    "what was called a voyage before 2026-11-07",
    "voyage": "one ship's run: one spec trained once, with its run id, in the ledger's runs table; "
    "what was called a run",
    "ship": "a class and a fitout; its voyages are its sailings",
    "library": "a book list Nothing up my sleeve reads from, scores on or refuses (thorp/library.py; the ship's two "
    "stores are the canonical libraries); what was called a shelf",
    "library aboard": "the libraries a voyage carried, with each one's books, tokens and hash "
    "(library.aboard(run_id))",
}


EXPEDITIONS["kipling"] = Expedition(
    key="kipling",
    name="The Kipling Expedition",
    goal="SOP v0.0.6 (Justin, 9 November), named for Kipling: six honest serving-men (What and Why and When and How and Where and Who) are the question answering, and \"If—\" is a poem of nothing but constraints, which is what instruction following is. Four aims on one standard. (1) Beat IFEval: a class trained to obey the "
    "25 verifiable instructions, scored prompt-level strict on the official 541. (2) Control tokens in our "
    "embeddings: the marked deck against the plain one. (3) Teach question answering to the 9m: the return leg on "
    "the dialogue shelf. (4) Test the probe phase in pretraining: pulse the scaffold down and measure whether the "
    "heads respond — the leak when the pull goes and the recovery when it returns — against the heads that do not "
    "respond at all. The investigations sail before the learning ships: auditing Qwen3 4B's heads comes first, "
    "because what the 300k, 1m and 9m are asked to grow is read off that map.",
    ship="SOP v0.0.6",
    fleet="Star Fleet",
    preset="300k",
    outcomes=(
        Outcome("ifeval/prompt_strict", "higher", "IFEval, prompt-level strict, the official 541"),
        Outcome("ifeval/instruction_strict", "higher", "instruction-level strict, as the proof beside it"),
        Outcome("tricks/logic_test/lift_one_hop", "higher", "following one stated premise: the step before two"),
    ),
    levers=(
        Lever("control tokens", choices=("marked", "plain"), about="the deck's premise/question/answer/end as pieces"),
        Lever("scaffold control", choices=("fixed 10/60", "probe and equilibrium"), about="the dynamic schedule"),
        Lever("class", choices=("300k", "1m", "9m"), about="which learning ship reads the standard"),
    ),
    stop=StopRule(6, "the investigations first (the Qwen3 4B head census, the control-token arm, the IFEval corpus "
                     "and its verifiers), then the three learning ships in size order; nothing sails before the "
                     "investigation it depends on is home"),
    runner="thorp/train.py",
    results="data/runs/",
    status="planned",
    plan=(
        {"n": 1, "kind": "investigation", "name": "audit Qwen3 4B's heads",
         "detail": "a census of all 1,152 heads (36 x 32): ablate each one, measure what it moves on the deck and "
                   "on held-out text, and rank the empty slots by how much they matter. The learning ships are "
                   "asked to grow what this map says is worth growing.",
         "queue": "cmd: the head census (backend/scripts/head_census.py) on mlx-community/Qwen3-4B-4bit"},
        {"n": 2, "kind": "investigation", "name": "the control tokens",
         "detail": "the marked deck (<premise>/<question>/<answer>/<end>) against the plain one, in the embeddings",
         "queue": "300k@v0.0.6-control (both arms)"},
        {"n": 3, "kind": "investigation", "name": "the IFEval corpus and its verifiers",
         "detail": "25 rule types, every training pair proved compliant by the official checker; the 541 read "
                   "prompt-level strict",
         "queue": "held until teh corpus and the evaluator are home (specs/ifeval-ready.hold)"},
        {"n": 4, "kind": "ship", "name": "300k@v0.0.6", "detail": "the first learning ship", "queue": "after 1-3"},
        {"n": 5, "kind": "ship", "name": "1m@v0.0.6", "detail": "the second, if the 300k clears its rung", "queue": "after 4"},
        {"n": 6, "kind": "ship", "name": "9m@v0.0.6", "detail": "the third, if the 1m does", "queue": "after 5"},
    ),
)

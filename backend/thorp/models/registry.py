"""Model presets and the family map. Preset names live here and nowhere else in the package."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GPTConfig:
    layers: int
    width: int
    heads: int
    vocab: int = 16384
    context: int = 1024
    # how the model knows where a piece is (2026-11-07, the two-fact problem's round 2): "learned"
    # (an embedding per position, added to the piece's) or "rope" (rotary positions, applied to the
    # queries and keys, so attention sees how far apart two pieces are: the relative skill a Nevermore
    # needs)
    positions: str = "learned"


PRESETS: dict[str, dict] = {
    "tiny": dict(layers=2, width=64, heads=2),  # tests only
    # 1m, the pilot (2026-11-07; renamed from "the proxy" at 09:00): a fast outer loop for data
    # questions, used only where it ranks shelves the way 9m does (DECISIONS.md, "The 1m proxy")
    # 300k, the keel (renamed from "the seedling" at 09:00): two layers of two 32-wide heads, the same
    # head size as 1m and 9m, so its heads can be carried up whole
    "300k": dict(layers=2, width=64, heads=2),
    "1m": dict(layers=4, width=128, heads=4),
    # shape variants for the card census (2026-11-07, Justin: "how many of the cards are possible at
    # 300k"): the same budget spent on more, smaller heads, or on one more layer; experiments within a
    # class, not rungs of the ladder
    "300k-h4": dict(layers=2, width=64, heads=4),
    "300k-l3": dict(layers=3, width=64, heads=2),
    "1m-h8": dict(layers=4, width=128, heads=8),
    "1m-l6": dict(layers=6, width=128, heads=4),
    "9m": dict(layers=6, width=192, heads=6),
    # The ladder (2026-11-06; DECISIONS.md): each rung has one job. 9m: spelling, punctuation and the
    # statistical laws. 21m: grammar and style. 50m: paragraphs and the size curve (rented GPUs).
    # 100m: the Origin test, the Mac's flagship. 350m: the top of the Origin curve (rented GPUs).
    "21m": dict(layers=8, width=320, heads=8),
    "50m": dict(layers=12, width=512, heads=8),
    "100m": dict(layers=12, width=768, heads=12),
    "350m": dict(layers=24, width=1024, heads=16),
}


# What each rung is for and how it is judged: the dashboard's Ladder tab reads this, so the page
# never names a preset itself.
LADDER: list[dict] = [
    dict(
        preset="300k",
        kind="nursery",
        vocab=2048,
        where="this Mac (a minute or two a run)",
        status="planned",
        name="The keel",
        job="Laid first, and everything is built on it: light the first stars in minutes, then become the foundation a 1m is built on",
        overview="2 layers x 64, two heads of 32 (the same head size as 1m and 9m, so a head can "
        "be carried up whole), vocabulary 2,048: about 0.3M parameters. Too small to judge books "
        "on; its job is the bottom of the stack. Can it light a previous-word head at all, how "
        "fast, and does a 1m built on its frozen layers reach the Nevermore sooner?",
        # scored on the card census and cause and effect (Justin, 13:25): the cards first, then cause
        scored="The four necessary cards held, then cause and effect, then chaining two facts",
        metrics=[
            [
                "cards held",
                "of the four every chaining model holds (previous-word, the Nevermore, the mover, the "
                "comparator), how many it draws, by one head or a layer's best two; the card census "
                "around its fitout says which are possible at 300k at all",
                "live",
            ],
            [
                "cause and effect",
                "the logic deck's chaining gain on its cause items (invented words, so no knowledge helps); "
                "0.1 to count, eight items",
                "live",
            ],
            [
                "chaining two facts",
                "the chaining lift on the four public chaining tests; above 0.03 it leaves the noise and "
                "joins the chaining board",
                "live",
            ],
            [
                "the 1m on top",
                "whether a 1m grown from it draws the cards sooner than one built from nothing",
                "to come",
            ],
        ],
    ),
    dict(
        preset="1m",
        kind="proxy",
        vocab=4096,
        where="this Mac (about 4 minutes a run)",
        status="calibrating against 9m",
        name="The pilot",
        job="A pilot study and the harbour pilot: scouts data questions fast, trusted only where it ranks shelves as 9m does, and brings the bigger ships in",
        overview="4 layers x 128, vocabulary 4,096, about 1.4M parameters. Scored only on the "
        "Forgotten Tomes, once at the end. First it re-runs comparisons already made at 9m; if its "
        "ranking agrees, it explores and 9m confirms the winners.",
        # scored on the cards and cause and effect, as the keel (Justin, 13:25); still the shelf scout
        scored="The four necessary cards held, then cause and effect, then chaining two facts; the Forgotten Tomes beside",
        metrics=[
            [
                "cards held",
                "of the four every chaining model holds (previous-word, the Nevermore, the mover, the "
                "comparator), how many it draws; the card census around its fitout says which are "
                "possible at 1m",
                "live",
            ],
            [
                "cause and effect",
                "the logic deck's chaining gain on its cause items; 0.1 to count, eight items",
                "live",
            ],
            [
                "chaining two facts",
                "the chaining lift on the four public chaining tests; above 0.03 it joins the chaining board",
                "live",
            ],
            [
                "Forgotten Tomes score",
                "bits per byte on 16 books Qwen 3.8 cannot have read: the shelf scout's measure",
                "live",
            ],
        ],
    ),
    dict(
        preset="9m",
        where="this Mac",
        status="running",
        name="The speller",
        job="Spelling, punctuation and the statistical laws of text",
        overview="The smallest model learns the surface of English: how words are spelled, where "
        "punctuation goes, how lines and paragraphs break, and the statistical regularities every "
        "real text obeys. Tuned first (vocabulary and context), then frozen for shelf experiments.",
        scored="Bits per byte split by kind of byte, and the laws on what it writes",
        metrics=[
            ["inside a word", "bits per byte on letters after the first: spelling", "live"],
            ["word start", "bits per byte on a word's first letter: which word comes next", "live"],
            ["punctuation", "bits per byte on punctuation marks", "live"],
            ["layout", "bits per byte on spaces and line breaks", "live"],
            [
                "non-words",
                "share of words it writes that the shelf never held (books' own rate beside it)",
                "live",
            ],
            [
                "Zipf and Heaps",
                "word frequency against rank; vocabulary growth (against the books)",
                "live",
            ],
            ["word length, punctuation mix", "divergence from the books' distributions", "live"],
            [
                "balance and capitals",
                "unclosed brackets and quotes; capitals after a full stop",
                "live",
            ],
            [
                "traits as they emerge",
                "fiction, verse, first person: at which step and layer each appears while spelling is learned",
                "live",
            ],
        ],
    ),
    dict(
        preset="21m",
        where="this Mac",
        status="waits for 9m to be used up",
        name="The stylist",
        job="Grammar and style: agreement, whole sentences, a register held through a passage",
        overview="Above the word: subject and verb agree across a clause, sentences close, and a "
        "passage keeps one voice (King James, Victorian novel, Greek translation). Also the size for "
        "the Leonardo pilot's second step if 9m shows nothing.",
        scored="Grammatical minimal pairs, loss by position in the window, a register probe",
        metrics=[
            [
                "minimal pairs",
                "grammatical against ungrammatical sentence, period vocabulary",
                "to come",
            ],
            [
                "loss by position",
                "does loss keep falling deep into the 1,024-token window",
                "to come",
            ],
            ["register probe", "can the hidden state tell a passage has changed voice", "to come"],
            ["the 9m laws", "kept, so the rung below stays visible", "live"],
        ],
    ),
    dict(
        preset="50m",
        where="rented GPUs (needs a PyTorch backend)",
        status="not built",
        name="The paragraph",
        job="Paragraphs, and the third point of this corpus's own size curve",
        overview="Sentences that connect into paragraphs, characters and topics that persist; with "
        "9m and 21m it fits this corpus's own loss-against-size curve in place of borrowed constants.",
        scored="The size curve; copy gain and late-in-window loss from the curiosity ladder",
        metrics=[
            [
                "size curve",
                "hole-card loss against parameters, fitted on 9m, 21m and 50m",
                "to come",
            ],
            [
                "in-context copying",
                "copy gain and late-minus-early loss (curiosity ladder)",
                "live",
            ],
        ],
    ),
    dict(
        preset="100m",
        where="rented (about $5 a run) or this Mac (5 to 8 days)",
        status="planned",
        name="The bettor",
        job="The Origin and Leonardo tests: does it bet on an idea before the world did?",
        overview="Trained only on text before a cutoff year, does it find natural selection, or each "
        "of Leonardo's rediscovered ideas, less surprising than the rival accounts of the time? "
        "Betting, not deriving.",
        scored="Matched rival passages in bits per byte, against floors; precursor shelves removed",
        metrics=[
            [
                "Origin preference",
                "selection against fixed species, Lamarck, special creation",
                "to come",
            ],
            [
                "Leonardo timeline",
                "per claim, the cutoff where his version starts to win",
                "to come",
            ],
            [
                "precursor ablation",
                "the preference with Malthus and Lyell taken off, same bytes",
                "to come",
            ],
        ],
    ),
    dict(
        preset="350m",
        where="rented GPUs (about $35 a run)",
        status="planned",
        name="The summit",
        job="The top of the Origin and Leonardo curves",
        overview="The largest model the legal corpus can feed. Its job is to show whether the "
        "preference keeps rising with size; at the 1858 cutoff it is short of data.",
        scored="As for 100m",
        metrics=[
            [
                "Origin and Leonardo curves",
                "the same tests, the top point of the size curve",
                "to come",
            ]
        ],
    ),
]


def _gpt_mlx(cfg: GPTConfig):
    from thorp.models.gpt_mlx import GPT

    return GPT(cfg)


def _gpt_torch(cfg: GPTConfig):
    from thorp.models.gpt_torch import GPT

    return GPT(cfg)


FAMILIES = {"gpt": _gpt_mlx}
TORCH_FAMILIES = {"gpt": _gpt_torch}  # the same models in PyTorch (CUDA), thorp/models/backend.py


def config(preset: str, vocab: int, context: int, positions: str = "learned") -> GPTConfig:
    if preset not in PRESETS:
        raise KeyError(f"unknown preset {preset!r}; known: {sorted(PRESETS)}")
    if positions not in ("learned", "rope"):
        raise KeyError(f"unknown positions {positions!r}; known: learned, rope")
    return GPTConfig(**PRESETS[preset], vocab=vocab, context=context, positions=positions)


def build(
    family: str, preset: str, vocab: int, context: int, positions: str = "learned", backend: str = "mlx"
):
    families = TORCH_FAMILIES if backend == "torch" else FAMILIES
    if family not in families:
        raise KeyError(f"unknown model family {family!r} for {backend}; known: {sorted(families)}")
    return families[family](config(preset, vocab, context, positions))

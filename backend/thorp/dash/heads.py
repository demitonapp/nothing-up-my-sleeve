"""The star chart: every kind of attention head described in the interpretability literature, for
the Discoveries page (2026-11-07, Justin: "add all known induction and attention heads").

A kind Nothing up my sleeve measures links to its star in `thorp.fleet.STARS` (`star`), and the page shows its live
state from the ledger. The rest are charted but not yet measured: each says what it does, what it
rests on, where it was first described, what size of model it has been seen in, and how Nothing up my sleeve could
measure it. Promoting one to a star is the fleet's job (fleet.STARS plus an evaluator); this list
only charts the sky.

`expected_class` is the smallest class of ship expected to reach the kind, by class name (the
ladder's names less "The", as in the page's addresses: "keel", "speller"…), a prediction
written down before it is tested (None: beyond the ladder). The server turns it into the class's
preset from the registry, so no size is written here. The floor is depth: each layer gives a head one hop,
so a mechanism of k heads in sequence needs at least k layers; width, data, vocabulary and context
decide the rest. `expected_why` says why in a line. The page sets it beside "first lit in", the
smallest class where a sailing actually lit it: a star lit below its expected class is a discovery.

`trick` names the trick in `thorp.fleet.TRICKS` the kind is thought to perform, where one is
measured: a trick is what a model can do, judged by its bets from outside; a star is the mechanism
inside that does it (DECISIONS.md, "Tricks and stars").

`rests_on` lists only dependencies the source reports (the indirect-object circuit's chain, and
induction resting on a previous-token head); a blank list means none reported, not none exists.

Families: "position" (attends by where a token is), "copying" (finds an earlier token and carries
it forward), "circuit" (a role in a larger named circuit), "suppression" (pushes a prediction down),
"structure" (follows grammar or reference), "task" (carries what the prompt is asking for).
"""

from __future__ import annotations

ELHAGE_2021 = "Elhage et al. 2021, A Mathematical Framework for Transformer Circuits"
OLSSON_2022 = "Olsson et al. 2022, In-context Learning and Induction Heads"
WANG_2022 = "Wang et al. 2022, Interpretability in the Wild: a Circuit for Indirect Object Identification in GPT-2 small"
VOITA_2019 = (
    "Voita et al. 2019, Analyzing Multi-Head Self-Attention: Specialized Heads Do the Heavy Lifting"
)
CLARK_2019 = "Clark et al. 2019, What Does BERT Look At? An Analysis of BERT's Attention"

KNOWN_HEADS: list[dict] = [
    # ------------------------------------------------------------------ position
    {
        "key": "attention_sink",
        "expected_class": "keel",
        "expected_why": "one hop: a single layer can rest its attention on the first token",
        "name": "Attention sink",
        "family": "position",
        "does": "Puts most of its attention on the first token of the window whatever comes, a resting place for a head with nothing to do.",
        "rests_on": [],
        "source": "Xiao et al. 2023, Efficient Streaming Language Models with Attention Sinks",
        "seen_in": "language models across sizes",
        "star": "attention_sink",
        "measure": "Mean attention to position 0 (Nothing up my sleeve's windows start with an end-of-text token) over every query; cheap, from the same attention patterns the stars use.",
    },
    {
        "key": "previous_token",
        "expected_class": "keel",
        "expected_why": "one hop: a single layer can attend by position",
        "name": "Previous-token head",
        "family": "position",
        "does": "At each word, attends to the word just before it, so the next layer knows what came before.",
        "rests_on": [],
        "source": ELHAGE_2021,
        "seen_in": "small models early in training; the first piece of an induction head",
        "star": "previous_word",
        "measure": "",
    },
    {
        "key": "offset_2",
        "expected_class": "keel",
        "expected_why": "one hop: a single layer can attend by position",
        "name": "Positional head: two words back",
        "family": "position",
        "does": "Attends to the token two back, whatever it is: a fixed offset (the previous-token head is offset one).",
        "rests_on": [],
        "source": VOITA_2019,
        "seen_in": "translation encoders and BERT",
        "star": "offset_2",
        "measure": "The previous-word test at offsets 2 and 3: mean attention from each token to the token k back.",
    },
    {
        "key": "offset_3",
        "expected_class": "keel",
        "expected_why": "one hop: a single layer can attend by position",
        "name": "Positional head: three words back",
        "family": "position",
        "does": "Attends to the token three back, whatever it is: a fixed offset.",
        "rests_on": [],
        "source": VOITA_2019,
        "seen_in": "translation encoders and BERT",
        "star": "offset_3",
        "measure": "The previous-word test at offsets 2 and 3: mean attention from each token to the token k back.",
    },
    {
        "key": "delimiter",
        "expected_class": "keel",
        "expected_why": "one hop: a single layer can find punctuation by its token",
        "name": "Delimiter head",
        "family": "position",
        "does": "Attends to separators and punctuation (full stops, line breaks, special tokens).",
        "rests_on": [],
        "source": CLARK_2019,
        "seen_in": "BERT",
        "star": "delimiter",
        "measure": "Share of attention landing on punctuation and newline tokens, against their share of the window.",
    },
    {
        "key": "rare_word",
        "expected_class": "keel",
        "expected_why": "one hop, once the embeddings know which tokens are rare",
        "name": "Rare-word head",
        "family": "position",
        "does": "Attends to the least frequent words in the sentence.",
        "rests_on": [],
        "source": VOITA_2019,
        "seen_in": "translation encoders",
        "star": "rare_word",
        "measure": "Correlation between attention received and the token's rarity on the shelf.",
    },
    # ------------------------------------------------------------------ copying
    {
        "key": "duplicate_token",
        "expected_class": "keel",
        "expected_why": "one hop: match the current token against earlier ones",
        "name": "Duplicate-token head",
        "family": "copying",
        "does": "At a word, attends to where the same word appeared before: noticing that Darcy has been mentioned already.",
        "rests_on": [],
        "source": WANG_2022,
        "seen_in": "GPT-2 small",
        "star": "duplicate_word",
        "measure": "",
    },
    {
        "key": "induction",
        "trick": "copying",
        "expected_class": "keel",
        "expected_why": "two hops, a previous-token head below and the induction head above; two layers is the minimum",
        "name": "Induction head (Nevermore)",
        "family": "copying",
        "does": "At a word seen before, attends to the word that followed it last time and bets it comes again: [A][B] … [A] → [B].",
        "rests_on": ["previous_token"],
        "source": OLSSON_2022,
        "seen_in": "models from two layers up; forms suddenly in training",
        "star": "nevermore",
        "measure": "",
    },
    {
        "key": "fuzzy_induction",
        "expected_class": "speller",
        "expected_why": "needs embeddings that put a word's forms (case, plural) near each other",
        "name": "Fuzzy and translation induction head",
        "family": "copying",
        "does": "Induction on near matches rather than exact ones: a word in another case or form, or the same sentence in another language.",
        "rests_on": ["induction"],
        "source": OLSSON_2022,
        "seen_in": "larger models in that paper",
        "star": None,
        "measure": "The Nevermore test with the second copy changed: capitalised, pluralised, or a parallel translation (Nothing up my sleeve's shelves hold several languages).",
    },
    {
        "key": "retrieval",
        "expected_class": None,
        "expected_why": "found only in long-context models of billions of parameters: beyond the ladder",
        "name": "Retrieval head",
        "family": "copying",
        "does": "Finds a fact stated far back in a long context and copies it out: the needle-in-a-haystack heads.",
        "rests_on": [],
        "source": "Wu et al. 2024, Retrieval Head Mechanistically Explains Long-Context Factuality",
        "seen_in": "long-context models of billions of parameters",
        "star": None,
        "measure": "A needle test across the 1,024-token window: plant a short phrase early, prompt for it late, score the head's attention to the needle.",
    },
    {
        "key": "successor",
        "trick": "successor",
        "expected_class": "stylist",
        "expected_why": "needs the order of numbers, days and months held in its weights",
        "name": "Successor head",
        "family": "copying",
        "does": "Given an item of an ordered series, pushes up the next one: Monday → Tuesday, 3 → 4, March → April.",
        "rests_on": [],
        "source": "Gould et al. 2023, Successor Heads: Recurring, Interpretable Attention Heads In The Wild",
        "seen_in": "many models across sizes",
        "star": None,
        "measure": "Prompts of numbers, weekdays, months and letters: does attending to an item raise the logit of its successor more than any other item's?",
    },
    # ------------------------------------------------------------------ the indirect-object circuit
    {
        "key": "s_inhibition",
        "expected_class": "explorer",
        "expected_why": "four or more hops in sequence; found in GPT-2 small, the shape of the 100m (12 x 768)",
        "name": "S-inhibition head",
        "family": "circuit",
        "does": "In 'When Mary and John went to the store, John gave a drink to', marks that John is repeated, so later heads leave him out.",
        "rests_on": ["duplicate_token", "induction"],
        "source": WANG_2022,
        "seen_in": "GPT-2 small",
        "star": None,
        "measure": "Indirect-object prompts in period English; the head's effect on name movers' attention to the repeated name when patched.",
    },
    {
        "key": "name_mover",
        "expected_class": "explorer",
        "expected_why": "four or more hops in sequence; found in GPT-2 small, the shape of the 100m (12 x 768)",
        "name": "Name mover head",
        "family": "circuit",
        "does": "Attends to the name not yet repeated and copies it to the answer: Mary.",
        "rests_on": ["s_inhibition"],
        "source": WANG_2022,
        "seen_in": "GPT-2 small",
        "star": "mover",
        "measure": "Attention from the last token to the indirect object on those prompts, and the head's direct push on the logit of that name.",
    },
    {
        "key": "backup_name_mover",
        "expected_class": "explorer",
        "expected_why": "redundancy beside the name movers; found in GPT-2 small",
        "name": "Backup name mover head",
        "family": "circuit",
        "does": "Does a name mover's job only when the name movers are knocked out: redundancy the model builds in.",
        "rests_on": ["name_mover"],
        "source": WANG_2022,
        "seen_in": "GPT-2 small",
        "star": None,
        "measure": "Ablate the name movers and see which heads start moving the name.",
    },
    {
        "key": "comparator",
        "expected_class": "stylist",
        "expected_why": "a single comparison read off the number words; found in GPT-2 small, but one hop, so a smaller ship may hold it",
        "name": "Comparator (greater-than) head",
        "family": "circuit",
        "does": "Orders two quantities: attends from the answer to the start year in 'from 1732 to 17' and pushes up the years after it; for the between and order items.",
        "rests_on": [],
        "source": "Hanna, Liu and Variengien 2023, How does GPT-2 compute greater-than?",
        "seen_in": "GPT-2 small",
        "star": "comparator",
        "measure": "Comparison prompts: the best head's share of attention on the quantity compared, and its push toward the larger (stars/comparator, provisional threshold 0.3).",
    },
    {
        "key": "bridge",
        "expected_class": "paragraph",
        "expected_why": "the middle term must be resolved in the middle layers, before the second hop: two hops need depth",
        "name": "Bridge (the middle term)",
        "family": "latent",
        "does": "Not a head but a state: the term two premises share (the slowest deer) present at the answer's position in the middle layers. Resolving it too late is how two-hop reasoning fails.",
        "rests_on": ["name_mover"],
        "source": "Yang et al. 2024, Do Large Language Models Latently Perform Multi-Hop Reasoning?; Biran et al. 2024, Hopping Too Late",
        "seen_in": "Llama 2, and larger models",
        "star": "bridge",
        "measure": "The soundings read at each layer how strongly the answer's position carries the bridge word (stars/bridge/layer_<i>, in nats; provisional threshold 0.5).",
    },
    # ------------------------------------------------------------------ suppression
    {
        "key": "negative_name_mover",
        "expected_class": "explorer",
        "expected_why": "beside the name movers in the same circuit; found in GPT-2 small",
        "name": "Negative name mover head",
        "family": "suppression",
        "does": "Attends to the right name and pushes its logit down, hedging the model's bet.",
        "rests_on": [],
        "source": WANG_2022,
        "seen_in": "GPT-2 small",
        "star": None,
        "measure": "On indirect-object prompts, a negative direct effect on the logit of the name it attends to.",
    },
    {
        "key": "copy_suppression",
        "expected_class": "paragraph",
        "expected_why": "sits above the copying heads late in the stack; found in a 12-layer model",
        "name": "Copy-suppression head",
        "family": "suppression",
        "does": "When a word earlier in the text is being over-predicted, attends to it and pushes it down: the brake on copying.",
        "rests_on": ["induction"],
        "source": "McDougall et al. 2023, Copy Suppression: Comprehensively Understanding an Attention Head",
        "seen_in": "GPT-2 small",
        "star": None,
        "measure": "On repeated text, heads that attend to an earlier copy of a token and lower that token's logit.",
    },
    # ------------------------------------------------------------------ structure
    {
        "key": "syntactic",
        "expected_class": "paragraph",
        "expected_why": "needs grammar in the hidden state; found in 12-layer encoders",
        "name": "Syntactic head",
        "family": "structure",
        "does": "Follows a grammatical relation: from a verb to its subject or object, from a noun to its determiner.",
        "rests_on": [],
        "source": f"{VOITA_2019}; {CLARK_2019}",
        "seen_in": "translation encoders and BERT",
        "star": None,
        "measure": "Parse held-out sentences and score each head's attention along each dependency arc against chance.",
    },
    {
        "key": "coreference",
        "expected_class": "paragraph",
        "expected_why": "needs names and pronouns tracked in the hidden state; found in 12-layer encoders",
        "name": "Coreference head",
        "family": "structure",
        "does": "From a pronoun, attends to the name it stands for: from 'she' back to Elizabeth.",
        "rests_on": [],
        "source": CLARK_2019,
        "seen_in": "BERT",
        "star": None,
        "measure": "Passages with marked pronoun-antecedent pairs; attention from the pronoun to its antecedent against other names in the window.",
    },
    # ------------------------------------------------------------------ task
    {
        "key": "function_vector",
        "expected_class": None,
        "expected_why": "found only in models of billions of parameters: beyond the ladder",
        "name": "Function-vector head",
        "family": "task",
        "does": "From a few examples in the prompt (hot → cold, big → small), carries what the task is, so the model does it on the next word.",
        "rests_on": [],
        "source": "Todd et al. 2023, Function Vectors in Large Language Models",
        "seen_in": "models of billions of parameters",
        "star": None,
        "measure": "Few-shot antonym and translation prompts; heads whose mean output, added to a zero-shot prompt, makes the model do the task.",
    },
]

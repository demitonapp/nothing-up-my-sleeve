"""The library's branches (Justin, 2026-11-08: "it has to start with branches of the library and those branches will
have different purposes. So currently we have Ogden with variations on it. So I'd like to be able to open the Ogden
branch and then explore what's in that branch").

A **branch** is a purpose the library's books are gathered for (Ogden: one fixed corpus every class reads; the decks:
yardsticks never read; ...). A branch holds **variations**, each a set of books defined one of three ways:
a `list` (a list in lists/, as a recipe reads it), a `spec` (a selection, thorp/selection.py, composed over the
library's facts: no list is written), or `all` (every book in the library). A variation may say what it was
`derived_from` and whether it is a `draft` that never sails. The Library page opens on the branches; a branch opens
to its variations; a variation opens to the same cards and filters the whole library has, scoped to its books.

The branches are Justin's to shape: stored in Postgres (`s3.library_branches`, `s3.library_variations`) by
`thorp select branches seed`, which writes these defaults and never removes what he has changed by hand.
"""

from __future__ import annotations

DEFAULTS: list[dict] = [
    {
        "key": "ogden", "name": "Ogden",
        "purpose": "One fixed corpus every class reads, so ships differ in size alone: whole books ranked by Ogden-ness "
                   "(the share of ordinary words in Ogden's 850), and the variations on it.",
        "variations": [
            {"key": "ogden-v0.1", "name": "Ogden v0.1", "list": "lists/ogden-v0.1.csv",
             "about": "The 592 store books at Ogden-ness 68% or more (7 November). What the first voyages read."},
            {"key": "ogden-v0.2", "name": "Ogden v0.2", "list": "lists/ogden-v0.2.csv", "derived_from": "ogden-v0.1",
             "about": "v0.1's rule over the whole library, the Bible struck, and the logic tutor's passages at 7.5% (8 November)."},
            {"key": "ogden-v0.2-declared", "name": "Ogden v0.2, declared", "list": "lists/composed/ogden-v0-2-declared-1.csv",
             "derived_from": "ogden-v0.2", "draft": True,
             "about": "v0.2 composed from a declared selection: the same books in the same order. A draft that never sails."},
            {"key": "ogden-candidates", "name": "Ogden-ness 68%+, now", "derived_from": "ogden-v0.2",
             "spec": {"languages": {"en": 1.0}, "ogden": {"min": 0.68}},
             "about": "Every English recipe book in the library at 68% or more today (the gate's rules applied): "
                      "what a v0.3 could draw on. Not a list; a selection."},
        ],
    },
    {
        "key": "library", "name": "The whole library",
        "purpose": "Everything fetched: the pool every selection draws on.",
        "variations": [{"key": "everything", "name": "Every book", "all": True,
                        "about": "Every book in the manifest that is not one of Thorp's own derived texts."}],
    },
    {
        "key": "scanned", "name": "The scanned corpus",
        "purpose": "Beyond Gutenberg: the scans of the original editions (Common Pile's HathiTrust and Library of "
                   "Congress books, the British Library's books, the newspapers). A branch of its own, with its own "
                   "vocabulary and OCR noise, so lifting Ogden's plain-English rule for it never changes what Ogden reads.",
        "variations": [
            {"key": "scanned-all", "name": "Every scanned book", "spec": {"languages": {"en": 1.0},
             "sources": {"include": ["common-pile-pre-1929", "common-pile-loc", "blbooks", "incunabula", "americanstories", "archive"]}},
             "about": "Every English scanned volume the gather pipeline admitted, through the same gate."},
            {"key": "scanned-before-1858", "name": "Before 1858 (the Origin shelf)", "spec": {"languages": {"en": 1.0},
             "period": {"end": 1857, "undated": "exclude"},
             "sources": {"include": ["common-pile-pre-1929", "common-pile-loc", "blbooks"]}},
             "about": "Scans whose printing year is before 1858: the Origin test's shelf, dated by the imprint rather than by a death year."},
            {"key": "scanned-blbooks", "name": "The British Library", "spec": {"languages": {"en": 1.0},
             "sources": {"include": ["blbooks"]}}, "about": "CC0, c.1510–1900, the longest reach back in English print."},
            {"key": "scanned-incunabula", "name": "Incunabula (pre-1501)", "list": "lists/incunabula.csv",
             "about": "The first printed books, 1450–1500, from the Boston Public Library's open incunabula set: mostly Latin, six English."},
            {"key": "scanned-common-pile", "name": "Common Pile books", "spec": {"languages": {"en": 1.0},
             "sources": {"include": ["common-pile-pre-1929", "common-pile-loc"]}},
             "about": "HathiTrust pre-1929 and the Library of Congress's Selected Digitized Books."},
            {"key": "scanned-newspapers", "name": "Newspapers", "spec": {"languages": {"en": 1.0},
             "sources": {"include": ["americanstories"]}},
             "about": "Chronicling America pages, unsigned: the S5 question the 'signed' rule would settle."},
        ],
    },
    {
        "key": "ancient", "name": "The ancient world",
        "purpose": "Greek, Latin and Sumerian texts as a discovery branch of their own: not English recipes, and not "
                   "ranked by Ogden-ness. Perseus's TEI editions and ETCSL's transliterations, kept for the day a ship "
                   "wants to read them.",
        "variations": [
            {"key": "ancient-latin", "name": "Perseus Latin", "list": "lists/perseus-latin.csv",
             "about": "344 Latin editions from the Perseus Digital Library, CC BY-SA 4.0."},
            {"key": "ancient-greek", "name": "Perseus Greek", "list": "lists/perseus-greek.csv",
             "about": "799 Ancient Greek editions from the Perseus Digital Library, CC BY-SA 4.0."},
            {"key": "ancient-cuneiform", "name": "ETCSL (Sumerian)", "list": "lists/etcsl.csv",
             "about": "Sumerian literary compositions with transliteration and English translation, from ETCSL."},
            {"key": "ancient-cdli", "name": "CDLI (cuneiform)", "list": "lists/cdli-sux.csv",
             "about": "CDLI's Sumerian transliterations, grouped into three volumes of 2M characters."},
        ],
    },
    {
        "key": "decks", "name": "Decks and yardsticks",
        "purpose": "Books ships are scored on and never read: the hole cards, the Forgotten Tomes, the truths, the held-out content books.",
        "variations": [
            {"key": "hole-cards", "name": "Hole cards", "list": "lists/hole-cards.csv", "about": "The first held-out deck; refused by every run."},
            {"key": "hole-cards-v2", "name": "Hole cards II", "list": "lists/hole-cards-v2.csv", "about": "The second held-out deck."},
            {"key": "forgotten-tomes", "name": "The Forgotten Tomes", "list": "lists/hole-cards-unseen.csv",
             "about": "Books released on Gutenberg after Qwen 3.8: the yardstick no outside model has read."},
            {"key": "truths", "name": "Truths", "list": "lists/truths.csv", "about": "The treatises the probes score."},
            {"key": "held-greek", "name": "Held Greek", "list": "lists/held-greek.csv", "about": "The content experiment's held-out Greek."},
            {"key": "held-islamic", "name": "Held Islamic", "list": "lists/held-islamic.csv", "about": "The content experiment's held-out Islamic."},
            {"key": "held-renaissance", "name": "Held Renaissance", "list": "lists/held-renaissance.csv", "about": "The content experiment's held-out Renaissance."},
        ],
    },
    {
        "key": "content", "name": "Content experiment",
        "purpose": "Does what a ship reads shape what it becomes: Greek, Islamic, Renaissance, about-the-world and three random draws.",
        "variations": [
            {"key": "content-greek", "name": "Greek", "list": "lists/content-greek.csv", "about": "What Athens Wrote."},
            {"key": "content-islamic", "name": "Islamic", "list": "lists/content-islamic.csv", "about": "Mostly The Thousand Nights."},
            {"key": "content-renaissance", "name": "Renaissance", "list": "lists/content-renaissance.csv", "about": "Florence."},
            {"key": "content-about", "name": "About", "list": "lists/content-about.csv", "about": "The about-the-world draw."},
            {"key": "content-random-1", "name": "Random 1", "list": "lists/content-random-1.csv", "about": "Whatever Washed Ashore."},
            {"key": "content-random-2", "name": "Random 2", "list": "lists/content-random-2.csv", "about": "Something Else Washed Ashore."},
            {"key": "content-random-3", "name": "Random 3", "list": "lists/content-random-3.csv", "about": "A Third Tide's Worth."},
        ],
    },
    {
        "key": "levers", "name": "Data levers and pools",
        "purpose": "The 9m sweep and the speller's pools: distinct text against total reading, fiction against non-fiction, verse.",
        "variations": [
            {"key": "pool-100", "name": "Lever: 100 books", "list": "lists/pool-100.csv", "about": "Distinct text against total reading."},
            {"key": "pool-200", "name": "Lever: 200 books", "list": "lists/pool-200.csv", "derived_from": "pool-100", "about": "As above, 200 books."},
            {"key": "pool-400", "name": "The speller's pool", "list": "lists/pool-400.csv", "derived_from": "pool-200", "about": "The 9m sweep's 400-book shelf."},
            {"key": "pool-800", "name": "Lever: 800 books", "list": "lists/pool-800.csv", "derived_from": "pool-400", "about": "As above, 800 books."},
            {"key": "pool-400-fiction", "name": "The speller's fiction", "list": "lists/pool-400-fiction.csv", "derived_from": "pool-400",
             "about": "Hispaniola's shelf: the fiction half."},
            {"key": "pool-400-nonfiction", "name": "The speller's non-fiction (Mayflower)", "list": "lists/pool-400-nonfiction.csv",
             "derived_from": "pool-400", "about": "Mayflower's shelf: the non-fiction half."},
            {"key": "pool-400-spellers", "name": "The spellers", "list": "lists/pool-400-spellers.csv", "about": "Spelling books and primers for the speller curriculum."},
            {"key": "stars-pool", "name": "The mixed pool", "list": "lists/stars-pool.csv", "about": "Fiction, non-fiction and verse together."},
            {"key": "stars-fiction", "name": "English-original fiction", "list": "lists/stars-fiction.csv", "about": "First Light's and the keel's reading."},
            {"key": "stars-fiction-shuffled", "name": "Shuffled fiction", "list": "lists/stars-fiction-shuffled.csv", "derived_from": "stars-fiction",
             "about": "The same books with every book's words shuffled (the control)."},
            {"key": "stars-verse", "name": "Verse", "list": "lists/stars-verse.csv", "about": "Poetry as a kind of its own."},
            {"key": "loop-pool", "name": "The loop pool", "list": "lists/loop-pool.csv", "about": "The book-value loop's pool."},
        ],
    },
    {
        "key": "early", "name": "The stores and early shelves",
        "purpose": "What the first ships read before Ogden: the two stores, the nursery, the legal, reasoning and cause shelves, dialogue, Britannica.",
        "variations": [
            {"key": "store-prose", "name": "The prose stores", "list": "lists/stores/prose.csv", "about": "Novels and stories at or above the bar."},
            {"key": "store-trigram", "name": "The trigram stores", "list": "lists/stores/trigram.csv", "about": "Everything else with variety."},
            {"key": "nursery", "name": "The nursery", "list": "lists/keel-nursery.csv", "about": "English children's books: picture books, primers, Mother Goose."},
            {"key": "legal", "name": "The legal shelf", "list": "lists/law-shelf.csv", "about": "The causal skeleton's law, from the period."},
            {"key": "reasoning", "name": "The reasoning shelf", "list": "lists/reasoning-shelf.csv", "about": "Logic, geometry, Plato, Descartes, Bacon, Faraday."},
            {"key": "cause", "name": "The cause-and-effect shelf", "list": "lists/cause-shelf.csv", "about": "Period how-to books: cookery, household, gardening."},
            {"key": "dialogue", "name": "Formulaic dialogue", "list": "lists/dialogue-shelf.csv", "about": "The repetition engine's dialogue, from the period."},
            {"key": "britannica", "name": "Britannica, 11th edition", "list": "lists/britannica-11.csv", "about": "The 1911 encyclopaedia."},
            {"key": "precursors", "name": "The precursors (Internet Archive)", "list": "lists/precursors-archive.csv", "about": "Scanned editions of the discovery tests' precursors."},
        ],
    },
]


def variation_ids(v: dict, facts: list[dict]) -> list[str]:
    """The book ids a variation holds, in the library's facts: a list's books, a selection composed, or every book."""
    have = {f["book"] for f in facts}
    if v.get("all"):
        return [f["book"] for f in facts if f["source"] != "local"]
    if v.get("spec"):
        from thorp import selection

        return [b["book"] for b in selection.compose(v["spec"], facts).books]
    if v.get("list"):
        from thorp import library, paths

        p = paths.resolve(v["list"])
        if not p.exists():
            return []
        ids = library._ids(p, v["list"], library._rows(p), library._resolved())
        return [i for i in dict.fromkeys(ids) if i in have]
    return []

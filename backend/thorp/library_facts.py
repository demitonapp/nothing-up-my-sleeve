"""What the library knows about each book, so a fitout can be composed from declared weights and filters
(Justin, 2026-11-08: "our fitouts or the part of it that controls what the books are should be able to have
weights, so I should be able to weight by language ... weight by ogdenish as we already do, then also choose a
time period, both a start and an end date, then it should have filters for content type. Novels, poems,
textbooks, etc."; and "we need to have sources, things like the library and the clergy for example will have
different biases. We need to track this early and transparently").

One row of facts per book in the manifest (data/manifest.sqlite), derived from the manifest, the Project
Gutenberg catalogue (data/catalogue/pg_catalog.csv) and the Ogden-ness scores (lists/ogden-*-scores.csv). Every
derived fact carries the rule that gave it (`year_basis`, `kind_rule`, `voice_rule`), so a book's place in a
count can always be traced to the words that put it there. The rules are the tables below, shown on the
dashboard as they are written here.

The facts are a pure function of those three inputs: `build()` returns the same rows for the same inputs, and
`fingerprint(rows)` names them, so a composition can say which facts it was drawn from.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter

from thorp import paths

FACTS_VERSION = 1
CHARS_PER_WORD = 5.7  # the library's own estimate (scripts/make_ogden_v02.py)

# ---- the date -------------------------------------------------------------------------------------------
# No catalogue we hold carries a publication or first-edition year (Project Gutenberg's "Issued" is the day the
# volunteers released the file). What it carries is the credited names' birth and death years. A book's
# year is therefore estimated, in this order, and the basis kept:
#   published  the year the library recorded when it fetched the book (archive.org books: "published 1812")
#   floruit    the writer's birth year + FLORUIT_AGE (capped at their death year): the classical convention
#              for dating a writer whose works are undated is the age of forty
#   late       when only the death year is known: death year - LATE_BEFORE_DEATH
#   undated    no usable year: the book has none, and a period with bounds leaves it out unless the
#              selection says `undated: include`
# "The writer" is the name whose English the book is in: the translator if one is credited, else the first
# credited name with no role, else the first credited name with dates (an editor, for a volume by "Various").
FLORUIT_AGE = 40
LATE_BEFORE_DEATH = 25
GATE_DEATH_LIMIT = 1955  # S5 'period': no credited name dead after this (liberty_machine._period_only)

_YEAR = r"(\d{1,4})\??(?:\s*(BC))?"
_LIFE = re.compile(rf"{_YEAR}\s*-\s*(?:{_YEAR})?")
_DIED_ONLY = re.compile(r"(?:\?|,\s)\s*-\s*(\d{1,4})\??(?:\s*(BC))?\s*$")
_ROLE = re.compile(r"\[([^\]]*)\]\s*$")


def _signed(n: str | None, bc: str | None) -> int | None:
    if not n:
        return None
    return -int(n) if bc else int(n)


def credits(authors: str) -> list[dict]:
    """The catalogue's credited names: name, role (None for an author), born, died."""
    out = []
    for part in (authors or "").split("; "):
        part = part.strip()
        if not part:
            continue
        m = _ROLE.search(part)
        role = m.group(1).strip() if m else None
        body = _ROLE.sub("", part).strip()
        life = _LIFE.search(body)
        born = died = None
        if life:
            born = _signed(life.group(1), life.group(2))
            died = _signed(life.group(3), life.group(4))
        else:
            gone = _DIED_ONLY.search(body)  # "Someone, -1900" or "Someone, ?-1900": a death year alone
            if gone:
                died = _signed(gone.group(1), gone.group(2))
        out.append({"name": body, "role": role, "born": born, "died": died})
    return out


def gate_death(authors: str) -> int | None:
    """The latest death year the period gate sees (liberty_machine._deaths, the same pattern): over every credited name."""
    ys = [int(y) for y in re.findall(r"\d{4}-(\d{4})", authors or "")]
    return max(ys) if ys else None


def writer(cs: list[dict]) -> dict | None:
    for c in cs:
        if c["role"] and c["role"].lower().startswith("translator"):
            return c
    for c in cs:
        if not c["role"] and (c["born"] is not None or c["died"] is not None):
            return c
    for c in cs:
        if c["born"] is not None or c["died"] is not None:
            return c
    return None


def year_of(authors: str, note: str = "") -> tuple[int | None, str, int | None, int | None]:
    """(year, basis, writer's born, writer's died) for a book."""
    m = re.search(r"published (\d{4})", note or "")
    w = writer(credits(authors))
    born, died = (w["born"], w["died"]) if w else (None, None)
    if m:
        return int(m.group(1)), "published", born, died
    if born is not None:
        y = born + FLORUIT_AGE
        if died is not None:
            y = min(y, died)
        return y, "floruit", born, died
    if died is not None:
        return died - LATE_BEFORE_DEATH, "late", born, died
    return None, "undated", born, died


# ---- the kind -------------------------------------------------------------------------------------------
# One kind to a book, the first rule that matches, in this order. A rule reads the catalogue's subjects (the
# Library of Congress subject headings), its bookshelves (Project Gutenberg's categories) and its LoC class.
# "shelf:" names a bookshelf exactly; a pattern is matched, case-blind, against the subjects (and the title
# where the rule says so). The order is the judgement: a sermon about a play is a sermon.
KINDS = (
    "novel", "stories", "poem", "play", "essay", "sermon", "dialogue", "textbook", "history", "biography",
    "travel", "philosophy", "religion", "science", "reference", "periodical", "practical", "other", "derived",
)  # fmt: skip

KIND_ABOUT = {
    "novel": "a long work of fiction, romance, adventure or mystery",
    "stories": "short stories, tales, fairy tales, fables and folklore",
    "poem": "verse: poetry, ballads, hymns, songs, nursery rhymes",
    "play": "drama, comedy, tragedy, opera and libretti",
    "essay": "essays, letters, speeches, lectures and addresses",
    "sermon": "sermons and homilies",
    "dialogue": "works in the form of a dialogue (Plato's, Berkeley's, Landor's imaginary conversations)",
    "textbook": "school books, primers, readers, spellers and manuals of a subject",
    "history": "history, in any period or country",
    "biography": "lives, memoirs, autobiography, diaries and journals",
    "travel": "voyages, travels and descriptions of places",
    "philosophy": "philosophy and ethics",
    "religion": "scripture, theology and devotion that is not a sermon",
    "science": "natural science, medicine, engineering and mathematics",
    "reference": "encyclopedias, dictionaries and handbooks",
    "periodical": "a volume of a magazine or journal (Punch, Notes and Queries)",
    "practical": "how-to, cookery, sport, trades, etiquette, gardening",
    "other": "law, politics, economics, art, music and what no rule above names",
    "derived": "made by Nothing up my sleeve: the logic tutor's passages and the shuffled-word controls",
}  # fmt: skip

# (kind, rule text, subject pattern or None, bookshelves (exact) or (), LoC class prefixes or (), title pattern or None)
_R = [
    ("periodical", r"periodicals", (), (), None),
    ("sermon", r"\bsermons?\b|\bhomil", (), (), r"\bsermons?\b"),
    ("dialogue", r"\bdialogues?\b|socratic", (), (), r"^(the )?dialogues?\b|\bdialogues? (of|between|on|concerning)\b"),
    ("textbook", r"textbooks?|\bprimers?\b|\breaders?\b|\bspellers?\b|spelling|elementary education|arithmetic|"
                 r"algebra|geometry|grammar|\bstudy and teaching\b|schoolbooks?|copy-?books?",
     ("Children's Instructional Books", "Category: Teaching & Education"), (),
     r"\b(primer|reader|speller|spelling[- ]book|arithmetic|grammar|algebra|geometry|elements of|first book|textbook|catechism)\b"),
    ("play", r"\b(drama|dramas|plays?|comed(y|ies)|traged(y|ies)|tragicomedy|operas?|librettos?|masques?|farces?|"
             r"pageants?|monologues?)\b", ("One Act Plays", "Opera"), (), None),
    ("poem", r"\b(poetry|poems?|ballads?|verse|songs?|hymns?|nursery rhymes|sonnets?|epic|odes?|elegies|limericks?|"
             r"lyrics?)\b", ("Category: Poetry", "Poetry"), (), None),
    ("stories", r"short stories|\btales\b|fairy tales|\bfables?\b|folklore|legends|myths?|ghost stories|"
                r"christmas stories|children's stories|animal stories|\bsketches\b|picture books", ("Category: Short Stories",), (), None),
    ("novel", r"\b(fiction|romances?|novels?|bildungsromans|love stories|adventure stories|detective|mystery|"
              r"western stories|war stories|humorous stories|historical fiction|science fiction|sea stories)\b",
     ("Category: Novels", "Category: Historical Novels", "Category: Crime, Thrillers and Mystery",
      "Category: Science-Fiction & Fantasy", "Category: Romance", "Category: Adventure"), ("PR", "PS", "PZ", "PQ", "PT"), None),
    ("essay", r"\b(essays?|letters|speeches|addresses|orations?|lectures?|aphorisms|correspondence|sayings|"
              r"maxims|quotations)\b", ("Category: Essays, Letters & Speeches",), (), None),
    ("biography", r"\b(biography|biographies|memoirs?|autobiograph\w*|diaries|diary|journals?|reminiscences)\b",
     ("Category: Biographies", "Category: Journals"), (), None),
    ("travel", r"\b(description and travel|voyages and travels|travel|voyages|explorers?|pilgrimages?)\b",
     ("Category: Travel Writing",), (), None),
    ("reference", r"\b(encyclopedias|dictionaries|gazetteers|handbooks|directories|almanacs?|glossaries)\b",
     ("Category: Encyclopedias/Dictionaries/Reference",), (), None),
    ("history", r"\bhistory\b|\bwars?\b|\bkings and rulers\b|\bhistorical\b|\bcivilization\b",
     tuple(f"Category: History - {x}" for x in
           ("American", "British", "European", "Modern (1750+)", "Other", "Ancient", "Warfare", "Royalty",
            "Religious", "Early Modern (c. 1450-1750)", "Medieval/Middle Ages")), ("D", "E"), None),
    ("philosophy", r"\b(philosophy|ethics|metaphysics|logic|moral)\b", ("Category: Philosophy & Ethics",), ("B",), None),
    ("religion", r"\b(bible|theology|christian\w*|church|prayers?|devotion\w*|god|buddhism|islam|religion)\b",
     ("Category: Religion/Spirituality",), ("BL", "BM", "BP", "BQ", "BR", "BS", "BT", "BV", "BX"), None),
    ("science", r"\b(science|natural history|medicine|anatomy|physics|chemistry|botany|zoology|geology|astronomy|"
                r"mathematics|engineering|biology|electricity|mechanics|diseases|agriculture)\b",
     ("Category: Science - Biology", "Category: Science - Earth/Agricultural/Farming", "Category: Science - Physics",
      "Category: Science - Chemistry/Biochemistry", "Category: Engineering & Technology", "Category: Health & Medicine",
      "Category: Nature/Gardening/Animals"), ("Q", "R", "S", "T"), None),
    ("practical", r"\b(cooking|cookery|etiquette|gardening|handicraft|sports|games|hobbies|home economics|"
                  r"housekeeping|carpentry|trades|domestic)\b",
     ("Category: How To ...", "Category: Cooking & Drinking", "Category: Sports/Hobbies"), (), None),
]  # fmt: skip
KIND_RULES = [
    (k, re.compile(sub, re.I) if sub else None, set(shelves), tuple(locc), re.compile(title, re.I) if title else None)
    for k, sub, shelves, locc, title in _R
]


def kind_of(title: str, subjects: str, shelves: list[str], locc: str) -> tuple[str, str]:
    """(kind, the rule that gave it): the first rule in KIND_RULES whose subject, bookshelf, class or title
    matches; subjects first, then bookshelves, then class, then title."""
    classes = [c.strip() for c in (locc or "").split(";") if c.strip()]
    shelf_set = set(shelves)
    for k, sub, shelf, loc, ttl in KIND_RULES:
        if sub and sub.search(subjects or ""):
            return k, f"subject /{sub.pattern[:40]}/"
        if ttl and ttl.search(title or ""):
            return k, "title"
        if k in ("periodical", "sermon", "dialogue"):  # these are named by subject or title alone
            continue
        hit = shelf_set & shelf
        if hit and (not loc or any(c.startswith(loc) for c in classes) or k not in ("novel",)):
            return k, f"bookshelf {sorted(hit)[0]}"
        if loc and any(c.startswith(loc) for c in classes) and k in ("history", "philosophy", "religion", "science"):
            return k, f"class {sorted(c for c in classes if c.startswith(loc))[0]}"
    return "other", "no rule"


# ---- the voice ------------------------------------------------------------------------------------------
# Who speaks: the institution behind the words, which brings its own bias. Said plainly: this is read from
# the catalogue's credit and subjects, so it finds a clergyman only when the credit says so ("Newman, John
# Henry, Cardinal" is found; "Spurgeon, C. H." is found by his sermons; a vicar writing a novel under his own
# name is missed). It undercounts. The counts are shown with the rule, so the bias is a figure, not a guess.
VOICES = ("clergy", "press", "official", "program", "lay")
VOICE_ABOUT = {
    "clergy": "the Church's voice: a clerical title in the credited writer's name, sermons, catechisms, prayer books",
    "press": "a magazine or journal's volume, many hands under an editor",
    "official": "a government, court or learned body: reports, proceedings, statutes",
    "program": "written by Nothing up my sleeve's own programs (the logic tutor) or derived from a book (the shuffled controls)",
    "lay": "any other named writer: no mark of an institution in the catalogue",
}  # fmt: skip
CLERICAL = re.compile(
    r"^(Rev\.?|Reverend|Saint|St\.|Cardinal|Archbishop|Bishop( of .*)?|Dean( of .*)?|Canon|Father|Fr\.|Pope|Abb[ée]|"
    r"Archdeacon|Vicar( of .*)?|Rector( of .*)?|Chaplain|Monsignor|Friar|Brother|Pastor|Moderator)$"
)  # a whole title after the surname ("More, Thomas, Saint"; "Newman, John Henry, Cardinal"), never a surname or given name
CHURCH_SUBJECT = re.compile(r"\bcatechisms?\b|\bdevotional (literature|exercises)\b|\bprayer ?books?\b|\bsermons?\b", re.I)
OFFICIAL = re.compile(
    r"\b(Great Britain\. (Parliament|Commission|Royal)|United States\. (Congress|Dept|Department|Supreme Court|Bureau)|"
    r"Royal Society|Parliament|Congress|Commission)\b"
)


def _titled(name: str) -> bool:
    segs = [x.strip() for x in re.sub(r",?\s*\d{1,4}\??.*$", "", name).split(",")][1:]
    return any(CLERICAL.match(x) for x in segs)


def voice_of(kind: str, authors: str, subjects: str, shelves: list[str], source: str) -> tuple[str, str]:
    if source == "local":
        return "program", "derived by Nothing up my sleeve"
    if kind == "periodical":
        return "press", "periodical"
    w = writer(credits(authors))
    name = w["name"] if w else ""
    if kind == "sermon":
        return "clergy", "sermons"
    if name and _titled(name):
        return "clergy", f"clerical title in {name[:40]!r}"
    if CHURCH_SUBJECT.search(subjects or ""):
        return "clergy", "subject: catechisms, devotion, prayer books"
    if (authors and OFFICIAL.search(authors)) or "Category: Reports & Conference Proceedings" in shelves:
        return "official", "a body credited, or reports and proceedings"
    return "lay", "no institutional mark"


# ---- the build -------------------------------------------------------------------------------------------
SCORE_FILES = (
    ("v0.1", "lists/ogden-v0.1-scores.csv"),
    ("v0.2", "lists/ogden-v0.2-scores.csv"),
    ("dialogue", "lists/dialogue-ogden-scores.csv"),
)  # the first score a book has stands: the scorings agree where they overlap, and v0.1's is the oldest
DECKS = ("lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv")
CONTROL = re.compile(r"shuffled|scrambled", re.I)  # the library's control texts (make_ogden_v02.CONTROL)


def title_key(t: str | None) -> str:
    return re.sub(r"[^a-z]", "", (t or "").lower())[:40]


def _catalogue() -> dict[str, dict]:
    p = paths.catalogue_dir() / "pg_catalog.csv"
    out: dict[str, dict] = {}
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out[f"pg{r['Text#']}"] = r
    return out


def _scores() -> dict[str, tuple[float, float, int, str]]:
    out: dict[str, tuple[float, float, int, str]] = {}
    for tag, lp in SCORE_FILES:
        p = paths.resolve(lp)
        if not p.exists():
            continue
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out.setdefault(r["book"], (float(r["ogden"]), float(r.get("names") or 0), int(r.get("words") or 0), tag))
    return out


def _held_out() -> set[str]:
    from thorp.sources.gutenberg import resolve_list

    held: set[str] = set()
    for deck in DECKS:
        try:
            held.update(f"pg{r.chosen}" for r in resolve_list(deck) if r.chosen)
        except Exception:  # noqa: BLE001 (a deck not here holds nothing back)
            pass
    return held


OVERRIDES = "lists/library-overrides.csv"  # book, field, value, why: a hand-made fact, kept where it can be read
OVERRIDE_FIELDS = ("kind", "voice", "year", "language")


def _overrides() -> dict[str, dict[str, tuple[str, str]]]:
    p = paths.resolve(OVERRIDES)
    out: dict[str, dict[str, tuple[str, str]]] = {}
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["field"] in OVERRIDE_FIELDS:
                    out.setdefault(r["book"], {})[r["field"]] = (r["value"], r.get("why") or "")
    return out


def build() -> list[dict]:
    """One row of facts for every book in the manifest, in id order."""
    from thorp import manifest

    cat, scores, held, over = _catalogue(), _scores(), _held_out(), _overrides()
    rows = []
    for b in sorted(manifest.all_books(), key=lambda b: b.id):
        c = cat.get(b.id)
        authors = (c["Authors"] if c else b.author) or ""
        subjects = c["Subjects"] if c else ""
        shelves = [s for s in (c["Bookshelves"] if c else "").split("; ") if s]
        locc = c["LoCC"] if c else ""
        lang = (b.language or "en").split(";")[0].strip() or "en"
        year, basis, born, died = year_of(authors, b.text if b.source != "gutenberg" else "")
        derived = b.source == "local"
        kind, krule = ("derived", "made by Nothing up my sleeve") if derived else kind_of(b.title, subjects, shelves, locc)
        voice, vrule = voice_of(kind, authors, subjects, shelves, b.source)
        o = over.get(b.id, {})
        if "kind" in o:
            kind, krule = o["kind"][0], f"override: {o['kind'][1]}"
            voice, vrule = voice_of(kind, authors, subjects, shelves, b.source)
        if "voice" in o:
            voice, vrule = o["voice"][0], f"override: {o['voice'][1]}"
        if "year" in o:
            year, basis = int(o["year"][0]), "override"
        if "language" in o:
            lang = o["language"][0]
        sc = scores.get(b.id)
        cs = credits(authors)
        rows.append({
            "book": b.id,
            "title": b.title or "",
            "author": b.author or "",
            "source": b.source,
            "set": b.set,
            "language": lang,
            "family": b.family or "",
            "translated": any((x["role"] or "").lower().startswith("translator") for x in cs),
            "born": born,
            "died": died,
            "gate_death": gate_death(authors),
            "year": year,
            "year_basis": basis,
            "kind": kind,
            "kind_rule": krule,
            "voice": voice,
            "voice_rule": vrule,
            "ogden": sc[0] if sc else None,
            "ogden_from": sc[3] if sc else "",
            "words": (sc[2] if sc and sc[2] else int((b.chars or 0) / CHARS_PER_WORD)),
            "fetched": (b.fetched_at or "")[:10],
            "held_out": b.id in held,
            "control": bool(CONTROL.search(b.title or "")),
            "title_key": title_key(b.title),
            "shelves": shelves,
            "subjects": subjects,
            "locc": locc,
        })  # fmt: skip
    return rows


def fingerprint(rows: list[dict]) -> str:
    """A name for a set of facts: the same inputs, the same fingerprint."""
    h = hashlib.sha1(json.dumps(rows, sort_keys=True, default=str).encode())
    return h.hexdigest()[:12]


def count(rows: list[dict], key: str, weight: str | None = None) -> dict[str, float]:
    c: Counter = Counter()
    for r in rows:
        v = r.get(key)
        c[str(v) if v is not None else "none"] += (r[weight] or 0) if weight else 1
    return dict(c.most_common())


# The four kinds of knowledge a ship can sail with (8 November, the four positions at the 1m: logic and maths,
# metaphysics, empirical knowledge, general knowledge; 12 November, Justin: "a selection which is the types of
# knowledge in the branch a ship will sail with ... and then configure the percentage"). One to a book, read from
# the facts a book already has: a mathematical or logical title wins over its kind, then the kind's house,
# and everything else is general. It is not stored in the facts (their fingerprint does not move).
KNOWLEDGE = ("general knowledge", "metaphysics", "empirical knowledge", "logic and maths")
KNOWLEDGE_ABOUT = {
    "general knowledge": "everything that is not one of the other three: novels, stories, poems, plays, essays, reference",
    "metaphysics": "philosophy, religion, sermons and dialogues",
    "empirical knowledge": "science, history, biography, travel, practical books and periodicals",
    "logic and maths": "a title that names logic, reasoning, mathematics, arithmetic, geometry, algebra, calculus, Euclid, number or proportion, whatever its kind",
}
_FORMAL = re.compile(r"\b(logic|reason|mathemat|arithmetic|geometry|geometr|algebra|calculus|euclid|number|proportion)\b", re.I)
_METAPHYSICS = {"philosophy", "religion", "sermon", "dialogue"}
_EMPIRICAL = {"science", "history", "biography", "travel", "practical", "periodical"}


def knowledge_of(fact: dict) -> str:
    if _FORMAL.search(fact.get("title") or ""):
        return "logic and maths"
    kind = fact.get("kind") or ""
    if kind in _METAPHYSICS:
        return "metaphysics"
    if kind in _EMPIRICAL:
        return "empirical knowledge"
    return "general knowledge"


def decade(year: int | None) -> str:
    if year is None:
        return "undated"
    if year < 1500:
        return "before 1500"
    return f"{year // 50 * 50}-{year // 50 * 50 + 49}"

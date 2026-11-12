r"""Acquisition: acquiring and cleaning books, as a viable system of its own (2026-11-07, Justin: "have the
cleaning and acquiring of books built out as per Beer's Viable System Model ... and then I want to be able to see that in the
UI").

Beer's model is recursive: each operation in S1 is itself a viable system. Nothing up my sleeve's S1 has two operations, the
voyages (training, thorp/liberty_machine.py) and acquisition (the books the voyages read). Acquisition's five systems:

- **S1, operations**: intakes. An intake (`intake(list)`, `thorp acquire LIST`) puts every row of a book list
  through the intake gate, fetches what is admitted, registers it in the manifest and checks that it cleans.
  A **gather** (`thorp/gather.py`, `thorp gather SOURCE`) is the same operation over a bulk corpus: it reads a
  source's records one at a time, through the same gate, and writes what is admitted where every book lives.
  Each intake is recorded (s1.intakes) and each book's verdict logged (s1.intake_verdicts). A book that reaches the manifest by the older paths (`thorp fetch`,
  train.prepare) is observed (`observe`): logged with the verdict the gate would give, never refused.
- **S2, coordination**: one intake at a time (the intake lock, data/acquisition/intake.lock). Acquisition
  never takes the GPU's helm, so an intake can run while a voyage is at sea. One request every two seconds per
  host (sources.base.http_get), one cache per source (data/texts/<source>/), and one writer of the manifest
  (thorp/manifest.py).
- **S3, control**: the intake gate (`admit`): Nothing up my sleeve's S5 policies applied to a book before it enters the
  library. Rules that serve an adopted policy refuse; proposed rules only record. Switched off in
  S5's switch "intake" (s5.policy_switches, `thorp s5 switch intake off`), by Justin. **S3\***: `audit()`, over the manifest and the texts,
  independent of the gate.
- **S4, intelligence**: the sources beyond Gutenberg (SOURCES_KNOWN, from plans/corpus-ceiling.md) and how
  much of the legal Gutenberg is fetched (`ceiling()`).
- **S5, policy**: RULES. Each serves one of Nothing up my sleeve's S5 policies (liberty_machine.POLICIES: decks, period, clean) or is
  proposed and awaits Justin's adoption, as an entry in DECISIONS.md.

Cleaning is not repeated here. It happens when a book is read (thorp/cleaning.py through sources.load_text;
S5 policy 'clean'), so the source's own text stays the record. An intake checks that each book it admits
cleans under the current version (deterministically) and records how its line breaks change; the audit
(liberty_machine.clean_audit) does the same for the stores.

    uv run thorp acquire LIST [--dry-run] [--limit N]   # S1: an intake
    uv run python -m thorp.acquisition audit             # S3*: the library's state
"""

from __future__ import annotations

import contextlib
import csv
import functools
import hashlib
import json
import os
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field

from thorp import manifest, paths
from thorp.sources import catalog

BYTES_PER_TOKEN = 3.6  # fetched English Gutenberg text under the 16,384-piece tokeniser
DIED_BY = 1955  # Australia's public-domain line: every person dead by 1955
PRINTED_BEFORE = 1930
UNDATED_PRINTED_BEFORE = (
    1870  # a person with no dates, in a book printed before this, was dead by 1955
)
UNSIGNED = {"anonymous", "unknown", "various", "anon", "anon."}


# ------------------------------------------------------------------------------------------- the five systems

SYSTEMS = [
    {
        "key": "S1",
        "name": "Operations",
        "purpose": "intakes: a book list through the gate, fetched, registered and checked that it cleans",
        "members": ["thorp/acquisition.py intake", "thorp/gather.py", "thorp acquire", "thorp gather", "data/acquisition/"],
    },
    {
        "key": "S2",
        "name": "Coordination",
        "purpose": "one intake at a time, one request every two seconds per host, one cache per source, one writer of the manifest",
        "members": [
            "data/acquisition/intake.lock",
            "thorp/sources/base.py http_get",
            "data/texts/",
            "thorp/manifest.py",
        ],
    },
    {
        "key": "S3",
        "name": "Control",
        "purpose": "the intake gate every book passes before it enters the library, and the audit (S3*)",
        "members": [
            "thorp/acquisition.py admit, audit",
            "thorp/cleaning.py",
            "thorp/liberty_machine.py clean_audit",
        ],
    },
    {
        "key": "S4",
        "name": "Intelligence",
        "purpose": "the sources beyond Gutenberg, and how much of the legal ceiling is fetched",
        "members": ["thorp/acquisition.py SOURCES_KNOWN, ceiling", "thorp/sources/catalog.py", "thorp/sources/bulk.py", "plans/corpus-ceiling.md"],
    },
    {
        "key": "S5",
        "name": "Policy",
        "purpose": "what may enter the library: Nothing up my sleeve's S5 policies applied to books, and rules proposed to Justin",
        "members": ["thorp/acquisition.py RULES", "thorp/liberty_machine.py POLICIES", "DECISIONS.md"],
    },
]


# ------------------------------------------------------------------------------------------- people and dates

_DATES = re.compile(r"(\d{1,4})\??\s*(BCE|BC)?\s*-\s*(\d{1,4})\??\s*(BCE|BC)?(?!\d)", re.IGNORECASE)
_DIED_ONLY = re.compile(r"(?:^|[\s,])-\s*(\d{3,4})\b")
_CENTURY = re.compile(
    r"active\s+(?:approximately\s+)?(\d{1,2})(?:st|nd|rd|th)\s+century(\s+BCE)?", re.I
)
_ACTIVE_YEAR = re.compile(r"active\s+(?:approximately\s+)?(\d{3,4})\b", re.IGNORECASE)


@dataclass(frozen=True)
class Person:
    name: str
    died: (
        int | None
    )  # the year of death (negative before the common era); None when the record gives none
    role: str = ""


def persons(authors: str) -> list[Person]:
    """Every person in an authors field, as Gutenberg's catalogue and library records write them:
    'Surname, Given, 1812-1870 [Translator]', '427? BCE-347? BCE', 'active 15th century', one per ';'.
    Unsigned names (Anonymous, Unknown, Various) are left out: they are no one's death date."""
    out = []
    for part in re.split(r";|\n", authors or ""):
        p = part.strip().rstrip(".").strip()
        if not p:
            continue
        role = ""
        if m := re.search(r"\[([^\]]+)\]\s*$", p):
            role, p = m.group(1).strip(), p[: m.start()].strip()
        name = re.split(r",?\s*(?=\d|active\b)", p, maxsplit=1)[0].strip(" ,")
        if name.lower() in UNSIGNED or not name:
            continue
        died = None
        if d := _DATES.search(p):
            y = int(d.group(3))
            died = -y if d.group(4) else y
        elif c := _CENTURY.search(p):
            n = int(c.group(1))
            died = -(n - 1) * 100 if c.group(2) else (n * 100 if n <= 19 else None)
        elif a := _ACTIVE_YEAR.search(p):
            y = int(a.group(1))
            died = y + 100 if y + 100 <= DIED_BY else None  # active by 1855: dead by 1955
        elif o := _DIED_ONLY.search(p):
            died = int(o.group(1))
        out.append(Person(name, died, role))
    return out


def with_dates(authors: str, resolved: dict[str, tuple[int | None, int | None]]) -> str:
    """The authors field with a lookup's dates written into it, so the manifest records what the gate used
    and the audit can read it again: 'Greene, Charles E.' -> 'Greene, Charles E., 1842-1903'."""
    if not resolved:
        return authors
    out = []
    for part in (authors or "").split(";"):
        role = ""
        body = part.strip()
        if m := re.search(r"\[([^\]]+)\]\s*$", body):
            role, body = f" [{m.group(1)}]", body[: m.start()].strip()
        ps = persons(body)
        key = ps[0].name if len(ps) == 1 else ""
        if key and key not in resolved and key + "." in resolved:
            key += "."
        if len(ps) == 1 and ps[0].died is None and key in resolved:
            born, died = resolved[key]
            body += f", {born}-{died}" if born is not None else f", -{died}"
        out.append(body + role)
    return "; ".join(x for x in out if x)


def unsigned(authors: str) -> bool:
    """No named person at all: Anonymous, Unknown, Various, or an empty field."""
    return not persons(authors)


# ------------------------------------------------------------------------------------------- a book at the gate


@dataclass
class Candidate:
    """A book at the intake gate: what is known about it before it is fetched, and after."""

    book_id: str
    title: str
    authors: str  # every person, with dates where the source gives them
    language: str
    set: str  # recipe (read), hole-card or truth (held out, scored on)
    source: str
    ref: str = ""
    published: int | None = None  # the year this edition was printed, when the source records it
    origin: str = ""
    text: str | None = None  # after fetch: the source's own text, the record
    sha1: str = ""
    resolved: dict[str, tuple[int | None, int | None]] = field(default_factory=dict)  # a lookup's dates (S4)


def _norm_title(t: str) -> str:
    return " ".join((t or "").lower().split())


@functools.cache
def _deck_titles() -> dict[str, str]:
    """Every held-out deck's titles (the hole cards and the Forgotten Tomes), as liberty_machine._decks_refused reads them."""
    out = {}
    for deck in ("lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"):
        p = paths.resolve(deck)
        if p.exists():
            with p.open(newline="", encoding="utf-8") as f:
                out |= {_norm_title(r["title"]): deck for r in csv.DictReader(f)}
    return out


DISCOVERY_SETS = ("classics", "cuneiform")  # not English recipes: the period rules do not speak to them
READ_SETS = ("recipe", "incunabula", *DISCOVERY_SETS)  # sets read as books; a deck is not


def _discovery(c: Candidate) -> bool:
    return c.set in DISCOVERY_SETS


def _english(c: Candidate) -> list[str]:
    if c.set == "recipe" and (c.language or "en") != "en":
        return [
            f"in {c.language}, not English (a held-out deck may be another language; a book read may not)"
        ]
    return []


def _dead_by_1955(c: Candidate) -> list[str]:
    if _discovery(c):
        return []
    bad = []
    for p in persons(c.authors):
        died = p.died
        if died is None and p.name in c.resolved:
            died = c.resolved[p.name][1]
        if died is None:
            if c.published is not None and c.published < UNDATED_PRINTED_BEFORE:
                continue
            bad.append(f"{p.name}{f' ({p.role})' if p.role else ''} has no death year")
        elif died > DIED_BY:
            bad.append(f"{p.name}{f' ({p.role})' if p.role else ''} died in {died}")
    return bad


def _printed_before_1930(c: Candidate) -> list[str]:
    if _discovery(c):
        return []
    return (
        [f"printed in {c.published}"]
        if c.published is not None and c.published >= PRINTED_BEFORE
        else []
    )


def _not_a_deck_book(c: Candidate) -> list[str]:
    if c.set not in READ_SETS:
        return []
    deck = _deck_titles().get(_norm_title(c.title))
    return [f"{c.title!r} is held out on {deck}"] if deck else []


_WORD = re.compile(r"[a-z0-9]+")
DECK_SHINGLE = 5
DECK_OVERLAP = 0.35  # of the shorter text's 5-word shingles; OCR variants still share most of a book
SHINGLE_CAP = 2000  # per candidate, evenly sampled: enough to recognise a deck book, cheap in bulk


def _shingles(text: str, size: int = DECK_SHINGLE, cap: int | None = None) -> set[int]:
    """The text's word shingles as hashes. A cap samples them evenly, so a long scan costs no more."""
    words = _WORD.findall((text or "").lower())
    if len(words) < size:
        return set()
    hs = [hash(tuple(words[i : i + size])) for i in range(len(words) - size + 1)]
    if cap and len(hs) > cap:
        hs = hs[:: max(1, len(hs) // cap)][:cap]
    return set(hs)


@functools.cache
def _deck_index() -> tuple[dict[int, set[str]], dict[str, int]]:
    """Every held-out book's shingles, indexed shingle -> the books it appears in, and each book's count.
    The decks are read raw, as the source gave them, so a scan is compared with the transcription."""
    from thorp.sources import load_text

    index: dict[int, set[str]] = {}
    sizes: dict[str, int] = {}
    for deck in ("lists/hole-cards.csv", "lists/hole-cards-v2.csv", "lists/hole-cards-unseen.csv"):
        p = paths.resolve(deck)
        if not p.exists():
            continue
        with p.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                ref = (row.get("text") or "").strip()
                if ref.startswith("pg") and ref[2:].isdigit():
                    bid = ref
                elif ":" in ref:
                    bid = ref.split(":", 1)[1]
                else:
                    continue  # a title-matched row: the deck is protected by title, not by text
                try:
                    sh = _shingles(load_text(bid, "raw"))
                except (KeyError, FileNotFoundError, AssertionError):
                    continue
                if not sh:
                    continue
                sizes[bid] = len(sh)
                for x in sh:
                    index.setdefault(x, set()).add(bid)
    return index, sizes


def _not_a_deck_text(c: Candidate) -> list[str]:
    """S5 'decks' by text, not by id: a scan of a held-out book may arrive under another name and year."""
    if c.set not in READ_SETS or not c.text:
        return []
    cand = _shingles(c.text, cap=SHINGLE_CAP)
    if not cand:
        return []
    index, sizes = _deck_index()
    hits: dict[str, int] = {}
    for x in cand:
        for bid in index.get(x, ()):  # type: ignore[union-attr]
            hits[bid] = hits.get(bid, 0) + 1
    for bid, n in hits.items():
        if n / min(len(cand), sizes[bid]) >= DECK_OVERLAP:
            return [f"shares {n / min(len(cand), sizes[bid]):.0%} of its shingles with held-out {bid}"]
    return []


_EDITION: dict[tuple[str, str], str] = {}


def _edition_key(title: str, authors: str) -> tuple[str, str] | None:
    t = " ".join(_WORD.findall((title or "").lower()))
    for a in ("the ", "a ", "an "):
        if t.startswith(a):
            t = t[len(a) :]
            break
    people = persons(authors)
    if not t or not people:
        return None
    return t, people[0].name.split(",")[0].strip().lower()


def _edition_index() -> dict[tuple[str, str], str]:
    if not _EDITION:
        for b in manifest.all_books():
            if k := _edition_key(b.title, b.author):
                _EDITION.setdefault(k, b.id)
    return _EDITION


def note_edition(book: manifest.Book) -> None:
    """Keep the title-and-author index current as a gather registers books, so a second edition in the
    same run is seen."""
    if k := _edition_key(book.title, book.author):
        _EDITION.setdefault(k, book.id)


def _same_edition(c: Candidate) -> list[str]:
    if not c.title or not c.authors:
        return []
    k = _edition_key(c.title, c.authors)
    if k is None:
        return []
    other = _edition_index().get(k)
    return [f"the same title and author is already in the library as {other}"] if other and other != c.book_id else []


def _cleans(c: Candidate) -> list[str]:
    if c.text is None:
        return []
    from thorp import cleaning

    a = cleaning.clean(c.text, cleaning.CURRENT)
    if not c.text.strip():
        return ["the source gave no text"]
    if not a.strip():
        return [f"cleaning ({cleaning.CURRENT}) leaves nothing"]
    if cleaning.clean(c.text, cleaning.CURRENT) != a:
        return [f"cleaning ({cleaning.CURRENT}) is not deterministic on it"]
    return []


def admitted_sources() -> set[str]:
    """S4's admitted sources, plus `local` (Nothing up my sleeve's own derived books): one list, the catalogue's."""
    return {s["key"] for s in catalog.SOURCES if s["status"] == "admitted"} | {"local"}


def _admitted_source(c: Candidate) -> list[str]:
    return [] if c.source in admitted_sources() else [f"{c.source} is not an admitted source"]


def _signed(c: Candidate) -> list[str]:
    if _discovery(c):
        return []
    if not unsigned(c.authors):
        return []
    if c.published is not None and c.published < PRINTED_BEFORE:
        return []
    return ["unsigned (no named person), and its printing year is not known"]


def _not_duplicate(c: Candidate) -> list[str]:
    if not c.sha1:
        return []
    other = manifest.same_text(c.sha1, c.book_id)  # the register the readers use (11 November), not the file
    return [f"the same text is already in the library as {other}"] if other else []


def _provenance(c: Candidate) -> list[str]:
    if c.source in ("gutenberg", "local"):
        return []
    return [] if c.origin else ["records no origin (where it came from)"]


@dataclass(frozen=True)
class Rule:
    key: str
    statement: str
    serves: (
        str | None
    )  # the Nothing up my sleeve S5 policy it applies to books (liberty_machine.POLICIES); None: proposed, awaiting Justin
    when: str  # "before fetch" or "after fetch"
    check: Callable[[Candidate], list[str]]

    @property
    def adopted(self) -> bool:
        return self.serves is not None


RULES: dict[str, Rule] = {
    r.key: r
    for r in (
        Rule(
            "english",
            "A book read for training is in English; a held-out deck may be in another language.",
            "period",
            "before fetch",
            _english,
        ),
        Rule(
            "dead-by-1955",
            "Every named person in the authors field (translators and editors too) died by 1955. A person with "
            f"no dates passes only in a book printed before {UNDATED_PRINTED_BEFORE}.",
            "period",
            "before fetch",
            _dead_by_1955,
        ),
        Rule(
            "printed-before-1930",
            "Where the source records the year an edition was printed, it was printed before 1930.",
            "period",
            "before fetch",
            _printed_before_1930,
        ),
        Rule(
            "not-a-deck-book",
            "A book entering to be read is not a book of a held-out deck (the hole cards, the Forgotten Tomes).",
            "decks",
            "before fetch",
            _not_a_deck_book,
        ),
        Rule(
            "not-a-deck-text",
            "A scanned book is not a held-out deck's text under another name or year: the decks are protected "
            "by the words, not only the id (shingle overlap after the fetch).",
            "decks",
            "after fetch",
            _not_a_deck_text,
        ),
        Rule(
            "cleans",
            "Each book cleans under the current version, deterministically, and leaves text behind; the source's "
            "own text is kept as the record and cleaned when it is read.",
            "clean",
            "after fetch",
            _cleans,
        ),
        Rule(
            "admitted-source",
            "Books come only from sources S5 has admitted (today Gutenberg, the Internet Archive, and books "
            "made here); a new source (plans/corpus-ceiling.md) is admitted by an entry in DECISIONS.md.",
            None,
            "before fetch",
            _admitted_source,
        ),
        Rule(
            "signed",
            "An unsigned work (Anonymous, Various, no author) enters only when its printing year is known and "
            "before 1930: the death rule cannot speak to it (Australia counts anonymous works from publication).",
            None,
            "before fetch",
            _signed,
        ),
        Rule(
            "not-duplicate",
            "A text already in the library (the same SHA-1 under another id) is not registered twice.",
            None,
            "after fetch",
            _not_duplicate,
        ),
        Rule(
            "not-same-edition",
            "A book whose title and first author are already in the library is recorded as another edition, "
            "not registered twice: the scan sets overlap each other and Gutenberg.",
            None,
            "after fetch",
            _same_edition,
        ),
        Rule(
            "provenance",
            "Every book records where it came from (its origin), when it was fetched and its text's hash.",
            None,
            "after fetch",
            _provenance,
        ),
    )
}


def enforced() -> bool:
    """The intake gate refuses on adopted rules unless Justin switches it off (S5's switch "intake",
    s5.policy_switches)."""
    from thorp import liberty_machine

    return bool(liberty_machine._enforcement().get("intake", True))


@dataclass
class Verdict:
    admitted: bool
    refused: list[str]  # adopted rules broken ("rule: why"): the gate refuses
    notes: list[
        str
    ]  # proposed rules broken, or adopted ones while the gate only observes: recorded only


def admit(
    c: Candidate,
    when: tuple[str, ...] = ("before fetch", "after fetch"),
    enforce: bool = True,
    only: set[str] | None = None,
) -> Verdict:
    """S3, the intake gate: every rule for this stage (or only those named) applied to the book."""
    refused, notes = [], []
    on = enforce and enforced()
    for r in RULES.values():
        if r.when not in when or (only is not None and r.key not in only):
            continue
        for why in r.check(c):
            (refused if (r.adopted and on) else notes).append(f"{r.key}: {why}")
    return Verdict(not refused, refused, notes)


# ------------------------------------------------------------------------------------------- S1: the record


def _dir():
    return paths.data_dir() / "acquisition"


LOG_TIME = "%Y-%m-%dT%H:%M:%S"
_LOG_COLUMNS = ("at", "intake", "how", "book_id", "verdict")


def _append_log(entry: dict) -> None:
    """One book's verdict, kept (s1.intake_verdicts)."""
    from datetime import datetime

    from thorp import store
    from thorp.viable.records import IntakeVerdict

    with store.session() as s:
        s.add(IntakeVerdict(at=datetime.fromisoformat(entry["at"]).astimezone(), intake_id=entry.get("intake"),
                            how=entry.get("how"), book_id=entry.get("book_id"), verdict=entry.get("verdict"),
                            entry={k: v for k, v in entry.items() if k not in _LOG_COLUMNS}))  # fmt: skip


def read_log(limit: int | None = None) -> list[dict]:
    """The verdicts, oldest first (the last `limit` of them), as the log's lines."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import IntakeVerdict

    q = select(IntakeVerdict).order_by(IntakeVerdict.at.desc(), IntakeVerdict.id.desc())
    with store.session() as s:
        rows = s.scalars(q.limit(limit) if limit else q).all()
        return [{"at": r.at.astimezone().strftime(LOG_TIME), "intake": r.intake_id, "how": r.how, "book_id": r.book_id,
                 **(r.entry or {}), "verdict": r.verdict} for r in rows[::-1]]  # fmt: skip


def _entry(
    c: Candidate, verdict: str, v: Verdict | None, intake_id: str | None, how: str, **extra
) -> dict:
    return {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "intake": intake_id,
        "how": how,
        "book_id": c.book_id,
        "ref": c.ref,
        "title": c.title,
        "authors": c.authors,
        "source": c.source,
        "set": c.set,
        "published": c.published,
        "verdict": verdict,
        "refused": v.refused if v else [],
        "notes": v.notes if v else [],
        **extra,
    }


def _clean_report(text: str) -> dict:
    from thorp import cleaning

    a, b = cleaning.breaks(text), cleaning.breaks(cleaning.clean(text, cleaning.CURRENT))
    return {
        "version": cleaning.CURRENT,
        "words_per_break": [round(a["words_per_break"], 1), round(b["words_per_break"], 1)],
        "inside_paragraph_share": [round(a["inside_share"], 3), round(b["inside_share"], 3)],
    }


def _write_intake(rec: dict) -> None:
    """An intake's record, written or brought up to date (s1.intakes)."""
    from thorp import store
    from thorp.viable.records import Intake

    with store.session() as s:
        s.merge(Intake(id=rec["id"], list=rec.get("list"), status=rec.get("status"), started=rec.get("started"),
                       finished=rec.get("finished"), record=json.loads(json.dumps(rec, default=str))))  # fmt: skip


def intakes(limit: int = 30) -> list[dict]:
    """The latest intakes' records, newest first."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import Intake

    with store.session() as s:
        q = select(Intake).order_by(Intake.started.desc(), Intake.id.desc()).limit(limit)
        return [r.record for r in s.scalars(q)]


def count_intakes() -> int:
    from sqlalchemy import func, select

    from thorp import store
    from thorp.viable.records import Intake

    with store.session() as s:
        return s.scalar(select(func.count()).select_from(Intake)) or 0


# ------------------------------------------------------------------------------------------- S2: one intake at a time


def _lock_paths():
    return _dir() / "intake.lock", None  # who holds it: s2.intake_holder


def _holder_write(rec: dict | None, pid: int) -> None:
    from sqlalchemy import delete

    from thorp import store
    from thorp.viable.records import IntakeHolder

    with store.session() as s:
        if rec is None:
            s.execute(delete(IntakeHolder).where(IntakeHolder.lock == "intake", IntakeHolder.pid == pid))
        else:
            s.merge(IntakeHolder(lock="intake", **rec))


def _holder_read() -> dict | None:
    from thorp import store
    from thorp.viable.records import IntakeHolder

    with store.session() as s:
        r = s.get(IntakeHolder, "intake")
        return {"id": r.id, "list": r.list, "pid": r.pid, "since": r.since} if r else None


@contextlib.contextmanager
def _intake_lock(intake_id: str, list_path: str, log=print):
    import fcntl

    lock, _ = _lock_paths()
    lock.parent.mkdir(parents=True, exist_ok=True)
    f = open(lock, "a+")
    try:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log(
                f"S2: waiting for the intake lock ({(holder() or {}).get('id')} is taking books in)"
            )
            fcntl.flock(f, fcntl.LOCK_EX)
        _holder_write({"id": intake_id, "list": list_path, "pid": os.getpid(), "since": time.strftime(LOG_TIME)}, os.getpid())
        yield
    finally:
        try:
            _holder_write(None, os.getpid())
        finally:
            f.close()


def holder() -> dict | None:
    """The intake taking books in now, or None."""
    import fcntl

    lock, _ = _lock_paths()
    if not lock.exists():
        return None
    with open(lock, "a+") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return _holder_read() or {"id": "(unknown)", "since": None}
        fcntl.flock(f, fcntl.LOCK_UN)
    return None


# ------------------------------------------------------------------------------------------- S1: an intake


@functools.cache
def _catalogue_rows() -> dict[str, dict]:
    """Gutenberg's catalogue by number (Authors with life dates, Language, Type)."""
    from thorp.sources import gutenberg

    p = gutenberg.catalogue_path()
    if not p.exists():
        return {}
    with p.open(newline="", encoding="utf-8") as f:
        return {r["Text#"]: r for r in csv.DictReader(f)}


def _gutenberg_candidate(
    gid: int, title: str, language: str, set_name: str, ref: str = ""
) -> Candidate:
    row = _catalogue_rows().get(str(gid), {})
    return Candidate(
        book_id=f"pg{gid}",
        title=title or " ".join((row.get("Title") or "").split()),
        authors=row.get("Authors", ""),
        language=language or (row.get("Language") or "en").split(";")[0].strip(),
        set=set_name,
        source="gutenberg",
        ref=ref or f"gutenberg:{gid}",
        origin=f"https://www.gutenberg.org/ebooks/{gid}",
    )


def intake(
    list_path: str,
    set_name: str | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    log=print,
) -> dict:
    """S1: one intake of a book list. Every row goes through the gate before it is fetched; a book admitted is
    fetched, checked again (it cleans, it is not a duplicate) and registered; a book already in the library is
    left as it is. Returns the intake's record."""
    from thorp.sources import base, gutenberg

    set_name = set_name or gutenberg.set_for_list(list_path)
    rid = "in-" + time.strftime("%Y%m%d-%H%M%S")
    rec = {
        "id": rid,
        "list": str(list_path),
        "set": set_name,
        "dry_run": dry_run,
        "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "finished": None,
        "status": "taking in",
        "counts": {
            "admitted": 0,
            "known": 0,
            "refused": 0,
            "failed": 0,
            "unresolved": 0,
            "would fetch": 0,
        },
        "refused_by_rule": {},
        "bytes": 0,
        "gate_enforced": enforced(),
    }
    rows = gutenberg.read_list(list_path)
    with _intake_lock(rid, str(list_path), log):
        _write_intake(rec)
        items: list[tuple[Candidate, object]] = []
        if rows and all(base.is_ref(r.text) for r in rows):
            for r in rows:
                key, ident = r.text.split(":", 1)
                if key == "gutenberg":
                    items.append(
                        (_gutenberg_candidate(int(ident), r.title, r.language, set_name, r.text), r)
                    )
                else:
                    prefix = "" if key == "local" else base._sources()[key].prefix
                    c = Candidate(
                        f"{prefix}{ident}",
                        r.title,
                        r.author,
                        r.language or "en",
                        set_name,
                        key,
                        ref=r.text,
                    )
                    items.append((c, r))
        else:
            resolutions = gutenberg.resolve_list(list_path)
            if not dry_run:
                gutenberg.write_resolution_csv(list_path, resolutions)
            for res in resolutions:
                if res.chosen is None:
                    rec["counts"]["unresolved"] += 1
                    c = Candidate(
                        "", res.row.title, res.row.author, res.row.language, set_name, "gutenberg"
                    )
                    _append_log(_entry(c, "unresolved", None, rid, "intake"))
                    continue
                items.append(
                    (
                        _gutenberg_candidate(res.chosen, res.row.title, res.row.language, set_name),
                        res,
                    )
                )
        for c, item in items[: limit or None]:
            _one(c, item, rec, dry_run, log)
            _write_intake(rec)
        rec["status"] = "home"
        rec["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        _write_intake(rec)
    log(
        f"intake {rid}: {rec['counts']['admitted']} admitted, {rec['counts']['known']} already in the library, "
        f"{rec['counts']['refused']} refused, {rec['counts']['failed']} failed, {rec['counts']['unresolved']} unresolved"
        + (f", {rec['counts']['would fetch']} would be fetched (dry run)" if dry_run else "")
    )
    return rec


def _refuse(c: Candidate, v: Verdict, rec: dict, log) -> None:
    rec["counts"]["refused"] += 1
    for why in v.refused:
        k = why.split(":", 1)[0]
        rec["refused_by_rule"][k] = rec["refused_by_rule"].get(k, 0) + 1
    _append_log(_entry(c, "refused", v, rec["id"], "intake"))
    log(f"  refused  {c.book_id or c.title}: {'; '.join(v.refused)}")


def _one(c: Candidate, item, rec: dict, dry_run: bool, log) -> None:
    from thorp.sources import base, gutenberg

    if c.book_id and manifest.get(c.book_id) is not None and c.source != "local":
        rec["counts"]["known"] += 1
        _append_log(_entry(c, "known", None, rec["id"], "intake"))
        return
    # Gutenberg's catalogue gives every person's dates before anything is fetched; a scanned source's people,
    # language and printing year come with the fetch, so only the list's own facts are judged first
    pre = None if c.source == "gutenberg" else {"english", "not-a-deck-book", "admitted-source"}
    v = admit(c, ("before fetch",), only=pre)
    if not v.admitted:
        return _refuse(c, v, rec, log)
    if dry_run:
        rec["counts"]["would fetch"] += 1
        _append_log(_entry(c, "would fetch", v, rec["id"], "intake"))
        return
    try:
        if c.source == "gutenberg":
            gid = int(c.book_id[2:])
            gutenberg.fetch(gid)
            c.text = gutenberg.text(gid)
        elif c.source == "local":
            book = manifest.get(c.book_id)
            if book is None:
                raise LookupError(f"no local book {c.book_id!r} in the manifest")
            rec["counts"]["known"] += 1
            _append_log(_entry(c, "known", v, rec["id"], "intake"))
            return
        else:
            key, ident = c.ref.split(":", 1)
            f = base._sources()[key].fetch(ident)
            c.text, c.published, c.origin = f.text, f.published, f.origin
            c.title, c.authors, c.language = (
                c.title or f.title,
                f.author or c.authors,
                f.language or c.language,
            )
    except Exception as e:  # noqa: BLE001
        rec["counts"]["failed"] += 1
        _append_log(_entry(c, "failed", None, rec["id"], "intake", error=str(e)[:300]))
        log(f"  failed   {c.book_id}: {e}")
        return
    c.sha1 = hashlib.sha1(c.text.encode("utf-8")).hexdigest()
    v = admit(
        c
    )  # every rule again, with what the fetch told us (an archive item's people, language, year)
    if not v.admitted:
        return _refuse(c, v, rec, log)
    if c.source == "gutenberg":
        book = (
            gutenberg.fetch_and_register(item, rec["set"], observe=False)
            if hasattr(item, "chosen")
            else _register_gutenberg(c, item, rec["set"])
        )
    else:
        key, ident = c.ref.split(":", 1)
        from thorp.sources.base import Fetched

        book = base.register_fetched(
            key,
            ident,
            Fetched(c.title, c.authors, c.language, c.text, c.published, c.origin),
            family=getattr(item, "family", ""),
            set_name=rec["set"],
            observe=False,
        )
    rec["counts"]["admitted"] += 1
    rec["bytes"] += book.bytes
    _append_log(
        _entry(c, "admitted", v, rec["id"], "intake", bytes=book.bytes, clean=_clean_report(c.text))
    )
    log(
        f"  admitted {c.book_id}: {book.bytes:,} bytes{f' ({len(v.notes)} notes)' if v.notes else ''}"
    )


def _register_gutenberg(c: Candidate, row, set_name: str) -> manifest.Book:
    """A list that names Gutenberg books by number (gutenberg:<n>): registered as the general fetcher does."""
    from thorp.sources import gutenberg
    from thorp.sources.gutenberg import Resolution

    res = Resolution(row)
    res.chosen = int(c.book_id[2:])
    return gutenberg.fetch_and_register(res, set_name, observe=False)


def observe(book: manifest.Book, how: str) -> None:
    """A book that entered the manifest by an older path (thorp fetch, train.prepare): logged with the verdict
    the gate would give, never refused. Cheap: the rules before fetch, the duplicate check and provenance."""
    c = candidate_of(book)
    v = admit(c, ("before fetch",), enforce=False)
    for why in _not_duplicate(c) + _provenance(c):
        v.notes.append(why)
    _append_log(_entry(c, "observed", v, None, how, bytes=book.bytes))


def candidate_of(book: manifest.Book) -> Candidate:
    """A registered book as the gate sees it: for Gutenberg, the catalogue's authors (with dates)."""
    from thorp.sources.base import published

    derived = re.search(r"pg(\d+)$", book.id) if book.source == "local" else None
    if book.source == "gutenberg" and book.id.startswith("pg") and book.id[2:].isdigit():
        c = _gutenberg_candidate(int(book.id[2:]), book.title, book.language, book.set or "recipe")
        if not c.authors:
            c.authors = book.author
    elif derived and str(int(derived.group(1))) in _catalogue_rows():
        # a book made here from a Gutenberg book (the shuffled shelf: shuf-pg100) answers for its original
        c = _gutenberg_candidate(
            int(derived.group(1)), book.title, book.language, book.set or "recipe"
        )
        c.book_id, c.source, c.ref, c.origin = book.id, "local", f"local:{book.id}", ""
    else:
        origin = (
            (book.text or "").split("; ", 1)[-1]
            if (book.text or "").startswith("published ")
            else ""
        )
        if not origin and (book.text or "").startswith("http"):
            origin = book.text
        c = Candidate(
            book.id,
            book.title,
            book.author,
            book.language or "en",
            book.set or "recipe",
            book.source,
            published=published(book),
            origin=origin,
        )
    c.sha1 = book.sha1 or ""
    return c


# ------------------------------------------------------------------------------------------- S3*: the audit


def _text_path(book: manifest.Book):
    if book.source == "gutenberg" and book.id[2:].isdigit():
        from thorp.sources import gutenberg

        return gutenberg.raw_path(int(book.id[2:]))
    return paths.texts_dir(book.source) / f"{book.id}.txt"


def audit(sample: int = 24) -> dict:
    """S3*: the library's state, independent of the gate. Every registered book read against every rule the
    manifest can answer; duplicate texts; missing files; for a sample, whether the source's text still hashes
    as registered and whether a source's boilerplate survived; and the cleaning audit of the stores."""
    from thorp import liberty_machine

    books = manifest.all_books()
    by_rule: dict[str, list[dict]] = {k: [] for k, r in RULES.items() if r.when == "before fetch"}
    by_rule["provenance"] = []
    for b in books:
        c = candidate_of(b)
        for k in list(by_rule):
            if whys := RULES[k].check(c):  # one row per book, every reason it gives
                by_rule[k].append({"book": b.id, "title": b.title, "set": b.set, "why": "; ".join(whys)})
    sha: dict[str, list[str]] = {}
    for b in books:
        if b.sha1:
            sha.setdefault(b.sha1, []).append(b.id)
    dups = [ids for ids in sha.values() if len(ids) > 1]
    missing = [b.id for b in books if b.source != "local" and not _text_path(b).exists()]
    pick = sorted(books, key=lambda b: hashlib.sha1(b.id.encode()).hexdigest())[:sample]
    drift, leftovers = [], []
    for b in pick:
        try:
            from thorp.sources import _source_text

            t = _source_text(b.id)
        except Exception:  # noqa: BLE001  (a missing file is counted above)
            continue
        if b.sha1 and hashlib.sha1(t.encode("utf-8")).hexdigest() != b.sha1:
            drift.append(b.id)
        tail = t[-4000:].lower()
        if (
            "project gutenberg" in tail
            and "license" in tail
            or "digitized by google" in t[:4000].lower()
        ):
            leftovers.append(b.id)
    totals: dict[str, dict] = {}
    for b in books:
        t = totals.setdefault(
            f"{b.source}|{b.set}", {"source": b.source, "set": b.set, "books": 0, "bytes": 0}
        )
        t["books"] += 1
        t["bytes"] += b.bytes or 0
    for t in totals.values():
        t["tokens_est"] = int(t["bytes"] / BYTES_PER_TOKEN)
    try:
        cleaning = liberty_machine.clean_audit()
    except Exception as e:  # noqa: BLE001
        cleaning = {"error": str(e)}
    return {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "books": len(books),
        "rules": {
            k: {
                "breaking": len(v),
                "examples": v[:12],
                "serves": RULES[k].serves,
                "adopted": RULES[k].adopted,
                "by_set": {
                    s: sum(1 for x in v if x["set"] == s) for s in sorted({x["set"] for x in v})
                },
            }
            for k, v in by_rule.items()
        },
        "duplicates": {"groups": len(dups), "examples": dups[:10]},
        "missing_files": {"count": len(missing), "examples": missing[:10]},
        "sample": {"checked": len(pick), "drifted": drift, "boilerplate_left": leftovers},
        "totals": sorted(totals.values(), key=lambda t: -t["bytes"]),
        "cleaning": cleaning,
    }


# ------------------------------------------------------------------------------------------- S4: the outside world

# S4's catalogue lives in thorp/sources/catalog.py: one list for acquisition, the gather operation and the
# dashboard, so a source's status and the adapter that can fetch it cannot drift apart.
SOURCES_KNOWN = catalog.SOURCES

@functools.cache
def _catalogue_counts(mtime: float) -> dict:
    """English texts in Gutenberg's catalogue by the death rule (cached per catalogue file)."""
    legal, undated, later, unsigned_n = set(), 0, 0, 0
    for k, r in _catalogue_rows().items():
        if r.get("Type") != "Text" or "en" not in (r.get("Language") or "").split("; "):
            continue
        ps = persons(r.get("Authors", ""))
        if not ps:
            unsigned_n += 1
        elif any(p.died is None for p in ps):
            undated += 1
        elif max(p.died for p in ps) > DIED_BY:
            later += 1
        else:
            legal.add(f"pg{k}")
    return {"legal": legal, "undated": undated, "after_1955": later, "unsigned": unsigned_n}


def ceiling() -> dict:
    """S4: how much of the legal Gutenberg is in the library, and the estimate beyond it."""
    from thorp.sources import gutenberg

    p = gutenberg.catalogue_path()
    if not p.exists():
        return {"catalogue": False}
    cc = _catalogue_counts(p.stat().st_mtime)
    fetched = [b for b in manifest.all_books() if b.source == "gutenberg"]
    legal_fetched = [b for b in fetched if b.id in cc["legal"]]
    n = len(cc["legal"])
    return {
        "catalogue": True,
        "gutenberg_legal_books": n,
        "gutenberg_undated_books": cc["undated"],
        "gutenberg_after_1955_books": cc["after_1955"],
        "gutenberg_unsigned_books": cc["unsigned"],
        "gutenberg_legal_tokens_est": [
            int(n * 362e3 / BYTES_PER_TOKEN),
            int(n * 495e3 / BYTES_PER_TOKEN),
        ],
        "fetched_legal_books": len(legal_fetched),
        "fetched_legal_tokens_est": int(sum(b.bytes or 0 for b in legal_fetched) / BYTES_PER_TOKEN),
        "fetched_tokens_est": int(
            sum(b.bytes or 0 for b in manifest.all_books()) / BYTES_PER_TOKEN
        ),
        "reachable_tokens_est": {
            "open books": [12e9, 18e9],
            "with Institutional Books": [40e9, 60e9],
        },
        "plan": "plans/corpus-ceiling.md",
    }


# ------------------------------------------------------------------------------------------- S2 and the payload


def coordination() -> dict:
    """S2: who holds the intake lock, who holds the GPU's helm (acquisition never takes it), the request
    interval, and each source's cache."""
    from thorp import liberty_machine
    from thorp.sources import base

    caches = []
    tdir = paths.data_dir() / "texts"
    if tdir.exists():
        for d in sorted(p for p in tdir.iterdir() if p.is_dir()):
            n = size = 0
            for e in os.scandir(d):
                if e.is_file():
                    n += 1
                    size += e.stat().st_size
            caches.append({"source": d.name, "files": n, "bytes": size})
    return {
        "intake": holder(),
        "helm": liberty_machine.helm(),
        "request_interval_s": base.REQUEST_INTERVAL_S,
        "caches": caches,
    }


def summary() -> dict:
    """For Nothing up my sleeve's own S1: acquisition at a glance, and what the bulk gathers have brought in."""
    from thorp import gather

    books = manifest.all_books()
    ins = intakes(1)
    return {
        "books": len(books),
        "tokens_est": int(sum(b.bytes or 0 for b in books) / BYTES_PER_TOKEN),
        "intakes": count_intakes(),
        "last_intake": ins[0] if ins else None,
        "taking_in": holder(),
        "gathered": gather.summary(),
    }


def payload(log_limit: int = 60) -> dict:
    """Acquisition's five systems for the dashboard (/api/acquisition); the audit (S3*) is served apart, warm."""
    from thorp import liberty_machine

    log = read_log()
    refused_by_rule: dict[str, int] = {}
    observed_breaking: dict[str, int] = {}
    for e in log:
        for why in e.get("refused") or []:
            k = why.split(":", 1)[0]
            refused_by_rule[k] = refused_by_rule.get(k, 0) + 1
        if e.get("verdict") == "observed":
            for why in e.get("notes") or []:
                k = why.split(":", 1)[0]
                observed_breaking[k] = observed_breaking.get(k, 0) + 1
    return {
        "systems": SYSTEMS,
        "S1": {"intakes": intakes(), "log": log[-log_limit:][::-1], "summary": summary()},
        "S2": coordination(),
        "S3": {
            "enforced": enforced(),
            "refused_by_rule": refused_by_rule,
            "observed_breaking": observed_breaking,
            "verdicts": {
                v: sum(1 for e in log if e.get("verdict") == v)
                for v in sorted({e.get("verdict") for e in log})
            },
        },
        "S4": {"sources": SOURCES_KNOWN, "ceiling": ceiling()},
        "S5": [
            {
                **{k: v for k, v in asdict(r).items() if k != "check"},
                "adopted": r.adopted,
                "policy_adopted": liberty_machine.POLICIES[r.serves].adopted
                if r.serves in liberty_machine.POLICIES
                else None,
            }
            for r in RULES.values()
        ],
    }


if __name__ == "__main__":
    import sys

    if sys.argv[1:2] == ["audit"]:
        a = audit()
        print(f"S3* acquisition audit: {a['books']} books in the library")
        for k, v in a["rules"].items():
            print(
                f"    {k:22} {'adopted' if v['adopted'] else 'proposed':8} breaking: {v['breaking']:5}  {v['by_set']}"
            )
        print(
            f"    duplicates: {a['duplicates']['groups']} groups; missing files: {a['missing_files']['count']}"
        )
        print(
            f"    sample of {a['sample']['checked']}: drifted {a['sample']['drifted']}, boilerplate left {a['sample']['boilerplate_left']}"
        )
    elif sys.argv[1:2] == ["ceiling"]:
        print(json.dumps(ceiling(), indent=1, default=str))

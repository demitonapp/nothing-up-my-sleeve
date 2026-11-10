"""The shelves: every book list Thorp reads from, scores on or refuses (2026-11-07, Justin: "a tab for
shelves").

A shelf is a CSV in lists/ (title, author, language, family, text). `payload()` is the dashboard's
/api/shelves: for each shelf its name, kind, what it is for, its books (how many rows, how many are
match a catalogue book, how many are fetched into the manifest, their bytes and a token estimate, the families), and which runs and queued specs use
it and how (read as a recipe or a stage, read first, refused, scored on, or the tokeniser's text).

Kinds: `training` (a shelf a model reads), `deck` (books held out to score on, always refused),
`probe` (short lists the evaluators use), `draft` (a working list, never read), `other`.
The chain tests' pairs (lists/tricks/) are not shelves; they belong to the tricks.
"""

from __future__ import annotations

import csv
import json
import os
import re
from collections import Counter
from pathlib import Path

from thorp import paths

BYTES_PER_TOKEN = 4.0  # a rough rule for English prose with Thorp's tokenisers

ABOUT: dict[str, tuple[str, str, str]] = {
    # path: (name, kind, what it is for)
    "lists/stores/prose.csv": (
        "The prose stores",
        "training",
        "One of the ship's two stores (Justin, 15:55): novels and stories at or above the median name density, ranked by names recurring within the window. Runs read the stores or opt out in words.",
    ),
    "lists/stores/trigram.csv": (
        "The trigram stores",
        "training",
        "One of the ship's two stores (Justin, 15:55): everything else with variety at least 0.6, ranked by in-window trigram repetition, the induction head's food. Runs read the stores or opt out in words.",
    ),
    "lists/stars-fiction.csv": (
        "English-original fiction",
        "training",
        "First Light's and the keel's reading: fiction first written in English, the most valuable kind in the book-value fit.",
    ),
    "lists/stars-verse.csv": (
        "Verse",
        "training",
        "Poetry as a kind of its own; a First Light and best-keel shelf lever.",
    ),
    "lists/stars-pool.csv": (
        "The mixed pool",
        "training",
        "Fiction, non-fiction and verse together; a First Light and best-keel shelf lever.",
    ),
    "lists/stars-fiction-shuffled.csv": (
        "Shuffled fiction",
        "training",
        "The fiction shelf with every book's words shuffled: the Magician's Apprentice, who reads words but no order.",
    ),
    "lists/reasoning-shelf.csv": (
        "The reasoning shelf",
        "training",
        "Logic, geometry, Plato, Descartes, Bacon and Faraday (39 books of argument and proof) and the 95 "
        "cause-and-effect books (Justin, 13:15): a late stage for the two-fact problem's round 2 and the card "
        "census (the books behind the chaining tests left out).",
    ),
    "lists/cause-shelf.csv": (
        "The cause-and-effect shelf",
        "training",
        "95 period how-to books: cookery and household management, gardening, first aid and home remedies, "
        "handicraft and woodwork, games and their rules, scouting and camping; step after step, when X then Y "
        "(Qwen3 4B chains cause and effect on invented words and nothing else). No engines, heat or mechanics, "
        "no animal breeding, no chemistry of the elements: the chaining tests' own subjects.",
    ),
    "lists/dialogue-shelf.csv": (
        "Formulaic dialogue",
        "training",
        "The repetition engine's dialogue, from the period (Justin: period only): catechisms, primers and readers, "
        "phrase books, courtesy and etiquette books, school colloquies, and ten issues of Notes and Queries; "
        "question and answer, said the same way again.",
    ),
    "lists/law-shelf.csv": (
        "The legal shelf",
        "training",
        "The causal skeleton's law, from the period: commentaries and textbooks of law, legal ethics and "
        "jurisprudence, and trial transcripts (formulaic question and answer, like the Old Bailey's).",
    ),
    "lists/keel-nursery.csv": (
        "The nursery",
        "training",
        "213 English children's books: picture books, primers, Mother Goose and nursery verse; the best-keel voyage's shelf lever and first stage.",
    ),
    "lists/loop-pool.csv": (
        "The loop pool",
        "training",
        "1,108 books the book-value loop drew its shelves from; the tokenisers of the 1m and the keel are trained on it.",
    ),
    "lists/pool-400.csv": ("The speller's pool", "training", "The 9m sweep's 400-book shelf."),
    "lists/pool-400-fiction.csv": (
        "The speller's fiction",
        "training",
        "The fiction half of the speller's pool.",
    ),
    "lists/pool-400-nonfiction.csv": (
        "The speller's non-fiction",
        "training",
        "The non-fiction half of the speller's pool.",
    ),
    "lists/pool-400-spellers.csv": (
        "The spellers",
        "training",
        "Spelling books and primers for the speller curriculum.",
    ),
    "lists/pool-800.csv": (
        "Lever: 800 books",
        "training",
        "The data levers: distinct text against total reading.",
    ),
    "lists/pool-200.csv": (
        "Lever: 200 books",
        "training",
        "The data levers: distinct text against total reading.",
    ),
    "lists/pool-100.csv": (
        "Lever: 100 books",
        "training",
        "The data levers: distinct text against total reading.",
    ),
    "lists/hole-cards-unseen.csv": (
        "The Forgotten Tomes",
        "deck",
        "Books released on Gutenberg after Qwen 3.8: the yardstick no outside model can have read; refused by every run.",
    ),
    "lists/hole-cards.csv": (
        "Hole cards",
        "deck",
        "The first held-out deck; refused by every run.",
    ),
    "lists/hole-cards-v2.csv": (
        "Hole cards II",
        "deck",
        "The second held-out deck; refused by every run.",
    ),
    "lists/precursors-archive.csv": (
        "The precursors (Internet Archive)",
        "training",
        "16 scanned editions of the discovery tests' precursors (Lyell, Legendre, Playfair and others), dated by publication year.",
    ),
    "lists/britannica-11.csv": ("Britannica, 11th edition", "training", "The 1911 encyclopaedia."),
    "lists/spellers.csv": ("Spellers", "probe", "Spelling books used by the speller evaluators."),
    "lists/spelling-rules.csv": ("Spelling rules", "probe", "The rules the speller is scored on."),
    "lists/traits.csv": ("Traits", "probe", "The trait probes' books."),
    "lists/truths.csv": ("Truths", "probe", "Statements the probes score."),
    "lists/neutral.csv": ("Neutral", "probe", "A neutral list for the probes' controls."),
    "lists/smoke-10.csv": ("Smoke", "other", "Ten books for smoke tests."),
}


def _kind(path: str) -> str:
    stem = Path(path).stem
    if "draft" in stem:
        return "draft"
    if "hole" in stem or stem.startswith("held-"):
        return "deck"
    if stem.startswith(("content-", "pool", "stars-", "loop-")):
        return "training"
    return "other"


def _rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if (r.get("title") or r.get("text"))]


def _resolved() -> dict[str, list[str]]:
    """list path -> manifest book ids, from data/resolution.csv (the title-matched lists that have been fetched)."""
    if os.environ.get("THORP_LIBRARY_PG") == "1":
        from thorp import manifest_store

        return manifest_store.resolved_lists()
    out: dict[str, list[str]] = {}
    p = paths.data_dir() / "resolution.csv"
    if p.exists():
        with p.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if (r.get("chosen") or "").isdigit():
                    out.setdefault(r["list"], []).append(f"pg{r['chosen']}")
    return out


def _uses() -> dict[str, list[dict]]:
    """list path -> [{run, role, status}] from the ledger's runs and the queued specs."""
    import yaml

    from thorp.ledger import connect

    uses: dict[str, list[dict]] = {}

    def add(spec: dict, who: str, status: str, label: str | None = None) -> None:
        from thorp import fleet

        voyage = fleet.expedition_of_label(who, label or spec.get("ship"))
        d, t, e = spec.get("data", {}), spec.get("tokeniser", {}), spec.get("eval", {})
        roles = [
            (d.get("recipe"), "reads"),
            (d.get("first"), "reads first"),
            (t.get("train_on"), "tokeniser"),
        ]
        roles += [(s.get("recipe"), f"stage {s.get('name')}") for s in d.get("stages") or []]
        roles += [(x, "refuses") for x in d.get("refuse") or []]
        roles += [(x, "scored on") for x in e.get("sets") or []]
        for path, role in roles:
            if isinstance(path, str) and path.startswith("lists/"):
                uses.setdefault(path, []).append(
                    {"run": who, "role": role, "status": status, "voyage": voyage}
                )

    from thorp.ledger import reader

    con = reader()
    try:
        for name, spec_json, status, ship in con.execute(
            "select name, spec_json, status, ship from runs"
        ):
            add(json.loads(spec_json), name, status or "", ship)
    finally:
        con.close()
    q = paths.resolve("specs/queue.txt")
    if q.exists():
        for line in q.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith(("#", "cmd:")):
                p = paths.resolve(f"specs/{line}.yaml")
                if p.exists():
                    add(yaml.safe_load(p.read_text()), line.split("/")[-1], "queued")
    return uses


def _by_voyage(uses: list[dict]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for x in uses:
        v = out.setdefault(
            x.get("voyage") or "none", {"runs": set(), "queued": set(), "roles": set()}
        )
        (v["queued"] if x["status"] == "queued" else v["runs"]).add(x["run"])
        v["roles"].add(x["role"])
    return {
        k: {"runs": len(v["runs"]), "queued": len(v["queued"]), "roles": sorted(v["roles"])}
        for k, v in out.items()
    }


def _ids(p: Path, rel: str, rows: list[dict], resolved: dict[str, list[str]]) -> list[str]:
    """The manifest ids a list names: by reference (`local:<id>`), else the title-matched, fetched ones."""
    refs = [r["text"] for r in rows if ":" in (r.get("text") or "")]
    if refs and len(refs) == len(rows):
        from thorp.sources import base

        ids = []
        for ref in refs:
            key, ident = ref.split(":", 1)
            if key == "local":
                ids.append(ident)
            elif key in base._sources():
                ids.append(base._sources()[key].prefix + ident)
            else:
                from thorp.sources import bulk

                if key in bulk.bulk_sources():
                    ids.append(bulk.bulk_sources()[key].prefix + ident)
        return ids
    ids = resolved.get(rel)
    if ids is None:  # never fetched: match its titles against the catalogue, offline
        from thorp.sources.gutenberg import resolve_list

        ids = [f"pg{r.chosen}" for r in resolve_list(p) if r.chosen]
    return ids


COLLECTION_EXTRA = {"lists/ogden-v0.1.csv": "Ogden v0.1", "lists/ogden-v0.2.csv": "Ogden v0.2"}  # fitout corpora, as collections


def collections() -> list[dict]:
    """The named collections a book may belong to, for the Library's filters: every training shelf and every
    held-out deck (Renaissance, Greek, Islamic, the nursery, the legal shelf, the stores...) and the two Ogden
    corpora, each with its book ids. Light: no trigram readings, no voyages (payload() has those)."""
    resolved = _resolved()
    lists = paths.resolve("lists")
    out = []
    for p in sorted(lists.glob("*.csv")) + sorted((lists / "stores").glob("*.csv")):
        rel = str(p.relative_to(lists.parent))
        name, kind, about = ABOUT.get(rel, (p.stem.replace("-", " "), _kind(rel), ""))
        if rel in COLLECTION_EXTRA:
            name, kind, about = COLLECTION_EXTRA[rel], "training", "A fitout's corpus."
        if kind not in ("training", "deck"):
            continue
        out.append({"path": rel, "name": name, "kind": kind, "about": about, "book_ids": sorted(set(_ids(p, rel, _rows(p), resolved)))})
    return out


_FACTS: dict[str, dict] | None = None


def _facts() -> dict[str, dict]:
    """Every book's facts, built once for the summaries (library_facts.build is the expensive part)."""
    global _FACTS
    if _FACTS is None:
        from thorp import library_facts

        _FACTS = {r["book"]: r for r in library_facts.build()}
    return _FACTS


CATEGORY_ORDER = ("logic and maths", "metaphysics", "empirical knowledge", "general knowledge")
_LOGIC = re.compile(r"\b(logic|reason|mathemat|arithmetic|geometry|geometr|algebra|calculus|euclid|number|proportion)\b", re.I)
_METAPHYSICS = {"philosophy", "religion", "sermon", "dialogue"}
_EMPIRICAL = {"science", "history", "biography", "travel", "practical", "periodical"}


def category_of(fact: dict) -> str:
    """The Library tab's four kinds of book: formal (logic and maths), metaphysics, empirical
    knowledge, and general knowledge. A mathematical or logical title wins over its genre; then the
    genre's house; everything else is general."""
    if _LOGIC.search(fact.get("title") or ""):
        return "logic and maths"
    kind = fact.get("kind") or ""
    if kind in _METAPHYSICS:
        return "metaphysics"
    if kind in _EMPIRICAL:
        return "empirical knowledge"
    return "general knowledge"


LANGUAGE_NAMES = {
    "en": "English", "la": "Latin", "grc": "Ancient Greek", "sux": "Sumerian", "akk": "Akkadian",
    "egy": "Egyptian", "ar": "Arabic", "he": "Hebrew", "fr": "French", "de": "German", "it": "Italian",
    "es": "Spanish", "ru": "Russian", "sa": "Sanskrit", "ang": "Old English", "enm": "Middle English",
    "frm": "Middle French", "non": "Old Norse", "got": "Gothic", "syr": "Syriac", "arc": "Aramaic",
    "peh": "Middle Persian", "uga": "Ugaritic", "nl": "Dutch", "pt": "Portuguese", "sv": "Swedish",
    "da": "Danish", "el": "Greek", "tr": "Turkish", "fa": "Persian", "zh": "Chinese", "ja": "Japanese",
}  # fmt: skip


def _large_summary(rel: str, p) -> dict:
    """A synthetic deck (hundreds of thousands of inline passages): count it without resolving a book
    or building the whole library's facts. These decks are not a manifest shelf; they are passages."""
    import csv

    langs = Counter()
    n = 0
    size = 0
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if not (r.get("title") or r.get("text")):
                continue
            n += 1
            langs[(r.get("language") or "en").split(";")[0].strip() or "en"] += 1
            size += len((r.get("text") or "").encode("utf-8"))
    name = ABOUT.get(rel, (p.stem.replace("-", " "), "", ""))[0]
    total = n or 1
    return {
        "path": rel,
        "name": name,
        "rows": n,
        "resolved": n,
        "books": 0,
        "bytes": size,
        "tokens_est": int(size / BYTES_PER_TOKEN),
        "languages": [
            {"code": c, "name": LANGUAGE_NAMES.get(c, c), "books": k, "share": round(k / total, 3)}
            for c, k in langs.most_common()
        ],
        "kinds": [],
        "categories": [],
        "date_range": None,
        "ogden": {"mean": None, "scored": 0, "unscored": n, "share_at_bar": None, "bar": 0.68},
        "synthetic": True,
    }


def _summary_pg(rel: str) -> dict | None:
    """A shelf's summary from Postgres: `list_rows` -> `books` -> `s3.library_facts`, with no CSV read
    and no library-facts build. Returns None when the shelf is not fully named there (a partially named
    shelf falls back to the resolver, which can still find the rest)."""
    try:
        from sqlalchemy import text

        from thorp import store

        with store.session() as s:
            rows = s.execute(text("""
                select r.title, r.language as list_language, r.book,
                       b.language as book_language, b.bytes,
                       f.title as fact_title, f.language as fact_language, f.kind, f.year, f.ogden
                from s1.list_rows r
                left join s1.books b on b.id = r.book
                left join s3.library_facts f on f.book = r.book
                where r.list = :rel
                order by r.ordinal
            """), {"rel": rel}).mappings().all()
    except Exception:  # noqa: BLE001  no list_rows table or no library_facts: the CSV path still works
        return None
    if not rows:
        return None
    have = [r for r in rows if r["book"] and r["bytes"] is not None]
    if len(have) != len(rows):
        return None  # some rows are not books (yet): the resolver can name them
    n = len(have) or 1
    langs = Counter((r["fact_language"] or r["book_language"] or r["list_language"] or "?") for r in have)
    kinds = Counter((r["kind"] or "other") for r in have)
    cats = Counter(category_of({"title": r["fact_title"] or r["title"], "kind": r["kind"]}) for r in have)
    years = [int(r["year"]) for r in have if r["year"] is not None]
    ogden = [float(r["ogden"]) for r in have if r["ogden"] is not None]
    size = sum(int(r["bytes"] or 0) for r in have)
    stem = rel.rsplit("/", 1)[-1].rsplit(".", 1)[0].replace("-", " ")
    name = ABOUT.get(rel, (stem, "", ""))[0]
    return {
        "path": rel,
        "name": name,
        "rows": len(rows),
        "resolved": len(rows),
        "books": len(have),
        "bytes": size,
        "tokens_est": int(size / BYTES_PER_TOKEN),
        "languages": [
            {"code": c, "name": LANGUAGE_NAMES.get(c, c), "books": k, "share": round(k / n, 3)}
            for c, k in langs.most_common()
        ],
        "kinds": [
            {"kind": k, "books": k_, "share": round(k_ / n, 3)}
            for k, k_ in kinds.most_common()
        ],
        "categories": [
            {"category": c, "books": cats.get(c, 0), "share": round(cats.get(c, 0) / n, 3)}
            for c in CATEGORY_ORDER
        ],
        "date_range": {"from": min(years), "to": max(years)} if years else None,
        "ogden": {
            "mean": round(sum(ogden) / len(ogden), 3) if ogden else None,
            "scored": len(ogden),
            "unscored": len(have) - len(ogden),
            "share_at_bar": round(sum(v >= 0.68 for v in ogden) / len(ogden), 3) if ogden else None,
            "bar": 0.68,
        },
    }


def summary(rel: str) -> dict:
    """A shelf at a glance for the ship builder's Library tab: its language(s), its kinds of book, its
    size (books, bytes, tokens) and its date range. Facts come from the manifest and library_facts."""
    from thorp import manifest

    p = paths.resolve(rel)
    if p.exists() and p.stat().st_size > 20_000_000:  # a synthetic card-stage deck: 360k inline passages, not books
        return _large_summary(rel, p)
    if os.environ.get("THORP_LIBRARY_PG") == "1":
        got = _summary_pg(rel)
        if got is not None:
            return got
    if not p.exists():
        raise LookupError(f"no shelf {rel!r}")
    rows = _rows(p)
    ids = _ids(p, rel, rows, _resolved())
    books = {i: b for i in ids if (b := manifest.get(i)) is not None}
    size = sum(b.bytes or 0 for b in books.values())
    facts = _facts()
    have = [facts[i] for i in books if i in facts]
    langs = Counter(f["language"] or "?" for f in have)
    kinds = Counter(f["kind"] or "other" for f in have)
    cats = Counter(category_of(f) for f in have)
    years = [int(f["year"]) for f in have if f.get("year") is not None]
    ogden = [float(f["ogden"]) for f in have if f.get("ogden") is not None]
    n = len(have) or 1
    return {
        "path": rel,
        "name": ABOUT.get(rel, (p.stem.replace("-", " "), "", ""))[0],
        "rows": len(rows),
        "resolved": len(ids),
        "books": len(books),
        "bytes": size,
        "tokens_est": int(size / BYTES_PER_TOKEN),
        "languages": [
            {"code": c, "name": LANGUAGE_NAMES.get(c, c), "books": n_, "share": round(n_ / n, 3)}
            for c, n_ in langs.most_common()
        ],
        "kinds": [
            {"kind": k, "books": n_, "share": round(n_ / n, 3)}
            for k, n_ in kinds.most_common()
        ],
        "categories": [
            {"category": c, "books": cats.get(c, 0), "share": round(cats.get(c, 0) / n, 3)}
            for c in CATEGORY_ORDER
        ],
        "date_range": {"from": min(years), "to": max(years)} if years else None,
        "ogden": {
            "mean": round(sum(ogden) / len(ogden), 3) if ogden else None,
            "scored": len(ogden),
            "unscored": len(have) - len(ogden),
            # the bar the selection uses (thorp/selection.py): a book at 0.68 is Ogden-ish
            "share_at_bar": round(sum(v >= 0.68 for v in ogden) / len(ogden), 3) if ogden else None,
            "bar": 0.68,
        },
    }


def payload() -> list[dict]:
    from thorp import manifest

    resolved, uses = _resolved(), _uses()
    out = []
    lists = paths.resolve("lists")
    for p in sorted(lists.glob("*.csv")) + sorted(
        (lists / "stores").glob("*.csv")
    ):  # and the ship's stores
        rel = str(p.relative_to(lists.parent))
        if p.name in ("overrides.csv",):
            continue
        rows = _rows(p)
        ids = _ids(p, rel, rows, resolved)
        books = {
            i: b for i in ids if (b := manifest.get(i)) is not None
        }  # the rest: not fetched yet
        size = sum(b.bytes or 0 for b in books.values())
        name, kind, about = ABOUT.get(rel, (p.stem.replace("-", " "), _kind(rel), ""))
        u = uses.get(rel, [])
        out.append(
            {
                "path": rel,
                "name": name,
                "kind": kind,
                "about": about,
                "rows": len(rows),
                "book_ids": sorted(books),
                # the induction head's food (thorp/trigrams.py): in-window repeated trigrams, cached readings
                "trigrams": __import__("thorp.trigrams", fromlist=["shelf_stats"]).shelf_stats(
                    sorted(books)
                ),
                "resolved": len(ids),
                "books": len(books),
                "bytes": size,
                "tokens_est": int(size / BYTES_PER_TOKEN),
                "families": dict(Counter(b.family or "?" for b in books.values()).most_common()),
                # the voyages that read it (Justin: shelves tagged per ship's voyage, so a shelf's
                # characteristics can be set beside the runs that read it): voyage -> runs, by role
                "voyages": _by_voyage(u),
                "runs": len({x["run"] for x in u if x["status"] != "queued"}),
                "queued": len({x["run"] for x in u if x["status"] == "queued"}),
                "uses": u,
            }
        )
    return out


def main() -> None:
    for s in payload():
        print(
            f"{s['kind']:9} {s['name'][:34]:34} {s['rows']:5} rows {s['resolved']:5} found {s['books']:5} fetched {s['tokens_est'] / 1e6:8.1f}M tok  runs {s['runs']:3} queued {s['queued']:3}"
        )


if __name__ == "__main__":
    main()


def fitouts() -> list[dict]:
    """Every fitout, the hand-curated ones (fleet.FITOUTS) and those saved from the builder (data/fitouts/,
    no class until built for one), each with its stages beside the shelves they read (books, tokens) and the
    runs it has compiled to: for the Library's fitout table (Justin, 13:15; saved ones added 19:05, "a table
    of fitouts ... with columns for its attributes")."""
    from thorp import fitouts as built
    from thorp import fleet
    from thorp.ledger import connect

    shelves = {x["path"]: x for x in payload()}
    from thorp.ledger import reader

    con = reader()
    try:
        ran = {
            r[0]: r[1] for r in con.execute("select name, status from runs where name like 'fo-%'")
        }
    finally:
        con.close()
    queued = set()
    q = paths.resolve("specs/queue.txt")
    if q.exists():
        queued = {
            ln.strip().split("/")[-1]
            for ln in q.read_text().splitlines()
            if ln.startswith("fitouts/")
        }

    def stage(st, kind: str, i: int) -> dict:
        sh = shelves.get(st.shelf, {})
        return {
            "phase": kind,
            "order": i,
            "name": st.name,
            "shelf": st.shelf,
            "shelf_name": sh.get("name", st.shelf),
            "books": sh.get("books"),
            "tokens_per_pass": sh.get("tokens_est"),
            "passes": st.passes,
            "tokens": (sh.get("tokens_est") or 0) * st.passes,
            "purpose": st.purpose,
            "lr": st.lr,
            "tack": st.tack,
        }

    out = []
    for f in fleet.FITOUTS.values():
        stages = [stage(st, "pretraining", i) for i, st in enumerate(f.pretraining, 1)]
        stages += [stage(st, "post-training", i) for i, st in enumerate(f.posttraining, 1)]
        runs = sorted({n for n in list(ran) + list(queued) if n.startswith(f"fo-{f.key}-")})
        out.append(
            {
                "key": f.key,
                "name": f.name,
                "preset": f.preset,
                "aim": f.aim,
                "positions": f.positions,
                "vocab": f.vocab,
                "tack": f.tack,
                "stages": stages,
                "tokens": sum(x["tokens"] for x in stages),
                "runs": [{"run": n, "status": ran.get(n, "queued")} for n in runs],
                "kind": "curated",
            }
        )
    for f in built.saved():  # the builder's: a stage may read only part of its shelf (its tokens), chosen by `select`
        stages, order = [], {"pretraining": 0, "post-training": 0}
        for s in f.get("stages") or []:
            sh = shelves.get(s.get("shelf"), {})
            per = min(s["tokens"], sh.get("tokens_est") or s["tokens"]) if s.get("tokens") else sh.get("tokens_est")
            order[s["phase"]] = order.get(s["phase"], 0) + 1
            stages.append(
                {
                    "phase": s["phase"],
                    "order": order[s["phase"]],
                    "name": s.get("name"),
                    "shelf": s.get("shelf"),
                    "shelf_name": sh.get("name", s.get("shelf")),
                    "books": sh.get("books"),
                    "tokens_per_pass": per,
                    "passes": s.get("passes", 1),
                    "tokens": (per or 0) * s.get("passes", 1),
                    "purpose": s.get("purpose", ""),
                    "lr": s.get("lr"),
                    "tack": s.get("tack"),
                    "select": s.get("select", "all"),
                }
            )
        runs = sorted({n for n in list(ran) + list(queued) if n.startswith(f"fo-{f['key']}-")})
        out.append(
            {
                "key": f["key"],
                "name": f.get("name"),
                "preset": None,
                "aim": f.get("aim", ""),
                "positions": f.get("positions"),
                "vocab": f.get("vocab"),
                "tack": f.get("tack"),
                "stages": stages,
                "tokens": sum(x["tokens"] for x in stages),
                "runs": [{"run": n, "status": ran.get(n, "queued")} for n in runs],
                "kind": "saved",
                "opt_in": f.get("opt_in", ""),
            }
        )
    return out


def carried(spec: dict) -> list[dict]:
    """The libraries a voyage carries, from its spec: each list it reads, by name, with its kind (one of
    the ship's stores, drawn from the stores, or outside them), its books and its content hash."""
    import hashlib

    from thorp import stores

    store_of = {s["path"]: k for k, s in stores.stores().items()}
    d = spec.get("data", {})
    out = []
    for lp in stores.reads(spec):
        p = paths.resolve(lp)
        rows = _rows(p) if p.exists() else []
        name = ABOUT.get(lp, (p.stem.replace("-", " "),))[0]
        where = (
            f"the {store_of[lp]} stores"
            if lp in store_of
            else "drawn from the stores"
            if stores.stores() and stores.drawn_from_stores(lp)
            else "outside the stores"
        )
        stage = next((s.get("name") for s in d.get("stages") or [] if s.get("recipe") == lp), None)
        out.append(
            {
                "path": lp,
                "name": name,
                "stage": stage,
                "where": where,
                "books": len(rows),
                "sha1": hashlib.sha1(p.read_bytes()).hexdigest() if p.exists() else None,
            }
        )
    return out


def aboard(run_id: str) -> dict:
    """The library aboard a voyage: its libraries as recorded when it sailed (the 'library' artifact),
    or, for voyages that sailed before 2026-11-07 16:30, worked out from its spec (marked so: the lists
    may have changed since), with the books it read and their tokens (the 'recipe' artifact)."""
    from thorp.ledger import reader

    rec = reader()
    run = rec.get_run(run_id)
    if not run:
        raise KeyError(run_id)
    spec = json.loads(run["spec_json"] or "{}")
    got = rec.latest_artifact_text(run_id, "library")
    recipe = rec.latest_artifact_text(run_id, "recipe")
    books = json.loads(recipe) if recipe else []
    return {
        "voyage": run["name"],
        "ship": run["ship"],
        "libraries": json.loads(got) if got else carried(spec),
        "recorded": got is not None,
        "opt_in": (spec.get("data", {}).get("opt_in") or "").strip(),
        "refused": spec.get("data", {}).get("refuse") or [],
        "books": len(books),
        "tokens": sum(b.get("tokens") or 0 for b in books),
        "book_list": books,
    }

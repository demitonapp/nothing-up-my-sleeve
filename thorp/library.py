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

    con = connect(readonly=True)
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
            ids = resolved.get(rel)
            if ids is None:  # never fetched: match its titles against the catalogue, offline
                from thorp.sources.gutenberg import resolve_list

                ids = [f"pg{r.chosen}" for r in resolve_list(p) if r.chosen]
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
    """Every hand-curated fitout (fleet.FITOUTS) with its stages beside the shelves they read (books,
    tokens) and the runs it has compiled to: for the Shelves tab (Justin, 13:15)."""
    from thorp import fleet
    from thorp.ledger import connect

    shelves = {x["path"]: x for x in payload()}
    con = connect(readonly=True)
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
    or, for voyages that sailed before 2026-11-07 16:40, worked out from its spec (marked so: the lists
    may have changed since), with the books it read and their tokens (the 'recipe' artifact)."""
    from thorp.ledger import Ledger

    rec = Ledger()
    run = rec.query("select name, ship, spec_json from runs where run_id=?", [run_id])
    if not run:
        raise KeyError(run_id)
    spec = json.loads(run[0]["spec_json"] or "{}")
    got = rec.query(
        "select text from artifacts where run_id=? and kind='library' order by rowid desc limit 1",
        [run_id],
    )
    recipe = rec.query(
        "select text from artifacts where run_id=? and kind='recipe' order by rowid desc limit 1",
        [run_id],
    )
    books = json.loads(recipe[0]["text"]) if recipe else []
    return {
        "voyage": run[0]["name"],
        "ship": run[0]["ship"],
        "libraries": json.loads(got[0]["text"]) if got else carried(spec),
        "recorded": bool(got),
        "opt_in": (spec.get("data", {}).get("opt_in") or "").strip(),
        "refused": spec.get("data", {}).get("refuse") or [],
        "books": len(books),
        "tokens": sum(b.get("tokens") or 0 for b in books),
        "book_list": books,
    }

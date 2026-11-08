"""A fitout's books, composed from declared weights and filters rather than listed by hand (Justin, 2026-11-08:
"our fitouts or the part of it that controls what the books are should be able to have weights, so I should be
able to weight by language ... then it should weight by ogdenish as we already do, then also choose a time
period, both a start and an end date, then it should have filters for content type"; "we need to have sources
... We need to track this early and transparently").

A selection is a JSON object, saved on a fitout's stage (`compose`, s3.stages) and read by `compose`:

    {"as_of": "2026-11-07",                   # only books the library held by this day (fetched on or before)
     "languages": {"en": 1.0},                # shares of the words; a language not named is not read
     "ogden": {"min": 0.68, "scored_by": null},   # the bar: Ogden-ness (thorp/ogden.py); unscored fall short of
                                                  # a bar; scored_by limits it to books one scoring measured ("v0.1"...)
     "period": {"start": null, "end": null, "undated": "exclude"},    # years, inclusive; see library_facts.py
     "kinds": {"include": [...], "exclude": [...]},     # novel, poem, play, textbook, essay, sermon, dialogue...
     "voices": {...}, "sources": {...}, "shelves": {...},            # the same include/exclude, by voice, collection, bookshelf
     "weights": {"kind": {"novel": 0.5, "poem": 0.5}},   # more shares of the words, by kind, voice or source
     "dedupe": {"by": "title", "keep": "ogden"},          # one copy of a title: keep the best-scored, the "lowest" id,
                                                          # or the first id read as text ("text": how v0.2's maker chose)
     "carry": ["lists/ogden-v0.1.csv"],                   # these lists' books are kept whole (the always-on rules still apply)
     "carry_only": false,                                 # true: the carried books alone, the rest of the library is not drawn on
     "not_in": ["lists/ogden-v0.1.csv"],                  # the books of these lists are left out of what is drawn
     "strike": [{"title": "...", "why": "..."}],          # named books struck, with the reason
     "append": [{"list": "lists/ogden-v0.2-tutor.csv", "why": "...", "words": null}],   # lists added after the composing
                                                          # (whole, or the first books of it up to `words` words)
     "words": null,                                       # a budget of words (None: as many as the shares allow); with a
                                                          # budget each group is filled up to its share, best-ranked books first
     "max_book_words": null,                              # leave out books longer than this (a small budget wants small books)
     "rank": "ogden",                                     # what a trim keeps: "ogden", "id" or "hash" (seeded)
     "order": "id"}                                       # the list's order: by id, or "carried-first" (carried lists as listed)

**Always on, whatever the selection says** (they are the gate's rules, not choices): the library's `recipe` books
only (never a hole card or a truth), none read by the decks (`held_out`), no shuffled control, and no credited
name dead after 1955 (S5 'period').

**Weights** are shares of the words. With no budget the corpus is the largest in which every named group holds
its share: each group is trimmed, lowest-ranked books first, to its share of the largest total all can fill.
A weighted group the library cannot fill at all is an error, never a silent zero.

`compose` is deterministic (the same facts and selection give the same list, byte for byte) and returns its
funnel (how many books each rule left), its counts by language, kind, voice, source and period, and the
prechecks of the S3 gate that read a library (period, decks, stores) on the list it wrote.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass, field

from thorp import library_facts as lf
from thorp import paths

DIMENSIONS = {"language": "language", "kind": "kind", "voice": "voice", "source": "source"}
RANKS = ("ogden", "id", "hash")
KEYS = {"as_of", "languages", "ogden", "period", "kinds", "voices", "sources", "shelves", "weights", "dedupe",
        "carry", "strike", "append", "words", "rank", "seed", "note", "order", "carry_only", "not_in", "max_book_words"}  # fmt: skip
LIST_FIELDS = ["title", "author", "language", "family", "text"]


class SelectionError(ValueError):
    pass


def validate(spec: dict) -> dict:
    """The selection in full form, or a SelectionError naming what is wrong."""
    bad = set(spec) - KEYS
    if bad:
        raise SelectionError(f"unknown selection keys: {sorted(bad)}")
    out = {
        "as_of": spec.get("as_of") or None,
        "languages": dict(spec.get("languages") or {}),
        "ogden": {"min": None, **(spec.get("ogden") or {})},
        "period": {"start": None, "end": None, "undated": "exclude", **(spec.get("period") or {})},
        "kinds": _incl(spec.get("kinds")),
        "voices": _incl(spec.get("voices")),
        "sources": _incl(spec.get("sources")),
        "shelves": _incl(spec.get("shelves")),
        "weights": {k: dict(v) for k, v in (spec.get("weights") or {}).items()},
        "dedupe": spec.get("dedupe") or None,
        "carry": list(spec.get("carry") or []),
        "carry_only": bool(spec.get("carry_only")),
        "max_book_words": int(spec["max_book_words"]) if spec.get("max_book_words") else None,
        "not_in": list(spec.get("not_in") or []),
        "strike": list(spec.get("strike") or []),
        "append": list(spec.get("append") or []),
        "words": int(spec["words"]) if spec.get("words") else None,
        "rank": spec.get("rank") or ("ogden" if (spec.get("ogden") or {}).get("min") is not None else "id"),
        "seed": int(spec.get("seed") or 0),
        "order": spec.get("order") or "id",
        "note": spec.get("note") or "",
    }
    if not out["languages"] or any(float(v) < 0 for v in out["languages"].values()) or sum(out["languages"].values()) <= 0:
        raise SelectionError("languages needs at least one language with a share above zero, e.g. {\"en\": 1.0}")
    if out["order"] not in ("id", "carried-first"):
        raise SelectionError('order is "id" or "carried-first"')
    if out["rank"] not in RANKS:
        raise SelectionError(f"rank must be one of {RANKS}")
    for k, w in out["weights"].items():
        if k not in DIMENSIONS or k == "language" or not w or sum(w.values()) <= 0:
            raise SelectionError(f"weights are by kind, voice or source (languages has its own); got {k!r}")
    for key, vocab in (("kinds", lf.KINDS), ("voices", lf.VOICES)):
        for v in (out[key]["include"] or []) + (out[key]["exclude"] or []):
            if v not in vocab:
                raise SelectionError(f"{key}: {v!r} is not one of {list(vocab)}")
    p = out["period"]
    if p["undated"] not in ("include", "exclude"):
        raise SelectionError("period.undated is include or exclude")
    if p["start"] is not None and p["end"] is not None and int(p["start"]) > int(p["end"]):
        raise SelectionError("period.start is after period.end")
    d = out["dedupe"]
    if d and (d.get("by") != "title" or d.get("keep", "ogden") not in ("ogden", "lowest", "text")):
        raise SelectionError('dedupe is {"by": "title", "keep": "ogden"|"lowest"|"text"}')
    return out


def _incl(v) -> dict:
    v = v or {}
    return {"include": list(v.get("include") or []), "exclude": list(v.get("exclude") or [])}


def spec_hash(spec: dict) -> str:
    return hashlib.sha1(json.dumps(validate(spec), sort_keys=True).encode()).hexdigest()[:12]


def _num(book: str) -> tuple:
    m = re.fullmatch(r"([a-z-]*?)(\d+)(.*)", book)
    return (m.group(1), int(m.group(2)), m.group(3)) if m else (book, 0, "")


def list_ids(lp: str) -> list[str]:
    """The books a list names by reference (`local:<id>`, `gutenberg:<n>`), in order."""
    p = paths.resolve(lp)
    out = []
    with p.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            t = r.get("text") or ""
            if t.startswith("local:"):
                out.append(t[6:])
            elif t.startswith("gutenberg:"):
                out.append("pg" + t.split(":", 1)[1])
    return out


@dataclass
class Composition:
    spec: dict
    facts_fingerprint: str
    books: list[dict] = field(default_factory=list)  # chosen library books, in list order
    appended: list[dict] = field(default_factory=list)  # rows of the appended lists
    funnel: list[tuple[str, int, str]] = field(default_factory=list)  # (rule, books left, what it did)
    notes: list[str] = field(default_factory=list)

    def rows(self) -> list[dict]:
        """The list's rows, as a recipe reads them."""
        out = [{"title": b["title"], "author": b["author"], "language": b["language"], "family": b.get("family") or "Germanic",
                "text": f"local:{b['book']}"} for b in self.books]  # fmt: skip
        return out + self.appended

    def summary(self) -> dict:
        from thorp import manifest

        bs = self.books
        tutor = {a["text"][6:] for a in self.appended}
        ap = [b for b in (manifest.get(i) for i in tutor) if b is not None]
        ap_words = int(sum((b.chars or 0) for b in ap) / lf.CHARS_PER_WORD)
        words = sum(b["words"] for b in bs)
        tot = words + ap_words
        return {
            "books": len(bs) + len(self.appended),
            "library_books": len(bs),
            "appended_books": len(self.appended),
            "words": tot,
            "library_words": words,
            "appended_words": ap_words,
            "appended_share": round(ap_words / tot, 4) if tot else 0.0,
            "by_language": _share(bs, "language"),
            "by_kind": _share(bs, "kind"),
            "by_voice": _share(bs, "voice"),
            "by_source": _share(bs, "source"),
            "by_period": _share(bs, lambda b: lf.decade(b["year"])),
            "by_year_basis": _share(bs, "year_basis"),
            "by_ogden": _share(bs, lambda b: "unscored" if b["ogden"] is None else f"{int(b['ogden'] * 20) * 5}%+"),
            "translated": sum(1 for b in bs if b["translated"]),
        }


def _share(bs: list[dict], key) -> dict:
    f = key if callable(key) else (lambda b: str(b.get(key)))
    c: dict[str, dict] = {}
    for b in bs:
        g = c.setdefault(f(b), {"books": 0, "words": 0})
        g["books"] += 1
        g["words"] += b["words"]
    tot = sum(v["words"] for v in c.values()) or 1
    return {k: {**v, "share": round(v["words"] / tot, 4)} for k, v in sorted(c.items(), key=lambda kv: -kv[1]["words"])}


def _meets(b: dict, bar: float) -> bool:
    """Ogden-ness at the bar. The scores files round to four places, so a book shown at the bar itself may
    stand either side of it (v0.2: The Greek View of Life above, Memories and Portraits below); only those are
    scored again from the text, exactly as the scores were made (thorp/ogden.py on its first 400,000 characters)."""
    if abs(b["ogden"] - bar) >= 5e-5:
        return b["ogden"] >= bar
    from thorp import ogden
    from thorp.sources import load_text

    return ogden.score(load_text(b["book"])[:400000])["ogden"] >= bar


def _priority(spec: dict):
    rank, seed = spec["rank"], spec["seed"]
    if rank == "ogden":
        return lambda b: (-(b["ogden"] if b["ogden"] is not None else -1), _num(b["book"]))
    if rank == "hash":
        return lambda b: hashlib.sha1(f"{seed}:{b['book']}".encode()).hexdigest()
    return lambda b: _num(b["book"])


def compose(spec: dict, facts: list[dict] | None = None) -> Composition:
    spec = validate(spec)
    facts = lf.build() if facts is None else facts
    comp = Composition(spec=spec, facts_fingerprint=lf.fingerprint(facts))
    pool = list(facts)

    def step(rule: str, keep, what: str) -> None:
        nonlocal pool
        pool = [b for b in pool if keep(b)]
        comp.funnel.append((rule, len(pool), what))

    comp.funnel.append(("the library", len(pool), "every book in the manifest"))
    carried_order = [i for lp in spec["carry"] for i in list_ids(lp)]
    carried: set[str] = set(carried_order)

    # always on: the gate's rules
    step("recipe books", lambda b: b["set"] == "recipe" or b["book"] in carried, "never a hole card or a truth (a carried list's books are kept as listed, and named in the notes)")
    comp.notes += [f"carried and not a recipe book: {b['book']} ({b['set']}) {b['title']}" for b in pool if b["set"] != "recipe" and b["book"] in carried]
    step("not held out", lambda b: not b["held_out"] and not b["control"], "none read by the decks, no shuffled control")
    step("period gate", lambda b: (b["gate_death"] or 0) <= lf.GATE_DEATH_LIMIT,
         f"no credited name dead after {lf.GATE_DEATH_LIMIT} (S5 'period')")  # fmt: skip
    # the sources never hand-listed: Thorp's own program's books come in only by `append`
    step("not derived", lambda b: b["source"] != "local" or b["book"] in carried, "Thorp's own derived books come in by append")

    if spec["carry_only"]:
        step("carried only", lambda b: b["book"] in carried, "the carried lists' books alone")
    left_out = {i for lp in spec["not_in"] for i in list_ids(lp)}
    if left_out:
        step("not in " + ", ".join(spec["not_in"]), lambda b: b["book"] not in left_out or b["book"] in carried,
             "left out: the books of these lists")  # fmt: skip
    if spec["max_book_words"]:
        step(f"books up to {spec['max_book_words']:,} words", lambda b: b["words"] <= spec["max_book_words"] or b["book"] in carried,
             "a small budget is filled with small books")  # fmt: skip
    if spec["as_of"]:
        step(f"as of {spec['as_of']}", lambda b: not b["fetched"] or b["fetched"] <= spec["as_of"] or b["book"] in carried,
             "the library as it stood that day")  # fmt: skip
    langs = {k: float(v) for k, v in spec["languages"].items() if float(v) > 0}
    step("language", lambda b: b["language"] in langs or b["book"] in carried, f"read in {sorted(langs)}")

    scored_by = spec["ogden"].get("scored_by")
    if scored_by:
        step(f"scored by {scored_by}", lambda b: b["ogden_from"] in scored_by or b["book"] in carried,
             "only books these scorings measured (the earlier scorings' books come in by carry)")  # fmt: skip
    o = spec["ogden"]["min"]
    if o is not None:
        step(f"Ogden-ness at least {o}", lambda b: (b["ogden"] is not None and _meets(b, float(o))) or b["book"] in carried,
             "at or above; unscored books fall short of a bar")  # fmt: skip
    p = spec["period"]
    if p["start"] is not None or p["end"] is not None:
        lo = int(p["start"]) if p["start"] is not None else -10**6
        hi = int(p["end"]) if p["end"] is not None else 10**6

        def in_period(b: dict) -> bool:
            if b["book"] in carried:
                return True
            if b["year"] is None:
                return p["undated"] == "include"
            return lo <= b["year"] <= hi

        step(f"period {p['start'] or '…'} to {p['end'] or '…'}", in_period,
             f"by the writer's year (floruit); undated books {p['undated']}d")  # fmt: skip
    for dim, key in (("kinds", "kind"), ("voices", "voice"), ("sources", "source")):
        inc, exc = spec[dim]["include"], spec[dim]["exclude"]
        if inc or exc:
            step(f"{dim}", lambda b, key=key, inc=inc, exc=exc: b["book"] in carried or
                 ((not inc or b[key] in inc) and b[key] not in exc), f"include {inc or 'all'}, exclude {exc or 'none'}")  # fmt: skip
    sh = spec["shelves"]
    if sh["include"] or sh["exclude"]:
        step("shelves", lambda b: b["book"] in carried or
             ((not sh["include"] or set(b["shelves"]) & set(sh["include"])) and not set(b["shelves"]) & set(sh["exclude"])),
             f"bookshelf include {sh['include'] or 'any'}, exclude {sh['exclude'] or 'none'}")  # fmt: skip
    # strikes (named, with the reason)
    struck_titles = {s["title"] for s in spec["strike"] if s.get("title")}
    struck_books = {s["book"] for s in spec["strike"] if s.get("book")}
    if struck_titles or struck_books:
        step("struck", lambda b: b["title"] not in struck_titles and b["book"] not in struck_books,
             "; ".join(f"{s.get('title') or s.get('book')} ({s.get('why', '')})" for s in spec["strike"]))  # fmt: skip
    # one copy a title
    d = spec["dedupe"]
    if d:
        carried_titles = {b["title_key"] for b in pool if b["book"] in carried}
        pr = {"ogden": lambda b: (-(b["ogden"] if b["ogden"] is not None else -1), _num(b["book"])),
              "lowest": lambda b: _num(b["book"]), "text": lambda b: b["book"]}[d.get("keep", "ogden")]  # fmt: skip
        seen: set[str] = set()
        keep_ids: set[str] = set()
        for b in sorted(pool, key=lambda b: (b["book"] not in carried, pr(b))):
            if b["book"] in carried:
                keep_ids.add(b["book"])
                seen.add(b["title_key"])
            elif b["title_key"] not in seen and b["title_key"] not in carried_titles:
                keep_ids.add(b["book"])
                seen.add(b["title_key"])
        step("one copy a title", lambda b: b["book"] in keep_ids, f"keep the first by {d.get('keep', 'ogden')}; carried titles win")

    # weights: language shares first, then kind, voice, source; trimmed by priority, lowest first
    prio = _priority(spec)
    dims = [("language", {k: v for k, v in langs.items()})] + [(k, {a: float(b) for a, b in w.items() if float(b) > 0}) for k, w in spec["weights"].items()]
    chosen = {b["book"]: b for b in pool}
    budget = spec["words"]
    if budget:  # a budget: fill each share of the last weighted dimension up to its words, best-ranked books first
        dim, shares = dims[-1]
        key, tot = DIMENSIONS[dim], sum(dims[-1][1].values())
        filled: dict[str, dict] = {}
        for g, sh in shares.items():
            target, got = budget * sh / tot, 0
            members = sorted((b for b in chosen.values() if b[key] == g and b["book"] not in carried), key=prio)
            if not members:
                raise SelectionError(f"{dim}: no book to fill the share of {g!r} after the filters")
            for b in members:
                if got + b["words"] <= target:
                    filled[b["book"]] = b
                    got += b["words"]
        chosen = {**{k: v for k, v in chosen.items() if k in carried}, **filled}
        dims = []  # the shares are met by filling; no trimming after it
    for _ in range(50):
        changed = False
        for dim, shares in dims:
            key = DIMENSIONS[dim]
            groups: dict[str, list[dict]] = {}
            for b in chosen.values():
                groups.setdefault(b[key], []).append(b)
            outside = [b for b in chosen.values() if b[key] not in shares and b["book"] not in carried]
            for b in outside:
                del chosen[b["book"]]
                changed = True
            tot = sum(shares.values())
            avail = {g: sum(b["words"] for b in groups.get(g, []) if b["book"] in chosen) for g in shares}
            missing = [g for g, a in avail.items() if a <= 0]
            if missing:
                raise SelectionError(f"{dim}: no book to fill the share of {missing} after the filters ({len(chosen)} books left)")
            ceiling = min(avail[g] / (shares[g] / tot) for g in shares)
            if budget:
                ceiling = min(ceiling, budget)
            for g in shares:
                target = ceiling * shares[g] / tot
                members = sorted((b for b in groups.get(g, []) if b["book"] in chosen), key=prio)
                got = sum(b["words"] for b in members)
                while members and got - members[-1]["words"] >= target and members[-1]["book"] not in carried:
                    b = members.pop()
                    got -= b["words"]
                    del chosen[b["book"]]
                    changed = True
        if not changed:
            break
    shortfall = ""
    if budget:
        got = sum(b["words"] for b in chosen.values())
        if got < budget * 0.97:
            shortfall = f"the library holds {got:,} of the {budget:,} words asked"
            comp.notes.append(shortfall)
    for dim, shares in dims:
        step_name = f"weights by {dim}"
        comp.funnel.append((step_name, len(chosen), ", ".join(f"{g} {s:g}" for g, s in shares.items())))
    order = {b: i for i, b in enumerate(carried_order)} if spec["order"] == "carried-first" else {}
    comp.books = sorted(chosen.values(), key=lambda b: (order.get(b["book"], len(order)), b["book"] if spec["order"] == "carried-first" else _num(b["book"])))
    from thorp import manifest

    for ap in spec["append"]:
        with paths.resolve(ap["list"]).open(encoding="utf-8") as f:
            rows = [{k: r.get(k, "") for k in LIST_FIELDS} for r in csv.DictReader(f)]
        cap, got, taken = ap.get("words"), 0, []
        for r in rows:
            if cap and got >= cap:
                break
            taken.append(r)
            bk = manifest.get(r["text"].split(":", 1)[-1]) if r["text"].startswith("local:") else None
            got += int((bk.chars if bk else 0) / lf.CHARS_PER_WORD)
        comp.appended += taken
    if spec["append"]:
        comp.funnel.append(("appended", len(comp.books) + len(comp.appended), "; ".join(f"{a['list']}{' to ' + format(a['words'], ',') + ' words' if a.get('words') else ''} ({a.get('why', '')})" for a in spec["append"])))
    return comp


def write_list(comp: Composition, lp: str) -> str:
    """The list on disk (a fixed list, as a recipe reads it); its sha1."""
    p = paths.resolve(lp)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LIST_FIELDS)
        w.writeheader()
        w.writerows(comp.rows())
    return hashlib.sha1(p.read_bytes()).hexdigest()


def prechecks(lp: str, opt_in: str = "", fitout_key: str = "") -> list[dict]:
    """The S3 gate's library prechecks (period, decks, stores) read on a list: the same items the fitout must
    pass before it sails, read now on the list the selection has just made."""
    from thorp.viable.precheck_item import Context
    from thorp.viable.s3_control import prechecks as s3

    ctx = Context(fitout={"key": fitout_key or "composed", "stages": [{"shelf": lp}]},
                  specs=[{"data": {"opt_in": opt_in}}] if opt_in else [])  # fmt: skip
    out = []
    for it in s3.ITEMS:
        if it.key == "library.enough_text":
            continue  # it needs the fitout's shared tokeniser and its classes: read when the fitout is checked whole
        value, ev = it.run(ctx)
        out.append({"key": it.key, "name": it.name, "value": value, "passed": it.passes(value), "evidence": ev})
    return out


def diff(comp: Composition, lp: str) -> dict:
    """The composed list against a list on disk: books only in one, only in the other, and whether the order differs."""
    want = [b["book"] for b in comp.books] + [a["text"][6:] for a in comp.appended]
    have = list_ids(lp)
    from thorp import manifest

    def label(i: str) -> str:
        b = manifest.get(i)
        return f"{i} {b.title if b else ''}"[:90]

    return {
        "composed": len(want),
        "list": len(have),
        "only_composed": [label(i) for i in sorted(set(want) - set(have), key=_num)],
        "only_list": [label(i) for i in sorted(set(have) - set(want), key=_num)],
        "same_books": set(want) == set(have),
        "same_order": want == have,
    }

"""A branch's saved configurations: the JSON of choices, not a version (11 November, Justin: "my thinking is
that branches ... have not so much a version but rather a set of attributes. Like for ogden it would be size,
books, control tokens, language, content_makeup ... and date. So there's too many variables so my thinking is
that a branch doesn't get a version but rather a json of choices").

A **branch** is a purpose (Ogden, the decks, the scanned corpus). A **configuration** is a JSON object of choices
drawn against the library's facts: how much text (`size`), which books (`books`), how the text is marked
(`control_tokens`), the language shares, the content makeup by kind/voice/source, the kinds of knowledge
(`knowledge`: general knowledge, metaphysics, empirical knowledge, logic and maths, each a share of the words),
the period, and the Ogden bar.
A configuration is saved with a name and a content hash; saving the same choices twice is the same
configuration. A voyage reads the composed list and its SHA-1, so a run is reproducible without a version number.

The old named lists (`lists/ogden-v0.1.csv`, ...) stay as **sailed** configurations: read-only rows in
`s3.library_variations`, never rewritten. A new configuration is a row in `s3.library_configs` (migration
`x5s8t1u4v7w0`) and is what the branch page's controls save.

`to_selection` is the bridge to the existing composer (`thorp/selection.py`): the book-choice half of a
configuration is a selection spec, with `carry_only` for an exact list. `control_tokens` is a format choice; it
changes the text, not which books are chosen.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from thorp import library_facts as lf
from thorp import paths, selection

SCHEMA = "branch-config/1"

# Which controls a branch exposes. A branch is not forced to carry controls that make no sense for it: the
# decks are exact lists, the ancient world is a set of lists, Ogden is the full composition space.
ATTRIBUTES: dict[str, list[str]] = {
    "ogden": ["size", "books", "control_tokens", "language", "knowledge", "content_makeup", "date", "ogden"],
    "library": ["books", "control_tokens"],
    "scanned": ["size", "books", "control_tokens", "language", "knowledge", "content_makeup", "date"],
    "ancient": ["size", "books", "control_tokens", "language"],
    "decks": ["books", "control_tokens"],
    "content": ["books", "control_tokens"],
    "levers": ["books", "control_tokens"],
    "early": ["books", "control_tokens"],
}

# The language of a known list, so a locked list opened as a starting point does not read as English.
_LIST_LANGUAGE: dict[str, dict[str, float]] = {
    "lists/perseus-latin.csv": {"la": 1.0},
    "lists/perseus-greek.csv": {"grc": 1.0},
    "lists/etcsl.csv": {"sux": 1.0},
    "lists/cdli-sux.csv": {"sux": 1.0},
}

_TOKEN_WRAPS = ("none", "bos-eos")
_TOKEN_TURNS = ("plain", "marked")
_BOOK_MODES = ("select", "list", "all")
_DEDUPE = ("title", "none")


def _base() -> dict:
    return {
        "size": {"words": None, "max_book_words": None},
        "books": {"mode": "select", "list": None, "rank": "ogden", "dedupe": "title", "order": "id",
                  "carry": [], "not_in": [], "strike": [],
                  "filters": {k: {"include": [], "exclude": []} for k in ("kinds", "voices", "sources", "shelves")}},
        "control_tokens": {"wrap": "none", "turns": "plain"},
        "language": {"en": 1.0},
        "content_makeup": {"kind": {}, "voice": {}, "source": {}},
        # the kinds of knowledge the ship sails with, as shares of the words; empty is the branch as it falls
        "knowledge": {},
        "date": {"start": None, "end": None, "undated": "exclude"},
        "ogden": {"min": None},
    }


def _int(v: Any) -> int | None:
    if v is None or v == "":
        return None
    n = int(v)
    return n


def _floats(d: Any) -> dict[str, float]:
    if not isinstance(d, dict):
        return {}
    return {str(k): float(v) for k, v in d.items() if v is not None and float(v) > 0}


def _lists(v: Any) -> list[str]:
    if not isinstance(v, list):
        return []
    return [str(x) for x in v if str(x).strip()]


def attributes(branch_key: str) -> list[str]:
    return list(ATTRIBUTES.get(branch_key, ["books", "control_tokens"]))


def validate(branch_key: str, choices: dict | None) -> dict:
    """The choices in full form, or ValueError naming what is wrong. Missing choices take the base."""
    if branch_key not in ATTRIBUTES:
        raise ValueError(f"no branch {branch_key!r}")
    if choices is None:
        choices = {}
    if not isinstance(choices, dict):
        raise ValueError("choices must be a JSON object")
    out = defaults(branch_key)  # a partial JSON still starts from the branch's own defaults

    size = choices.get("size") or {}
    if not isinstance(size, dict):
        raise ValueError("size must be an object")
    out["size"]["words"] = _int(size.get("words")) or None
    if out["size"]["words"] is not None and out["size"]["words"] < 0:
        raise ValueError("size.words must be zero or more")
    out["size"]["max_book_words"] = _int(size.get("max_book_words")) or None
    if out["size"]["max_book_words"] is not None and out["size"]["max_book_words"] <= 0:
        raise ValueError("size.max_book_words must be above zero")

    books = choices.get("books") or {}
    if not isinstance(books, dict):
        raise ValueError("books must be an object")
    mode = books.get("mode") or "select"
    if mode not in _BOOK_MODES:
        raise ValueError(f"books.mode must be one of {_BOOK_MODES}")
    out["books"]["mode"] = mode
    out["books"]["list"] = (books.get("list") or None) if mode == "list" else None
    if mode == "list":
        if not out["books"]["list"]:
            raise ValueError("books.mode is list, so books.list must name a list")
        if not paths.resolve(str(out["books"]["list"])).exists():
            raise ValueError(f"no list {out['books']['list']!r}")
    rank = books.get("rank") or "ogden"
    if rank not in selection.RANKS:
        raise ValueError(f"books.rank must be one of {selection.RANKS}")
    out["books"]["rank"] = rank
    dedupe = books.get("dedupe") or "title"
    if dedupe not in _DEDUPE:
        raise ValueError(f"books.dedupe must be one of {_DEDUPE}")
    out["books"]["dedupe"] = dedupe
    order = books.get("order") or "id"
    if order not in ("id", "carried-first"):
        raise ValueError('books.order must be "id" or "carried-first"')
    out["books"]["order"] = order
    out["books"]["carry"] = _lists(books.get("carry"))
    out["books"]["not_in"] = _lists(books.get("not_in"))
    out["books"]["strike"] = books.get("strike") if isinstance(books.get("strike"), list) else []
    filters = books.get("filters") or {}
    if not isinstance(filters, dict):
        raise ValueError("books.filters must be an object")
    for key, vocab in (("kinds", lf.KINDS), ("voices", lf.VOICES), ("sources", None), ("shelves", None)):
        got = filters.get(key) or {}
        if not isinstance(got, dict):
            raise ValueError(f"books.filters.{key} must be an object")
        inc, exc = _lists(got.get("include")), _lists(got.get("exclude"))
        if vocab is not None:
            bad = sorted({*inc, *exc} - set(vocab))
            if bad:
                raise ValueError(f"books.filters.{key}: not one of {list(vocab)}: {bad}")
        out["books"]["filters"][key] = {"include": inc, "exclude": exc}

    tokens = choices.get("control_tokens") or {}
    if not isinstance(tokens, dict):
        raise ValueError("control_tokens must be an object")
    wrap = tokens.get("wrap") or "none"
    if wrap not in _TOKEN_WRAPS:
        raise ValueError(f"control_tokens.wrap must be one of {_TOKEN_WRAPS}")
    turns = tokens.get("turns") or "plain"
    if turns not in _TOKEN_TURNS:
        raise ValueError(f"control_tokens.turns must be one of {_TOKEN_TURNS}")
    out["control_tokens"] = {"wrap": wrap, "turns": turns}

    langs = _floats(choices.get("language") if "language" in choices else out["language"])
    if not langs:
        raise ValueError("language needs at least one language with a share above zero")
    out["language"] = langs

    makeup = choices.get("content_makeup") or {}
    if not isinstance(makeup, dict):
        raise ValueError("content_makeup must be an object")
    for dim, vocab in (("kind", lf.KINDS), ("voice", lf.VOICES)):
        got = _floats(makeup.get(dim))
        bad = sorted(set(got) - set(vocab))
        if bad:
            raise ValueError(f"content_makeup.{dim}: not one of {list(vocab)}: {bad}")
        out["content_makeup"][dim] = got
    out["content_makeup"]["source"] = _floats(makeup.get("source"))

    if "knowledge" in choices and not isinstance(choices.get("knowledge") or {}, dict):
        raise ValueError("knowledge must be an object of shares")
    knowledge = _floats(choices.get("knowledge"))
    bad = sorted(set(knowledge) - set(lf.KNOWLEDGE))
    if bad:
        raise ValueError(f"knowledge: not one of {list(lf.KNOWLEDGE)}: {bad}")
    out["knowledge"] = {k: knowledge[k] for k in lf.KNOWLEDGE if k in knowledge}  # the house order, so one hash

    date = choices.get("date") or {}
    if not isinstance(date, dict):
        raise ValueError("date must be an object")
    start, end = _int(date.get("start")), _int(date.get("end"))
    if start is not None and end is not None and start > end:
        raise ValueError("date.start is after date.end")
    undated = date.get("undated") or "exclude"
    if undated not in ("include", "exclude"):
        raise ValueError('date.undated must be "include" or "exclude"')
    out["date"] = {"start": start, "end": end, "undated": undated}

    if "ogden" in choices:
        ogden = choices.get("ogden") or {}
        if not isinstance(ogden, dict):
            raise ValueError("ogden must be an object")
        bar = ogden.get("min")
        bar = None if bar in (None, "") else float(bar)
        if bar is not None and not 0.0 <= bar <= 1.0:
            raise ValueError("ogden.min must be between 0 and 1")
        out["ogden"] = {"min": bar}
    return out


def config_hash(branch_key: str, choices: dict) -> str:
    """A configuration's identity: the branch and its full, normalised JSON of choices."""
    full = validate(branch_key, choices)
    if not full["knowledge"]:  # a configuration saved before the choice existed keeps the identity it had
        del full["knowledge"]
    body = json.dumps({"branch": branch_key, "choices": full}, sort_keys=True, separators=(",", ":"))
    return hashlib.sha1(body.encode()).hexdigest()


def key_for(branch_key: str, choices: dict) -> str:
    return f"{branch_key}-{config_hash(branch_key, choices)[:12]}"


def to_selection(choices: dict) -> dict:
    """The book-choice half as `thorp/selection.py` reads it. `control_tokens` is deliberately not here: it
    marks the text after the books are chosen."""
    c = choices
    spec = {
        "languages": c["language"],
        "ogden": {"min": c["ogden"]["min"]} if c["ogden"]["min"] is not None else {},
        "period": c["date"],
        # knowledge last: with a budget of words the composer fills the shares of the last weighted dimension
        "weights": {**{k: v for k, v in c["content_makeup"].items() if v},
                    **({"knowledge": dict(c["knowledge"])} if c["knowledge"] else {})},
        "dedupe": {"by": "title", "keep": "ogden"} if c["books"]["dedupe"] == "title" else None,
        "kinds": c["books"]["filters"]["kinds"], "voices": c["books"]["filters"]["voices"],
        "sources": c["books"]["filters"]["sources"], "shelves": c["books"]["filters"]["shelves"],
        "carry": list(c["books"]["carry"]),
        "not_in": list(c["books"]["not_in"]),
        "strike": list(c["books"]["strike"]),
        "words": c["size"]["words"],
        "max_book_words": c["size"]["max_book_words"],
        "rank": c["books"]["rank"],
        "order": c["books"]["order"],
        "carry_only": False,
    }
    if c["books"]["mode"] == "list":
        spec["carry"] = [c["books"]["list"], *spec["carry"]]
        spec["carry_only"] = True
    return selection.validate(spec)


def _summary(books: list[dict], facts: list[dict], spec: dict | None) -> dict:
    comp = selection.Composition(
        spec=spec or {}, facts_fingerprint=lf.fingerprint(facts), books=books, appended=[]
    )
    return comp.summary()


def books_for(branch_key: str, choices: dict, facts: list[dict]) -> tuple[list[dict], dict | None]:
    """The books a configuration holds, and the selection spec when it has one."""
    c = validate(branch_key, choices)
    mode = c["books"]["mode"]
    if mode == "all":
        return [f for f in facts if f["source"] != "local"], None
    if mode == "list":
        from thorp import library_branches

        ids = library_branches.variation_ids({"list": c["books"]["list"]}, facts)
        by_id = {f["book"]: f for f in facts}
        return [by_id[i] for i in ids if i in by_id], to_selection(c)
    spec = to_selection(c)
    return selection.compose(spec, facts).books, spec


def preview(branch_key: str, choices: dict, facts: list[dict]) -> dict:
    """What a configuration holds, for the branch page's live card and its JSON."""
    c = validate(branch_key, choices)
    books, spec = books_for(branch_key, c, facts)
    summary = _summary(books, facts, spec)
    return {
        "schema": SCHEMA,
        "branch": branch_key,
        "choices": c,
        "spec": spec,
        "config_hash": config_hash(branch_key, c),
        "summary": summary,
        "books": [b["book"] for b in books],
        "control_tokens": c["control_tokens"],
    }


def from_variation(v: dict) -> dict:
    """A sailed variation as a starting point for the editor: a list, an all-books variation, or a selection.
    The old row is not changed; saving the editor writes a new configuration."""
    d = _base()
    if v.get("all"):
        d["books"]["mode"] = "all"
        return d
    if v.get("list"):
        d["books"]["mode"] = "list"
        d["books"]["list"] = v["list"]
        d["language"] = dict(_LIST_LANGUAGE.get(v["list"], {"en": 1.0}))
        return d
    if v.get("spec"):
        try:
            s = selection.validate(v["spec"])
        except selection.SelectionError:
            return d
        d["language"] = dict(s["languages"]) or {"en": 1.0}
        d["ogden"] = {"min": s["ogden"]["min"]}
        d["date"] = {"start": s["period"]["start"], "end": s["period"]["end"], "undated": s["period"]["undated"]}
        d["content_makeup"] = {k: dict(s["weights"].get(k) or {}) for k in ("kind", "voice", "source")}
        d["knowledge"] = dict(s["weights"].get("knowledge") or {})
        d["size"] = {"words": s["words"], "max_book_words": s["max_book_words"]}
        d["books"] = {"mode": "select", "list": None, "rank": s["rank"],
                      "dedupe": "title" if s["dedupe"] else "none", "order": s["order"],
                      "carry": list(s["carry"]), "not_in": list(s["not_in"]), "strike": list(s["strike"]),
                      "filters": {k: {"include": list(s[k]["include"]), "exclude": list(s[k]["exclude"])}
                                  for k in ("kinds", "voices", "sources", "shelves")}}
    return d


def defaults(branch_key: str, variations: list[dict] | None = None) -> dict:
    """The choices the editor opens on. Ogden opens at its 68% bar; another branch opens on its first sailed
    variation, so the editor begins on something that has actually been read."""
    if branch_key == "ogden":
        d = _base()
        d["ogden"]["min"] = 0.68
        d["books"]["rank"] = "ogden"
        d["books"]["dedupe"] = "title"
        return d
    if variations:
        return from_variation(variations[0])
    return _base()

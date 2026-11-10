"""The rule of the ship's stores (2026-11-07, Justin): "from now on runs can only occur on two canonical
stores: one optimised for prose and one optimised for trigrams. All runs have to use one or the other.
No other data for runs can be used unless explicitly opted in."

- **The stores** (scripts/make_stores.py, frozen in s1.stores): `lists/stores/prose.csv`, the prose
  stores (narrative ranked by names recurring within the window), and `lists/stores/trigram.csv`, the
  trigram stores (everything else ranked by in-window trigram repetition).
- **The rule**, checked when a run is prepared (`check(spec)`): every list a run reads (`data.recipe`,
  each `data.stages[*].recipe`, `data.first`) is one of the stores, and each store's file still matches
  its frozen hash. A spec may read anything else only with `data.opt_in` set to the reason, in words:
  an explicit opt-in, recorded with the run. Lists a run only refuses, scores on or trains its tokeniser
  on are not reading, and are not checked.
- **Runs that are not new**: a run whose spec was already in the ledger before the rule (its run id is
  known) continues as it was.
"""

from __future__ import annotations

import hashlib

from thorp import paths

RULE_FROM = "2026-11-07T15:55"  # the rule's time, so a log can say which runs it governed


def stores() -> dict:
    """The ship's stores, as frozen (s1.stores): {key: {path, books, tokens, sha1, ranked_by, ...}}."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import StoreList

    if store.papers():  # aboard a hired box: as frozen when it sailed
        return dict(store.read_papers().get("stores") or {})
    with store.session() as s:
        return {r.key: {"path": r.path, "books": r.books, "tokens": r.tokens, **(r.measures or {}), "sha1": r.sha1}
                for r in s.scalars(select(StoreList))}  # fmt: skip


def freeze(stores_: dict) -> None:
    """The stores frozen in the store (scripts/make_stores.py), each replacing its earlier freeze."""
    from thorp import store
    from thorp.viable.records import StoreList

    with store.session() as s:
        for k, v in stores_.items():
            rest = {x: y for x, y in v.items() if x not in ("path", "books", "tokens", "sha1")}
            s.merge(StoreList(key=k, path=v["path"], books=int(v["books"]), tokens=int(v["tokens"]), sha1=v["sha1"], measures=rest))


def store_paths() -> set[str]:
    return {s["path"] for s in stores().values()}


def reads(spec: dict) -> list[str]:
    d = spec.get("data", {})
    out = [d.get("recipe"), d.get("first")] + [s.get("recipe") for s in d.get("stages") or []]
    return [x for x in out if isinstance(x, str)]


class StoresRuleError(ValueError):
    pass


def enforced() -> bool:
    """Whether the rule is switched on: S5's switch for the policy 'stores' (thorp/vsm.py,
    s5.policy_switches); off until Justin decides what happens to the runs queued before it (15:55)."""
    from thorp import vsm

    return vsm.enforced("stores")


_TEXTS_CACHE: dict[tuple[str, int], set[str]] = {}


def _texts(lp: str) -> set[str]:
    """The texts a list names, cached on the file's mtime: the audit asks the same store lists once a
    spec, and re-reading them each time was the other half of /api/governance's cost."""
    import csv

    p = paths.resolve(lp)
    if not p.exists():
        return set()
    key = (str(p), p.stat().st_mtime_ns)
    hit = _TEXTS_CACHE.get(key)
    if hit is not None:
        return hit
    with p.open() as f:
        out = {r.get("text") or "" for r in csv.DictReader(f)}
    _TEXTS_CACHE[key] = out
    return out


def drawn_from_stores(lp: str) -> bool:
    """A list every book of which is in the stores (a fitout stage that takes part of a store, or both)
    reads the stores: the rule governs the books, not the file name."""
    books = _texts(lp)
    within = set().union(*(_texts(s["path"]) for s in stores().values())) if stores() else set()
    return bool(books) and books <= within


def check(spec: dict, known_run: bool = False, always: bool = False) -> str:
    """'' when the spec keeps the rule; the opt-in's reason when it opts out; raises otherwise.
    `always` checks even while the rule is switched off (the S3* audit's view)."""
    if known_run or not (always or enforced()):
        return ""
    st = stores()
    if not st:  # before the stores exist there is nothing to hold a run to
        return ""
    opt_in = (spec.get("data", {}).get("opt_in") or "").strip()
    allowed = {s["path"]: s for s in st.values()}
    outside = [x for x in reads(spec) if x not in allowed and not drawn_from_stores(x)]
    for x in reads(spec):
        if x in allowed:
            now = hashlib.sha1(paths.resolve(x).read_bytes()).hexdigest()
            if now != allowed[x]["sha1"]:
                raise StoresRuleError(
                    f"the store {x} has changed since it was frozen (s1.stores)"
                )
    if outside and not opt_in:
        raise StoresRuleError(
            "runs read the ship's stores only (lists/stores/prose.csv or lists/stores/trigram.csv); "
            f"{spec.get('name')} reads {outside}. To read anything else, set data.opt_in to the reason."
        )
    return opt_in if outside else ""

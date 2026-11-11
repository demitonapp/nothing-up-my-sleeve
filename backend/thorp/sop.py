"""The SOP as data: the standard a voyage is built to (8 November, Justin: "should the scaffold be part of the SOP
data model with a relationship to a voyage in postgres ... one line of the voyages
sop.pretraining_phases.[content, scaffold] ... yeah do it").

The standard lives in `s5.sop_versions` (one row a version), and the prose stays in `ships/plans/sop-v<version>.md`;
the row is the machine's copy and points at the document. A voyage names its version (`sop: '0.0.1'` in the spec) and
may declare `departures`: what it does differently, and why. A voyage that names no version is not refused — the
cutover is Justin's to set — but a voyage that names one is held to it.

- `standard(version)` — the row, or the built-in copy when the store has none yet.
- `check(spec)` — the gate's question: the version exists, and the spec's content, tokeniser, size parameters and
  scaffold match it. A declared departure is not a violation: it is a departure, and it is recorded.
- `resolve(spec)` — the standard's scaffold for this size, for a voyage that omits its own (not used by the trainer
  yet: it still reads `optim.scaffold`).

The build is deliberately small: the cards and phases are JSONB inside the row (one consumer today), not tables; the
prose is not in Postgres; the readings stay where they are.
"""

from __future__ import annotations

import contextlib

VERSIONS = ("0.0.1", "0.0.2", "0.0.3", "0.0.4", "0.0.5", "0.0.6")
CURRENT = "0.0.5"  # 0.0.6 carries the post-training stage, not yet sailable


# The standard as built (ships/plans/sop-v0.0.1.md, §2, §3 and §4a). The row in s5.sop_versions is the source of
# truth once seeded; this copy is what `thorp sop seed` writes and what a bare checkout can still be read against.
def _builtin(version: str) -> dict | None:
    """A version's standard from its file (`ships/plans/sop-v<version>.json`) — **seed input only** (9 November, Justin:
    "the json shouldn't be a file it should be stored in postgres"). Once seeded, `s5.sop_versions` is the source and the
    file is deleted; `standard()` never reads it."""
    import json

    from thorp import paths

    p = paths.resolve(f"ships/plans/sop-v{version}.json")
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


# the built-in copies, read once, so a bare checkout can be read against without the store
STANDARD: dict[str, dict] = {v: std for v in VERSIONS if (std := _builtin(v))}


def standard(version: str = CURRENT) -> dict | None:
    """The version's standard, from **Postgres** — `s5.sop_versions`, one row a version (9 November, Justin: "the json
    shouldn't be a file it should be stored in postgres"). The files are seed input only; a version that is not in the
    register does not exist, file or no file."""
    from thorp import store

    with contextlib.suppress(Exception):
        from thorp.viable.records import SOPVersion

        with store.session() as s:
            row = s.get(SOPVersion, version)
            if row is not None:
                return {**(row.standard or {}), "adopted": row.adopted, "doc": row.doc,
                        "supersedes": row.supersedes}  # fmt: skip
    return None


def at_sea() -> dict[str, str]:
    """The SOP versions with a voyage at sea: version -> the run's name.

    A version with a ship out is **locked** (9 November, Justin: "any time a SOP has a ship out then
    it's locked and you can't make any more changes to that SOP version"). The lock is a reading of
    the store, not a flag: a run's status and its `sop_version` decide it, so it lifts by itself when
    the ship docks.
    """
    out: dict[str, str] = {}
    from thorp.ledger import _use_pg

    if _use_pg():
        # at home the store is the ledger: a store that is down raises StoreDown rather than reading the old
        # ledger.sqlite, whose 'running' rows stopped moving at the cut-over (11 November)
        from sqlalchemy import text

        from thorp import store

        try:
            with store.session() as s:
                rows = s.execute(
                    text("select sop_version, name from s1.runs where status = 'running' and sop_version is not null")
                )
                return {str(v): str(n or "") for v, n in rows}
        except store.StoreDown:
            raise
        except Exception:  # noqa: BLE001  a store without the column yet: no version is locked
            return out
    # a hired box's own SQLite ship's log: it knows the version inside the spec
    with contextlib.suppress(Exception):
        import json

        from thorp.ledger import connect

        con = connect()
        for row in con.execute("select name, spec_json from runs where status = 'running' and spec_json is not null"):
            with contextlib.suppress(Exception):
                v = json.loads(row["spec_json"]).get("sop")
                if v:
                    out[str(v)] = str(row["name"] or "")
    return out


def versions() -> list[str]:
    """Every version the store holds, oldest first, or the built-in list when the store has none."""
    from thorp import store

    with contextlib.suppress(Exception):
        from sqlalchemy import select

        from thorp.viable.records import SOPVersion

        with store.session() as s:
            got = [r.version for r in s.scalars(select(SOPVersion).order_by(SOPVersion.version))]
            if got:
                return sorted(set(got) | set(VERSIONS))
    return list(VERSIONS)


def seed() -> int:
    """Write the built-in standards into s5.sop_versions (idempotent: the same bytes, the same row)."""
    from thorp import store
    from thorp.viable.records import SOPVersion

    n = 0
    with store.session() as s:
        for version, std in STANDARD.items():
            row = s.get(SOPVersion, version)
            if row is None:
                row = SOPVersion(version=version)
                s.add(row)
            row.adopted = std["adopted"]
            row.doc = std["doc"]
            row.supersedes = std.get("supersedes")
            row.standard = {
                k: v for k, v in std.items() if k not in ("adopted", "doc", "supersedes")
            }
            n += 1
    return n


REQUIRED = ("content", "parameters", "sizes", "cards", "phases", "readings")


def validate(standard: dict) -> dict:
    """The SOP variables a version must carry, and the rough shapes the gate reads. Unknown keys are kept:
    a standard may grow before this validator knows the new variable."""
    if not isinstance(standard, dict):
        raise ValueError("the SOP standard is a JSON object")
    missing = [k for k in REQUIRED if k not in standard]
    if missing:
        raise ValueError(f"the SOP standard is missing {', '.join(missing)}")
    if not isinstance(standard["content"], dict) or not isinstance(standard["parameters"], dict):
        raise ValueError("content and parameters are objects")
    if not isinstance(standard["sizes"], dict):
        raise ValueError("sizes is an object of size -> {lr, warmup_steps}")
    for size, p in standard["sizes"].items():
        if not isinstance(p, dict):
            raise ValueError(f"sizes.{size} is an object")
    if not isinstance(standard["cards"], list) or not all(isinstance(c, str) for c in standard["cards"]):
        raise ValueError("cards is a list of card keys")
    if not isinstance(standard["phases"], list):
        raise ValueError("phases is a list")
    if not isinstance(standard["readings"], list):
        raise ValueError("readings is a list")
    return {
        k: v for k, v in standard.items() if k not in ("adopted", "doc", "supersedes")
    }


def next_version() -> str:
    """The next patch version after the highest the store holds (0.0.5 -> 0.0.6)."""
    def parts(v: str) -> tuple[int, int, int]:
        try:
            a, b, c = (int(x) for x in v.split(".")[:3])
            return a, b, c
        except (ValueError, TypeError):
            return (0, 0, 0)

    high = max((parts(v) for v in versions()), default=(0, 0, 0))
    return f"{high[0]}.{high[1]}.{high[2] + 1}"


def save(standard: dict, *, adopted: str, doc: str = "", version: str | None = None,
         supersedes: str | None = None) -> str:
    """Define a new SOP version from the ship_builder's edited variables. A version is never overwritten:
    the next patch is written, and the current version stays in force until a spec names the new one."""
    from thorp import store
    from thorp.viable.records import SOPVersion

    body = validate(standard)
    v = version or next_version()
    if v in versions():
        raise ValueError(f"SOP v{v} already exists; a saved version is not overwritten")
    with store.session() as s:
        row = SOPVersion(
            version=v,
            adopted=adopted,
            doc=doc,
            supersedes=supersedes or (versions()[-1] if versions() else None),
            standard=body,
        )
        s.add(row)
    return v


def _departures(spec: dict) -> list[str]:
    d = spec.get("departures")
    if isinstance(d, str):
        return [d]
    return [str(x) for x in (d or [])]


def check(spec: dict) -> list[str]:
    """The gate's question: a voyage that names an SOP version is built to it — the same content, tokeniser and size
    parameters, and the standard's cards in the standard's order. A declared departure is recorded, and so is not a
    violation; a voyage that names no version is not refused (the cutover is Justin's to set)."""
    version = spec.get("sop")
    if not version:
        return []
    std = standard(str(version))
    if std is None:
        return [f"names SOP v{version}, which does not exist (have: {', '.join(versions())})"]
    out: list[str] = []
    # a declared departure is not a violation (the module's own rule): a spec may name the standard and
    # say which of its blocks it departs from, and why. Only the declared block is excused — everything
    # else is still held to the version (9 November, Justin: "wouldn't we run 4 on the 0.0.5 SOP": the
    # IFEval arm reads an instruction corpus under v0.0.5 rather than a new standard).
    declared = {
        (d.get("field") if isinstance(d, dict) else str(d))
        for d in (spec.get("departures") or [])
    }

    def departed(field: str) -> bool:
        return field in declared

    content, params = std["content"], std["parameters"]
    data = dict(spec.get("data") or {})
    # a staged corpus: the content stage (the one that reads the standard's recipe) carries the check, so a voyage
    # with a card stage before Ogden is judged on the Ogden it actually reads
    for st in data.get("stages") or []:
        if (st.get("recipe") or "") == content["recipe"]:
            data = {**data, "recipe": st.get("recipe"), "passes": st.get("passes", data.get("passes"))}
            break
    if departed("content"):
        pass
    elif data.get("recipe") != content["recipe"]:
        out.append(f"reads {data.get('recipe')!r}; SOP v{version} reads {content['recipe']!r}")
    if not departed("content") and data.get("clean") != content["clean"]:
        out.append(
            f"cleans with {data.get('clean')!r}; SOP v{version} cleans with {content['clean']!r}"
        )
    if not departed("content") and int(data.get("passes", 1)) != int(content["passes"]):
        out.append(f"reads {data.get('passes')} passes; SOP v{version} reads {content['passes']}")
    emb = std.get("embeddings") or {}
    chosen = emb.get("chosen")
    if chosen:
        v = (emb.get("versions") or {}).get(chosen) or {}
        if str((spec.get("tokeniser") or {}).get("vocab")) != str(v.get("vocab")):
            out.append(f"tokeniser vocab {(spec.get('tokeniser') or {}).get('vocab')}; SOP v{version} chooses {chosen} ({v.get('vocab')} pieces)")
    tok = spec.get("tokeniser") or {}
    want_sym = list(((emb.get("versions") or {}).get(chosen) or {}).get("control_tokens") or [])
    got_sym = list((spec.get("tokeniser") or {}).get("symbols") or [])
    if sorted(got_sym) != sorted(want_sym) and not departed("tokeniser"):
        out.append(f"tokeniser declares {len(got_sym)} control tokens; SOP v{version}'s {chosen} declares {len(want_sym)}")
    for key in () if departed("tokeniser") else ("kind", "vocab", "byte_fallback", "train_on"):
        if tok.get(key) != content["tokeniser"].get(key):
            out.append(
                f"tokeniser {key} {tok.get(key)!r}; SOP v{version} has {content['tokeniser'].get(key)!r}"
            )
    size = (spec.get("model") or {}).get("preset")
    params_size = (std.get("sizes") or {}).get(str(size))
    optim = spec.get("optim") or {}
    if params_size:
        if float(optim.get("lr", 0)) != float(params_size["lr"]):
            out.append(f"lr {optim.get('lr')}; SOP v{version} at {size} is {params_size['lr']}")
        if int(optim.get("warmup_steps", 0)) != int(params_size["warmup_steps"]):
            out.append(
                f"warmup {optim.get('warmup_steps')}; SOP v{version} at {size} is {params_size['warmup_steps']}"
            )
    if int((spec.get("model") or {}).get("context", 0)) != int(params["context"]):
        out.append(f"context {spec['model'].get('context')}; SOP v{version} is {params['context']}")
    sc = optim.get("scaffold") or {}
    if not sc:
        out.append(f"names SOP v{version} but declares no scaffold phase")
        return out
    if float(sc.get("floor", 0.0)) > 0:
        out.append(
            f"carries a floor of {sc.get('floor')}; SOP v{version} has none (a floor is never by heart)"
        )
    cards = [h.get("card") for h in sc.get("heads") or []]
    # a riddle card names composed items, not a head: the standard's head order is its cards less the riddles
    from thorp.train import RIDDLES  # a riddle card names composed items, not a head

    expected = [c for c in std["cards"] if c not in RIDDLES][: len(cards)]
    # the standard names a floor, not a ceiling: pinning more cards on top of its order is an extension,
    # pinning different ones is a departure (9 November, the 10-card arms)
    if cards[: len(expected)] != expected and not departed("scaffold"):
        out.append(f"pins {cards}, not SOP v{version}'s order {expected}")
    riddle = sc.get("riddles") or {}
    if "comparator" in std["cards"][: len(cards)] and "comparator" not in cards and not riddle:
        out.append("leaves the comparator unpinned although the size has room")
    arm = (std.get("chart") or {}).get("arm") or {}
    if arm.get("pins"):
        want = list(arm["pins"])
        got = [c for c in cards if c in want]
        if sorted(got) != sorted(want):
            out.append(f"pins {got} as the chart's arm; v{version} pins exactly {want}")
        if arm.get("riddle") and arm["riddle"] not in cards and arm["riddle"] not in (riddle or {}):
            out.append(f"pins no {arm['riddle']} riddle; the chart's arm has one")
    pin = ((std.get("pinning") or {}).get("sizes") or {}).get(str(size)) or {}
    at = {h.get("card"): h.get("layer") for h in sc.get("heads") or []}
    for card, layer in pin.items():
        if card in at and at[card] != layer and not departed("scaffold"):
            out.append(f"{card} is pinned at L{at[card]}; the depth standard puts it at L{layer}")
    return out


def resolve(spec: dict) -> dict | None:
    """The standard's scaffold phase for this spec's size — for a voyage that names the SOP and omits its own (the
    trainer still reads `optim.scaffold`, so this is the bridge for a later version of the runner)."""
    version = spec.get("sop")
    if not version:
        return None
    std = standard(str(version))
    if std is None:
        return None
    phase = next((p for p in std.get("phases") or [] if p.get("kind") == "scaffold"), None)
    if phase is None:
        return None
    return {
        "weight": phase.get("weight", 1.0),
        "hold": phase.get("hold", 0.0),
        "fade": phase.get("fade"),
        "floor": phase.get("floor", 0.0),
    }


# ---------------------------------------------------------------- control tokens (9 November)

CONTROL_CLASSES: tuple[dict, ...] = (
    {"key": "boundary", "name": "Boundary", "is_special": True, "ordinal": 0,
     "about": "the model's own sequence specials: the start and end of a text, padding, and the unknown piece. "
              "They are SentencePiece's specials, not user-defined pieces; selecting the class controls their use, not the vocabulary."},
    {"key": "separator", "name": "Separator", "is_special": False, "ordinal": 1,
     "about": "delimiters between documents, fields or examples."},
    {"key": "argument", "name": "Argument", "is_special": False, "ordinal": 2,
     "about": "the premise and the conclusion of a logical argument."},
    {"key": "dialogue", "name": "Dialogue", "is_special": False, "ordinal": 3,
     "about": "the question and the answer of a turn."},
)

CONTROL_TOKENS: tuple[dict, ...] = (
    {"key": "bos", "symbol": "<s>", "class_key": "boundary", "ordinal": 0,
     "about": "the start of a text (SentencePiece BOS)."},
    {"key": "eos", "symbol": "</s>", "class_key": "boundary", "ordinal": 1,
     "about": "the end of a text (SentencePiece EOS)."},
    {"key": "pad", "symbol": "<pad>", "class_key": "boundary", "ordinal": 2,
     "about": "padding (SentencePiece PAD)."},
    {"key": "unk", "symbol": "<unk>", "class_key": "boundary", "ordinal": 3,
     "about": "the unknown piece (SentencePiece UNK)."},
    {"key": "sep", "symbol": "<|sep|>", "class_key": "separator", "ordinal": 4,
     "about": "the boundary between documents or fields."},
    {"key": "end", "symbol": "<|end|>", "class_key": "separator", "ordinal": 5,
     "about": "the end of a record or example."},
    {"key": "premise", "symbol": "<|premise|>", "class_key": "argument", "ordinal": 6,
     "about": "opens the premise of an argument."},
    {"key": "conclusion", "symbol": "<|conclusion|>", "class_key": "argument", "ordinal": 7,
     "about": "opens the conclusion of an argument."},
    {"key": "question", "symbol": "<|question|>", "class_key": "dialogue", "ordinal": 8,
     "about": "opens a question."},
    {"key": "answer", "symbol": "<|answer|>", "class_key": "dialogue", "ordinal": 9,
     "about": "opens an answer."},
)


def _control_catalog_db() -> dict:
    """The control-token taxonomy, seeded idempotently into `s5.control_token_classes` and `s5.control_tokens`
    and returned grouped by class for the ship builder. The models live in `thorp/viable/records.py`."""
    from sqlalchemy import select

    from thorp import store
    from thorp.viable.records import ControlToken, ControlTokenClass

    ControlTokenClass.__table__.create(store.engine(), checkfirst=True)
    ControlToken.__table__.create(store.engine(), checkfirst=True)
    with store.session() as s:
        for c in CONTROL_CLASSES:
            row = s.get(ControlTokenClass, c["key"])
            if row is None:
                s.add(ControlTokenClass(**c))
            else:
                row.name, row.about, row.ordinal, row.is_special = c["name"], c["about"], c["ordinal"], c["is_special"]
        for t in CONTROL_TOKENS:
            row = s.get(ControlToken, t["key"])
            if row is None:
                s.add(ControlToken(**t))
            else:
                row.symbol, row.class_key, row.about, row.ordinal = t["symbol"], t["class_key"], t["about"], t["ordinal"]
        classes = s.scalars(select(ControlTokenClass).order_by(ControlTokenClass.ordinal)).all()
        tokens = s.scalars(select(ControlToken).order_by(ControlToken.ordinal)).all()
    by_class: dict[str, list[dict]] = {}
    for t in tokens:
        by_class.setdefault(t.class_key, []).append({"key": t.key, "symbol": t.symbol, "about": t.about})
    return {"classes": [
        {"key": c.key, "name": c.name, "about": c.about, "is_special": c.is_special, "tokens": by_class.get(c.key, [])}
        for c in classes
    ]}


_CONTROL_CACHE: dict | None = None
_CONTROL_LOCK = None


def control_catalog() -> dict:
    """The control-token taxonomy. The tables are created and seeded once, then served from memory: the
    catalog is code-defined and static, and creating/updating the tables on every shipbuilder request was
    taking seconds and locking them."""
    global _CONTROL_CACHE, _CONTROL_LOCK
    import threading

    if _CONTROL_CACHE is not None:
        return _CONTROL_CACHE
    if _CONTROL_LOCK is None:
        _CONTROL_LOCK = threading.Lock()
    with _CONTROL_LOCK:
        if _CONTROL_CACHE is None:
            _CONTROL_CACHE = _control_catalog_db()
        return _CONTROL_CACHE


def control_symbols(standard: dict, ship: str | None = None) -> list[str]:
    """The user-defined control symbols an expedition's standard declares for a ship.

    `embeddings.control = {classes: [...], ships: 'all' | [keys]}`. The boundary class is the model's own
    specials and contributes no user-defined piece; the other classes contribute their symbols in taxonomy
    order. A ship outside the selection gets none. The run builder uses this when it builds the tokeniser.
    """
    control = ((standard or {}).get("embeddings") or {}).get("control") or {}
    ships = control.get("ships", "all")
    if ship is not None and ships != "all" and ship not in (ships or []):
        return []
    wanted = set(control.get("classes") or [])
    return [t["symbol"] for t in CONTROL_TOKENS if t["class_key"] in wanted and t["class_key"] != "boundary"]

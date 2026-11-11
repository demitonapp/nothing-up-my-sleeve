"""The expedition as a launch, and the master charter it sails under (12 November 2026).

Justin: "expeditions are broken down into research, test voyages, rework, basically getting everything
ready and then launching a version across the fleet ... the knockout, the kipling, laying the keel and the
card census ... are all preparation for the expedition ... the first real fleet version launch of Nothing
up my sleeve is the best possible version taking into account all the goals of all the prep work."

So there is one expedition, Nothing up my sleeve v0.1, and what `fleet.EXPEDITIONS` calls expeditions are
its preparations. This module is that one expedition:

- **the fleet**: five classes, a base ship at each, an instruct ship from the 9m up (the 300k and the 1m
  are too small for one). An instruct ship is its base with the return leg sailed from it.
- **the master charter** (Justin, of the voyage card: "this is what the master charter is, so as we go
  through preparation we'll start signing off the parameters that are here for the fleet"): the voyage
  card's own parameters, one row each, read class by class from the draft standard's fitouts. A row is
  signed off when preparation has settled it. The signature is the store's (`s5.charter_signoffs`) and
  keeps the values as they were signed, so a draft reworked afterwards shows as drifted, not as signed.
- **every goal's part in the launch**: a goal decides a parameter, is a reading the fleet is judged on, is
  delivered by the fleet itself, or is carried to the next expedition. `PARTS` is a first cut, proposed and
  not yet signed off: the words are Justin's to change.

`payload(detail)` is the page's /api/launch. `detail` is the dashboard's reading of a spec (the function the
voyage card is drawn from), passed in so the charter and the card can never name a parameter differently.

    uv run python -m thorp.launch        # the charter and the fleet in plain text
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from thorp import fleet, paths

VERSION = "0.1"
NAME = "Nothing up my sleeve"
CLASSES = ("300k", "1m", "9m", "21m", "50m")
INSTRUCT = ("9m", "21m", "50m")  # the 300k and the 1m are too small for an instruct ship
TOO_SMALL = "too small for an instruct ship"
# a fitout whose name carries one of these is a return leg: the rehearsal of an instruct ship
LEG_MARKS = ("converse", "talk", "return")
NOT_A_LEG = ("rigged", "ifeval")  # the rigged IFEval pilot is a reading, not a ship to talk to
FT = "eval/hole-cards-unseen/bpb_mean_en"

# a preparation is research (outside models, nothing of ours trained) or test voyages (the default)
RESEARCH = ("knockout",)

PHASES = (
    ("research", "Research"),
    ("trials", "Test voyages"),
    ("rework", "Rework"),
    ("freeze", "Sign-off"),
    ("launch", "Launch"),
    ("home", "Home"),
)

# ---- every goal's part in the launch. PROPOSED (12 November): a first reading of the goals as they stood
# in the store, for Justin to correct. goal id -> (part, why).
DECIDES, ACCEPTANCE, DELIVERED, CARRIED = "decides", "acceptance", "delivered", "carried"
PART_WORDS = {
    DECIDES: "decides a parameter of the charter",
    ACCEPTANCE: "a reading the fleet is judged on",
    DELIVERED: "delivered by the fleet itself",
    CARRIED: "carried to the next expedition",
}
PARTS: dict[str, tuple[str, str]] = {
    "ogden": (DECIDES, "the one corpus every class reads, and how many times"),
    "kipling:2": (DECIDES, "whether the fleet's pieces carry the control symbols"),
    "kipling:3": (DECIDES, "the return leg an instruct ship sails: its turns, its stages and its rate"),
    "kipling:4": (DECIDES, "how long a pin is held and when it is released, read from each head's leak and recovery"),
    "kipling:6": (DECIDES, "the key/value heads"),
    "card_census:1": (DECIDES, "which cards each class is given to hold"),
    "knockout:1": (DECIDES, "whether a card is pinned because chaining needs it"),
    "kipling:8": (DECIDES, "the hull's shape: how many layers, how wide, and the heads the width allows"),
    "kipling:9": (DECIDES, "the window every class reads through"),
    "kipling:10": (DECIDES, "how many pieces each class's tokeniser has"),
    "kipling:11": (DECIDES, "which kinds of knowledge the fleet's corpus holds, and in what shares"),
    "kipling:12": (DECIDES, "the Ogden branch with control tokens: what the tokeniser is trained on and what every class reads"),
    "seedling:1": (CARRIED, "built from nothing is signed (Justin, 12 November: 'Built: agreed'); whether a class grown from the one beneath gets there sooner is tested against this fleet, not before it"),
    "kipling:1": (ACCEPTANCE, "IFEval on prompts the ship was not taught: the rigged pilot beat the mark and cost the language"),
    "knockout:3": (ACCEPTANCE, "the 21m read against SmolLM2-360M"),
    "knockout:7": (ACCEPTANCE, "AI2 ARC, each class beside the outside readings"),
    "kipling:5": (DELIVERED, "the 21m instruct ship is the one to hold a conversation with"),
    "knockout:8": (DELIVERED, "class over class is the fleet's own reading: it cannot be read before the fleet is home"),
    "knockout:2": (CARRIED, "a reasoning budget needs a new tokeniser version; low priority (Justin, 11 November)"),
    "knockout:5": (CARRIED, "the arch is a programme of its own, each rung earning the next"),
    "knockout:6": (CARRIED, "rests on the reasoning budget, which is carried"),
    "knockout:9": (CARRIED, "a stage sailed from a finished 9m: it reads the fleet rather than shaping it"),
    "card_census:2": (DECIDES, "which riddles the fleet carries: the comparator is kept at one-third depth (Justin, 12 November); the bridge is decided by the riddle voyages"),
    "seedling:2": (CARRIED, "the apprentice's next steps follow the grown-from-keel answer"),
}


# ---- the master charter: the voyage card's parameters, one row each
@dataclass(frozen=True)
class Param:
    key: str
    name: str
    read: Callable[[dict], Any]  # from the dashboard's spec detail to the words the card shows
    goals: tuple[str, ...] = ()  # the goals that decide it; none: carried from the draft unquestioned
    leg: bool = False  # a parameter of the return leg: instruct ships only


def _n(v: Any) -> str | None:
    return None if v is None or v == "" else f"{int(v):,}" if isinstance(v, int | float) and float(v).is_integer() else str(v)


def _pct(v: Any) -> str | None:
    return None if v is None else f"{round(float(v) * 100)}%"


def _pins(d: dict) -> str | None:
    heads = (d.get("scaffold") or {}).get("heads") or []
    return ", ".join(f"{h.get('card')} L{h.get('layer')}" for h in heads) or "none"


def _riddles(d: dict) -> str | None:
    r = (d.get("scaffold") or {}).get("riddles") or {}
    return ", ".join(f"{k} L{v.get('layer')}" for k, v in r.items()) or "none"


def _stages(d: dict) -> str | None:
    st = (d.get("post") or {}).get("stages") or []
    return "; ".join(f"{s.get('name') or 'stage'}: {str(s.get('recipe') or '').split('/')[-1]} × {s.get('passes') or 1}" for s in st) or None


def _lr(d: dict) -> str | None:
    o = d.get("optim") or {}
    return None if o.get("lr") is None else str(o["lr"])


def _built(d: dict) -> str:
    seed = (d.get("post") or {}).get("seed") or {}
    return f"grown from {seed.get('run')}" if seed.get("run") else "from nothing"


def _m(k: str) -> Callable[[dict], Any]:
    return lambda d: (d.get("model") or {}).get(k)


def _o(k: str) -> Callable[[dict], Any]:
    return lambda d: (d.get("optim") or {}).get(k)


def _s(k: str) -> Callable[[dict], Any]:
    return lambda d: (d.get("scaffold") or {}).get(k)


GROUPS: tuple[tuple[str, str, tuple[Param, ...]], ...] = (
    ("ship", "The ship", (
        # layers, width and the heads that follow from the width are one decision: the clean pair at the 1m
        # (kipling:8; Justin, 12 November: "I agree with running a clean pair ... make that line wait on those voyages")
        Param("ship.layers", "layers", lambda d: _n(_m("layers")(d)), ("kipling:8",)),
        Param("ship.heads", "query heads", lambda d: _n(_m("heads")(d)), ("kipling:8",)),
        Param("ship.kv_heads", "KV heads", lambda d: _n(_m("kv_heads")(d)) if _m("kv_heads")(d) else "one per query head", ("kipling:6",)),
        Param("ship.width", "width", lambda d: _n(_m("width")(d)), ("kipling:8",)),
        Param("ship.context", "context", lambda d: f"{int(_m('context')(d)):,} pieces" if _m("context")(d) else None, ("kipling:9",)),
        Param("ship.positions", "positions", _m("positions")),
        Param("ship.built", "built", _built),
    )),
    ("tokeniser", "The tokeniser", (
        Param("tokeniser.pieces", "pieces", lambda d: f"{(d.get('tokeniser') or {}).get('kind') or '–'} · {int((d.get('tokeniser') or {}).get('vocab') or 0):,} pieces", ("kipling:10",)),
        Param("tokeniser.byte_fallback", "byte fallback", lambda d: "yes" if (d.get("tokeniser") or {}).get("byte_fallback") else "no"),
        Param("tokeniser.train_on", "trained on", lambda d: (d.get("tokeniser") or {}).get("train_on"), ("kipling:11", "kipling:12")),
        Param("tokeniser.symbols", "control symbols", lambda d: " ".join((d.get("tokeniser") or {}).get("symbols") or []) or "none declared", ("kipling:2", "kipling:12")),
    )),
    ("reads", "What it reads", (
        Param("reads.recipe", "recipe", lambda d: (d.get("data") or {}).get("recipe"), ("ogden", "kipling:11", "kipling:12")),
        Param("reads.passes", "passes", lambda d: _n((d.get("data") or {}).get("passes")), ("ogden",)),
        Param("reads.clean", "clean", lambda d: (d.get("data") or {}).get("clean") or "raw"),
        Param("reads.order", "order", lambda d: (d.get("data") or {}).get("order")),
        Param("reads.refuse", "refuses", lambda d: ", ".join(str(x).split("/")[-1] for x in (d.get("data") or {}).get("refuse") or []) or "nothing"),
    )),
    ("scaffold", "The scaffold", (
        Param("scaffold.pins", "pins", _pins, ("card_census:1", "knockout:1")),
        Param("scaffold.riddles", "riddles", _riddles, ("card_census:1", "card_census:2")),
        Param("scaffold.weight", "weight", lambda d: _n(_s("weight")(d))),
        Param("scaffold.hold", "hold", lambda d: _pct(_s("hold")(d)), ("kipling:4",)),
        Param("scaffold.fade", "fade", lambda d: _pct(_s("fade")(d)), ("kipling:4",)),
        Param("scaffold.release", "release", lambda d: _pct(_s("release")(d)) or "none", ("kipling:4",)),
    )),
    ("training", "The training", (
        Param("training.optimiser", "optimiser", _o("name")),
        Param("training.lr", "learning rate", _lr),
        Param("training.warmup", "warm-up", lambda d: f"{int(_o('warmup_steps')(d)):,} steps" if _o("warmup_steps")(d) is not None else None),
        Param("training.batch", "batch", lambda d: f"{int(_o('batch_tokens')(d)):,} tokens" if _o("batch_tokens")(d) else None),
        Param("training.schedule", "schedule", lambda d: (f"{_o('schedule')(d)} · min {_pct(_o('min_lr_ratio')(d))}" if _o("min_lr_ratio")(d) is not None else _o("schedule")(d))),
        Param("training.grad_clip", "grad clip", lambda d: _n(_o("grad_clip")(d))),
        Param("training.precision", "precision", _o("precision")),
    )),
    ("leg", "The return leg (instruct ships)", (
        Param("leg.inherits", "inherits", lambda d: ((d.get("post") or {}).get("seed") or {}).get("mode"), ("kipling:3",), True),
        Param("leg.turns", "turns", lambda d: ((d.get("post") or {}).get("turns") or {}).get("format"), ("kipling:3",), True),
        Param("leg.stages", "stages", _stages, ("kipling:3",), True),
        Param("leg.lr", "learning rate", lambda d: _n((d.get("post") or {}).get("lr")), ("kipling:3",), True),
        Param("leg.pull", "the pull", lambda d: None if not (d.get("post") or {}).get("pull") else "off" if (d.get("post") or {})["pull"].get("off") else f"on at {(d.get('post') or {})['pull'].get('weight')}", ("kipling:3",), True),
    )),
)
PARAMS: dict[str, Param] = {p.key: p for _, _, ps in GROUPS for p in ps}
SHORT = {"ship": "the ship", "tokeniser": "the tokeniser", "reads": "what it reads", "scaffold": "the scaffold",
         "training": "the training", "leg": "the return leg"}  # fmt: skip


# ---- which fitout is which ship
_NAME = re.compile(r"^(?P<size>\d+[km])@v(?P<ver>\d+\.\d+(?:\.\d+)?)(?P<rest>(?:-.+)?)$")


def _ver(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def variant_of(name: str) -> tuple[str, str, str] | None:
    """A fitout's (class, version, variant) by its name: `base` for the plain ship and its other seeds,
    `instruct` for a return leg, `arm` for anything else (a preparation's variation, not a fleet ship)."""
    m = _NAME.match(name or "")
    if not m or m["size"] not in CLASSES:
        return None
    rest = m["rest"]
    if rest in ("", "-instruct") or re.fullmatch(r"-s\d+", rest):
        return m["size"], m["ver"], "instruct" if rest == "-instruct" else "base"
    if any(k in rest for k in LEG_MARKS) and not any(k in rest for k in NOT_A_LEG):
        return m["size"], m["ver"], "instruct"
    return m["size"], m["ver"], "arm"


def ship_name(size: str, variant: str) -> str:
    return f"{size}@v{VERSION}" + ("-instruct" if variant == "instruct" else "")


def state_of(name: str, run: dict | None, seats: set[str], queued: set[str], laid: bool) -> str:
    """A ship's state in the fleet's words: at sea, home, queued, laid (a spec, never sailed), not laid, or
    the ledger's own word for a voyage that did not come home (stopped, failed, killed)."""
    st = str((run or {}).get("status") or "")
    if st == "running" and name in seats and name not in queued:
        return "at sea"
    if st == "finished":
        return "home"
    if name in queued:
        return "queued"
    if not run:
        return "laid" if laid else "not laid"
    return "stopped" if st == "running" else st.split(":")[0]


def param_state(signed: dict | None, values: dict, goals: list[dict]) -> str:
    """signed: signed off and the draft still says what was signed. drifted: signed, and the draft has been
    reworked since. waiting: a goal that decides it is still open. ready: nothing left to wait for."""
    if signed is not None:
        return "signed" if (signed.get("values") or {}) == values else "drifted"
    # anything short of a verdict is unsettled: open, partly, or a goal the store does not hold at all (a
    # process running older code can drop a new goal's row, 12 November), which must never read as ready
    if any(g.get("status") not in ("done", "dropped") for g in goals):
        return "waiting"
    return "ready"


# ---- the sign-offs (the store's: the charter's only record that is not read from a spec)
_DDL = (
    "create table if not exists s5.charter_signoffs ("
    "charter text not null, "
    "param text not null, "
    "value jsonb not null default '{}'::jsonb, "
    "signed_by text not null default '', "
    "note text not null default '', "
    "signed_at timestamptz not null default now(), "
    "primary key (charter, param))"
)


def ensure() -> None:
    from sqlalchemy import text

    from thorp import store

    with store.session() as s:
        s.execute(text(_DDL))


def signoffs() -> dict[str, dict]:
    """Every signed parameter of this charter: param -> {values, by, note, at}."""
    from sqlalchemy import text

    from thorp import store

    ensure()
    with store.session() as s:
        rows = s.execute(
            text("select param, value, signed_by, note, signed_at from s5.charter_signoffs where charter = :c"),
            {"c": VERSION},
        ).all()
    return {
        p: {"values": v if isinstance(v, dict) else json.loads(v or "{}"), "by": by, "note": note, "at": at.isoformat() if at else None}
        for p, v, by, note, at in rows
    }


def sign(param: str, values: dict, by: str = "Justin", note: str = "") -> None:
    """Sign a parameter off at the values the charter shows now (a second signing replaces the first)."""
    from sqlalchemy import text

    from thorp import store

    if param not in PARAMS:
        raise KeyError(f"the charter has no parameter called {param!r}")
    ensure()
    with store.session() as s:
        s.execute(
            text(
                "insert into s5.charter_signoffs (charter, param, value, signed_by, note, signed_at) "
                "values (:c, :p, cast(:v as jsonb), :by, :note, now()) "
                "on conflict (charter, param) do update set value = excluded.value, "
                "signed_by = excluded.signed_by, note = excluded.note, signed_at = now()"
            ),
            {"c": VERSION, "p": param, "v": json.dumps(values), "by": by, "note": note},
        )


def unsign(param: str) -> bool:
    from sqlalchemy import text

    from thorp import store

    ensure()
    with store.session() as s:
        r = s.execute(
            text("delete from s5.charter_signoffs where charter = :c and param = :p"), {"c": VERSION, "p": param}
        )
        return bool(r.rowcount)


# ---- what the store and the ledger say
def _goals() -> tuple[list[dict], bool]:
    """Every goal with its verdict, from the store; from the code's words alone when the store is down."""
    try:
        from thorp import expedition_goals

        return expedition_goals.read(), True
    except Exception:  # noqa: BLE001  no store: the words without the verdicts
        from thorp import expedition_goals

        out = []
        for key, e in fleet.EXPEDITIONS.items():
            for r in expedition_goals._rows_of(e):
                out.append({**r, "expedition_key": key, "name": e.name, "declared_status": e.status,
                            "status": r.get("status", "open"), "evidence": "", "words": ""})  # fmt: skip
        return out, False


def _draft() -> tuple[str, list[str]]:
    """The draft standard (the newest one an expedition sails under) and every version there has been."""
    from thorp import sop

    vs = sop.versions()
    named = [v for v in vs if (sop.standard(v) or {}).get("expedition")]
    return (max(named, key=_ver) if named else sop.CURRENT), vs


def _specs() -> dict[str, Any]:
    """Every fitout spec that is a class's ship or leg: name -> its path."""
    d = paths.resolve("specs/fitouts")
    return {p.stem: p for p in d.glob("*@v*.yaml") if variant_of(p.stem)} if d.exists() else {}


def _runs() -> dict[str, dict]:
    """The newest ledger row of every fitout voyage, by name."""
    from thorp.ledger import reader

    rows = reader().query(
        "select run_id, name, status, started from runs where name like ? order by started", ["%@v%"]
    )
    return {r["name"]: r for r in rows if variant_of(r["name"])}


def _ft(run_id: str) -> float | None:
    from thorp.ledger import reader

    r = reader().query(
        "select value from metrics where run_id=? and name=? order by step desc, rowid desc limit 1", [run_id, FT]
    )
    return r[0]["value"] if r else None


def _wall() -> dict[str, dict]:
    from thorp.ledger import reader

    rows = reader().query(
        "select json_extract(spec_json,'$.model.preset') p, count(*) n, avg(wall_minutes) m from runs "
        "where status='finished' and wall_minutes > 1 group by p"
    )
    return {r["p"]: {"voyages": r["n"], "mean_minutes": r["m"]} for r in rows if r["p"]}


def charter_specs(specs: dict[str, Any], draft: str) -> dict[str, dict[str, str | None]]:
    """The fitout each class's column is read from: the plain ship at the draft standard (an earlier one
    where the class has none yet), and the newest return leg written for the class."""
    out: dict[str, dict[str, str | None]] = {}
    for size in CLASSES:
        plain = [n for n in specs if (v := variant_of(n)) and v[0] == size and v[2] == "base" and _NAME.match(n)["rest"] == ""]
        at = [n for n in plain if _ver(variant_of(n)[1]) <= _ver(draft)]
        base = max(at or plain, key=lambda n: _ver(variant_of(n)[1]), default=None)
        legs = [n for n in specs if (v := variant_of(n)) and v[0] == size and v[2] == "instruct"]
        newest = max((_ver(variant_of(n)[1]) for n in legs), default=None)
        leg = max((n for n in legs if _ver(variant_of(n)[1]) == newest), key=lambda n: specs[n].stat().st_mtime, default=None)
        out[size] = {"base": base, "leg": leg if size in INSTRUCT else None}
    return out


def charter_values(details: dict[str, dict[str, dict | None]]) -> dict[str, dict[str, str | None]]:
    """Every parameter's value at every class: param -> {class: words}. `details` is each class's spec
    detail, {"base": ..., "leg": ...}; a class with no spec for a column reads None."""
    out: dict[str, dict[str, str | None]] = {}
    for p in PARAMS.values():
        row: dict[str, str | None] = {}
        for size in CLASSES:
            d = (details.get(size) or {}).get("leg" if p.leg else "base")
            try:
                v = p.read(d) if d else None
            except (TypeError, ValueError, KeyError):
                v = None
            row[size] = None if v is None or v == "" else str(v)
        out[p.key] = row
    return out


def _load(path: Any) -> dict:
    import yaml

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:  # noqa: BLE001  an unreadable spec is a class with no column, not a page that fails
        return {}


def current_values(detail: Callable[[dict], dict]) -> dict[str, dict[str, str | None]]:
    """The charter as the draft's fitouts say it now: what a signature freezes."""
    specs = _specs()
    draft, _ = _draft()
    cols = charter_specs(specs, draft)
    details = {
        size: {k: (detail(_load(specs[n])) if n else None) for k, n in c.items()} for size, c in cols.items()
    }
    return charter_values(details)


def payload(detail: Callable[[dict], dict]) -> dict:
    """The one expedition: its phases, its fleet, its charter and every goal's part in it."""
    from thorp import expeditions as voyages
    from thorp import sop

    specs = _specs()
    draft, versions = _draft()
    frozen = VERSION in versions and bool(sop.standard(VERSION))
    runs = _runs()
    seats, queued = voyages._status_ctx()
    wall = _wall()
    goals, store_up = _goals()
    by_id = {g["goal_id"]: g for g in goals}
    try:
        signed = signoffs()
    except Exception:  # noqa: BLE001  no store: the charter reads unsigned, and says so
        signed, store_up = {}, False

    # ---- the charter
    cols = charter_specs(specs, draft)
    details = {size: {k: (detail(_load(specs[n])) if n else None) for k, n in c.items()} for size, c in cols.items()}
    values = charter_values(details)

    def goal_ref(gid: str) -> dict:
        g = by_id.get(gid) or {}
        return {"goal_id": gid, "text": g.get("text") or gid, "status": g.get("status") or "unknown",
                "expedition": g.get("expedition_key"), "words": g.get("words") or "", "evidence": g.get("evidence") or ""}  # fmt: skip

    groups, tally = [], {"signed": 0, "drifted": 0, "ready": 0, "waiting": 0}
    for key, name, ps in GROUPS:
        rows = []
        for p in ps:
            refs = [goal_ref(g) for g in p.goals]
            st = param_state(signed.get(p.key), values[p.key], refs)
            tally[st] += 1
            rows.append({"key": p.key, "name": p.name, "leg": p.leg, "values": values[p.key], "goals": refs,
                         "state": st, "signed": signed.get(p.key)})  # fmt: skip
        groups.append({"key": key, "name": name, "params": rows})

    # ---- the fleet
    def cell(size: str, variant: str) -> dict:
        if variant == "instruct" and size not in INSTRUCT:
            return {"ship": None, "state": "too small", "why": TOO_SMALL, "rehearsals": []}
        name = ship_name(size, variant)
        names = set(specs) | set(runs) | {q for q in queued if variant_of(q)}
        reh = []
        for n in names:
            v = variant_of(n)
            if not v or v[0] != size or v[2] != variant or v[1] == VERSION:
                continue
            r = runs.get(n)
            st = state_of(n, r, seats, queued, n in specs)
            reh.append({"name": n, "sop": v[1], "state": st, "started": (r or {}).get("started"),
                        "ft": _ft(r["run_id"]) if r and st == "home" else None})  # fmt: skip
        # the draft's own rehearsals first (a later side standard is not one), what is queued or at sea
        # before what is home, then the newest
        reh.sort(key=lambda x: (_ver(x["sop"]) <= _ver(draft), _ver(x["sop"]), x["state"] in ("at sea", "queued"),
                                x["started"] or ""), reverse=True)  # fmt: skip
        return {"ship": name, "state": state_of(name, runs.get(name), seats, queued, name in specs),
                "spec": name in specs, "rehearsals": reh[:3], "rehearsal_count": len(reh)}  # fmt: skip

    ships = [
        {"class": size, **(wall.get(size) or {"voyages": 0, "mean_minutes": None}),
         "base": cell(size, "base"), "instruct": cell(size, "instruct")}  # fmt: skip
        for size in CLASSES
    ]
    cells = [s[v] for s in ships for v in ("base", "instruct") if s[v]["ship"]]
    home = sum(1 for c in cells if c["state"] == "home")

    # ---- every goal's part
    open_keys = {k for k, e in fleet.EXPEDITIONS.items() if e.status != "done"}
    decides_of: dict[str, list[str]] = {}
    for p in PARAMS.values():
        for g in p.goals:
            decides_of.setdefault(g, []).append(p.key)
    parts = []
    for g in goals:
        gid = g["goal_id"]
        part = PARTS.get(gid)
        if not part and (g["expedition_key"] not in open_keys or g["status"] == "dropped"):
            continue  # a settled preparation's record, or a goal folded into another: no part of its own
        parts.append({
            "goal_id": gid, "expedition": g["expedition_key"], "expedition_name": g.get("name"),
            "text": g["text"], "status": g["status"], "evidence": g.get("evidence") or "", "words": g.get("words") or "",
            "part": part[0] if part else "unassigned", "why": part[1] if part else "",
            "params": decides_of.get(gid, []),
        })  # fmt: skip
    blocking = [x for x in parts if x["part"] == DECIDES and x["status"] in ("open", "partly")]

    # ---- the preparations: what each decides and how much of it still stands in the launch's way
    preps: dict[str, dict] = {}
    for k in fleet.EXPEDITIONS:
        mine = [x for x in parts if x["expedition"] == k]
        if not mine:
            continue
        keys = sorted({p for x in mine if x["part"] == DECIDES for p in x["params"]}, key=list(PARAMS).index)
        preps[k] = {
            "kind": "research" if k in RESEARCH else "test voyages",
            "decides": [f"{SHORT[p.split('.')[0]]}: {PARAMS[p].name}" for p in keys],
            "blocking": sum(1 for x in mine if x in blocking),
            "parts": {w: sum(1 for x in mine if x["part"] == w) for w in (DECIDES, ACCEPTANCE, DELIVERED, CARRIED, "unassigned")},
        }

    # ---- the phases
    def open_in(kind: str) -> int:
        return sum(1 for x in blocking if (preps.get(x["expedition"]) or {}).get("kind") == kind)

    total = len(PARAMS)
    all_signed = tally["signed"] == total
    prep_done = not blocking
    state = {
        "research": "active" if open_in("research") else "done",
        "trials": "active" if open_in("test voyages") else "done",
        "rework": "done" if frozen else "active",
        "freeze": "done" if frozen else "active" if (tally["signed"] or tally["drifted"] or prep_done) else "ahead",
        "launch": "ahead" if not frozen else "done" if home == len(cells) else "active",
        "home": "done" if frozen and home == len(cells) else "ahead",
    }
    notes = {
        "research": f"{open_in('research')} deciding goal{'' if open_in('research') == 1 else 's'} open",
        "trials": f"{open_in('test voyages')} deciding goal{'' if open_in('test voyages') == 1 else 's'} open",
        "rework": f"the draft is SOP v{draft}",
        "freeze": f"{tally['signed']} of {total} parameters signed",
        "launch": f"{home} of {len(cells)} ships home",
        "home": "the readings, and the next expedition's preparation",
    }
    return {
        "version": VERSION, "name": NAME, "frozen": frozen, "draft": draft, "store": store_up,
        "phases": [{"key": k, "name": n, "state": state[k], "note": notes[k]} for k, n in PHASES],
        "readiness": {"params": total, **tally, "all_signed": all_signed, "blocking": len(blocking),
                      "ships": len(cells), "home": home},  # fmt: skip
        "fleet": ships,
        "charter": {"columns": [{"class": s, **cols[s]} for s in CLASSES], "groups": groups},
        "parts": parts, "part_words": PART_WORDS, "parts_proposed": True,
        "preparations": preps,
    }  # fmt: skip


def main() -> None:
    from thorp.dash.server import _spec_detail

    d = payload(_spec_detail)
    r = d["readiness"]
    print(f"{d['name']} v{d['version']}: draft SOP v{d['draft']}, {r['signed']} of {r['params']} parameters signed, "
          f"{r['blocking']} deciding goals open, {r['home']} of {r['ships']} ships home")  # fmt: skip
    for s in d["fleet"]:
        print(f"  {s['class']:5} base {s['base']['state']:9} instruct {s['instruct']['state']}")
    for g in d["charter"]["groups"]:
        print(g["name"])
        for p in g["params"]:
            vals = " | ".join(p["values"][c] or "–" for c in CLASSES)
            print(f"  [{p['state']:7}] {p['name']:16} {vals}")


if __name__ == "__main__":
    main()

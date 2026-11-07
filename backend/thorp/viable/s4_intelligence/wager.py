"""The Navigator's Wager (S4 intelligence; Justin, 2026-11-07 21:25: "wouldn't the game be predicting where the
cards fall based on pulling a specific lever?"). A round is one lever pulled: two voyages that differ by one
lever (the control and the pull). For each of the deck's 16 cards (s5_policy/deck.py) the Navigator calls how
the pull moves it against where it fell in the control; the House calls that nothing moves (the null). The
readings reveal it. What a round reveals is the lever's effect on the deck: the lesson.

- **Where a card falls** in a voyage: the first reading at which it is played (its look past its mark, a
  Stage 1 above a played Basic in an earlier layer, a Face with its cards below it in order and its ability
  past its mark), in tokens read, and the layer it is in then; or never.
- **Moves**: appears (never in the control, played in the pull), vanishes (the reverse), earlier / later
  (played in both, sooner or later by more than a quarter of the control's tokens), same.
- **Chips**: five a round (one hand). **Points**: the right move +3, and the right layer +2 more; a wrong
  call -2. Ties go to the House. A bet placed after the pull has sailed is practice: shown, not scored.
"""

from __future__ import annotations

import json
import re
import sqlite3
from functools import lru_cache

from thorp import paths
from thorp.viable.s5_policy import deck

MOVES = ("appears", "vanishes", "earlier", "later", "same")
CHIPS = 5
SHIFT = 0.25  # earlier / later: by more than this share of the control's tokens


def _con():
    con = sqlite3.connect(f"file:{paths.ledger_path()}?mode=ro", uri=True, timeout=30)
    con.row_factory = sqlite3.Row
    return con


def _voyage(name: str) -> dict | None:
    """The latest sailing of a voyage by name (finished, at sea, recalled ...)."""
    with _con() as c:
        r = c.execute(
            "select run_id, name, status, started, spec_json from runs where name=? order by started desc limit 1",
            [name],
        ).fetchone()
    return dict(r) if r else None


def _series(run_id: str, names: set[str]) -> dict[str, list[tuple[int, float]]]:
    marks = ",".join("?" * len(names))
    with _con() as c:
        rows = c.execute(
            f"select name, step, value from metrics where run_id=? and name in ({marks}) order by step",
            [run_id, *names],
        ).fetchall()
    out: dict[str, list[tuple[int, float]]] = {}
    for r in rows:
        if r["value"] is not None:
            out.setdefault(r["name"], []).append((r["step"], r["value"]))
    return out


def _needed() -> set[str]:
    out = set()
    for c in deck.CARDS:
        if c.look:
            out.update(c.look[0])
        if c.layer:
            out.add(c.layer)
        if c.ability:
            out.add(c.ability[0])
    return out


def falls(run_id: str, batch_tokens: int) -> dict[str, dict]:
    """Where each card falls in a voyage: {card: {played, step, tokens, layer}} (played False: never so far)."""
    s = _series(run_id, _needed())
    steps = sorted({st for name in s for st, _ in s[name]})

    def at(name: str, step: int):
        best = None
        for st, v in s.get(name, []):
            if st > step:
                break
            best = v
        return best

    def look_ok(card, step):
        if not card.look:
            return True
        names, mark = card.look
        vals = [v for v in (at(n, step) for n in names) if v is not None]
        return bool(vals) and max(vals) >= mark

    def layer(card, step):
        v = at(card.layer, step) if card.layer else None
        return None if v is None else int(v)

    out: dict[str, dict] = {}
    for card in deck.CARDS:
        out[card.key] = {"played": False, "step": None, "tokens": None, "layer": None, "charted": deck.charted(card)}
    if not steps:
        return out
    # cards in deck order: a card's Basics come before it in its constellation
    for card in deck.CARDS:
        if not deck.charted(card):
            continue
        for step in steps:
            if not look_ok(card, step):
                continue
            if card.ability:
                v = at(card.ability[0], step)
                if v is None or v < card.ability[1]:
                    continue
            ok = True
            mine = layer(card, step)
            for below in card.on:
                b = out[below]
                if not deck.charted(deck.BY_KEY[below]):
                    continue  # an uncharted Basic cannot be checked: the card stands on its own reading
                if not b["played"] or b["step"] > step:
                    ok = False
                    break
                bl = layer(deck.BY_KEY[below], step)
                if card.stage == "Stage 1" and mine is not None and bl is not None and bl >= mine:
                    ok = False  # a Stage 1 sits above its Basic, in a later layer
                    break
            if ok:
                out[card.key] = {
                    "played": True, "step": step, "tokens": step * batch_tokens, "layer": mine, "charted": True,
                }  # fmt: skip
                break
    return out


def move(control: dict, pull: dict) -> str:
    if not control["played"] and not pull["played"]:
        return "same"
    if not control["played"]:
        return "appears"
    if not pull["played"]:
        return "vanishes"
    c, p = control["tokens"], pull["tokens"]
    if p < c * (1 - SHIFT):
        return "earlier"
    if p > c * (1 + SHIFT):
        return "later"
    return "same"


def _spec_of(row: dict) -> dict:
    try:
        return json.loads(row["spec_json"] or "{}")
    except ValueError:
        return {}


def _class_of(preset: str) -> str:
    return preset.split("-")[0]


@lru_cache(maxsize=1)
def _ogden_specs() -> dict[str, dict]:
    import yaml

    out = {}
    for p in sorted(paths.resolve("specs/fitouts").glob("fu-ogden-v0-1*.yaml")):
        s = yaml.safe_load(p.read_text()) or {}
        out[s["name"]] = s
    return out


def rounds_for(preset: str) -> list[dict]:
    """The lever pulls a class can be wagered on: Ogden v0.1's pairs that differ by one lever."""
    _ogden_specs.cache_clear()
    specs = _ogden_specs()
    cls = _class_of(preset)
    out = []

    def add(key, lever, about, control, pull):
        if control in specs and pull in specs:
            out.append({"key": pull, "lever": lever, "about": about, "control": control, "pull": pull,
                        "source": "Ogden v0.1"})

    deeper = _variant(cls, "layers")
    for seed in (1, 2):
        base = f"fu-ogden-v0-1@{cls}-pre-s{seed}"
        if deeper:
            tag = "l" + deeper.split("-l")[-1]
            add(f"depth-s{seed}", "Depth", f"more layers ({cls} to {deeper})", base, f"fu-ogden-v0-1~{tag}@{deeper}-pre-s{seed}")
            add(f"tack-s{seed}", "The copy tack", f"the induction tack on the deeper {cls} (alpha 3)",
                f"fu-ogden-v0-1~{tag}@{deeper}-pre-s{seed}", f"fu-ogden-v0-1~{tag}-copy@{deeper}-pre-s{seed}")
    add("seed", "Seed", "the second seed of the same voyage (the noise: should move nothing)",
        f"fu-ogden-v0-1@{cls}-pre-s1", f"fu-ogden-v0-1@{cls}-pre-s2")
    prv = _prev_class(cls)
    if prv:
        add(f"class-from-{prv}", "Class", f"the next class up on the same corpus ({prv} to {cls})",
            f"fu-ogden-v0-1@{prv}-pre-s1", f"fu-ogden-v0-1@{cls}-pre-s1")
    nxt = _next_class(cls)
    if nxt:
        add(f"class-{nxt}", "Class", f"the next class up on the same corpus ({cls} to {nxt})",
            f"fu-ogden-v0-1@{cls}-pre-s1", f"fu-ogden-v0-1@{nxt}-pre-s1")
    return out


def _sailing(name: str) -> dict:
    v = _voyage(name)
    if not v:
        return {"name": name, "status": "queued", "falls": None}
    spec = _spec_of(v)
    bt = (spec.get("optim") or {}).get("batch_tokens") or 32768
    status = v["status"] if v["status"] in ("finished", "running") else v["status"].split(":")[0]
    return {"name": name, "status": "at sea" if status == "running" else status, "run_id": v["run_id"],
            "started": v["started"], "falls": falls(v["run_id"], bt)}  # fmt: skip


def house_bets(control: dict) -> dict[str, dict]:
    """The House calls the null: the pull moves nothing. Its five chips go on 'same' for the charted cards the
    control played (the surest of 'same'), then on the charted cards it never played."""
    f = control.get("falls") or {}
    played = [k for k in f if f[k]["played"]]
    never = [k for k in f if f[k]["charted"] and not f[k]["played"]]
    picks = (played + never)[:CHIPS]
    return {k: {"move": "same", "layer": f[k]["layer"] if f[k]["played"] else None} for k in picks}


def points(bet: dict, outcome: str, pull_fall: dict) -> int:
    if bet["move"] != outcome:
        return -2
    p = 3
    if bet.get("layer") is not None and pull_fall.get("played") and pull_fall.get("layer") == bet["layer"]:
        p += 2
    return p


def _in_queue(name: str) -> bool:
    q = paths.resolve("specs/queue.txt")
    return q.exists() and f"fitouts/{name}" in {ln.strip() for ln in q.read_text().splitlines()}


def payload(preset: str, bets_for=None) -> dict:
    """The Bet tab: the deck, and each round with both voyages' falls, the House's calls, the Navigator's bets
    (bets_for(round_key) -> {card: {move, layer, placed_at, practice}}), outcomes and the score."""
    rounds = []
    seen: set[str] = set()
    every = []
    for r in [*dealt_rounds(preset), *rounds_for(preset)]:
        if r["key"] not in seen:
            seen.add(r["key"])
            every.append(r)
    bets_for = bets_for or bets
    for r in every:
        control, pull = _sailing(r["control"]), _sailing(r["pull"])
        settled = control["status"] == "finished" and pull["status"] == "finished"
        house = house_bets(control) if control.get("falls") else {}
        mine = bets_for(r["key"]) if bets_for else {}
        claude = bets(r["key"], "Claude")
        cards, you, them, cl = [], 0, 0, 0
        for card in deck.CARDS:
            cf = (control.get("falls") or {}).get(card.key)
            pf = (pull.get("falls") or {}).get(card.key)
            outcome = move(cf, pf) if settled and cf and pf and cf["charted"] else None
            hb, nb = house.get(card.key), mine.get(card.key)
            hp = points(hb, outcome, pf) if outcome and hb else None
            np_ = points(nb, outcome, pf) if outcome and nb and not nb.get("practice") else None
            cb = claude.get(card.key)
            cp = points(cb, outcome, pf) if outcome and cb and not cb.get("practice") else None
            them += hp or 0
            you += np_ or 0
            cl += cp or 0
            cards.append({"card": card.key, "control": cf, "pull": pf, "outcome": outcome,
                          "house": hb, "house_points": hp, "bet": nb, "points": np_,
                          "claude": cb, "claude_points": cp})  # fmt: skip
        rounds.append({
            **r, "control_voyage": {k: v for k, v in control.items() if k != "falls"},
            "pull_voyage": {k: v for k, v in pull.items() if k != "falls"},
            "settled": settled, "cards": cards, "score": {"navigator": you, "house": them, "claude": cl},
            "winner": (None if not settled else "navigator" if you > them else "house"),
            "open": pull["status"] == "queued",
            "in_queue": _in_queue(r["pull"]),
        })  # fmt: skip
    return {
        "preset": preset,
        "constellations": [{"key": k, "suit": s, "name": n, "about": a} for k, s, n, a in deck.CONSTELLATIONS],
        "deck": [
            {
                "key": c.key, "name": c.name, "constellation": c.constellation, "stage": c.stage, "cost": c.cost,
                "look": ({"metrics": list(c.look[0]), "mark": c.look[1]} if c.look else None),
                "ability": c.ability_text, "ability_reading": ({"metric": c.ability[0], "mark": c.ability[1]} if c.ability else None),
                "fragility": c.fragility, "on": list(c.on), "charted": deck.charted(c),
            }
            for c in deck.CARDS
        ],  # fmt: skip
        "moves": list(MOVES),
        "chips": CHIPS,
        "levers": [{"key": k, "name": v[0], "about": v[1]} for k, v in LEVERS.items()],
        "controls": controls_for(preset),
        "rounds": rounds,
    }



# ---- the levers the Navigator can pull (Justin, 21:30: "I should be able to choose the lever, bet and then queue
# an experiment"). Each turns a control voyage of Ogden v0.1 into its pull: the same corpus, cleaning and shared
# tokeniser, one thing changed. A lever that would change the tokeniser (the vocabulary) is not offered: it
# would break the comparison every card is read against.


def _variant(preset: str, field: str) -> str | None:
    """The registry's next preset of the same class with more layers (field "layers") or heads ("heads")."""
    from thorp.models.registry import PRESETS

    base = PRESETS.get(preset)
    if base is None:
        return None
    letter = {"layers": "l", "heads": "h"}[field]
    options = [
        (cfg[field], name)
        for name, cfg in PRESETS.items()
        if name.startswith(_class_of(preset) + "-" + letter) and cfg[field] > base[field]
        and all(cfg[k] == base[k] for k in ("layers", "heads", "width") if k != field)
    ]
    return min(options)[1] if options else None


def _prev_class(preset: str) -> str | None:
    from thorp.models.registry import LADDER

    order = [r["preset"] for r in LADDER]
    c = _class_of(preset)
    return order[order.index(c) - 1] if c in order and order.index(c) > 0 else None


def _next_class(preset: str) -> str | None:
    from thorp.models.registry import LADDER

    order = [r["preset"] for r in LADDER]
    c = _class_of(preset)
    return order[order.index(c) + 1] if c in order and order.index(c) + 1 < len(order) else None


def _bump_preset(field: str):
    def apply(spec):
        nxt = _variant(spec["model"]["preset"], field)
        if nxt is None:
            return None
        spec["model"]["preset"] = nxt
        return spec

    return apply


def _tack(spec):
    if (spec.get("optim") or {}).get("copy_weight"):
        return None
    spec["optim"]["copy_weight"] = {"alpha": 3, "kind": "induction"}
    return spec


def _lr(factor):
    def apply(spec):
        spec["optim"]["lr"] = round(spec["optim"]["lr"] * factor, 6)
        return spec

    return apply


def _positions(spec):
    if spec["model"].get("positions", "learned") != "rope":
        return None
    spec["model"]["positions"] = "learned"
    return spec


def _passes(n):
    def apply(spec):
        if spec["data"].get("passes") == n:
            return None
        spec["data"]["passes"] = n
        return spec

    return apply


LEVERS = {
    "depth": ("Depth", "more layers, the next deeper preset of the class (the keel 2 to 3; the pilot 4 to 6)", "l", _bump_preset("layers")),
    "heads": ("Heads", "more heads, the next preset of the class with more (the keel 2 to 4; the pilot 4 to 8)", "h", _bump_preset("heads")),
    "tack": ("The copy tack", "the induction tack (alpha 3): loss weighted towards what copying can predict", "copy", _tack),
    "lr-up": ("Learning rate x2", "twice the learning rate", "lr2", _lr(2.0)),
    "lr-down": ("Learning rate /2", "half the learning rate", "lrh", _lr(0.5)),
    "learned": ("Learned positions", "a learned position table instead of rotary positions", "learned", _positions),
    "passes-1": ("One pass", "read the corpus once instead of four times", "p1", _passes(1)),
    "passes-2": ("Two passes", "read the corpus twice instead of four times", "p2", _passes(2)),
    "seed": ("Seed", "the same voyage with a new seed: the noise, which should move nothing", "seed", None),
}  # fmt: skip


def _variation_of(name: str) -> str:
    m = re.match(r"fu-ogden-v0-1(?:~([a-z0-9-]+))?@", name)
    return (m.group(1) or "") if m else ""


def controls_for(preset: str) -> list[str]:
    """The voyages of this class the Navigator can pull a lever on: Ogden v0.1's, base and variations."""
    _ogden_specs.cache_clear()
    cls = _class_of(preset)
    return sorted(n for n, s in _ogden_specs().items() if _class_of(s["model"]["preset"]) == cls)


def build_pull(control: str, lever: str) -> dict:
    """The pull voyage's spec: the control's, with the lever pulled, named as a variation of Ogden v0.1."""
    import copy

    _ogden_specs.cache_clear()
    specs = _ogden_specs()
    if control not in specs:
        raise ValueError(f"no Ogden v0.1 voyage {control!r}")
    if lever not in LEVERS:
        raise ValueError(f"no lever {lever!r}; levers: {', '.join(LEVERS)}")
    name, about, tag, apply = LEVERS[lever]
    base = specs[control]
    spec = copy.deepcopy(base)
    seed = base["seed"]
    var = _variation_of(control)
    if lever == "seed":
        taken = {s["seed"] for s in specs.values() if _variation_of(s["name"]) == var and s["model"]["preset"] == base["model"]["preset"]}
        seed = max(taken | {seed}) + 1
        spec["seed"] = seed
        newvar = var
    else:
        spec = apply(spec)
        if spec is None:
            raise ValueError(f"the lever {name!r} cannot be pulled on {control} (already pulled, or not for this class)")
        if lever == "depth":
            tag = "l" + spec["model"]["preset"].split("-l")[-1]
        if lever == "heads":
            tag = "h" + spec["model"]["preset"].split("-h")[-1]
        newvar = f"{var}-{tag}" if var else tag
    preset = spec["model"]["preset"]
    spec["name"] = f"fu-ogden-v0-1{('~' + newvar) if newvar else ''}@{preset}-pre-s{seed}"
    spec["ship"] = f"Fitout: Ogden v0.1 @ {preset}{(' ~ ' + newvar) if newvar else ''}, pretraining"
    spec["question"] = f"The Navigator's Wager: what does {name.lower()} ({about}) do to where the cards fall, against {control}?"
    spec["fitout"] = {"key": "ogden-v0-1", "variation": newvar or None}
    return spec


def _store():
    from thorp.viable.s3_control import fitout_store

    return fitout_store


def deal(preset: str, control: str, lever: str) -> dict:
    """Deal a round: the pull voyage built from the control and the lever, kept in Postgres (game.rounds)."""
    from thorp.viable.s3_control.models import WagerRound

    spec = build_pull(control, lever)
    with _store().session() as s, s.begin():
        row = s.get(WagerRound, spec["name"])
        if row is None:
            row = WagerRound(key=spec["name"], preset=preset, lever=lever, control=control, pull=spec["name"],
                             pull_spec=spec, status="dealt")  # fmt: skip
            s.add(row)
    return {"key": spec["name"], "lever": LEVERS[lever][0], "control": control, "pull": spec["name"]}


def place(round_key: str, card: str, move_: str | None, layer: int | None = None, player: str = "Justin") -> dict:
    """Place (or take back, with move None) a player's chip on a card; five a round, each."""
    from sqlalchemy import delete, func, select

    from thorp.viable.s3_control.models import WagerBet

    c = deck.BY_KEY.get(card)
    if c is None:
        raise ValueError(f"no card {card!r}")
    if move_ is not None and move_ not in MOVES:
        raise ValueError(f"a move is one of {', '.join(MOVES)}")
    if move_ is not None and not deck.charted(c):
        raise ValueError(f"{c.name} is uncharted: Thorp cannot yet tell whether it is played")
    sailed = _voyage(round_key) is not None
    with _store().session() as s, s.begin():
        if move_ is None:
            s.execute(delete(WagerBet).where(WagerBet.round_key == round_key, WagerBet.card == card, WagerBet.player == player))
            return {"removed": card}
        held = s.scalar(select(func.count()).select_from(WagerBet).where(
            WagerBet.round_key == round_key, WagerBet.card != card, WagerBet.player == player))
        if held >= CHIPS:
            raise ValueError("five chips a round: take one back before placing another")
        s.merge(WagerBet(round_key=round_key, card=card, player=player, move=move_, layer=layer, practice=sailed))
    return {"placed": card, "move": move_, "layer": layer, "practice": sailed, "player": player}


def bets(round_key: str, player: str = "Justin") -> dict[str, dict]:
    from sqlalchemy import select

    from thorp.viable.s3_control.models import WagerBet

    with _store().session() as s:
        return {
            b.card: {"move": b.move, "layer": b.layer, "practice": b.practice, "placed_at": b.placed_at.isoformat()}
            for b in s.scalars(select(WagerBet).where(WagerBet.round_key == round_key, WagerBet.player == player))
        }


def queue(round_key: str) -> dict:
    """Queue the pull voyage: its spec written to ships/specs/fitouts/, passed through the S3 gate, and put at
    the end of the standing queue. A voyage already written (one of Ogden's own) is queued as it is."""
    import yaml

    from thorp import vsm
    from thorp.viable.s3_control.models import WagerRound

    with _store().session() as s, s.begin():
        row = s.get(WagerRound, round_key)
        spec = dict(row.pull_spec) if row else None
        if row is None:
            _ogden_specs.cache_clear()
            spec = _ogden_specs().get(round_key)
        if spec is None:
            raise ValueError(f"no round {round_key!r}")
        if _voyage(spec["name"]) is not None:
            raise ValueError(f"{spec['name']} has already sailed")
        line = f"fitouts/{spec['name']}"
        q = paths.resolve("specs/queue.txt")
        queued = [ln.strip() for ln in q.read_text().splitlines()]
        if line in queued:
            raise ValueError(f"{spec['name']} is already in the queue")
        vsm.gate(spec)  # S3 before the queue: a refused voyage is not queued
        p = paths.resolve(f"specs/{line}.yaml")
        if not p.exists():
            p.write_text(
                "# ships/specs/fitouts: dealt in the Navigator's Wager (the Bet tab): Ogden v0.1 with one lever pulled.\n"
                + yaml.safe_dump(spec, sort_keys=False, width=100)
            )
        with q.open("a", encoding="utf-8") as f:
            f.write(f"# The Navigator's Wager: {round_key}\n{line}\n")
        if row is not None:
            row.status = "queued"
            row.queued_at = __import__("datetime").datetime.now(__import__("datetime").UTC)
    return {"queued": spec["name"], "position": sum(1 for ln in queued if ln and not ln.startswith("#")) + 1}


def dealt_rounds(preset: str) -> list[dict]:
    from sqlalchemy import select

    from thorp.viable.s3_control.models import WagerRound

    cls = _class_of(preset)
    with _store().session() as s:
        rows = s.scalars(select(WagerRound).order_by(WagerRound.dealt_at.desc()))
        return [
            {"key": r.key, "lever": LEVERS.get(r.lever, (r.lever,))[0], "about": LEVERS.get(r.lever, ("", ""))[1],
             "control": r.control, "pull": r.pull, "source": "dealt", "status": r.status}
            for r in rows if _class_of(r.preset) == cls
        ]  # fmt: skip

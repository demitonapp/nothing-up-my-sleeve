"""The plan, and which waters each ship sails in (the Queue tab, /api/waters; Justin, 8 November: "so i can easily
understand what's the plan and then within that plan which ships are in local waters (mac mini) and which are in
foreign waters as per the coordinator").

Read only through the coordinator (thorp/viable/s2_coordination/lanes.py: which lane a line sails in, what it waits
for, what each lane has out) and the charter (S3's spend: the ships hired and not released; S5's terms). **Local
waters** are this Mac mini, the Mac lane; **foreign waters** are GPUs hired from Vast.ai, the Vast lane.

The plan is the standing queue in its order, each line with its lane, about when it sails and for how long, and
what it waits for. Times are guides: a voyage at its class's mean wall time on this Mac over finished voyages (on a
hired GPU no slower than that, the charter's own rule until a class has sailed); a hold at its longest; another
step between voyages with no time of its own.
"""

from __future__ import annotations

import contextlib
import re
import time
from datetime import datetime

from thorp import paths

WATERS = {
    # local waters are Phaleron (Justin, 8 November: "name it after a famous bay, perhaps that the greeks used to
    # train ships in"): Athens' first harbour, where its early fleet lay before Themistocles built Piraeus beside it
    "mac": {"name": "Phaleron", "where": "this Mac mini", "how": "MLX, the Mac lane: internal waters"},
    # outer waters are the Market Harbour (Justin, 8 November: "the outer waters should be the first great trading
    # harbour"): where the ships that need hired GPUs trade
    "vast": {"name": "The Market Harbour", "where": "a GPU hired from Vast.ai", "how": "torch on CUDA, the Vast lane: outer waters"},
}

# The harbours the Ships page opens on (Justin, 8 November: "on the ships pages, it's actually called harbours and then
# when you open it, it's two tiles for the two harbours of today and then you click in the harbour to view its ships.
# So Phaleron has Pan, Augustus, the 9m and the 21m and then the Market Harbour has the 50m up"). A ship's harbour is
# its size's; a size not named here is in the outer harbour. To be a column of s1.sizes once the store takes it.
HARBOURS = (
    {"key": "phaleron", "name": "Phaleron", "aka": "internal waters", "lane": "mac", "where": "this Mac mini",
     "about": "Athens' first harbour, where its early fleet lay and sailed from: the youngest ships, trained on this Mac.",
     "sizes": ("300k", "1m", "9m", "21m")},
    {"key": "market", "name": "The Market Harbour", "aka": "outer waters", "lane": "vast", "where": "GPUs hired from Vast.ai",
     "about": "The first great trading harbour: the ships that need hired GPUs, from the 50m up.",
     "sizes": ("50m", "100m", "350m")},
)  # fmt: skip


def harbour_of(preset: str) -> str:
    return next((h["key"] for h in HARBOURS if preset in h["sizes"]), HARBOURS[-1]["key"])


def _wall_minutes() -> dict:
    """Wall times (minutes) of voyages finished on this Mac: per class (the mean), and per corpus and class (the
    latest), since a class's voyages on a bigger corpus take longer (the 9m on Ogden v0.2: 3.5 h; on v0.1: 1.2 h)."""
    from thorp.ledger import Ledger

    out: dict = {}
    with contextlib.suppress(Exception):
        mlx = "status='finished' and wall_minutes > 0 and coalesce(json_extract(spec_json,'$.model.backend'),'mlx')='mlx'"
        rec = Ledger()
        for r in rec.query(f"select json_extract(spec_json,'$.model.preset') p, avg(wall_minutes) m from runs where {mlx} group by p"):
            out[r["p"]] = r["m"]
        for r in rec.query(  # keyed by the corpus read (the ledger's spec keeps data.recipe, not the fitout label)
            "select json_extract(spec_json,'$.model.preset') p, json_extract(spec_json,'$.data.recipe') f, wall_minutes m"
            f" from runs where {mlx} and json_extract(spec_json,'$.data.recipe') is not null order by finished"
        ):
            out[(r["f"], r["p"])] = r["m"]  # the latest wins
    return out


def _step_minutes() -> dict:
    """How long each queue command took the last time it ran (data/runs/queue.out's starting and exited lines)."""
    out, start = {}, {}
    pat = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\] (?:\[\w+\] )?(starting (.*)|(.*) exited -?\d+)$")
    with contextlib.suppress(Exception):
        for line in (paths.data_dir() / "runs" / "queue.out").read_text(encoding="utf-8", errors="replace").splitlines():
            m = pat.match(line)
            if not m:
                continue
            t = int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 60
            if m.group(5) is not None:
                start[m.group(5).strip()] = t
            else:
                text = m.group(6).strip()
                if text in start:
                    out[text] = (t - start.pop(text)) % (24 * 60)
    return out


HOLD = re.compile(r"while \[ -e (\S+\.hold) \](?: && \[ \$n -lt (\d+) \])?.*?sleep (\d+)")


def _hold(cmd: str) -> dict | None:
    """A hold line (`while [ -e <file>.hold ] && [ $n -lt N ]; do sleep S ...`): its file, whether it is still
    held, its longest wait and what the hold file says it waits for."""
    m = HOLD.search(cmd)
    if not m:
        return None
    rel, n, s = m.group(1), m.group(2), m.group(3)
    p = paths.resolve(rel.removeprefix("ships/"))
    note = ""
    with contextlib.suppress(Exception):
        note = p.read_text(encoding="utf-8").strip()
    return {"file": rel, "held": p.exists(), "max_min": round(int(n) * int(s) / 60) if n else None, "note": note}


def _step_name(cmd: str) -> str:
    """A short name for a queue command: what it runs (a module or a script) and on what."""
    m = re.search(r"python (?:-m )?(\S+)(.*?)(?:>>|$)", cmd)
    if not m:
        return cmd.split(";")[0][:80]
    what = m.group(1).replace("thorp.", "").replace("backend/scripts/", "")
    args = [a.split("/")[-1] for a in m.group(2).split() if not a.startswith("-")]
    return f"{what} {' '.join(args[:3])}".strip() + (" …" if len(args) > 3 else "")


_BOOKS: dict[str, int | None] = {}


def _books(recipe: str) -> int | None:
    """How many books a reading list names (its rows), cached by path."""
    if recipe not in _BOOKS:
        n = None
        with contextlib.suppress(Exception):
            import csv

            with paths.resolve(recipe).open(newline="", encoding="utf-8") as f:
                n = sum(1 for _ in csv.DictReader(f))
        _BOOKS[recipe] = n
    return _BOOKS[recipe]


def _fitout(key: str | None) -> dict:
    """The named fitout (ships/fitouts/<key>.json): its name and aim."""
    import json

    if not key:
        return {}
    with contextlib.suppress(Exception):
        return json.loads(paths.resolve(f"fitouts/{key}.json").read_text(encoding="utf-8"))
    return {}


def _like_run(recipe: str | None, preset: str | None) -> dict:
    """The last finished voyage on this Mac of the same corpus and size: its steps and tokens (the material's
    size and the voyage's length, which only preparing the voyage would otherwise tell)."""
    from thorp.ledger import Ledger

    if not recipe:
        return {}
    with contextlib.suppress(Exception):
        rows = Ledger().query(
            "select r.tokens_seen t, (select max(step) from metrics where run_id=r.run_id and name='loss') s,"
            " json_extract(r.spec_json,'$.data.passes') p from runs r where r.status='finished'"
            " and json_extract(r.spec_json,'$.data.recipe')=? and json_extract(r.spec_json,'$.model.preset')=?"
            " order by r.finished desc limit 1",
            [recipe, preset],
        )
        if rows:
            r = rows[0]
            return {"steps": r["s"], "tokens": r["t"], "per_pass": int(r["t"] / r["p"]) if r["t"] and r["p"] else None}
    return {}


def _material(spec: dict) -> dict:
    """What a voyage reads: its fitout, each stage's reading list, books and passes, and about how many tokens."""
    d = spec.get("data") or {}
    f = spec.get("fitout") if isinstance(spec.get("fitout"), dict) else {}
    fo = _fitout(f.get("key"))
    stages = d.get("stages") or ([{"name": "the reading", "recipe": d["recipe"], "passes": d.get("passes", 1)}] if d.get("recipe") else [])
    like = _like_run(d.get("recipe"), (spec.get("model") or {}).get("preset"))
    return {
        "fitout": fo.get("name") or f.get("key"),
        "variation": f.get("variation"),
        "aim": fo.get("aim"),
        "stages": [{"name": s.get("name"), "recipe": s.get("recipe"), "books": _books(s.get("recipe", "")), "passes": s.get("passes", 1)} for s in stages],
        "tokens_per_pass": like.get("per_pass"),
        "clean": d.get("clean"),
        "opt_in": bool(d.get("opt_in")),
        "held_out": len(d.get("refuse") or []),
    }


def _training(spec: dict) -> dict:
    """How a voyage trains: its length, the optimiser's schedule, and the pulls and tacks on top."""
    o, m, d = spec.get("optim") or {}, spec.get("model") or {}, spec.get("data") or {}
    sc = o.get("scaffold") or {}
    like = _like_run(d.get("recipe"), m.get("preset"))
    plan = {
        "steps": like.get("steps"),
        "batch_tokens": o.get("batch_tokens"),
        "lr": o.get("lr"),
        "schedule": o.get("schedule"),
        "warmup": o.get("warmup_steps"),
        "context": m.get("context"),
        "positions": m.get("positions"),
        "backend": m.get("backend") or "mlx",
        "phases": [],
    }
    if sc:
        heads = sc.get("heads") or []
        cards = sorted({h["card"].replace("_", " ") for h in heads})
        ph = [f"the pull on {len(heads)} heads ({', '.join(cards)})" + (f" and the {' and '.join(sc['riddles'])} riddle{'s' if len(sc['riddles']) > 1 else ''}" if sc.get("riddles") else "")]
        if any("from" in h for h in heads) or any("from" in r for r in (sc.get("riddles") or {}).values()):
            starts = sorted({float(x.get("from", 0)) for x in [*heads, *(sc.get("riddles") or {}).values()]})
            ph.append("staged: " + ", ".join("from the start" if s == 0 else f"more from {s:.0%}" for s in starts))
        if sc.get("fade") is not None:
            ph.append(f"full weight to {float(sc.get('hold', 0)):.0%}, eased to {sc.get('floor', 0)} by {float(sc['fade']):.0%}")
        if sc.get("release") is not None:
            ph.append(f"released (off) from {float(sc['release']):.0%}")
        if ((sc.get("riddles") or {}).get("bridge") or {}).get("kinds") == "all":
            ph.append("the Bridge in all four relations")
        plan["phases"] = ph
    if (o.get("copy_weight") or {}).get("alpha"):
        plan["phases"].append(f"the copy tack ({o['copy_weight'].get('kind')}, alpha {o['copy_weight']['alpha']})")
    if (o.get("teacher") or {}).get("run"):
        plan["phases"].append(f"taught by {o['teacher']['run']}")
    if (spec.get("seeded_from") or {}).get("run"):
        plan["phases"].append(f"seeded from {spec['seeded_from']['run']} ({spec['seeded_from'].get('mode', 'free')})")
    return plan


def _voyage(ln, wall: dict) -> dict:
    from thorp import fleet

    spec = ln.spec or {}
    m = spec.get("model") or {}
    ex = fleet.expedition_of_label(spec.get("name"), spec.get("ship"))
    return {
        "name": ln.name or ln.payload,
        "spec": ln.payload,
        "ship": spec.get("ship") or "",
        "material": _material(spec) if spec else None,
        "training": _training(spec) if spec else None,
        "goal": spec.get("question") or spec.get("experiment") or "",
        "expedition": ex,
        "expedition_name": fleet.EXPEDITIONS[ex].name if ex in fleet.EXPEDITIONS else None,
        "preset": m.get("preset"),
        "seed": spec.get("seed"),
        "missing": ln.spec is None,
        "est_min": next((round(wall[k]) for k in (((spec.get("data") or {}).get("recipe"), m.get("preset")), m.get("preset")) if k in wall), None),
    }


def _item(ln, wall: dict, steps: dict | None = None) -> dict:
    out = {"lane": ln.lane, "kind": ln.kind, "text": ln.text}
    if ln.kind == "spec":
        out.update(_voyage(ln, wall))
    elif ln.kind == "wait":
        out.update(name=f"wait for {ln.payload} to dock", est_min=0)
    else:
        h = _hold(ln.payload)
        last = (steps or {}).get(ln.text)
        out.update(name=_step_name(ln.payload), hold=h, est_is_max=bool(h),
                   est_min=(h or {}).get("max_min") if h else (round(last) if last is not None else None))  # fmt: skip
        if h:
            out["kind"] = "hold"
            out["name"] = f"hold: {h['file'].split('/')[-1]}"
    return out


def _step_now(name: str | None) -> int | None:
    """The last step a voyage at sea has recorded (its running row on the ledger)."""
    from thorp.ledger import Ledger

    with contextlib.suppress(Exception):
        rows = Ledger().query(
            "select (select max(step) from metrics m where m.run_id=r.run_id and m.name='loss') s from runs r"
            " where r.name=? and r.status='running' order by r.started desc limit 1",
            [name],
        )
        return rows[0]["s"] if rows else None
    return None


def _since_min(since: str | None) -> float | None:
    with contextlib.suppress(Exception):
        return (time.time() - datetime.fromisoformat(since).timestamp()) / 60
    return None


def waters() -> dict:
    from thorp.viable.s2_coordination import lanes
    from thorp.viable.s3_control import charter as s3
    from thorp.viable.s5_policy import charter as s5

    wall, steps = _wall_minutes(), _step_minutes()
    q = paths.resolve("specs/queue.txt")
    lines = [lanes.parse(t, q.parent) for t in lanes.pending(q)]
    st = lanes.state()
    key = lanes.has_key()
    now = time.time()

    # what each lane has out now, and about how long it has left
    at_sea, ahead = {}, {}
    for lane in lanes.LANES:
        r = st.get(lane)
        if not r:
            at_sea[lane], ahead[lane] = None, 0.0
            continue
        it = _item(lanes.parse(r["line"], q.parent), wall, steps)
        gone = _since_min(r.get("since"))
        left = None if it.get("est_min") is None or gone is None else max(0.0, it["est_min"] - gone)
        at_sea[lane] = {**it, "since": r.get("since"), "pid": r.get("pid"), "elapsed_min": round(gone) if gone is not None else None,
                        "left_min": round(left) if left is not None else None}  # fmt: skip
        if it.get("kind") == "spec":  # how far it has sailed: its last step on the ledger, of its like voyage's steps
            at_sea[lane]["step"] = _step_now(it.get("name"))
        ahead[lane] = left or 0.0

    # the hired ships (S3's spend log): one may be out though the queue did not send it (a charter sailed by hand)
    ships = []
    with contextlib.suppress(Exception):
        for h in s3.out_now():
            ships.append({
                "name": h.get("name"), "run_id": h.get("run_id"), "gpu": h.get("gpu"), "dph": h.get("dph"),
                "since": datetime.fromtimestamp(float(h["started"])).isoformat(timespec="seconds"),
                "cost": round(s3.cost_of(h), 2), "quote": h.get("quote"), "quote_hours": h.get("quote_hours"),
                "left_min": round(max(0.0, float(h.get("quote_hours") or 0) * 60 - (now - float(h["started"])) / 60)),
                "by_queue": bool(at_sea.get("vast")) and at_sea["vast"].get("spec") and h.get("name") == at_sea["vast"].get("name"),
            })  # fmt: skip
    if ships and not at_sea.get("vast"):
        ahead["vast"] = max(s["left_min"] for s in ships)  # one ship out at a time: the next waits for it

    # the plan: the queue in its order, each line in its lane at about its time
    plan, unknown = [], {lane: False for lane in lanes.LANES}
    for lane in lanes.LANES:  # what is at sea heads the plan: it sails now
        if at_sea[lane]:
            plan.append({**at_sea[lane], "n": None, "at_sea": True, "starts_at": "now", "starts_in_min": 0, "at_least": False, "waits_for": None})
    sea = {lane: (lanes.parse(st[lane]["line"], q.parent) if st.get(lane) else None) for lane in lanes.LANES}
    for i, ln in enumerate(lines):
        it = _item(ln, wall, steps)
        why = lanes.blocked(ln, lines[:i], sea)
        if ln.lane == "vast" and not key:
            why = "no Vast.ai key yet"
        start = ahead[ln.lane]
        it.update(n=i + 1, starts_in_min=round(start), at_least=unknown[ln.lane], waits_for=why,
                  starts_at=datetime.fromtimestamp(now + start * 60).strftime("%H:%M"))  # fmt: skip
        if it.get("est_min") is None:
            unknown[ln.lane] = True
        else:
            ahead[ln.lane] += it["est_min"]
        plan.append(it)

    t = s5.terms()
    week = {"spent": None, "budget": t.get("weekly_budget"), "voyage_budget": t.get("voyage_budget"),
            "max_out": t.get("max_instances"), "gpus": t.get("gpus")}  # fmt: skip
    with contextlib.suppress(Exception):
        week["spent"] = round(s3.week_spent(), 2)
    lanes_out = {}
    for lane in lanes.LANES:
        mine = [p for p in plan if p["lane"] == lane]
        lanes_out[lane] = {
            **WATERS[lane],
            "at_sea": at_sea[lane],
            "queued": len(mine),
            "voyages": sum(p["kind"] == "spec" for p in mine),
            "hours_left": round(ahead[lane] / 60, 1),
            "at_least": unknown[lane],
            "clear_at": datetime.fromtimestamp(now + ahead[lane] * 60).strftime("%a %H:%M"),
        }
    lanes_out["vast"].update(ships=ships, key=key, week=week)
    return {"now": datetime.fromtimestamp(now).strftime("%H:%M"), "lanes": lanes_out, "plan": plan}

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
    "mac": {"name": "Local waters", "where": "this Mac mini", "how": "MLX, the Mac lane"},
    "vast": {"name": "Foreign waters", "where": "a GPU hired from Vast.ai", "how": "torch on CUDA, the Vast lane"},
}


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


def _voyage(ln, wall: dict) -> dict:
    from thorp import fleet

    spec = ln.spec or {}
    m = spec.get("model") or {}
    ex = fleet.expedition_of_label(spec.get("name"), spec.get("ship"))
    return {
        "name": ln.name or ln.payload,
        "spec": ln.payload,
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

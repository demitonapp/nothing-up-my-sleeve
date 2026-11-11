"""The expeditions' priority, by goal (11 November, Justin: on an expedition's goal, choose the priority
across all expeditions, so the coordinator can schedule accordingly; then, the same day, "the queue has
to be more flexible. So it has to be ordered by goals within an expedition. So I could run an ARC-AGI
audit as a goal under arc de triomphe and then next a knockout expedition goal").

A key is an expedition (`arc_de_triomphe`), or one of its goals (`arc_de_triomphe:3`, the goal's 1-based
row in `fleet.EXPEDITIONS[...].goals`). An expedition that states goals is ranked one row a goal, so a
goal of one expedition can sit between two goals of another; an expedition that states none is one row.
A spec joins a goal by naming it: `goal: 4` in the fitout's YAML. A line with no goal sits with its
expedition's first goal, so an unmarked queue still sails in expedition order.

The queue is still the coordinator's order — a line never sails before the one above it. What priority
does is *order the queue*: on save, the pending spec lines are stably sorted by their expedition's rank
(cmd and wait lines keep their places), so the highest-priority expedition's earliest line is first and
the coordinator schedules it next without a new scheduling rule.

The order lives in `data/expedition-priority.json` (`{"order": [keys]}`), beside the other operational
choices (`data/policies.json`), and is Justin's: nothing here invents a priority, it only records and
applies one. An expedition missing from the file sits after the ranked ones, in fleet.py's own order.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from thorp import fleet, paths


def _path() -> Path:
    return paths.data_dir() / "expedition-priority.json"


def goals_of(key: str) -> list[str]:
    """An expedition's goals as the page names them, in fleet.py's order (empty where it states none)."""
    e = fleet.EXPEDITIONS.get(key)
    return [str(g.get("text") or "") for g in getattr(e, "goals", ()) if g.get("text")]


def keys_for(key: str) -> list[str]:
    """The priority rows an expedition owns: one a goal where it states goals, else the expedition."""
    n = len(goals_of(key))
    return [f"{key}:{i + 1}" for i in range(n)] if n else [key]


def known() -> list[str]:
    """Every key that can stand in the order, in fleet.py's own order."""
    out: list[str] = []
    for k in fleet.EXPEDITIONS:
        out.extend(keys_for(k))
    return out


def closed(key: str) -> bool:
    """An expedition that is over: nothing may be planned under it (11 November, Justin: "you shouldn't
    be able to plan an expedition that is closed"). `done` is the fleet's own word for it."""
    e = fleet.EXPEDITIONS.get(key.split(":", 1)[0])
    return bool(e) and e.status == "done"


def order() -> list[str]:
    """Every rankable key, ranked first, in fleet.py's order after the ranked ones.

    A bare expedition key saved before goals were ranked expands to its goals in place, so an order
    written under the old shape keeps its meaning."""
    try:
        raw = json.loads(_path().read_text(encoding="utf-8")).get("order") or []
    except (OSError, ValueError):
        raw = []
    every = known()
    out: list[str] = []
    for k in (str(x) for x in raw):
        for want in (keys_for(k) if k in fleet.EXPEDITIONS else [k]):
            if want in every and want not in out:
                out.append(want)
    out += [k for k in every if k not in out]
    return out


def rank(key: str | None) -> int:
    """Where an expedition stands: the first row it owns."""
    try:
        first = keys_for(str(key))[0]
        return order().index(first)
    except (ValueError, TypeError):
        return len(known())


def rank_of(expedition: str | None, goal: int | None) -> int:
    """Where a line stands: its own goal's row when the expedition states goals, else the expedition's
    first row. A line with no goal sits with its expedition, never in a bucket of its own."""
    rows = order()
    if expedition and goal:
        with_goal = f"{expedition}:{int(goal)}"
        if with_goal in rows:
            return rows.index(with_goal)
    return rank(expedition)


def set_order(keys: list[str]) -> list[str]:
    """Record the order (unknown keys dropped, missing ones appended) and reorder the queue to it."""
    every = known()
    ranked: list[str] = []
    for k in (str(x) for x in keys):
        for want in (keys_for(k) if k in fleet.EXPEDITIONS else [k]):
            if want in every and want not in ranked:
                ranked.append(want)
    ranked += [k for k in every if k not in ranked]
    _path().parent.mkdir(parents=True, exist_ok=True)
    _path().write_text(
        json.dumps({"order": ranked, "updated": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=2) + "\n",
        encoding="utf-8",
    )
    apply_queue()
    return ranked


def _line_rank(row: dict) -> int:
    """A queue line's rank: its expedition's goal row when the spec names a goal, else the expedition's
    own row. A spec that cannot be read goes last."""
    import yaml

    if row.get("kind") != "spec":
        return len(known())
    p = paths.resolve("specs") / f"{row['payload']}.yaml"
    try:
        spec = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except (OSError, ValueError):
        return len(known())
    exp = fleet.expedition_of_label(spec.get("name"), spec.get("ship"))
    goal = spec.get("goal")
    try:
        goal = int(goal) if goal is not None else None
    except (TypeError, ValueError):
        goal = None
    return rank_of(exp, goal)


def apply_queue() -> bool:
    """Stable-sort the pending spec lines by their expedition's priority, cmd/wait lines untouched."""
    try:
        from thorp.viable.s2_coordination import queue_store

        queue_store.sort_specs(_line_rank)
        queue_store.export()
        return True
    except Exception:  # noqa: BLE001  the store may be down; the order is still recorded
        return False

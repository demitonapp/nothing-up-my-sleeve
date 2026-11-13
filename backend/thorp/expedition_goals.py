"""An expedition's goals as rows, and the queue's link to them (11 November, Justin: "the goals have to
have a relationship to expeditions in the db ... so we start retiring expeditions").

Two tables and one column:

- `s1.expeditions` — one row per expedition. `fleet.EXPEDITIONS` stays the source of the words (name,
  goal, fleet, preset); this table is the row a goal and a queue line can hang from, and the record of
  a declared status.
- `s1.expedition_goals` — one row a goal, keyed by the same `expedition:position` key `priorities.py`
  already ranks by (`kipling:3`), or by the bare expedition key where it states no goals (there the
  single row carries the expedition's own `goal` text). **The store owns the numbered goals** (13 November,
  Justin: "shouldn't it be going straight to postgres?"): their words (`text`, `detail`, `why`) and their
  verdict (`status`, `evidence`, `settled_at`, `words`) are rows, added and edited with `thorp goals add` and
  `thorp goals edit`, and no sync touches them. `fleet.py` states no goals; only an expedition that has no
  numbered goal in the store is synced from code (its one bare row, or goals a new expedition's code seeds).
- `s2.queue_lines.goal_id` — which goal a pending line serves, so work is attributable and an
  expedition can be retired when every one of its goals is `done` or `dropped`.

A goal is retired when its verdict is `done` (`dropped` for one deliberately abandoned). That is a
claim about the ledger, so `evidence` holds where the reading is: run name, metric, value.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from thorp import fleet, store

# the values are the column's check (expedition_goals_status); listed here only to name them in the message.
# open: no reading yet / not started; partly: some readings, the question not settled; done: settled;
# dropped: deliberately abandoned (with a reason in `words`).
STATUSES = ("open", "partly", "done", "dropped")

def ensure() -> None:
    """The tables are Alembic's (v3q6r9s2t5u8 made them; e6a8b0c2d4f6 added `shown`): no runtime DDL (13 November, Justin: all
    database work in Postgres). Kept so the callers read as they did; it has nothing to do."""


def goal_id_of(key: str, position: int, stated: bool) -> str:
    """The key a goal is known by: `key:n` where the expedition states goals, else the bare key
    (the same namespace `priorities.keys_for` ranks, so a priority row and a goal id are one string)."""
    return f"{key}:{position}" if stated else key


def _rows_of(e: fleet.Expedition) -> list[dict]:
    """An expedition's goals as rows, from the code's words.

    A goal may carry its own `position` (1-based, the page's own numbering). That keeps an id stable when
    an earlier goal is deleted — Justin, 11 November: two of the knockout's three goals were removed, and
    the remaining one must stay `knockout:3`, not slide into the freed `knockout:1`."""
    if e.goals:
        rows = []
        for i, g in enumerate(e.goals, 1):
            pos = int(g.get("position") or i)
            rows.append(
                {
                    "goal_id": goal_id_of(e.key, pos, True),
                    "position": pos,
                    "text": str(g.get("text") or ""),
                    "detail": str(g.get("detail") or ""),
                    "why": str(g.get("why") or ""),
                }
            )
        return rows
    # no stated goals: the expedition's own goal is its one row, and its key is the priority key. A
    # closed expedition's row is born settled, so a re-sync never reopens a goal on an expedition that
    # is over (the merged Arc de Triomphe, 11 November), and a closed expedition that never had goals
    # keeps its single record instead of losing it.
    return [
        {
            "goal_id": goal_id_of(e.key, 0, False),
            "position": 0,
            "text": str(e.goal or ""),
            "detail": "",
            "why": "",
            "status": "done" if e.status == "done" else "open",
        }
    ]


def _stale() -> bool:
    """True when fleet.py on disk is newer than the copy this process imported. A long-running process (the
    coordinator syncs on every pass) would otherwise write yesterday's words back and delete every open goal
    added since it started (12 November: kipling:8 and :9 were deleted by a coordinator up since 6:42 PM)."""
    import os

    try:
        return os.path.getmtime(fleet.__file__) > _FLEET_LOADED
    except OSError:
        return False


_FLEET_LOADED = __import__("os").path.getmtime(fleet.__file__)


def sync() -> dict[str, int]:
    """Upsert every expedition from `fleet.EXPEDITIONS`, and the goals of those the store holds no numbered goal for.

    Run after a fleet edit or on a refresh. Idempotent, and safe on a fresh store (it creates the two
    tables). An expedition with numbered goals in the store is left to the store: its goals are never rewritten
    or deleted from the code (12 November: a coordinator syncing old words deleted kipling:8 and :9). An
    expedition without any is synced as before: its one bare row, or the goals a new expedition's code states
    (a seed, after which they are the store's). A process whose fleet.py is older than the file on disk does
    nothing: it would undo the edit it has not loaded."""
    if _stale():
        return {"expeditions": 0, "goals": 0, "stale": 1}
    ensure()
    goals = 0
    owned = set(numbered())
    with store.session() as s:
        for key, e in fleet.EXPEDITIONS.items():
            s.execute(
                text(
                    "insert into s1.expeditions (key, name, goal, fleet, preset, ship, declared_status, updated_at) "
                    "values (:key, :name, :goal, :fleet, :preset, :ship, :status, now()) "
                    "on conflict (key) do update set name = excluded.name, goal = excluded.goal, "
                    "fleet = excluded.fleet, preset = excluded.preset, ship = excluded.ship, "
                    "declared_status = excluded.declared_status, updated_at = now()"
                ),
                {
                    "key": key,
                    "name": e.name,
                    "goal": e.goal,
                    "fleet": e.fleet,
                    "preset": e.preset,
                    "ship": e.ship,
                    "status": e.status,
                },
            )
            if key in owned:
                continue
            rows = _rows_of(e)
            for r in rows:
                s.execute(
                    text(
                        "insert into s1.expedition_goals (goal_id, expedition_key, position, text, detail, why, status) "
                        "values (:goal_id, :key, :position, :text, :detail, :why, :status) "
                        "on conflict (goal_id) do update set expedition_key = excluded.expedition_key, "
                        "position = excluded.position, text = excluded.text, detail = excluded.detail, "
                        "why = excluded.why, updated_at = now()"
                    ),
                    {**r, "key": key, "status": r.get("status", "open")},
                )
                goals += 1
            kept = [r["goal_id"] for r in rows]
            # a goal the code no longer states goes, unless it was settled (then it is a record)
            s.execute(
                text(
                    "delete from s1.expedition_goals where expedition_key = :key "
                    "and goal_id <> all(:kept) and status = 'open'"
                ),
                {"key": key, "kept": kept},
            )
    return {"expeditions": len(fleet.EXPEDITIONS), "goals": goals, "reattached": _reattach()}


def _reattach() -> int:
    """Give a queued spec line back the goal its spec declares when the line has lost it. The line's goal is a
    foreign key that empties when the goal's row is deleted, and a stale process can delete a goal that the
    code still states (12 November); once the goal is synced back, its lines get it again."""
    try:
        from thorp.viable.s2_coordination import queue_store
    except Exception:  # noqa: BLE001  no queue module on a box
        return 0
    with store.session() as s:
        known = {r[0] for r in s.execute(text("select goal_id from s1.expedition_goals")).all()}
        try:
            lost = s.execute(
                text("select position, payload from s2.queue_lines where goal_id is null and kind = 'spec'")
            ).all()
        except Exception:  # noqa: BLE001  a store whose queue is not migrated yet
            return 0
        n = 0
        for pos, payload in lost:
            g = queue_store._goal_of_spec(payload)
            if g and g in known:
                s.execute(
                    text("update s2.queue_lines set goal_id = :g where position = :p and goal_id is null"),
                    {"g": g, "p": pos},
                )
                n += 1
        return n


def read(expedition: str | None = None) -> list[dict]:
    """Every goal, with its expedition, in expedition order then position."""
    ensure()
    sql = (
        "select g.goal_id, g.expedition_key, e.name, e.declared_status, g.position, g.text, g.detail, "
        "g.why, g.status, g.evidence, g.words, g.settled_at "
        "from s1.expedition_goals g join s1.expeditions e on e.key = g.expedition_key "
        + ("where g.expedition_key = :key " if expedition else "")
        + "order by g.expedition_key, g.position"
    )
    with store.session() as s:
        out = []
        for r in s.execute(text(sql), {"key": expedition} if expedition else {}).mappings():
            d = dict(r)
            d["settled_at"] = d["settled_at"].isoformat() if d["settled_at"] else None
            out.append(d)
        return out


def numbered(expedition: str | None = None) -> dict[str, list[dict]]:
    """The goals each expedition states, from the store: {expedition key: [{position, text, detail, why}]} in
    position order (an expedition with only its bare row is not in it; a goal taken off the page is not in it).
    The same dicts the code's `goals` were."""
    ensure()
    sql = (
        "select expedition_key, position, text, detail, why from s1.expedition_goals where position > 0 and shown "
        + ("and expedition_key = :key " if expedition else "")
        + "order by expedition_key, position"
    )
    out: dict[str, list[dict]] = {}
    with store.session() as s:
        for r in s.execute(text(sql), {"key": expedition} if expedition else {}).mappings():
            out.setdefault(r["expedition_key"], []).append(
                {"position": r["position"], "text": r["text"], "detail": r["detail"], "why": r["why"]}
            )
    return out


def stated(expedition: str) -> list[dict]:
    """One expedition's goals as the page draws them (empty where it states none)."""
    return numbered(expedition).get(expedition, [])


def add(expedition: str, text_: str, detail: str = "", why: str = "", position: int | None = None) -> str:
    """Add a numbered goal and return its id (`knockout:10`). The position defaults to the one after the highest
    (a dropped or settled goal keeps its number, so a number is not handed out twice while the record stands)."""
    if not text_.strip():
        raise ValueError("a goal needs its words")
    ensure()
    with store.session() as s:
        if not s.execute(text("select 1 from s1.expeditions where key = :k"), {"k": expedition}).first():
            raise ValueError(f"no expedition {expedition!r} (thorp goals sync registers the code's expeditions)")
        rows = s.execute(
            text("select position from s1.expedition_goals where expedition_key = :k"), {"k": expedition}
        ).all()
        have = {r[0] for r in rows}
        if have and not any(p > 0 for p in have):
            # the expedition's one bare row (its own goal, key = the expedition) gives way to its first numbered goal,
            # as the sync did when the code began to state goals; a settled one is a record and stays, so it is refused
            bare = s.execute(
                text("select status from s1.expedition_goals where goal_id = :k"), {"k": expedition}
            ).scalar()
            if bare != "open":
                raise ValueError(f"{expedition}'s one goal is {bare}; a settled goal is a record, not replaced")
            s.execute(text("delete from s1.expedition_goals where goal_id = :k"), {"k": expedition})
            have = set()
        pos = int(position) if position else max([p for p in have if p > 0] or [0]) + 1
        if pos in have:
            raise ValueError(f"{goal_id_of(expedition, pos, True)} already exists")
        s.execute(
            text(
                "insert into s1.expedition_goals (goal_id, expedition_key, position, text, detail, why, status) "
                "values (:g, :k, :p, :t, :d, :w, 'open')"
            ),
            {"g": goal_id_of(expedition, pos, True), "k": expedition, "p": pos, "t": text_.strip(), "d": detail, "w": why},
        )
    return goal_id_of(expedition, pos, True)


def edit(goal_id: str, text_: str | None = None, detail: str | None = None, why: str | None = None) -> bool:
    """Change a goal's words; a field left None stays. The verdict is not touched."""
    ensure()
    with store.session() as s:
        r = s.execute(
            text(
                "update s1.expedition_goals set text = coalesce(:t, text), detail = coalesce(:d, detail), "
                "why = coalesce(:w, why), updated_at = now() where goal_id = :g"
            ),
            {"g": goal_id, "t": text_, "d": detail, "w": why},
        )
        return bool(r.rowcount)


def remove(goal_id: str) -> bool:
    """Delete a goal that was never worked on: open, and no queued line serves it. A settled goal is a record
    (`thorp goals set ID dropped` is how one is given up)."""
    ensure()
    with store.session() as s:
        row = s.execute(
            text("select status, position from s1.expedition_goals where goal_id = :g"), {"g": goal_id}
        ).first()
        if not row:
            return False
        if row[0] != "open" or row[1] == 0:
            raise ValueError(f"{goal_id} is {row[0]}: a settled goal is a record; mark it dropped instead")
        try:
            queued = s.execute(text("select count(*) from s2.queue_lines where goal_id = :g"), {"g": goal_id}).scalar()
        except Exception:  # noqa: BLE001  a store whose queue is not migrated yet
            queued = 0
        if queued:
            raise ValueError(f"{goal_id} has {queued} queued line(s); move or drop them first")
        s.execute(text("delete from s1.expedition_goals where goal_id = :g"), {"g": goal_id})
        return True


def dangling(ids) -> list[str]:
    """The goal ids among `ids` the store does not hold: a decision, a priority or a line pointing at nothing."""
    known = {g["goal_id"] for g in read()}
    return sorted(set(ids) - known)


def set_verdict(goal_id: str, status: str, evidence: str = "", words: str = "") -> bool:
    """Record a goal's verdict. `done` stamps `settled_at`; anything else clears it. A `dropped` goal comes off the
    page and out of the priority order and stays as a record."""
    status = status.strip().lower()
    try:
        with store.session() as s:
            r = s.execute(
                text(
                    "update s1.expedition_goals set status = :status, "
                    "evidence = case when :evidence = '' then evidence else :evidence end, "
                    "words = case when :words = '' then words else :words end, "
                    "settled_at = case when :status in ('done','dropped') then now() else null end, "
                    "shown = case when :status = 'dropped' then false else shown end, "
                    "updated_at = now() where goal_id = :goal_id"
                ),
                {"status": status, "evidence": evidence, "words": words, "goal_id": goal_id},
            )
            return bool(r.rowcount)
    except IntegrityError:  # the check on the column (expedition_goals_status) is the rule; Python only says so
        raise ValueError(f"status must be one of {', '.join(STATUSES)}") from None


def retireable() -> list[dict]:
    """Expeditions whose every goal is settled: the ones that can be closed."""
    rows = read()
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["expedition_key"], []).append(r)
    return [
        {
            "key": k,
            "name": rs[0]["name"],
            "goals": len(rs),
            "open": sum(1 for r in rs if r["status"] in ("open", "partly")),
        }
        for k, rs in by.items()
        if all(r["status"] in ("done", "dropped") for r in rs)
    ]


def goal_of_line(goal_id: str | None) -> dict | None:
    """One goal row by id, or None (a queue line may carry no goal)."""
    if not goal_id:
        return None
    found = [r for r in read() if r["goal_id"] == goal_id]
    return found[0] if found else None

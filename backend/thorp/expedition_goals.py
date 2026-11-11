"""An expedition's goals as rows, and the queue's link to them (11 November, Justin: "the goals have to
have a relationship to expeditions in the db ... so we start retiring expeditions").

Two tables and one column:

- `s1.expeditions` — one row per expedition. `fleet.EXPEDITIONS` stays the source of the words (name,
  goal, fleet, preset); this table is the row a goal and a queue line can hang from, and the record of
  a declared status.
- `s1.expedition_goals` — one row a goal, keyed by the same `expedition:position` key `priorities.py`
  already ranks by (`kipling:3`), or by the bare expedition key where it states no goals (there the
  single row carries the expedition's own `goal` text). The goal's words are synced from code on every
  refresh; the **verdict** is the store's (`status`, `evidence`, `settled_at`, `words`) and a sync never
  overwrites it.
- `s2.queue_lines.goal_id` — which goal a pending line serves, so work is attributable and an
  expedition can be retired when every one of its goals is `done` or `dropped`.

A goal is retired when its verdict is `done` (`dropped` for one deliberately abandoned). That is a
claim about the ledger, so `evidence` holds where the reading is: run name, metric, value.
"""

from __future__ import annotations

from sqlalchemy import text

from thorp import fleet, store

# open: no reading yet / not started; partly: some readings, the question not settled; done: settled;
# dropped: deliberately abandoned (with a reason in `words`).
STATUSES = ("open", "partly", "done", "dropped")

_DDL = (
    "create table if not exists s1.expeditions ("
    "key text primary key, "
    "name text not null, "
    "goal text, "
    "fleet text, "
    "preset text, "
    "ship text, "
    "declared_status text, "
    "updated_at timestamptz not null default now())",
    "create table if not exists s1.expedition_goals ("
    "goal_id text primary key, "
    "expedition_key text not null references s1.expeditions(key) on delete cascade, "
    "position integer not null default 0, "
    "text text not null default '', "
    "detail text not null default '', "
    "why text not null default '', "
    "status text not null default 'open', "
    "evidence text not null default '', "
    "words text not null default '', "
    "settled_at timestamptz, "
    "updated_at timestamptz not null default now(), "
    "unique (expedition_key, position))",
    "alter table if exists s2.queue_lines add column if not exists goal_id text "
    "references s1.expedition_goals(goal_id) on delete set null",
    "create index if not exists expedition_goals_expedition on s1.expedition_goals (expedition_key)",
)


def ensure() -> None:
    with store.session() as s:
        for ddl in _DDL:
            s.execute(text(ddl))


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


def sync() -> dict[str, int]:
    """Upsert every expedition and goal from `fleet.EXPEDITIONS`; verdicts in the store are kept.

    Run after a fleet edit or on a refresh. Idempotent, and safe on a fresh store (it creates the two
    tables). A goal deleted from the code is removed unless the store has settled it."""
    ensure()
    goals = 0
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
    return {"expeditions": len(fleet.EXPEDITIONS), "goals": goals}


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


def set_verdict(goal_id: str, status: str, evidence: str = "", words: str = "") -> bool:
    """Record a goal's verdict. `done` stamps `settled_at`; anything else clears it."""
    status = status.strip().lower()
    if status not in STATUSES:
        raise ValueError(f"status must be one of {', '.join(STATUSES)}")
    ensure()
    with store.session() as s:
        r = s.execute(
            text(
                "update s1.expedition_goals set status = :status, "
                "evidence = case when :evidence = '' then evidence else :evidence end, "
                "words = case when :words = '' then words else :words end, "
                "settled_at = case when :status in ('done','dropped') then now() else null end, "
                "updated_at = now() where goal_id = :goal_id"
            ),
            {"status": status, "evidence": evidence, "words": words, "goal_id": goal_id},
        )
        return bool(r.rowcount)


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

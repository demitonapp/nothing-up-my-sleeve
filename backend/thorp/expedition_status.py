"""The expeditions' state, as a column (11 November, Justin: "let's not make it a derived state but a
postgres column").

`s1.expedition_status` holds one row per expedition: the six-state value the pages show (`at sea`,
`under way`, `in port`, `home`, `paused`, `awaiting orders`), written when the coordinator re-reads the
helm and the queue (`liberty_machine.refresh_expedition_states`) and read back by the Expeditions page. The column
is the record; the helm and the queue are only what fills it. A missing table or a missing expedition
falls back to one refresh, so a fresh store is never blank.
"""

from __future__ import annotations

from sqlalchemy import text

from thorp import store


def ensure() -> None:
    """The table is Alembic's (migration r9n2o5p8q1s4): no runtime DDL (S5 policy 'postgres', 13 November). Kept so the callers read
    as they did; it has nothing to do."""


def read() -> dict[str, str]:
    """Every stored state, key -> status."""
    ensure()
    with store.session() as s:
        return {k: v for k, v in s.execute(text("select key, status from s1.expedition_status")).all()}


def write(states: dict[str, str]) -> None:
    """Upsert the states the coordinator computed; a row nothing touched keeps its time."""
    if not states:
        return
    ensure()
    with store.session() as s:
        for key, status in states.items():
            s.execute(
                text(
                    "insert into s1.expedition_status (key, status, updated_at) values (:k, :s, now()) "
                    "on conflict (key) do update set status = excluded.status, updated_at = now()"
                ),
                {"k": key, "s": status},
            )

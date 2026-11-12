"""The tests table in Postgres (12 November, Justin: "we'll need a table for all our tests in postgres").

`s4.tests` is the catalogue of everything a model can be scored on: one row per `thorp.fleet.TRICKS` key,
with the chain and rung it belongs to, the evaluator and metric that write its reading, its threshold and
share rule, and its matched-pairs list. The fleet is the source of truth; `sync()` rewrites the table from
it, so a test added to fleet is in the store the next time the catalogue is read.

    thorp tests                  # sync and list
"""

from __future__ import annotations

from thorp import fleet, store


def desired() -> list[dict]:
    """Every test, in fleet's own order, with its chain and rung (a test may be in no chain)."""
    rungs = [r.title for r in getattr(fleet, "RUNGS", ())]
    where: dict[str, tuple[str, str]] = {}
    for chain in fleet.chains():
        for i, key in enumerate(chain):
            where[key] = (chain[-1], rungs[i] if i < len(rungs) else "")
    out = []
    for i, (key, t) in enumerate(fleet.TRICKS.items()):
        chain, rung = where.get(key, ("", ""))
        out.append(
            {
                "key": key,
                "name": t.name,
                "chain": chain,
                "rung": rung,
                "evaluator": t.evaluator,
                "metric": t.metric,
                "threshold": float(t.threshold) if t.threshold is not None else None,
                "min_score": float(t.min_score) if t.min_score is not None else None,
                "pairs": t.pairs or "",
                "about": t.about or "",
                "ordinal": i,
            }
        )
    return out


def sync() -> int:
    """Rewrite s4.tests from fleet; returns the row count."""
    from sqlalchemy import text

    rows = desired()
    with store.session() as s:
        s.execute(text("delete from s4.tests"))
        if rows:
            s.execute(
                text(
                    "insert into s4.tests (key, name, chain, rung, evaluator, metric, threshold, "
                    "min_score, pairs, about, ordinal) values (:key, :name, :chain, :rung, :evaluator, "
                    ":metric, :threshold, :min_score, :pairs, :about, :ordinal)"
                ),
                rows,
            )
    return len(rows)


def rows() -> list[dict]:
    """The table, in its ordinal order, synced first if it is empty."""
    from sqlalchemy import text

    with store.session() as s:
        got = s.execute(
            text(
                "select key, name, chain, rung, evaluator, metric, threshold, min_score, pairs, about, ordinal "
                "from s4.tests order by ordinal"
            )
        ).mappings().all()
    if not got:
        sync()
        return rows()
    return [dict(r) for r in got]


def _score(model: str) -> dict:
    from thorp.viable.s4_intelligence import readings

    grades = readings.chain_grades()
    return (grades.get("models") or {}).get(model) or {}


def scored(model: str) -> dict[str, dict]:
    """Each test this model has a reading for, and the reading itself (the chain-grades shape)."""
    return _score(model)


def for_model(model: str) -> list[dict]:
    """The catalogue with what this model scored on each test, if anything."""
    got = _score(model)
    out = []
    for row in rows():
        x = got.get(row["key"])
        out.append(
            {
                **row,
                "scored": bool(x),
                "lift": None if not x else x.get("lift"),
                "score": None if not x else x.get("score"),
                "performed": bool(x and x.get("performed")),
            }
        )
    return out

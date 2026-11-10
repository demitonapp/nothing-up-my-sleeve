"""S4: the readings of outside models, in the store (s4.outside_readings; was data/compare/*.json). A reading keeps
the name its file had (`deck-EleutherAI--pythia-14m`, `chain-grades`, `knockout-microsoft__phi-2`), so every
reader finds it as before: `get(name)`, `glob(pattern)`, `put(name, reading)`.

A non-finite number (NaN, infinity) cannot be held in JSON and is kept as null: no reading.
"""

from __future__ import annotations

import fnmatch
import json
import math

from thorp import store

KINDS = ("chain-grades", "knockout-deck", "knockout", "deck", "logic", "math500")


def kind_of(name: str) -> tuple[str, str | None]:
    """What a reading is, and of which model, from its name."""
    if name == "chain-grades":
        return "chain-grades", None
    if name.startswith("math500-"):
        return "math500", name[len("math500-"):].replace("--", "/").replace("__", "/")
    for k in KINDS[1:]:
        if name.startswith(k + "-"):
            return k, name[len(k) + 1:].replace("--", "/").replace("__", "/")
    if "__" in name:  # <model>__<list>[__<clean>]: a book list scored on an outside model
        return "scored", name.split("__")[0].replace("--", "/")
    return "other", None


def _finite(x):
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, dict):
        return {k: _finite(v) for k, v in x.items()}
    if isinstance(x, list | tuple):
        return [_finite(v) for v in x]
    return x


def put(name: str, reading: dict | list) -> None:
    """A reading kept (replacing one of the same name)."""
    from thorp.viable.records import OutsideReading

    kind, model = kind_of(name)
    doc = _finite(json.loads(json.dumps(reading, default=float)))
    with store.session() as s:
        own = reading.get("model") if isinstance(reading, dict) else None  # a list of runs has none
        s.merge(OutsideReading(name=name, kind=kind, model=own or model, reading=doc))


def get(name: str) -> dict | None:
    from thorp.viable.records import OutsideReading

    with store.session() as s:
        r = s.get(OutsideReading, name)
        return r.reading if r else None


def glob(pattern: str) -> list[tuple[str, dict]]:
    """Every reading whose name matches the pattern (as the files were globbed: `knockout-*`), by name."""
    from sqlalchemy import select

    from thorp.viable.records import OutsideReading

    with store.session() as s:
        rows = s.execute(select(OutsideReading.name, OutsideReading.reading).order_by(OutsideReading.name)).all()
    return [(n, r) for n, r in rows if fnmatch.fnmatchcase(n, pattern)]


def chain_grades() -> dict:
    """The chain grades' models ({model: grades}; scripts/grade_chains.py), {} before any were graded."""
    return (get("chain-grades") or {}).get("models", {})

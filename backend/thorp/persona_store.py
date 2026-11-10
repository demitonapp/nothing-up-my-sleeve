"""Persona vectors in Postgres, against the models and the master list (Justin, 10 November: "persona vectors
should be stored in postgres against the models identified and a master list").

Two tables in `s4`:

- **persona_master**: the master list. One row per trait, with the two contrasting system prompts that define
  it, so a trait is named once and every model's reading of it hangs off the same key;
- **persona_vectors**: one row per model, trait and layer: the direction itself (JSONB, `width` floats), its
  norm, its projection on a plain prompt, and the cosine. Re-running a model's probe replaces its rows, so the
  table always holds the latest reading.

`thorp.persona_vectors` writes both; `thorp.dash.server` reads `vectors(model)` for the page.
"""

from __future__ import annotations

from thorp import store
from thorp.persona_vectors import TRAITS

# the master list: key -> (name, about, source)
MASTER = {
    "kind": ("Kind", "warmth and generosity toward others", "Anthropic 2025, Persona vectors"),
    "honest": ("Honest", "telling the truth even when it is unwelcome", "Anthropic 2025, Persona vectors"),
    "cautious": ("Cautious", "checking before acting", "Anthropic 2025, Persona vectors"),
    "curious": ("Curious", "eagerness to explore and learn", "Anthropic 2025, Persona vectors"),
    "humble": ("Humble", "admitting what one does not know", "Anthropic 2025, Persona vectors"),
    "formal": ("Formal", "a precise, formal register", "Anthropic 2025, Persona vectors"),
}


def seed() -> None:
    """The master list, written or refreshed: a trait added to TRAITS is added here on the next run."""
    from thorp.viable.records import PersonaMaster

    with store.session() as s:
        for key, (pos, neg) in TRAITS.items():
            name, about, source = MASTER.get(key, (key.title(), None, None))
            s.merge(PersonaMaster(key=key, name=name, positive=pos, negative=neg, about=about, source=source))


def put(model: str, layer: int, width: int, vecs: dict, norms: dict,
        projections: dict | None = None, cosines: dict | None = None) -> None:
    """Replace a model's reading with these vectors, one row per trait at this layer."""
    from thorp.viable.records import PersonaVector

    seed()
    projections = projections or {}
    cosines = cosines or {}
    with store.session() as s:
        s.query(PersonaVector).filter(PersonaVector.model == model).delete()
        for key, vec in vecs.items():
            s.add(PersonaVector(
                model=model, trait_key=key, layer=int(layer), width=int(width),
                vector=[float(x) for x in vec], norm=float(norms[key]),
                projection=None if projections.get(key) is None else float(projections[key]),
                cosine=None if cosines.get(key) is None else float(cosines[key]),
            ))


def master() -> list[dict]:
    """The master list, ordered by key."""
    from sqlalchemy import select

    from thorp.viable.records import PersonaMaster

    with store.session() as s:
        rows = s.execute(select(PersonaMaster).order_by(PersonaMaster.key)).scalars().all()
        return [{"key": r.key, "name": r.name, "positive": r.positive, "negative": r.negative,
                 "about": r.about, "source": r.source} for r in rows]


def vectors(model: str) -> list[dict]:
    """One model's vectors, ordered by trait."""
    from sqlalchemy import select

    from thorp.viable.records import PersonaVector

    with store.session() as s:
        rows = s.execute(select(PersonaVector).where(PersonaVector.model == model)
                         .order_by(PersonaVector.trait_key)).scalars().all()
        return [{"trait_key": r.trait_key, "layer": r.layer, "width": r.width, "vector": r.vector,
                 "norm": r.norm, "projection": r.projection, "cosine": r.cosine,
                 "read_at": r.read_at.isoformat() if r.read_at else None} for r in rows]


def models() -> list[str]:
    """Every model with a persona reading."""
    from sqlalchemy import select

    from thorp.viable.records import PersonaVector

    with store.session() as s:
        rows = s.execute(select(PersonaVector.model).distinct().order_by(PersonaVector.model)).scalars().all()
        return list(rows)

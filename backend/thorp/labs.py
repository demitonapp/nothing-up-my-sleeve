"""The labs: who made each outside model, and what each lab's models do best and worst on Nothing up my sleeve's tests.

A **lab** (`Lab`) is the maker of a family of outside models (EleutherAI makes Pythia, Alibaba Qwen,
and so on), matched by the model's family name, since many checkpoints are re-hosted under
`mlx-community/` and the repo owner does not say who made them.

The houses are rows in Postgres (`s4.labs`, `thorp/lab_store.py`), not lists in this file (12 November,
Justin: "labs should be in postgres not hardcoded"): the profile, the funding and the rounds beside each
house come from the store, and `thorp/labs.py` is the shape the dashboard, the leaderboard and the chat
read.

A lab's **best and worst** are its models' readings on every rung of the four chains
(the chain grades, s4.outside_readings), each set against the field: the other labs' models on the same test.
A reading's **standing** is its lift less the field's median, over the field's spread (its standard
deviation), so a test where every model scores 2.0 does not crowd out a test where the field scores
0.1; the five highest standings are the lab's best, the five lowest its worst.

    uv run python -m thorp.labs eleutherai     # one lab's best and worst, in plain text
"""

from __future__ import annotations

import re
import statistics
import sys
from dataclasses import dataclass, field

from thorp import fleet, lab_store


@dataclass(frozen=True)
class Lab:
    key: str  # the address: #/leaderboard/lab/<key>
    name: str
    families: tuple[str, ...]  # the model families it makes, as they appear in model names
    url: str = ""  # its model organisation
    short: str = ""  # the name on the card, where it is longer than the lab key's name
    country: str = ""  # the flag key in frontend/public/flags
    country_name: str = ""
    hq: str = ""
    founded: str = ""
    site: str = ""  # the house's own door; url above stays its model org
    blurb: str = ""  # one sentence on what the house makes, in this world
    flagship: tuple[str, ...] = ()  # the models it had shipped by the as-of date
    focus: str = "research"  # frontier, open fleet, enterprise, agents or research
    open_weights: bool = True  # whether it ships any open-weight line
    listed: bool = True  # on the Labs page, or only named under it
    category: str = "lab"  # lab or research: which view of the Reach it lives in
    kind: str = ""  # company, university group, collective, national infrastructure
    funding: dict = field(default_factory=dict)  # the split, its note and the rounds
    gov: dict | None = None  # Washington, for the American houses
    description: str = ""  # the house page's longer paragraph
    purpose: str = ""  # what it is for

    def makes(self, model: str) -> bool:
        return any(re.search(f, model, re.I) for f in self.families)

    @property
    def door(self) -> str:
        """The link a card opens when it is not a lab page."""
        return self.site or self.url


AS_OF = "2026-11-12"
TOP = 5

# The fallback funding shape, for a house the store has no split for: the Reach says an estimate from public
# reporting, not an audited cap table.
_PRIVATE = {
    "government": 0,
    "private": 100,
    "kind": "private",
    "note": "A private company: equity, debt and revenue, with no direct government equity or grant funding. Public-sector work is a customer, not a funder.",
    "basis": "Public reporting and company statements to 12 November 2026; an estimate, not an audited cap table.",
    "rounds": [],
}


def _lab(row: dict) -> Lab:
    return Lab(
        key=row["key"],
        name=row["name"],
        families=tuple(row["families"]),
        url=row["url"],
        short=row["short"],
        country=row["country"],
        country_name=row["country_name"],
        hq=row["hq"],
        founded=row["founded"],
        site=row["site"],
        blurb=row["blurb"],
        flagship=tuple(row["flagship"]),
        focus=row["focus"],
        open_weights=row["open_weights"],
        listed=row["listed"],
        category=row["category"],
        kind=row["kind"],
        funding=dict(row["funding"] or {}),
        gov=row["gov"],
        description=row["description"],
        purpose=row["purpose"],
    )


def all() -> tuple[Lab, ...]:
    """Every house in the Reach, in the store's order (the Labs page's, then the leaderboard-only ones)."""
    return tuple(_lab(row) for row in lab_store.labs())


def listed() -> tuple[Lab, ...]:
    """The houses the Reach shows: the ones with a card and a page of their own."""
    return tuple(lab for lab in all() if lab.listed)


def of_category(category: str) -> tuple[Lab, ...]:
    """The listed houses of one view: `lab` (the Labs page) or `research` (the Research page)."""
    return tuple(lab for lab in listed() if lab.category == category)


def get(key: str) -> Lab | None:
    return next((lab for lab in all() if lab.key == key.lower()), None)


def lab_of(model: str) -> Lab | None:
    return next((lab for lab in all() if lab.makes(model)), None)


def _grades() -> dict:
    from thorp.viable.s4_intelligence import readings

    return readings.chain_grades()


def _label(model: str) -> str:
    return fleet.COMPETITORS.get(model, (model.split("/")[-1], 0))[0]


def readings(models: dict | None = None) -> list[dict]:
    """Every (model, test) reading of a lab's model on a rung of the four chains."""
    models = _grades() if models is None else models
    names = {k: t.name for k, t in fleet.TRICKS.items()}
    rungs = [r.title for r in getattr(fleet, "RUNGS", ())]
    where = {}  # test -> (its chain's name, its rung's title)
    for c in fleet.chains():
        for i, k in enumerate(c):
            where[k] = (names.get(c[-1], c[-1]), rungs[i] if i < len(rungs) else None)
    out = []
    for model, v in models.items():
        lab = lab_of(model)
        if not lab:
            continue
        for test, x in v.items():
            if test not in where or not isinstance(x, dict) or x.get("lift") is None:
                continue
            out.append(
                {
                    "lab": lab.key,
                    "model": model,
                    "label": _label(model),
                    "test": test,
                    "name": names.get(test, test),
                    "chain": where[test][0],
                    "rung": where[test][1],
                    "lift": x["lift"],
                    "score": x.get("score"),
                    "performed": bool(x.get("performed")),
                }
            )
    return out


def standings(lab: Lab, rows: list[dict] | None = None) -> list[dict]:
    """The lab's readings, each with its standing against the other labs' models on the same test."""
    rows = readings() if rows is None else rows
    field: dict[str, list[float]] = {}
    for r in rows:
        if r["lab"] != lab.key:
            field.setdefault(r["test"], []).append(r["lift"])
    out = []
    for r in rows:
        f = field.get(r["test"], [])
        if r["lab"] != lab.key or len(f) < 2:
            continue
        med, sd = statistics.median(f), statistics.pstdev(f)
        out.append(
            {
                **r,
                "field_median": med,
                "field_n": len(f),
                "beats": sum(x < r["lift"] for x in f),
                "standing": (r["lift"] - med) / sd if sd > 0 else 0.0,
            }
        )
    return sorted(out, key=lambda r: -r["standing"])


def _profile(lab: Lab, rank: int | None = None) -> dict:
    """The card's facts, shared by the Labs index and one lab's own page. The row carries the house's
    description and purpose, so the card stays one line and the page can say more."""
    return {
        "key": lab.key,
        "name": lab.name,
        "short": lab.short or lab.name,
        "rank": rank,
        "url": lab.url,
        "site": lab.door,
        "country": lab.country,
        "country_name": lab.country_name,
        "hq": lab.hq,
        "founded": lab.founded,
        "blurb": lab.blurb,
        "open": lab.open_weights,
        "category": lab.category,
        "kind": lab.kind,
        "focus": lab.focus,
        "funding": lab.funding or _PRIVATE,
        "gov": lab.gov if lab.country == "us" else None,
        "description": lab.description,
        "purpose": lab.purpose,
        "flagship": list(lab.flagship),
        "art": f"lab-{lab.key}" if lab.listed else "",
        "families": list(lab.families),
    }


def houses() -> dict:
    """The Labs page (12 November 2026): the houses, each with its profile and what the Reach holds of
    it, then the other houses whose models the leaderboard keeps (EleutherAI's Pythias, Hugging Face's
    SmolLMs). The facts are the house's releases by AS_OF; the readings are the store's, as every lab page
    reads them."""
    graded = _grades()
    rows = readings(graded)
    out = []
    for rank, lab in enumerate(listed(), 1):
        mine = [r for r in rows if r["lab"] == lab.key]
        read = sorted({r["label"] for r in mine})
        out.append({
            **_profile(lab, rank),
            "readings": len(mine),
            "models_read": len(read),
            "read": read,
        })
    next_houses = []
    for lab in all():
        if lab.listed:
            continue
        mine = [r for r in rows if r["lab"] == lab.key]
        next_houses.append({
            **_profile(lab),
            "readings": len(mine),
            "models_read": len({r["label"] for r in mine}),
        })
    return {
        "as_of": AS_OF,
        "as_of_label": "12 November 2026",
        "houses": out,
        "next": next_houses,
    }


def payload(key: str) -> dict:
    lab = get(key)
    if not lab:
        raise LookupError(f"no lab {key}")
    models = _grades()
    s = standings(lab, readings(models))
    mine = [m for m in models if lab.makes(m)]
    try:  # the reference ladder's sizes (the competitors carry theirs in fleet.COMPETITORS)
        from thorp.smoking_qwen import REFERENCE_PARAMS as sizes
    except ImportError:
        sizes = {}
    # Every ship of this house the Reach knows, read or not: the foreign registry is the list the harbour
    # draws, so the lab page can show the whole fleet, not only the models with a chain reading.
    from thorp import foreign as foreign_registry

    reach_ships, seen = [], set()
    for x in foreign_registry.models():
        k = x.get("key")
        if x.get("lab") != lab.key or not k or k in seen:
            continue
        seen.add(k)
        reach_ships.append({
            "key": k,
            "model": x.get("model"),
            "label": x.get("label") or _label(x.get("model") or k),
            "params": x.get("params"),
            "read": bool(x.get("read")),
            "chained": bool(x.get("chained")),
        })
    rank = next((i for i, x in enumerate(listed(), 1) if x.key == lab.key), None)
    return {
        **_profile(lab, rank),
        "fleet": reach_ships,
        "models": [
            {
                "model": m,
                "label": _label(m),
                "params": fleet.COMPETITORS.get(m, (None, None))[1] or sizes.get(m),
                "competitor": m in fleet.COMPETITORS,
                "ladder": m in fleet.REFERENCE_LADDER,
            }
            for m in mine
        ],
        "readings": len(s),
        "best": s[:TOP],
        "worst": s[::-1][:TOP] if len(s) > TOP else [],
        "labs": [{"key": x.key, "name": x.name} for x in all()],
    }


def main() -> None:
    d = payload(sys.argv[1] if len(sys.argv) > 1 else "eleutherai")
    print(f"{d['name']}: {', '.join(m['label'] for m in d['models'])} ({d['readings']} readings)")
    for title, rows in (("best", d["best"]), ("worst", d["worst"])):
        print(f"\n{title}")
        for r in rows:
            print(
                f"  {r['standing']:+5.2f}σ  {r['label']:<18} {r['name']:<24} lift {r['lift']:+.3f}"
                f" (field {r['field_median']:+.3f})"
            )


if __name__ == "__main__":
    main()

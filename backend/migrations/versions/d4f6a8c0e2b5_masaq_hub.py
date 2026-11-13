"""Masaq' Hub: the houses of the Reach that belong to no one country

13 November (Justin: "for companies like hugging face that have numerous companies in different jurisdictions
are it's own separate categorization within masaq' reach", then "not even labs though. because hugging face is
something else entirely"; he chose the name Masaq' Hub, and the cross-border collectives as its other members).
In Look to Windward, Hub is the Mind that runs Masaq' Orbital; Hugging Face calls its platform the Hub.

A Hub house is `category = 'hub'` and `country = 'hub'`: the country column is the house's address segment and
flag key (`/orbitals/masaq/hub/<key>`, `frontend/public/flags/hub.svg`), and its `country_name` says which
jurisdictions it spans. The Countries view leaves the Hub out; the Hub view shows only it.

- `huggingface`: was the one leaderboard-only row, with no country or profile. It is listed now, as a platform:
  founded in New York in 2016 by three French founders, with its science team largely in Paris.
- `bigscience`: new. The year-long research workshop (May 2021 to May 2022) that Hugging Face coordinated with
  more than a thousand researchers from some sixty countries; it built BLOOM, released in July 2022 under the
  BigScience RAIL licence, and was trained on France's Jean Zay supercomputer on a public compute grant.
- `masakhane`: moves out of South Africa's research houses. It is a pan-African collective, not a South
  African one.

Sources: arXiv 2211.05100 (the BLOOM paper: authors, languages, licence, Jean Zay), huggingface.co/bigscience/bloom,
masakhane.io, and Hugging Face's own about page and press for the founding.

Revision ID: d4f6a8c0e2b5
Revises: c3e5a7b9d1f4
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "d4f6a8c0e2b5"
down_revision = "c3e5a7b9d1f4"
branch_labels = None
depends_on = None

JSON_COLS = ("families", "orgs", "flagship", "funding")

HUGGINGFACE = {
    "listed": True,
    "category": "hub",
    "kind": "platform",
    "short": "Hugging Face",
    "families": ["smollm"],
    "orgs": ["HuggingFaceTB", "HuggingFaceFW"],
    "url": "https://huggingface.co/HuggingFaceTB",
    "site": "https://huggingface.co",
    "country": "hub",
    "country_name": "United States and France",
    "hq": "New York and Paris",
    "founded": "2016",
    "blurb": "the harbour itself: Hugging Face, the Hub where nearly every house in the Reach moors its open "
    "weights, and the builder of the small SmolLM fleet.",
    "description": "Hugging Face was founded in New York in 2016 by three French founders, Clément Delangue, Julien "
    "Chaumond and Thomas Wolf, and keeps much of its science team in Paris. It is not a lab in the Reach's sense: "
    "its Hub is where the other houses publish their weights and datasets, and its Transformers library is how "
    "most of the trade loads them. It also builds: the SmolLM models, small open models published with their "
    "training data and recipes, and the FineWeb datasets. It coordinated the BigScience workshop that built BLOOM.",
    "purpose": "to keep the open models, datasets and tools of the whole trade in one place anyone can reach.",
    "flagship": ["SmolLM3", "SmolLM2", "FineWeb"],
    "focus": "open fleet",
    "open_weights": True,
    "funding": {
        "government": 0,
        "private": 100,
        "kind": "private company",
        "note": "A venture-backed private company. Its 2023 Series D was led by Salesforce Ventures, with Google, "
        "Amazon, Nvidia, Intel, AMD, Qualcomm and IBM among the investors.",
        "basis": "Public reporting to 13 November 2026; an estimate, not an audited cap table.",
        "rounds": [
            {"date": "2023-08", "round": "Series D", "amount": "$235M", "valuation": "$4.5B",
             "investors": "Salesforce Ventures (lead), Google, Amazon, Nvidia, Intel, AMD, Qualcomm, IBM"},
        ],
    },
}
HUGGINGFACE_OLD = {
    "listed": False, "category": "lab", "kind": "company", "short": "Hugging Face", "families": ["smollm"],
    "orgs": [], "url": "https://huggingface.co/HuggingFaceTB", "site": "", "country": "", "country_name": "",
    "hq": "", "founded": "", "blurb": "", "description": "", "purpose": "", "flagship": [], "focus": "research",
    "open_weights": True, "funding": {},
}

BIGSCIENCE = {
    "key": "bigscience",
    "ordinal": 48,
    "listed": True,
    "category": "hub",
    "kind": "collective",
    "name": "BigScience",
    "short": "BigScience · BLOOM",
    "families": ["bloom", "bigscience"],
    "orgs": ["bigscience"],
    "url": "https://huggingface.co/bigscience",
    "site": "https://bigscience.huggingface.co",
    "country": "hub",
    "country_name": "some sixty countries",
    "hq": "a year-long workshop, run from Paris",
    "founded": "2021",
    "blurb": "the thousand-hands house: BigScience, the open workshop of more than a thousand researchers that "
    "built BLOOM, a 176-billion-parameter model for 46 languages.",
    "description": "BigScience was a one-year research workshop, from May 2021 to May 2022, coordinated by Hugging "
    "Face with more than a thousand researchers from some sixty countries and over 250 institutions. It built "
    "the ROOTS corpus and BLOOM, a 176-billion-parameter model for 46 natural languages and 13 programming "
    "languages, released in July 2022 under the BigScience RAIL licence (open weights, with use restrictions). "
    "BLOOM was trained on the Jean Zay supercomputer near Paris on a French public compute grant.",
    "purpose": "to show that a large language model could be built in the open, by many hands, for many languages.",
    "flagship": ["BLOOM", "BLOOMZ", "ROOTS"],
    "focus": "research",
    "open_weights": True,
    "funding": {
        "government": 0,
        "private": 0,
        "kind": "workshop",
        "note": "A research workshop, not a company: its compute was a French public grant on Jean Zay (GENCI and "
        "IDRIS), and its people were volunteers and the staff of their own institutions.",
        "basis": "The BLOOM paper (arXiv 2211.05100); not a cap table.",
        "rounds": [],
    },
}

MASAKHANE = {"category": "hub", "country": "hub", "country_name": "across Africa"}
MASAKHANE_OLD = {"category": "research", "country": "za", "country_name": "Pan-African · South Africa"}


def _set(key: str, values: dict) -> None:
    sets = ", ".join(f"{k} = CAST(:{k} AS jsonb)" if k in JSON_COLS else f"{k} = :{k}" for k in values)
    params = {k: json.dumps(v) if k in JSON_COLS else v for k, v in values.items()}
    op.get_bind().execute(sa.text(f"UPDATE s4.labs SET {sets} WHERE key = :_key"), {**params, "_key": key})


def upgrade() -> None:
    _set("huggingface", HUGGINGFACE)
    _set("masakhane", MASAKHANE)
    cols = list(BIGSCIENCE)
    values = ", ".join(f"CAST(:{k} AS jsonb)" if k in JSON_COLS else f":{k}" for k in cols)
    params = {k: json.dumps(v) if k in JSON_COLS else v for k, v in BIGSCIENCE.items()}
    op.get_bind().execute(
        sa.text(f"INSERT INTO s4.labs ({', '.join(cols)}) VALUES ({values}) ON CONFLICT (key) DO NOTHING"), params
    )


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM s4.labs WHERE key = 'bigscience'"))
    _set("masakhane", MASAKHANE_OLD)
    _set("huggingface", HUGGINGFACE_OLD)

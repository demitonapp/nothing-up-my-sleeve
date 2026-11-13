"""NILC is not Tucano's house: Tucano comes from the University of Bonn's Polygl0t project

13 November, found while fact-checking the country notes (Justin: "Yes, fix it"). The research house seeded as
`nilc` said NILC, the São Carlos group, "built Tucano". It did not: the Tucano papers (arXiv 2411.07854 and
2603.03543) and the University of Bonn's pages name the Polygl0t project there (Nicholas Kluge Corrêa and
colleagues), supported by Germany's BMBF and North Rhine-Westphalia's MWK. No source ties NILC to Tucano.

NILC is real and stays, described for what it is: the Interinstitutional Center for Computational Linguistics,
created in 1993 (not 1996) around a Portuguese grammar-checker project at the University of São Paulo's
institute in São Carlos, with researchers from USP, UFSCar and UNESP, building the resources and tools of
Brazilian Portuguese. It is a research group, not a model builder, so it loses the `tucano` family, the
`TucanoBR` Hub organisation and the flagship; its own Hub organisation is `nilc-nlp`. Tucano's models now
belong to no house in the Reach (a Bonn house, in Germany, is a separate decision).

Revision ID: d5f7a9c1e3b4
Revises: c4e8f1a2b6d3
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "d5f7a9c1e3b4"
down_revision = "c4e8f1a2b6d3"
branch_labels = None
depends_on = None

NEW = {
    "short": "NILC",
    "families": ["nilc"],
    "orgs": ["nilc-nlp"],
    "founded": "1993",
    "blurb": "the Portuguese-language house: NILC, the São Carlos group that has built the tools and resources of "
    "Brazilian Portuguese language processing since 1993.",
    "description": "NILC is the Interinstitutional Center for Computational Linguistics, based at the University of "
    "São Paulo's institute in São Carlos, with researchers from USP, UFSCar and UNESP. Created in 1993 around a "
    "Portuguese grammar-checker project, it builds the resources, tools and applications for processing Brazilian "
    "Portuguese. It is a research group, not a model builder: the open Portuguese models called Tucano come from the "
    "University of Bonn's Polygl0t project, not from NILC.",
    "purpose": "to build the language resources and tools that Brazilian Portuguese models draw on.",
    "flagship": [],
}
OLD = {
    "short": "NILC · Tucano",
    "families": ["tucano", "nilc"],
    "orgs": ["TucanoBR"],
    "founded": "1996",
    "blurb": "the toucan house: NILC, the São Carlos group that built Tucano — an open Portuguese model for Brazil's "
    "own texts.",
    "description": "NILC is the Interinstitutional Center for Computational Linguistics at the University of São "
    "Paulo, in São Carlos. Its Tucano line is a family of open Portuguese language models trained on Brazilian "
    "texts, built as a public alternative to English-first models.",
    "purpose": "to keep a Portuguese-first open model in Brazilian hands.",
    "flagship": ["Tucano"],
}
JSON_COLS = ("families", "orgs", "flagship")


def _set(values: dict) -> None:
    sets = ", ".join(f"{k} = CAST(:{k} AS jsonb)" if k in JSON_COLS else f"{k} = :{k}" for k in values)
    params = {k: json.dumps(v) if k in JSON_COLS else v for k, v in values.items()}
    op.get_bind().execute(sa.text(f"UPDATE s4.labs SET {sets} WHERE key = 'nilc'"), params)


def upgrade() -> None:
    _set(NEW)


def downgrade() -> None:
    _set(OLD)

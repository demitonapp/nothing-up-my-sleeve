"""Nothing up my sleeve joins Australia's labs in Masaq' Reach

13 November (Justin: "can you add Nothing Up My Sleeve to http://localhost:4321/orbitals/masaq/au/labs it's not formed yet,
but it will be a non profit"). One row in `s4.labs`: an Australian lab whose kind says it is a non-profit not yet formed.

Its families are empty on purpose: its ships are built and sailed in the Demiton orbital, and the Reach reads outside
models, so no model of ours is matched to this house or counted among the Reach's ships. Its door is the project's public
repository.

Revision ID: e5a7c9d1f3b6
Revises: d4f6a8c0e2b5
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op

revision = "e5a7c9d1f3b6"
down_revision = "d4f6a8c0e2b5"
branch_labels = None
depends_on = None

JSON_COLS = ("families", "orgs", "flagship", "funding")

ROW = {
    "key": "nothing-up-my-sleeve",
    "ordinal": 49,
    "listed": True,
    "category": "lab",
    "kind": "nonprofit (not yet formed)",
    "name": "Nothing up my sleeve",
    "short": "Nothing up my sleeve",
    "families": [],
    "orgs": [],
    "url": "https://github.com/demitonapp/nothing-up-my-sleeve",
    "site": "https://github.com/demitonapp/nothing-up-my-sleeve",
    "country": "au",
    "country_name": "Australia",
    "hq": "Australia",
    "founded": "2026",
    "blurb": "our own house: Nothing up my sleeve, the small-model project behind this site, to become an Australian "
    "non-profit; its fleet is built and sailed in the Demiton orbital.",
    "description": "Nothing up my sleeve is the project this site belongs to: a fleet of small GPTs trained from scratch "
    "on a ladder of sizes, with every step shown. It is not yet formed as an organisation; it will be a non-profit. It "
    "stands here among Australia's labs, but its ships are built and sailed in the Demiton orbital, not read in the Reach.",
    "purpose": "to find the smallest kernel of English a model can hold, and to keep it accessible to all.",
    "flagship": ["9m · chat and tools"],
    "focus": "open fleet",
    "open_weights": True,
    "funding": {
        "government": 0,
        "private": 0,  # not formed: neither side has put money in, so the bar is drawn empty
        "kind": "not yet formed",
        "note": "Not yet formed as an organisation: no cap table and no funding rounds. It will be a non-profit.",
        "basis": "Justin, 13 November 2026.",
        "rounds": [],
    },
}


def upgrade() -> None:
    cols = list(ROW)
    values = ", ".join(f"CAST(:{k} AS jsonb)" if k in JSON_COLS else f":{k}" for k in cols)
    params = {k: json.dumps(v) if k in JSON_COLS else v for k, v in ROW.items()}
    op.get_bind().execute(
        sa.text(f"INSERT INTO s4.labs ({', '.join(cols)}) VALUES ({values}) ON CONFLICT (key) DO NOTHING"), params
    )


def downgrade() -> None:
    op.get_bind().execute(sa.text("DELETE FROM s4.labs WHERE key = 'nothing-up-my-sleeve'"))

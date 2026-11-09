"""the 100m is Invention

The 100m's name, role and the quote on her page (Justin, 8 November: "i just want to rename the 100m ship
and then also have my quote appear on her in some form"). Her scored tests and metrics are left as they are:
the Medusa is not encoded yet.

Revision ID: d4e8f1a2b6c9
Revises: f3a7c2d9e1b4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d4e8f1a2b6c9"
down_revision = "f3a7c2d9e1b4"
branch_labels = None
depends_on = None

ROLE = "The first inventor: what a 100m can find that a larger ship cannot, on a budget that forbids scaling"
OVERVIEW = (
    "\u201cNecessity is the mother of all invention, tedium is the step mother of invention, and being "
    "broke is the whore of invention.\u201d \u2014 Justin\n\n"
    "The Invention is the 100m: the first ship asked to invent rather than explore. Necessity sets the "
    "question, tedium is the reading it must do, and being broke is the budget that forbids scaling. "
    "What can it find that a larger ship cannot?"
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            "update s1.sizes set name=:name, role=:role, overview=:overview where preset='100m'"
        ),
        {"name": "Invention", "role": ROLE, "overview": OVERVIEW},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("update s1.sizes set name='The explorer', role=:role, overview='' where preset='100m'"),
        {"role": "The first true explorer: the Origin and Leonardo tests, does it bet on an idea before the world did?"},
    )

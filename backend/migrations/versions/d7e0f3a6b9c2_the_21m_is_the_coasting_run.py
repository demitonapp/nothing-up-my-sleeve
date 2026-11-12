"""the 21m is the coasting run

The 21m's name, with the 9m's (Justin, 12 November: "Yes, rename both"). After the sea trial a proven ship
makes her first working trips: port to port along the coast with a cargo aboard and the land always in sight.
That is the 21m's place on the ladder: it is the first size given something to carry (grammar and a held
style, and the first of the logic questions), and it comes before the 50m, the crossing, where a ship first
leaves sight of land.

Its objective is unchanged: grammar and style. The hull is the 24-layer 21m. The class slug becomes
`coasting-run`; `stylist` stays as an address that forwards (CLASS_RENAMES, server.py and router.ts), and the
tests and heads that name their class "stylist" still find the 21m through it.

Revision ID: d7e0f3a6b9c2
Revises: c6d9e2f5a8b1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d7e0f3a6b9c2"
down_revision = "c6d9e2f5a8b1"
branch_labels = None
depends_on = None

NAME = "The coasting run"
ROLE = (
    "Primary objective: grammar and style (agreement, whole sentences, a register held through a passage). "
    "It is the coasting run: a proven ship's first working trips, port to port with a cargo aboard and the "
    "land in sight, before the 50m's crossing"
)
OVERVIEW = (
    "Twenty-four layers of 192, eight heads of 24. It is the coasting run: a proven ship's first working "
    "trips, port to port along the coast with a cargo aboard and the land always in sight. The 21m's cargo "
    "is what lies above the word: subject and verb agree across a clause, sentences close, and a passage "
    "keeps one voice (King James, Victorian novel, Greek translation). The logic questions begin here, and "
    "it is the size for the Leonardo pilot's second step if 9m shows nothing. What it carries safely along "
    "the coast, the 50m takes out of sight of land."
)
OLD_NAME = "The stylist"
OLD_ROLE = "Grammar and style: agreement, whole sentences, a register held through a passage"
OLD_OVERVIEW = (
    "Above the word: subject and verb agree across a clause, sentences close, and a passage keeps one voice "
    "(King James, Victorian novel, Greek translation). Also the size for the Leonardo pilot's second step if "
    "9m shows nothing."
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("update s1.sizes set name=:name, role=:role, overview=:overview where preset='21m'"),
        {"name": NAME, "role": ROLE, "overview": OVERVIEW},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("update s1.sizes set name=:name, role=:role, overview=:overview where preset='21m'"),
        {"name": OLD_NAME, "role": OLD_ROLE, "overview": OLD_OVERVIEW},
    )

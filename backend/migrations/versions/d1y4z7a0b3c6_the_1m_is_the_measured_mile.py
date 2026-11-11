"""the 1m is the measured mile

The 1m's name, to follow the 300k's (Justin, 11 November, night: "Also what should the 1m be?"; then "Yes,
rename 1m"). The 300k is the towing tank, where a combination is changed and read at model scale. The
measured mile is what comes after a tank: the marked stretch of open water where a real hull is timed between
two posts, to check what the tank predicted. That is the 1m's place on the ladder: a finding from the 300k is
run again here, and a comparison already made at the 9m is re-run here before its ranking is trusted.

Its objective is unchanged: De Morgan's maths book. The hull is the 12-layer 1m (the description before still
said 4 layers of 128, the shape before the deep ladder). The class slug becomes `measured-mile`; `augustus`,
`pilot` and `proxy` stay as addresses that forward (CLASS_RENAMES, server.py and router.ts). Augustus the
position at the 1m, and his plate, are not touched.

Revision ID: d1y4z7a0b3c6
Revises: c0x3y6z9a2b5
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "d1y4z7a0b3c6"
down_revision = "c0x3y6z9a2b5"
branch_labels = None
depends_on = None

NAME = "The measured mile"
ROLE = (
    "Primary objective: pass De Morgan. All nine chapters of the maths book (Augustus De Morgan, Elements of "
    "Arithmetic, his Book I in his order); and it is the measured mile: what the towing tank found is run "
    "again here at the first larger scale, and comparisons already made at the 9m are re-run here, so its "
    "ranking can be trusted before it scouts data questions for the bigger ships"
)
OVERVIEW = (
    "Twelve layers of 80, four heads of 20, vocabulary 4,096: about 1.3M parameters. It is the yard's "
    "measured mile: the marked stretch of open water where a real hull is timed between two posts, to check "
    "what the tank predicted. A finding from the 300k is tried again here before it is trusted, and a "
    "comparison already made at the 9m is re-run here first; if its ranking agrees, it explores and the 9m "
    "confirms the winners. Scored on the maths book, chapter by chapter, with the Forgotten Tomes beside."
)
OLD_NAME = "Augustus"
OLD_ROLE = (
    "Primary objective: pass De Morgan. All nine chapters of the maths book (Augustus De Morgan, Elements of "
    "Arithmetic, his Book I in his order); and still the harbour pilot that scouts data questions fast for "
    "the bigger ships"
)
OLD_OVERVIEW = (
    "4 layers x 128, vocabulary 4,096, about 1.4M parameters. Scored only on the Forgotten Tomes, once at "
    "the end. First it re-runs comparisons already made at 9m; if its ranking agrees, it explores and 9m "
    "confirms the winners."
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("update s1.sizes set name=:name, role=:role, overview=:overview where preset='1m'"),
        {"name": NAME, "role": ROLE, "overview": OVERVIEW},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("update s1.sizes set name=:name, role=:role, overview=:overview where preset='1m'"),
        {"name": OLD_NAME, "role": OLD_ROLE, "overview": OLD_OVERVIEW},
    )

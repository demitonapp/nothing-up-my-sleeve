"""the 300k is the towing tank

The 300k's name and what it is for (Justin, 11 November, night: "we need an analogy for the 300k ... we mix a
bunch of combinations there and then measure it to see what comes out"; then "i like towing tank, please
update the fal images and the naming"). A towing tank is the long trough of still water a shipwright draws
scale hulls down, one shape after another, timing each, so the yard knows what a hull will do before it pays
for the ship. That is the 300k's work: a combination changed, a run of minutes, a reading out.

What it measures first is unchanged from the name before (Faces): the four Face cards. The hull is still the
6-layer 300k; the name, the role and the description are the store's. The class slug becomes `towing-tank`;
`faces`, `pan`, `keel` and `seedling` stay as addresses that forward (CLASS_RENAMES, server.py and router.ts).

Revision ID: c0x3y6z9a2b5
Revises: b9w2x5y8z1a4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c0x3y6z9a2b5"
down_revision = "b9w2x5y8z1a4"
branch_labels = None
depends_on = None

NAME = "The towing tank"
ROLE = (
    "Primary objective: try many combinations cheaply and measure what each one makes — shelves, stages, "
    "pins and schedules, one changed at a time, each run a few minutes and each read the same way. What it "
    "measures first is the four Face cards — the Nevermore, the Counter, the Scales and the Mover: which "
    "combinations form them and make them hold. All four in one 300k is the optional result; the tank's "
    "finding is what to carry into the 1m."
)
OVERVIEW = (
    "Six layers of 48, two heads of 24, vocabulary 2,048: about 0.3M parameters, the smallest ship that "
    "can hold a card map. It is the yard's towing tank: a small hull drawn down the same measured water "
    "again and again with one thing changed each time, so the yard learns what a mixture makes before a "
    "larger ship is built on it. Its first readings are the four Face cards — the Nevermore, the Counter, "
    "the Scales and the Mover — and which of them a 300k can earn. A tank reading is a reading at model "
    "scale: what holds here is tried again at the 1m before it is trusted, and what the tank cannot hold, "
    "the 1m inherits."
)
OLD_NAME = "Faces"
OLD_ROLE = (
    "Primary objective: form the four Face cards — the Nevermore, the Counter, the Scales and the "
    "Mover — and find how to make them hold. All four in one 300k is the optional result; if they do "
    "not all hold here, the 300k's finding is how to carry them into the 1m and get all four there."
)
OLD_OVERVIEW = (
    "Six layers of 48, two heads of 24, vocabulary 2,048: about 0.3M parameters, the smallest ship that "
    "can hold a card map. Its job is the four Face cards — the Nevermore, the Counter, the Scales and "
    "the Mover — and the experiments that show which of them a 300k can earn. It is the bottom of the "
    "ladder; what it cannot hold, the 1m inherits."
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("update s1.sizes set name=:name, role=:role, overview=:overview where preset='300k'"),
        {"name": NAME, "role": ROLE, "overview": OVERVIEW},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("update s1.sizes set name=:name, role=:role, overview=:overview where preset='300k'"),
        {"name": OLD_NAME, "role": OLD_ROLE, "overview": OLD_OVERVIEW},
    )

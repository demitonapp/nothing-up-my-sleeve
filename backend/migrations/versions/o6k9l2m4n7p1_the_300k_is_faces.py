"""the 300k is Faces

The 300k's name and purpose (Justin, 11 November: "the 300k ship should be called Faces not Pan. As the
300k's purpose is how to form the 4 Face cards with the optional goal of achieving all 4 Faces in the
300, but if all 4 are not likely in the 300k, then the learnings from the 300k are to take it into the
1m and see if we can get all 4 faces on the 1m"). The hull is still the 6-layer 300k; the name, the
role and the description are the store's.

Revision ID: o6k9l2m4n7p1
Revises: n5j8k1g3b4c6
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "o6k9l2m4n7p1"
down_revision = "n5j8k1g3b4c6"
branch_labels = None
depends_on = None

NAME = "Faces"
ROLE = (
    "Primary objective: form the four Face cards — the Nevermore, the Counter, the Scales and the "
    "Mover — and find how to make them hold. All four in one 300k is the optional result; if they do "
    "not all hold here, the 300k's finding is how to carry them into the 1m and get all four there."
)
OVERVIEW = (
    "Six layers of 48, two heads of 24, vocabulary 2,048: about 0.3M parameters, the smallest ship that "
    "can hold a card map. Its job is the four Face cards — the Nevermore, the Counter, the Scales and "
    "the Mover — and the experiments that show which of them a 300k can earn. It is the bottom of the "
    "ladder; what it cannot hold, the 1m inherits."
)
OLD_NAME = "Pan"
OLD_ROLE = (
    "Primary objective: the best at the two-word bigram table. Its next word guessed as well as Ogden's "
    "keyed table of word pairs guesses it (853 x 853: the 850 words, <name>, <number>, <thing>), or "
    "better"
)
OLD_OVERVIEW = (
    "2 layers x 64, two heads of 32 (the same head size as 1m and 9m, so a head can be carried up "
    "whole), vocabulary 2,048: about 0.3M parameters. Too small to judge books on; its job is the "
    "bottom of the stack. Can it light a previous-word head at all, how fast, and does a 1m built on "
    "its frozen layers reach the Nevermore sooner?\n"
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

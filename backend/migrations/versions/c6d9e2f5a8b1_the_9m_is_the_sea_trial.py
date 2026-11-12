"""the 9m is the sea trial

The 9m's name, to follow the 300k's and the 1m's (Justin, 12 November: "Can you suggest new metaphors for the
9m and 21m ships. the 300k is the towing tank and the 1m is the measured mile. What should the 9 and 21 be?";
then "Yes, rename both"). After the tank and the mile comes the sea trial: the finished ship taken past the
harbour bar for the first time, with helm, pumps and canvas all worked at once, to see whether she does at sea
what the yard's measurements said she would. That is the 9m's place on the ladder: what the 1m ranked is
confirmed here, and a tank reading does not always hold here (a 300k has passed tests a 9m fails).

Its objective is unchanged: the surface of English (spelling, punctuation, the statistical laws of text). The
hull is the 18-layer 9m; the description before still called it the smallest model. The class slug becomes
`sea-trial`; `speller` stays as an address that forwards (CLASS_RENAMES, server.py and router.ts), and the
tests, heads and question sets that name their class "speller" still find the 9m through it.

Revision ID: c6d9e2f5a8b1
Revises: b5c8d1e4f7a0
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c6d9e2f5a8b1"
down_revision = "b5c8d1e4f7a0"
branch_labels = None
depends_on = None

NAME = "The sea trial"
ROLE = (
    "Primary objective: spelling, punctuation and the statistical laws of text, the surface of English. It "
    "is the sea trial: the first size taken out whole, where what the towing tank and the measured mile "
    "found is confirmed before a larger ship is built on it"
)
OVERVIEW = (
    "Eighteen layers of 120, six heads of 20. It is the yard's sea trial: the finished ship taken past the "
    "harbour bar for the first time, with helm, pumps and canvas all worked at once, to see whether she does "
    "at sea what the tank and the mile said she would. The 9m is the first size asked for English itself, "
    "not a card map or a maths book: how words are spelled, where punctuation goes, how lines and paragraphs "
    "break, and the statistical regularities every real text obeys. What the 1m ranked is confirmed here, "
    "and a tank reading does not always hold here (a 300k has passed tests a 9m fails), which is what a sea "
    "trial is for. Tuned first (vocabulary and context), then frozen for shelf experiments."
)
OLD_NAME = "The speller"
OLD_ROLE = "Spelling, punctuation and the statistical laws of text"
OLD_OVERVIEW = (
    "The smallest model learns the surface of English: how words are spelled, where punctuation goes, how "
    "lines and paragraphs break, and the statistical regularities every real text obeys. Tuned first "
    "(vocabulary and context), then frozen for shelf experiments."
)


def upgrade() -> None:
    op.get_bind().execute(
        sa.text("update s1.sizes set name=:name, role=:role, overview=:overview where preset='9m'"),
        {"name": NAME, "role": ROLE, "overview": OVERVIEW},
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text("update s1.sizes set name=:name, role=:role, overview=:overview where preset='9m'"),
        {"name": OLD_NAME, "role": OLD_ROLE, "overview": OLD_OVERVIEW},
    )

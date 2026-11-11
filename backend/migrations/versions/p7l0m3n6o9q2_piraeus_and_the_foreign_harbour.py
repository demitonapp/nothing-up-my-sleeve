"""Piraeus for our deep ships; Zayton is the foreign ships' harbour

Justin, 11 November: "our 50m, 100m, 350m need a new harbour sitting alongside Phaleron for our own
ships, but a deeper harbour and then Zayton is where all foreign ships are." Piraeus, Themistocles'
deep harbour beside Phaleron, takes our own ships too deep for Phaleron (50m, 100m, 350m). Zayton
keeps the outside models: its `foreign_only` flag says it is a berth for foreign ships, not a depth
rule for ours.

Revision ID: p7l0m3n6o9q2
Revises: o6k9l2m4n7p1
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "p7l0m3n6o9q2"
down_revision = "o6k9l2m4n7p1"
branch_labels = None
depends_on = None

ZAYTON_ABOUT = (
    "Zayton (Quanzhou), the greatest trading harbour of the Silk Road's sea road: every foreign ship, "
    "read on our decks, not ours to build."
)
OLD_ZAYTON_ABOUT = (
    "Zayton (Quanzhou), the greatest trading harbour of the Silk Road's sea road: the ships too deep "
    "for Phaleron, which need hired GPUs."
)
PIRAEUS_ABOUT = (
    "Themistocles' deep harbour beside Phaleron: our own 50m, 100m and 350m, the ships too deep for "
    "Phaleron and too big for this Mac."
)


def upgrade() -> None:
    op.add_column(
        "harbours",
        sa.Column("foreign_only", sa.Boolean(), server_default=sa.false(), nullable=False),
        schema="s1",
    )
    c = op.get_bind()
    # Zayton moves after Piraeus; ordinal is unique, so move it out of the way before inserting
    c.execute(sa.text("update s1.harbours set ordinal=2 where key='zayton'"))
    c.execute(
        sa.text(
            "insert into s1.harbours (key, ordinal, name, aka, lane, location, about, depth,"
            " ship_builder, foreign_only) values ('piraeus', 1, 'Piraeus', :aka, 'vast', :where,"
            " :about, null, '', false)"
        ),
        {
            "aka": "the deep waters",
            "where": "GPUs hired from Vast.ai",
            "about": PIRAEUS_ABOUT,
        },
    )
    c.execute(
        sa.text(
            "update s1.harbours set foreign_only=true, lane='foreign', location=:where, aka=:aka,"
            " about=:about where key='zayton'"
        ),
        {"where": "the Market Harbour", "aka": "the Market Harbour", "about": ZAYTON_ABOUT},
    )


def downgrade() -> None:
    c = op.get_bind()
    c.execute(sa.text("delete from s1.harbours where key='piraeus'"))
    c.execute(
        sa.text(
            "update s1.harbours set ordinal=1, foreign_only=false, lane='vast',"
            " location='GPUs hired from Vast.ai', aka='outer waters', about=:about where key='zayton'"
        ),
        {"about": OLD_ZAYTON_ABOUT},
    )
    op.drop_column("harbours", "foreign_only", schema="s1")

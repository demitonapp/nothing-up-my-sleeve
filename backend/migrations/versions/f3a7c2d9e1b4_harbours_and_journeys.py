"""harbours and journeys

A harbour is a table (`s1.harbours`): its depth, its lane and its harbourmaster. A journey is a plan
(`s3.journeys`) with two legs, each a list of stages (`s3.journey_stages`): pretraining goes out from
the harbour, posttraining returns to it.

Revision ID: f3a7c2d9e1b4
Revises: c1d9b0e4a2f7
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "f3a7c2d9e1b4"
down_revision = "c1d9b0e4a2f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "harbours",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("aka", sa.Text(), server_default="", nullable=False),
        sa.Column("lane", sa.Text(), nullable=False),
        sa.Column("location", sa.Text(), server_default="", nullable=False),
        sa.Column("about", sa.Text(), server_default="", nullable=False),
        sa.Column("depth", sa.BigInteger(), nullable=True),
        sa.Column("harbourmaster", sa.Text(), server_default="", nullable=False),
        sa.PrimaryKeyConstraint("key"),
        sa.UniqueConstraint("ordinal"),
        sa.UniqueConstraint("name"),
        schema="s1",
    )
    op.create_table(
        "journeys",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("ship_key", sa.Text(), nullable=True),
        sa.Column("harbour_key", sa.Text(), nullable=True),
        sa.Column("aim", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("signed_by", sa.Text(), nullable=True),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("manifest_sha1", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ship_key"], ["s1.ships.key"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["harbour_key"], ["s1.harbours.key"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("key"),
        schema="s3",
    )
    op.create_table(
        "journey_stages",
        sa.Column("journey_key", sa.Text(), nullable=False),
        sa.Column("phase", sa.Text(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("purpose", sa.Text(), server_default="", nullable=False),
        sa.Column("library", sa.Text(), nullable=True),
        sa.Column("tokens", sa.BigInteger(), nullable=True),
        sa.Column("passes", sa.Integer(), server_default="1", nullable=False),
        sa.Column("lr", sa.Float(), nullable=True),
        sa.Column("compose", postgresql.JSONB(), nullable=True),
        sa.CheckConstraint("phase in ('pretraining', 'posttraining')", name="journey_stage_phase"),
        sa.ForeignKeyConstraint(["journey_key"], ["s3.journeys.key"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("journey_key", "phase", "ordinal"),
        schema="s3",
    )

    harbours = sa.table(
        "harbours",
        sa.column("key", sa.Text()),
        sa.column("ordinal", sa.Integer()),
        sa.column("name", sa.Text()),
        sa.column("aka", sa.Text()),
        sa.column("lane", sa.Text()),
        sa.column("location", sa.Text()),
        sa.column("about", sa.Text()),
        sa.column("depth", sa.BigInteger()),
        sa.column("harbourmaster", sa.Text()),
        schema="s1",
    )
    op.bulk_insert(
        harbours,
        [
            {
                "key": "phaleron",
                "ordinal": 0,
                "name": "Phaleron",
                "aka": "internal waters",
                "lane": "mac",
                "location": "this Mac mini",
                "about": "Athens' first harbour, where its early fleet lay and sailed from: the youngest "
                "ships, trained on this Mac.",
                "depth": 20_000_000,
                "harbourmaster": "Justin",
            },
            {
                "key": "zayton",
                "ordinal": 1,
                "name": "Zayton",
                "aka": "outer waters",
                "lane": "vast",
                "location": "GPUs hired from Vast.ai",
                "about": "Zayton (Quanzhou), the greatest trading harbour of the Silk Road's sea road: the "
                "ships too deep for Phaleron, which need hired GPUs.",
                "depth": None,
                "harbourmaster": "Justin",
            },
        ],
    )

    journeys = sa.table(
        "journeys",
        sa.column("key", sa.Text()),
        sa.column("name", sa.Text()),
        sa.column("ship_key", sa.Text()),
        sa.column("harbour_key", sa.Text()),
        sa.column("aim", sa.Text()),
        sa.column("status", sa.Text()),
        schema="s3",
    )
    op.bulk_insert(
        journeys,
        [
            {
                "key": "invention-return",
                "name": "The Invention's journey",
                "ship_key": None,
                "harbour_key": "phaleron",
                "aim": "Necessity, tedium and being broke: the 100m goes out to learn the language and the "
                "shapes of the world, and returns to Phaleron with modern information.",
                "status": "draft",
            }
        ],
    )
    stages = sa.table(
        "journey_stages",
        sa.column("journey_key", sa.Text()),
        sa.column("phase", sa.Text()),
        sa.column("ordinal", sa.Integer()),
        sa.column("name", sa.Text()),
        sa.column("purpose", sa.Text()),
        sa.column("library", sa.Text()),
        sa.column("tokens", sa.BigInteger()),
        sa.column("passes", sa.Integer()),
        sa.column("lr", sa.Float()),
        schema="s3",
    )
    op.bulk_insert(
        stages,
        [
            {
                "journey_key": "invention-return",
                "phase": "pretraining",
                "ordinal": 0,
                "name": "ogden",
                "purpose": "go out: learn the language and the shapes of the world",
                "library": "lists/ogden-v0.1.csv",
                "tokens": None,
                "passes": 4,
                "lr": None,
            },
            {
                "journey_key": "invention-return",
                "phase": "posttraining",
                "ordinal": 0,
                "name": "modern",
                "purpose": "return to Phaleron with modern information",
                "library": None,
                "tokens": None,
                "passes": 1,
                "lr": None,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("journey_stages", schema="s3")
    op.drop_table("journeys", schema="s3")
    op.drop_table("harbours", schema="s1")

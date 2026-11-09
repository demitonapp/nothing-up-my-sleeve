"""the SOP as data: s5.sop_versions (a voyage names its version in the spec)

Justin, 8 November: "should the scaffold be part of the SOP data model with a relationship to a voyage in postgres
and then the scaffold is just actually one line of the voyages sop.pretraining_phases.[content, scaffold] or something
like that" — "yeah do it". One row a version: content, parameters, the sizes' learning rates, the five cards in rank
order, and the phases (the scaffold as a phase, content as the phase after it). The prose stays in
ships/plans/sop-v<version>.md, which the row points at; the readings stay in the ledger.

Revision ID: c1d9b0e4a2f7
Revises: b7c2f41a9d03
Create Date: 2026-11-08 20:35:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c1d9b0e4a2f7"
down_revision: str | Sequence[str] | None = "b7c2f41a9d03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sop_versions",
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("adopted", sa.Text(), server_default="", nullable=False),
        sa.Column("doc", sa.Text(), server_default="", nullable=False),
        sa.Column("supersedes", sa.Text(), nullable=True),
        sa.Column("standard", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("version"),
        schema="s5",
    )


def downgrade() -> None:
    op.drop_table("sop_versions", schema="s5")

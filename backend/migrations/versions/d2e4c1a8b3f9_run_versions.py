"""a plan's version, 1.2.3: s1.run_versions

Justin, 8 November: "we need a numbering version for runs. with 1.2.3 where major version is the journey of the ship,
so order of the pretraining and postraining, the minor version is the content and the last number can be something
else". Major = the ordered stages; minor = the corpus and its tokeniser; patch = the rest of the plan. A seed is not a
version. Assigned on first sight by thorp/versioning.py, never reused.

Revision ID: d2e4c1a8b3f9
Revises: c1d9b0e4a2f7
Create Date: 2026-11-08 21:50:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d2e4c1a8b3f9"
down_revision: str | Sequence[str] | None = "c1d9b0e4a2f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "run_versions",
        sa.Column("version", sa.Text(), nullable=False),
        sa.Column("major", sa.Integer(), nullable=False),
        sa.Column("minor", sa.Integer(), nullable=False),
        sa.Column("patch", sa.Integer(), nullable=False),
        sa.Column("journey_fp", sa.Text(), nullable=False),
        sa.Column("content_fp", sa.Text(), nullable=False),
        sa.Column("params_fp", sa.Text(), nullable=False),
        sa.Column("journey", sa.Text(), server_default="", nullable=False),
        sa.Column("first_spec", sa.Text(), server_default="", nullable=False),
        sa.Column("last_run", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("version"),
        schema="s1",
    )
    op.create_index("run_versions_plan", "run_versions", ["journey_fp", "content_fp", "params_fp"], schema="s1")


def downgrade() -> None:
    op.drop_index("run_versions_plan", table_name="run_versions", schema="s1")
    op.drop_table("run_versions", schema="s1")

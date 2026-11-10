"""Yards and work: provenance on every run, and the federation seam.

Revision ID: l3h6i9e1f8a0
Revises: k2g5h8d0e7f9
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "l3h6i9e1f8a0"
down_revision = "k2g5h8d0e7f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in ("yard_id", "spec_sha", "artifact_root"):
        op.add_column("runs", sa.Column(col, sa.Text(), nullable=True), schema="s1")
    op.create_table(
        "yards",
        sa.Column("yard_id", sa.Text(), primary_key=True),
        sa.Column("owner", sa.Text()),
        sa.Column("compute", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="s1",
    )
    op.create_table(
        "work",
        sa.Column("work_id", sa.Text(), primary_key=True),
        sa.Column("spec_sha", sa.Text(), nullable=False),
        sa.Column("goal", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="open"),
        sa.Column("claimed_by", sa.Text()),
        sa.Column("run_id", sa.Text()),
        sa.Column("bundle_sha", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        schema="s1",
    )
    op.create_index("work_status", "work", ["status"], schema="s1")


def downgrade() -> None:
    op.drop_index("work_status", table_name="work", schema="s1")
    op.drop_table("work", schema="s1")
    op.drop_table("yards", schema="s1")
    for col in ("yard_id", "spec_sha", "artifact_root"):
        op.drop_column("runs", col, schema="s1")

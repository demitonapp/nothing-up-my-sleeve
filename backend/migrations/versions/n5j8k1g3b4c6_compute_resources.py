"""Compute resources: a yard can add machines, test them, and cap them.

Revision ID: n5j8k1g3b4c6
Revises: m4i7j0f2a3b5
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "n5j8k1g3b4c6"
down_revision = "m4i7j0f2a3b5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "compute_resources",
        sa.Column("resource_id", sa.Text(), primary_key=True),
        sa.Column("yard_id", sa.Text()),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("specs", JSONB),
        sa.Column("bench", JSONB),
        sa.Column("caps", JSONB),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="s1",
    )
    op.add_column("lanes", sa.Column("resource_id", sa.Text()), schema="s2")


def downgrade() -> None:
    op.drop_column("lanes", "resource_id", schema="s2")
    op.drop_table("compute_resources", schema="s1")

"""A lane counts its seats.

Revision ID: i0e3f6b8c4d5
Revises: h9d2e5f7a1c3
"""
from alembic import op
import sqlalchemy as sa

revision = "i0e3f6b8c4d5"
down_revision = "h9d2e5f7a1c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("lanes", sa.Column("seats", sa.Integer(), nullable=True, server_default="1"), schema="s2")


def downgrade() -> None:
    op.drop_column("lanes", "seats", schema="s2")

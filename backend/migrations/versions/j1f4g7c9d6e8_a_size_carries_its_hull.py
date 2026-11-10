"""A size carries its hull.

Revision ID: j1f4g7c9d6e8
Revises: i0e3f6b8c4d5
"""
from alembic import op
import sqlalchemy as sa

revision = "j1f4g7c9d6e8"
down_revision = "i0e3f6b8c4d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for col in ("layers", "width", "heads"):
        op.add_column("sizes", sa.Column(col, sa.Integer(), nullable=True), schema="s1")


def downgrade() -> None:
    for col in ("layers", "width", "heads"):
        op.drop_column("sizes", col, schema="s1")

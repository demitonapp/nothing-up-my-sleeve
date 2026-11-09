"""the analogy is ship builder, not harbourmaster

Revision ID: c8f2a4d6e1b3
Revises: 213865d7b61d
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "c8f2a4d6e1b3"
down_revision = "213865d7b61d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "harbours",
        "harbourmaster",
        new_column_name="ship_builder",
        schema="s1",
        existing_type=sa.Text(),
        existing_server_default="",
    )


def downgrade() -> None:
    op.alter_column(
        "harbours",
        "ship_builder",
        new_column_name="harbourmaster",
        schema="s1",
        existing_type=sa.Text(),
        existing_server_default="",
    )

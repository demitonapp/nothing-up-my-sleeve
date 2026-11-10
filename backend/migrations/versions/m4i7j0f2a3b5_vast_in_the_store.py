"""The Vast key in the store, so the yard's compute is one store.

Revision ID: m4i7j0f2a3b5
Revises: l3h6i9e1f8a0
"""

from alembic import op
import sqlalchemy as sa

revision = "m4i7j0f2a3b5"
down_revision = "l3h6i9e1f8a0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "provider_credentials",
        sa.Column("provider", sa.Text(), primary_key=True),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="s5",
    )


def downgrade() -> None:
    op.drop_table("provider_credentials", schema="s5")

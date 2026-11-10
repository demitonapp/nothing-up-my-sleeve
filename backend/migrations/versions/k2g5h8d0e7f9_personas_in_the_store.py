"""Persona vectors in the store: a master list of traits, and each model's reading against it.

Revision ID: k2g5h8d0e7f9
Revises: j1f4g7c9d6e8
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "k2g5h8d0e7f9"
down_revision = "j1f4g7c9d6e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "persona_master",
        sa.Column("key", sa.Text(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("positive", sa.Text(), nullable=False),
        sa.Column("negative", sa.Text(), nullable=False),
        sa.Column("about", sa.Text()),
        sa.Column("source", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        schema="s4",
    )
    op.create_table(
        "persona_vectors",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("trait_key", sa.Text(), nullable=False),
        sa.Column("layer", sa.Integer(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("vector", JSONB, nullable=False),
        sa.Column("norm", sa.Float(), nullable=False),
        sa.Column("projection", sa.Float()),
        sa.Column("cosine", sa.Float()),
        sa.Column("read_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["trait_key"], ["s4.persona_master.key"], ondelete="CASCADE"),
        sa.UniqueConstraint("model", "trait_key", "layer", name="persona_vectors_model_trait_layer"),
        schema="s4",
    )
    op.create_index("persona_vectors_model", "persona_vectors", ["model"], schema="s4")


def downgrade() -> None:
    op.drop_index("persona_vectors_model", table_name="persona_vectors", schema="s4")
    op.drop_table("persona_vectors", schema="s4")
    op.drop_table("persona_master", schema="s4")

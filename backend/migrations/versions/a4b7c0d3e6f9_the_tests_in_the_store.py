"""the tests in the store

12 November (Justin: "we'll need a table for all our tests in postgres"): `s4.tests` is one row per test
Nothing up my sleeve scores a model on, synced from `thorp.fleet.TRICKS` and its four discovery chains.
The key is the trick key; the row keeps the name, the chain and rung it belongs to, the evaluator and
metric that write it, its threshold and share rule, its matched-pairs list, and the ordinal it is shown in.

Revision ID: a4b7c0d3e6f9
Revises: f3a6b9c2d5e8
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "a4b7c0d3e6f9"
down_revision = "f3a6b9c2d5e8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tests",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("chain", sa.Text(), nullable=False, server_default=""),
        sa.Column("rung", sa.Text(), nullable=False, server_default=""),
        sa.Column("evaluator", sa.Text(), nullable=False, server_default=""),
        sa.Column("metric", sa.Text(), nullable=False, server_default=""),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("min_score", sa.Float(), nullable=True),
        sa.Column("pairs", sa.Text(), nullable=False, server_default=""),
        sa.Column("about", sa.Text(), nullable=False, server_default=""),
        sa.Column("ordinal", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("key"),
        schema="s4",
    )
    op.create_index("tests_chain_ordinal", "tests", ["chain", "ordinal"], schema="s4")


def downgrade() -> None:
    op.drop_index("tests_chain_ordinal", table_name="tests", schema="s4")
    op.drop_table("tests", schema="s4")

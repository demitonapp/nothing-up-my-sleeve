"""no ship builder in Zayton

Ships are built at Phaleron; Zayton is where the deep ships sail, not where they are built (Justin,
9 November: "there shouldn't be a shipbuilder in zayton. We don't build ships there, only sail there").

Revision ID: f6b1d3a8c2e4
Revises: c8f2a4d6e1b3
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "f6b1d3a8c2e4"
down_revision = "c8f2a4d6e1b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(sa.text("update s1.harbours set ship_builder='' where key='zayton'"))


def downgrade() -> None:
    op.get_bind().execute(sa.text("update s1.harbours set ship_builder='Justin' where key='zayton'"))

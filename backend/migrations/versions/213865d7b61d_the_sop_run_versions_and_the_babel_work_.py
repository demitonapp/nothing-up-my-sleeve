"""the SOP, run versions and the babel work, one head

Revision ID: 213865d7b61d
Revises: a9c3e5b7d1f2, d2e4c1a8b3f9
Create Date: 2026-11-08 21:37:02.738255

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '213865d7b61d'
down_revision: Union[str, Sequence[str], None] = ('a9c3e5b7d1f2', 'd2e4c1a8b3f9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

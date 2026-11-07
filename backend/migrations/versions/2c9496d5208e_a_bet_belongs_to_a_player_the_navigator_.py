"""a bet belongs to a player (the Navigator, Claude)

Revision ID: 2c9496d5208e
Revises: 13d6214bc39b
Create Date: 2026-11-07 22:00:00.572107

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '2c9496d5208e'
down_revision: str | Sequence[str] | None = '13d6214bc39b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema: a bet is one player's chip on one card of one round."""
    op.drop_constraint("bets_pkey", "bets", schema="game", type_="primary")
    op.create_primary_key("bets_pkey", "bets", ["round_key", "card", "player"], schema="game")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("bets_pkey", "bets", schema="game", type_="primary")
    op.create_primary_key("bets_pkey", "bets", ["round_key", "card"], schema="game")

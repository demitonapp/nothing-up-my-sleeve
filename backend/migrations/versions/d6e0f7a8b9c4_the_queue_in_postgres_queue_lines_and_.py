"""the queue in Postgres: queue_lines and queue_history

The standing queue moves into the one store, schema `s2` (DECISIONS.md, phase 3: the queue): `queue_lines`
(the pending lines, in order) and `queue_history` (every line that started, from queue-done.txt). The
backfill (`thorp.viable.s2_coordination.queue_store.backfill`) copies the live files read-only; the queue
itself cuts over in port, at a time agreed with Justin.

Revision ID: d6e0f7a8b9c4
Revises: c5d9e6f7a8b3
Create Date: 2026-11-09 18:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd6e0f7a8b9c4'
down_revision: Union[str, Sequence[str], None] = 'c5d9e6f7a8b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'queue_lines',
        sa.Column('position', sa.BigInteger(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('kind', sa.Text(), nullable=False),
        sa.Column('payload', sa.Text(), nullable=False),
        sa.Column('lane', sa.Text(), nullable=False),
        sa.Column('added_by', sa.Text(), nullable=True),
        sa.Column('added_at', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('position'),
        schema='s2',
    )
    op.create_table(
        'queue_history',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('lane', sa.Text(), nullable=True),
        sa.Column('started', sa.Text(), nullable=True),
        sa.Column('status', sa.Text(), nullable=True),
        sa.Column('run', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='s2',
    )


def downgrade() -> None:
    op.drop_table('queue_history', schema='s2')
    op.drop_table('queue_lines', schema='s2')

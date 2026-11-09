"""the ledger in Postgres: runs, metrics, evals and artifacts

S1 operations' own record (the voyages) moves from ledger.sqlite into the one store, schema `s1`. The tables
mirror the SQLite ledger (thorp/ledger.py) with one addition: `metrics`, `evals` and `artifacts` carry an `id`
(BIGSERIAL) that stands for SQLite's implicit `rowid` ("the later row at one step stands"). The backfill
(`thorp/ledger_store.backfill`) copies rows in rowid order; readers move over in the cut-over phase.

Revision ID: e3b7d2a9c4f1
Revises: g8c1f4a6b2d7
Create Date: 2026-11-09 13:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e3b7d2a9c4f1'
down_revision: Union[str, Sequence[str], None] = 'g8c1f4a6b2d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('runs',
    sa.Column('run_id', sa.Text(), nullable=False),
    sa.Column('name', sa.Text(), nullable=True),
    sa.Column('ship', sa.Text(), nullable=True),
    sa.Column('spec_json', sa.Text(), nullable=True),
    sa.Column('commit', sa.Text(), nullable=True),
    sa.Column('hardware', sa.Text(), nullable=True),
    sa.Column('started', sa.Text(), nullable=True),
    sa.Column('finished', sa.Text(), nullable=True),
    sa.Column('status', sa.Text(), nullable=True),
    sa.Column('tokens_seen', sa.BigInteger(), nullable=True),
    sa.Column('wall_minutes', sa.Float(), nullable=True),
    sa.PrimaryKeyConstraint('run_id'),
    schema='s1'
    )
    op.create_index('runs_started', 'runs', ['started'], unique=False, schema='s1')

    op.create_table('metrics',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('run_id', sa.Text(), nullable=False),
    sa.Column('step', sa.BigInteger(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('value', sa.Float(), nullable=False),
    sa.Column('ts', sa.Float(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='s1'
    )
    op.create_index('metrics_run', 'metrics', ['run_id', 'name', 'step', 'id'], unique=False, schema='s1')

    op.create_table('evals',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('run_id', sa.Text(), nullable=False),
    sa.Column('step', sa.BigInteger(), nullable=False),
    sa.Column('set', sa.Text(), nullable=False),
    sa.Column('book_id', sa.Text(), nullable=False),
    sa.Column('ce_nats', sa.Float(), nullable=True),
    sa.Column('bpb', sa.Float(), nullable=True),
    sa.Column('tokens', sa.BigInteger(), nullable=True),
    sa.Column('bytes', sa.BigInteger(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    schema='s1'
    )
    op.create_index('evals_run', 'evals', ['run_id', 'step'], unique=False, schema='s1')

    op.create_table('artifacts',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('run_id', sa.Text(), nullable=False),
    sa.Column('step', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.Text(), nullable=False),
    sa.Column('path', sa.Text(), server_default='', nullable=False),
    sa.Column('sha1', sa.Text(), server_default='', nullable=False),
    sa.Column('text', sa.Text(), server_default='', nullable=False),
    sa.PrimaryKeyConstraint('id'),
    schema='s1'
    )
    op.create_index('artifacts_run', 'artifacts', ['run_id', 'kind', 'step'], unique=False, schema='s1')


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('artifacts_run', table_name='artifacts', schema='s1')
    op.drop_table('artifacts', schema='s1')
    op.drop_index('evals_run', table_name='evals', schema='s1')
    op.drop_table('evals', schema='s1')
    op.drop_index('metrics_run', table_name='metrics', schema='s1')
    op.drop_table('metrics', schema='s1')
    op.drop_index('runs_started', table_name='runs', schema='s1')
    op.drop_table('runs', schema='s1')

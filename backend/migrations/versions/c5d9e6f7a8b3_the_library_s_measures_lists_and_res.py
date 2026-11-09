"""the library's measures, lists and resolutions

The library CSVs move into the one store, schema `s1` (DECISIONS.md, phase 2: the library):
`book_measures` (data/trigrams.csv), `lists` (the distinct `ships/lists/*.csv` paths the resolutions name)
and `list_resolutions` (data/resolution.csv and data/unresolved.csv). Each ties to `books`/`lists` by
foreign key. The backfill (`thorp/manifest_store.backfill`) copies them; readers move over in the cut-over.

Revision ID: c5d9e6f7a8b3
Revises: b4c8d5e6f7a2
Create Date: 2026-11-09 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c5d9e6f7a8b3'
down_revision: Union[str, Sequence[str], None] = 'b4c8d5e6f7a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'book_measures',
        sa.Column('book_id', sa.Text(), nullable=False),
        sa.Column('repeat_rate', sa.Float(), nullable=True),
        sa.Column('variety', sa.Float(), nullable=True),
        sa.Column('words', sa.Integer(), nullable=True),
        sa.Column('name_repeat', sa.Float(), nullable=True),
        sa.Column('name_density', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['book_id'], ['s1.books.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('book_id'),
        schema='s1',
    )
    op.create_table(
        'lists',
        sa.Column('path', sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint('path'),
        schema='s1',
    )
    op.create_table(
        'list_resolutions',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('list', sa.Text(), nullable=True),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('language', sa.Text(), nullable=True),
        sa.Column('chosen', sa.Text(), nullable=True),
        sa.Column('how', sa.Text(), nullable=True),
        sa.Column('n_candidates', sa.Integer(), nullable=True),
        sa.Column('candidates', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['list'], ['s1.lists.path'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        schema='s1',
    )
    op.create_index('list_resolutions_list', 'list_resolutions', ['list'], unique=False, schema='s1')


def downgrade() -> None:
    op.drop_index('list_resolutions_list', table_name='list_resolutions', schema='s1')
    op.drop_table('list_resolutions', schema='s1')
    op.drop_table('lists', schema='s1')
    op.drop_table('book_measures', schema='s1')

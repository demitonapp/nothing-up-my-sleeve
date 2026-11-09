"""the library in Postgres: books

S1 operations' book register moves from data/manifest.sqlite into the one store, schema `s1`. The table
mirrors the SQLite manifest (thorp/manifest.py); its `set` column is the model's `book_set` (as the ledger's
evals call `set` `eval_set`). The backfill (`thorp/manifest_store.backfill`) copies the rows and
`verify()` checks the count; readers move over in the cut-over phase (DECISIONS.md, phase 2: the library).

Revision ID: b4c8d5e6f7a2
Revises: e3b7d2a9c4f1
Create Date: 2026-11-09 15:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b4c8d5e6f7a2'
down_revision: Union[str, Sequence[str], None] = 'e3b7d2a9c4f1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'books',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('source', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=True),
        sa.Column('author', sa.Text(), nullable=True),
        sa.Column('language', sa.Text(), nullable=True),
        sa.Column('family', sa.Text(), nullable=True),
        sa.Column('text', sa.Text(), nullable=True),
        sa.Column('chars', sa.Integer(), nullable=True),
        sa.Column('bytes', sa.Integer(), nullable=True),
        sa.Column('sha1', sa.Text(), nullable=True),
        sa.Column('fetched_at', sa.Text(), nullable=True),
        sa.Column('set', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        schema='s1',
    )
    op.create_index('books_source', 'books', ['source'], unique=False, schema='s1')


def downgrade() -> None:
    op.drop_index('books_source', table_name='books', schema='s1')
    op.drop_table('books', schema='s1')

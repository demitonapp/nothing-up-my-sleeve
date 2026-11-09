"""a journey is not a voyage

A journey's `ship_key` is a plan's reference, not a foreign key: a journey may be written before its ship,
and `truncate s1.ships cascade` (a test's clean slate) must not delete the plan. The Invention's journey is
re-seeded if it was lost.

Revision ID: e7b1c4d8a2f6
Revises: d4e8f1a2b6c9
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "e7b1c4d8a2f6"
down_revision = "d4e8f1a2b6c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("journeys_ship_key_fkey", "journeys", schema="s3", type_="foreignkey")
    op.get_bind().execute(
        sa.text(
            """insert into s3.journeys (key, name, ship_key, harbour_key, aim, status)
               values ('invention-return', 'The Invention''s journey', null, 'phaleron',
                       'Necessity, tedium and being broke: the 100m goes out to learn the language and the '
                       'shapes of the world, and returns to Phaleron with modern information.', 'draft')
               on conflict (key) do nothing"""
        )
    )
    op.get_bind().execute(
        sa.text(
            """insert into s3.journey_stages (journey_key, phase, ordinal, name, purpose, library, tokens, passes, lr)
               values
                 ('invention-return', 'pretraining', 0, 'ogden',
                  'go out: learn the language and the shapes of the world', 'lists/ogden-v0.1.csv', null, 4, null),
                 ('invention-return', 'posttraining', 0, 'modern',
                  'return to Phaleron with modern information', null, null, 1, null)
               on conflict (journey_key, phase, ordinal) do nothing"""
        )
    )


def downgrade() -> None:
    op.create_foreign_key(
        "journeys_ship_key_fkey", "journeys", "ships", ["ship_key"], ["key"],
        source_schema="s3", referent_schema="s1", ondelete="SET NULL",
    )

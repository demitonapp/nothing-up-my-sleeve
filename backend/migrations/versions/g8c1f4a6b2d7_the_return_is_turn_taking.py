"""the return is turn-taking

SOP v0.0.6 adds posttraining for conversation turn-taking. The 100m's journey's return stage is
turned from the empty `modern` draft into `turn-taking`, reading the dialogue shelf for one pass.

Revision ID: g8c1f4a6b2d7
Revises: f6b1d3a8c2e4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "g8c1f4a6b2d7"
down_revision = "f6b1d3a8c2e4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """update s3.journey_stages
               set name='turn-taking',
                   purpose='return with turn-taking: answer its own turn, stop at the end of it, hand the conversation back',
                   library='lists/dialogue-shelf.csv', passes=1, cards=null
               where journey_key='invention-return' and phase='posttraining' and ordinal=0"""
        )
    )


def downgrade() -> None:
    op.get_bind().execute(
        sa.text(
            """update s3.journey_stages
               set name='modern', purpose='return to Phaleron with modern information',
                   library=null, passes=1, cards=null
               where journey_key='invention-return' and phase='posttraining' and ordinal=0"""
        )
    )

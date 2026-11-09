"""the cards a journey stage carries, with their characteristics

A pretraining stage records the cards it puts in, not just the books: the basic cards now, stage 1 cards
when a bigger model changes the plan. The snapshot keeps the card's level, metric, threshold and meaning as
they stood when the journey was written.

Revision ID: a9c3e5b7d1f2
Revises: e7b1c4d8a2f6
"""

from __future__ import annotations

import json

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "a9c3e5b7d1f2"
down_revision = "e7b1c4d8a2f6"
branch_labels = None
depends_on = None


def _basic_cards() -> str:
    from thorp import fleet

    out = [
        {
            "key": s.key,
            "name": s.name,
            "level": s.level,
            "kind": "star",
            "metric": s.metric,
            "shared_metric": s.shared_metric,
            "evaluator": s.evaluator,
            "threshold": s.threshold,
            "about": s.about,
        }
        for s in fleet.STARS.values()
        if s.level == 0
    ]
    return json.dumps(out)


def upgrade() -> None:
    op.add_column(
        "journey_stages",
        sa.Column("cards", postgresql.JSONB(), nullable=True),
        schema="s3",
    )
    op.get_bind().execute(
        sa.text(
            """update s3.journey_stages set cards=cast(:cards as jsonb)
               where journey_key='invention-return' and phase='pretraining' and ordinal=0"""
        ),
        {"cards": _basic_cards()},
    )


def downgrade() -> None:
    op.drop_column("journey_stages", "cards", schema="s3")

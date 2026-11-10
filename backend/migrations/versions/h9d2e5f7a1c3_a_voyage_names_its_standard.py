"""a voyage names the standard it was built to

`s1.runs` and `s3.journeys` gain `sop_version`, a foreign key to `s5.sop_versions(version)`. Until
now the only link between a voyage and its standard was the `sop` string inside `spec_json`, which
no join could reach — so "which standard did this run sail?" could not be asked of the store.

The backfill reads the string out of each spec and sets it only where the named version exists, so
the foreign key cannot be violated by a spec that names a version the register has never held.

Revision ID: h9d2e5f7a1c3
Revises: d6e0f7a8b9c4
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "h9d2e5f7a1c3"
down_revision = "d6e0f7a8b9c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("runs", sa.Column("sop_version", sa.Text(), nullable=True), schema="s1")
    op.create_foreign_key(
        "runs_sop_version_fkey", "runs", "sop_versions",
        ["sop_version"], ["version"], source_schema="s1", referent_schema="s5",
    )
    op.add_column("journeys", sa.Column("sop_version", sa.Text(), nullable=True), schema="s3")
    op.create_foreign_key(
        "journeys_sop_version_fkey", "journeys", "sop_versions",
        ["sop_version"], ["version"], source_schema="s3", referent_schema="s5",
    )
    op.execute(
        """
        update s1.runs r
           set sop_version = v.version
          from s5.sop_versions v
         where r.spec_json is not null
           and (r.spec_json::jsonb ->> 'sop') = v.version
        """
    )


def downgrade() -> None:
    op.drop_constraint("runs_sop_version_fkey", "runs", schema="s1")
    op.drop_column("runs", "sop_version", schema="s1")
    op.drop_constraint("journeys_sop_version_fkey", "journeys", schema="s3")
    op.drop_column("journeys", "sop_version", schema="s3")

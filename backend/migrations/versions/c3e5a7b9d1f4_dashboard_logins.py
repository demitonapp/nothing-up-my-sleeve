"""The dashboard's logins

13 November (Justin: "this page http://localhost:4321/orbitals/demiton should not show expeditions and liberty machine
unless i'm logged in. Happy using a username and password for now"). S5 policy 'postgres': a new kind of record starts
as a migration.

- `s5.dash_logins`: one row a person who may log in to the dashboard. The password is never kept, only its PBKDF2-SHA256
  hash, its salt and the iteration count. `secret` signs that person's session cookies (thorp/dash/auth.py), so setting a
  new password makes a new secret and every cookie signed with the old one stops working.

Revision ID: c3e5a7b9d1f4
Revises: b9d2e4f6a8c1
"""

from __future__ import annotations

from alembic import op

revision = "c3e5a7b9d1f4"
down_revision = "b9d2e4f6a8c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create table if not exists s5.dash_logins ("
        "username text primary key check (username ~ '^[A-Za-z0-9._-]{1,64}$'), "
        "salt bytea not null check (length(salt) >= 16), "
        "hash bytea not null check (length(hash) = 32), "
        "iterations integer not null check (iterations >= 200000), "
        "secret bytea not null check (length(secret) >= 32), "
        "set_at timestamptz not null default now())"
    )


def downgrade() -> None:
    op.execute("drop table if exists s5.dash_logins")

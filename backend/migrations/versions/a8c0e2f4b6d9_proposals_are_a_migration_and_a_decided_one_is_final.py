"""S5 proposals are a migration, and the database holds the rules Python stated

13 November (S5 policy "postgres"). `s5.proposals` was made at run time by `proposals.ensure()` because the Alembic head was
another session's uncommitted migration when it was written. It is chained here. The rules `proposals.py` stated in Python
become the table's: a proposal has a filer, a title and a question (not blank), a decided proposal has a time it was decided
and an open one has none, and a decided proposal is never reopened or changed (a trigger refuses the update, whoever sends it).

Revision ID: a8c0e2f4b6d9
Revises: f7b9d1e3a5c8
"""

from __future__ import annotations

from alembic import op

revision = "a8c0e2f4b6d9"
down_revision = "f7b9d1e3a5c8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "create table if not exists s5.proposals ("
        "id bigserial primary key, filed_at timestamptz not null default now(), filed_by text not null, "
        "area text not null default '', title text not null, asks text not null, why text not null default '', "
        "status text not null default 'open' check (status in ('open', 'signed', 'declined', 'withdrawn')), "
        "decided_at timestamptz, words text not null default '')"
    )
    op.execute("create index if not exists proposals_status on s5.proposals (status, filed_at desc)")
    op.execute(
        "alter table s5.proposals "
        "add constraint proposals_filed_by_not_blank check (btrim(filed_by) <> ''), "
        "add constraint proposals_title_not_blank check (btrim(title) <> ''), "
        "add constraint proposals_asks_not_blank check (btrim(asks) <> ''), "
        "add constraint proposals_decided_when_decided check ((status = 'open') = (decided_at is null))"
    )
    op.execute(
        "create function s5.proposals_decided_is_final() returns trigger language plpgsql as $$ "
        "begin "
        "if old.status <> 'open' then "
        "raise exception 'proposal % is already %: file a new one', old.id, old.status using errcode = '23514'; "
        "end if; "
        "return new; "
        "end $$"
    )
    op.execute(
        "create trigger proposals_decided_is_final before update on s5.proposals "
        "for each row execute function s5.proposals_decided_is_final()"
    )


def downgrade() -> None:
    op.execute("drop trigger if exists proposals_decided_is_final on s5.proposals")
    op.execute("drop function if exists s5.proposals_decided_is_final()")
    op.execute("alter table s5.proposals drop constraint if exists proposals_decided_when_decided")
    op.execute("alter table s5.proposals drop constraint if exists proposals_asks_not_blank")
    op.execute("alter table s5.proposals drop constraint if exists proposals_title_not_blank")
    op.execute("alter table s5.proposals drop constraint if exists proposals_filed_by_not_blank")

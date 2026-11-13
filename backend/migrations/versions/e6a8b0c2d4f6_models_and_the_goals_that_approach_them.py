"""Outside models as rows, the goals that approach them as a relation, and the goals' `shown` column

13 November (Justin: "this model card should show if there's an existing approach on a model ... the knockout goal related to
the TII Falcon tiny should be represented here but made secure in postgres with relations"; "ACID and all database stuff has to
occur in postgres"). Three additions, all in Postgres and all constrained there:

- `s4.models`: one row an outside model (its Hugging Face repository id), belonging to a house (`s4.labs`) by a foreign key.
- `s1.goal_models`: the relation between a goal (`s1.expedition_goals`) and a model, with the role the goal gives the model
  (`beat`: the goal is to beat it; `compare`: read beside it; `study`: taken apart) and a note. A goal that goes takes its
  links with it (cascade); a model that has a goal's link cannot be deleted (restrict).
- `s4.model_approaches`: the join the model cards read, a view, so no Python stitches four tables together.
- `s1.expedition_goals.shown`: a goal the page and the priority order no longer list but the record keeps (it was added at run
  time by thorp/expedition_goals.py, which no longer makes tables).

Revision ID: e6a8b0c2d4f6
Revises: d5f7a9c1e3b4
"""

from __future__ import annotations

from alembic import op

revision = "e6a8b0c2d4f6"
down_revision = "d5f7a9c1e3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("alter table s1.expedition_goals add column if not exists shown boolean not null default true")
    op.execute(
        "create table s4.models ("
        "id text primary key, "
        "lab_key text not null references s4.labs(key) on update cascade, "
        "name text not null, "
        "params bigint check (params is null or params > 0), "
        "url text not null default '', "
        "created_at timestamptz not null default now())"
    )
    op.execute("create index models_lab on s4.models (lab_key)")
    op.execute(
        "create table s1.goal_models ("
        "goal_id text not null references s1.expedition_goals(goal_id) on delete cascade, "
        "model_id text not null references s4.models(id) on delete restrict, "
        "role text not null check (role in ('beat', 'compare', 'study')), "
        "note text not null default '', "
        "linked_at timestamptz not null default now(), "
        "primary key (goal_id, model_id, role))"
    )
    op.execute("create index goal_models_model on s1.goal_models (model_id)")
    op.execute(
        "create view s4.model_approaches as "
        "select m.id as model_id, m.name as model_name, m.lab_key, l.country, m.params, m.url, "
        "gm.role, gm.note, g.goal_id, g.text as goal_text, g.status as goal_status, "
        "e.key as expedition_key, e.name as expedition_name "
        "from s4.models m "
        "join s4.labs l on l.key = m.lab_key "
        "join s1.goal_models gm on gm.model_id = m.id "
        "join s1.expedition_goals g on g.goal_id = gm.goal_id "
        "join s1.expeditions e on e.key = g.expedition_key "
        "where g.shown"
    )


def downgrade() -> None:
    op.execute("drop view if exists s4.model_approaches")
    op.execute("drop table if exists s1.goal_models")
    op.execute("drop table if exists s4.models")
    op.execute("alter table s1.expedition_goals drop column if exists shown")

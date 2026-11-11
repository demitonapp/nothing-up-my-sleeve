"""The newest value of every metric of every run, kept by the database itself

11 November (the architecture audit, item 7: "dashboard endpoints loop over every run"). /api/ships, /api/compare and
/api/bridge each read every run's whole metric history (16M rows at 197 runs) to find one number per name: the last
one. `s1.metric_latest` holds that number, one row a (run_id, name), with the step, value and ts of the metrics row
that is newest by (step, id), and that row's id (`metric_id`), so "not older than what is stored" is exact and a
delete knows whether it took the stored row.

Statement-level triggers on `s1.metrics` keep it, reading the statement's transition table:

- AFTER INSERT upserts, per (run_id, name), the newest row of the batch, only where it is not older than the stored
  one (a re-score at the same step is newer: its id is larger). A multi-row INSERT or a COPY costs one upsert.
- AFTER DELETE recomputes only the pairs whose stored row was deleted, from what is left in `s1.metrics` (one index
  probe a pair), and drops a pair with no rows left. So the fold (delete the leg's rows past its start, then insert
  the box's) leaves the table right: the delete falls back to the leg start, the insert brings the newest back.
- AFTER UPDATE does both (nothing updates metrics today; it is here so the table cannot drift if something does).
- AFTER TRUNCATE empties it (the test fixtures truncate the ledger).

The table starts empty: `thorp store latest` fills it from the history, once, after this migration (a long read of
s1.metrics that must not run inside the migration's transaction, which holds the trigger's lock). A side table
keyed by run_id with no foreign key: nothing here touches s1.runs, which the coordinator holds. Creating a trigger
takes SHARE ROW EXCLUSIVE on s1.metrics, which a trainer's insert conflicts with for an instant: lock_timeout first,
so a busy table fails this fast instead of queueing the trainer behind it.

Revision ID: z7u0v3w6x9y2
Revises: y6t9u2v5w8x1
"""

from __future__ import annotations

from alembic import op

revision = "z7u0v3w6x9y2"
down_revision = "y6t9u2v5w8x1"
branch_labels = None
depends_on = None

STATEMENTS = (
    """
create table if not exists s1.metric_latest (
    run_id text not null,
    name text not null,
    step bigint not null,
    value double precision not null,
    ts double precision not null,
    metric_id bigint not null,
    primary key (run_id, name)
)
""",
    """
create index if not exists metric_latest_metric_id on s1.metric_latest (metric_id)
""",
    """
create or replace function s1.metric_latest_put() returns trigger language plpgsql as $$
begin
    insert into s1.metric_latest as l (run_id, name, step, value, ts, metric_id)
    select distinct on (n.run_id, n.name) n.run_id, n.name, n.step, n.value, n.ts, n.id
    from new_rows n
    order by n.run_id, n.name, n.step desc, n.id desc
    on conflict (run_id, name) do update
        set step = excluded.step, value = excluded.value, ts = excluded.ts, metric_id = excluded.metric_id
        where (excluded.step, excluded.metric_id) >= (l.step, l.metric_id);
    return null;
end $$
""",
    """
create or replace function s1.metric_latest_gone() returns trigger language plpgsql as $$
begin
    -- only a pair whose stored latest row was deleted changes; it takes the newest row left, or goes
    with hit as materialized (
        select l.run_id, l.name from s1.metric_latest l join old_rows o on o.id = l.metric_id
    ), fresh as materialized (
        select h.run_id, h.name, m.step, m.value, m.ts, m.id from hit h
        cross join lateral (
            select x.step, x.value, x.ts, x.id from s1.metrics x
            where x.run_id = h.run_id and x.name = h.name
            order by x.step desc, x.id desc limit 1
        ) m
    )
    update s1.metric_latest l
        set step = f.step, value = f.value, ts = f.ts, metric_id = f.id
    from fresh f where l.run_id = f.run_id and l.name = f.name;
    delete from s1.metric_latest l using old_rows o where l.metric_id = o.id;
    return null;
end $$
""",
    """
create or replace function s1.metric_latest_changed() returns trigger language plpgsql as $$
begin
    -- an update is a delete of the old rows and an insert of the new (nothing updates metrics today)
    with hit as materialized (
        select l.run_id, l.name from s1.metric_latest l join old_rows o on o.id = l.metric_id
    ), fresh as materialized (
        select h.run_id, h.name, m.step, m.value, m.ts, m.id from hit h
        cross join lateral (
            select x.step, x.value, x.ts, x.id from s1.metrics x
            where x.run_id = h.run_id and x.name = h.name
            order by x.step desc, x.id desc limit 1
        ) m
    )
    update s1.metric_latest l
        set step = f.step, value = f.value, ts = f.ts, metric_id = f.id
    from fresh f where l.run_id = f.run_id and l.name = f.name;
    delete from s1.metric_latest l using old_rows o
        where l.metric_id = o.id
          and not exists (select 1 from s1.metrics x where x.id = o.id and x.run_id = l.run_id and x.name = l.name);
    insert into s1.metric_latest as l (run_id, name, step, value, ts, metric_id)
    select distinct on (n.run_id, n.name) n.run_id, n.name, n.step, n.value, n.ts, n.id
    from new_rows n
    order by n.run_id, n.name, n.step desc, n.id desc
    on conflict (run_id, name) do update
        set step = excluded.step, value = excluded.value, ts = excluded.ts, metric_id = excluded.metric_id
        where (excluded.step, excluded.metric_id) >= (l.step, l.metric_id);
    return null;
end $$
""",
    """
create or replace function s1.metric_latest_emptied() returns trigger language plpgsql as $$
begin
    delete from s1.metric_latest;
    return null;
end $$
""",
    """
create or replace trigger metric_latest_put after insert on s1.metrics
    referencing new table as new_rows for each statement execute function s1.metric_latest_put()
""",
    """
create or replace trigger metric_latest_gone after delete on s1.metrics
    referencing old table as old_rows for each statement execute function s1.metric_latest_gone()
""",
    """
create or replace trigger metric_latest_changed after update on s1.metrics
    referencing old table as old_rows new table as new_rows for each statement execute function s1.metric_latest_changed()
""",
    """
create or replace trigger metric_latest_emptied after truncate on s1.metrics
    for each statement execute function s1.metric_latest_emptied()
""",
)


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    for sql in STATEMENTS:
        op.execute(sql)


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    for t in ("metric_latest_put", "metric_latest_gone", "metric_latest_changed", "metric_latest_emptied"):
        op.execute(f"drop trigger if exists {t} on s1.metrics")
        op.execute(f"drop function if exists s1.{t}()")
    op.execute("drop table if exists s1.metric_latest")

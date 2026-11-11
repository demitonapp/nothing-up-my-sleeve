"""A run's state and expedition as rows, and the lanes as rows

11 November (the architecture audit, item 11: "expeditions, lanes and run status are hard-coded"). Three side tables,
all additive, none of them an ALTER of `s1.runs` (the live coordinator holds a lock on it):

- `s1.run_state` (run_id, state, reason, heartbeat_at, updated_at): one of six states with its reason in words and a
  heartbeat (thorp/run_state.py). Backfilled once from `s1.runs.status`, the reason the status's own words.
- `s1.run_expedition` (run_id, expedition, source, recorded_at): the expedition a run belongs to and where that was
  read: the spec's `expedition:` field, the label chain (fleet.expedition_of_label) or by hand. Backfilled once from
  the label chain for every run it places.
- `s2.lane_defs` (lane, kind, seats, shared_presets, resource_id, enabled, note): the coordinator's lanes as rows
  (lanes.py), seeded with today's two: mac (local, the seats `s2.lanes` holds, 300k may share) and vast (charter,
  one seat). The CHECK `lane_known` on `s2.lanes` is swapped for a foreign key to it, in a savepoint under the 5 s
  lock timeout: if `s2.lanes` cannot be locked (the live coordinator), the CHECK stays, the new table stays, and the
  swap waits for the coordinator to be in port (said on stdout).

No foreign key from the two run tables to `s1.runs`, for the same reason as `s1.run_provenance`.

Revision ID: b9w2x5y8z1a4
Revises: a8v1w4x7y0z3
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "b9w2x5y8z1a4"
down_revision = "a8v1w4x7y0z3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute(
        "create table if not exists s1.run_state ("
        "run_id text primary key, "
        "state text not null, "
        "reason text not null default '', "
        "heartbeat_at timestamptz, "
        "updated_at timestamptz not null default now(), "
        "constraint run_state_known check (state in ('running','finished','failed','stopped','recalled','lost')))"
    )
    op.execute("create index if not exists run_state_state on s1.run_state (state)")
    op.execute(
        "create table if not exists s1.run_expedition ("
        "run_id text primary key, "
        "expedition text not null, "
        "source text not null, "
        "recorded_at timestamptz not null default now(), "
        "constraint run_expedition_source check (source in ('spec','label','manual')))"
    )
    op.execute("create index if not exists run_expedition_expedition on s1.run_expedition (expedition)")
    op.execute(
        "create table if not exists s2.lane_defs ("
        "lane text primary key, "
        "kind text not null, "
        "seats integer, "
        "shared_presets text[] not null default '{}', "
        "resource_id text, "
        "enabled boolean not null default true, "
        "note text not null default '')"
    )
    op.execute(
        "insert into s2.lane_defs (lane, kind, seats, shared_presets, resource_id, enabled, note) values "
        "('mac', 'local', coalesce((select seats from s2.lanes where lane = 'mac'), 1), '{300k}', "
        "(select resource_id from s2.lanes where lane = 'mac'), true, "
        "'this Mac: every line not written for CUDA; a second seat only for 300k-scale lines'), "
        "('vast', 'charter', 1, '{}', (select resource_id from s2.lanes where lane = 'vast'), true, "
        "'a GPU hired from Vast.ai (thorp charter sail), one ship out') "
        "on conflict (lane) do nothing"
    )
    conn = op.get_bind()
    # a run row of every lane s2.lanes has must have its definition before the key can be checked
    conn.execute(
        text(
            "insert into s2.lane_defs (lane, kind, seats, note) select lane, 'local', seats, 'found in s2.lanes' "
            "from s2.lanes on conflict (lane) do nothing"
        )
    )
    try:
        with conn.begin_nested():
            conn.execute(text("alter table s2.lanes drop constraint if exists lane_known"))
            conn.execute(
                text(
                    "alter table s2.lanes add constraint lanes_lane_def foreign key (lane) "
                    "references s2.lane_defs (lane)"
                )
            )
        print("b9w2x5y8z1a4: s2.lanes.lane now references s2.lane_defs (the CHECK lane_known is gone)")
    except Exception as e:  # noqa: BLE001  (lock_timeout: the coordinator holds s2.lanes)
        print(
            "b9w2x5y8z1a4: s2.lanes could not be locked within 5 s, so its CHECK lane_known stays and the swap to "
            f"a foreign key waits for the coordinator to be in port ({e.__class__.__name__})"
        )
    # the backfill: the two new tables only, never over a row already there
    from thorp import run_state

    print(f"b9w2x5y8z1a4: backfilled {run_state.backfill(conn)}")


def downgrade() -> None:
    op.execute("SET LOCAL lock_timeout = '5s'")
    op.execute("alter table s2.lanes drop constraint if exists lanes_lane_def")
    op.execute(
        "do $$ begin if not exists (select 1 from pg_constraint where conname = 'lane_known') then "
        "alter table s2.lanes add constraint lane_known check (lane in ('mac', 'vast')); end if; end $$"
    )
    op.execute("drop table if exists s2.lane_defs")
    op.execute("drop table if exists s1.run_expedition")
    op.execute("drop table if exists s1.run_state")

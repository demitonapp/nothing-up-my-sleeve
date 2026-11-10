#!/bin/sh
# The standing queue (2026-11-06, 22:30), since 2026-11-08 run by the S2 coordinator in two lanes, this Mac and a
# GPU hired from Vast.ai (backend/thorp/viable/s2_coordination/lanes.py: the rules are there). The lines are as
# before: a spec under ships/specs (no .yaml), "cmd: <shell command>", and now "vast: <spec>" (sailed with
# `thorp charter sail`) and "wait: <voyage name>" (the Mac lane holds until that voyage docks). A line is removed
# when it starts and appended to ships/specs/queue-done.txt with its exit status.
# Log: data/runs/queue.out (redirect this script's output there, as before).
export THORP_LEDGER_PG=1 THORP_LIBRARY_PG=1 THORP_QUEUE_PG=1  # the one store (10 November); the files are exports
cd "$(dirname "$0")/../.." || exit 1  # the repository root: backend/, ships/, data/
# The venv's python directly, not `uv run`: under launchd uv's cache lock has failed with "Operation
# not permitted" on ~/.cache/uv/.tmp (10 November), and the coordinator must never depend on uv's cache.
PYTHONPATH=backend backend/.venv/bin/python -m thorp.viable.s2_coordination.lanes  # not exec: queue.sh stays the parent, so `pgrep -f queue.sh` still finds the queue

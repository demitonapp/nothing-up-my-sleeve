#!/bin/sh
# Restart the S2 coordinator from the queue, between voyages (11 November 2026, Justin: "we need to restart the
# coordinator when the 9m docks. can we schedule it in the queue").
#
#   thorp queue add "cmd: sh backend/scripts/restart_coordinator.sh" --top
#
# Why a restart: the coordinator is one long-lived process, so it runs the lanes.py it was started with, however
# the file has changed since, and it keeps whatever it held open. Why from the queue: the line is taken when the
# lane is free, so the restart falls between two voyages and not on top of one.
#
# What it does, in order:
#   1. waits for every voyage at sea when it starts (`python -m thorp.train ...`) to dock. A line runs in its own
#      session and a new coordinator adopts it, so a restart under a voyage should be safe, but nothing needs it.
#   2. checks that the code on disk loads (lanes and train). If it does not, the running coordinator is left as
#      it is: an old coordinator sailing the queue is better than a new one that cannot start.
#   3. stops the coordinator (SIGTERM). queue.sh then exits non-zero and launchd (com.thorp.queue, KeepAlive on
#      an unsuccessful exit) starts it again; the new coordinator adopts this line, and takes the next when this
#      script exits.
#   4. confirms a new coordinator is up. If launchd has not started one in 90 seconds it is asked to
#      (kickstart), and failing that queue.sh is started by hand, so the queue is never left without one.
#
# `--dry-run` does 2 and reports what 3 would stop; it waits for nothing and stops nothing.
# Log: data/runs/cmd-sh-backend-scripts-restart_coordinator.sh.out (the coordinator gives a cmd: its own log).

cd "$(dirname "$0")/../.." || exit 1
DRY=""
[ "$1" = "--dry-run" ] && DRY=1
say() { echo "[$(date +%H:%M:%S)] restart: $*"; }
coordinator() { pgrep -f "thorp.viable.s2_coordination.lanes" | head -1; }

# 1. the voyages at sea now: wait for these, and only these (the next line may start the moment they dock)
at_sea=$(pgrep -f -- "-m thorp.train" | tr '\n' ' ')
if [ -n "$at_sea" ] && [ -z "$DRY" ]; then
  say "waiting for the voyage(s) at sea to dock (pid $at_sea)"
  for pid in $at_sea; do
    while kill -0 "$pid" 2>/dev/null; do sleep 15; done
  done
  say "docked"
elif [ -n "$at_sea" ]; then
  say "dry run: would wait for pid $at_sea to dock"
fi

# 2. the code a new coordinator would start on
if ! err=$(THORP_LEDGER_PG=1 THORP_LIBRARY_PG=1 THORP_QUEUE_PG=1 PYTHONPATH=backend backend/.venv/bin/python -c \
  "import thorp.viable.s2_coordination.lanes, thorp.train" 2>&1); then
  say "the code on disk does not load; the running coordinator is left as it is"
  echo "$err" | tail -5
  exit 1
fi
say "the code on disk loads"

old=$(coordinator)
if [ -n "$DRY" ]; then
  say "dry run: would stop coordinator pid ${old:-none} and wait for launchd (com.thorp.queue) to start another"
  launchctl print "gui/$(id -u)/com.thorp.queue" 2>/dev/null | grep -E "^\s*(state|pid|last exit code) =" | sed 's/^[[:space:]]*/  /'
  exit 0
fi

# 3. stop it
if [ -n "$old" ]; then
  say "stopping coordinator pid $old"
  kill -TERM "$old"
else
  say "no coordinator was running"
fi

# 4. a new one must be up
up() { new=$(coordinator); [ -n "$new" ] && [ "$new" != "$old" ]; }
waited=0
while ! up && [ "$waited" -lt 90 ]; do sleep 5; waited=$((waited + 5)); done
if ! up; then
  say "launchd has not started a coordinator in 90 s; asking it to"
  launchctl kickstart "gui/$(id -u)/com.thorp.queue" 2>&1 | tail -1
  sleep 20
fi
if ! up; then
  say "still none; starting queue.sh by hand"
  nohup /usr/bin/caffeinate -dimsu /bin/sh backend/scripts/queue.sh >> data/runs/queue.out 2>&1 &
  sleep 20
fi
if up; then
  sleep 20  # a coordinator that dies on start-up is not one
  if up; then
    say "coordinator pid $new is up"
    exit 0
  fi
fi
say "NO COORDINATOR IS RUNNING: start it with 'launchctl kickstart gui/$(id -u)/com.thorp.queue'"
exit 1

#!/bin/sh
# The store (Postgres 17, the cluster under data/postgres on localhost:5433) under launchd, so it is up again
# after a restart of this Mac (12 November, Justin: "yes, set it up"). Until then it was started by hand, and
# after the macOS update at 19:35 the queue waited on "the store is not answering" until someone started it.
#
# If a postgres is already serving the cluster (started by hand, or by onboarding's pg_ctl), this script does
# not start a second one: it watches that one and exits non-zero when it stops, so launchd starts this
# script again and it then runs postgres itself. Postgres is exec'd, so launchd's SIGTERM at shutdown is
# postgres's own (a smart shutdown), and a crash (non-zero) is relaunched after the agent's ThrottleInterval.
# Log: data/postgres.log, as pg_ctl -l wrote it before.
cd "$(dirname "$0")/../.." || exit 1  # the repository root
PG=/opt/homebrew/opt/postgresql@17/bin
CLUSTER=data/postgres

pid=$(head -n 1 "$CLUSTER/postmaster.pid" 2>/dev/null)
if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null && ps -p "$pid" -o comm= | grep -q postgres; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') postgres.sh: postgres (pid $pid) is already serving $CLUSTER: watching it"
  while kill -0 "$pid" 2>/dev/null; do sleep 30; done
  echo "$(date '+%Y-%m-%d %H:%M:%S') postgres.sh: pid $pid has stopped: launchd starts the store again"
  exit 1
fi
exec "$PG/postgres" -D "$CLUSTER" -p 5433 -k /tmp -c listen_addresses=localhost

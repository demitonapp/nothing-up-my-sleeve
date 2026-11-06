#!/bin/sh
# The night's queue (2026-11-06, 22:00), the 9m rung's job first: spelling, punctuation and the
# statistical laws, with the traits that emerge while spelling is learned (DECISIONS.md, "The
# ladder"). Replaces queue_content.sh and the phase-2 re-score (queue_rescore.sh, dropped by Justin).
# (1) the bits-per-byte split and the laws for every finished 9m run; (2) the 9m tuning sweep
# (specs/9m-order.txt); (3) the content ships, then the traits ships. One GPU job at a time.
# Log: data/runs/queue-9m.out
cd "$(dirname "$0")/.." || exit 1
while pgrep -f "thorp run " >/dev/null || pgrep -f "thorp eval " >/dev/null; do
  sleep 30
done
echo "[$(date +%H:%M:%S)] the split and the laws for finished 9m runs"
for rid in $(uv run python -c "
import json
from thorp.ledger import Ledger
for r in Ledger().query(\"select run_id, spec_json from runs where status='finished' order by started\"):
    if json.loads(r['spec_json'])['model']['preset'] == '9m':
        print(r['run_id'])
"); do
  echo "[$(date +%H:%M:%S)] eval $rid"
  uv run thorp eval "$rid" --evaluators bpb_split laws > "data/runs/split-$rid.out" 2>&1
  echo "[$(date +%H:%M:%S)] $rid exited $?"
done
for s in $(cat specs/9m-order.txt) $(cat specs/content-order.txt) hundred-traits-v1 hundred-traits-v1-seed2 pool-400-traits-v1 pool-400-traits-v1-seed2; do
  echo "[$(date +%H:%M:%S)] starting $s"
  uv run thorp run specs/$s.yaml > "data/runs/$s.out" 2>&1
  echo "[$(date +%H:%M:%S)] $s exited $?"
done
echo "[$(date +%H:%M:%S)] queue finished"

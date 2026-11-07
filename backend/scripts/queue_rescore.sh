#!/bin/sh
# Phase 2 (2026-11-06): after the night's queue exits, re-score every finished run's final
# checkpoint on the v2 hole cards and the truths deck (ce_bpb, probes with their floors, and the
# curiosity ladder). Training rows are
# untouched; the new rows are keyed by set (hole-cards-v2, truths). One GPU job at a time.
# Log: data/runs/rescore.out
cd "$(dirname "$0")/../.." || exit 1  # the repository root: backend/, ships/, data/
while pgrep -f "backend/scripts/queue_next.sh" >/dev/null || pgrep -f "thorp run " >/dev/null; do
  sleep 60
done
echo "[$(date +%H:%M:%S)] queue done; re-scoring finished runs"
for rid in $(uv run --project backend python -c "
from thorp.ledger import Ledger
for r in Ledger().query(\"select run_id from runs where status='finished' order by started\"):
    print(r['run_id'])
"); do
  echo "[$(date +%H:%M:%S)] eval $rid"
  uv run --project backend thorp eval "$rid" --sets ships/lists/hole-cards-v2.csv ships/lists/truths.csv \
    --evaluators ce_bpb probes curiosity > "data/runs/rescore-$rid.out" 2>&1
  echo "[$(date +%H:%M:%S)] $rid exited $?"
done
echo "[$(date +%H:%M:%S)] re-score finished"

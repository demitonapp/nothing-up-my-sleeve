#!/bin/sh
# The night's second queue (2026-11-06): after the night queue and the re-score, the fifteen content
# ships (specs/content-order.txt: each shelf's first ship before any shelf's second), then the four
# kinks-against-traits ships. One GPU job at a time. Log: data/runs/queue-content.out
cd "$(dirname "$0")/.." || exit 1
while pgrep -f "scripts/queue_next.sh" >/dev/null || pgrep -f "scripts/queue_rescore.sh" >/dev/null || pgrep -f "thorp run " >/dev/null || pgrep -f "thorp eval " >/dev/null; do
  sleep 60
done
for s in $(cat specs/content-order.txt) hundred-traits-v1 hundred-traits-v1-seed2 pool-400-traits-v1 pool-400-traits-v1-seed2; do
  echo "[$(date +%H:%M:%S)] starting $s"
  uv run thorp run specs/$s.yaml > "data/runs/$s.out" 2>&1
  echo "[$(date +%H:%M:%S)] $s exited $?"
done
echo "[$(date +%H:%M:%S)] queue finished"

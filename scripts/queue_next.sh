#!/bin/sh
# The night's queue (2026-11-06): wait for the seed-2 run and the pool fetch, cut the pool, then
# run the six next specs one after another so no two share the GPU. Log: data/runs/queue.out
cd "$(dirname "$0")/.." || exit 1
while pgrep -f "thorp run specs/hundred-by-reach-v1-seed2" >/dev/null || pgrep -f "thorp fetch lists/pool-draft" >/dev/null; do
  sleep 30
done
echo "[$(date +%H:%M:%S)] seed-2 and the fetch are done; cutting the pool"
uv run python scripts/cut_pool.py 400 100 || exit 1
for s in pool-400-v1 pool-400-fiction-v1 pool-400-nonfiction-v1 pool-400-v1-seed2 pool-400-fiction-v1-seed2 pool-400-nonfiction-v1-seed2; do
  echo "[$(date +%H:%M:%S)] starting $s"
  uv run thorp run specs/$s.yaml > "data/runs/$s.out" 2>&1
  echo "[$(date +%H:%M:%S)] $s exited $?"
done
echo "[$(date +%H:%M:%S)] queue finished"

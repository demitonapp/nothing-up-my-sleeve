#!/bin/sh
# Score every finished Thorp run's latest checkpoint on the unseen deck (lists/hole-cards-unseen.csv),
# for the comparison with Qwen (DECISIONS.md, "Thorp against Qwen"). Log: data/runs/unseen-<run>.out
cd "$(dirname "$0")/.." || exit 1
for rid in $(uv run python -c "
from thorp.ledger import Ledger
for r in Ledger().query(\"select run_id from runs where status='finished' order by started\"):
    print(r['run_id'])
"); do
  uv run thorp eval "$rid" --sets lists/hole-cards-unseen.csv --evaluators ce_bpb > "data/runs/unseen-$rid.out" 2>&1
  echo "unseen $rid exited $?"
done

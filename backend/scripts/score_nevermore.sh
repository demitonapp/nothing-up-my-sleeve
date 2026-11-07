#!/bin/sh
# Score every finished 1m and 9m run's last checkpoint for Nevermores (induction heads), once
# (2026-11-07). Log: data/runs/nevermore-<run>.out
cd "$(dirname "$0")/../.." || exit 1  # the repository root: backend/, ships/, data/
for rid in $(uv run --project backend python -c "
import json
from thorp.ledger import Ledger
for r in Ledger().query(\"select run_id, spec_json from runs where status='finished' order by started\"):
    if json.loads(r['spec_json'])['model']['preset'] in ('1m', '9m'):
        print(r['run_id'])
"); do
  uv run --project backend thorp eval "$rid" --evaluators nevermore > "data/runs/nevermore-$rid.out" 2>&1
  echo "nevermore $rid exited $?"
done

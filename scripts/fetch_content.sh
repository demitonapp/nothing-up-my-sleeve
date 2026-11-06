#!/bin/sh
# Fetch the content experiment's lists one after another (2026-11-06). Log: data/runs/fetch-content.out
cd "$(dirname "$0")/.." || exit 1
for l in content-islamic-draft content-greek-draft content-renaissance-draft content-about-draft content-random-1-draft content-random-2-draft content-random-3-draft; do
  echo "[$(date +%H:%M:%S)] $l"
  uv run thorp fetch lists/$l.csv | tail -1
done
echo "[$(date +%H:%M:%S)] fetch done"

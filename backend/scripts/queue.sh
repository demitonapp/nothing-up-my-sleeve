#!/bin/sh
# The standing queue (2026-11-06, 22:30): runs the specs named in ships/specs/queue.txt, one at a time,
# taking the first line each time, so the file can be edited while the queue runs (add, remove or
# reorder lines; blank lines and lines starting with # are skipped). A line is removed when its run
# starts and appended to ships/specs/queue-done.txt with its exit status. A line "cmd: <shell command>"
# runs that command instead of a spec (an outside-model score, a re-score), still one at a time.
# Log: data/runs/queue.out
cd "$(dirname "$0")/../.." || exit 1  # the repository root: backend/, ships/, data/
while :; do
  while pgrep -f "thorp run " >/dev/null || pgrep -f "thorp eval " >/dev/null; do
    sleep 30
  done
  s=$(grep -v '^[[:space:]]*\(#\|$\)' ships/specs/queue.txt | head -n 1)
  [ -z "$s" ] && break
  awk -v s="$s" 'done || $0 != s { print; next } { done = 1 }' ships/specs/queue.txt > ships/specs/queue.txt.tmp && mv ships/specs/queue.txt.tmp ships/specs/queue.txt
  echo "[$(date +%H:%M:%S)] starting $s"
  case "$s" in
    cmd:*) sh -c "${s#cmd:}"; code=$? ;;
    *) mkdir -p "$(dirname "data/runs/$s.out")"  # a voyage's log folder is made here, never forgotten (7 Nov: twice)
       uv run --project backend thorp run "ships/specs/$s.yaml" > "data/runs/$s.out" 2>&1; code=$? ;;
  esac
  echo "[$(date +%H:%M:%S)] $s exited $code"
  echo "$(date +%Y-%m-%dT%H:%M:%S) $s $code" >> ships/specs/queue-done.txt
done
echo "[$(date +%H:%M:%S)] queue empty"

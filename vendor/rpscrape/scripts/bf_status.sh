#!/usr/bin/env bash
# Quick status of the Betfair prefetch: log tail, cache row counts, proc state.
C=/home/gabriel/projects/racing_project/vendor/rpscrape/.cache/betfair
echo "=== log ==="
tail -n 12 /home/gabriel/projects/racing_project/output/pull_logs/betfair_prefetch.log
echo "=== caches ==="
for f in 2024_01_01_2024_12_31 2025_01_01_2025_12_31 2026_01_01_2026_06_19; do
  P="$C/$f.csv"
  if [ -f "$P" ]; then
    echo "$f: $(($(wc -l < "$P") - 1)) rows, $(du -h "$P" | cut -f1)"
  else
    echo "$f: (not yet)"
  fi
done
echo "=== proc ==="
ps -o etime,time,cmd -C python 2>/dev/null | grep -i prefetch || echo "PROC DONE (no python prefetch running)"

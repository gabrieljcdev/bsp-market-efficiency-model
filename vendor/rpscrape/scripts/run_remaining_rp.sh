#!/usr/bin/env bash
# Phase B (run VPN-ON, NL exit): RP scrape all remaining years, chained.
# Each year reads BSP from its pre-seeded Betfair cache (Phase A) and is
# resume-aware with retries via run_year_rp.sh. Runs straight through.
set -u
cd "$(dirname "$0")"
ROOT="$(cd ../../.. && pwd)"
LOG="$ROOT/output/pull_logs/remaining_rp.log"
mkdir -p "$ROOT/output/pull_logs"
: > "$LOG"

# range  filename
YEARS="
2024/01/01-2024/12/31 2024_01_01_2024_12_31
2025/01/01-2025/12/31 2025_01_01_2025_12_31
2026/01/01-2026/06/19 2026_01_01_2026_06_19
"

echo "=== remaining RP scrape start $(date -u +%FT%TZ) ===" >> "$LOG"
echo "$YEARS" | while read -r range name; do
  [ -z "${name:-}" ] && continue
  echo ">>> $name start $(date -u +%FT%TZ)" >> "$LOG"
  bash run_year_rp.sh "$range" "$name" >> "$LOG" 2>&1
  echo ">>> $name finished $(date -u +%FT%TZ)" >> "$LOG"
done
echo "=== remaining RP scrape done $(date -u +%FT%TZ) ===" >> "$LOG"

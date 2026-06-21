#!/usr/bin/env bash
# Year-by-year GB results pull, 2018->present, with auto-refresh auth and BSP.
# Uses date-range mode (no --type needed; captures all race types in one file).
# Runs unattended: each year logs to its own file; a one-line summary is
# appended to the progress log after each year. A failing year is logged and
# skipped rather than aborting the whole run.
set -u

ROOT="$HOME/projects/racing_project"
cd "$ROOT/vendor/rpscrape/scripts" || exit 1

PY="$ROOT/.venv313/bin/python"
DATADIR="$ROOT/vendor/rpscrape/data/region/gb/all"
LOGDIR="$ROOT/output/pull_logs"
PROG="$ROOT/output/gb_pull_progress.log"
mkdir -p "$LOGDIR"

# Force refresh-token-driven auth (ignore any stale ACCESS_TOKEN in .env).
export ACCESS_TOKEN=""

# Years to pull (override via YEARS env var for partial re-runs).
YEARS="${YEARS:-2018 2019 2020 2021 2022 2023 2024 2025 2026}"

# Append to the progress log (do not wipe prior runs' record).
echo "=== PULL START $(date -u +%FT%TZ) [$YEARS] ===" >> "$PROG"

MAX_ATTEMPTS=6

for Y in $YEARS; do
    START="$Y/01/01"
    if [ "$Y" = "2026" ]; then
        END="2026/06/18"   # present
    else
        END="$Y/12/31"
    fi
    # date-range output filename: YYYY_MM_DD_YYYY_MM_DD.csv
    OUT="$DATADIR/$(echo "${START}_${END}" | tr '/' '_').csv"

    # Retry-until-success per year. Resume (per-day progress + cached Betfair +
    # cached URL list) makes each retry skip everything already done, so a
    # transient crash/throttle costs little. Append to the log across attempts.
    attempt=0
    rc=1
    while [ "$rc" -ne 0 ] && [ "$attempt" -lt "$MAX_ATTEMPTS" ]; do
        attempt=$((attempt + 1))
        echo "--- YEAR $Y ($START-$END) attempt $attempt start $(date -u +%FT%TZ) ---" >> "$PROG"
        timeout 36000 "$PY" rpscrape.py -d "$START-$END" -r gb >> "$LOGDIR/scrape_$Y.log" 2>&1
        rc=$?
        echo "--- YEAR $Y attempt $attempt exit=$rc $(date -u +%FT%TZ) ---" >> "$PROG"
        if [ "$rc" -ne 0 ] && [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
            sleep 60   # let any throttle clear before resuming
        fi
    done
    "$PY" "$ROOT/vendor/rpscrape/year_summary.py" "$Y" "$OUT" >> "$PROG" 2>&1
done

echo "=== PULL DONE $(date -u +%FT%TZ) ===" >> "$PROG"

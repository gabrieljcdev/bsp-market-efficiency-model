# Systematic Racing Project — Build Bundle

Handoff bundle for Claude Code. Goal of the wider project: a British-racing
fundamental model, blended with market price, validated by **beating the
Betfair Starting Price (BSP) out of sample, net of commission** (CLV).
This bundle contains the benchmark-pipeline starting point plus vendored
reference code.

## What's here

```
racing_project/
├── parsers/
│   └── parse_bsp.py          ← WORKING. Betfair stream file -> BSP table (CSV)
├── backtest/                 ← empty. NEXT: CLV harness (struck price vs BSP)
├── features/                 ← empty. LATER: sectional / pedigree edge features
├── data/
│   ├── historical/           ← drop real Betfair ADVANCED .tar files here
│   └── samples/
│       ├── make_sample.py     ← generates a synthetic stream file
│       ├── sample_market_*.jsonl(.bz2)  ← synthetic test fixture
│       └── real_format_fixtures/        ← 2 GENUINE Betfair stream files
│                                           (greyhound mkts, format-test only)
├── output/
│   └── bsp_table.csv          ← parser output
└── vendor/
    ├── rpscrape/              ← Racing Post scraper (RPR, Topspeed, form) — OSS
    └── autoHubTutorials/      ← Betfair Down Under tutorials (trimmed)
```

## parse_bsp.py — status: validated

Reads a Betfair "Stream" historical file (plain or .bz2), tracks market
definitions across packets, and emits one row per runner with:
`market_id, selection_id, venue, market_time, country, market_type,
runner_status, bsp, last_preoff_ltp, total_volume, bsp_reconciled`.

Tested on both the synthetic fixture and a real Betfair file (correctly
extracted 8 runners + reconciled BSPs). Run:
```
python3 parsers/parse_bsp.py [path_to_stream_file]
```
Note: real files in real_format_fixtures are eventTypeId 4339 (greyhounds).
Horse racing is eventTypeId 7 — add an event-type filter for production.
For real ADVANCED data, files are bz2 stream files inside a .tar; iterate
the tar members and feed each to `parse_stream()`.

## vendor/ — reference code (not pip packages)

- **rpscrape** (joenano): free RP form/ratings; cross-validation layer.
- **autoHubTutorials** (Betfair Down Under), trimmed from 219M to ~24M.
  Most relevant folders:
    - `backtestRatings`        — backtest ratings vs BSP (our CLV cross-check)
    - `analysingAndPredictingBSP`
    - `processingTarFiles101`  — real .tar iteration
    - `jsonToCsv` / `jsonToCsvRevisited` — fast parsing path
    - `automatedBettingAngles`, `stakingMethodsAndBankrollManagement`
  The heavy `howToAutomate/sample_monthly_data_output` dump was removed;
  2 sample market files were retained under data/samples/real_format_fixtures.

## NOT included — you must source these

- **Betfair Historical ADVANCED files** — the real closing-line/BSP source.
  Buy per period from the Betfair historical data site. Nothing public
  substitutes for the real line.

## Suggested next steps

1. `backtest/clv.py` — join a table of struck prices to bsp_table, compute
   `struck/bsp - 1` per bet, aggregate mean CLV and % beating BSP, net of a
   configurable commission (default 5%). This is the project's core metric.
2. Extend parser to walk real .tar archives + filter eventTypeId == 7.
3. Begin `features/` with the Tier-1 edge layer (sectional/pace, sire profiles).

## Python deps

See requirements.txt. Core: betfairlightweight, betfair_data,
betfairdatabase, flumine (execution/backtest framework), pandas.

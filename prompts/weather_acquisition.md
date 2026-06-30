# CC Brief — Weather Data Acquisition

**For: Claude Code, working in `~/projects/racing_project` with `.venv` active.**
**Goal:** acquire free historical weather (+ visibility, + air quality as a
separate probe) for every GB race in the joined dataset, build the weather-derived
feature families, and score them on the metric that actually matters — **blend
weight + drift, NOT Brier.** Zero spend (Open-Meteo free tier, no API key).

Read `PROJECT_NOTES.md`, `Free_Experiment_Catalogue.md` (governing principle +
leakage discipline), and `Feature_Catalogue` first. Work block by block. After
each block, **stop and report** (row counts, a sample, anomalies) before moving
on. Do not run the whole thing unattended.

---

## Why this brief is hedged before it starts (read this — it governs the work)

The 21 Jun result proved: public, *predictive* features are fully priced. Rolling
form / handicap / speed figures each improved standalone Brier but the blend
down-weighted them (3% → 1.5%), drift unchanged. **Weather is a public feature** —
the published GOING LINE is the market's own summary of recent weather, already in
the price. So raw weather, fed in as main effects, will almost certainly come back
PRICED like everything else.

The ONE thing worth chasing: **going-shift vs declared going** — the gap between
what the weather since declaration implies the ground has done and the stale
published going. The Feature Catalogue rates this *lightly* priced. Everything
else in this brief is feedstock for that, or a low-prior exploratory probe.

**This means the single most important step is Block 0**, not the fetch. If the
data that makes the going-shift feature possible does not exist, the whole
acquisition collapses to "another fully-priced input" and we stop. Do Block 0
first and report before touching any API.

---

## Guardrails (important)

- **No betting, no live endpoints.** Data download + local processing only.
- **Metric discipline (non-negotiable):** every weather feature is scored on
  Brier **AND blend weight AND drift**, read together (per Free Experiment
  Catalogue cross-cutting rules). A Brier gain with no blend-weight rise is not a
  result. Do not report a weather feature as promising on Brier alone.
- **Leakage discipline (non-negotiable):** every feature computed strictly from
  pre-race information. Weather AT or AFTER the off is post-race — only use weather
  up to a defined pre-off cutoff. Anchor any new feature against the or (−0.13,
  pre-race) / rpr (−0.88, post-race) within-race finishing-position test. A
  feature that suddenly looks great + blend weight spikes = suspect a leak first.
- **BSP/WAP stays the benchmark, never a model input.** Weather features go in the
  feature table only.
- **Be polite to the API:** Open-Meteo free tier is rate-limited. One call per
  course-day, cache, sleep between calls, back off on 429.
- Explain each step briefly before running it; surface anything surprising.

---

## Block 0 — Audit & blocker check (DO THIS FIRST, then stop)

The going-shift feature needs to know **what the declared going was and WHEN it
was declared**, so weather *after* declaration can be turned into an implied
ground-change the stale published going hasn't caught up to.

1. **Declared-going timestamps.** Search the joined data and the raw form source
   for: declared/official going, going-stick readings, AND any timestamp or
   "going updated" field. rpscrape going is typically a single race-day string
   with no declaration time. Confirm whether ANY temporal going information exists.
2. **GIS / Met layer.** Confirm there is no existing Met Office or ground-condition
   layer already in the project (29 Jun-am notes say none — verify).
3. **Backtest window vs source coverage.** Note the dataset's full date span
   (2018–2026 per notes) for the coverage check air quality will fail in Block 3.

**Report — and WAIT for a decision:**
- Do historical declared-going timestamps exist? (yes / no / partial)
- If **NO/partial:** the going-shift feature is not buildable as specified; it
  collapses to raw weather. State this plainly. The user decides whether to
  proceed with the reduced (raw-weather + visibility + AQ probe) scope or stop.
- **Do not proceed to Block 1 until the user responds to Block 0.**

---

## Block 1 — Course geolocation table

Build `data/weather/course_coords.py` (or `.csv`): every GB course in the joined
data → (lat, lon). A scaffold already exists in the project outputs
(`course_coords.py`, ~60 GB courses with a normalise/lookup helper) — start from
it, do not rebuild from scratch.

1. Extract the distinct course strings actually present in the joined CSV.
2. Map each to coordinates; log any course with no coordinate match.
3. Handle source naming quirks (e.g. "Newmarket (July)" vs "Newmarket",
   all-weather suffixes, "Bangor-on-Dee").

**Report:** count of distinct courses, count matched, and the list of any
unmatched course strings (so the user can supply aliases).

---

## Block 2 — Weather + visibility fetch

Source: **Open-Meteo Historical (ERA5 / ERA5-Land reanalysis)** — free, no key,
hourly, full archive, `archive-api.open-meteo.com/v1/archive`, `timezone=Europe/London`.

1. One API call per **(course, date)** — covers all races that day at that course;
   the per-race off-time selects the hour. Cache, sleep, back off on 429.
2. **Hourly variables (Core + visibility):**
   `temperature_2m, relative_humidity_2m, dew_point_2m, precipitation,
   wind_speed_10m, wind_gusts_10m, wind_direction_10m, surface_pressure,
   visibility`.
   (dewpoint and gusts kept — cheap, and feed the fog/abandonment mechanism.)
3. **Antecedent rainfall** for the going-shift feedstock: also pull the **7 days
   prior** to each race date at each course and aggregate (sum precip 24h / 72h /
   7d before the off). This is the physical driver of ground softening.
4. Join at **race level** on course × off-hour (nearest available hour). Prefix all
   weather columns `wx_`. Output `data/weather/weather_by_race.csv` and a merged
   `data/joined/joined_gb_weather.csv`.

**Visibility mechanism (real, unlike most weather):** low visibility / fog →
inspections, delays, abandonments, and genuinely affects running. Keep
`wx_visibility` and derive a simple fog flag (e.g. visibility < 1000 m).

**Report:** unique course-days fetched, runner rows that got weather (target =
all of them), a 5-row sample, and any course-days the API returned empty.

---

## Block 3 — Air quality (SEPARATE file, low-prior probe, extra caution)

Source: **Open-Meteo Air Quality API** (CAMS). Pull a full panel + pollen:
`pm10, pm2_5, nitrogen_dioxide, ozone, sulphur_dioxide, carbon_monoxide`,
plus `alder/birch/grass/ragweed pollen` where available.

**Caveats to enforce, not bury:**
- **Coverage:** detailed CAMS history only runs ~2022+, which **clips roughly half
  the 2018–2026 backtest window.** Any AQ result is on a shorter sample — flag this
  in the output and in the report.
- **No documented mechanism.** Unlike going/visibility, there is no racing-physics
  reason AQ predicts results. This is a weak-prior exploratory probe ONLY.
- Keep it in a **separate file** (`data/weather/air_quality_by_race.csv`), do NOT
  merge into the main weather join. It must not contaminate the going-shift work.

**Report:** AQ coverage date range vs dataset range (how much window is lost),
rows fetched, a sample. Label the whole block exploratory.

---

## Block 4 — Weather feature families

Build features in `features/build_weather.py`, in five families, each through the
full leakage proof. **The going-shift family is the only one with a real prior;**
the rest are documented-but-tempered.

1. **Going-shift (the target — only if Block 0 cleared).** Implied ground change
   from antecedent rainfall + evaporation (temp/wind/humidity) since declaration,
   vs the published going. The orthogonal candidate.
2. **Going-suitability × today's *implied* going.** Reuse the Test-3 interaction
   pattern (horse's prior strike-rate on a going band) but keyed to the
   weather-implied band, not just the declared band. Varies within race → survives
   conditional logit.
3. **Raw weather main effects** (temp, wind, pressure, humidity). EXPECTED PRICED —
   include only as the control that proves the going-shift feature (if any) beats
   raw weather. These are race-constant → cancel in conditional logit on their own;
   only their horse-level interactions are identifiable.
4. **Wind × draw / wind × run-style.** Headwind/tailwind on the straight by course
   orientation × draw. Speculative; varies within race so it is testable.
5. **Visibility / fog flag** (from Block 2) — race-level, mechanism-backed.

For each feature: run the or/rpr anchor test, run-by-run trace, debut-null,
no-backfill — before trusting it.

**Report:** the feature list, the leakage-trace result for each (anchor
correlations vs or/rpr), and any feature that tripped the leak alarm.

---

## Block 5 — Join, score, verdict

1. Merge the weather feature table into the existing modelling table on the
   leakage-safe race key.
2. Re-run the existing **Stage-1 → blend → three-metric** harness with the weather
   features added, **inside the holdout structure** (train 2018–2023 / val 2024 /
   holdout 2025–2026 — touch holdout once). Also run **segmented** (low-class,
   low-liquidity, large-field, AW, midweek — the pre-registered segments) since
   that is where any weather edge would concentrate if anywhere.
3. **Read all three metrics together:** Brier (resolution), **blend weight
   (orthogonality)**, **drift (side of the informed move)**. Apply the min-cell-size
   (≥~2,000 selections) and holdout-survival rules.

**Report — the verdict:**
- Pooled: did any weather feature earn a non-trivial blend weight, or did it price
  out like the rolling features did on 21 Jun?
- Segmented: any segment where weather features lift blend weight or flip drift to
  the right side of the move?
- Rule-in / rule-out per feature family, and append the result to the Free
  Experiment Catalogue learnings log.

---

## Done = the going-shift question is answered

The acquisition succeeds if it gives a clean verdict on the ONE feature with a
prior (going-shift vs declared going) on the metric that matters (blend weight +
drift, not Brier). A clean "priced out" is a real result — it removes weather from
the free hypothesis space and moves the project one step closer to the paid Tier-1
decision (TPD sectionals, pedigree) made from a position of having proven the free
space is exhausted.

Stop after Block 5 and report the verdict. Do not start live execution or staking.
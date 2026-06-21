# CC Brief — Phase 3: Free Edge-Feature Proxies (Pace, Race-Shape, Sire)

**For: Claude Code, working in `~/projects/racing_project` with `.venv` active,
launched from a NATIVE WSL shell (see Block 0).**

**Goal:** build the best *free* proxies for the Tier-1 edge features
(pace/running-style, race-shape, sire aptitude), then re-fit the two-stage
model and read ONE number — did Stage-1's model weight in the Benter blend move
off ~3%? That answer decides whether the paid data (TPD sectionals, Weatherbys
pedigree) is worth buying. **This phase is a cheap test of an expensive
decision, not an attempt to beat BSP.**

Read first for context: `PROJECT_NOTES.md`, `Day_Summary_18Jun.md`,
`Feature_Catalogue.docx` (§3 pace, §4 pedigree), `Data_Sources_Reference.docx`,
`models/stage1_logit.py`, `models/stage2_blend.py`. Work block by block. After
each block, STOP and report (row counts, a sample, any errors) before moving on.
Do not run the whole thing unattended.

---

## Guardrails (important)

- **Concept-then-code.** The USER understands each piece before you build it.
  Briefly explain what a script does and surface anything surprising. Do not
  hand off a feature the user can't explain back.
- **No bets, no live betting endpoints.** Data download and local processing
  only. Credentials are entered by the USER; never store passwords in plain
  text. `.env` stays git-ignored.
- **AS-OF-DATE IS THE CARDINAL RULE THIS PHASE.** Every feature for a race on
  date D may use ONLY data from strictly before D. This is the `rpr` leakage
  trap in a new costume — sneakier here because features are AGGREGATES, so a
  single leaked future race contaminates a whole sire/track/horse stat. Build
  leakage detection as a unit test (see Block B), do not just hope.
- **Do NOT build a fake sectional model.** We do NOT have GPS timing splits.
  Running style is a position-derived PROXY — direction (front/closer), not
  magnitude (closing %). Label it as such. Engineering a "sectional figure"
  from finishing positions would be self-deception.
- **BSP stays the benchmark, never an input.** Sept-2025 BSP is for scoring
  only. Older races (2018–Aug 2025) are FEATURE FUEL, never scoring rows.
- **CLV is NOT the verdict this phase.** It's still on the LTP stand-in and
  can't be trusted as the answer. The real readouts are the Stage-1 MODEL
  WEIGHT in the blend and the PROPER SCORES (Brier/log-loss) vs BSP.

---

## Pre-set decisions (don't stall asking — use these defaults)

Two judgment calls will come up mid-build. Defaults are set; flag if the data
makes them look wrong, but don't block on them.

- **2020 COVID gap.** British racing was suspended ~mid-Mar to early-Jun 2020,
  then ran behind closed doors. DEFAULT: keep 2020 data, do NOT special-case
  it, but PRINT a races-per-month count so the gap is visible. Behind-closed-
  doors racing had no crowd-pace dynamics worth modelling separately at this
  resolution — note it, move on.
- **Sire-sample threshold.** A sire going/distance win-rate is junk on a tiny
  progeny sample. DEFAULT: require at least 30 prior progeny runs in the
  relevant going/distance band before emitting a non-null stat; below that,
  null (and let the model treat it as missing, as it already does for `or`).
  Report how many runners clear the bar at 30; if coverage is poor, the user
  may relax it — surface the number, don't silently change the threshold.

---

## Block 0 — Fix the WSL path (~10 min, do FIRST)

Per the open issue in `PROJECT_NOTES.md`, CC has been running via a Windows UNC
path (`pwd` → `//wsl.localhost/...`), the slow boundary path.

- USER: open WSL-connected VS Code (green `WSL: Ubuntu-22.04` badge) → new WSL
  terminal → `cd ~/projects/racing_project`.
- Confirm `pwd` returns `/home/gabriel/projects/racing_project` with NO
  `//wsl.localhost/` prefix.
- `source .venv/bin/activate` → check for `(.venv)` → relaunch `claude`.

**Report:** `pwd` output confirming the native path.

---

## Block A — Deep history scrape (BACKGROUND — days, not minutes)

This is the long part. "Takes a long time" is fine and expected — rpscrape is
rate-limited and we are pulling years. Be gentle.

**Concept (explain to user first):** history depth ≠ scoring rows. We scrape
2018→present so that each Sept-2025 runner has a backward record to compute
features from. The scored set stays Sept-2025 only.

- Scrape GB results 2018→present, BOTH flat and jumps (remember: for jumps the
  `-y` year is the SEASON START). Cap at 2018 deliberately — older free data is
  patchier and tracks change (drainage/rail/surface), a form of staleness.
- **Flag the 2020 COVID gap** (suspended racing / behind-closed-doors) — note
  it, do not try to fix it.
- Capture per past run, at minimum: date, course, race time, distance, class,
  going, finishing position, IN-RUNNING position if available, jockey, trainer,
  sire, dam, headgear/wind-op flags, horse id/race id if present.
- Scrape a SMALL window first (a few days) to confirm columns before the long
  pull. Save under `data/form_history/`.

**Report:** rows per year; the column list; median prior-runs-per-runner for
the Sept-2025 set; count of zero-history runners (debutants — flagged for the
sire feature, which is exactly where they get priced).

---

## Block B — The windowing engine (~2 hrs, the conceptual core)

**Concept first:** as-of-date; the two window types (structural = long,
~2018→D; form/style = short rolling, ~last 12–18 months or last N runs, up to
D); why one leaked future race poisons an aggregate.

Build a REUSABLE as-of feature builder: given a race date D and a runner (and
sire/track as needed), it returns features computed from prior data ONLY. Build
it once, correctly; every feature in Blocks C–D plugs into it.

**Leakage unit test (required, like `backtest/test_clv.py`):** assert that
recomputing a feature WITH future races included changes the value, and that
the production path EXCLUDES them. Make leakage detection a passing test, not a
hope.

**Report:** the engine's interface, and the passing leakage test output.

---

## Block C — Running style + pace map (~2 hrs)

**Concept first:** style tag = direction-only proxy for sectionals (front/
prominent/midfield/hold-up from historical early positions, short rolling
window). Pace map = the relational prize: count projected front-runners per
race; a lone front-runner (uncontested lead) is undervalued, a contested pace
(meltdown) sets up closers. Pace-draw interaction = draw value conditional on
pace.

- Compute per-horse running-style tag via the Block B engine (short window,
  as-of-D).
- Compute per-race pace-pressure (count/share of front-runners) and a
  pace-draw interaction column, joined to the Sept-2025 runner rows.

**Checkpoint — the DESCRIPTIVE gate before any modelling:** does a lone front-
runner show a higher raw win rate than a contested-pace front-runner? Print the
raw win rates. If the signal isn't visible by eye, modelling won't conjure it —
report that as a FINDING, not a failure.

**Report:** style distribution; the raw-win-rate table; 3 eyeballed front-
runners.

---

## Block D — Sire going/distance proxy (~90 min)

**Concept first:** aggregate progeny results WE scraped ourselves — this sire's
runners' win-rate by going band and distance band, long window, as-of-D. Crude
vs Weatherbys stamina indices, but the right DIRECTION. Most valuable for
lightly-raced horses and debutants where the market has little form to price.

- Compute sire going-profile and distance-profile via the Block B engine
  (long window, as-of-D), joined per runner. Require a minimum progeny sample
  before emitting a non-null stat (note the threshold chosen).

**Report:** coverage (runners with a non-null sire stat at adequate sample);
debutant coverage specifically.

---

## Block E — Re-fit, re-blend, read the ONE number (~90 min)

**Concept first:** add the new features to Stage-1; the question is whether the
Benter blend now leans on the model more than the old ~3%.

- Add new features to `models/stage1_logit.py` (keep the existing leakage guard;
  no BSP, no `pos`, no post-race ratings). Re-run the full pipeline through
  `models/stage2_blend.py` and the three-way scorer.
- **Readouts that matter:** (1) Stage-1 MODEL WEIGHT in the blend vs the prior
  ~3%; (2) Brier and log-loss vs BSP. **NOT CLV** — state this so a noisy
  LTP-driven CLV isn't over-read.

**Interpretation rule, set in advance:**
- Weight materially above 3% AND Brier closing toward BSP → signal is real,
  paid data (TPD/Weatherbys) justified. This is the buy signal.
- Weight still ~3% → proxies found nothing. Either the signal needs real
  sectionals (proxy too crude) or it isn't there. Also a clean, fundable
  answer — it saves the spend.

**Report:** the weight, the proper scores (Stage-1 / Blend / BSP), and a
one-paragraph honest read against the interpretation rule.

---

## Stop / status

Write the one-line status + the weight readout into `PROJECT_NOTES.md`.
Deferred to its own later block (NOT this phase): the sales-price scraper
(separate auction sites, separate name-matching) and the real Tier-1 paid
features. Do not start them.

**On the paid-data decision this phase informs:** TPD's published prices
(£10–£200/month) are for LIVE in-running GPS, the wrong product for
backtesting — useless for historical features. The historical/stride archive
we'd actually need is quote-only ("contact us") and likely four figures. Before
paying, there is a free-but-laborious middle step: British sectionals now
appear per-race on racingtv.com and attheraces.com (post-2024 59-course
consolidation) and could be scraped into a historical archive. That is a SEPARATE
future block, only worth attempting if THIS phase's proxy moves the model weight
enough to justify it. Sequence: free proxy (this phase) → if it moves the weight,
racingtv/ATR scrape OR a TPD historical quote → buy only with measured evidence.
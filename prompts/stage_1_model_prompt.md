# CC Brief — Stage-1 Fundamental Model (Day Plan Blocks A–C)

**For: Claude Code, working in `~/projects/racing_project` with `.venv` active.**
**Goal:** build a Stage-1 fundamental win-probability model (conditional/multinomial
logit), check its calibration, and score it for CLV against BSP. This is the first
model the whole data foundation exists to serve.

Read `PROJECT_NOTES.md`, `Tomorrow_Plan_17Jun.md`, `Feature_Catalogue.docx`, and
`backtest/clv.py` first for context. Work block by block. **After each block, STOP
and report** (what you built, the checkpoint numbers, anything surprising) before
moving on. Do not run all blocks unattended.

---

## Guardrails (read before writing any code)

- **Leakage is the cardinal sin.** Features must be computable strictly from
  information available BEFORE the off. The following must NEVER enter the model
  as inputs: BSP, any in-running/pre-off price, finishing position (`pos`), any
  post-race rating, or anything derived from the result. BSP is the SCORING
  benchmark only — it lives in the CLV harness, never in the feature matrix.
- **Build an explicit leakage guard**, not just discipline: define an allowed
  feature list and assert that the feature matrix contains only those columns.
  Print the exact features used so the user can eyeball them.
- **Keep it readable and commented.** The user is learning this; favour clarity
  over cleverness. The user must be able to explain each piece back.
- **Everything stays in WSL on H:.** Use project-relative paths
  (`data/joined/...`, `models/...`). Do NOT drift to Windows paths
  (`/mnt/h/`, `//wsl.localhost/`).
- **Reproducibility:** set a fixed random seed; if you split data, log the split.
- Do not place bets or touch any live betting endpoint. Local modelling only.

---

## Block A — Stage-1 conditional/multinomial logit (the model)

**Input:** `data/joined/joined_gb_2025_09.csv` (886 GB races, 7,979 runners,
form features + BSP per runner).

Write a readable, commented script (suggest `models/stage1_logit.py`) that:

1. **Loads** the joined table.
2. **Selects pre-race features ONLY.** Start with these (drop any not present,
   log which): `rpr`, `going` (encoded), `dist`/distance (numeric, in a
   consistent unit), `class` (encoded), `draw`, `days_since_run`, `weight`
   (carried), `age`. Treat `going` and `class` as categoricals (one-hot or
   ordinal as appropriate — explain the choice).
   - **Explicit leakage assertion:** build the allowed-feature list, then assert
     the feature matrix columns are a subset of it. Hard-fail if `bsp`, `pos`,
     or any post-race column appears.
3. **Handles missing values** sensibly (impute or drop — state which per column,
   and how many rows affected). Note: Topspeed is known-missing (see
   PROJECT_NOTES); RPR is the primary rating and is present.
4. **Fits a conditional/multinomial logit grouped by race.** Each race is one
   choice set; exactly one winner per race. Either:
   - a true conditional logit (e.g. via a discrete-choice approach), or
   - a multinomial logit reframed as per-race choice sets,
   whichever is cleaner — but the OUTPUT MUST be: one win-probability per runner,
   and **those probabilities sum to ~1.0 within each race** (softmax normalised
   over the race's own runners).
   - The race grouping key already exists in the joined table (date + course +
     off time / race id) — use it as the choice-set identifier.
5. **Outputs** a per-runner probability column. Write the scored table to
   `models/stage1_scored.csv` (keep race key, horse name, the features used,
   the model prob, AND bsp/pos carried along as NON-features for later scoring —
   clearly separated so they can't be mistaken for inputs).

**Print / report:**
- The exact list of features used (and any dropped, with reason).
- Confirmation that per-race probabilities sum to ~1.0 (report min/max/mean of
  the per-race sum across all 886 races — should all be ≈ 1.000).
- For 2–3 sample races: the runners, model prob, and BSP-implied prob side by
  side. **Does the model's favourite usually match the market's favourite?**

**Checkpoint:** probability column summing to 1.0 per race; model favourite
broadly tracks market favourite. STOP and report.

---

## Block B — Calibration check

**Learn-first note for the user:** calibration asks "when the model says 20%,
do those runners actually win ~20%?" — not "does it pick winners."

Write a calibration check (suggest `models/calibrate.py` or a function):

1. Bucket all runners by predicted probability (e.g. bands
   0–2%, 2–5%, 5–10%, 10–20%, 20–35%, 35–50%, 50%+ — pick sensible bands and
   state them).
2. Per band: predicted mean prob vs ACTUAL win rate (uses `pos == 1`; this is
   the one legitimate use of the result — for SCORING, not as a feature).
3. Print as a table: band, n runners, mean predicted, actual win rate, diff.
4. Optional: a simple reliability plot (predicted vs actual, with the diagonal)
   saved to `models/`.

**For comparison**, run the SAME calibration on BSP-implied probability
(1/BSP, renormalised per race) so the user sees model vs BSP on one table.

**Checkpoint — expected result:** the model should be calibrated but **WORSE
than BSP** (fewer, public-only features). That is correct and expected, NOT a
failure. If the model is wildly off the diagonal, note it — don't try to fix it
now. STOP and report the table.

---

## Block C — Score the model with CLV

**Learn-first note for the user:** this is the moment the project points at —
convert the model's probabilities to fair prices and ask whether the model found
value BSP didn't.

Write glue (suggest `models/score_stage1_clv.py`) that:

1. Takes `models/stage1_scored.csv`.
2. Converts model prob to a fair price: `fair_price = 1 / prob`.
3. **Selection rule:** back a runner where the model's fair price is BIGGER than
   the price the market offered (model thinks it's likelier than the price
   implies → model sees value). For the "price the market offered", use the
   available pre-off / interim struck-price column `clv.py` already expects —
   **NOT BSP** (BSP is the scorer). Document exactly which column is used as the
   struck price and flag that, per PROJECT_NOTES, the free-tier struck price is
   currently an LTP stand-in (so a positive CLV may be a timing artifact, not
   edge).
4. Feeds those selections into the existing `backtest/clv.py` harness (reuse it;
   `--struck-col` is configurable). Score CLV vs BSP, net of commission (default
   5%).
5. Report: number of selections, mean CLV, % beating BSP, and realised P&L block,
   broken down by race type if easy.

**Checkpoint — the honest one:** expect this to **NOT beat BSP**. The model uses
only Tier-3 public features the market already prices (per Feature Catalogue), so
it should roughly match or slightly lag the close. A model that beat BSP from
public features alone would be SUSPICIOUS — first suspect leakage, not edge.
STOP and report.

---

## Stop after Block C — do NOT start Stage 2

Stage 2 (the Benter market blend) is a separate stretch task and only if the user
asks. When Blocks A–C are done and reported, write a one-line status into
`PROJECT_NOTES.md` (newest at top) summarising: model built, calibration result,
CLV result.

**Report at the end:** the three checkpoint outputs (per-race sum, calibration
table, CLV summary) and the paths of every file you created.
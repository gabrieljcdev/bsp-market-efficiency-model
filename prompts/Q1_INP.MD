# CC PROMPT — Q1: Does CLV transfer to in-play?
## Pre-registered metric-validity test, run on GB racing data already held

**Status:** PRE-REGISTRATION. Date and commit this file BEFORE running any code or inspecting
any data. If you are reading this and it is not yet committed, commit it first.

**Date registered:** 2026-07-09  (fill in, do not backdate)
**Repo / commit at registration:** 2ffac7cd167e832d8e883beb04ce57c66ed1e4ab (branch `ui-editorial`)
**Answers:** `FOOTBALL_HANDOVER.md` §7, open question 1.

---

## 0. What this test is, and what it is not

**It is:** a test of whether a closing-line-value metric, computed against a *pseudo-close*
constructed from in-running prices, ranks pre-specified trading rules the same way that
absolute realised return does.

**It is not:**
- a test of football anything;
- a test of whether any rule has edge;
- a liquidity test;
- a reason to look at the 2025–26 holdout.

The question is sport-agnostic arithmetic. Racing data answers it because the *mechanism*
under test — "is `struck / pseudo_close − 1` a trustworthy ranker when no true closing price
exists" — has no sport in it. A verdict here transfers to football. A rule's performance here
does not.

**Why this blocks everything:** `FOOTBALL_HANDOVER.md` §2.1 lists `backtest/clv.py` as one of
five files that "port unchanged" and treats the CLV harness as a carried-over asset. In-play
has no Starting Price — the market resolves, it does not reconcile. If CLV is not a safe
metric in-play, that file ports as **plumbing only**, and the Step-1 edge gate must be written
against a price-band-stratified in-running null instead. That rewrite must happen before the
football pre-registration is authored, not after tick data is bought.

---

## 1. Standing guardrails (inherited, non-negotiable)

- **Do not place any bets, log in to Betfair to bet, or call any live betting endpoint.**
- **Do not purchase any data.** This test runs on data already in the repo or it does not run.
- **Do not touch the 2025–26 holdout.** Discovery split only. It is already partially burned;
  every look burns it further.
- **Hardcode `commission = 0.02` in this harness.** Do not read `DEFAULT_COMMISSION` — it is
  `0.05` in `backtest/clv.py` and `backtest/lay_clv.py`, and that split is an open P0
  (`FOOTBALL_HANDOVER.md` §3.1). Do not fix it as a side effect of this task; just do not
  depend on it. Note in the report which constant you used.
- **INCONCLUSIVE is a permitted and respected verdict.** It is not a failure to deliver.
- **A mechanism story is not a verdict.** Do not reason your way to an answer this test was
  built to measure.

---

## 2. Stage A — Data inventory. This stage can end the task.

Before anything else, establish what in-running price data actually exists in the repo.

1. Locate every dataset containing any in-running or post-off price field. Report, per source:
   file path, row count, date range, exact column names, dtype, null rate.
2. For each candidate price column, determine and state **explicitly**:
   - Is it a *series* (multiple timestamped observations per runner per race), or a single
     scalar per runner?
   - If a series: what is the sampling granularity, in seconds? Is it uniform?
   - Is there a timestamp column, and is it monotonic within a race?
   - Does the series extend past the off, and does it terminate at or before settlement?
3. Report the aggregate volume column (`ip_vol` or equivalent) separately and state, in one
   line, why it cannot substitute for a price series.

**Stop condition — apply it honestly.**

> If no per-instant, timestamped in-running price series exists, this test **cannot be run**.
> Report **INCONCLUSIVE (data-insufficient)**, state exactly which column would have been
> needed and at what granularity, and **stop**. Do not construct a pseudo-close from BSP. Do
> not interpolate a series from a scalar. Do not proceed to Stage B.

BSP is the *pre-off* close. Using it as the in-play pseudo-close would assume the answer to
the very question under test, and would produce a confident, wrong PASS.

**Also record:** whether the joined CSV is globally date-sorted. It is known not to be
(disorder ~row 452717). Sort by date before any time-series operation. Assert monotonicity
after sorting and fail loudly if it does not hold.

---

## 3. Stage B — Pre-specified rules. Fix these before seeing any result.

Define **five** mechanically-specified in-play entry rules. They are deliberately not fitted,
not tuned, and not expected to be profitable. They exist only to be *ranked*. Each must be a
pure function of data available at or before the entry instant.

| # | Rule | Entry condition | Side |
|---|------|-----------------|------|
| R1 | Short-price back | in-running price first trades ≤ 2.0 | back |
| R2 | Short-price lay | in-running price first trades ≤ 1.5 | lay |
| R3 | Drifter back | in-running price first trades ≥ 2× its BSP | back |
| R4 | Front-runner back | `run_style_proxy == led` AND price first trades ≤ 2.0 | back |
| R5 | Random control | uniformly random runner-instant, seeded, ~matched count | back |

R5 is the control. **It must score as zero-edge under any honest metric.** If any metric
awards R5 a positive verdict, that metric is broken, and that finding is reportable on its own.

Fill model, fixed now: 1.0s latency from signal to order, cross the spread, 1-tick slippage
cap, commission 0.02. State the tick ladder used.

Exit, fixed now: hold to settlement. No exit rule is under test; introducing one would make
this a strategy test, which it is not.

---

## 4. Stage C — Pre-specified metrics

Score every rule under **all** of the following, independently.

**Ground truth (the thing CLV is being checked against):**

- **G1. Absolute realised ROI**, net of 2% commission, on the modelled fill.
- **G2. Stratified-null differential.** Bin by entry-price band (use the existing 14 bands from
  `run_strategy.py`; <50 obs → global fallback). Compute the band-common return of a zero-skill
  bettor entering at the same instants. Report `rule_return − band_common_return`.

**Metrics under test — three pseudo-closes, each yielding `struck / pseudo_close − 1`:**

- **P1.** Final in-running LTP before settlement.
- **P2.** In-running LTP at a fixed offset, t + 30s from entry.
- **P3.** BSP. *(Included deliberately as a known-invalid control, since BSP is the pre-off
  close, not an in-play close. It should misbehave. If P3 looks fine, suspect the harness.)*

**Canary (runs first, gates everything else):**

- **C1.** Re-run G1 under a hindsight-perfect fill: entry at the best price traded in the entry
  window, zero latency, zero slippage, commission still 0.02.

> If C1 does not show a large edge on at least one of R1–R4, the test is
> **INCONCLUSIVE (underpowered)** — the data cannot resolve the effect sizes at issue — and
> **not** a clean result. Report and stop. Do not interpret metric agreement measured on a
> sample too weak to separate anything.

---

## 5. Stage D — The comparison, and the decision rule

Written before results are seen. Do not renegotiate it after.

For each pseudo-close P ∈ {P1, P2, P3}, across rules R1–R5, compute:

1. **Sign agreement** between P's CLV verdict and G1 (absolute ROI), per rule.
2. **Kendall τ** between the P-ranking of rules and the G1-ranking.
3. **Kendall τ** between the P-ranking and the G2-ranking.
4. The spread in CLV across P1/P2/P3 **for the same rule** — i.e. how far the metric moves when
   only the *close proxy* changes and the underlying bets do not.

Item 4 is the heart of it. The project has already seen this exact pathology once: racing CLV
swung **+2.63% → −24.87%** on a change of *struck*-price proxy while Brier moved 0.00007
(`FOOTBALL_HANDOVER.md` §9.2). That was the struck side. This tests the close side.

### Pre-registered verdict thresholds

- **CLV IS NOT SAFE IN-PLAY** if *any* of:
  - any pseudo-close disagrees in **sign** with G1 on any of R1–R4; or
  - any rule's CLV spread across P1/P2/P3 exceeds **10 percentage points**; or
  - any pseudo-close awards R5 (random control) a positive verdict.

  → **Consequence:** `clv.py` ports as plumbing only. The Step-1 edge gate is written against
  the stratified in-running null (G2), absolute return > 0 after commission, holdout-
  corroborated. Amend `FOOTBALL_HANDOVER.md` §2.1 to say so.

- **CLV IS PROXY-ROBUST** only if *all* of:
  - sign agreement with G1 on all of R1–R4, for both P1 and P2; **and**
  - Kendall τ ≥ 0.8 against G1 for both P1 and P2; **and**
  - CLV spread across P1/P2 ≤ 3 percentage points on every rule; **and**
  - R5 scores ~zero under P1 and P2; **and**
  - P3 (the invalid control) visibly misbehaves.

  → **Consequence:** CLV may be retained as a **secondary, never sole** metric, and the
  Brier-corroboration gate still applies. Positive CLV is still not edge.

- **Anything else → INCONCLUSIVE.** Say so plainly, and say what would resolve it.

Note the asymmetry: it is easy to conclude CLV is unsafe and hard to conclude it is safe. That
is intentional and correct. The cost of wrongly trusting the metric is a bought month of tick
data and a model scored against a criterion that does not mean what you think it means.

---

## 6. Anti-fooling requirements

- **Re-check anything surprising.** Both of this project's false positives were caught by this
  rule, not by a test. If a result is clean, attack it before reporting it.
- **Report the null result even if boring.** "All three proxies agreed and nothing moved" is a
  real finding and must not be dressed up.
- **Never report a differential without its absolute.** Test 8 of the racing project produced a
  positive differential-vs-band-common while its absolute ROI/CLV was negative. Every G2 number
  in the output must sit next to its G1 number.
- **Refuse leakage server-side.** Assert that every field used at entry carries a timestamp at
  or before the entry instant. Do not rely on the rule definition to have got it right.
- **Assume a silent zero-match bug exists.** Three were found in racing (`dist_f` suffix,
  course-name byte-match, horse-name country suffix), each returning plausible nulls rather
  than an error. Before scoring anything, assert non-zero row counts at every join and print
  match rates. A join that silently matched 0 rows will produce a beautiful, meaningless
  Kendall τ.
- **State the sample size** for every rule. If any of R1–R4 yields < 200 entries, flag it and do
  not let it drive the verdict.

---

## 7. Deliverables

1. `reports/Q1_inplay_clv_validity.md` — verdict on the first line, one of:
   `NOT SAFE` / `PROXY-ROBUST` / `INCONCLUSIVE (data-insufficient)` /
   `INCONCLUSIVE (underpowered)`. Then the tables. Then the caveats.
2. A results table: rows R1–R5, columns G1, G2, C1, P1, P2, P3, n.
3. A proxy-spread table: rows R1–R5, column = max(P) − min(P) over P1..P3.
4. The Kendall τ matrix.
5. `backtest/test_q1_clv_validity.py` — tests pinning the harness itself: that R5 scores zero on
   synthetic zero-edge data; that a synthetic known-edge rule is detected; that the joins assert
   on zero matches.
6. A one-paragraph statement of what, if anything, this changes in `FOOTBALL_HANDOVER.md` §2.1
   and §5 Step 1.

**Do not write the football pre-registration in this task.** Answer the question, then stop.

---

## 8. If you find yourself wanting to deviate

You will be tempted, at Stage A, to substitute BSP when the in-running series turns out to be
missing or too coarse. That temptation is the entire reason this document exists and is dated.
Report INCONCLUSIVE (data-insufficient) and stop. A cheap honest null is the product.

# HANDOVER — Systematic Betting/Trading Project ("Racing Edge — Rule Lab")

**Document date:** 9 July 2026
**Prepared for:** incoming engineer with zero prior context
**Status of project at handover:** research apparatus complete and trusted; **no validated edge found**; at a strategic fork (buy paid data / pivot sport / stop).

---

## ⚠️ Provenance and reliability of this document — read first

This handover was assembled from:

1. **The `horse racing model` Claude Project document set** — 23 markdown/text files, snapshot synced `2026-07-09T09:31:41Z`. These are the project's own running notes, written contemporaneously by the operator and by Claude Code (referred to throughout as "CC").
2. **Prior conversation history** in this session (the 9 Jul football-pivot discussion).

**The source code repository was NOT accessible when this document was written.** The repo lives on the operator's Windows machine inside WSL (`~/projects/racing_project`) and was not mounted into this session. Therefore:

- **Every file path, function name, port number, git SHA and command in this document was originally transcribed from the project notes, not the filesystem.** As of **2026-07-09 the repository was opened and reconciled** against this document — see `RECONCILIATION.md`. The §5/§7 paths, the CLI signatures, the test count, the `field_manifest.json` counts, the venv contents and the git state below have now been **verified against the tree**, and four factual corrections were applied inline (venv split, test count, derived-feature count, and two "absent" docs that are in fact present). Items RECONCILIATION could not check — chiefly runtime *behaviour* and the historical numeric *results*, none of which were recomputed — remain marked `[doc-sourced, unverified]`.
- **Every numeric result is quoted from the notes.** None has been independently recomputed here.
- Two source documents in the project set are **zero bytes** (empty): `Betfair Betting Exchange in Academic Research` and `Detecting Horse Racing Corruption`. They are referenced by other docs but their content is unavailable.
- Several documents referenced by the notes are **absent from the snapshot entirely** — see §12.

**First action for the incoming engineer:** read `RECONCILIATION.md` (the §5/§7 reconciliation, done 2026-07-09) alongside this document. The paths and counts it checked are now certified against the tree; treat everything else here as a map, not a certificate.

---

## 1. Executive summary

This is a **research project, not a trading system**. Over roughly three weeks (16 Jun – 1 Jul 2026) the operator, working with Claude Code, built a complete, disciplined, end-to-end apparatus for testing whether a systematic betting strategy on **British horse racing** can beat the **Betfair Starting Price (BSP)** out of sample, net of commission. The apparatus works, has caught two of its own false positives, and is genuinely trustworthy. It has been pointed at eight distinct hypotheses drawn from free public data. **All eight returned the same verdict: the signal is real and the market has already priced it.** No harvestable edge has been found. Nothing has ever been bet: **no live Betfair betting API has ever been called, no order has ever been placed, and no real money has been staked.** The system's maturity is therefore "validated backtesting instrument, zero live execution." As of 1 Jul the project pivoted its *question* from pre-race prediction to **in-running exchange trading**, pre-registered a kill-test for it, and stalled on a single blocking action: **purchasing Betfair Historical PRO tick data**. As of 9 Jul the operator has additionally proposed pivoting the *sport* from horse racing to **football**, which is under discussion and not decided.

---

## 2. Objective & success criteria

### 2.1 The thesis (stated verbatim in `PROJECT_NOTES.md`)

> A betting system has a real edge ONLY if its selections beat BSP, out of sample, after commission. BSP = the market's sharpest, margin-free closing line; CLV (struck/BSP − 1) is the validation metric. Architecture = Benter two-stage: a fundamental win-probability model, then blended with the market's own price.

### 2.2 What "done" looks like

There is **no written definition of project completion.** `Milestone_Eight_Tests_Summary.md` explicitly offers three legitimate end-states, none privileged:

1. Test the remaining narrow subpopulations (free, cheap) before spending.
2. Take the paid-data step deliberately (TPD sectionals / Weatherbys pedigree).
3. **Treat the null result as the answer** and redirect toward the applied-statistics skill-building framing "this project was always partly for."

That option 3 is written into the project's own summary is important context for the incoming engineer: **this was never purely a money-making venture.**

### 2.3 Target markets / sports

| | Current | Notes |
|---|---|---|
| Sport | GB horse racing | Exclusively. `region` column is single-valued `GB`. |
| Market type | WIN | Betfair `eventTypeId == 7`, market type `WIN`. |
| Place markets | **Untested** | Flagged in `Free_Experiment_Catalogue.md` Test 4; unknown whether place BSP is present in the cache. |
| Proposed pivot (undecided) | Football | Proposed 9 Jul 2026. Betfair `eventTypeId == 1`. |

### 2.4 Staking model

- **No live staking model exists.**
- A **bankroll simulator** was built into the UI's betting stage (29 Jun): toggle between **fixed-%**, **flat**, and **Kelly**; settles at both `wap` and `bsp` side by side; per-partition (discovery/holdout) bankroll curves. `[doc-sourced, unverified]`
- It is deliberately framed as **secondary to the verdict**: "compounding never creates edge." Demonstrated: a priced rule (Good going, `or ≥ 80`) at 3% staking cliffs to £0 / −100% across all three staking models.
- **Fractional Kelly + live execution via `flumine` is explicitly out of scope** until an edge is validated (`Free_Experiment_Catalogue.md`, "What this catalogue deliberately excludes").

### 2.5 Risk limits

**None are defined anywhere in the project documentation.** No max stake, no max daily loss, no exposure cap, no per-market liability limit, no kill switch. This is not an oversight in the sense of a bug — nothing has ever been bet. But it is a **hard prerequisite before any live capital**, and it is currently a blank page. See §12.

### 2.6 Expected edge

The project's own honest expectation, from `Milestone_Eight_Tests_Summary.md` and `racing_betting_literature_review.md`:

- Documented market anomalies are **"mostly too small to overcome transaction costs"** — which is precisely why they survive unarbitraged.
- On paid data: *"Go in expecting 'probably still mostly priced, possibly a thinner residual' — not 'edge waiting to be found.'"*
- The `RULED-IN` bar coded into the tool is **> +1% discovery edge vs a composition-fair, price-band-stratified BSP null, holding on holdout, AND corroborated by a Brier edge.**

The measured edge to date, on everything tested, is **zero or negative**.

### 2.7 What "human-supervised" means in practice

The system is described as semi-automated. Concretely, from the notes:

**The human does (unattended automation explicitly forbidden):**

- Downloads Betfair historical data manually from `historicdata.betfair.com` (it is a website with a login; one month at a time).
- Supplies and pastes all credentials (Racing Post cookies, Betfair login). CC is instructed never to ask for or store passwords in plaintext.
- Triggers the Racing Post scrape. **The `/scan` endpoint deliberately does NOT auto-fire a live scrape** — if today's card file is absent it returns the pull command instead. This is a designed guardrail, not a limitation.
- Approves each block of work. From `CC_Brief_Data_Acquisition.md`: *"After each block, stop and report what you got … before moving on — do not run the whole thing unattended."*
- Verifies Tier-2 course-geometry descriptors before the engine will accept rules on them.
- Would place any bet. **CC's standing guardrail:** *"Do not place any bets, log into Betfair to bet, or call any live betting endpoint."*

**Runs unattended:**

- Parsing, joining, feature building, model fitting, backtesting, verdict scoring, unit tests.
- The local bridge server on `127.0.0.1:8765` serving the browser UI.

**There is no unattended path to an order.** The "semi-automated trading system" framing describes an *intended* future state, not the current one.

---

## 3. Research log (chronological)

Dates are as recorded in the notes. Sessions were roughly full days.

### 16 Jun 2026 — Data foundation
- **Hypothesis:** A free-only data stack (Betfair free historical tier + `rpscrape`) is sufficient to build a BSP-scored backtest.
- **Method:** Four blocks — Betfair download → parser extension → Racing Post scrape → join.
- **Data:** September 2025, GB, WIN markets.
- **Result:** 27k stream files → 26k markets → **274k runner rows**; book sums median **1.001** (near-perfect fair book). `rpscrape` yielded **7,979 runner rows over 29 GB race days** (10 Sep had no GB racing — confirmed in both sources), 41 columns. Join on `date+course+off+normalised horse name` → **7,979 runners / 886 races, 100% valid BSP**.
- **Also:** `backtest/clv.py` built; 10 unit tests.
- **Key finding:** BSP-implied probability vs actual win rate is near-perfect in every band (1–2: 63% vs 62%; 3–5: 25% vs 25%; 20+: 2.2% vs 2.4%). **Real-data proof BSP probabilities are true.**
- **Near-miss caught:** "Back the favourite" showed **+1.43% CLV**. Diagnosed as a **timing artifact** of using last-traded-price (LTP) as the struck-price stand-in — favourites steam late, so LTP sits a touch bigger than BSP. **Not edge.**
- **Verdict:** Foundation **pursued**. Lesson banked: *positive CLV only means something when the struck price is real.*

### 18 Jun 2026 — Two-stage model built (the "17 Jun" plan slipped one day; there is no 17 Jun session)
- **Hypothesis:** A conditional-logit fundamental model + Benter market blend, on public features, will reveal whether the machinery works.
- **Method:** Stage-1 McFadden conditional logit written from scratch in pure Python (no numpy/sklearn), race = one choice set, softmax within race, gradient descent on NLL. Stage-2 = conditional logit on `x1 = log(model_prob)`, `x2 = log(market_prob)`, grouped by race → weighted geometric mean.
- **Data:** the 7,979-runner Sept-2025 join.
- **THE LEAKAGE CATCH (the project's defining event):** `rpr` (Racing Post Rating) is **post-race** in results-sourced data. The highest-`rpr` horse wins **72.9%** of races — a pre-race forecast physically cannot do that. Excluded. Replaced with `or` (Official Rating), highest-`or` wins **23%** — a genuine pre-race signal.
- **Confirmation diagnostic (read-only, gating):** within-race Spearman(rating, finishing pos): `rpr` **−0.886**, `or` **−0.134**. Highest-rated finishes top-3: `rpr` **96.7%**, `or` **54.2%**. Decisive same-horse consecutive-runs test (1,825 horses with ≥2 runs): `rpr` tracks its **own** run's position (−0.506); `or` ≈ 0 with same run (−0.017) and sticky between runs (e.g. KRANJCAR `or` steps 57→62→67→72→75 across wins). **Verdict: `rpr` post-race by nature (no fix possible); `or` pre-race and clean.**
- **Features used:** `or`, `draw`, `lbs`, `age`. Dropped: `rpr` (leakage); `going`/`class`/`dist`/`type` (constant within race → cancel in conditional logit, unidentifiable); `days_since_run` (not in data). Missing `or` (1,459) and `draw` (1,041) imputed race-mean. Standardised coefficients: `or` +0.422, `lbs` +0.266, `age` −0.131, `draw` −0.067.
- **Metric trap caught:** by **ECE**, the model (0.258%) looked *better* than BSP (0.676%). This is an artifact of **low resolution** — the model bunches ~90% of runners in the 5–20% band near the ~11% base rate, and **ECE rewards timidity**. Proper scores corrected it.
- **Results (Sept-2025, struck = pre-off LTP stand-in):**

  | Metric | Stage-1 | Blend | BSP |
  |---|---|---|---|
  | Brier | 0.0960 | 0.0863 | 0.0863 |
  | Log-loss | 2.1067 | 1.7868 | 1.7848 |
  | Mean CLV | −0.38% | −0.10% | — |
  | % beat close | 36.8% | 37.9% | — |

- **Learned blend weights:** `a`(model) = **+0.026**, `b`(market) = **+0.981** → **~97% market / 3% model.** Robust to L2 (identical at L2 = 0 → real MLE, not shrinkage).
- **Verdict:** Machinery **pursued and proven.** Edge: none, by design (public Tier-3 features only). *"A model that beat BSP from public features alone would be suspicious."*

### 21 Jun 2026 — Full dataset, real struck price, first edge hunt
- **Dataset expanded** to `data/joined/joined_gb_2018_2026.csv`: **726,044 rows**, 2018-02-11 → 2026-06-19, 100% GB, 65 courses, 73k–91k rows/year, **0 duplicate `(date,course,off,horse)` keys**. Missing Apr–May 2020 = COVID shutdown (correct, not a gap). Fill: `or` 100%, `rpr` 100%, `bsp` 99.6%, `draw` 65.7% (flat-only, expected).
- **Schema break:** the new Betfair source dropped `bf_market_id`, `bf_last_preoff_ltp`, `bf_runner_status`; added `pre_min/pre_max/ip_min/ip_max/pre_vol/ip_vol`. All four model scripts were hard-coded to the old columns. Rewired: races regrouped on `(date, course, off)`; valid-BSP filter (`bsp > 1.0`) replaces `bf_runner_status`.
- **THE PROXY LESSON:** with no last-traded price, a struck-price proxy sanity check swung CLV from **+2.63% (geometric mean of pre_min/pre_max) to −24.87% (pre_min)** while Brier moved **0.00007**. *"The proxy IS the CLV number."* Conclusion: no signal survives under proxy choice; real prices only.
- **THE STRUCK-PRICE FIX (the day's win, zero spend):** **PPWAP was found native in the `rpscrape` Betfair cache** as the `wap` column, present 2018–2026, simply never carried into the join. It is a genuine volume-weighted pre-off traded price. Carried `wap`, `morning_wap`, `morning_vol` into the join via `offline_join.py` `BF_COLS`, with a `wap_valid` flag. **2018 is 88% valid** (untraded tail); **2019+ ≥ 99.6%**.
- **Re-scored on real WAP:** Blend CLV **−1.00%** (median −0.38%, beats close 47.9%); Blend Brier **0.08721** vs BSP **0.08694**. Slightly negative, consistent, trustworthy.
- **`morning_wap` analysis:** Blend morning CLV **+6.20%** — **not edge**, confirmed timing offset. Market-implied Brier is monotone: morning **0.08881** > wap **0.08751** > BSP **0.08724** (morning is mechanically further from the sharp close).
- **THE MOST INFORMATIVE SINGLE RESULT — selection drift** (`wap/morning_wap − 1`): Blend picks **steam** (right side of the informed move) but Blend is 93–97% market weight, so this is near-tautological. **Stage-1 picks drift OUT hard: +31.66% vs a +14.12% baseline.** → **Stage-1 has NEGATIVE standalone information.** It selects horses the market correctly marks down (a favourite-longshot / public-bias trap on a weak public-feature model).
- **Rolling features (Tier-2/3), built → tested → reverted:** `features/build_rolling.py` produced six leakage-safe features (`career_runs`, `days_since`, `win_rate`, `place_rate`, `jockey_sr`, `trainer_sr`), all strictly prior-date, current race excluded. Leakage proof passed (anchors reproduced: `or` −0.131, `rpr` −0.875; all `f_*` in −0.04 to −0.21; run-by-run trace + debut-null confirmed). Standalone Stage-1 Brier improved **0.09743 → 0.09508** (closed ~23% of the gap to BSP), coefficients sane. **But zero market-relative gain:** drift unchanged (+32.4% vs +31.7%, still wrong side), **blend weight FELL 6.9% → 1.5%.**
- **THE GOVERNING PRINCIPLE, proven live:** *predictiveness ≠ orthogonality-to-market.* The features are real and **fully priced**; the blend therefore trusted Stage-1 **less**. Features reverted; `build_rolling.py` retained.
- **Segmentation × holdout (first subset hunt):** the **short 3–6 price band** cleared all three criteria (CLV +1.10% val / +0.65% holdout, drift beats baseline, survives holdout); `fav < 3` stronger (+2.70% / +2.68%) but missed the 2,000-selection validation minimum by 148.
- **Verdict on that:** **parked as almost certainly the favourite-steamer timing offset, not edge.** The price band is a clean monotone (short steams → +CLV; long drifts → −CLV) — the textbook FLB/steamer microstructure, which a market-dominated blend inherits. Same artifact family as geomean and `morning_wap`.

### 28 Jun 2026 — Front end built end-to-end; struck-price sign reconciled
- **Built** the five-piece front end in `racing_rulebuilder/` (see §5).
- **Field manifest / leakage gate:** 52 CSV columns classified — **33 pre-race selectable, 19 post-race BLOCKED** (`pos, ovr_btn, btn, time, secs, dec, rpr, comment, bsp, pre_min, pre_max, ip_min, ip_max, pre_vol, ip_vol, wap, morning_wap, morning_vol, wap_valid`). 13 derived prior-run features added, each carrying a non-negotiable `leakage_note`: *prior-run only, join strictly before the current race date.* 6 pending-acquisition items roadmapped.
- **Server-side leakage enforcement:** the bridge **refuses** any strategy whose selection rules touch a post-race column — independently of the UI's client-side gate. *Never trust the client.*
- **CLV SIGN RECONCILED (was a genuine worry):** back-all on the full set is **−10.76% CLV**; lay-all is **+17.46%**. This is **not a sign bug.** The two are **reciprocal, not negated**: back-CLV = `wap/bsp − 1`, lay-CLV = `bsp/wap − 1`, related by a strictly-positive AM-GM convexity term `(wap−bsp)²/(wap·bsp)`, mean **+6.69%**. Hand-walked on 3 bets; pre-commission P&L sums to exactly 0 per bet. The −10.76% is the **WAP-vs-BSP timing offset** (wap sits ~10% under bsp; prices shorten into the off) — a level artifact, not harvestable.
- **@BSP efficiency confirmed:** settle both sides at BSP and both bleed **≈ −4.5%** (commission + overround), matching the documented lay-all@BSP **−4.63%**. The struck-vs-BSP offset is **not** edge.
- **Discovery/holdout split + verdict logic** implemented; verdict **decided on holdout**, benchmarked to BSP. States: `ruled-in` / `priced` / `to-holdout` / `thin`.
- **COMPOSITION-FAIR BASELINE added (caught a real bias):** the old baseline was the full field, but selections skew to higher-`or` / shorter horses (less commission drag). Swapped to a BSP-calibrated null on the **same horses**. On Good/`or ≥ 80` it lifted both edges ~+1.4pts (discovery −0.40 → **+0.96%**; holdout +5.16 → **+6.79%**) and turned discovery from "clearly nothing" into "borderline" — exactly the sensitivity feared. The fair null lands −4.1/−4.5%, matching the known BSP-efficiency line (independent sanity check).
- **Live-data bug caught by integration test (fixture had masked it):** `race_class` is a native `int` in live `rpscrape` racecard JSON but a `string` in the fixture → categorical compare did `(3).strip()` → `AttributeError`. Fixed at the shared source (`_eval_rule` coerces non-string cells to `str` first). Regression test added and **verified to fail if the coercion line is reverted (7 ERRORs)** — not a vacuous test. Historical path unchanged (regression: 24,466 qualifiers). Suite: 17 tests, green.
- **First real non-trivial rule:** `dist in 6f AND draw ≤ 1` → discovery **+24.27%**, holdout **−12.26%** → **PRICED**. A draw-bias mirage, sign-flipped out of sample. *"Do NOT flip this to a lay; a sign-flipping rule has no stable signal either way."*

### 29 Jun 2026 — UI day (branch `ui-editorial`)
- Field-control audit against real CSV values; added a `control` property so the UI input is chosen by the field's **actual values**, not its dtype. Fixed 4 miscalls (`course_detail`, `pattern`, `rating_band`, `sex_rest` were numeric-operator boxes over category strings). 10 free-text categoricals → searchable `enum_select`. `region` dropped (single value `GB`). Leakage tiers verified **byte-identical** after the change (zero diff lines).
- **Race view** + `/races` endpoint; **Runner view** + `/runners` endpoint (Layer 1 complete, Layer 2 deliberately stubbed with an honest "Needs history join — pending" banner). **CC correctly refused to build a half-correct leaky join.**
- **Staking layer** (see §2.4) and **saved-strategy flag system** built. The flag gate: only `ruled-in` / `to-holdout` strategies may flag races; `priced` / `thin` are saved as drafts but **blocked from flagging**, enforced at the promote step. Gate verified by contrast (same priced rule: 14 flags with demo override on, **0** with it off).
- **Bug banked:** the joined CSV is **NOT globally date-sorted** (disorder observed ~row 452717). Any order-dependent computation must sort by date first. **Critical for the pending Layer-2 history join.**
- **Security incident:** the Racing Post `REFRESH_TOKEN` was visible in `vendor/rpscrape/.env` in several screenshots and is **considered burned.** See §11.

### 30 Jun 2026 — Verdict hardened; free-feature space declared exhausted
- **THE VERDICT HOLE (most important correctness event since the leakage catch).** `trainer_course_sr` produced a false **RULED-IN** at **+4.26% holdout edge**. Three-check scrutiny killed it:
  1. It survived the @BSP null → **not** the WAP timing artifact, so *worse*, not better.
  2. **No Brier edge** (+0.10pp blend weight; the blend does not beat BSP).
  3. The "course" signal is a **non-orthogonal proxy for general trainer hot-form** — strip overall-hot trainers and the course edge **flips to −3.86%**. The selection's own ROI@BSP is **−2.15%** (it loses money).
- **Root cause:** the composition-fair null priced each runner by within-race de-overrounding (`1/bsp / Z`). That removes overround **level** but not favourite-longshot **composition**. Short prices return more @BSP than their de-overrounded probability implies, so **any favourite-skewed rule beats that null with zero skill.** The fair null (−4.11%) was in fact *more negative* than the plain full-field null (−2.86%), **inflating** the measured edge. The 28 Jun composition-fair fix had corrected OR-skew but not price-band skew — a partial fix that looked complete.
- **The fix (two parts, both needed):**
  1. **Price-band-stratified null** — 14 BSP odds bands, fine at the favourite end; each selection benchmarked against the full field's actual back-all@BSP ROI **in its own band**. Bands with <50 observations fall back to global.
  2. **Brier-corroboration gate** — to read `RULED-IN`, the blend must beat BSP on Brier over the selection's holdout horses. **A CLV edge with no probability edge behind it can no longer rule in.** Coverage below 0.5 → `priced`.
  - The stratified null alone trimmed the trainer rule to **+1.33%** (residual stable across 8→64 bands) and it *would still have barely ruled in.* The Brier gate is the decisive backstop.
- **Tests:** `backtest/test_verdict.py`, 7 new — including a synthetic favourite-skewed **no-skill** market that reads `PRICED` even with a monkeypatched *passing* blend, proving the composition fix alone blocks the false rule-in. Suite 35/35, later 46/46.
- **Course-geometry infrastructure:** `data/reference/course_geometry.csv`, **65/65 courses matched, 0 guessed** (builder aborts on mismatch). 7 geometry columns joined into the pipeline (**726,044 / 726,044 rows**). Tier-1 facts (handedness, shape, circumference) verified + selectable. Tier-2 descriptors (character, undulation, `uphill_finish`) gated **three ways** — manifest `selectable:false`, UI ⊘ chip, engine refuses rules on unverified fields. `uphill_finish` human-verified for **11 courses, 0 corrections needed**; **54 calls remain unverified** (14 Y / 40 N). Multi-config caveat: Aintree = Mildmay not National; Newmarket = Rowley; Salisbury = loop; Fontwell = figure-of-eight — **check whether the `course` column distinguishes dual-config tracks before trusting their geometry.**
- **Milestone:** five feature families tested (rolling form, handicap structure, speed figures, weather/visibility, trainer-course) — **all real, all priced.** Speed figures were the only family ever to move the blend weight positively (**+2.98%**, "the clock beats the ratings as a model ingredient") and even that does not beat BSP.

### 30 Jun – 1 Jul 2026 — The eight-test milestone

From `Milestone_Eight_Tests_Summary.md`:

| # | Test | Question type | Result | Verdict |
|---|---|---|---|---|
| 1 | Rolling form | Knowledge (who wins) | Real, priced | Killed |
| 2 | Handicap structure | Knowledge | Real, priced | Killed |
| 3 | Speed figures | Knowledge | Real (first +blend-weight move, +2.98%), still priced | Killed |
| 4 | Weather / visibility | Knowledge | Real where testable; mostly **untestable** (fog too rare) | Parked |
| 5 | Trainer-course form | Knowledge | Looked like edge (+4.26%) — was a **verdict-baseline bug** (favourite-longshot artifact). Fixed. | Killed |
| 6 | Best-of-rest (favourite excluded) | Knowledge, reframed | Priced — the market's own sub-ranking is efficient too | Killed |
| 7 | Conditions on 2nd-fav reliability | Knowledge, reframed | Priced — **canary-confirmed real null** (rig proven powered) | Killed |
| 8 | Price-movement / CLV drift | **Timing**, not knowledge | **First OOS-stable signal found (R² +0.0119)** — real, but lives in an **untradeable longshot tail**; negative CLV, loses to commission | Killed (economically) |

**The one mechanism, seven confirmations:** every test that found a real effect found the *same thing happen to it* — the effect was genuine and the market had already absorbed it. This held across **knowledge** (public information) and **timing** (price behaviour) — two structurally different question types, one wall. *That consistency is the actual evidence, more than any single test.*

**Two self-caught near-misses (the discipline working):**
1. `trainer_course_sr` (test 5) — false RULED-IN via the fair-null hole. Found by the standing *"re-check anything surprising"* rule, root-caused, fixed with permanent infrastructure.
2. The price-drift probe (test 8) — **the same shape of bug recurred in a new form**: a positive "differential vs band-common" reading looked like edge while the absolute ROI/CLV was negative. **CC caught it mid-analysis, before reporting a verdict**, and hardened the money gate to require the absolute return to survive commission before ruling in. *This is the discipline generalising, not just being followed once.*

### 1 Jul 2026 — PIVOT to in-running trading; live-card bug; Stage 0 pre-registered
- **Bug found + fixed — horse-name normalisation (live card ↔ historical index).** Found via a "just for fun" demo (Worcester 13:20 handicap chase). Live racecards use clean names ("Atreides"); the historical joined CSV keys on RP country-suffixed names ("Atreides (IRE)"). **Every horse-level Layer-2 lookup on a LIVE card silently returned null** (`career_runs = 0` etc.) for **100% of runners** — a dangerous **silent** failure that looked like "no history," not a loud error. Trainer/jockey SRs matched fine (no suffix), which is why it went unnoticed.
  - **Fix** (`features/history_join.py`): `canon_horse()` strips/canonicalises the country suffix; exact name tried first, canonical base only on a miss. **Ambiguity guard:** a base mapping to >1 distinct country code is **REFUSED** (never silently merged — could be different horses); case-only variants merge.
  - Historical bridge path confirmed **unaffected** (byte-identical code path on exact match; test-pinned; empirically verified on the full 726k index — **69,741 horses → 69,488 canonical bases, only 124 / 0.18% ambiguous, correctly refused**).
  - 46 → **51 tests**, all green. Logged as **"Gotcha 2"** alongside the `dist_f` suffix and course-name byte-match issues — the same class of error (silent zero-match), now three instances caught.
- **THE PIVOT.** Motivation: the operator built crypto HFT bots, found that market too institutionally efficient for retail edge, and is testing whether Betfair's **in-running** exchange is a "softer" market. Explicitly a **different question** from the 8 pre-race tests — reacting to race development speed, not predicting from pre-race data.
- **Deep research pass** (`Deep_Research_Brief_InRunning_Trading.md` — **absent from the doc snapshot**, see §12). Findings as summarised in `PROJECT_NOTES_append_1Jul.md`:
  - The price/order-book feed is **relatively flat for retail** (~40ms Streaming API latency; no crypto-style co-location arms race; the regulatory **1-second UK in-play bet delay** is a universal equaliser).
  - **But:** a real-time GPS position feed (TPD) exists and is used by pros, with a documented retail-vs-pro latency hierarchy (**~0.5s retail / ~20ms pro**) — the "react faster" edge is **already contested**.
  - **Liquidity is thin and shrinking:** only **~20% of turnover is in-play**; UK/IRE win-market volume fell from **£1.5bn to under £1bn, 2020–2024.**
  - **Betfair's Expert Fee** (replaced the Premium Charge, **6 Jan 2025**) taxes profit **20–40%** above **£25k/year lifetime gross profit** — a structural drag crypto exchanges do not impose.
  - **Recommendation:** cheap historical backtest **before** any build or live capital.
- **Stage 0 pre-registered** — **before any spend.** The committed pre-registration is in **`Strategy_Direction_InRunning.md`** (repo root) and the canonical brief in **`prompts/InRunning_Stage0_PreRegistration.md`** — **both are present in the repo** (they were missing only from the doc snapshot this handover was first assembled from; see §12.1). Quoted here **verbatim** rather than paraphrased from the notes — a pre-registration paraphrased is not a pre-registration.

  The falsifiable claim (`Strategy_Direction_InRunning.md` §1), verbatim:
  > "At a realistic, latency- and liquidity-constrained fill model, a pre-registered in-running entry signal can get **≥ £X matched in > Y% of ≥ N qualifying opportunities**, AND the net-commission ROI on the **matched subset** beats the price-band-stratified structural in-running null by **≥ +1.0%** and is **> 0**, out of sample."

  The confirmed parameters (`Strategy_Direction_InRunning.md`, footer), verbatim:
  > **CONFIRMED 2026-07-01:** N = 2,000, X = £100, Y = 50%; edge bar ≥ +1.0% over the stratified null AND > 0 net commission; fill model L = 1.0 s, S = 1 tick, **2% commission** (corrected from 5%); liquidity-gate signal = front-runner (`run_style_proxy = led`) entered when the in-running price first trades ≤ 2.0. Stage 1 is authorized for the **LIQUIDITY GATE ONLY** — report the liquidity result and wait for confirmation before any further spend or the edge backtest.

  The qualifying-opportunity definition (`Strategy_Direction_InRunning.md` §8) and the power canary (§5), verbatim:
  > a qualifying opportunity = a GB runner whose pre-race dominant run-style = **`led`** (a front-runner), entered when its in-running price **first trades ≤ P_trigger = 2.0**.
  >
  > **Hindsight-perfect-fill canary:** re-run the edge test replacing the realistic fill with the **best in-running price actually traded** in each opportunity. This MUST show a large edge … **If even the hindsight-perfect fill shows no edge → INCONCLUSIVE** (data/signal underpowered), not a clean fail.
- **Liquidity gate run FREE, zero spend** (first-pass, `models/inrunning_liquidity_screen.py`), using the Betfair in-play aggregates `ip_min` / `ip_max` / `ip_vol` already in the 726k dataset (99.8% populated). Per **`Handover_InRunning_Stage1_Pending.md`**: **21,416** qualifying opportunities (led & `ip_min` ≤ 2.0; ≫ N_MIN 2,000); TOTAL in-play matched volume per runner **median £48,723**, p10 £17,679, p25 £28,784; **fraction with `ip_vol` ≥ £100 = 100.0%** (discovery 100%, holdout 100%). £100 is ~**0.2%** of the median.
  - **Verdict: NOT KILLED but INCONCLUSIVE.** `ip_vol` is a whole-market / whole-period aggregate — **not proof that £100 is matchable AT the entry price AT the entry instant (t+1s).** The free screen **cannot pass** the gate, it can only fail it.
- **Guardrail written for the next session:** *"the free liquidity screen is ENCOURAGING, not a PASS — don't let CC (or yourself) treat 'not obviously dead' as 'found edge.'"*
- **Source reconciliation (2026-07-09):** the 1 Jul entry above is now re-sourced from **`Handover_InRunning_Stage1_Pending.md`** (the contemporaneous Stage-1 handover) rather than paraphrased from `PROJECT_NOTES_append_1Jul.md`. The two sources **agree** on every gate parameter (N/X/Y, fill model, 2% commission, entry signal) and on the liquidity result (21,416 opps; median £48,723; INCONCLUSIVE). Two caveats worth flagging: **(a)** the **deep-research findings** above (~40 ms latency, TPD ~0.5 s/20 ms hierarchy, £1.5bn→<£1bn, Expert Fee) are **not** in `Handover_InRunning_Stage1_Pending.md` — they trace to `PROJECT_NOTES_append_1Jul.md` and the still-absent `Deep_Research_Brief_InRunning_Trading.md`, so they remain second-hand; **(b)** a minor **`>` vs `≥`** inconsistency exists *within the source docs themselves* — `Handover_InRunning_Stage1_Pending.md` and the §1 claim require ≥ £X matched in **> Y%**, while `Strategy_Direction_InRunning.md` §2's PASS/FAIL line says **≥ Y%**. Y = 50% either way.

### 9 Jul 2026 — Football pivot proposed (this session, no work done)
- Operator asked whether the build is interchangeable to football, seeking "a more tradable market."
- Assessment given (not yet acted on): the harness (`parse_bsp.py` with `eventTypeId 7 → 1`, `clv.py`, calibration, Stage-2 blend, holdout/stratified-null/Brier verdict) ports directly. **Stage-1 does not** — conditional logit is a discrete-choice-over-a-choice-set model; football is 3 correlated outcomes and standard practice is a bivariate Poisson / Dixon-Coles goals model. The entire feature catalogue is racing-specific and dies.
- **Status: proposed, undecided.** See §10.

---

## 4. Findings

### 4.1 Confident (well-evidenced, large sample, replicated)

| Finding | Evidence | Sample |
|---|---|---|
| **BSP probabilities are true.** BSP-implied probability matches actual win rate across every price band. | 1–2: 63% vs 62%; 3–5: 25% vs 25%; 20+: 2.2% vs 2.4% | Sept 2025 GB (7,979 runners), corroborated on the 726k set |
| **`rpr` is post-race and must never be a model input.** | Within-race Spearman −0.886; top-rated finishes top-3 96.7%; same-horse consecutive-runs test tracks *own* run's position (−0.506) | 886 races / 1,825 multi-run horses |
| **`or` is genuinely pre-race and clean.** | Spearman −0.134; ≈0 with same run (−0.017); sticky between runs | Same |
| **Public form features are real but fully priced.** Predictiveness ≠ orthogonality. | 6 rolling features improved standalone Brier 0.09743 → 0.09508 yet **blend weight fell 6.9% → 1.5%** and drift was unchanged | 726,044 runners |
| **Stage-1 (public features) has negative standalone information.** | Its selections drift out **+31.66%** vs a **+14.12%** baseline — it picks horses the market correctly marks down | 726,044 runners |
| **The market is ~97% of the blend.** | Learned Benter weights a=+0.026, b=+0.981 (Sept); blend weight 6.9% on the full WAP-scored set | Both datasets |
| **The WAP-vs-BSP gap is a timing artifact, not edge.** | back-all −10.76% CLV / lay-all +17.46% are reciprocal, not negated (AM-GM convexity term, mean +6.69%); **both sides bleed ≈ −4.5% at BSP** | 726,044 runners |
| **Favourite-skewed rules beat a de-overrounded null with zero skill.** | The fair null (−4.11%) was *more negative* than the full-field null (−2.86%); a synthetic no-skill favourite-skewed market read RULED-IN before the fix | Unit-tested (`test_verdict.py`) |
| **Eight hypotheses, five feature families, two question-shapes → one wall.** Free public-information edge is comprehensively ruled out **on this market, population-wide.** | See §3 table | 726,044 runners, 2018–2026 |
| **A struck-price proxy can BE the metric.** | CLV swung +2.63% → −24.87% on proxy choice while Brier moved 0.00007 | 726,044 runners |

### 4.2 Suggestive (real but under-powered, unconfirmed, or economically dead)

| Finding | Evidence | Caveat |
|---|---|---|
| **Speed figures are the only family to move the blend weight positively (+2.98%).** "The clock beats the ratings as a model ingredient." | 30 Jun test 3 | Still does not beat BSP. |
| **Test 8: an OOS-stable price-drift signal exists (R² +0.0119).** The first and only out-of-sample-stable signal ever found. | 30 Jun / 1 Jul | Lives in an **untradeable longshot tail**; **negative CLV**; loses to commission. Economically dead as found. |
| **Short-price band (3–6) cleared all three segmentation criteria.** CLV +1.10% val / +0.65% holdout. | 21 Jun | Almost certainly the **favourite-steamer timing offset**. `fav < 3` was stronger (+2.70/+2.68%) but **missed the 2,000-selection minimum by 148**. Not confirmed under the *hardened* (post-30-Jun) verdict. |
| **In-running liquidity is not obviously dead.** 21,416 qualifying opportunities; £100 ≈ 0.2% of median £48,723 in-play volume/runner. | 1 Jul | **INCONCLUSIVE, explicitly not a pass.** `ip_vol` is a period aggregate, not instantaneous depth at the entry price at t+1s. |
| **`uphill_finish` judgements are probably sound.** | 11/65 courses human-verified, **0 corrections needed** | 54 remain **unverified** and are engine-gated. |

### 4.3 Explicitly NOT concluded

From `Milestone_Eight_Tests_Summary.md`, verbatim in substance:

- It does **not** mean the dataset is exhausted. **Narrow subpopulations were never tested** — every test so far was population-wide.
- It does **not** mean paid data will work. *"Professional syndicates already trade on this data; much of its edge is likely already arbitraged."* The honest framing: paid data has a **higher barrier to entry** → fewer competitors hold it → **less efficiently priced**. A difference of **degree, not a guarantee**.
- **Narrowing the search increases mirage risk, not decreases it.** A narrow slice is only worth testing if it has a **mechanism decided BEFORE seeing results** — not chosen because a broad test looked promising and needs rescuing.

---

## 5. What's been built — component inventory

> **Paths verified 2026-07-09** against the working tree (`RECONCILIATION.md` §1) — every path below resolved; none missing or renamed except the Desktop dead-file, which is already gone. Component *states/behaviours* (e.g. the "Working" column) are not all runtime-verified. Repo root is `~/projects/racing_project` inside WSL Ubuntu-22.04, physically on the `H:` drive.

### 5.1 Data acquisition & preparation

| Component | Path | Purpose | Stack | State | How to run |
|---|---|---|---|---|---|
| BSP parser | `parsers/parse_bsp.py` | Betfair stream JSON / `.tar` / `.tar.bz2` → `output/bsp_table.csv`. Walks tar members; filters `eventTypeId == 7`. | Python, stdlib | **Working** | `python parsers/parse_bsp.py` over `data/historical/` |
| Form scraper | `vendor/rpscrape/` (vendored fork of `github.com/joenano/rpscrape`) | Racing Post results & racecards | Python **3.13+**; deps `curl_cffi jarowinkler lxml orjson python-dotenv tomli tqdm` | **Working** (auth token **burned** — rotate) | `./rpscrape.py -d 2020/10/01 -r gb` or `./rpscrape.py -r gb -y 2019 -t flat` |
| Join | `parsers/join_form_bsp.py` and/or `offline_join.py` | Joins BSP + form per runner on `date + course + off + normalised horse name`. `BF_COLS` carries `wap`, `morning_wap`, `morning_vol`. | Python | **Working** | *(entry point not recorded — verify)* |
| Rolling features | `features/build_rolling.py` | 6 leakage-safe prior-run features | Python | **Built, retained, features reverted from the model** | — |
| History join | `features/history_join.py` | Strictly-prior, date-sorted per-horse history join. Contains `canon_horse()` + ambiguity guard. | Python | **Working** (fixed 1 Jul) | — |
| Course geometry | `data/reference/course_geometry.csv` + a builder script *(name not recorded)* | 7 geometry columns, 65/65 courses, builder **aborts on mismatch** | Python | **Working**; Tier-2 fields gated | — |

### 5.2 Model

| Component | Path | Purpose | State |
|---|---|---|---|
| Stage-1 | `models/stage1_logit.py` | McFadden conditional logit, pure Python, gradient descent on NLL. Features `or, draw, lbs, age`. | **Working** |
| Stage-1 output | `models/stage1_scored.csv` | Per-runner Stage-1 probabilities | Artifact |
| Calibration | `models/calibrate.py` | Reliability bands + Brier + log-loss (model vs BSP). Text reliability chart (matplotlib not installed). | **Working** |
| Stage-1 CLV | `models/score_stage1_clv.py` | Value selections → CLV | **Working** |
| Stage-2 | `models/stage2_blend.py` | Benter blend: conditional logit on `log(model_prob)`, `log(market_prob)`, grouped by race | **Working** |
| Stage-2 output | `models/stage2_scored.csv` | model / market / blend probs per runner | Artifact |
| Three-way scorer | `models/score_blend_clv.py` | Stage-1 / Blend / BSP calibration + CLV | **Working** |

### 5.3 Backtest & verdict

| Component | Path | Purpose | State |
|---|---|---|---|
| CLV harness | `backtest/clv.py` | `CLV = struck/BSP − 1`; mean/median CLV; % beating close; realised P&L net of commission. Takes `--struck-col` so the struck price can be repointed. **`DEFAULT_COMMISSION = 5%`** | **Working** |
| CLV tests | `backtest/test_clv.py` | 10 tests pinning the metric maths | **Working** |
| Verdict tests | `backtest/test_verdict.py` | 7 tests incl. a synthetic no-skill favourite-skewed market | **Working** |
| Scanner tests | `backtest/test_scan_today.py` | Regression; **verified to fail (7 ERRORs) if the str-coercion line is reverted** | **Working** |
| Test runner | — | `python -m unittest discover backtest` | **130 tests, all green** (verified 2026-07-09; was 51 at 1 Jul) |

### 5.4 Front end — `racing_rulebuilder/`

Five deliverables. The browser **never** parses the 726k CSV; it emits `strategy.json`, POSTs to the local bridge, renders `results.json`.

| Component | Path | Purpose | State |
|---|---|---|---|
| Rule-builder UI (canonical) | `racing_rulebuilder/index.html` | Original working UI. **Untouched by the restyle.** | **Working** |
| Rule-builder UI (restyle) | `racing_rulebuilder/index_editorial.html` | Four-mode editorial version (Build · Backtest · Scan · Track), on branch `ui-editorial` | **Partial — NOT promoted.** Build + Backtest eyeballed; **Scan never seen**; Track not re-verified post-restyle. |
| Bridge / server | `racing_rulebuilder/run_strategy.py` | Backtest engine + stdlib HTTP endpoint. Imports `backtest/clv.py`. **Server-side leakage refusal.** Routes: `/scan`, `/races`, `/runners`. | **Working** |
| Scanner | `racing_rulebuilder/scan_today.py` | Stage-3 scanner over `rpscrape` racecards. **Imports the bridge's `_eval_node` / `check_fields`** — filter logic literally identical to the historical path. Tier-1 (card columns) live; **Tier-2 (history-join derived) stubbed.** | **Partial** |
| Tracker | `racing_rulebuilder/edge_tracker.html` | Stage-4 forward CLV log. Persistence = Export/Import JSON, **no browser storage**. **To be retired** on promote (folded into "Track" mode). | **Working, to be deprecated** |
| Field manifest | `racing_rulebuilder/field_manifest.json` | 52 cols classified + **20 derived (14 materialised)** + 6 pending-acquisition. Each derived field carries a `leakage_note`. | **Working** |
| Dead file | `C:\Users\gabriel\Desktop\index_editorial.html` | Throwaway copy made only to launch in a browser (the `\\wsl.localhost` UNC path wouldn't launch via `cmd start`). | **DEAD END — delete. Do not edit.** |

**Run the bridge:**
```bash
cd ~/projects/racing_project
source .venv/bin/activate          # .venv (3.10) HAS pandas — use for modelling/backtests; .venv313 (3.13) is rpscrape-only, NO pandas
python racing_rulebuilder/run_strategy.py --serve    # binds 127.0.0.1:8765, CORS *
```
Then open `racing_rulebuilder/index.html` (a `file://` page can reach the bridge because CORS is `*`).

### 5.5 Abandoned / reverted

- **The 6 rolling features as model inputs** — reverted 21 Jun (priced). `build_rolling.py` retained.
- **`bf_market_id` / `bf_last_preoff_ltp` / `bf_runner_status`** code paths — obsolete after the 21 Jun schema change.
- **LTP as the struck price** — superseded by real `wap`.
- **The Desktop `index_editorial.html` copy.**

### 5.6 Project documents (on disk)

| Doc | Path | Purpose |
|---|---|---|
| **In-running Stage-1 handover** | `Handover_InRunning_Stage1_Pending.md` | The contemporaneous 1 Jul handover: the confirmed pre-registration, the FREE liquidity-screen result (INCONCLUSIVE), and the blocker (buy PRO ladder data). **Primary source for §3 (1 Jul).** |
| In-running strategy direction | `Strategy_Direction_InRunning.md` | The committed Stage-0 pre-registration (claim, N/X/Y, fill model, canary). Quoted verbatim in §3. |
| Stage-0 canonical brief | `prompts/InRunning_Stage0_PreRegistration.md` | The pre-registration brief; a third copy at `analysis/preregistration_inrunning.md`. |
| Running log | `PROJECT_NOTES.md` | The single on-disk running log (H:-drive original; the Claude Project copy is a synced snapshot). |
| This handover | `HANDOVER.md` | This document. |
| Reconciliation | `RECONCILIATION.md` | 2026-07-09 verification of §5/§7 paths, counts, CLI signatures, venvs and git state against the tree. |

---

## 6. Architecture

### 6.1 Current data flow (offline research loop)

```
  [ HUMAN ]  manual download, one month at a time
      │      historicdata.betfair.com  (FREE tier, GB, Horse Racing, WIN, file type M)
      ▼
  data/historical/*.tar(.bz2)          Betfair Exchange Stream format JSON
      │
      ▼  parsers/parse_bsp.py   (walks tar; eventTypeId == 7)
  output/bsp_table.csv                 274k runner rows (Sept-2025 build)
      │
      │        [ HUMAN ] triggers scrape ──►  vendor/rpscrape  ──► data/form/*.csv
      │                                        (Racing Post, cookie auth)
      ▼
  parsers/join_form_bsp.py / offline_join.py
      │   join key: date + course + off + normalised horse name
      │   BF_COLS carries wap, morning_wap, morning_vol (+ wap_valid)
      ▼
  data/joined/joined_gb_2018_2026.csv  726,044 rows  ◄── THE dataset
      │
      ├──► features/build_rolling.py      (retained, unused)
      ├──► features/history_join.py       (strictly-prior; canon_horse)
      ├──► data/reference/course_geometry.csv  (7 cols, 65/65 courses)
      │
      ▼
  models/stage1_logit.py   ──►  models/stage1_scored.csv
      │        (or, draw, lbs, age; softmax within race)
      ▼
  models/stage2_blend.py   ──►  models/stage2_scored.csv
      │        (Benter: log(model), log(market from wap) → weighted geo-mean)
      ▼
  racing_rulebuilder/run_strategy.py   (bridge, :8765)
      │   • SERVER-SIDE LEAKAGE REFUSAL on post-race columns
      │   • discovery / holdout split on date_cutoff
      │   • price-band-stratified null (14 BSP bands, <50 → global)
      │   • Brier-corroboration gate (coverage < 0.5 → priced)
      │   • imports backtest/clv.py  →  CLV = struck(wap)/bsp − 1
      ▼
  VERDICT: ruled-in | to-holdout | priced | thin
      │
      ▼
  racing_rulebuilder/scan_today.py   (Stage 3)  ──► today's rpscrape racecards
      │   Tier-1 live; Tier-2 stubbed. Never auto-scrapes.
      ▼
  edge_tracker / "Track" mode   (Stage 4)  ── forward CLV log, Export/Import JSON
      │
      ▼
  [ HUMAN ] would place the bet.  ◄── NO CODE PATH EXISTS BEYOND THIS POINT
```

### 6.2 Betfair API surface used

**This is the most important line in this section: none of the live Betfair APIs are used. No integration exists.**

| API | Used? | Notes |
|---|---|---|
| **Betting API** (`SportsAPING`) | **NO** | Never called. CC operates under a standing prohibition: *"Do not place any bets, log into Betfair to bet, or call any live betting endpoint."* |
| **Stream API** (`ESAClient`) | **NO** | Researched only. Notes record ~40ms retail latency and the 1-second UK in-play bet delay. |
| **Accounts API** | **NO** | Never called. |
| **Historical Data service** (`historicdata.betfair.com`) | **YES — via the website, manually** | FREE tier. Not the programmatic download API. |
| `betfairlightweight` | **NO — candidate only** | Listed in `Data_Sources_Reference.md` §3 as the standard OSS client. Never integrated. |
| `flumine` | **NO — explicitly deferred** | "Phase-4 problem; pointless before an edge is found." |

**Auth model:**
- **Betfair:** a normal, free Betfair account, used interactively on the historical-data website. **No app key, no certificate login, no session token has ever been provisioned.**
- **Racing Post (`rpscrape`):** cookie-based. `vendor/rpscrape/.env` (git-ignored) holds `EMAIL`, `AUTH_STATE`, `ACCESS_TOKEN` (`CognitoIdentityServiceProvider…accessToken`), and a `REFRESH_TOKEN`. **The user extracts and pastes these from browser dev-tools themselves.** CC never handles passwords.

**Rate limits:** none are documented for anything. `rpscrape` scrapes Racing Post HTML pages and *"can be slow / rate-limited; be gentle."* Betfair recommends downloading **one month at a time** (larger ranges time out). No Betfair transaction/data-request limits are relevant because no API is called.

**Market-data provider dependencies:**
- **Betfair Historical FREE tier** — BSP + per-minute LTP. **No traded volume, no full ladder, no timestamped struck prices.**
- **Racing Post via `rpscrape`** — form, ratings, racecards. Includes an embedded Betfair cache from which `wap` / `morning_wap` / `morning_vol` were recovered.
- **Betfair Historical PRO** — **the single blocking purchase.** 50ms granularity, full ladder + volume, SP reconciliation detail. Required for the in-running liquidity gate. Not bought. Cost: "tens-to-low-hundreds of £." **Not re-purchasable once bought for a given period** — buy the right window.
- **TPD (Total Performance Data)** — GPS/sectionals; the single gateway to the consolidated 59-course British sectional DB post-2024. Paid, commercial. Not contacted.
- **Weatherbys Bloodstock** — pedigree. Paid, commercial. Not contacted.

---

## 7. Data assets

| Asset | Path | Source | Coverage | Size | Notes |
|---|---|---|---|---|---|
| **THE dataset** | `data/joined/joined_gb_2018_2026.csv` | Betfair + `rpscrape`, joined | **2018-02-11 → 2026-06-19**, 100% GB, 65 courses | **726,044 rows** | Everything downstream builds on this. |
| Original small join | `data/joined/joined_gb_2025_09.csv` | Same | Sept 2025, 29 race days | 7,979 runners / 886 races | 100% valid BSP. Superseded. |
| Parsed BSP | `output/bsp_table.csv` | Betfair FREE tier | Sept 2025 (all countries, all `eventTypeId` 7 types) | 274k runner rows | Book sums **median 1.001**. |
| Raw Betfair archives | `data/historical/*.tar(.bz2)` | historicdata.betfair.com | one month at a time | — | Multi-country (GB-only filter is paywalled); pipeline filters GB downstream. |
| Form CSVs | `data/form/` | `rpscrape` | matches BSP period | — | 41 columns. |
| Course geometry | `data/reference/course_geometry.csv` | Manual + CC research | 65/65 GB courses | small | 7 columns. Builder aborts on mismatch. |
| Real-format fixtures | `data/samples/real_format_fixtures/` | Betfair | — | small | **`eventTypeId 4339` = greyhounds.** Format tests only; correctly filtered out by the `== 7` rule. |
| Model outputs | `models/stage1_scored.csv`, `models/stage2_scored.csv` | Derived | — | — | Artifacts. |

### 7.1 Schema of the joined table (52 columns, per `field_manifest.json`)

**Pre-race, selectable (33):** `date, region, course, course_detail, off, race_name, type, class, pattern, rating_band, age_band, sex_rest, dist, dist_f (coerce), dist_m, going, surface, ran, num, draw, horse, age, sex, lbs, hg, jockey, trainer, prize, or (coerce), sire, dam, damsire, owner`
*(`region` was subsequently dropped from the UI — single value `GB`.)*

**Post-race, BLOCKED as selection inputs (19):** `pos, ovr_btn, btn, time, secs, dec, rpr, comment, bsp, pre_min, pre_max, ip_min, ip_max, pre_vol, ip_vol, wap, morning_wap, morning_vol, wap_valid`

**Derived, prior-run only (20 classified, 14 materialised)** *(per `field_manifest.json`; verified 2026-07-09 — HANDOVER's earlier "13" was outdated):* `career_wins, career_runs, career_win_pct, career_place_pct, won_course_flag, won_dist_flag, won_cd_flag, class_change, or_trajectory, dslr, run_style_proxy, trainer_course_sr, trainer_class_sr, trainer_going_sr, jockey_trainer_combo_sr, hcap_transition, going_suit, sire_going_profile, sire_dist_profile, first_time_hg`
Each carries a non-negotiable `leakage_note`: **prior-run only; join strictly before the current race date.**

**Pending acquisition (6):** weather, `going_vs_forecast`, TPD sectionals, forecast tissue price, book impact, distance travelled.

**Plus 7 course-geometry columns** joined at 726,044/726,044 rows: Tier-1 = handedness, shape, circumference (verified, selectable); Tier-2 = character, undulation, `uphill_finish` (**gated, not selectable**).

### 7.2 Fill rates
`or` 100% · `rpr` 100% · `bsp` 99.6% · `draw` 65.7% (flat-only — expected) · `wap_valid`: 2018 = **88%** (untraded tail), 2019+ ≥ **99.6%** · `ip_min/ip_max/ip_vol` ≈ **99.8%**

### 7.3 Known quality issues

1. **The joined CSV is NOT globally date-sorted** — disorder observed around **row 452717**. **Any order-dependent computation must sort by date first.** Critical for the history join. *(29 Jun)*
2. **Apr–May 2020 is absent** — the COVID racing shutdown. Correct real-world behaviour, **not** missing data.
3. **`rpr` is post-race.** It is present, 100% filled, and **poisonous**. Blocked in the manifest.
4. **Horse-name suffix mismatch** (Gotcha 2). Historical index keys on `"Atreides (IRE)"`; live cards give `"Atreides"`. Fixed via `canon_horse()`; **124 / 69,741 (0.18%) bases are ambiguous across country codes and are REFUSED, not merged.**
5. **`dist_f` and `or` require object→numeric coercion** (flagged `coerce` in the manifest).
6. **Dual-configuration courses** — Aintree (Mildmay vs National), Newmarket (Rowley), Salisbury (loop), Fontwell (figure-of-eight). **Unverified whether the `course` column distinguishes them.** Do not trust their geometry rows until checked.
7. **54 of 65 `uphill_finish` calls are unverified** (14 Y / 40 N). Engine-gated. 11 verified with 0 corrections.
8. **`ip_vol` is a whole-market, whole-period aggregate** — it is **not** instantaneous depth at a price at an instant. This single fact is why the in-running liquidity gate returned INCONCLUSIVE.
9. **Topspeed is missing** from the vendored `rpscrape` (no `ts` column/flag). Deferred. Re-scrape is cheap (~6 min) if a newer version has it.
10. **`days_since_run` is not in the joined table** despite being in the Feature Catalogue. Derivable from per-horse race dates.
11. **Betfair archives arrive multi-country** (the GB-only filter is paywalled). Harmless; filtered downstream.

---

## 8. Backtest & live results

### 8.1 Live results

**None. Zero bets have been placed. Zero capital has been deployed. There is no live P&L.**

### 8.2 Backtest methodology

- **Struck price:** `wap` (Betfair pre-off volume-weighted average traded price), recovered native from the `rpscrape` Betfair cache. This is an **interim** struck price, not a timestamped fill.
- **Benchmark:** `bsp` (Betfair Starting Price).
- **Metric:** `CLV = struck / bsp − 1`, per bet. Aggregated as mean CLV, median CLV, % beating the close. Realised P&L reported **separately**, net of commission.
- **Commission:** `clv.py` `DEFAULT_COMMISSION = 5%`. The UI caption states `5% commission`. **The in-running Stage-0 pre-registration corrected this to 2%, Betfair's actual rate.** ⚠️ **This inconsistency is unresolved — see §12.**
- **Splits:** chronological discovery/holdout on a `date_cutoff` (UI default `2024-01-01`). The catalogued intent was Train 2018–2023 / Validation 2024 / **Holdout 2025–2026 (touch once)**.
- **Null / baseline (current, hardened):** a **price-band-stratified** null — 14 BSP odds bands, fine at the favourite end; each selection benchmarked against the full field's **actual back-all@BSP ROI in its own band**; bands with <50 obs fall back to global. This is aliased to `edge_bsp` and **is the verdict metric.**
- **Corroboration gate:** to read `RULED-IN`, the Stage-2 blend must **beat BSP on Brier** over the selection's holdout horses. Coverage < 0.5 → `priced`.
- **Verdict bar:** discovery edge > **+1%** AND holdout holds it AND Brier gate passes.
- **Minimum cell size:** ≥ ~2,000 selections before a segment result is believed.
- **The three-metric read (never Brier alone):** proper scores (resolution) + **blend weight** (orthogonality to market) + **drift** (which side of the informed move the selections sit on).
- **Canary check:** a hindsight-perfect-fill / monkeypatched-passing run must show a large edge; if not, the test is **INCONCLUSIVE (underpowered)**, not a clean fail.

### 8.3 Market-impact treatment

**None.** No slippage or market-impact model exists for the pre-race backtests. Selections are assumed to fill at `wap` in unlimited size. This is a **material unmodelled assumption**, and the notes acknowledge the adjacent problem: *"in thin markets a large BSP order can itself move the final price — your own money becomes part of the reconciliation."* The only slippage model that exists anywhere is the **in-running Stage-0 fill model** (1.0s latency, cross the spread, 1-tick slippage cap), and it has never been run on real tick data.

### 8.4 Headline metrics

**Sept 2025 (7,979 runners, struck = LTP stand-in):**

| | Stage-1 | Blend | BSP |
|---|---|---|---|
| Brier | 0.0960 | 0.0863 | 0.0863 |
| Log-loss | 2.1067 | 1.7868 | 1.7848 |
| Mean CLV | −0.38% | −0.10% | — |
| % beat close | 36.8% | 37.9% | — |

**Full set (726,044 runners, struck = real `wap`):**

| | Value |
|---|---|
| Blend CLV | **−1.00%** (median −0.38%) |
| % beat close | 47.9% |
| Blend Brier | 0.08721 |
| BSP Brier | **0.08694** |
| Blend weight on Stage-1 | 6.9% |
| Stage-1 selection drift | +31.66% (baseline +14.12%) |
| back-all CLV | −10.76% |
| lay-all CLV | +17.46% |
| back-all @BSP | ≈ −4.5% |
| lay-all @BSP | −4.63% |

**Illustrative rule verdicts:**

| Rule | Discovery | Holdout | Verdict |
|---|---|---|---|
| `dist in 6f AND draw ≤ 1` | +24.27% | −12.26% | **PRICED** (sign flip = draw-bias mirage) |
| Good going, `or ≥ 80` | +0.96% | +6.79% | Borderline under the *old* fair null; **not re-run under the hardened verdict** |
| `trainer_course_sr` | — | +4.26% → +1.33% after stratified null | **PRICED** (ROI@BSP −2.15%; edge flips to −3.86% when hot trainers stripped) |

### 8.5 Honest caveats about overfitting and lookahead

The project is unusually candid here, and the incoming engineer should preserve this posture.

- **Lookahead / leakage:** the *cardinal sin*, and the project has caught it three times (`rpr`; the derived-feature prior-run guard; the silent horse-name zero-match). Defences: the `or`(−0.13, pre-race) / `rpr`(−0.88, post-race) **anchor test**; a run-by-run trace; a debut-null check; no backfill; server-side column refusal. **Every new feature must pass the same anchor test.** *"A leak shows up as a feature suddenly looking great and the blend weight spiking — treat any large jump as a bug to find, not a result to celebrate."*
- **Overfitting / multiple comparisons:** explicitly flagged as **severe** once segmentation and interaction-hunting begin. Mitigations coded in: ≥2,000-selection minimum per cell; chronological holdout; **pre-registration of expected segments**; a "touch the holdout once" rule (*"every time the holdout is looked at it is partially burned"*).
- **The holdout has been touched repeatedly.** Eight tests, plus a segmentation sweep, plus a verdict-logic rewrite that re-scored old rules. **How partially burned the 2025–26 holdout now is has not been quantified.** Treat any future "it held out" claim on this dataset with corresponding suspicion.
- **The struck price is still not a real fill.** `wap` is a volume-weighted *average* over the pre-off window, not a price you demonstrably could have taken at a timestamp. **Positive CLV under `wap` may still be a timing artifact.** *"A CLV 'win' that is not matched by a blend-weight rise is probably the timing component, not edge."*
- **Two false positives were produced by the *baseline*, not by the model.** Both (`trainer_course_sr`, the price-drift differential) were artifacts of an insufficiently neutral null. The current stratified-null + Brier-gate combination is the fix, and it is unit-tested against a synthetic no-skill market — but **it has not been stress-tested against a third, unknown shape of the same bug.**

---

## 9. Failed approaches & dead ends

**Do not repeat these.**

1. **`rpr` as a model feature.** Post-race by nature. No fix exists. The highest-`rpr` horse wins 72.9% of races.
2. **ECE as the model-vs-market metric.** It rewards timidity/low resolution. Use **Brier + log-loss**.
3. **LTP, `pre_min`, `pre_max`, or their geometric mean as the struck price.** CLV swings ±27pts on proxy choice while Brier is flat. **The proxy becomes the metric.** Use real `wap` (or a real timestamped fill).
4. **Reading positive CLV as edge.** back-all is −10.76% and lay-all is +17.46% *on the same bets*; both bleed −4.5% at BSP. The gap is convexity + timing, not money.
5. **Backing on Stage-1's standalone value calls.** Stage-1 has **negative** standalone information (its picks drift out +31.66% vs +14.12% baseline). It selects horses the market correctly marks down.
6. **The 6 rolling form features as model inputs.** Improve Brier, *reduce* blend weight. Real, fully priced. Reverted.
7. **A bare `draw ≤ 1` filter.** Discovery +24.27%, holdout −12.26%. A draw-bias mirage. If you want draw, build **draw × field-size × course** raw. And *"do NOT flip this to a lay; a sign-flipping rule has no stable signal either way."*
8. **`trainer_course_sr`.** A non-orthogonal proxy for general trainer hot-form. Loses money at BSP.
9. **A de-overrounded within-race null as the baseline.** Removes overround *level* but not favourite-longshot *composition*. Any favourite-skewed rule beats it with zero skill.
10. **CLV edge without a Brier edge.** Now structurally blocked by the corroboration gate.
11. **The short-price / favourite band as a hunting ground.** It is the favourite-steamer timing offset, inherited by a 93–97% market-weighted blend. Same artifact family as `morning_wap` and the geomean.
12. **Weather / visibility features.** Fog is too rare to test. Blocked more fundamentally by the absence of **declared-going-change timestamps**. Humidity is explicitly parked: *"answer 'what does it tell me that `going` doesn't, and how do I verify it' before spending any time."*
13. **The `data/samples/real_format_fixtures/` as a source of horse-racing rows.** They are `eventTypeId 4339` = **greyhounds**. Format tests only.
14. **Fixtures as a substitute for a live-data integration test.** The `race_class` int-vs-string bug survived precisely because the fixture masked it.
15. **The Desktop copy of `index_editorial.html`.** A dead end. Delete it.
16. **Running CC from a Windows UNC path** (`//wsl.localhost/…`). Not a correctness problem (project-relative `__file__` paths resolve identically) but I/O crosses the Windows↔WSL boundary and some tools misbehave from a non-POSIX cwd. **Launch from a WSL-connected VS Code.**

---

## 10. Current state & immediate next steps

### 10.1 State

- **Branch:** `ui-editorial`, **not promoted**, WIP-committed. `index.html` (canonical) untouched.
- **Test suite:** 130 tests, all green (verified 2026-07-09; was 51 at 1 Jul).
- **Nothing is pushed.** Git identity is still set to a personal email.
- **The tool is complete and trusted. There is no edge.**
- The project sits at a **three-way fork** (`Milestone_Eight_Tests_Summary.md`), plus a **fourth option proposed 9 Jul** (football).

### 10.2 Prioritised next steps

**P0 — Hygiene. Do before anything else. Cheap, and two are security issues.**

1. **Rotate the Racing Post `REFRESH_TOKEN`.** It was exposed in screenshots and is **burned**. Invalidate at source, regenerate, before any live scrape. *(Carried forward since 29 Jun — still open.)*
2. **Set a repo-local git identity.** Currently a personal email. Do this **before any push**. *(Carried forward since 21 Jun.)*
3. **Resolve the commission constant.** `clv.py` uses `DEFAULT_COMMISSION = 5%`; the UI caption says 5%; the Stage-0 pre-registration corrected it to **2%, Betfair's actual rate**. Every historical CLV/P&L number in this document was computed at **5%**. Decide, unify, and note which results need re-running. *(This is the single most consequential unresolved inconsistency in the codebase.)*
4. **Confirm CC runs from a native WSL cwd** (`pwd` → `/home/gabriel/projects/racing_project`, **not** `//wsl.localhost/`).
5. **Delete `C:\Users\gabriel\Desktop\index_editorial.html`.**
6. **Confirm the `uphill_finish` verification commit landed** (was staged at the 30 Jun wrap).

**P1 — Decide the fork. This is the operator's call, not an engineering one.**

The four options, with the honest case for each:

| Option | Cost | Case for | Case against |
|---|---|---|---|
| **A. Buy Betfair PRO tick data** and run the pre-registered in-running gate | tens–low hundreds of £ | This is **the one open action** from 1 Jul. Everything is built and pre-registered; CC can run it the moment the data exists. It is the only path that can *resolve* the INCONCLUSIVE liquidity screen. **Pre-registered bar (verbatim, `Strategy_Direction_InRunning.md`):** liquidity PASS-to-edge-stage iff *"≥ £X matched (conservative fill) in ≥ Y% of ≥ N qualifying opportunities"* with *"N = 2,000, X = £100, Y = 50%"*; then edge PASS iff *"matched-subset ROI beats the stratified null by ≥ +1.0% … AND is > 0 absolute … corroborated same-sign on discovery,"* net **2% commission** — decided on holdout. | Racing in-play liquidity is **thin and shrinking** (~20% of turnover; £1.5bn → <£1bn 2020–24). The gate may well fail — which is a *cheap, informative* fail. **Buy the right window: not re-purchasable once bought.** Verify each market's **actual `betDelay`**, do not assume 1s. |
| **B. Test the narrow subpopulations** (free) | £0 | Never tested — every test so far was population-wide. Four have stated mechanisms: the original target segment (Flat, ≤6 runners, ≤2f); small/regional tracks vs majors; extreme field sizes; lowest class tiers. | **Narrowing increases mirage risk.** Only legitimate with a **mechanism decided before seeing results**. The holdout is already partially burned. |
| **C. Buy TPD sectionals / Weatherbys pedigree** | commercial, unquoted | Both the five exhausted experiments and the data-sources doc **independently** point here. `run_style_proxy` is a proxy from aggregated prior `comment`, **not true pace** — a null on it means "the free proxy prices out," not "geometry is irrelevant." | *"Professional syndicates already trade on this data."* Expect "probably still mostly priced, possibly a thinner residual." Higher barrier to entry ≠ guaranteed edge. Not a build; a **money + vendor-contact decision**. |
| **D. Pivot the sport to football** *(proposed 9 Jul, undecided)* | £0 data (football-data.co.uk, Understat/FBref, StatsBomb open data) | **Buys tradability, not edge.** Football match-odds is Betfair's deepest market; a match is 90 minutes of discrete state changes vs a 3-minute race. The in-running liquidity gate would plausibly **actually pass** rather than return INCONCLUSIVE. Betfair historical covers football in the same tiers (`eventTypeId 1`). | Pre-match 1X2 is **the most-modelled market in sports betting**; Pinnacle's close is as brutal a benchmark as BSP. Expect Stage-1 to earn ~3% blend weight again. **Stage-1 does not port** — conditional logit is a discrete-choice-over-a-choice-set model; football needs a bivariate-Poisson / Dixon-Coles goals model. The entire feature catalogue dies. The Expert Fee still applies. |

**What ports to football if D is chosen** (from the 9 Jul assessment): `parse_bsp.py` (change `eventTypeId 7 → 1`), `clv.py` + its 10 tests, the calibration/proper-score harness, the Stage-2 Benter blend, and — most valuable — the **holdout + price-band-stratified-null + Brier-gate verdict machinery**. The leakage *methodology* ports; the manifest must be rebuilt from scratch.

**P2 — Deferred until the fork is resolved.**

- Finish the `ui-editorial` cleanup (list in `UI_NOTES.md`), **see the Scan mode render** (never yet eyeballed), then promote: replace `index.html`, retire standalone `edge_tracker.html`.
- Two discipline-touching cleanup items rank above cosmetics: **(a)** verify all 20 derived fields visibly carry the prior-run guard on their chips (`career_wins` is derived from `pos` and sits in the green selectable tier with **no visible "prior-run only" marker**); **(b)** add a persistent "not yet backtested" indicator on Build — *you can currently build a rule, skip Backtest, jump to Scan, and bet it.*
- **Scanner Tier-2** (history-join derived features) — makes the interaction rules scannable on today's cards, not just backtestable.
- The **run_style × draw × geometry** interaction test (Direction 1), if B is chosen. **Spec it fully first** — the spec was truncated on 30 Jun.

---

## 11. Risks

### 11.1 Technical

| Risk | Severity | Status |
|---|---|---|
| **Silent zero-match failures.** Three instances found (`dist_f` suffix, course-name byte-match, horse-name country suffix). All returned plausible-looking nulls, not errors. | **High** | Class of bug identified and named ("Gotcha 2"). Assume a fourth exists. |
| **The joined CSV is not date-sorted.** Any order-dependent computation (history joins, rolling features) is silently wrong unless it sorts first. | **High** | Known, documented, not structurally enforced. |
| **The holdout is partially burned.** Repeatedly touched across 8 tests, a segmentation sweep, and a verdict rewrite. | **High** | Unquantified. |
| **The struck price is not a real fill.** `wap` is a window average. | **Medium** | Acknowledged. Only a real timestamped price (PRO tier / forward capture) fixes it. |
| **No market-impact model** for pre-race backtests. Your own BSP order becomes part of the reconciliation in thin markets. | **Medium** | Unmodelled. |
| **Commission constant is inconsistent (5% vs 2%).** | **Medium** | Unresolved. |
| **54 unverified `uphill_finish` calls; dual-config courses unresolved.** | **Low** | Engine-gated; cannot leak into a rule. |
| **Fixtures diverge from live data** (int vs string). | **Low** | One instance found + regression-tested. Assume more. |
| **`.venv` vs `.venv313`** — `.venv` (Python 3.10) is the modelling venv and **HAS pandas**; `.venv313` (Python 3.13) is **rpscrape-only, NO pandas**. | **Low** | Use `.venv` for modelling/backtests; `.venv313` only to run `rpscrape`. (Verified 2026-07-09 — HANDOVER earlier stated this backwards.) |

### 11.2 Financial

| Risk | Notes |
|---|---|
| **No risk limits exist.** No max stake, daily loss cap, exposure limit, or kill switch. | **Blocking prerequisite for any live capital.** |
| **No edge has been found.** Deploying capital now would be deploying into a measured −1.00% CLV. | The apparatus exists precisely to prevent this. |
| **Liquidity in thin markets.** BSP is only as sharp as the market is deep; a large order moves the reconciliation. Inefficiency concentrates exactly where BSP is least reliable — *"low attention ≠ free money."* | Capacity analysis is inseparable from any BSP strategy. |
| **Betfair PRO data is not re-purchasable** for a period once bought. | Choose the window deliberately before spending. |
| **Edges are small, competitive, and decaying.** The literature's own summary. | Do not import "abundance framing" from retail sources. |

### 11.3 Regulatory / T&Cs

| Risk | Detail | Status |
|---|---|---|
| **Betfair Expert Fee** | Replaced the Premium Charge on **6 Jan 2025**. Taxes profit **20–40%** above **£25k/year lifetime gross profit**. A structural drag crypto exchanges do not impose. | **Project research finding; not independently verified against Betfair's current T&Cs by this document. Verify before modelling net returns.** |
| **UK in-play bet delay** | ~**1 second**, regulatory, universal. Acts as an equaliser against latency arms races — and as a hard floor on any reaction-speed strategy. | Baked into the Stage-0 fill model (1.0s). **The pre-registration explicitly requires verifying each market's actual `betDelay` rather than assuming 1s.** |
| **Account restriction** | Binding for **bookmaker** betting at any scale. **Not** a risk on the exchange — the notes flag it specifically as something retail sources hand-wave. Relevant only if the project ever prices against bookmakers. | Not applicable to current design. |
| **Credential exposure** | The Racing Post `REFRESH_TOKEN` **is burned** (visible in screenshots). `.env` is git-ignored, so it was never committed, but the token itself is exposed. | **OPEN. Rotate.** |
| **Racing Post ToS** | `rpscrape` scrapes HTML behind a login. Scraping a logged-in site may breach its terms. | **Not assessed anywhere in the project docs. Unverified.** |
| **Jurisdiction** | Operator appears UK-based (GB racing, £, Betfair UK, UK in-play delay). Betting is legal and regulated; gambling winnings are not taxed for individuals in the UK. | **Inferred, not stated in any doc. Unverified.** No tax, entity, or licensing analysis exists. |

---

## 12. Open questions / gaps

### 12.1 Documents referenced but absent from the snapshot

These were cited by `PROJECT_NOTES_append_1Jul.md` and `Handover_NextSession_30Jun.md`. **Reconciled 2026-07-09 against the repo** (`RECONCILIATION.md` §7):

- `Deep_Research_Brief_InRunning_Trading.md` — **genuinely missing** (not in the repo tree). The entire in-running viability research pass; its findings survive only second-hand in §3 (1 Jul) via `PROJECT_NOTES_append_1Jul.md`.
- `Strategy_Direction_InRunning.md` — **PRESENT** at the repo root. Holds the committed pre-registration, now quoted **verbatim** in §3 (1 Jul) and §10.2 Option A. *(No longer absent.)*
- `prompts/InRunning_Stage0_PreRegistration.md` — **PRESENT.** The canonical Stage-0 brief; the §3 N/X/Y quotes are now first-hand, not second-hand. A third copy of the pre-registration sits at `analysis/preregistration_inrunning.md`. *(No longer absent.)*
- `README.md` — **PRESENT** at the repo root. `One_Day_Data_Plan.docx` — not in the repo tree (a `.docx`, likely never synced); still unread.

Two documents in the snapshot are **zero bytes**:
- `Betfair Betting Exchange in Academic Research`
- `Detecting Horse Racing Corruption` — cited by `Free_Experiment_Catalogue.md` Test 5 as the basis for the Shin's-z anomaly filter.

### 12.2 Unresolved technical questions

1. **Which commission rate is correct — 5% or 2%?** Every backtest number in this document assumes 5%. Betfair's standard rate is 2% per the Stage-0 correction. **Which historical conclusions change at 2%?** (Note: none of the *verdicts* plausibly flip — they were negative before commission — but the magnitudes are all wrong.)
2. **How burned is the 2025–26 holdout?** Never quantified. No count of how many times it was scored.
3. **Does `wap` genuinely represent an achievable fill?** It is a volume-weighted *average* over a window, not a timestamped price.
4. **Does the `course` column distinguish dual-configuration tracks** (Aintree Mildmay/National, Newmarket Rowley/July, Salisbury, Fontwell)?
5. **Does the Betfair cache carry place-market SP?** Determines whether Free-Experiment Test 4 (place markets) is a free test or a data purchase.
6. **What is the actual `betDelay` per market?** The pre-registration explicitly forbids assuming 1s.
7. **Where exactly is the join entry point?** The notes name both `parsers/join_form_bsp.py` and `offline_join.py`. Unclear which is canonical.
8. **Does the newer `rpscrape` expose Topspeed (`ts`)?** Check `settings/user_settings.toml` for a toggle; if absent, the vendored version dropped it. Re-scrape is ~6 min.
9. **Was the `uphill_finish` verification commit made?** Staged at wrap on 30 Jun.
10. **What are the exact contents of `field_manifest.json`'s 6 "pending acquisition" entries?** Only their names are recorded.

### 12.3 Undocumented entirely

- **Risk limits, staking rules, and any live-execution design.** Blank.
- **Any Betfair API integration** — app key, cert login, session management, rate-limit handling.
- **Deployment / scheduling.** Everything is run by hand.
- **The `models/` scripts' CLI signatures.** No `--help` output or argparse spec is recorded anywhere.
- **`requirements.txt` / dependency pinning** for the project venv. Only `rpscrape`'s deps are listed.
- **Racing Post ToS compliance.**
- **Jurisdiction, tax, entity structure.**
- **What the `.venv` vs `.venv313` split actually contains.**

### 12.4 Strategic questions requiring the operator

- **Is this a money-making project or a skill-building project?** `Milestone_Eight_Tests_Summary.md` offers option 3 — *"treat tonight as the answer"* — as a legitimate, non-defeatist end-state. The incoming engineer cannot resolve the fork in §10.2 without knowing this.
- **If football (option D): re-run the pre-race edge hunt on a new sport, or abandon pre-race entirely and build the in-play system on a market with real liquidity?** These imply completely different work. In the latter case `stage1_logit.py` and the feature catalogue are not ported at all; you build an in-play state model (score, time, red cards → live win probability) and go straight to the liquidity gate.

---

## 13. Glossary & key decisions

### 13.1 Glossary

| Term | Meaning |
|---|---|
| **BSP** | Betfair Starting Price. The exchange's reconciled price at the off, formed by matching maximum volume between SP backers, SP layers, and unmatched limit orders. **Margin-free.** The project's benchmark, **never a model input.** |
| **ISP** | Industry Starting Price — the on-course bookmaker average. Carries overround. Not used. |
| **CLV** | Closing Line Value. `struck / BSP − 1` for a back. The project's validation metric. |
| **Lay-CLV** | `BSP / struck − 1`. **Reciprocal, not negated,** relative to back-CLV — they differ by a strictly-positive AM-GM convexity term `(wap−bsp)²/(wap·bsp)`. |
| **WAP / PPWAP** | Pre-play volume-weighted average traded price. The project's real (interim) struck price. Column `wap`. |
| **`morning_wap`** | The morning volume-weighted price. Known pre-race. **Blocked as a who-wins input; legitimate as an input for predicting the price move.** |
| **Stage-1** | The fundamental win-probability model. Conditional logit over `or, draw, lbs, age`. |
| **Stage-2 / Benter blend** | Conditional logit on `log(model_prob)` and `log(market_prob)`, grouped by race = a weighted geometric mean. The learned model weight **is** the answer to "did my model add anything." |
| **Blend weight** | The Stage-2 coefficient on the model. **Measures orthogonality to the market**, not predictiveness. Currently 6.9% (was 3% under LTP; **only comparable across the same struck-price convention**). |
| **Drift criterion** | `wap / morning_wap − 1`. Which side of the informed move a selection sits on. Good **backs** should steam (shorten); good **lays** should drift (lengthen). |
| **Three-metric read** | Proper scores + blend weight + drift, **always together.** Brier alone can fool you. |
| **Composition-fair null** | A BSP-calibrated baseline computed on the **same horses** the rule selects, not the full field. Corrects OR-skew. **Insufficient on its own** — see next. |
| **Price-band-stratified null** | The **current** verdict baseline. 14 BSP odds bands; each selection benchmarked against the field's actual back-all@BSP ROI **in its own band**. Neutralises favourite-longshot composition, which the composition-fair null did not. |
| **Brier-corroboration gate** | To read RULED-IN, the blend must beat BSP on Brier over the selection's holdout horses. **A CLV edge with no probability edge behind it cannot rule in.** |
| **Canary check** | A hindsight-perfect / monkeypatched-passing run that *must* show a large edge. If it doesn't, the test is **INCONCLUSIVE (underpowered)**, not a clean fail. |
| **Anchor test** | Every new feature's within-race Spearman(feature, finishing position) must land near `or` (−0.13, pre-race), not near `rpr` (−0.88, post-race). |
| **Verdict states** | `ruled-in` (green) · `to-holdout` (amber, unconfirmed) · `priced` (red) · `thin` (grey). Only `ruled-in` and `to-holdout` may flag live races. |
| **Gotcha 2** | The class of **silent zero-match** bug: a join key mismatch that returns plausible nulls instead of an error. Three instances found. |
| **FLB** | Favourite-longshot bias. Bettors overbet longshots. Much milder on the exchange than with bookmakers (Smith, Paton & Vaughan Williams 2006, *Economica*: 2.17% in mean bookmaker prices, significantly lower on Betfair). **Absent or mildly reversed in Hong Kong/Japan (Busche 1994)** — proving it is a product of market structure, not a law of nature. |
| **Shin's z** | An insider-trading-incidence estimator derived from odds structure. **Caveat (Whelan 2025): z partly measures overround/margin, not purely insiders.** Never implemented. |
| **Expert Fee** | Betfair's profit charge, replaced the Premium Charge 6 Jan 2025. 20–40% above £25k/year lifetime gross profit. |
| **CC** | Claude Code — the coding agent used throughout. |
| **TPD** | Total Performance Data. GPS/sectional provider; since the 2024 consolidation, the single gateway to the complete 59-course British sectional database. |

### 13.2 Key decisions (do not relitigate)

| Decision | Rationale | Date |
|---|---|---|
| **BSP is the benchmark, never a model input.** | It is the margin-free, market-formed, publicly-recorded closing line. Verified near-perfectly calibrated on real data. | 16 Jun |
| **`rpr` is permanently excluded.** | Post-race by nature. Confirmed by two independent tests. No fix exists. | 18 Jun |
| **Any future rating feature must pass the same pre/post-race anchor test.** | | 18 Jun |
| **Use proper scores (Brier / log-loss), not ECE.** | ECE rewards an under-confident model that just predicts the base rate. | 18 Jun |
| **FREE data only, for now.** Paid (TPD, Weatherbys) is a deliberate later decision. | Prove there is no free signal *before* spending — that is the prior you want. | 16 Jun |
| **Real struck prices only. No proxies.** | The proxy becomes the metric (±27pts CLV swing on a flat Brier). | 21 Jun |
| **Read Brier + blend weight + drift together, always.** | Predictiveness ≠ orthogonality-to-market. Proven live. | 21 Jun |
| **Server-side leakage refusal, independent of the UI gate.** | Never trust the client. | 28 Jun |
| **Derived features are prior-run only, joined strictly before the current race date.** | Non-negotiable `leakage_note` on every one. | 28 Jun |
| **The verdict is decided on the holdout, benchmarked to BSP.** | | 28 Jun |
| **The verdict baseline is the price-band-stratified null + a Brier-corroboration gate.** | Both were needed. The stratified null alone still let the false rule-in through at +1.33%. | 30 Jun |
| **Tier-2 course descriptors are gated three ways until human-verified.** | Manifest `selectable:false` + UI ⊘ chip + engine refusal. | 30 Jun |
| **Only `ruled-in` / `to-holdout` strategies may flag live races.** | Enforced at the promote step. Verified by contrast (14 flags with override on, 0 with it off). | 29 Jun |
| **Staking is secondary to the verdict.** *"Compounding never creates edge."* | Demonstrated: a priced rule cliffs to −100% under every staking model. | 29 Jun |
| **Pre-register the gate before any spend.** | Stage 0 was written and dated before the PRO-data decision. | 1 Jul |
| **The in-running question is independent of the pre-race conclusion.** | A good or bad in-running result does not change the fact that free public knowledge-based edge is priced. That conclusion stands on its own. | 1 Jul |
| **CC builds the plumbing; the operator understands the model first, not handed off blind.** | | 16 Jun |
| **`PROJECT_NOTES.md` is the single running log.** The Claude Project copy is a synced snapshot of the on-disk (H:) original. | | 16 Jun |
| **Work inside WSL, never via `/mnt/h/` or `//wsl.localhost/` Windows paths.** | I/O crosses the boundary; tools misbehave from a non-POSIX cwd. | 16 Jun |
| **Do not place bets, log into Betfair to bet, or call any live betting endpoint.** | Standing guardrail for the agent. | 16 Jun |

---

## 14. Appendix — start-of-session commands

**Paths + test count verified 2026-07-09** (`RECONCILIATION.md`); runtime behaviour of `--serve` not exercised.

```bash
# 1. Open VS Code WSL-connected (green "WSL: Ubuntu-22.04" badge).
#    Ctrl+Shift+P -> "WSL: Connect to WSL" -> open /home/gabriel/projects/racing_project
#    A NEW WSL TERMINAL. Not a Windows one.

cd ~/projects/racing_project
pwd                              # MUST print /home/gabriel/projects/racing_project
                                 # NOT //wsl.localhost/...

source .venv/bin/activate        # .venv (3.10) HAS pandas — use for modelling/backtests
                                 # .venv313 (3.13) is rpscrape-only (NO pandas); use it only to run rpscrape

git checkout ui-editorial
git status                       # confirm clean
git config user.email "<repo-local identity>"   # NOT the personal default

ls data/joined/                  # expect joined_gb_2018_2026.csv (726,044 rows)

python -m unittest discover backtest    # expect 130 tests, all green

python racing_rulebuilder/run_strategy.py --serve   # 127.0.0.1:8765
# then open racing_rulebuilder/index.html in a browser
```

**Environment variables / credentials — all redacted, all user-managed:**

| Variable | Location | Notes |
|---|---|---|
| `EMAIL` | `vendor/rpscrape/.env` | Racing Post account email |
| `AUTH_STATE` | `vendor/rpscrape/.env` | `auth_state` browser cookie |
| `ACCESS_TOKEN` | `vendor/rpscrape/.env` | `CognitoIdentityServiceProvider…accessToken` cookie value |
| `REFRESH_TOKEN` | `vendor/rpscrape/.env` | ⚠️ **BURNED — exposed in screenshots. ROTATE BEFORE ANY SCRAPE.** |
| Betfair account | interactive, browser | Used only on `historicdata.betfair.com`. **No app key or cert has ever been provisioned.** |

`.env` is git-ignored and was never committed. **The user extracts and pastes these values themselves; the agent never handles passwords.**

---

*End of handover. Reconcile §5 and §7 against the actual repository before trusting any path in this document.*

# Pre-Registration — In-Running / Trading Gate Program (Q1–Q4)

**Governs:** all gate/analysis work on `data/historical/betfair_pro/` (Betfair PRO
full-ladder + traded-volume stream, GB horse racing, May-2015 → Apr-2016).
**Status:** DRAFT — committed *before first data contact*, **awaiting user sign-off**.
No parser/analysis code has been run against the PRO market content for gate work.
**Date committed:** 2026-07-05.

---

## 0. The immutability rule (the whole point of this document)

This document fixes the falsifiable claims, nulls, fill model, splits, and pass/fail
bars **before** looking at a single tick of the PRO market stream — the exact
discipline that made the pre-race work trustworthy and that the free-data catalogue
(Test 1–8) and Test 4 enforced.

- **Nothing here may be altered after first data contact** except by a **dated
  amendment** in §12 stating *what changed and why*. Deciding a bar after seeing
  results is how the `trainer_course_sr` mirage happened; this rule exists to make
  that impossible.
- **"First data contact" is defined precisely** as: the first time any script
  decompresses and parses the *content* (JSON stream) of a `data/historical/betfair_pro/`
  market file **for Q1–Q4 gate work**. It **explicitly excludes** the ≤10-market
  ingest-validation sample already taken on 2026-07-04/05 (recorded in `PROJECT_NOTES.md`),
  which only confirmed PRO fields (`atb`/`atl`/`trd`, sub-second `pt`, `eventTypeId`,
  `countryCode`) and fitted nothing. Path-only `tar -tf` listings (the ingest inventory)
  are likewise not data contact.
- Edits **before** sign-off + first parse are free (still pre-registration); they do
  **not** require a §12 amendment. The lock engages at first gate parse.

---

## 1. Provenance & inherited discipline (non-negotiable, carried verbatim)

Same rules as the eight-test free-data program and Test 4. Money logic is written
**after** the verdict rig, never before.

- **Pre-register the bar before the data** — claim, null, fill model, pass/fail fixed
  in writing first (this file).
- **Price-band-stratified structural nulls**, not naive/uniform ones — each qualifying
  runner is benchmarked against the mean outcome of all qualifying runners *in its own
  entry-price band*. This is what closed the favourite-longshot hole pre-off and named
  the Test 4 lay artifact (the +32% "edge" that was pure BSP-band composition).
- **Per-course stratification** on top of price bands (§9) — course geometry drives
  in-running price paths; an unstratified null invites a course-composition artifact
  (the in-running analog of the Test 4 BSP-band-composition artifact).
- **Brier-corroboration gate** where a probability/forecast claim is made — a CLV/
  drift edge that carries no forecasting skill (fails to beat BSP on Brier) is flagged
  CLV-relative-only, exactly as Test 4 V2 was.
- **Discovery / holdout split** (§7), verdict on holdout, discovery for same-sign
  corroboration only.
- **Hindsight-perfect-fill / rpr-style power canary** (§ per-question) — so a null
  result is *informative*, not merely underpowered.
- **Conservative fill model is the crux** (§6) — paper fills at the displayed price for
  unlimited size are the deadliest in-running artifact. Pinned now, never chosen after.
- **Intra-race leakage discipline** — a rule may only use price/volume that existed at
  the *simulated instant*, never a later tick in the same race (the within-race analog
  of "strictly-prior runs only").
- **Report the kill.** If a question fails as specified, that IS the result. No retune-
  to-pass; no post-hoc subpopulation narrowing.

**Reference docs (canonical, read alongside this file):**
- `Strategy_Direction_InRunning.md` — full Stage-0 spec of the liquidity + edge gates (source of Q1/Q2).
- `prompts/InRunning_Stage0_PreRegistration.md` — canonical Stage-0/1 brief (2% commission, fill model).
- `Handover_InRunning_Stage1_Pending.md` — free-screen liquidity first-pass (NOT KILLED / INCONCLUSIVE).
- `Milestone_Eight_Tests_Summary.md` — summary of the eight free-data tests. **⚠ NOT YET IN REPO** (to be compiled from the PROJECT_NOTES Test 1–8 entries; see §13). Until it exists, the canonical record is the dated PROJECT_NOTES entries + `prompts/test_4_prompt.md`.
- `PROJECT_NOTES.md` — the 2026-07-03 **Test 4** lay-side note (the named-artifact exemplar) and the 2026-07-04/05 PRO ingest note.

---

## 2. The data (fixed universe of this study — facts from ingest, no content parsed)

From the path-only ingest inventory (`PROJECT_NOTES.md`, 2026-07-04/05):
- **12 tars, 45.71 GiB, 153,613 members**, PRO tier (`atb`/`atl`/`trd` ladders +
  sub-second `publishTime` confirmed on the validation sample).
- **One continuous block: 2015-05-01 → 2016-04-30 = 365 racedays** (only 2015-12-25
  absent = no GB racing → not a gap). 7 stray 2016–18 days are out-of-window noise, **excluded**.
- `eventTypeId == 7` (horse racing) = 100% of the validation sample; countryCode
  predominantly **GB**, some **IE**.

This 12-month window is the **entire** evidentiary base. Every Q1–Q4 verdict is a
verdict *about GB flat in-running/pre-off microstructure in 2015-16* and is caveated
accordingly (§8).

---

## 3. Universe — GB FLAT only (turf + AW); jumps EXCLUDED ex ante

- **Included:** GB (`countryCode == "GB"`), `eventTypeId == 7`, **flat** races only
  (turf + all-weather). Selection is by `marketDefinition` (`countryCode`, `marketType`
  = `WIN`, and race-type/name flat classification), cross-checked against the project's
  existing course/going reference where a market maps to a known GB flat course.
- **IE excluded** by default (window is a GB study; IE markets in the pull are dropped,
  not analysed). If an IE inclusion is ever wanted it is a §12 amendment.
- **Jumps EXCLUDED ex ante — pre-registered reason:** a faller/unseat/pull-up on a
  jumps runner imposes a **3–10% per-runner faller cost** that makes an **unhedged
  back-to-lay in-running tail risk unacceptable** (a leader you have laid can be
  brought down or fall while you hold liability). Flat has a near-zero non-completion
  rate, so the in-running lay-the-tiring-leader family has **bounded** tail risk there.
  **Jumps are a separate future program**, not a subpopulation of this one — they are
  not revisited by any Q1–Q4 amendment.
- **Non-completion handling (flat, rare):** a runner that falls / unseats / is pulled
  up / refuses is scored at its **actual Betfair settlement** (loser / void per market
  rules), never silently voided or dropped — dropping them would understate exactly the
  tail this universe is chosen to bound. The realised faller rate in the flat sample is
  reported as a robustness figure.

---

## 4. Q1 — LIQUIDITY FEASIBILITY  *(PRIMARY gate; the cheapest kill)*  — CONFIRMED

Transcribed from the confirmed Stage-0 pre-registration (`Strategy_Direction_InRunning.md`
§2–3, confirmed 2026-07-01). Prior belief, stated to be falsified: **this probably
fails here.** Q1 runs first; Q2 is only run if Q1 passes.

- **Claim:** a pre-registered in-running entry signal can get **≥ £X matched in > Y% of
  ≥ N qualifying opportunities** under a realistic, latency- and liquidity-constrained
  fill model.
- **Parameters (confirmed, do NOT retune):** **N = 2,000** qualifying opportunities ·
  **X = £100** target matched stake · **Y = 50%**.
- **Qualifying opportunity (confirmed placeholder signal):** a GB flat runner whose
  pre-race dominant run-style proxy = **`led`** (front-runner), entered when its
  in-running price **first trades ≤ P_trigger = 2.0**. (Signal-agnostic framework; this
  instantiation is fixed for Q1. The edge-gate signal may be revisited at Q2 — §5.)
- **Fill model (the crux, §6).** An opportunity counts as **filled** iff ≥ £X is matched
  under §6; a partial < £X is **not filled** (counts against Y).
- **Metric is liquidity, a market property** → measured over the **whole** qualifying
  set; **no discovery/holdout split for Q1** (liquidity is not fitted). If qualifying
  opportunities are rarer than N in the window, **widen nothing / lower nothing** —
  report the shortfall; the 365-day GB flat window is the fixed base.
- **PASS → run Q2** iff ≥ £X matched in ≥ Y% of ≥ N qualifying opportunities.
  **Otherwise FAIL → abandon the in-running direction** (no Q2, no further work).
- Note: the free-data first-pass (`models/inrunning_liquidity_screen.py`) was **NOT
  KILLED / INCONCLUSIVE** because `ip_vol` is a total-in-play **upper bound**; Q1 on the
  PRO ladder is the point-in-time test that turns that into a definitive PASS/FAIL.

---

## 5. Q2 — IN-RUNNING EDGE  *(SECONDARY gate; only if Q1 passes + fresh authorization)*  — CONFIRMED

Transcribed from `Strategy_Direction_InRunning.md` §4–5.

- **Claim:** on the **matched subset** (opportunities where ≥ £X actually filled), the
  net-2%-commission ROI beats the price-band-stratified structural in-running null by
  **≥ +1.0%** (`EDGE_TOL`) **AND is > 0** absolute, **corroborated same-sign on discovery**.
- **Metric:** net-of-2%-commission ROI per matched opportunity. Paper edge on unfillable
  opportunities does **not** count.
- **Null:** **price-band × course-stratified** structural in-running return (§9) — each
  qualifying runner benchmarked against the mean net outcome of all qualifying runners in
  its own entry-price band *and* course stratum. Strips the price-dependent (and course-
  dependent) in-running drift everyone gets.
- **Commission = 2%** on net winnings (canonical; the 5% in `clv.py` is a pre-off carry-
  over and does not apply here).
- **Power canary (mandatory):** re-run Q2 with the realistic fill replaced by the **best
  in-running price actually traded** in each opportunity. This MUST show a large edge
  (proves the rig can detect edge if one exists — the in-running analog of the rpr canary).
  **If even the hindsight-perfect fill shows no edge → INCONCLUSIVE**, not a clean fail.
- **Verdict on holdout** (§7); discovery for corroboration only.
- **Kill (any):** matched-subset ROI ≤ 0 net commission; or ≤ null + tol; or not
  same-sign corroborated; or **edge exists ONLY under hindsight-perfect fill and vanishes
  under the realistic fill** (a latency/liquidity artifact — the in-running analog of the
  WAP-vs-close timing artifact, not harvestable).

---

## 6. The conservative fill model (pinned now — shared by Q1/Q2 and any in-running question)

- **Data used:** in-running **price + traded-volume-at-price** (the `atb`/`atl`/`trd`
  ladders in the stream), never BSP/LTP alone.
- **Latency `L = 1.0 s`** between signal and matchable moment — act on the ladder at
  `t + L`, never at the signal instant `t`. **`betDelay` is VERIFIED per market** from
  `marketDefinition.betDelay` rather than assumed (some sources cite 2 s; if a market's
  `betDelay` ≠ 1 s, its own value is used and the mix is reported).
- **Cross the spread:** take the available side. Matched £ =
  `min(£X, £ available at or through your price within slippage S = 1 tick)` at `t + L`.
- A fill counts **only when price genuinely trades THROUGH your level** in the replayed
  book; cap at actually-available matched size; never assume infinite size at the
  displayed price. **When unsure, err MORE conservative** — optimism here manufactures
  false positives.

---

## 7. Discovery / holdout split (adapted to the 12-month PRO window)

The confirmed Stage-0 cutoff was 2023-12-31 "or the data window's midpoint — to be set
at Stage 1." The PRO window is 2015-05 → 2016-04, so the 2023 cutoff is inapplicable and
the **window split** governs:

- **Discovery = 2015-05-01 … 2015-12-31** (8 months, 244 racedays).
- **Holdout   = 2016-01-01 … 2016-04-30** (4 months, 121 racedays).
- **Verdict decided on holdout; discovery for same-sign corroboration only** (applies to
  Q2 and any fitted question; Q1 liquidity uses the full set, §4).
- **Pre-registered caveat:** a chronological split confounds *season* with *split*
  (discovery skews summer/autumn turf; holdout skews winter AW). This is accepted to
  preserve the no-look-ahead discipline; **per-course and per-going stratification (§9)
  is the mitigation**, and any PASS must survive within-stratum, not just in aggregate.
  *(Alternative offered for sign-off: odd/even-week interleave to balance season at the
  cost of adjacent-race proximity. Chronological is the default unless you choose otherwise.)*

---

## 8. Era weighting / external validity (2015-16 data → 2026 live market)

- The window is a **single 2015-16 regime**, so there is no *intra-window* era weighting
  to apply — all 365 racedays weighted equally. A within-window drift check (a rule/market
  change mid-sample) is run as robustness only.
- **The load-bearing caveat:** 2015-16 in-running microstructure is **~10 years stale**
  relative to a 2026 live deployment — `betDelay`, bot/algo prevalence, queue dynamics,
  commission tiers, and participant mix have all evolved. **Any Q1/Q2 PASS is PROVISIONAL**
  and does not authorise live capital on its own: it must be **re-confirmed on a small,
  current-era mini-sample** (a fresh recorded/purchased stream) before any live prototype.
  This is pre-registered so a 2015-16 pass cannot be quietly treated as a 2026 pass.

---

## 9. Per-course (and per-going) stratification

- The project already holds a **65-course static geometry table** (uphill finish, draw
  bias, straight/turning — `data/reference`), verified per-course for 11 courses.
- The structural in-running null (§5) is stratified by **price-band × course**; where a
  course cell is too thin (< the project's ~min-cell rule), courses are pooled by
  **geometry class** (e.g. uphill-finish / turning / straight-track) rather than left
  unstratified. Going (`marketDefinition` / reference) is a secondary stratum where
  populated.
- **Why:** in-running price paths are course-shaped (a front-runner on an uphill finish
  tires differently than on a flat straight). An unstratified null lets **course
  composition** masquerade as edge — the direct analog of the BSP-band-composition
  artifact Test 4 exposed. A PASS must hold **within** strata, not only pooled.

---

## 10. Q3 & Q4 — ⚠ PROPOSED, PENDING YOUR SIGN-OFF (prompt truncated here)

> **Transparency note:** the source prompt was cut off at the `## Q1–Q4` section
> (mid-word, "separate fu…"). Q1 and Q2 above are transcribed from your **confirmed**
> Stage-0 pre-registration and are safe. **Q3 and Q4 below are my proposals** — grounded
> in the PRO data's unique capabilities and the project's stated "next shots"
> (timestamped strike for true CLV; in-running) — **for you to confirm, edit, or
> replace.** They are pre-registration placeholders; the immutability lock (§0) does not
> engage until sign-off + first parse, so replacing them now costs nothing.

### Q3 (PROPOSED) — Pre-off ladder microstructure: true timestamped-strike CLV
The free work could only use WAP and BSP snapshots; every "edge" collapsed to the
**WAP-vs-close timing artifact**. The PRO ladder carries the *full pre-off traded ladder
second-by-second*, enabling a genuine timestamped strike.
- **Claim:** striking a pre-registered selection at a pre-registered pre-off moment
  `T_strike` (e.g. `off − 120 s`) on the live ladder yields **positive true CLV vs BSP**
  (`bsp/struck − 1 > 0`) that **beats a price-band × course-stratified null AND passes the
  Brier gate** (blend beats BSP), out of sample.
- **Kill:** CLV that is just the structural WAP→BSP drift of its price band (Test 4's
  named artifact) → PRICED. No Brier improvement → CLV-relative-only, not a forecast edge.

### Q4 (PROPOSED) — In-running back-to-lay scalp economics on the front-runner family
The natural complement to Q2: not "is there directional edge" but "**does the
mechanically predictable front-runner price path (shorten on an uncontested lead → layable
as it tires) produce a positive round-trip after realistic two-sided fills + 2% commission**."
- **Claim:** a pre-registered back-at-entry / lay-at-exit (or the reverse) round trip on
  the `led`-≤2.0 family clears **> 0 net of 2% commission and the §6 fill model on BOTH
  legs**, beats the price-band × course null by ≥ +1.0%, holdout-corroborated, with the
  hindsight-fill canary.
- **Kill:** positive only under one-sided/hindsight fills; round-trip ≤ null+tol; tail
  dominated by the rare flat non-completion (§3).

*(If your intended Q3/Q4 differ, paste them and I will swap them in verbatim before any
parse — nothing downstream depends on the proposed wording.)*

---

## 11. Global ordering & kill criteria

1. **Q1 (liquidity) gates everything.** FAIL → abandon in-running (Q2/Q4 not run).
2. **Q2 / Q4 (in-running edge / scalp)** run only on a Q1 PASS **+ fresh authorization**.
3. **Q3 (pre-off CLV)** is independent of Q1 (it is a pre-off question) but shares the
   stratified-null + Brier discipline; it may run in parallel once authorized.
4. Any question: **report the kill as the result.** No retune-to-pass, no post-hoc
   subpopulation narrowing, no moving `EDGE_TOL`/N/X/Y/`T_strike` after data contact.

---

## 12. Amendment log  *(append-only; each entry: date — what changed — why)*

_(empty — no amendments; the document is pre-data-contact.)_

---

## 13. Non-goals / what is NOT happening under this commit

- No parsing/replay/fitting of PRO market content for gate work yet (this file governs it,
  it does not perform it).
- No live capital; no TPD/sectional purchase; no jumps.
- `Milestone_Eight_Tests_Summary.md` is **referenced but not yet created** — flagged for
  compilation from the PROJECT_NOTES Test 1–8 entries (offered, not assumed).

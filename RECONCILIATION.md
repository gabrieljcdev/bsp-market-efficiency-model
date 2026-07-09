# RECONCILIATION — HANDOVER.md vs. the actual repository

**Date:** 2026-07-09
**Method:** every path, count, signature and result below was checked against the
live filesystem / git / a real `unittest` run. Nothing was fixed; this is a
read-only reconciliation.

**Provenance note (important):** `HANDOVER.md` **did not exist in the repo** when
this task began — not in the working tree and not anywhere in git history. It was
retrieved from the Claude desktop-app session outputs at
`…/AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/local-agent-mode-sessions/c2e2dc16-…/…/outputs/HANDOVER.md`
and copied to the repo root. It is therefore currently an **untracked** file
(`?? HANDOVER.md` in `git status`). HANDOVER's own opening warning — "the source
code repository was NOT accessible when this document was written … reconcile §5
and §7 against reality" — is exactly what this document does.

---

## 1. Every path in §5 and §7 — exists / missing / renamed

### §5.1 Data acquisition & preparation

| HANDOVER path | Status | Note |
|---|---|---|
| `parsers/parse_bsp.py` | **EXISTS** | |
| `vendor/rpscrape/` | **EXISTS** | |
| `parsers/join_form_bsp.py` | **EXISTS** | see Q2 |
| `offline_join.py` (path not given in doc) | **EXISTS** — at `vendor/rpscrape/scripts/offline_join.py` | doc said "entry point not recorded — verify"; located. See Q2 |
| `features/build_rolling.py` | **EXISTS** | |
| `features/history_join.py` | **EXISTS** | |
| `data/reference/course_geometry.csv` | **EXISTS** | |
| geometry **builder** ("name not recorded") | **FOUND** | `data/reference/build_course_geometry.py` (builds the CSV); also `features/build_geometry_join.py` (joins it in) and `features/course_geometry.py` |
| `output/bsp_table.csv` | **EXISTS** | |

### §5.2 Model — all present

`models/stage1_logit.py`, `models/stage1_scored.csv`, `models/calibrate.py`,
`models/score_stage1_clv.py`, `models/stage2_blend.py`, `models/stage2_scored.csv`,
`models/score_blend_clv.py` — **all EXIST.**

### §5.3 Backtest & verdict — all present

`backtest/clv.py`, `backtest/test_clv.py`, `backtest/test_verdict.py`,
`backtest/test_scan_today.py` — **all EXIST.** (Suite is much larger than the four
named — see Q5.)

### §5.4 Front end — all present except the dead Desktop copy

| HANDOVER path | Status |
|---|---|
| `racing_rulebuilder/index.html` | **EXISTS** |
| `racing_rulebuilder/index_editorial.html` | **EXISTS** |
| `racing_rulebuilder/run_strategy.py` | **EXISTS** |
| `racing_rulebuilder/scan_today.py` | **EXISTS** |
| `racing_rulebuilder/edge_tracker.html` | **EXISTS** |
| `racing_rulebuilder/field_manifest.json` | **EXISTS** |
| `C:\Users\gabriel\Desktop\index_editorial.html` (dead file, "delete") | **MISSING** — not on the Desktop. HANDOVER P0 step #5 ("delete it") is already satisfied (or it never existed on this machine). |

### §7 Data assets

| HANDOVER path | Status | Note |
|---|---|---|
| `data/joined/joined_gb_2018_2026.csv` | **EXISTS** | 726,044 rows — confirmed (Q9) |
| `data/joined/joined_gb_2025_09.csv` | **EXISTS** | the superseded small join |
| `output/bsp_table.csv` | **EXISTS** | |
| `data/historical/*.tar(.bz2)` | **EXISTS** (dir present) | |
| `data/form/` | **EXISTS** | |
| `data/reference/course_geometry.csv` | **EXISTS** | |
| `data/samples/real_format_fixtures/` | **EXISTS** | |
| `models/stage1_scored.csv`, `models/stage2_scored.csv` | **EXIST** | |

**Assets present but NOT listed in §7** (additive, not conflicting): per-year joins
`data/joined/joined_gb_2018.csv … joined_gb_2026.csv`; feature-variant joins
`…_feat.csv`, `…_hcap.csv`, `…_hist.csv`, `…_sf.csv`, `…_wx.csv`;
`data/joined/unmatched_bsp.csv`, `unmatched_form.csv`; and a `data/weather/`
directory. No §5/§7 path was found **renamed** — every listed path resolved.

---

## 2. §12.2 Q7 — is `join_form_bsp.py` or `offline_join.py` canonical? Is the other dead?

**Canonical for THE 726k dataset = `vendor/rpscrape/scripts/offline_join.py`.**
Its own docstring: it replicates rpscrape's inline `Race.join_betfair_data`
exactly, carries `BF_COLS = [bsp, pre_min, pre_max, ip_min, ip_max, pre_vol,
ip_vol, wap, morning_wap, morning_vol]` plus derived `wap_valid`, and emits the
cross-era **52-col** schema combinable by `vendor/rpscrape/scripts/combine_years.py`
(confirmed present). Usage `python offline_join.py <form_csv> <betfair_cache_csv>
<out_csv>` — this is what produced `joined_gb_2024.csv` etc. → combined into
`joined_gb_2018_2026.csv`. This matches HANDOVER's own §3 (21 Jun) note that `wap`
was carried "into the join via `offline_join.py` `BF_COLS`."

**`parsers/join_form_bsp.py` is the original Sept-2025-only joiner**, not the
current entry point. Its docstring: joins Block-3 RP form to Block-2 BSP for
`data/form/rp_form_gb_2025_09.csv` → outputs `joined_gb_2025_09.csv` /
`unmatched_form.csv` / `unmatched_bsp.csv`. It predates the full pipeline and does
**not** carry the `wap`/BF_COLS 52-col schema.

**Is the other dead?** Not exactly:
- For the **join itself**, `join_form_bsp.py` is **superseded/legacy** (it only
  builds the obsolete Sept-2025 file), but it is **not orphaned code** — it is still
  imported live: `backtest/pro_form_join.py:19` does
  `from parsers.join_form_bsp import norm_course, norm_name` (reuses its
  name/course normalisers). So the module is live; its role as the *dataset* joiner
  is dead.
- `offline_join.py` is the live canonical joiner for everything downstream.

So: **two joiners for two different builds** — `offline_join.py` canonical (full
2018–2026 dataset), `join_form_bsp.py` legacy (Sept-2025 only) but its helper
functions remain in use.

---

## 3. §12.3 — CLI signatures + requirements + venvs

### 3a. argparse / CLI signatures

**`models/` — NO script uses argparse.** All are run bare
(`python models/<script>.py`) with hardcoded input/output paths inside `def main()`
(no `sys.argv` handling anywhere in the directory). Applies to: `stage1_logit.py`,
`stage2_blend.py`, `calibrate.py`, `score_stage1_clv.py`, `score_blend_clv.py`,
`score_slices.py`, `score_target_c.py`, `score_target_c_conditions.py`,
`score_price_drift.py`, `score_lay_selection.py`, `score_speedfig_lay.py`,
`score_handicap_lay.py`, `score_weather_lay.py`, `inrunning_liquidity_screen.py`,
and the `test_*_verdict.py` files. **This resolves HANDOVER §12.3's "the models/
scripts' CLI signatures … no argparse spec is recorded" — because there is none;
they take no flags.**

**`backtest/` — only two scripts use argparse:**

`backtest/clv.py`:
```
ArgumentParser(description="CLV scoring harness (struck vs BSP).")
  --joined       (default=DEFAULT_JOINED)
  --struck-col   (default="struck")
  --strategy     (default="all", choices=["all","favourites"])
  --commission   (type=float, default=DEFAULT_COMMISSION=0.05)
```

`backtest/lay_clv.py`:
```
ArgumentParser(description="Lay-CLV scoring harness (bsp vs struck).")
  --joined       (default=DEFAULT_JOINED)
  --struck-col   (default="struck")
  --strategy     (default="all", choices=["all","favourites"])
  --commission   (type=float, default=DEFAULT_COMMISSION=0.05)
```

All other `backtest/` scripts (`gate1_liquidity.py`, `gate_preoff.py`,
`gate_preoff_analysis.py`, `gate_q7_nonrunner.py`, `gate_q7_gate2.py`,
`clv_readiness.py`, `pro_stream.py`, `pro_form_join.py`, and the `test_*.py`) have
`if __name__=="__main__"` blocks but **no argparse** — run bare.

**`racing_rulebuilder/` — two scripts use argparse:**

`racing_rulebuilder/run_strategy.py`:
```
ArgumentParser(description="Rule-builder <-> CLV pipeline bridge.")
  strategy       (positional, nargs="?"  — path to strategy.json)
  --out          (results JSON path; default results.json beside input)
  --count-only   (store_true — qualifier count only)
  --serve        (store_true — run local HTTP endpoint)
  --port         (type=int, default=8765)
```

`racing_rulebuilder/scan_today.py`:
```
ArgumentParser(description="Stage 3 scanner -- rule -> today's qualifying races.")
  --strategy     (required — strategy.json with selection_rules)
  --date         (YYYY-MM-DD; default today)
  --cards        (explicit path to a racecards JSON file)
  --out          (write scan results JSON here)
```

### 3b. `requirements.txt` (verbatim)

```
# Core Betfair tooling
betfairlightweight>=2.23
betfair_data>=0.3.4
betfairdatabase>=1.3
flumine>=2.13
# Data / modelling
pandas
numpy
# rpscrape has its own requirements in vendor/rpscrape/requirements.txt
```

(No pins on pandas/numpy — confirms HANDOVER §12.3 "dependency pinning … only
rpscrape's deps are listed.")

### 3c. `.venv` vs `.venv313` — what each contains

| | `.venv` | `.venv313` |
|---|---|---|
| Python | **3.10** | **3.13** |
| pandas | **YES (2.3.3)** | **NO** |
| numpy | YES | NO |
| Role | full analysis/modelling + Betfair stack | rpscrape scraper only |

- **`.venv` (3.10)** installed dists include: `pandas 2.3.3`, `numpy`, `betfairlightweight`,
  `betfair_data`, `betfairdatabase`, `flumine`, `betconnect`, `betdaq_retail`,
  `curl_cffi`, `jarowinkler`, `lxml`, `orjson`, `pydantic`, `rapidfuzz`, `requests`,
  `rich`, `tqdm`, `zeep`, `smart_open`, `tenacity`, `uv`, etc. — i.e. the project
  requirements.txt stack **plus** rpscrape's.
- **`.venv313` (3.13)** installed dists: `curl_cffi`, `jarowinkler`, `lxml`,
  `orjson`, `python_dotenv`, `rapidfuzz`, `rich`, `tomli`, `tqdm`, `markdown_it_py`,
  `mdurl`, `pygments`, `certifi`, `cffi`, `pycparser` — exactly rpscrape's deps,
  **no pandas/numpy.**

> ⚠️ **HANDOVER is backwards on this.** The start-of-session note and §5.4 say
> "`source .venv/bin/activate` **or `.venv313` if pandas is missing**." In reality
> **pandas is in `.venv`, and `.venv313` is the one *without* pandas.** For any
> pandas/modelling/backtest work use **`.venv`**; `.venv313` (Py3.13) is for running
> `rpscrape` only. The unittest run below used `.venv`.

---

## 4. `DEFAULT_COMMISSION` and every hardcoded 0.05 / 0.02 commission site

### `DEFAULT_COMMISSION` — defined in 2 places, both **0.05**
- `backtest/clv.py:48` → `DEFAULT_COMMISSION = 0.05`
- `backtest/lay_clv.py:55` → `DEFAULT_COMMISSION = 0.05`

**Consumers of `DEFAULT_COMMISSION` (all inherit 0.05):**
- `backtest/clv.py:229` (`--commission` default), `:230` (help "default 0.05")
- `backtest/lay_clv.py:261`/`:262`
- `models/score_slices.py:66` → `clv.DEFAULT_COMMISSION`
- `models/score_price_drift.py:64` → `clv.DEFAULT_COMMISSION` (back side)
- `models/score_target_c.py:71` → `clv.DEFAULT_COMMISSION  # 0.05`
- `models/score_lay_selection.py:59` → `lay_clv.DEFAULT_COMMISSION  # 0.05, net (not 2%)`
- `racing_rulebuilder/run_strategy.py:64` → `clv.DEFAULT_COMMISSION  # 0.05` (and `:269`, `:1140`, `:1170` propagate it; UI caption prints `{…:.0%}` = 5%)

### Hardcoded `COMMISSION = 0.05` (commission constants)
- `backtest/clv_readiness.py:22`
- `models/score_blend_clv.py:29`
- `models/score_stage1_clv.py:41`
- `models/score_speedfig_lay.py:45`
- `models/score_handicap_lay.py:40`
- `models/score_weather_lay.py:33`

### Hardcoded `= 0.02` (commission constants)
- `backtest/gate_preoff_analysis.py:31` → `COMMISSION = 0.02`
- `backtest/gate_q7_gate2.py:44` → `COMMISSION = 0.02`
- `models/score_price_drift.py:75` → `LAY_COMMISSION = 0.02` (lay side only; back side is 0.05 above)
- `paper_trades/_lay_rank.py:14`, `paper_trades/_select_btl.py:12`,
  `paper_trades/score_btl.py:30` → `STAKE, COMM = 20.0, 0.02`
- `reports/_btl_scan.py:15` → `COMM = 0.02`; `reports/_btl_observed.py:17` → `... 0.02`

### Which reported numbers were computed at 5%?
**Every pre-race edge-hunt number in HANDOVER §8** — i.e. the whole pre-race CLV/P&L
body of work — was computed at **5%**, because it flows through `clv.py`/`lay_clv.py`
`DEFAULT_COMMISSION = 0.05` and the `COMMISSION = 0.05` scorers:
Stage-1/Blend CLV, back-all/lay-all CLV & @BSP, `score_stage1_clv`, `score_blend_clv`,
`score_slices`, `score_target_c`(+conditions), `score_speedfig_lay`,
`score_handicap_lay`, `score_weather_lay`, `score_lay_selection`, the back side of
`score_price_drift`, and all `run_strategy.py`/UI backtests (default 0.05).

**Computed at 2%:** the newer **pre-off gate program** (`gate_preoff_analysis`,
`gate_q7_gate2`), the **lay side** of `score_price_drift` (`LAY_COMMISSION=0.02`),
and the **paper-trade / BTL scan** logs (`paper_trades/*`, `reports/_btl_*`).

This **confirms** HANDOVER §8.2 / §12.2-Q1 / P0-#3: the 5%↔2% split is real and
unresolved. The 2% correction announced in the in-running pre-registration was
applied to the pre-off/Q7 gate work and paper trades, but the historical pre-race
numbers still stand at 5%.

*(Non-commission `0.05`/`0.02` occurrences exist and were excluded from the list
above: Betfair tick sizes in `pro_stream.py`, calibration bands in `calibrate.py`,
`alpha=0.05` significance thresholds in the gate analysis, lay-strikeability
haircuts in `score_price_drift.py`, unit-test fixtures, and vendored
`autoHubTutorials` staking demos.)*

---

## 5. Test count + `python -m unittest discover backtest`

**RESULT: PASSES.** Ran via the `.venv` (Py3.10, has pandas):

```
Ran 130 tests in 0.389s

OK
```

**Test count = 130, all green** — **not** the 51 HANDOVER cites (§5.3, §10.1, §14
all say "51 tests, all green [as of 1 Jul]"). The suite has grown by 79 tests since
the handover snapshot — consistent with the pre-off / Q7 gate machinery added in the
git log after 1 Jul (`test_gate_preoff*`, `test_gate_q7*`, `test_gate1_liquidity`,
`test_pro_stream`, `test_lay_clv`, etc.).

---

## 6. git — log / status / email / uphill_finish commit

**`git config user.email` = `gabrieljorgeclemente@live.com`** — the personal
default. Matches HANDOVER P0-#2 ("still a personal email; set a repo-local identity
before any push"). **Still open.**

**`git status`** (short):
```
 M .claude/settings.local.json
?? HANDOVER.md        <- untracked; created by this task (copied in, see provenance)
```
(Otherwise clean. Branch `ui-editorial`.)

**Did the uphill_finish verification commit land? — YES.**
`git log` shows: `9e12899 Verify uphill_finish per-course (11 courses) + per-field
Tier-2 gating`. This closes HANDOVER §12.2-Q9 and P0-#6 ("was the uphill_finish
verification commit made? staged at wrap on 30 Jun").

**`git log --oneline -30`** (top → bottom):
```
25bcfd3 Q7 (non-runner repricing latency): Gate 1 PASS (marginal) -> Gate 2 PRICED
6759710 Pre-reg Amendment 2: Q7 (non-runner repricing latency) defined + gated
dc5c39f chore: live-card scan reports + paper-trade logs + .claude permission sync
0a00043 Mirror Gate 2: lay predicted drifters -> ARTIFACT (unquotable-WAP kill)
17095e2 Test 4 (lay-side selection): V1 ARTIFACT-NAMED, V2 PRICED
69220df Pre-off Gate 2 results: Q2/Q3/Q6 all FAIL — PRO trading direction closed
315ba07 Pre-off Gate 2 machinery: extractor + verdict analysis (Q2/Q3/Q6)
e54c2f4 Pre-off Gate 1 (Q2/Q3/Q6): all PASS — advance to Gate 2
7aa0f28 Pre-reg Amendment 1: Q1 closed (FAIL); in-running retired; pre-off Q2/Q3/Q6 defined
82b9786 Gate 1 (liquidity) result: DOES NOT PASS — in-running direction not advanced
1242434 Gate 1 (liquidity): PRO stream reconstruction + fill model + form join
522f5e2 Pre-register in-running/trading gate program (Q1–Q4) before PRO-data contact
9f37a11 chore: sync .claude local permission allowlist (session grants)
fec4d3d Horse-name normalization fix + in-running Stage 0/1 + parallel probes
9e12899 Verify uphill_finish per-course (11 courses) + per-field Tier-2 gating
33a48c2 Course-geometry reference table + manifest/UI wiring
f6287a1 PROJECT_NOTES: log the verdict-baseline hardening (eec32a1)
eec32a1 Harden verdict baseline against the favourite-longshot hole
482565a Weather/visibility probe: modules + notes (FOURTH free family, ruled out)
f10f73c Layer-2 Phase 2/3: full feature set + wired into 3 surfaces
b9859b4 Layer-2 Phase 1: shared strictly-prior history-join engine + leakage proof
3b509f6 Add saved-strategy flag system + UI_NOTES
c36093f Add runner view (Task 3): per-runner detail, Layer 1 complete
b469281 Add race view (Task 2): per-course race list browse surface
2938e6d Add staking/bankroll layer + systematic field-control audit
c1776fb WIP: rule-builder tool + editorial restyle (four modes)
2255b81 Add speed-figure feature family … first positive blend-weight movement (+2.98%) but priced
892a502 Add handicap feature set + lay kill-test rig; …
d183edb Add leakage-safe rolling-feature machinery; first batch tested and reverted
bbd1dac Log morning_wap analysis — timing offset confirmed …
```
Note: the log shows the project advanced **past** the HANDOVER's "stalled on buying
PRO data" framing — the in-running direction was retired (Amendment 1) and a
pre-off Q2/Q3/Q6 + Q7 gate program was run to completion (all FAIL/PRICED).

---

## 7. In-running pre-registration docs — located + quoted

| Doc (per §12.1 / Q7) | Status |
|---|---|
| `Deep_Research_Brief_InRunning_Trading.md` | **NOT FOUND** — absent from the repo (matches HANDOVER §12.1). |
| `Strategy_Direction_InRunning.md` | **PRESENT** (repo root). |
| `prompts/InRunning_Stage0_PreRegistration.md` | **PRESENT.** |

> **Reconciliation:** HANDOVER §12.1 lists `Strategy_Direction_InRunning.md` and
> `prompts/InRunning_Stage0_PreRegistration.md` as "**both absent from the doc
> snapshot**." They are **present in the repository** (the snapshot lacked them; the
> repo has them). A third copy also exists: `analysis/preregistration_inrunning.md`.
> Only `Deep_Research_Brief_InRunning_Trading.md` is genuinely absent.

### 7a. `Strategy_Direction_InRunning.md` — the committed pre-registration (verbatim)

The falsifiable claim (§1):
> "At a realistic, latency- and liquidity-constrained fill model, a pre-registered
> in-running entry signal can get **≥ £X matched in > Y% of ≥ N qualifying
> opportunities**, AND the net-commission ROI on the **matched subset** beats the
> price-band-stratified structural in-running null by **≥ +1.0%** and is **> 0**,
> out of sample."

The confirmed parameters (footer, verbatim):
> **CONFIRMED 2026-07-01:** N = 2,000, X = £100, Y = 50%; edge bar ≥ +1.0% over the
> stratified null AND > 0 net commission; fill model L = 1.0 s, S = 1 tick, **2%
> commission** (corrected from 5%); liquidity-gate signal = front-runner
> (`run_style_proxy = led`) entered when the in-running price first trades ≤ 2.0.
> Stage 1 is authorized for the **LIQUIDITY GATE ONLY** — report the liquidity
> result and wait for confirmation before any further spend or the edge backtest.
>
> (The suggested X in the canonical brief was £10; the confirmed £100 is a
> deliberately harder bar — more likely to fail, which is the point of a cheap kill.)

Fill model (§3, verbatim key lines):
> - **Latency** `L = 1.0 s` between signal and matchable moment. You act on the
>   ladder at `t + L`, never at the instant of the signal `t` …
> - **Crossing the spread:** … Matched £ = `min(£X, £ available at or through your
>   price within slippage S = 1 tick)` at `t + L`.
> - **Commission** = **2%** on net winnings. (CORRECTED 2026-07-01: an earlier draft
>   carried 5% over from `clv.py`'s `DEFAULT_COMMISSION` …)
> - **Explicitly rejected fantasy:** matched at the displayed price for unlimited size.

### 7b. `prompts/InRunning_Stage0_PreRegistration.md` — the canonical brief (verbatim)

The candidate falsifiable claim (Stage 0):
> "Reacting to an in-running price move of ≥N ticks within the 1-second bet
> delay window yields positive expectancy, net of 2% commission and a
> conservative fill model, at a stake of at least £X per race, across a sample
> of at least Y races."

> Fill in N, X, Y now. Suggested starting point: N = a move of 20%+ in-running
> price within a short window (e.g. 2-5 seconds), X = £10 (a stake that would
> actually matter, not a token £1), Y = at least 200-300 races …

> **Also pre-register:** what counts as PASS (proceed to Stage 2) vs FAIL (stop,
> adopt the research brief's option-c read). Suggested: FAIL if net expectancy is
> ≤0 OR if the achievable matched size at the modelled fill rate is trivially
> small (e.g. can't get £10 matched in >50% of qualifying opportunities).

*(Note: the brief's suggested X=£10 / Y=200-300 races were superseded by the
`Strategy_Direction` "CONFIRMED" values X=£100 / Y=50% / N=2,000. HANDOVER §3's
N/X/Y figures track the confirmed values, which is correct.)*

---

## 8. `field_manifest.json` — does it list 52 + 13 + 6?

**Partly.** The manifest's own `counts` block reads:
```json
{ "pre_race_selectable": 33, "post_race_disabled": 19,
  "derived_features": 20, "derived_materialised": 14 }
```

| HANDOVER §7.1 claim | Manifest reality |
|---|---|
| 52 columns (`fields`) | **52 ✓** (33 pre-race selectable + 19 post-race blocked) |
| **13** derived prior-run features | **20 derived** classified (**14** materialised). ✗ — the "13" is outdated. |
| 6 pending-acquisition | **6 ✓** |

So **52 ✓ and 6 ✓, but 13 → 20 (14 materialised).** The 20 derived (all
`selectable:true`): `career_wins, career_runs, career_win_pct, career_place_pct,
won_course_flag, won_dist_flag, won_cd_flag, class_change, or_trajectory, dslr,
run_style_proxy, trainer_course_sr, trainer_class_sr, trainer_going_sr,
jockey_trainer_combo_sr, hcap_transition, going_suit, sire_going_profile,
sire_dist_profile, first_time_hg`. (HANDOVER's 13 are a subset; the manifest adds
the `career_*_pct`, `dslr`, and four `trainer_*/jockey_*_sr` features — note
`trainer_course_sr`, the killed test-5 feature, is here and selectable.)

### The 6 pending-acquisition entries (verbatim)
```json
[
  { "name": "weather", "available": false, "selectable": false,
    "blocker": "Open-Meteo join not built — needs a ~60-course lat/long table.",
    "cost": "easy / free" },
  { "name": "going_vs_forecast", "available": false, "selectable": false,
    "blocker": "Derived once weather is joined.", "depends_on": ["weather"] },
  { "name": "sectional_pace", "available": false, "selectable": false,
    "blocker": "TPD paid licence required — the genuine edge layer.",
    "cost": "paid licence" },
  { "name": "forecast_tissue_price", "available": false, "selectable": false,
    "blocker": "No feed yet — blocks forecast-vs-market rules." },
  { "name": "book_impact", "available": false, "selectable": false,
    "blocker": "Only crudely proxyable — no clean pre-race source." },
  { "name": "distance_travelled", "available": false, "selectable": false,
    "blocker": "Needs trainer-yard locations — no such field exists." }
]
```
(Names match HANDOVER §7.1's "weather, going_vs_forecast, TPD sectionals, forecast
tissue price, book impact, distance travelled" — `sectional_pace` = the TPD item.)

---

## 9. `joined_gb_2018_2026.csv` — head + row count

**Row count confirmed = 726,044 data rows.** `wc -l` = **726,045** lines including
the header, i.e. exactly **726,044** data rows. ✓

`head -3` (header + first two rows):
```
date,region,course,course_detail,off,race_name,type,class,pattern,rating_band,age_band,sex_rest,dist,dist_f,dist_m,going,surface,ran,num,pos,draw,ovr_btn,btn,horse,age,sex,lbs,hg,time,secs,dec,jockey,trainer,prize,or,rpr,sire,dam,damsire,owner,comment,bsp,pre_min,pre_max,ip_min,ip_max,pre_vol,ip_vol,wap,morning_wap,morning_vol,wap_valid
2018-02-11,GB,Ayr,,14:55,totequadpot Novices Hurdle,Hurdle,Class 4,,,4yo+,,2m,16f,3219,Heavy,Turf,6,2,1,,0,0,Grand Morning (GB),6,G,162,t1,4:39.80,279.80,1.80,Derek Fox,Lucinda Russell,4483.62,122,117,Midnight Legend (GB),Valentines Lady (IRE),Zaffaran,John P Mcmanus,Chased leaders - smooth headway to lead 2 out - soon hard pressed - kept on gamely to assert close home,,1001,1,1001,1,0,0,1.00,1.00,0,0
2018-02-11,GB,Ayr,,14:55,totequadpot Novices Hurdle,Hurdle,Class 4,,,4yo+,,2m,16f,3219,Heavy,Turf,6,1,2,,0.3,0.3,Cubomania (IRE),5,G,159,t,4:39.88,279.88,3.50,Andrew Ring,Gordon Elliott,1316.52,114,117,Halling (USA),Surrealism I (GB),Pivotal,Cubomania Syndicate,Held up in touch - smooth headway to challenge 2 out - not fluent last - kept on run-in - held near finish,,1001,1,1001,1,0,0,1.00,1.00,0,0
```
The header is the 52-column schema (33 pre-race + 19 post-race), exactly as §7.1
describes. Note both sample rows have `bsp` **empty** and `wap`/`morning_wap` = 1.00
with `wap_valid=0` — consistent with §7.2's "2018 = 88% valid (untraded tail)."

---

## Summary of divergences found (HANDOVER vs. reality)

1. **`HANDOVER.md` was not in the repo** — retrieved from the desktop-app session
   outputs and copied in; now untracked.
2. **`.venv` / `.venv313` are described backwards** — pandas is in `.venv` (3.10),
   not `.venv313` (3.13, rpscrape only). Use `.venv` for modelling/backtests.
3. **Test count is 130, not 51** — suite grew with the post-1-Jul gate machinery;
   still all green.
4. **Derived features = 20 (14 materialised), not 13** — 52 cols and 6 pending are
   correct.
5. **`Strategy_Direction_InRunning.md` and `prompts/InRunning_Stage0_PreRegistration.md`
   are present**, though §12.1 called them absent (they were missing only from the
   *snapshot*). `Deep_Research_Brief_InRunning_Trading.md` is genuinely absent.
6. **The project moved past the "stalled on buying PRO data" state** — in-running
   was retired (Amendment 1) and a pre-off Q2/Q3/Q6 + Q7 gate program ran to a
   PRICED/FAIL conclusion (git log).
7. **Confirmed as HANDOVER states:** uphill_finish commit landed (`9e12899`);
   git email still personal; 5%↔2% commission split real and unresolved; 726,044
   rows; the Desktop dead file is already gone; every §5/§7 path resolved (none
   renamed/missing except the already-deleted Desktop copy).

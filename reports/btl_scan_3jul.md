# Back-to-lay scan — 6 Sandown races — Fri 3 Jul 2026 (REPORT ONLY, no bets)

Generated **~06:30 BST** (card pulled 06:27). Trade studied: **BACK £20 at the 06:14 morning price → LAY off pre-off, modelled exit = BSP, greened across the book. Commission 2%.** Candidate pool = **top four by the betting, per race**. **No bet was placed. No bet should be placed off this sheet.**

---

## ⚠️ CAVEAT BLOCK — read before the numbers (they are illustrative, not tradeable)

1. **There is no real price anywhere in this scan.** The rpscrape racecard carries **no odds field at all** (`ofr`=official rating, `rpr`/`ts`=ratings; no forecast, no SP, no exchange quote), and this project has **no live Betfair feed**. So the "06:14 morning price" and "top four in the betting" **cannot be observed**. Both are stood in for by the **Stage-1 model fair price** (conditional logit on `or, draw, lbs, age`, softmax within race). Everything below is *model price → historical drift → projected BSP*, not market data.
2. **The model favourite ≠ the market favourite.** Stage-1 is under-confident / low-resolution (documented): it spreads probability across the field, so its "favourites" price out at **3.8–11.0** here — far longer than the ~1.5–3.5 a real market top-4 would show. The whole top-4 lands in price bands that historically **drift OUT**, which mechanically produces a loss. With *real* short prices the picture would be less bad but still ~breakeven-negative (see the reference table).
3. **The drift applied is a population statistic, not a per-horse forecast.** "Band baseline drift" = the historical distribution of `BSP / morning_wap − 1` for **all runners whose morning price fell in that band** (discovery split ≤2023-12-31, the same bands/data as the *priced* CLV probe). It is a **band median with an enormous right tail** — the per-horse outcome is essentially unknowable; p25→p75 spans e.g. −12% to +23% in the 3.0–4.0 band.
4. **Category substitution.** The drift model was built on real morning_wap→BSP moves; applying it to *model* prices assumes the model price behaves like a morning exchange price. It does not.
5. **This trade is already known to be un-harvestable.** The project's CLV/price-movement probe (holdout-tested) is **PRICED**: prices structurally drift OUT morning→close, so *the close is the better back price* and backing-at-morning/laying-at-BSP loses after commission. This scan is a concrete instance of that verdict, not a new signal.
6. **Execution ignored.** Greening "across the book" assumes you can lay the modelled BSP in size at the off; no liquidity, no slippage, no queue risk, no partial-fill is modelled. 2% commission is applied only to a *winning* greened book (none here win at the median).

**Bottom line up front:** across 24 candidate bets the modelled book is **−£26.43 at the band median** (−£1.10/bet, −5.5% of stake) and **−£121.32 at the 75th-pct drift** (−£5.06/bet, −25%). Every single candidate loses at the median. Do not trade this.

---

## Method / provenance

- **Card:** pulled live 06:27 BST via rpscrape (`racecards.py --day 1 --region gb`) → `vendor/rpscrape/racecards/2026-07-03.json`.
- **Races (6):** Sandown, the day's feature Flat meeting. All 7 Sandown races **except the 5-runner 16:10 Coral Marathon** (in a 5-runner race "top 4" is the whole field bar one). Declared rule, since the brief said "6 of today's races" without naming them.
- **Back price:** Stage-1 model fair price `= 1 / model_prob`, fit fresh on `joined_gb_2018_2026.csv` (726,044 runners); β(or,draw,lbs,age)=[+0.676, −0.029, +0.226, −0.238]. **Proxy for the unobservable 06:14 price.**
- **Top four:** the four shortest model fair prices per race (proxy for "top four in the betting").
- **Band drift:** `reports/band_drift.json`, computed from `joined_gb_2018_2026_feat.csv` morning_wap→BSP, discovery split, same bands as `models/score_price_drift.py`.
- **P&L (stake £20, comm 2%):** greened back-to-lay profit `= 20·(B/L − 1)`, ×0.98 when positive (commission bites only on a winning book). `L_median = B·(1+d_median)`, `L_p75 = B·(1+d_p75)`. **Breakeven lay = the back price B** (you profit only if BSP comes in *below* where you backed).

### Band baseline drift engine (discovery, `BSP/morning_wap − 1`)

| morning band | n | median | p75 | mean | % that steam (drift<0) |
|---|--:|--:|--:|--:|--:|
| 1.0–1.5 | 1,372 | −2.0% | +4.3% | +36.0%\* | 57% |
| 1.5–2.0 | 4,916 | −1.0% | +10.2% | +3.9% | 52% |
| 2.0–2.5 | 7,643 | 0.0% | +14.2% | +5.3% | 50% |
| 2.5–3.0 | 10,700 | 0.0% | +17.2% | +7.3% | 50% |
| 3.0–4.0 | 27,648 | +2.6% | +22.5% | +9.3% | 46% |
| 4.0–5.0 | 30,706 | +3.5% | +26.7% | +11.8% | 45% |
| 5.0–6.0 | 31,077 | +4.2% | +30.0% | +13.0% | 45% |
| 6.0–8.0 | 55,961 | +5.6% | +33.7% | +15.1% | 44% |
| 8–10 | 48,051 | +7.3% | +38.3% | +19.0% | 42% |
| 10–15 | 81,795 | +10.4% | +46.3% | +24.6% | 40% |

\*The 1.0–1.5 mean is dragged by odds-on shots that occasionally collapse to a big number; the **median** (−2.0%) is the honest central move. **Note the key fact: the median drift is only negative in the two shortest bands and is ≥0 from 2.0 up — prices drift OUT, so back-to-lay has no median edge above ~2.5, and the shortest bands' tiny negative median is erased by 2% commission.**

---

## The scan — 6 races × top-4 (all prices are MODEL prices, not market)

Columns: back price (model) · band · band median drift · median BSP · 75th-pct BSP · breakeven lay · net £ @median · net £ @p75.

### 13:50 Sandown — HKJC World Pool Battaash Handicap [5f, Good, 5 ran]
| horse | back(mdl) | band | med drift | BSP med | BSP p75 | b/e lay | net@med | net@p75 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Havana Hurricane | 3.82 | 3.0–4.0 | +2.6% | 3.93 | 4.69 | 3.82 | −£0.52 | −£3.68 |
| Comical Point | 4.49 | 4.0–5.0 | +3.5% | 4.65 | 5.69 | 4.49 | −£0.68 | −£4.21 |
| Westport | 4.96 | 4.0–5.0 | +3.5% | 5.14 | 6.29 | 4.96 | −£0.68 | −£4.21 |
| Exclamation | 5.28 | 5.0–6.0 | +4.2% | 5.50 | 6.86 | 5.28 | −£0.81 | −£4.61 |

### 14:25 Sandown — Coral Dragon Stakes (Listed) [5f, Good, 8 ran]
| horse | back(mdl) | band | med drift | BSP med | BSP p75 | b/e lay | net@med | net@p75 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Ronson | 6.97 | 6.0–8.0 | +5.6% | 7.36 | 9.32 | 6.97 | −£1.05 | −£5.04 |
| Bill The Bull | 7.24 | 6.0–8.0 | +5.6% | 7.65 | 9.68 | 7.24 | −£1.05 | −£5.04 |
| Miss Lizzy | 7.70 | 6.0–8.0 | +5.6% | 8.13 | 10.29 | 7.70 | −£1.05 | −£5.04 |
| It Dunt Marra | 7.94 | 6.0–8.0 | +5.6% | 8.38 | 10.61 | 7.94 | −£1.05 | −£5.04 |

### 15:00 Sandown — Tattersalls £40,000 EBF Novice Stakes [7f, Good, 11 ran]
| horse | back(mdl) | band | med drift | BSP med | BSP p75 | b/e lay | net@med | net@p75 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Encounter | 9.74 | 8–10 | +7.3% | 10.45 | 13.46 | 9.74 | −£1.36 | −£5.54 |
| Gymbaazy | 10.24 | 10–15 | +10.4% | 11.30 | 14.98 | 10.24 | −£1.88 | −£6.33 |
| Cilician | 10.68 | 10–15 | +10.4% | 11.78 | 15.61 | 10.68 | −£1.88 | −£6.33 |
| Collateral Damage | 10.85 | 10–15 | +10.4% | 11.98 | 15.87 | 10.85 | −£1.88 | −£6.33 |

### 15:35 Sandown — Davies Insurance Gala Stakes (Listed) [1m2f, Good, 6 ran]
| horse | back(mdl) | band | med drift | BSP med | BSP p75 | b/e lay | net@med | net@p75 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Sallaal | 4.72 | 4.0–5.0 | +3.5% | 4.88 | 5.98 | 4.72 | −£0.68 | −£4.21 |
| Dividend | 5.72 | 5.0–6.0 | +4.2% | 5.97 | 7.44 | 5.72 | −£0.81 | −£4.61 |
| Persica | 5.94 | 5.0–6.0 | +4.2% | 6.19 | 7.72 | 5.94 | −£0.81 | −£4.61 |
| Boiling Point | 6.18 | 6.0–8.0 | +5.6% | 6.52 | 8.26 | 6.18 | −£1.05 | −£5.04 |

### 16:42 Sandown — JRA Handicap (GBBPlus) [1m6f, Good, 8 ran]
| horse | back(mdl) | band | med drift | BSP med | BSP p75 | b/e lay | net@med | net@p75 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Marnier | 5.79 | 5.0–6.0 | +4.2% | 6.04 | 7.53 | 5.79 | −£0.81 | −£4.61 |
| Minhad | 5.90 | 5.0–6.0 | +4.2% | 6.16 | 7.68 | 5.90 | −£0.81 | −£4.61 |
| Arqoob | 7.63 | 6.0–8.0 | +5.6% | 8.06 | 10.20 | 7.63 | −£1.05 | −£5.04 |
| Galactic Jack | 7.90 | 6.0–8.0 | +5.6% | 8.34 | 10.56 | 7.90 | −£1.05 | −£5.04 |

### 17:15 Sandown — Debenhams Handicap [1m, Good, 10 ran]
| horse | back(mdl) | band | med drift | BSP med | BSP p75 | b/e lay | net@med | net@p75 |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| Ascending Star | 8.17 | 8–10 | +7.3% | 8.77 | 11.30 | 8.17 | −£1.36 | −£5.54 |
| Triple Double A | 8.43 | 8–10 | +7.3% | 9.05 | 11.66 | 8.43 | −£1.36 | −£5.54 |
| Silca Bay | 8.65 | 8–10 | +7.3% | 9.28 | 11.96 | 8.65 | −£1.36 | −£5.54 |
| Cristo | 8.97 | 8–10 | +7.3% | 9.62 | 12.40 | 8.97 | −£1.36 | −£5.54 |

---

## Totals

| | net @ band median | net @ 75th-pct drift |
|---|--:|--:|
| **24 candidate bets, £20 each (£480 turned over)** | **−£26.43** | **−£121.32** |
| per-bet mean | −£1.10 (−5.5%) | −£5.06 (−25.3%) |

Every candidate is a loss at the median because the model prices them long (3.8–11.0), landing in bands whose median drift is positive (prices drift out) — so the modelled BSP is always *above* the back price and the greened trade is a guaranteed small loss, worsening into the right tail (p75).

## Reference: what BTL would look like on *genuine* short favourites

If real market prices were available and the top-4 were true favourites (bands ≤3.0), the median BTL still barely clears zero and the tail still buries it — the trade isn't rescued by better prices, only made less bad:

| morning band | median drift | net@median (£20) | net@p75 (£20) |
|---|--:|--:|--:|
| 1.0–1.5 | −2.0% | **+£0.40** | −£0.82 |
| 1.5–2.0 | −1.0% | **+£0.20** | −£1.85 |
| 2.0–2.5 | 0.0% | £0.00 | −£2.49 |
| 2.5–3.0 | 0.0% | £0.00 | −£2.94 |

A genuine odds-on favourite nets ~ +£0.20–0.40 per £20 at the median — a tiny positive that 2% commission and the fat drift-out tail (a single p75 outcome wipes out 4–9 median wins) turn negative in expectation. This is the CLV probe's "priced" verdict in miniature.

---

## Verdict

**No tradeable edge; do not place these bets.** The scan reproduces the project's holdout-tested conclusion: morning→close drift is priced, prices drift OUT (the close is the better back price), and back-to-lay off the morning line loses after commission — decisively so here, amplified by using an under-confident model price in place of a real, shorter market price. The sheet is a structural illustration only.

*Artifacts: `reports/btl_scan_results.json`, `reports/band_drift.json`. No pipeline code touched; no order placed.*

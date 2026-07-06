# Back-to-lay scan on OBSERVED prices — 6 races — Fri 3 Jul 2026 (REPORT ONLY, no bets)

Generated **~06:40 BST**. Trade: **BACK £20 at the observed morning exchange price → LAY off pre-off, modelled exit = BSP (greened), commission 2%.** Strike prices are **the supplied observed prices only** — no model fair prices. Racecard used **only** to `canon_horse`-match names to declared runners and confirm NRs. **No bet placed; none should be off this sheet.**

Companion to `btl_scan_3jul.md` (which used model prices on a different, self-scoped Sandown set). This run uses the six races and real prices you supplied and does **not** re-scope.

---

## Method / mapping

- **Strike (back):** exchange price **EX1** (the primary observed exchange back price). Greened **lay exit = BSP**, projected from EX1 by the **same discovery band-drift model** as the prior report (`reports/band_drift.json`, `BSP/morning_wap−1` per morning-price band).
- **BST+1h:** your race times are the card off-time **minus 1h** (documented gotcha). Each race is paired to its card off-time below; the prices are genuine **~06:xx morning captures**, so the *morning→BSP* drift model fits cleanly here (unlike the prior model-price run).
- **P&L:** greened `= 20·(EX1/BSP − 1)`, ×0.98 when positive (2% commission bites only a winning book). **Breakeven lay = EX1.** `BSP_med = EX1·(1+d_med)`, `BSP_p75 = EX1·(1+d_p75)`.
- **EX1 vs EX2:** I used **EX1** as the back strike. Where EX2 is the better back (e.g. Comical Point EX2 2.86 > EX1 2.72) taking best-of-both moves the 24-bet total by **< £1** and changes no band — EX2 is reserved for the sportsbook cross-check per your item 3.
- **No guessing:** Jumeirah Storm SB was cut off → left **n/a**, excluded from the SB cross-check (kept in the BTL leg on its EX price).

### Name match & NR confirmation (`canon_horse`)
All 24 supplied runners matched a **declared active** runner in `2026-07-03.json`; all three NRs confirmed **non-runner** and excluded:

| race (card off) | field | supplied matched | NR confirmed |
|---|--:|--:|---|
| Sandown 13:50 | 5 | 4/4 | — |
| Sandown 14:25 | 8 | 4/4 | Divine Whisper ✓NR |
| Doncaster 14:00 | 11 | 4/4 | Give Hand ✓NR |
| Doncaster 14:35 | 9 | 4/4 | — |
| Newton Abbot 14:10 | 8 | 4/4 | — |
| Newton Abbot 14:45 | 6 | 4/4 | Katzoff ✓NR |

---

## The scan (per race)

Columns: EX1 (back strike) · EX2 · SB · band · median drift · BSP@median · BSP@p75 · **net £@median** · **net £@p75** · SB implied% · EX2 implied% · divergence(pp) · arb. Implied% are overround-normalised **over the top-4 shown** (partial book — see cross-check note).

### 1 · Sandown 12:50 (card 13:50) — 5f Handicap · mkt 1.259648496
| horse | EX1 | EX2 | SB | band | dMed | BSPmed | BSPp75 | net@med | net@p75 | SB% | EX2% | div | arb |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|
| Comical Point | 2.72 | 2.86 | 2.40 | 2.5–3.0 | +0.0% | 2.72 | 3.19 | **£0.00** | −£2.94 | 37.7% | 35.5% | +2.2 | · |
| Westport | 3.25 | 2.90 | 2.88 | 3.0–4.0 | +2.6% | 3.34 | 3.98 | −£0.52 | −£3.68 | 31.4% | 35.0% | −3.6 | · |
| Havana Hurricane | 4.70 | 4.70 | 4.00 | 4.0–5.0 | +3.5% | 4.87 | 5.95 | −£0.68 | −£4.21 | 22.6% | 21.6% | +1.0 | · |
| One And Gone | 13.00 | 13.00 | 11.00 | 10–15 | +10.4% | 14.35 | 19.02 | −£1.88 | −£6.33 | 8.2% | 7.8% | +0.4 | · |

### 2 · Sandown 13:25 (card 14:25) — 5f Listed (Divine Whisper NR) · mkt 1.259648502
| horse | EX1 | EX2 | SB | band | dMed | BSPmed | BSPp75 | net@med | net@p75 | SB% | EX2% | div | arb |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|
| Ronson | 4.60 | 4.70 | 3.20 | 4.0–5.0 | +3.5% | 4.76 | 5.83 | −£0.68 | −£4.21 | 34.9% | 28.9% | +6.1 | · |
| Miss Lizzy | 5.10 | 5.10 | 5.00 | 5.0–6.0 | +4.2% | 5.32 | 6.63 | −£0.81 | −£4.61 | 22.4% | 26.6% | −4.2 | · |
| Bill The Bull | 6.00 | 6.00 | 5.00 | 6.0–8.0 | +5.6% | 6.33 | 8.02 | −£1.05 | −£5.04 | 22.4% | 22.6% | −0.3 | · |
| A Bear Affair | 6.20 | 6.20 | 5.50 | 6.0–8.0 | +5.6% | 6.54 | 8.29 | −£1.05 | −£5.04 | 20.3% | 21.9% | −1.6 | · |

### 3 · Doncaster 13:00 (card 14:00) — 6f Novice Stakes (Give Hand NR) · mkt 1.259648089
| horse | EX1 | EX2 | SB | band | dMed | BSPmed | BSPp75 | net@med | net@p75 | SB% | EX2% | div | arb |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|
| Jumeirah Storm | 3.05 | 3.05 | n/a | 3.0–4.0 | +2.6% | 3.13 | 3.74 | −£0.52 | −£3.68 | — | — | — | · |
| Launch Sequence | 3.55 | 3.55 | 2.88 | 3.0–4.0 | +2.6% | 3.64 | 4.35 | −£0.52 | −£3.68 | 61.0% | 59.6% | +1.4 | · |
| Sultan Darius | 10.50 | 9.60 | 9.00 | 10–15 | +10.4% | 11.59 | 15.36 | −£1.88 | −£6.33 | 19.5% | 22.0% | −2.5 | · |
| No More Pino | 11.00 | 11.50 | 9.00 | 10–15 | +10.4% | 12.14 | 16.09 | −£1.88 | −£6.33 | 19.5% | 18.4% | +1.1 | · |

### 4 · Doncaster 13:35 (card 14:35) — 1m Handicap · mkt 1.259648109 · **⚠ THIN**
| horse | EX1 | EX2 | SB | band | dMed | BSPmed | BSPp75 | net@med | net@p75 | SB% | EX2% | div | arb |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|
| Al Muqdad | 5.60 | 5.60 | 4.50 | 5.0–6.0 | +4.2% | 5.84 | 7.28 | −£0.81 | −£4.61 | 27.9% | 28.1% | −0.2 | · |
| Amidst The Chaos | 5.90 | 6.60 | 5.00 | 5.0–6.0 | +4.2% | 6.15 | 7.67 | −£0.81 | −£4.61 | 25.1% | 23.9% | +1.3 | · |
| Tilani | 5.90 | 5.90 | 4.33 | 5.0–6.0 | +4.2% | 6.15 | 7.67 | −£0.81 | −£4.61 | 29.0% | 26.7% | +2.3 | · |
| Yafaarr | 7.20 | 7.40 | 7.00 | 6.0–8.0 | +5.6% | 7.60 | 9.63 | −£1.05 | −£5.04 | 17.9% | 21.3% | −3.3 | · |

### 5 · Newton Abbot 13:10 (card 14:10) — 2m1f Maiden Hurdle · mkt 1.259648047 · **⚠ THIN**
| horse | EX1 | EX2 | SB | band | dMed | BSPmed | BSPp75 | net@med | net@p75 | SB% | EX2% | div | arb |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|
| Likewhatyousee | 2.86 | 2.90 | 2.80 | 2.5–3.0 | +0.0% | 2.86 | 3.35 | **£0.00** | −£2.94 | 29.4% | 34.6% | −5.1 | · |
| Elated | 4.40 | 4.40 | 4.33 | 4.0–5.0 | +3.5% | 4.56 | 5.57 | −£0.68 | −£4.21 | 19.0% | 22.8% | −3.8 | · |
| For Her Glory | 4.70 | 4.30 | 3.20 | 4.0–5.0 | +3.5% | 4.87 | 5.95 | −£0.68 | −£4.21 | 25.8% | 23.3% | +2.4 | · |
| Getmyfriend | 4.90 | 5.20 | 3.20 | 4.0–5.0 | +3.5% | 5.07 | 6.21 | −£0.68 | −£4.21 | 25.8% | 19.3% | +6.5 | · |

### 6 · Newton Abbot 13:45 (card 14:45) — 2m3f Novice Handicap Hurdle (Katzoff NR) · mkt 1.259648053 · **⚠ THIN**
| horse | EX1 | EX2 | SB | band | dMed | BSPmed | BSPp75 | net@med | net@p75 | SB% | EX2% | div | arb |
|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|:--:|
| Kittys Glance | 2.76 | 2.74 | 2.50 | 2.5–3.0 | +0.0% | 2.76 | 3.24 | **£0.00** | −£2.94 | 37.3% | 42.1% | −4.8 | · |
| Ask Peter | 4.80 | 5.00 | 3.25 | 4.0–5.0 | +3.5% | 4.97 | 6.08 | −£0.68 | −£4.21 | 28.7% | 23.1% | +5.6 | · |
| Backer Bilk | 5.00 | 5.10 | 4.50 | 5.0–6.0 | +4.2% | 5.21 | 6.50 | −£0.81 | −£4.61 | 20.7% | 22.6% | −1.9 | · |
| Saucats | 8.40 | 9.40 | 7.00 | 8–10 | +7.3% | 9.01 | 11.61 | −£1.36 | −£5.54 | 13.3% | 12.3% | +1.1 | · |

---

## Totals

| | net @ band median | net @ 75th-pct drift |
|---|--:|--:|
| **24 bets × £20 (£480 staked)** | **−£19.86** | **−£107.82** |
| per-bet mean | −£0.83 (−4.1%) | −£4.49 (−22.5%) |

Three genuine ~2.7–2.9 favourites (Comical Point, Likewhatyousee, Kittys Glance) sit in the only band with a **zero** median drift (2.5–3.0) and so break **exactly even** at the median; every other runner is in a band that drifts OUT (median +2.6% → +10.4%), so BSP projects *above* the back price and the greened trade is a locked small loss, worsening into the tail.

## 3 · Sportsbook cross-check (SB vs EX2)

- **Zero cross-market arbs.** In all 24 runners the raw SB price is **≤ EX2** (no runner where SB odds > EX2 best lay), so there is no back-SB/lay-EX arb — exactly as expected.
- **SB is systematically shorter than EX** (SB odds < EX in ~every runner): the partial top-4 SB book sums to **1.07–1.21** implied vs EX2's **0.47–1.00**, i.e. the sportsbook is carrying a margin the exchange does not. **This SB-shortness is bookmaker overround, not signal.**
- **Per-runner SB-vs-EX2 divergence** (both normalised over the same top-4 subset) is small and non-systematic — mostly **±1–6 pp** (largest +6.5 Getmyfriend, +6.1 Ronson, −5.1 Likewhatyousee). That is the sportsbook distributing its margin slightly differently across the head of the market, not a tradeable disagreement. (Caveat: normalised over the **top-4 only**, so absolute implied% are inflated; read the SB-vs-EX2 *difference*, not the level.)

## 4 · Thin-market flags

**Doncaster 13:35, Newton Abbot 13:10, Newton Abbot 13:45** were matched £613–£1,407 at capture. For these: **BSP is a noisy projection** (the band-drift median is a population statistic; on £1k-matched markets a single late order moves the close a lot), and — decisive for this trade — the **greened lay fill is uncertain**: you may not get matched at the modelled BSP in size at the off. Treat all six of their non-breakeven losses as **best-case**; realistic execution is worse.

## 5 · Verdict

| race | verdict |
|---|---|
| Sandown 12:50 | **No edge.** Comical Point breakeven at median; other three lose. SB margin ~10%. |
| Sandown 13:25 | **No edge.** Favourite Ronson already 4.6 (band 4–5, +3.5% drift); whole card loses at median. |
| Doncaster 13:00 | **No edge.** Two 3.0–3.6 favourites lose ~£0.52; Jumeirah SB n/a (BTL leg only). |
| Doncaster 13:35 ⚠ | **No edge + execution risk.** All in 5–8 bands; thin market, fill uncertain. |
| Newton Abbot 13:10 ⚠ | **No edge.** Likewhatyousee breakeven at median; rest lose. Thin. |
| Newton Abbot 13:45 ⚠ | **No edge.** Kittys Glance breakeven at median; rest lose. Thin. |

**Overall:** **No tradeable edge — verdict unchanged from the prior run, now on real observed morning prices rather than model proxies.** Using genuine market prices makes the sheet *less bad* (−£19.86 vs −£26.43 at median) because the real top-of-market is shorter than the under-confident model priced it, but the conclusion holds: the head of the market sits in drift-OUT bands, back-to-lay nets **≤ £0 at the median and loses into the tail**, the only breakeven runners are ~2.7–2.9 favourites where median drift is exactly 0% (and 2% commission plus thin-market fill risk removes even that), and there is no SB↔EX arb. Prices drift out morning→close — the close remains the better back price. **Do not trade.**

*Artifacts: `reports/btl_observed_results.json`, `reports/band_drift.json`. No pipeline code touched; no order placed.*

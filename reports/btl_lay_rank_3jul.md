# Outright-lay ranking — top-4 in 6 races — Fri 3 Jul 2026 (REPORT + LOG only, no bets)

> **STRUCTURAL CAVEAT (verbatim):** the lay price already charges the true loss probability (9 tests, priced); this ranking finds the least-bad lay under drift assumptions, not an edge.

Generated **~07:24 BST**. **No bet placed; none should be off this sheet.**

## Trade & assumptions

- **Trade:** OUTRIGHT LAY, lay to win £20 (backer's stake £20 against us), **settled on the race**, 2% commission. Win **£20×0.98 = £19.60** if the horse **loses**; pay liability **£20×(strike−1)** if it **wins**.
- **Expected P&L** uses the **band-median projected BSP** to set the fair win probability `p = 1/BSP_proj`, `BSP_proj = EX2 × (1 + band-median drift)` (`reports/band_drift.json`, discovery). This is the only validated input. Laying *below* the projected BSP = layer's positive CLV — the mirror of the back-side drift-out.
- **Lay strike (stated on every row):** you supplied **EX2 = best-back**, which you *cannot lay at*. Primary quotable lay = **EX2 + 1 Betfair tick**; sensitivity columns at **EX2×1.025** and **EX2×1.05**. Every EV column below is labelled with its strike assumption.

Ranked within each race by **EV at EX2 + 1 tick** (best = least-bad / most-positive).

---

### 1 · Sandown 12:50 — 5f Hcap · mkt 1.259648496
| rk | horse | EX2 | band | projBSP | lay +1tick | CLV@+1t | **EV@+1tick** | EV@×1.025 | EV@×1.05 |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | One And Gone | 13.00 | 10–15 | 14.35 | 13.50 | +5.9% | **+£0.81** | +£1.05 | +£0.60 |
| 2 | Havana Hurricane | 4.70 | 4.0–5.0 | 4.87 | 4.80 | +1.3% | −£0.05 | −£0.12 | −£0.60 |
| 3 | Comical Point | 2.86 | 2.5–3.0 | 2.86 | 2.88 | −0.7% | −£0.40 | −£0.76 | −£1.26 |
| 4 | Westport | 2.90 | 2.5–3.0 | 2.90 | 2.92 | −0.7% | −£0.40 | −£0.76 | −£1.26 |

Best = **One And Gone** (survives ×1.05) — but it's a **13.0 FLB longshot**; liability **£250** to win £20.

### 2 · Sandown 13:25 — 5f Listed · mkt 1.259648502
| rk | horse | EX2 | band | projBSP | lay +1tick | CLV@+1t | **EV@+1tick** | EV@×1.025 | EV@×1.05 |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | Miss Lizzy | 5.10 | 5.0–6.0 | 5.32 | 5.20 | +2.2% | **+£0.11** | +£0.01 | −£0.47 |
| 2 | A Bear Affair | 6.20 | 6.0–8.0 | 6.54 | 6.40 | +2.2% | +£0.10 | +£0.24 | −£0.23 |
| 3 | Bill The Bull | 6.00 | 6.0–8.0 | 6.33 | 6.20 | +2.1% | +£0.09 | +£0.24 | −£0.23 |
| 4 | Ronson | 4.70 | 4.0–5.0 | 4.87 | 4.80 | +1.3% | −£0.05 | −£0.12 | −£0.60 |

Best = **Miss Lizzy**: +£0.11 at +1 tick, **DIES by ×1.05 (−£0.47)** — strikeability trap. Liability £84.

### 3 · Doncaster 13:00 — 6f Nov Stks · mkt 1.259648089
| rk | horse | EX2 | band | projBSP | lay +1tick | CLV@+1t | **EV@+1tick** | EV@×1.025 | EV@×1.05 |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | No More Pino | 11.50 | 10–15 | 12.69 | 12.00 | +5.5% | **+£0.72** | +£1.06 | +£0.61 |
| 2 | Sultan Darius | 9.60 | 8–10 | 10.30 | 9.80 | +4.8% | +£0.61 | +£0.53 | +£0.06 |
| 3 | Launch Sequence | 3.55 | 3.0–4.0 | 3.64 | 3.60 | +1.2% | −£0.05 | −£0.26 | −£0.75 |
| 4 | Jumeirah Storm | 3.05 | 3.0–4.0 | 3.13 | 3.10 | +1.0% | −£0.08 | −£0.24 | −£0.73 |

Best = **No More Pino** (survives ×1.05) — an **11.5 FLB longshot**; liability **£220**.

### 4 · Doncaster 13:35 — 1m Hcap · mkt 1.259648109 · ⚠THIN
| rk | horse | EX2 | band | projBSP | lay +1tick | CLV@+1t | **EV@+1tick** | EV@×1.025 | EV@×1.05 |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | Yafaarr | 7.40 | 6.0–8.0 | 7.81 | 7.60 | +2.7% | **+£0.19** | +£0.23 | −£0.24 |
| 2 | Tilani | 5.90 | 5.0–6.0 | 6.15 | 6.00 | +2.4% | +£0.15 | −£0.00 | −£0.48 |
| 3 | Al Muqdad | 5.60 | 5.0–6.0 | 5.84 | 5.70 | +2.4% | +£0.14 | +£0.00 | −£0.48 |
| 4 | Amidst The Chaos | 6.60 | 6.0–8.0 | 6.97 | 6.80 | +2.4% | +£0.14 | +£0.24 | −£0.24 |

Best = **Yafaarr**: +£0.19 at +1 tick, **DIES by ×1.05 (−£0.24)** — strikeability trap. Thin market.

### 5 · Newton Abbot 13:10 — 2m1f Mdn Hrd · mkt 1.259648047 · ⚠THIN
| rk | horse | EX2 | band | projBSP | lay +1tick | CLV@+1t | **EV@+1tick** | EV@×1.025 | EV@×1.05 |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | Getmyfriend | 5.20 | 5.0–6.0 | 5.42 | 5.30 | +2.2% | **+£0.12** | +£0.01 | −£0.47 |
| 2 | Elated | 4.40 | 4.0–5.0 | 4.56 | 4.50 | +1.2% | −£0.07 | −£0.11 | −£0.60 |
| 3 | For Her Glory | 4.30 | 4.0–5.0 | 4.45 | 4.40 | +1.2% | −£0.08 | −£0.11 | −£0.60 |
| 4 | Likewhatyousee | 2.90 | 2.5–3.0 | 2.90 | 2.92 | −0.7% | −£0.40 | −£0.76 | −£1.26 |

Best = **Getmyfriend**: +£0.12 at +1 tick, **DIES by ×1.05 (−£0.47)** — strikeability trap. Thin market.

### 6 · Newton Abbot 13:45 — 2m3f Nov Hcap Hrd · mkt 1.259648053 · ⚠THIN
| rk | horse | EX2 | band | projBSP | lay +1tick | CLV@+1t | **EV@+1tick** | EV@×1.025 | EV@×1.05 |
|--:|---|--:|--:|--:|--:|--:|--:|--:|--:|
| 1 | Saucats | 9.40 | 8–10 | 10.08 | 9.60 | +4.8% | **+£0.60** | +£0.53 | +£0.07 |
| 2 | Backer Bilk | 5.10 | 5.0–6.0 | 5.32 | 5.20 | +2.2% | +£0.11 | +£0.01 | −£0.47 |
| 3 | Ask Peter | 5.00 | 5.0–6.0 | 5.21 | 5.10 | +2.1% | +£0.11 | +£0.01 | −£0.47 |
| 4 | Kittys Glance | 2.74 | 2.5–3.0 | 2.74 | 2.76 | −0.7% | −£0.40 | −£0.75 | −£1.25 |

Best = **Saucats** (survives ×1.05) — a **9.4 FLB longshot**; liability **£172**. Thin market.

---

## The strikeability trap = the verdict

**The ranking mechanically favours the longest price in the race** — because the band-median drift model projects the biggest drift-out (hence biggest "layer CLV") for longshots (10–15 band +10.4%, 8–10 band +7.3%). That is the **favourite-longshot tail**, the exact artifact the project has priced nine times.

- **3/6 race-best lays die by ×1.05** (Miss Lizzy, Yafaarr, Getmyfriend): +EV of ~+£0.1–0.2 at EX2+1 tick, negative by a realistic 5% strikeability haircut. Textbook trap — the "edge" was the sub-tick gap to the projected BSP.
- **3/6 "survive ×1.05" (One And Gone 13.0, No More Pino 11.5, Saucats 9.4) — but this is not an edge:** their EV is positive only because the band-median *assumes* they blow out to 14.4 / 12.7 / 10.1 (the FLB drift the mirror Gate 2 already ruled **ARTIFACT** at holdout). It is the unquotable-drift assumption, not a mispricing; and it demands **£172–£250 liability to win £20** in thin morning markets — ruinous variance for a phantom edge.
- **Shortest favourites (2.5–3.0: Comical Point, Westport, Likewhatyousee, Kittys Glance) are negative even at EX2+1 tick** (−£0.40 ≈ pure commission on the £20). The lay price simply charges the true win probability plus the exchange margin.

**Overall verdict: ARTIFACT / least-bad lay under drift assumptions — no strikeable lay edge.** Consistent with the 9-test PRICED conclusion and the mirror Gate 2 ARTIFACT: laying at the quotable strike (EX2+1 tick, or worse) charges the true loss probability; any positive EV is (a) the band-median drift *assumption*, which dies at a realistic 2.5–5% haircut, and (b) concentrated in the FLB longshot tail where liability is punitive. **No bet.**

*Log: `paper_trades/btl_lay_3jul.json` (all 24 ranked, 3-strike sensitivity, structural caveat in header). Reuses `reports/band_drift.json`. No pipeline code touched; no order placed. Anecdote, not evidence.*

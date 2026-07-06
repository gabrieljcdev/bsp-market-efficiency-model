# Live-card model pass — 2 Jul 2026 (observation only; no bets)

Micro-bet calibration + live-path regression check (canon_horse suffix fix, 1 Jul). Model has **no established edge** — fair prices are for manual side-by-side vs the exchange ladder only. No Betfair prices, CLV, value flags, or selections produced.

**Provenance:** cards pulled live via rpscrape (`racecards.py --day 1 --region gb`) → `vendor/rpscrape/racecards/2026-07-02.json`. model_prob = Stage-1 conditional logit (features: or, draw, lbs, age), fit fresh on `joined_gb_2018_2026.csv` (726,045 runners), softmax within race. Layer-2 (career_runs, run_style_proxy, trainer/jockey SR, layer2_hit) from the shared strictly-prior `history_join` engine. trainer_SR/jockey_SR = overall prior strike rate (+n).

## ⚠️ ALERTS

1. **Race-time mapping (+1h):** every task-sheet time is 1 hour earlier than the pulled card off-time (BST+1h gotcha). Mapping verified by the NR fingerprint on the last race (task 17:33 NRs Shihoku+Port Road = card **18:33** NR Port Road+Shihoku). Tables are keyed by the true card off-time.
2. **No silent-lookup suspicion:** every career_runs=0 runner is a genuine debut (absent from the history index entirely), not a canon_horse lookup miss. The 1 Jul suffix-normalisation fix holds at volume across these 5 races.

---
### Nottingham 16:05  (1m Hcap (8))  —  task-sheet time 15:05 [+1h BST offset]

Field: 8 active  •  probs renormalised over 8 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Thornaby Annie | 15.0% | 6.67 | held_up | 9 | 9% (n=1122) | 12% (n=424) | ✓ |
| Mayflower Billy | 14.2% | 7.04 | prominent | 5 | 8% (n=935) | 11% (n=3381) | ✓ |
| Storm Esme | 13.3% | 7.51 | midfield | 6 | 9% (n=11103) | 11% (n=5175) | ✓ |
| Empirical | 12.5% | 8.01 | held_up | 4 | 14% (n=3689) | 14% (n=4097) | ✓ |
| Sahara Magic | 12.1% | 8.27 | held_up | 6 | 11% (n=7014) | 12% (n=6875) | ✓ |
| Albertini Star | 11.2% | 8.91 | prominent | 3 | 13% (n=4958) | 14% (n=4019) | ✓ |
| Kameko Fever | 11.2% | 8.96 | prominent | 8 | 11% (n=281) | 13% (n=2216) | ✓ |
| Mereside Princess | 10.5% | 9.50 | held_up | 14 | 10% (n=1000) | 9% (n=1116) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **100%** (8/8). career_runs=0: 0 runner(s).

### Kempton (AW) 16:55  (7f Nov Stks (10))  —  task-sheet time 15:55 [+1h BST offset]

Field: 10 active  •  probs renormalised over 10 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Khaleejy | 12.2% | 8.18 | prominent | 2 | 0% (n=10) | 8% (n=458) | ✓ |
| Landslide | 10.6% | 9.43 | held_up | 1 | 10% (n=126) | 10% (n=9696) | ✓ |
| Screen Actor | 10.5% | 9.52 | held_up | 1 | 6% (n=2464) | 6% (n=409) | ✓ |
| Charlies Cannon | 10.2% | 9.80 | — | 0 | 18% (n=4738) | 15% (n=7035) | · |
| Kenergy ⚑ | 9.9% | 10.09 | led | 2 | 10% (n=1607) | 13% (n=1880) | ✓ |
| Veil Of Clouds | 9.6% | 10.41 | prominent | 2 | 19% (n=2334) | 16% (n=3942) | ✓ |
| Gift Box | 9.5% | 10.52 | — | 0 | 4% (n=706) | 8% (n=1396) | · |
| Stormy Music | 9.2% | 10.83 | prominent | 2 | 16% (n=7719) | 10% (n=5343) | ✓ |
| Shadow Brigade ⚑ | 9.1% | 10.95 | led | 3 | 13% (n=1924) | 9% (n=560) | ✓ |
| Rajiba | 9.1% | 11.04 | midfield | 2 | 14% (n=3478) | 12% (n=2147) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Kenergy, Shadow Brigade — tonight's in-running Stage-0 eyeball targets.
layer2_hit coverage: **80%** (8/10)  ⚠️ <100%. career_runs=0: 2 runner(s) — 2 genuine debut (absent from history index), 0 present-but-zero (see ALERT).

### Kempton (AW) 17:33  (7f Nov Stks (9))  —  task-sheet time 16:33 [+1h BST offset]

Field: 9 active  •  probs renormalised over 9 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Gold Star Gazing | 12.3% | 8.14 | prominent | 3 | 15% (n=2511) | 12% (n=5291) | ✓ |
| Brave New World | 11.8% | 8.46 | held_up | 2 | 14% (n=3689) | 10% (n=1614) | ✓ |
| Yazoo | 11.7% | 8.54 | held_up | 1 | 11% (n=1963) | 15% (n=4651) | ✓ |
| One Of The Boys | 11.6% | 8.62 | midfield | 1 | 13% (n=2940) | 16% (n=3942) | ✓ |
| Conspiracist | 11.4% | 8.79 | prominent | 1 | 16% (n=7719) | 10% (n=5343) | ✓ |
| Le Samourai | 11.2% | 8.96 | held_up | 1 | 18% (n=4738) | 20% (n=4172) | ✓ |
| Cortado Girl | 10.6% | 9.43 | prominent | 2 | 9% (n=90) | 7% (n=965) | ✓ |
| Lady Fizz | 10.1% | 9.90 | held_up | 1 | 0% (n=10) | 8% (n=458) | ✓ |
| Korbut | 9.3% | 10.70 | prominent | 4 | 17% (n=2050) | 10% (n=9696) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **100%** (9/9). career_runs=0: 0 runner(s).

### Kempton (AW) 18:03  (7f Nursery (8))  —  task-sheet time 17:03 [+1h BST offset]

Field: 8 active  •  probs renormalised over 8 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Rhodes Runner | 17.2% | 5.81 | midfield | 2 | 18% (n=4738) | 20% (n=4172) | ✓ |
| Time Saxon Warrior | 15.2% | 6.57 | held_up | 3 | 14% (n=3478) | 16% (n=3942) | ✓ |
| Indian Land | 14.5% | 6.90 | midfield | 2 | 18% (n=4738) | 15% (n=7035) | ✓ |
| Bayside | 14.3% | 7.01 | midfield | 4 | 12% (n=2593) | 15% (n=4651) | ✓ |
| Bin Waary ⚑ | 12.8% | 7.79 | led | 3 | 13% (n=3745) | 10% (n=5343) | ✓ |
| Graceful George | 10.8% | 9.27 | prominent | 3 | 11% (n=2262) | 9% (n=1717) | ✓ |
| Agnes Hathaway | 8.4% | 11.92 | held_up | 3 | 13% (n=2940) | 10% (n=9696) | ✓ |
| Magical Life | 6.8% | 14.70 | held_up | 3 | 6% (n=1726) | 13% (n=221) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Bin Waary — tonight's in-running Stage-0 eyeball targets.
layer2_hit coverage: **100%** (8/8). career_runs=0: 0 runner(s).

### Kempton (AW) 18:33  (1m Hcap (8; NR Shihoku, Port Road))  —  task-sheet time 17:33 [+1h BST offset]

Field: 8 active  •  NR excluded: Port Road, Shihoku  •  probs renormalised over 8 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| First Ambition | 15.4% | 6.48 | midfield | 8 | 7% (n=387) | 10% (n=5343) | ✓ |
| Blue Prince | 15.3% | 6.55 | held_up | 39 | 10% (n=4275) | 15% (n=7035) | ✓ |
| Zabeel Alkabeir | 14.6% | 6.83 | prominent | 3 | 17% (n=1983) | 20% (n=4172) | ✓ |
| Grizedale | 14.5% | 6.88 | prominent | 6 | 14% (n=1142) | 12% (n=2410) | ✓ |
| Spangled Mac | 12.3% | 8.11 | held_up | 33 | 16% (n=3635) | 16% (n=3942) | ✓ |
| Maximising | 12.1% | 8.29 | midfield | 8 | 14% (n=1740) | 12% (n=5291) | ✓ |
| Kitaro Kich | 10.6% | 9.47 | midfield | 30 | 10% (n=1607) | 13% (n=1880) | ✓ |
| Bold Suitor | 5.2% | 19.30 | midfield | 36 | 10% (n=125) | 8% (n=1396) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **100%** (8/8). career_runs=0: 0 runner(s).

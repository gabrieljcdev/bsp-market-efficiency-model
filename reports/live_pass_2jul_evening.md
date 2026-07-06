# Live-card model pass — EVENING — 2 Jul 2026 (observation only; no bets)

Generated at **14:54 BST**. All GB races with off-time later than now. Micro-bet calibration + live-path regression check (canon_horse suffix fix). Model has **no established edge** — fair prices are for manual side-by-side vs the exchange ladder only. No Betfair prices, CLV, value flags, or selections produced.

**Scope:** 28 races across Kempton (AW) (8), Newbury (6), Nottingham (5), Yarmouth (5), Perth (4).

**Provenance:** cards re-pulled live via rpscrape (`racecards.py --day 1 --region gb`) → `vendor/rpscrape/racecards/2026-07-02.json`. model_prob = Stage-1 conditional logit (or, draw, lbs, age), fit fresh on `joined_gb_2018_2026.csv` (726,044 runners), softmax within race. Layer-2 (career_runs, run_style_proxy, trainer/jockey SR, layer2_hit) from the shared strictly-prior `history_join` engine. trainer_SR/jockey_SR = overall prior strike rate (+n). Tables keyed to TRUE card off-times (all BST).

## ⚠️ ALERTS

1. **BST timing:** current time 14:54 BST — the afternoon sheet was 1h behind card off-times, so this pass keys strictly to the card's own off-times (all BST). At this hour "remaining" spans the afternoon Kempton/Nottingham/Perth/Yarmouth cards too, not only the evening Newbury card the brief anticipated.
2. **No silent-lookup suspicion:** every career_runs=0 runner is a genuine debut (absent from the history index entirely), not a canon_horse lookup miss. The suffix-normalisation fix holds at volume across the whole evening card set.
3. **RF% not available:** the rpscrape card schema carries no non-runner reduction-factor field (RF% is exchange-derived and out of scope for this price-free pass); NRs are listed by name only.

---
### Nottingham 15:00  —  Hon. Alderman Malcolm Wood Memorial Nursery   [Flat, 5f, Good To Firm]

Field: 7 active  •  probs renormalised over 7 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Wait Geordie ⚑ | 21.9% | 4.57 | led | 3 | 14% (n=3614) | 13% (n=595) | ✓ |
| Undercover Affair ⚑ | 20.2% | 4.95 | led | 6 | 10% (n=4275) | 7% (n=2330) | ✓ |
| Seed Ya Later | 13.1% | 7.64 | held_up | 3 | 15% (n=1147) | 13% (n=1678) | ✓ |
| Havana Gift ⚑ | 12.1% | 8.23 | led | 3 | 10% (n=873) | 12% (n=6875) | ✓ |
| On The Queue Tee ⚑ | 12.1% | 8.28 | led | 3 | 6% (n=1726) | 14% (n=4097) | ✓ |
| Past Passion ⚑ | 10.3% | 9.67 | led | 3 | 10% (n=2308) | 8% (n=3348) | ✓ |
| Holi Scarlett | 10.2% | 9.76 | held_up | 3 | 12% (n=3663) | 12% (n=1223) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Wait Geordie, Undercover Affair, Havana Gift, On The Queue Tee, Past Passion
layer2_hit coverage: **100%** (7/7). career_runs=0: 0.

### Yarmouth 15:09  —  Weatherbys EBF Maiden Stakes (GBB Race)  [Flat, 6f, Good To Firm]

Field: 4 active  •  probs renormalised over 4 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Shoof | 25.4% | 3.94 | prominent | 1 | 13% (n=1924) | 8% (n=3656) | ✓ |
| Sovereign Dawn | 25.1% | 3.98 | midfield | 1 | 7% (n=387) | 6% (n=141) | ✓ |
| Cant Stop | 24.9% | 4.02 | — | 0 | 11% (n=1963) | 12% (n=2768) | · |
| Nabati | 24.6% | 4.06 | — | 0 | 29% (n=2883) | 22% (n=4631) | · |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **50%** (2/4)  ⚠️ <100%. career_runs=0: 2 — 2 genuine debut (absent from index), 0 present-but-zero (see ALERT).

### Perth 15:18  —  Secure Air Parks Edinburgh Airport Parking H  [Chase, 2m4f, Good]

Field: 6 active  •  NR excluded (1): Jiair Madrik  •  RF%: n/a (not in card schema)  •  probs renormalised over 6 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Gunnery Sergeant | 23.8% | 4.20 | — | 0 | 18% (n=1221) | 20% (n=5393) | · |
| Kinbara Firstdraft | 17.1% | 5.85 | held_up | 12 | 5% (n=183) | 9% (n=539) | ✓ |
| Moodofthemoment | 16.6% | 6.03 | midfield | 27 | 6% (n=1447) | 12% (n=3932) | ✓ |
| Wasdell Dundalk | 16.1% | 6.21 | held_up | 50 | 7% (n=386) | 14% (n=2613) | ✓ |
| Garde Des Champs | 14.3% | 7.00 | held_up | 36 | 10% (n=615) | 8% (n=649) | ✓ |
| Button Rock | 12.1% | 8.26 | — | 0 | 7% (n=297) | 12% (n=1786) | · |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **67%** (4/6)  ⚠️ <100%. career_runs=0: 2 — 2 genuine debut (absent from index), 0 present-but-zero (see ALERT).

### Nottingham 15:30  —  Construction Day 14th October Handicap  [Flat, 1m2f, Good To Firm]

Field: 6 active  •  NR excluded (1): Bergamo Gold  •  RF%: n/a (not in card schema)  •  probs renormalised over 6 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Al Maslool | 18.3% | 5.47 | held_up | 6 | 22% (n=5618) | 14% (n=4097) | ✓ |
| Red Rifle ⚑ | 17.6% | 5.67 | led | 8 | 12% (n=2160) | 11% (n=1426) | ✓ |
| Liveinthelight | 17.1% | 5.84 | held_up | 4 | 13% (n=813) | 14% (n=4019) | ✓ |
| Ceinture dOrion | 17.0% | 5.89 | midfield | 3 | 12% (n=7889) | 17% (n=5220) | ✓ |
| Emmas Letter | 16.1% | 6.22 | midfield | 9 | 10% (n=3391) | 12% (n=6875) | ✓ |
| Baron Wagstaff | 13.9% | 7.19 | midfield | 3 | 8% (n=699) | 10% (n=1128) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Red Rifle
layer2_hit coverage: **100%** (6/6). career_runs=0: 0.

### Yarmouth 15:40  —  Weatherbys Racing Bank Fillies' Novice Stake  [Flat, 7f, Good To Firm]

Field: 5 active  •  probs renormalised over 5 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Musical Times ⚑ | 22.3% | 4.49 | led | 1 | 29% (n=2883) | 22% (n=4631) | ✓ |
| Attack Attack | 19.7% | 5.07 | midfield | 2 | 13% (n=1924) | 8% (n=3656) | ✓ |
| Aunty Patsy | 19.5% | 5.12 | — | 0 | 13% (n=2940) | 15% (n=4277) | · |
| Skyglow | 19.3% | 5.17 | — | 0 | 11% (n=573) | 16% (n=5125) | · |
| Gracious Gift | 19.2% | 5.22 | — | 0 | 29% (n=2883) | 11% (n=929) | · |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Musical Times
layer2_hit coverage: **40%** (2/5)  ⚠️ <100%. career_runs=0: 3 — 3 genuine debut (absent from index), 0 present-but-zero (see ALERT).

### Perth 15:50  —  PWA Architecture Handicap Hurdle  [Hurdle, 2m4f, Good]

Field: 10 active  •  NR excluded (1): Fourofakind  •  RF%: n/a (not in card schema)  •  probs renormalised over 10 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Sonyourastar | 17.2% | 5.80 | prominent | 3 | 19% (n=4431) | 20% (n=5393) | ✓ |
| Betteryouthanme | 13.8% | 7.27 | held_up | 5 | 6% (n=1959) | 13% (n=784) | ✓ |
| Bayonetta | 12.8% | 7.84 | midfield | 8 | 17% (n=63) | 9% (n=290) | ✓ |
| Lenko | 12.5% | 8.00 | — | 0 | 18% (n=1221) | 14% (n=2613) | · |
| Top Flight Century | 12.2% | 8.20 | midfield | 26 | 6% (n=1447) | 8% (n=352) | ✓ |
| Breaking Ground | 7.8% | 12.87 | held_up | 7 | 6% (n=1959) | 9% (n=979) | ✓ |
| Fairly Fulling | 7.1% | 14.08 | held_up | 19 | 8% (n=958) | 9% (n=1463) | ✓ |
| King Kodiak | 6.9% | 14.51 | held_up | 12 | 8% (n=768) | 8% (n=620) | ✓ |
| Dreamings Free | 5.3% | 19.02 | prominent | 8 | 7% (n=71) | 9% (n=888) | ✓ |
| Malangen ⚑ | 4.5% | 22.10 | led | 98 | 7% (n=386) | 9% (n=995) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Malangen
layer2_hit coverage: **90%** (9/10)  ⚠️ <100%. career_runs=0: 1 — 1 genuine debut (absent from index), 0 present-but-zero (see ALERT).

### Nottingham 16:05  —  Watch Racing TV Now Handicap  [Flat, 1m½f, Good To Firm]

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
layer2_hit coverage: **100%** (8/8). career_runs=0: 0.

### Yarmouth 16:15  —  Winning Experience With Moulton Racing Handi  [Flat, 1m, Good To Firm]

Field: 5 active  •  NR excluded (1): Sir Edward Lear  •  RF%: n/a (not in card schema)  •  probs renormalised over 5 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Great Mates | 27.3% | 3.67 | midfield | 8 | 12% (n=3131) | 14% (n=3278) | ✓ |
| Tactical Plan | 20.6% | 4.85 | midfield | 24 | 10% (n=3391) | 12% (n=2768) | ✓ |
| Kalamunda | 18.6% | 5.38 | midfield | 24 | 11% (n=1001) | 22% (n=4631) | ✓ |
| Man Of Desert | 18.1% | 5.53 | midfield | 11 | 14% (n=725) | 15% (n=4277) | ✓ |
| Big Alex Walmsley | 15.4% | 6.48 | midfield | 6 | 8% (n=353) | 8% (n=3656) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **100%** (5/5). career_runs=0: 0.

### Perth 16:25  —  Horizon Parking UK's Leading Parking Company  [Chase, 3m, Good]

Field: 7 active  •  probs renormalised over 7 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| The Flying Poet | 27.5% | 3.63 | held_up | 10 | 19% (n=4431) | 20% (n=5393) | ✓ |
| Cosmic Blizzard ⚑ | 22.0% | 4.55 | led | 6 | 10% (n=615) | 12% (n=1786) | ✓ |
| Get A Superstar | 17.3% | 5.79 | midfield | 15 | 12% (n=1181) | 12% (n=1989) | ✓ |
| Defying Gravity | 9.9% | 10.09 | held_up | 8 | 7% (n=297) | 9% (n=539) | ✓ |
| Burgundy Man | 8.3% | 12.08 | midfield | 22 | 6% (n=1959) | 9% (n=1463) | ✓ |
| Twp Stori | 7.7% | 13.03 | midfield | 21 | 10% (n=668) | 9% (n=290) | ✓ |
| Thehairyfella | 7.3% | 13.63 | midfield | 4 | 18% (n=1221) | 14% (n=2613) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Cosmic Blizzard
layer2_hit coverage: **100%** (7/7). career_runs=0: 0.

### Nottingham 16:40  —  Wildwest Beer Festival 4th July Handicap  [Flat, 1m2f, Good To Firm]

Field: 9 active  •  probs renormalised over 9 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Pay Attention | 13.4% | 7.46 | held_up | 17 | 14% (n=173) | 9% (n=127) | ✓ |
| Mohmentous | 12.0% | 8.33 | midfield | 7 | 13% (n=813) | 17% (n=5220) | ✓ |
| Rugby Union | 11.9% | 8.41 | prominent | 2 | 10% (n=868) | 11% (n=3381) | ✓ |
| Spec Of Light | 11.7% | 8.57 | midfield | 18 | 4% (n=169) | 0% (n=18) | ✓ |
| Crimson Road | 11.1% | 9.01 | held_up | 22 | 7% (n=292) | 7% (n=3004) | ✓ |
| Talking In Kode | 10.8% | 9.30 | held_up | 5 | 16% (n=1434) | 6% (n=223) | ✓ |
| Phantom Shadow | 10.3% | 9.66 | midfield | 7 | 14% (n=603) | 14% (n=4097) | ✓ |
| Beauty Generation | 9.7% | 10.29 | held_up | 21 | 14% (n=116) | 12% (n=6875) | ✓ |
| Wadacre Geisha ⚑ | 9.1% | 10.96 | led | 5 | 13% (n=3745) | 11% (n=3991) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Wadacre Geisha
layer2_hit coverage: **100%** (9/9). career_runs=0: 0.

### Yarmouth 16:50  —  Mark Sumner Handicap  [Flat, 1m, Good To Firm]

Field: 7 active  •  probs renormalised over 7 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Give Me The Night | 18.8% | 5.31 | midfield | 9 | 12% (n=404) | 4% (n=49) | ✓ |
| Campani | 15.9% | 6.30 | held_up | 10 | 13% (n=3022) | 8% (n=3030) | ✓ |
| Midnights Dream | 15.7% | 6.36 | held_up | 22 | 11% (n=1001) | 22% (n=4631) | ✓ |
| Luminous Warrior | 15.5% | 6.47 | midfield | 14 | 12% (n=1059) | 12% (n=2768) | ✓ |
| Mart | 14.7% | 6.83 | held_up | 49 | 12% (n=1059) | 9% (n=423) | ✓ |
| Sporty Socks | 9.8% | 10.19 | midfield | 8 | 11% (n=752) | 9% (n=5700) | ✓ |
| Shaws Phoenix | 9.7% | 10.34 | prominent | 17 | 6% (n=365) | 10% (n=2500) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **100%** (7/7). career_runs=0: 0.

### Kempton (AW) 16:55  —  Unibet Supporting Safer Gambling Novice Stak  [Flat, 7f, Standard To Slow]

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

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Kenergy, Shadow Brigade
layer2_hit coverage: **80%** (8/10)  ⚠️ <100%. career_runs=0: 2 — 2 genuine debut (absent from index), 0 present-but-zero (see ALERT).

### Perth 17:00  —  AEJ Facilities Management Handicap Hurdle  [Hurdle, 3m, Good]

Field: 10 active  •  probs renormalised over 10 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Maggies Boy | 16.7% | 6.00 | midfield | 17 | 12% (n=2522) | 12% (n=3932) | ✓ |
| Creadan Grace | 15.5% | 6.47 | prominent | 2 | 18% (n=1221) | 9% (n=2114) | ✓ |
| Less Legacy | 11.8% | 8.48 | held_up | 46 | 8% (n=958) | 9% (n=1463) | ✓ |
| Loro White | 11.4% | 8.74 | held_up | 6 | 19% (n=4431) | 20% (n=5393) | ✓ |
| The Best Way | 10.5% | 9.57 | held_up | 8 | 17% (n=1844) | 14% (n=2613) | ✓ |
| CMon So | 9.6% | 10.47 | held_up | 6 | 10% (n=615) | 12% (n=1786) | ✓ |
| Dalileo | 7.3% | 13.72 | held_up | 49 | 7% (n=386) | 9% (n=995) | ✓ |
| Prince Nino | 6.0% | 16.68 | midfield | 32 | 6% (n=484) | 8% (n=649) | ✓ |
| King Gold Boy | 5.7% | 17.45 | held_up | 7 | 0% (n=89) | 8% (n=352) | ✓ |
| Myfavouritesister | 5.6% | 17.71 | held_up | 14 | 15% (n=376) | 17% (n=6525) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **100%** (10/10). career_runs=0: 0.

### Nottingham 17:15  —  Events At Nottingham Racecourse Training Ser  [Flat, 5f, Good To Firm]

Field: 7 active  •  probs renormalised over 7 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Winchurch | 21.1% | 4.73 | held_up | 28 | 11% (n=7014) | 18% (n=103) | ✓ |
| Sams Hope | 16.6% | 6.01 | held_up | 38 | 9% (n=346) | 6% (n=70) | ✓ |
| Beaumadier | 13.8% | 7.27 | prominent | 29 | 8% (n=3199) | 0% (n=17) | ✓ |
| Miss Brazen | 12.8% | 7.80 | prominent | 34 | 9% (n=2644) | 6% (n=222) | ✓ |
| Spirit Of Applause | 12.6% | 7.93 | held_up | 48 | 9% (n=11103) | 12% (n=120) | ✓ |
| Muker | 12.6% | 7.96 | held_up | 47 | 9% (n=3259) | 0% (n=18) | ✓ |
| Hurt You Never | 10.5% | 9.55 | prominent | 67 | 9% (n=1122) | 9% (n=127) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **100%** (7/7). career_runs=0: 0.

### Yarmouth 17:25  —  Branfords Handicap  [Flat, 7f, Good To Firm]

Field: 9 active  •  probs renormalised over 9 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Jungle Knight | 13.2% | 7.55 | held_up | 8 | 12% (n=404) | 4% (n=49) | ✓ |
| Hakin Adraar | 12.7% | 7.87 | midfield | 6 | 9% (n=346) | 10% (n=2500) | ✓ |
| Dancing With Drums | 12.6% | 7.92 | midfield | 10 | 16% (n=77) | 8% (n=3030) | ✓ |
| Federal Envoy ⚑ | 11.5% | 8.71 | led | 20 | 18% (n=160) | 14% (n=3278) | ✓ |
| Giant ⚑ | 10.9% | 9.19 | led | 39 | 11% (n=5722) | 10% (n=584) | ✓ |
| Wilde And Dandy | 10.3% | 9.71 | held_up | 40 | 9% (n=2869) | 15% (n=4277) | ✓ |
| Adelaide Bay | 9.6% | 10.41 | held_up | 18 | 11% (n=1809) | 10% (n=1820) | ✓ |
| Mayflower Rock | 9.6% | 10.42 | midfield | 3 | 12% (n=1059) | 12% (n=2768) | ✓ |
| Dion Baker ⚑ | 9.5% | 10.48 | led | 65 | 10% (n=979) | 8% (n=3656) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Federal Envoy, Giant, Dion Baker
layer2_hit coverage: **100%** (9/9). career_runs=0: 0.

### Kempton (AW) 17:33  —  Unibet Supporting Safer Gambling Novice Stak  [Flat, 7f, Standard To Slow]

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
layer2_hit coverage: **100%** (9/9). career_runs=0: 0.

### Kempton (AW) 18:03  —  Bet £20 Get £20 With Unibet Nursery Handicap  [Flat, 7f, Standard To Slow]

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

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Bin Waary
layer2_hit coverage: **100%** (8/8). career_runs=0: 0.

### Newbury 18:15  —  Sequoia Hair & Beauty Group Handicap  [Flat, 1m2f, Good To Firm]

Field: 11 active  •  probs renormalised over 11 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Kimeko Glory | 10.0% | 9.96 | midfield | 17 | 13% (n=3418) | 12% (n=4777) | ✓ |
| Brighlee | 9.9% | 10.13 | prominent | 6 | 12% (n=1366) | 14% (n=7591) | ✓ |
| Morcar | 9.6% | 10.40 | prominent | 27 | 11% (n=9210) | 12% (n=1675) | ✓ |
| Ablon | 9.6% | 10.46 | held_up | 4 | 11% (n=9210) | 12% (n=4280) | ✓ |
| Home Hero | 9.3% | 10.70 | prominent | 5 | 14% (n=3614) | 12% (n=8071) | ✓ |
| Rossa Raheen | 9.2% | 10.88 | held_up | 5 | 13% (n=813) | 12% (n=5376) | ✓ |
| Fanciulla Del West ⚑ | 9.1% | 10.98 | led | 4 | 14% (n=3689) | 12% (n=4560) | ✓ |
| James Choice | 8.8% | 11.30 | prominent | 3 | 11% (n=2091) | 9% (n=3992) | ✓ |
| Harlington | 8.6% | 11.69 | midfield | 34 | 18% (n=160) | 12% (n=1494) | ✓ |
| Perfect Scoundrel | 8.5% | 11.82 | midfield | 7 | 10% (n=1375) | 12% (n=2485) | ✓ |
| Madjid | 7.4% | 13.49 | held_up | 6 | 14% (n=603) | 10% (n=3840) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Fanciulla Del West
layer2_hit coverage: **100%** (11/11). career_runs=0: 0.

### Kempton (AW) 18:33  —  Unibet More Extra Place Races Handicap (Lond  [Flat, 1m, Standard To Slow]

Field: 8 active  •  NR excluded (2): Port Road, Shihoku  •  RF%: n/a (not in card schema)  •  probs renormalised over 8 (softmax, Σ=1.000)

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
layer2_hit coverage: **100%** (8/8). career_runs=0: 0.

### Newbury 18:50  —  Gracelands EBF Fillies' Novice Stakes (GBB/I  [Flat, 6f, Good To Firm]

Field: 14 active  •  probs renormalised over 14 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Topaz | 7.6% | 13.16 | held_up | 2 | 15% (n=1147) | 14% (n=7591) | ✓ |
| Parvenue Star | 7.5% | 13.29 | — | 0 | 11% (n=9210) | 12% (n=1675) | · |
| Nuit dEclair | 7.5% | 13.41 | — | 0 | 14% (n=1740) | 12% (n=5376) | · |
| Royal Message | 7.4% | 13.54 | midfield | 1 | 14% (n=3689) | 12% (n=4560) | ✓ |
| Gravastar | 7.3% | 13.68 | held_up | 1 | 11% (n=9210) | 12% (n=4280) | ✓ |
| Bymiddaytomorrow | 7.2% | 13.81 | prominent | 2 | 14% (n=3689) | 7% (n=1414) | ✓ |
| Art Of Life | 7.2% | 13.94 | — | 0 | 14% (n=3631) | 12% (n=8071) | · |
| Lola De Valence | 7.1% | 14.08 | — | 0 | 12% (n=2593) | 14% (n=250) | · |
| Kiah | 7.0% | 14.22 | — | 0 | 10% (n=1468) | 11% (n=1414) | · |
| Perfect Hope | 7.0% | 14.35 | midfield | 1 | 10% (n=1291) | 12% (n=1494) | ✓ |
| Spirit Of Progress | 6.9% | 14.49 | — | 0 | 10% (n=295) | 8% (n=1371) | · |
| Marsala | 6.8% | 14.63 | — | 0 | 18% (n=4738) | 15% (n=4378) | · |
| Fillipas | 6.8% | 14.78 | — | 1 | 12% (n=2593) | 10% (n=3840) | ✓ |
| Avalon Queen | 6.7% | 14.92 | midfield | 1 | 10% (n=1916) | 12% (n=4777) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **50%** (7/14)  ⚠️ <100%. career_runs=0: 7 — 7 genuine debut (absent from index), 0 present-but-zero (see ALERT).

### Kempton (AW) 19:08  —  Unibet More Extra Place Races Handicap (Lond  [Flat, 1m, Standard To Slow]

Field: 10 active  •  probs renormalised over 10 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Breakdancer | 13.8% | 7.24 | prominent | 5 | 19% (n=2334) | 20% (n=4172) | ✓ |
| The Liffey | 13.6% | 7.37 | prominent | 1 | 9% (n=90) | 10% (n=9696) | ✓ |
| Zatsgood | 12.9% | 7.75 | held_up | 4 | 16% (n=3635) | 16% (n=3942) | ✓ |
| Vincent Rocks | 12.2% | 8.21 | midfield | 6 | 14% (n=3614) | 10% (n=745) | ✓ |
| Renewal | 10.6% | 9.46 | prominent | 7 | 18% (n=4738) | 15% (n=7035) | ✓ |
| Notimeforchitchat | 9.6% | 10.45 | held_up | 16 | 14% (n=3478) | 12% (n=2147) | ✓ |
| Helm Rock | 9.2% | 10.89 | midfield | 59 | 14% (n=1142) | 12% (n=2410) | ✓ |
| Farasi Lane | 7.5% | 13.38 | held_up | 63 | 12% (n=1181) | 7% (n=15) | ✓ |
| Atlantis Blue | 6.0% | 16.72 | held_up | 27 | 10% (n=1607) | 13% (n=1519) | ✓ |
| Billy Mill | 4.7% | 21.06 | midfield | 68 | 12% (n=2593) | 6% (n=409) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **100%** (10/10). career_runs=0: 0.

### Newbury 19:25  —  Fidelity Energy Green Future Novice Stakes (  [Flat, 6f, Good To Firm]

Field: 10 active  •  NR excluded (1): Tumishi  •  RF%: n/a (not in card schema)  •  probs renormalised over 10 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Magi Melchior | 10.5% | 9.51 | — | 0 | 11% (n=9210) | 12% (n=4280) | · |
| Pride Of Toledo | 10.4% | 9.60 | — | 0 | 14% (n=3631) | 12% (n=8071) | · |
| Jimtrott | 10.2% | 9.78 | prominent | 1 | 11% (n=3307) | 9% (n=3992) | ✓ |
| Coatimundi | 10.1% | 9.88 | — | 0 | 13% (n=3418) | 12% (n=4777) | · |
| Alaskan Bear | 10.0% | 9.98 | — | 0 | 10% (n=31) | 15% (n=4378) | · |
| Off The Peg | 9.9% | 10.07 | — | 0 | 14% (n=3478) | 12% (n=2485) | · |
| Shakwaa | 9.8% | 10.17 | — | 0 | 14% (n=3689) | 12% (n=4560) | · |
| Secano | 9.7% | 10.27 | — | 0 | 14% (n=603) | 10% (n=3840) | · |
| Hackpen Hill | 9.6% | 10.37 | — | 0 | 14% (n=3689) | 7% (n=1414) | · |
| Noahs Gold | 9.6% | 10.47 | — | 0 | 15% (n=2295) | 12% (n=5376) | · |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **10%** (1/10)  ⚠️ <100%. career_runs=0: 9 — 9 genuine debut (absent from index), 0 present-but-zero (see ALERT).

### Kempton (AW) 19:43  —  Unibet 40,000+ Live Streamed Events Handicap  [Flat, 1m4f, Standard To Slow]

Field: 7 active  •  probs renormalised over 7 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Master Vintner | 19.6% | 5.09 | prominent | 5 | 18% (n=4738) | 15% (n=7035) | ✓ |
| Bulletin | 17.8% | 5.61 | midfield | 16 | 10% (n=2308) | 10% (n=5343) | ✓ |
| Thinthread | 17.6% | 5.68 | — | 0 | 10% (n=1607) | 13% (n=1880) | · |
| Steel Tiger | 15.2% | 6.58 | prominent | 13 | 19% (n=2334) | 20% (n=4172) | ✓ |
| Yaa Min | 12.1% | 8.28 | prominent | 10 | 9% (n=90) | 16% (n=3942) | ✓ |
| Max Mayhem | 11.2% | 8.96 | held_up | 16 | 10% (n=1607) | 13% (n=1519) | ✓ |
| Tripoli Flyer | 6.5% | 15.41 | held_up | 16 | 17% (n=4825) | 10% (n=1550) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **86%** (6/7)  ⚠️ <100%. career_runs=0: 1 — 1 genuine debut (absent from index), 0 present-but-zero (see ALERT).

### Newbury 20:00  —  World Cup Super Boosts At BetVictor Handicap  [Flat, 7f, Good To Firm]

Field: 14 active  •  NR excluded (1): Manly Fireball  •  RF%: n/a (not in card schema)  •  probs renormalised over 14 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Huscal | 8.5% | 11.74 | held_up | 15 | 13% (n=3418) | 12% (n=4777) | ✓ |
| Annastarzy | 8.5% | 11.78 | prominent | 7 | 11% (n=9210) | 11% (n=1414) | ✓ |
| Best Rate | 8.5% | 11.81 | held_up | 19 | 11% (n=9210) | 12% (n=4280) | ✓ |
| Herculeus | 8.2% | 12.24 | prominent | 10 | 12% (n=1190) | 10% (n=3840) | ✓ |
| Kennington | 8.1% | 12.29 | midfield | 2 | 12% (n=2445) | 12% (n=8071) | ✓ |
| Gallant | 8.1% | 12.40 | held_up | 14 | 11% (n=37) | 14% (n=7591) | ✓ |
| Melvin Udall | 8.0% | 12.48 | midfield | 6 | 8% (n=1662) | 12% (n=5376) | ✓ |
| Splash | 7.0% | 14.20 | midfield | 4 | 9% (n=1808) | 9% (n=1030) | ✓ |
| Slipper Time | 6.3% | 15.94 | held_up | 7 | 10% (n=1214) | 8% (n=2709) | ✓ |
| Stratocracy | 6.2% | 16.23 | prominent | 26 | 12% (n=25) | 7% (n=1414) | ✓ |
| Mr Ubiquitous | 6.1% | 16.40 | prominent | 17 | 12% (n=1055) | 12% (n=1127) | ✓ |
| Euphonia | 5.8% | 17.29 | prominent | 9 | 14% (n=3689) | 12% (n=4560) | ✓ |
| Mercury Day | 5.7% | 17.59 | midfield | 15 | 10% (n=781) | 14% (n=250) | ✓ |
| Commander Of Life | 5.1% | 19.63 | midfield | 42 | 8% (n=935) | 15% (n=4378) | ✓ |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **100%** (14/14). career_runs=0: 0.

### Kempton (AW) 20:17  —  Try Unibet's New Improved Acca Boosts Handic  [Flat, 6f, Standard To Slow]

Field: 11 active  •  NR excluded (1): Perfect Location  •  RF%: n/a (not in card schema)  •  probs renormalised over 11 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Evenepoel | 10.2% | 9.76 | held_up | 3 | 15% (n=5105) | 10% (n=9696) | ✓ |
| Shahik | 10.2% | 9.79 | held_up | 7 | 7% (n=387) | 12% (n=5291) | ✓ |
| Echo Of Faith | 10.1% | 9.89 | midfield | 1 | 7% (n=1303) | 10% (n=1614) | ✓ |
| The Lost Sock | 10.0% | 9.98 | prominent | 8 | 19% (n=4846) | 12% (n=2410) | ✓ |
| Aigeas ⚑ | 9.7% | 10.28 | led | 2 | 10% (n=126) | 12% (n=2147) | ✓ |
| Night Shining | 9.6% | 10.41 | prominent | 3 | 16% (n=3635) | 16% (n=3942) | ✓ |
| Unionville | 8.7% | 11.54 | prominent | 4 | 6% (n=2464) | 6% (n=409) | ✓ |
| Trinculo ⚑ | 8.1% | 12.35 | led | 3 | 10% (n=1607) | 13% (n=1880) | ✓ |
| Concert | 7.9% | 12.59 | midfield | 9 | 15% (n=1147) | 10% (n=1239) | ✓ |
| Arctic Wind ⚑ | 7.8% | 12.75 | led | 6 | 10% (n=4275) | 15% (n=7035) | ✓ |
| Our Guy | 7.5% | 13.30 | prominent | 5 | 9% (n=830) | 12% (n=426) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Aigeas, Trinculo, Arctic Wind
layer2_hit coverage: **100%** (11/11). career_runs=0: 0.

### Newbury 20:30  —  Local IQ Handicap  [Flat, 1m, Good To Firm]

Field: 5 active  •  probs renormalised over 5 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Lucky Luna | 23.0% | 4.35 | midfield | 3 | 11% (n=9210) | 12% (n=4280) | ✓ |
| Thanos | 22.8% | 4.39 | held_up | 8 | 14% (n=603) | 10% (n=3840) | ✓ |
| Drymee | 22.2% | 4.51 | prominent | 3 | 15% (n=2511) | 14% (n=7591) | ✓ |
| Del Corso | 16.3% | 6.12 | midfield | 6 | 14% (n=3689) | 12% (n=4560) | ✓ |
| Venturing | 15.7% | 6.36 | — | 0 | 11% (n=7574) | 12% (n=5376) | · |

**Predicted front-runner(s):** none classified `led` from prior comments.
layer2_hit coverage: **80%** (4/5)  ⚠️ <100%. career_runs=0: 1 — 1 genuine debut (absent from index), 0 present-but-zero (see ALERT).

### Kempton (AW) 20:53  —  Try Unibet's New Smartview Racecards Handica  [Flat, 6f, Standard To Slow]

Field: 11 active  •  NR excluded (1): Balon dOr  •  RF%: n/a (not in card schema)  •  probs renormalised over 11 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Travel Agent | 11.5% | 8.72 | held_up | 16 | 16% (n=77) | 6% (n=409) | ✓ |
| Invincible Speed | 10.4% | 9.59 | midfield | 28 | 8% (n=3199) | 12% (n=2410) | ✓ |
| Newsreader | 10.2% | 9.78 | midfield | 17 | 10% (n=136) | 10% (n=2600) | ✓ |
| Dannick | 9.8% | 10.18 | held_up | 15 | 12% (n=1647) | 9% (n=2180) | ✓ |
| Initial Blue | 9.3% | 10.75 | midfield | 21 | 12% (n=1181) | 15% (n=7035) | ✓ |
| Express Train ⚑ | 9.2% | 10.85 | led | 8 | 8% (n=699) | 15% (n=4651) | ✓ |
| Serenity Dream | 8.5% | 11.75 | midfield | 29 | 11% (n=7574) | 16% (n=3942) | ✓ |
| Massimo Blue | 8.4% | 11.91 | midfield | 14 | 10% (n=1607) | 13% (n=1880) | ✓ |
| Giorgio M | 8.3% | 11.98 | midfield | 35 | 8% (n=3199) | 10% (n=5343) | ✓ |
| Brazen Idol | 7.8% | 12.79 | held_up | 26 | 9% (n=1388) | 9% (n=1717) | ✓ |
| Diamond Dreamer | 6.5% | 15.48 | held_up | 40 | 8% (n=1119) | 12% (n=5291) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Express Train
layer2_hit coverage: **100%** (11/11). career_runs=0: 0.

### Newbury 21:00  —  Pump Technology Apprentice Handicap  [Flat, 5f, Good To Firm]

Field: 8 active  •  NR excluded (1): Life After Love  •  RF%: n/a (not in card schema)  •  probs renormalised over 8 (softmax, Σ=1.000)

| runner | model_prob | fair_price | run_style_proxy | career_runs | trainer_SR | jockey_SR | layer2_hit |
|--------|-----------:|-----------:|-----------------|------------:|-----------|-----------|:----------:|
| Over Spiced ⚑ | 16.0% | 6.24 | led | 33 | 8% (n=1662) | 13% (n=344) | ✓ |
| Artista | 14.9% | 6.71 | prominent | 13 | 13% (n=813) | 0% (n=6) | ✓ |
| Merrimack | 14.7% | 6.83 | prominent | 35 | 12% (n=3663) | 7% (n=46) | ✓ |
| Truly Glamorous | 14.1% | 7.11 | prominent | 7 | 13% (n=616) | 13% (n=155) | ✓ |
| Nifty | 12.8% | 7.83 | held_up | 9 | 14% (n=3478) | 11% (n=146) | ✓ |
| Havana Jag ⚑ | 10.8% | 9.29 | led | 9 | 8% (n=1120) | 10% (n=280) | ✓ |
| Just Jump | 10.7% | 9.31 | held_up | 5 | 11% (n=7574) | 20% (n=79) | ✓ |
| Faustus | 6.1% | 16.49 | prominent | 58 | 6% (n=460) | 16% (n=82) | ✓ |

**Predicted front-runner(s)** (run_style_proxy=led ⚑): Over Spiced, Havana Jag
layer2_hit coverage: **100%** (8/8). career_runs=0: 0.

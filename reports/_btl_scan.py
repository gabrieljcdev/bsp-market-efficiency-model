"""Back-to-lay scan (report-only) for 6 Sandown races, 3 Jul 2026.

Reuses the Stage-1 conditional logit (or, draw, lbs, age) to produce a MODEL fair
price for each runner (the ONLY price available -- the racecard carries no odds and
there is no exchange feed). Ranks the top-4 by model prob (shortest fair price =
'most backed' proxy), buckets each into the price-drift model's morning-price band,
and applies that band's historical drift distribution (median / p75) to project a
BSP and the back-to-lay P&L. Nothing here is a real market price. No bets.
"""
import os, sys, json, csv
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "models"))
import stage1_logit as s1

STAKE = 20.0
COMM = 0.02
CARD = "vendor/rpscrape/racecards/2026-07-03.json"
BANDS = json.load(open("reports/band_drift.json"))
EDGES = (1.0,1.5,2.0,2.5,3.0,4.0,5.0,6.0,8.0,10.0,15.0,20.0,30.0,50.0,float("inf"))
NB = len(EDGES)-1

# 6 Sandown races (drop the 5-runner 16:10 Coral Marathon).
PICK = ["13:50","14:25","15:00","15:35","16:42","17:15"]

def band_of(px):
    if not px or px <= 1.0: return -1
    for i in range(NB):
        if EDGES[i] <= px < EDGES[i+1]: return i
    return NB-1

# ---- 1. fit Stage-1 on the historical joined set, capture beta + z stats ----
races = s1.load_races()
imputed, stats = s1.build_matrix(races)   # stats[f] = (mu, sd) on training data
beta, nll = s1.fit(races)
gmean = {f: stats[f][0] for f in s1.FEATURES}   # training mean = global fallback

import math
def score_card_race(runners):
    """runners: list of dicts with raw or/draw/lbs/age. Returns model probs."""
    # race-mean impute (within this race), fallback to training global mean
    feats = {}
    for f in s1.FEATURES:
        present = [runners[i]["_raw"][f] for i in range(len(runners)) if runners[i]["_raw"][f] is not None]
        rmean = sum(present)/len(present) if present else gmean[f]
        feats[f] = [ (r["_raw"][f] if r["_raw"][f] is not None else rmean) for r in runners]
    us = []
    for i in range(len(runners)):
        u = 0.0
        for k,f in enumerate(s1.FEATURES):
            mu,sd = stats[f]
            z = (feats[f][i]-mu)/sd
            u += beta[k]*z
        us.append(u)
    m = max(us); ex = [math.exp(u-m) for u in us]; s = sum(ex)
    return [e/s for e in ex]

def fnum(x):
    try: return float(x)
    except (TypeError, ValueError): return None

card = json.load(open(CARD))
sandown = card["GB"]["Sandown"]

out = []
for off in PICK:
    c = sandown[off]
    active = [r for r in c["runners"] if not (r.get("non_runner") or r.get("reserve"))]
    runners = []
    for r in active:
        runners.append({"name": r["name"], "_raw": {
            "or": fnum(r.get("ofr")), "draw": fnum(r.get("draw")),
            "lbs": fnum(r.get("lbs")), "age": fnum(r.get("age"))}})
    probs = score_card_race(runners)
    ranked = sorted(range(len(runners)), key=lambda i: -probs[i])
    race = {"off": off, "race_name": c.get("race_name"), "dist": c.get("distance"),
            "going": c.get("going"), "field": len(active), "cands": []}
    for rank, i in enumerate(ranked[:4]):   # TOP 4 by model prob
        p = probs[i]; B = 1.0/p
        bi = band_of(B)
        bd = BANDS.get(str(bi))
        d_med = bd["med"]; d_p75 = bd["p75"]
        lay_med = B*(1+d_med); lay_p75 = B*(1+d_p75)
        def net(L):
            raw = STAKE*(B/L - 1.0)
            return raw*(1-COMM) if raw > 0 else raw
        race["cands"].append({
            "rank": rank+1, "horse": runners[i]["name"], "model_prob": p,
            "back_price": B, "band": bd["lab"], "band_i": bi,
            "d_med": d_med, "d_p75": d_p75, "bsp_med": lay_med, "bsp_p75": lay_p75,
            "breakeven_lay": B, "net_med": net(lay_med), "net_p75": net(lay_p75)})
    out.append(race)

json.dump(out, open("reports/btl_scan_results.json","w"), indent=2)

# ---- pretty print ----
print(f"beta (or,draw,lbs,age): {[round(b,3) for b in beta]}")
print(f"\n{'off':>6} {'horse':<20}{'rk':>3}{'backP':>7}{'band':>9}{'dMed':>7}{'dP75':>7}{'bspMed':>8}{'bspP75':>8}{'netMed':>8}{'netP75':>8}")
tot_med = tot_p75 = 0.0
for race in out:
    print(f"\n{race['off']}  {race['race_name'][:44]}  [{race['dist']}, {race['going']}, fld {race['field']}]")
    for cd in race["cands"]:
        print(f"{'':>6} {cd['horse'][:20]:<20}{cd['rank']:>3}{cd['back_price']:>7.2f}{cd['band']:>9}"
              f"{cd['d_med']:>+7.1%}{cd['d_p75']:>+7.1%}{cd['bsp_med']:>8.2f}{cd['bsp_p75']:>8.2f}"
              f"{cd['net_med']:>+8.2f}{cd['net_p75']:>+8.2f}")
        tot_med += cd['net_med']; tot_p75 += cd['net_p75']
n = sum(len(r['cands']) for r in out)
print(f"\nTOTAL over {n} candidate bets:  net@median {tot_med:+.2f}   net@p75 {tot_p75:+.2f}")
print(f"per-bet mean:  net@median {tot_med/n:+.3f}   net@p75 {tot_p75/n:+.3f}  (stake £{STAKE:.0f}, comm {COMM:.0%})")

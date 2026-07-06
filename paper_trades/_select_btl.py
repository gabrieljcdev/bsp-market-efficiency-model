"""Select ONE back-to-lay pick per race (6 total) from btl_scan_3jul_observed.md
top-4, strike = EX2, and write the forward paper-trade ledger.

SELECTION RULE (no improvised signals): rank each race's top-4 by expected net
P&L at band-MEDIAN drift (the only criterion with validated data); pick the best;
tiebreak within the same band by shorter price (better exit liquidity). Report
band, median & p75 expected P&L, and margin over the race's 2nd-best. Flag any
pick that is still negative-EV at the median. NOT a verdict -- an anecdote seed.
"""
import os, json
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAKE, COMM = 20.0, 0.02
STRIKE_TS = "2026-07-03T06:37+01:00 (BST)"
BANDS = json.load(open(os.path.join(_ROOT, "reports", "band_drift.json")))
EDGES = (1.0,1.5,2.0,2.5,3.0,4.0,5.0,6.0,8.0,10.0,15.0,20.0,30.0,50.0,float("inf"))
NB = len(EDGES)-1
def band_of(px):
    for i in range(NB):
        if EDGES[i] <= px < EDGES[i+1]: return i
    return NB-1
def net(strike, bsp):
    raw = STAKE*(strike/bsp - 1.0)
    return raw*(1-COMM) if raw > 0 else raw

# Top-4 per race with the STRIKE = EX2. (horse, ex2)
RACES = [
 {"course":"Sandown","user_off":"12:50","card_off":"13:50","desc":"5f Hcap",
  "market_id":"1.259648496","thin":False,"top4":[
    ("Comical Point",2.86),("Westport",2.90),("Havana Hurricane",4.70),("One And Gone",13.0)]},
 {"course":"Sandown","user_off":"13:25","card_off":"14:25","desc":"5f Listed",
  "market_id":"1.259648502","thin":False,"top4":[
    ("Ronson",4.70),("Miss Lizzy",5.10),("Bill The Bull",6.00),("A Bear Affair",6.20)]},
 {"course":"Doncaster","user_off":"13:00","card_off":"14:00","desc":"6f Nov Stks",
  "market_id":"1.259648089","thin":False,"top4":[
    ("Jumeirah Storm",3.05),("Launch Sequence",3.55),("Sultan Darius",9.60),("No More Pino",11.5)]},
 {"course":"Doncaster","user_off":"13:35","card_off":"14:35","desc":"1m Hcap",
  "market_id":"1.259648109","thin":True,"top4":[
    ("Al Muqdad",5.60),("Amidst The Chaos",6.60),("Tilani",5.90),("Yafaarr",7.40)]},
 {"course":"Newton Abbot","user_off":"13:10","card_off":"14:10","desc":"2m1f Mdn Hrd",
  "market_id":"1.259648047","thin":True,"top4":[
    ("Likewhatyousee",2.90),("Elated",4.40),("For Her Glory",4.30),("Getmyfriend",5.20)]},
 {"course":"Newton Abbot","user_off":"13:45","card_off":"14:45","desc":"2m3f Nov Hcap Hrd",
  "market_id":"1.259648053","thin":True,"top4":[
    ("Kittys Glance",2.74),("Ask Peter",5.00),("Backer Bilk",5.10),("Saucats",9.40)]},
]

picks = []
for R in RACES:
    scored = []
    for horse, ex2 in R["top4"]:
        bi = band_of(ex2); bd = BANDS[str(bi)]
        dM, d7 = bd["med"], bd["p75"]
        scored.append({"horse":horse,"ex2":ex2,"band_i":bi,"band":bd["lab"],
                       "d_med":dM,"d_p75":d7,
                       "bsp_med":ex2*(1+dM),"bsp_p75":ex2*(1+d7),
                       "net_med":net(ex2, ex2*(1+dM)),"net_p75":net(ex2, ex2*(1+d7))})
    # rank: best net_med desc, tiebreak shorter ex2 asc. Round net_med so that
    # same-band picks (mathematically equal EV) tie exactly and the shorter-price
    # tiebreak decides, rather than 1-ULP float noise picking the longer price.
    scored.sort(key=lambda s: (-round(s["net_med"], 6), s["ex2"]))
    best, second = scored[0], scored[1]
    margin = best["net_med"] - second["net_med"]
    if abs(margin) < 1e-9:
        margin = 0.0
    picks.append({
        "race": f"{R['course']} {R['user_off']} ({R['desc']})",
        "course": R["course"], "off_user": R["user_off"], "off_card": R["card_off"],
        "market_id": R["market_id"], "horse": best["horse"],
        "strike_ex2": best["ex2"], "timestamp": STRIKE_TS, "stake": STAKE,
        "band": best["band"], "d_med": best["d_med"], "d_p75": best["d_p75"],
        "predicted_bsp_median": round(best["bsp_med"], 4),
        "predicted_net_pnl_median": round(best["net_med"], 4),
        "predicted_net_pnl_p75": round(best["net_p75"], 4),
        "margin_over_2nd": round(margin, 4), "second_best": second["horse"],
        "negative_ev_at_median": best["net_med"] < -1e-9,
        "thin_market": R["thin"],
        "realised": None,   # filled by score_btl.py once actual BSPs land
    })

ledger = {
    "header": "6 picks is ANECDOTE, NOT evidence. This is the SEED of a forward CLV "
              "ledger, not a verdict. Band-median EV is the only validated criterion; "
              "the project's standing conclusion (price-drift PRICED) is unchanged.",
    "generated": STRIKE_TS,
    "trade_spec": {"stake_gbp": STAKE, "back_at": "EX2 (observed morning exchange price)",
                   "exit": "greened lay at BSP across the book", "commission": COMM},
    "band_drift_model": "reports/band_drift.json (discovery split, BSP/morning_wap-1, "
                        "morning-price-band median/p75)",
    "note_predicted_bsp": "predicted BSP = strike x (1 + band-median drift); a POPULATION "
                          "median with a fat right tail, not a per-horse forecast.",
    "picks": picks,
}
os.makedirs(os.path.join(_ROOT, "paper_trades"), exist_ok=True)
outp = os.path.join(_ROOT, "paper_trades", "btl_3jul.json")
json.dump(ledger, open(outp, "w"), indent=2)

# ---- print report ----
print("6 PICKS -- ANECDOTE, NOT EVIDENCE (forward CLV ledger seed; not a verdict)\n")
print(f"{'race':<34}{'pick':<17}{'strike':>7}{'band':>9}{'net@med':>9}{'net@p75':>9}{'margin':>8}  flag")
tm = tp = 0.0
for p in picks:
    flag = "NEGATIVE-EV@median" if p["negative_ev_at_median"] else "~breakeven@median"
    if p["thin_market"]: flag += " +THIN"
    print(f"{p['race'][:34]:<34}{p['horse'][:17]:<17}{p['strike_ex2']:>7.2f}{p['band']:>9}"
          f"{p['predicted_net_pnl_median']:>+9.2f}{p['predicted_net_pnl_p75']:>+9.2f}"
          f"{p['margin_over_2nd']:>+8.2f}  {flag}")
    tm += p["predicted_net_pnl_median"]; tp += p["predicted_net_pnl_p75"]
print(f"\n{'PORTFOLIO (6 x £20 = £120)':<58}{tm:>+9.2f}{tp:>+9.2f}")
print(f"wrote {os.path.relpath(outp, _ROOT)}")

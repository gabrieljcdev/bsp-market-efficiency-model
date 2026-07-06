"""Rank the top-4 in each of the 6 races as OUTRIGHT LAYS (report + paper log only).

Trade: lay to win £20 (backer's stake £20 against us), SETTLED OUTRIGHT on the race,
2% commission on our winnings. Lay strike = EX2 + 1 Betfair tick (the quotable lay),
with sensitivity at EX2 x 1.025 and x 1.05. Expected P&L uses the band-median
projected BSP to set the fair win probability (the only validated input).

STRUCTURAL CAVEAT (verbatim, printed at top): the lay price already charges the true
loss probability (9 tests, priced); this ranking finds the least-bad lay under drift
assumptions, not an edge.
"""
import os, json
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAKE, COMM = 20.0, 0.02
CAVEAT = ("the lay price already charges the true loss probability (9 tests, priced); "
          "this ranking finds the least-bad lay under drift assumptions, not an edge.")
BANDS = json.load(open(os.path.join(_ROOT, "reports", "band_drift.json")))
EDGES = (1.0,1.5,2.0,2.5,3.0,4.0,5.0,6.0,8.0,10.0,15.0,20.0,30.0,50.0,float("inf"))
NB = len(EDGES)-1
def band_of(px):
    for i in range(NB):
        if EDGES[i] <= px < EDGES[i+1]: return i
    return NB-1

def tick_up(p):
    """Next Betfair ladder price above p (1 tick up)."""
    for hi, inc in [(2,0.01),(3,0.02),(4,0.05),(6,0.10),(10,0.20),
                    (20,0.50),(30,1.0),(50,2.0),(100,5.0),(1000,10.0)]:
        if p < hi:
            return round(p + inc, 2)
    return round(p + 10, 2)

# top-4 EX2 (best-back, as supplied) + market ids.
RACES = [
 {"race":"Sandown 12:50 (5f Hcap)","market_id":"1.259648496","thin":False,"top4":[
   ("Comical Point",2.86),("Westport",2.90),("Havana Hurricane",4.70),("One And Gone",13.0)]},
 {"race":"Sandown 13:25 (5f Listed)","market_id":"1.259648502","thin":False,"top4":[
   ("Ronson",4.70),("Miss Lizzy",5.10),("Bill The Bull",6.00),("A Bear Affair",6.20)]},
 {"race":"Doncaster 13:00 (6f Nov Stks)","market_id":"1.259648089","thin":False,"top4":[
   ("Jumeirah Storm",3.05),("Launch Sequence",3.55),("Sultan Darius",9.60),("No More Pino",11.5)]},
 {"race":"Doncaster 13:35 (1m Hcap)","market_id":"1.259648109","thin":True,"top4":[
   ("Al Muqdad",5.60),("Amidst The Chaos",6.60),("Tilani",5.90),("Yafaarr",7.40)]},
 {"race":"Newton Abbot 13:10 (2m1f Mdn Hrd)","market_id":"1.259648047","thin":True,"top4":[
   ("Likewhatyousee",2.90),("Elated",4.40),("For Her Glory",4.30),("Getmyfriend",5.20)]},
 {"race":"Newton Abbot 13:45 (2m3f Nov Hcap Hrd)","market_id":"1.259648053","thin":True,"top4":[
   ("Kittys Glance",2.74),("Ask Peter",5.00),("Backer Bilk",5.10),("Saucats",9.40)]},
]

STRIKES = [("+1tick", None), ("x1.025", 1.025), ("x1.050", 1.05)]

def lay_ev(strike, proj_bsp):
    """Expected outright-settled lay P&L, win-prob from projected BSP.
    lose (horse doesn't win): +STAKE*(1-COMM); win: -STAKE*(strike-1)."""
    p = 1.0 / proj_bsp
    return (1 - p) * STAKE * (1 - COMM) - p * STAKE * (strike - 1.0)

out = []
for R in RACES:
    runners = []
    for horse, ex2 in R["top4"]:
        bi = band_of(ex2); bd = BANDS[str(bi)]
        d_med = bd["med"]
        proj_bsp = ex2 * (1 + d_med)
        s1 = tick_up(ex2)
        strikes = {"+1tick": s1, "x1.025": round(ex2*1.025, 4), "x1.050": round(ex2*1.05, 4)}
        evs = {k: lay_ev(v, proj_bsp) for k, v in strikes.items()}
        clvs = {k: 1 - v/proj_bsp for k, v in strikes.items()}   # layer CLV: >0 if strike<projBSP
        liability = STAKE * (s1 - 1.0)
        runners.append({"horse":horse,"ex2":ex2,"band":bd["lab"],"d_med":d_med,
                        "proj_bsp":proj_bsp,"strikes":strikes,"ev":evs,"clv":clvs,
                        "liability_1tick":liability})
    runners.sort(key=lambda r: -round(r["ev"]["+1tick"], 6))
    for i, r in enumerate(runners): r["rank"] = i+1
    out.append({**{k:R[k] for k in ("race","market_id","thin")}, "runners":runners})

# ---- paper log ----
log = {"header": "ANECDOTE, NOT evidence -- outright-lay ranking, forward log. " + CAVEAT,
       "structural_caveat_verbatim": CAVEAT,
       "trade": {"type":"outright lay, settled on race","win":"£20 x (1-2% comm) if horse loses",
                 "lose":"pay £20 x (strike-1) if horse wins","stake_backer_gbp":STAKE,"commission":COMM},
       "lay_strike": {"primary":"EX2 + 1 Betfair tick","sensitivity":["EX2 x 1.025","EX2 x 1.05"]},
       "projected_bsp":"EX2 x (1 + band-median drift), reports/band_drift.json (discovery)",
       "generated":"2026-07-03T07:24+01:00 (BST)","races":out}
json.dump(log, open(os.path.join(_ROOT,"paper_trades","btl_lay_3jul.json"),"w"), indent=2)

# ---- report ----
print("STRUCTURAL CAVEAT: " + CAVEAT + "\n")
print("Outright lays, win £20 (net 2%) if horse loses / pay £20x(strike-1) if it wins.")
print("Ranked by expected net P&L at lay strike = EX2 + 1 tick, vs band-median projected BSP.\n")
best_dies = 0
for R in out:
    thin = "  [THIN]" if R["thin"] else ""
    print(f"=== {R['race']}  mkt {R['market_id']}{thin} ===")
    print(f"  {'rk':>2} {'horse':<17}{'EX2':>6}{'band':>8}{'projBSP':>8}{'lay+1t':>7}"
          f"{'CLV+1t':>8}{'EV+1t':>7}{'EVx1.025':>9}{'EVx1.05':>9}  strike/verdict")
    for r in R["runners"]:
        e1,e2,e3 = r["ev"]["+1tick"], r["ev"]["x1.025"], r["ev"]["x1.050"]
        dies = e1 > 0 and e3 <= 0
        tag = ""
        if r["rank"] == 1:
            if e1 <= 0: tag = "BEST=least-bad (neg even @+1tick)"
            elif dies: tag = "BEST: +@1tick, DIES by x1.05 (trap)"
            else: tag = "BEST: survives x1.05"
            if r["rank"]==1 and dies: best_dies += 1
        print(f"  {r['rank']:>2} {r['horse'][:17]:<17}{r['ex2']:>6.2f}{r['band']:>8}"
              f"{r['proj_bsp']:>8.2f}{r['strikes']['+1tick']:>7.2f}{r['clv']['+1tick']:>+8.1%}"
              f"{e1:>+7.2f}{e2:>+9.2f}{e3:>+9.2f}  {tag}")
    print(f"  (all strikes assume EX2 supplied = best-back; lay struck 1 tick above, "
          f"liability@+1tick £{R['runners'][0]['liability_1tick']:.0f} on the top rank)\n")

print(f"STRIKEABILITY TRAP: {best_dies}/6 race-best lays show +EV at EX2+1tick that DIES by x1.05.")
print("wrote paper_trades/btl_lay_3jul.json")

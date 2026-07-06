"""Back-to-lay scan on OBSERVED prices (report-only), 3 Jul 2026.

No model fair prices. Back strike = observed exchange price EX1; greened lay exit =
BSP projected from the SAME discovery band-drift model as btl_scan_3jul.md. SB/EX2
sportsbook cross-check. Racecard used ONLY to canon_horse-match the supplied names
to declared runners and confirm the NRs. Stake £20, commission 2%. No bet.

BST+1h: user race times are the card off-time minus 1h (documented gotcha); the
mapping below pairs each supplied race to its card off-time and the prices are
~06:30 MORNING captures, which the morning->BSP drift model fits cleanly.
"""
import os, sys, json
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "features"))
import history_join as hj

STAKE, COMM = 20.0, 0.02
BANDS = json.load(open(os.path.join(_ROOT, "reports", "band_drift.json")))
EDGES = (1.0,1.5,2.0,2.5,3.0,4.0,5.0,6.0,8.0,10.0,15.0,20.0,30.0,50.0,float("inf"))
NB = len(EDGES)-1
def band_of(px):
    if not px or px <= 1.0: return -1
    for i in range(NB):
        if EDGES[i] <= px < EDGES[i+1]: return i
    return NB-1

# Observed prices exactly as supplied. card_off = supplied time + 1h (BST gotcha).
# thin: matched <~£1.5k at capture -> BSP noisy. mkt_id = Betfair market id supplied.
RACES = [
 {"course":"Sandown","user_off":"12:50","card_off":"13:50","desc":"5f Hcap",
  "mkt_id":"1.259648496","nr":[],"thin":False,"runners":[
    ("Comical Point",2.72,2.86,2.4),("Westport",3.25,2.9,2.88),
    ("Havana Hurricane",4.7,4.7,4.0),("One And Gone",13.0,13.0,11.0)]},
 {"course":"Sandown","user_off":"13:25","card_off":"14:25","desc":"5f Listed",
  "mkt_id":"1.259648502","nr":["Divine Whisper"],"thin":False,"runners":[
    ("Ronson",4.6,4.7,3.2),("Miss Lizzy",5.1,5.1,5.0),
    ("Bill The Bull",6.0,6.0,5.0),("A Bear Affair",6.2,6.2,5.5)]},
 {"course":"Doncaster","user_off":"13:00","card_off":"14:00","desc":"6f Nov Stks",
  "mkt_id":"1.259648089","nr":["Give Hand"],"thin":False,"runners":[
    ("Jumeirah Storm",3.05,3.05,None),("Launch Sequence",3.55,3.55,2.88),
    ("Sultan Darius",10.5,9.6,9.0),("No More Pino",11.0,11.5,9.0)]},
 {"course":"Doncaster","user_off":"13:35","card_off":"14:35","desc":"1m Hcap",
  "mkt_id":"1.259648109","nr":[],"thin":True,"runners":[
    ("Al Muqdad",5.6,5.6,4.5),("Amidst The Chaos",5.9,6.6,5.0),
    ("Tilani",5.9,5.9,4.33),("Yafaarr",7.2,7.4,7.0)]},
 {"course":"Newton Abbot","user_off":"13:10","card_off":"14:10","desc":"2m1f Mdn Hrd",
  "mkt_id":"1.259648047","nr":[],"thin":True,"runners":[
    ("Likewhatyousee",2.86,2.9,2.8),("Elated",4.4,4.4,4.33),
    ("For Her Glory",4.7,4.3,3.2),("Getmyfriend",4.9,5.2,3.2)]},
 {"course":"Newton Abbot","user_off":"13:45","card_off":"14:45","desc":"2m3f Nov Hcap Hrd",
  "mkt_id":"1.259648053","nr":["Katzoff"],"thin":True,"runners":[
    ("Kittys Glance",2.76,2.74,2.5),("Ask Peter",4.8,5.0,3.25),
    ("Backer Bilk",5.0,5.1,4.5),("Saucats",8.4,9.4,7.0)]},
]

# ---- racecard: canon_horse name-match + NR confirmation ----
card = json.load(open(os.path.join(_ROOT,"vendor","rpscrape","racecards","2026-07-03.json")))
def card_race(course, off):
    return card.get("GB",{}).get(course,{}).get(off)
def active_canon(c):
    out={}
    for r in c.get("runners",[]):
        base,_ = hj.canon_horse(r.get("name"))
        out[base] = {"name":r.get("name"),"nr":bool(r.get("non_runner") or r.get("reserve"))}
    return out

def net(B,L):
    raw = STAKE*(B/L-1.0)
    return raw*(1-COMM) if raw>0 else raw

results=[]
for R in RACES:
    c = card_race(R["course"], R["card_off"])
    canon = active_canon(c) if c else {}
    row = {**{k:R[k] for k in ("course","user_off","card_off","desc","mkt_id","thin","nr")},
           "card_found": bool(c), "field_active": sum(1 for v in canon.values() if not v["nr"]),
           "match":[], "cands":[]}
    # name matching
    for name,ex1,ex2,sb in R["runners"]:
        base,_ = hj.canon_horse(name)
        m = canon.get(base)
        row["match"].append({"name":name,"matched":bool(m and not m["nr"]),
                             "card_name": (m["name"] if m else None)})
    # NR confirmation
    row["nr_confirmed"] = {nr: (hj.canon_horse(nr)[0] in canon and canon[hj.canon_horse(nr)[0]]["nr"]) for nr in R["nr"]}
    # ---- BTL on EX1 + SB/EX2 cross-check ----
    inv_sb = {n:1.0/sb for (n,e1,e2,sb) in R["runners"] if sb}
    inv_ex2= {n:1.0/e2 for (n,e1,e2,sb) in R["runners"] if sb}   # same subset for comparability
    sum_sb, sum_ex2 = sum(inv_sb.values()), sum(inv_ex2.values())
    for name,ex1,ex2,sb in R["runners"]:
        B=ex1; bi=band_of(B); bd=BANDS[str(bi)]
        dM,d7 = bd["med"], bd["p75"]
        Lm,L7 = B*(1+dM), B*(1+d7)
        p_sb = (inv_sb[name]/sum_sb) if sb else None
        p_ex2= (inv_ex2[name]/sum_ex2) if sb else None
        arb = (sb is not None) and (sb > ex2)   # RAW SB odds > EX2 -> back SB / lay EX2
        row["cands"].append({
            "horse":name,"ex1":ex1,"ex2":ex2,"sb":sb,"band":bd["lab"],
            "d_med":dM,"d_p75":d7,"bsp_med":Lm,"bsp_p75":L7,"breakeven_lay":B,
            "net_med":net(B,Lm),"net_p75":net(B,L7),
            "p_sb":p_sb,"p_ex2":p_ex2,
            "div_pp":((p_sb-p_ex2)*100 if p_sb is not None else None),
            "arb":arb})
    row["book_sum_sb"]=sum_sb; row["book_sum_ex2"]=sum_ex2
    results.append(row)

json.dump(results, open(os.path.join(_ROOT,"reports","btl_observed_results.json"),"w"), indent=2)

# ---- print ----
tot_m=tot_7=0.0; n=0
for R in results:
    thin = "  [THIN MKT]" if R["thin"] else ""
    print(f"\n=== {R['course']} {R['user_off']} (card {R['card_off']}) {R['desc']}  mkt {R['mkt_id']}{thin} ===")
    print(f"    card matched: {R['card_found']}  active field: {R['field_active']}  "
          f"NR confirmed: {R['nr_confirmed']}")
    bad=[m for m in R['match'] if not m['matched']]
    if bad: print("    !! UNMATCHED:", [m['name'] for m in bad])
    print(f"    {'horse':<17}{'EX1':>6}{'EX2':>6}{'SB':>6}{'band':>8}{'dMed':>7}{'BSPmd':>7}{'BSPp75':>8}"
          f"{'netMd':>7}{'net75':>7}{'pSB':>7}{'pEX2':>7}{'div':>7}{'arb':>5}")
    for cd in R["cands"]:
        sb = f"{cd['sb']:.2f}" if cd['sb'] else " n/a"
        psb = f"{cd['p_sb']:.1%}" if cd['p_sb'] is not None else "  -"
        pex = f"{cd['p_ex2']:.1%}" if cd['p_ex2'] is not None else "  -"
        dv  = f"{cd['div_pp']:+.1f}" if cd['div_pp'] is not None else "  -"
        print(f"    {cd['horse'][:17]:<17}{cd['ex1']:>6.2f}{cd['ex2']:>6.2f}{sb:>6}{cd['band']:>8}"
              f"{cd['d_med']:>+7.1%}{cd['bsp_med']:>7.2f}{cd['bsp_p75']:>8.2f}"
              f"{cd['net_med']:>+7.2f}{cd['net_p75']:>+7.2f}{psb:>7}{pex:>7}{dv:>7}{('YES' if cd['arb'] else '.'):>5}")
        tot_m+=cd['net_med']; tot_7+=cd['net_p75']; n+=1
    print(f"    partial-book overround (top-4 shown): SB {R['book_sum_sb']:.3f}  EX2 {R['book_sum_ex2']:.3f}")

print(f"\nTOTAL {n} bets:  net@median {tot_m:+.2f}   net@p75 {tot_7:+.2f}")
print(f"per-bet:        net@median {tot_m/n:+.3f}   net@p75 {tot_7/n:+.3f}   (stake £{STAKE:.0f}, comm {COMM:.0%})")

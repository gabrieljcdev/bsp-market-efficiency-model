import csv, json
import numpy as np
CUT = "2023-12-31"
EDGES = (1.0,1.5,2.0,2.5,3.0,4.0,5.0,6.0,8.0,10.0,15.0,20.0,30.0,50.0,float("inf"))
NB = len(EDGES)-1
lab = ["1.0-1.5","1.5-2.0","2.0-2.5","2.5-3.0","3.0-4.0","4.0-5.0","5.0-6.0",
       "6.0-8.0","8-10","10-15","15-20","20-30","30-50","50+"]

def band(px):
    if not px or px <= 1.0:
        return -1
    for i in range(NB):
        if EDGES[i] <= px < EDGES[i+1]:
            return i
    return NB-1

def fnum(x):
    try:
        v = float(x)
        return v if v == v else None
    except Exception:
        return None

disc = [[] for _ in range(NB)]
full = [[] for _ in range(NB)]
with open("data/joined/joined_gb_2018_2026_feat.csv", newline="") as f:
    for r in csv.DictReader(f):
        m = fnum(r.get("morning_wap")); b = fnum(r.get("bsp"))
        if not (m and b and m > 1.0 and b > 1.0):
            continue
        d = b/m - 1.0
        bi = band(m)
        if bi < 0:
            continue
        full[bi].append(d)
        if r.get("date", "") <= CUT:
            disc[bi].append(d)

hdr = "{:>9}{:>8}{:>8}{:>8}{:>8}{:>8}{:>8}{:>9}{:>8}{:>8}".format(
    "band","n_disc","med","p25","p75","mean","pctNeg","n_full","med_f","p75_f")
print(hdr)
out = {}
for i in range(NB):
    dd = np.array(disc[i]); ff = np.array(full[i])
    if len(dd) >= 50:
        med = float(np.median(dd)); p75 = float(np.percentile(dd,75))
        p25 = float(np.percentile(dd,25)); mean = float(dd.mean())
        pneg = float((dd < 0).mean())
        medf = float(np.median(ff)); p75f = float(np.percentile(ff,75))
        out[str(i)] = {"lab":lab[i],"n":len(dd),"med":med,"p25":p25,"p75":p75,
                       "mean":mean,"pctNeg":pneg,"med_full":medf,"p75_full":p75f,
                       "n_full":len(ff)}
        print("{:>9}{:>8}{:>+8.3f}{:>+8.3f}{:>+8.3f}{:>+8.3f}{:>7.1%}{:>9}{:>+8.3f}{:>+8.3f}".format(
            lab[i],len(dd),med,p25,p75,mean,pneg,len(ff),medf,p75f))
    else:
        print("{:>9}{:>8}  thin".format(lab[i], len(dd)))
json.dump(out, open("reports/band_drift.json","w"), indent=2)
print("wrote reports/band_drift.json")

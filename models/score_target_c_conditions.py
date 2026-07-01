#!/usr/bin/env python3
"""score_target_c_conditions.py -- Target C EXTENSION: when does the 2nd-favourite's
ranking of the non-favourites hold, and when does it fail?

Reuses Target C's setup verbatim (models/score_target_c.py): the non-favourite
sub-race population, the same leakage-clean feature CSV, the same discovery/holdout
split @2023-12-31, and the same 2nd-favourite null (the lowest-BSP runner among the
non-favs = the market's single best guess at best-of-rest).

NEW QUESTION -- a per-SUB-RACE binary label:
    Y = 1  iff the 2nd-favourite IS the best-of-rest (it finished best of the
           non-favourite sub-group), else 0.
Its overall holdout rate is Target C's 32.60%. Do PRE-RACE conditions -- draw,
going, field size, distance, class, and course geometry (handedness / shape) --
predict WHEN the 2nd-fav is more/less reliable than that flat 32.60%?

THE HARDENED BAR (same spirit as Target C / the main verdict):
  A raw correctness-rate wobble across conditions is NOT enough -- most of it is
  already in the PRICE that made this runner the 2nd-favourite. The honest test is
  whether knowing the condition improves CALIBRATION BEYOND THE MARKET'S OWN
  PROBABILITY for that runner. So the deciding comparison, on holdout, is:
      M2  : logistic  Y ~ market_logit + conditions
   vs B1c : logistic  Y ~ market_logit            (market prob merely recalibrated)
  Conditions rule in only if M2 beats B1c on Brier by a MEANINGFUL margin
  (> BRIER_EPS), corroborated on discovery. Beating the flat uniform base rate, or
  beating the raw (un-recalibrated) market prob, does NOT count -- that is just
  fixing the market's mild miscalibration, not a conditioning edge.

ANCHOR / POWER CHECK: rpr of the 2nd-favourite is POST-RACE (leakage). A canary
model (market + rpr) MUST beat B1c by a lot -- proving the test can SEE a real
conditioning signal when one exists -- while the pre-race conditions do not.

Writes models/target_c_conditions_results.json. Touches no pipeline code.
"""
import os
import sys
import csv
import json
import math
from collections import defaultdict

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backtest"))
sys.path.insert(0, os.path.join(_ROOT, "features"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clv  # noqa: E402
import course_geometry as cg  # noqa: E402
from score_target_c import fnum, parse_pos, SPLIT_CUTOFF, BRIER_EPS  # noqa: E402

FEAT_CSV = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_feat.csv")
OUT_JSON = os.path.join(_ROOT, "models", "target_c_conditions_results.json")
THIN_HOLDOUT_N = 2000

# Coarse going buckets (turf moisture ordinal + the AW standards), one-hot below.
GOING_LEVELS = ["Firm", "Good To Firm", "Good", "Good To Soft", "Soft", "Heavy",
                "Standard To Fast", "Standard", "Standard To Slow", "Slow"]


def going_key(g):
    g = (g or "").strip()
    return g if g in GOING_LEVELS else "Other"


def class_num(c):
    s = (c or "").replace("Class", "").strip()
    return int(s) if s.isdigit() else None


_NUM_RE = __import__("re").compile(r"-?\d+(?:\.\d+)?")


def dist_num(x):
    """Tolerant distance parse: `dist_f` carries an 'f' suffix (e.g. '8f', '5.5f'),
    so plain float() fails on every row -- pull the leading numeric token."""
    v = fnum(x)
    if v is not None:
        return v
    mo = _NUM_RE.search("" if x is None else str(x))
    return float(mo.group()) if mo else None


# --------------------------------------------------------------------------- #
# 1. Rebuild the non-fav sub-races, this time carrying the 2nd-fav + conditions #
# --------------------------------------------------------------------------- #
def build():
    geo = cg.load_geometry()
    keep = ["date", "course", "off", "horse", "pos", "bsp", "rpr", "draw",
            "ran", "dist_f", "class", "going"]
    races = defaultdict(list)
    with open(FEAT_CSV, newline="") as f:
        for r in csv.DictReader(f):
            races[f"{r['date']}|{r['course']}|{r['off']}"].append(
                {k: r.get(k) for k in keep})

    rows = []   # one dict per sub-race (the 2nd-favourite + its context + Y)
    for rid, rs in races.items():
        priced = [r for r in rs if (fnum(r["bsp"]) or 0) > 1.0]
        if len(priced) < 3:
            continue
        fav = min(priced, key=lambda r: fnum(r["bsp"]))
        nonfav = [r for r in priced if r is not fav]
        if len(nonfav) < 2:
            continue
        finishers = [r for r in nonfav if parse_pos(r["pos"]) is not None]
        if not finishers:
            continue
        best = min(finishers, key=lambda r: (parse_pos(r["pos"]), fnum(r["bsp"])))
        secfav = min(nonfav, key=lambda r: fnum(r["bsp"]))     # 2nd-fav = min-BSP non-fav
        inv = sum(1.0 / fnum(r["bsp"]) for r in nonfav)
        market_p = (1.0 / fnum(secfav["bsp"])) / inv           # its implied P(best-of-rest)

        fs = fnum(secfav["ran"]) or float(len(priced))
        draw = fnum(secfav["draw"])
        geo_row = geo.get(secfav["course"], {})
        rows.append({
            "date": secfav["date"],
            "Y": 1.0 if secfav is best else 0.0,
            "market_p": market_p,
            "n_nonfav": float(len(nonfav)),
            "field_size": fs,
            "dist_f": dist_num(secfav["dist_f"]),
            "class_num": class_num(secfav["class"]),
            "draw_norm": (draw / fs) if (draw is not None and fs) else None,
            "going": going_key(secfav["going"]),
            "handed": (geo_row.get("handedness") or "Other"),
            "shape": (geo_row.get("course_shape") or "Other"),
            "rpr": fnum(secfav["rpr"]),                          # POST-RACE canary
        })
    return rows


# --------------------------------------------------------------------------- #
# 2. Design matrix.                                                            #
# --------------------------------------------------------------------------- #
NUMERIC = ["n_nonfav", "field_size", "dist_f", "class_num", "draw_norm"]


def design(rows):
    disc = [r for r in rows if r["date"] <= SPLIT_CUTOFF]

    # numeric impute (discovery median) + z-score (discovery stats)
    stats = {}
    for c in NUMERIC:
        vals = np.array([r[c] for r in disc if r[c] is not None], dtype=float)
        if vals.size == 0:
            raise ValueError(f"numeric condition {c!r} has ZERO valid discovery "
                             "values -- check its parser/column name (leakage of a "
                             "None column into the model would go silently NaN).")
        med, mu, sd = float(np.median(vals)), float(vals.mean()), float(vals.std())
        stats[c] = (med, mu, sd if sd > 0 else 1.0)

    going_cats = GOING_LEVELS + ["Other"]
    hand_cats = ["Left", "Right", "Figure-of-eight", "Other"]
    shape_cats = ["Oval", "Horseshoe", "Triangular", "Pear", "Figure-of-eight",
                  "Round", "Other"]
    cat_cols = ([f"going={g}" for g in going_cats[1:]]      # drop first = reference
                + [f"handed={h}" for h in hand_cats[1:]]
                + [f"shape={s}" for s in shape_cats[1:]])

    def numrow(r):
        out = []
        for c in NUMERIC:
            med, mu, sd = stats[c]
            v = r[c] if r[c] is not None else med
            out.append((v - mu) / sd)
        return out

    def catrow(r):
        out = []
        for g in going_cats[1:]:
            out.append(1.0 if r["going"] == g else 0.0)
        for h in hand_cats[1:]:
            out.append(1.0 if r["handed"] == h else 0.0)
        for s in shape_cats[1:]:
            out.append(1.0 if r["shape"] == s else 0.0)
        return out

    y = np.array([r["Y"] for r in rows])
    mlogit = np.array([math.log(min(max(r["market_p"], 1e-9), 1 - 1e-9)
                                / (1 - min(max(r["market_p"], 1e-9), 1 - 1e-9)))
                       for r in rows])
    Xcond = np.array([numrow(r) + catrow(r) for r in rows])
    rpr_med = float(np.median([r["rpr"] for r in disc if r["rpr"] is not None]))
    rpr = np.array([(r["rpr"] if r["rpr"] is not None else rpr_med) for r in rows])
    rpr = (rpr - rpr.mean()) / (rpr.std() or 1.0)
    is_disc = np.array([r["date"] <= SPLIT_CUTOFF for r in rows], dtype=bool)
    feat_names = NUMERIC + cat_cols
    return y, mlogit, Xcond, rpr, is_disc, feat_names


# --------------------------------------------------------------------------- #
# 3. L2 logistic regression (numpy, with intercept).                          #
# --------------------------------------------------------------------------- #
def fit_logit(X, y, l2=1.0, iters=400):
    Xb = np.column_stack([np.ones(len(y)), X])
    w = np.zeros(Xb.shape[1])
    lr = 0.5

    def loss_grad(w):
        z = Xb @ w
        p = 1.0 / (1.0 + np.exp(-z))
        eps = 1e-12
        ll = -(y * np.log(p + eps) + (1 - y) * np.log(1 - p + eps)).mean()
        reg = l2 * (w[1:] @ w[1:]) / len(y)
        g = Xb.T @ (p - y) / len(y)
        g[1:] += 2 * l2 * w[1:] / len(y)
        return ll + reg, g

    val, g = loss_grad(w)
    for _ in range(iters):
        trial = w - lr * g
        v2, g2 = loss_grad(trial)
        if v2 < val:
            w, val, g, lr = trial, v2, g2, lr * 1.1
        else:
            lr *= 0.5
            if lr < 1e-9:
                break
    return w


def predict(w, X):
    Xb = np.column_stack([np.ones(len(X)), X])
    return 1.0 / (1.0 + np.exp(-(Xb @ w)))


def brier(p, y):
    return float(((p - y) ** 2).mean())


def logloss(p, y):
    p = np.clip(p, 1e-12, 1 - 1e-12)
    return float(-(y * np.log(p) + (1 - y) * np.log(1 - p)).mean())


# --------------------------------------------------------------------------- #
# 4. Subset probe: does any condition bin sit STABLY off the 32.60% baseline?  #
# --------------------------------------------------------------------------- #
def _rate_se(y):
    n = len(y)
    p = float(y.mean()) if n else float("nan")
    se = math.sqrt(p * (1 - p) / n) if n else float("nan")
    return p, se, n


def subset_probe(rows, is_disc):
    """For a few interpretable conditions, the 2nd-fav correctness rate per bin on
    discovery vs holdout -- a real conditioning subset must be stable OOS and its
    deviation from the base rate must clear ~2 SE."""
    y = np.array([r["Y"] for r in rows])
    hold = ~is_disc
    base_h, base_se, base_n = _rate_se(y[hold])

    def by(keyfn, label):
        buckets = defaultdict(lambda: [[], []])   # key -> [disc_Y, hold_Y]
        for r, d in zip(rows, is_disc):
            buckets[keyfn(r)][0 if d else 1].append(r["Y"])
        out = []
        for k in sorted(buckets, key=lambda x: (str(type(x)), x)):
            dY = np.array(buckets[k][0]); hY = np.array(buckets[k][1])
            if len(dY) < 200 or len(hY) < 200:
                continue
            dp, _, dn = _rate_se(dY)
            hp, hse, hn = _rate_se(hY)
            out.append({"bin": k, "disc_rate": dp, "disc_n": dn,
                        "hold_rate": hp, "hold_n": hn, "hold_se": hse,
                        "dev_from_base": hp - base_h,
                        "dev_sigma": (hp - base_h) / hse if hse else None})
        return {"label": label, "bins": out}

    probes = [
        by(lambda r: int(r["n_nonfav"]) if r["n_nonfav"] <= 8 else 9, "n_nonfav (9=9+)"),
        by(lambda r: r["going"], "going"),
        by(lambda r: r["handed"], "handedness"),
        by(lambda r: (class_num_bucket(r["class_num"])), "class"),
        by(lambda r: draw_bucket(r["draw_norm"]), "draw_norm (thirds)"),
    ]
    return {"base_rate_holdout": base_h, "base_se": base_se, "base_n": base_n,
            "probes": probes}


def class_num_bucket(c):
    if c is None:
        return "NA"
    return f"C{c}"


def draw_bucket(d):
    if d is None:
        return "NA"
    if d <= 1 / 3:
        return "low"
    if d <= 2 / 3:
        return "mid"
    return "high"


# --------------------------------------------------------------------------- #
# 5. Verdict.                                                                  #
# --------------------------------------------------------------------------- #
def verdict(res):
    hn = res["holdout"]["n"]
    d = res["discovery"]
    h = res["holdout"]
    # meaningful conditioning edge = M2 (market+conditions) beats B1c (market recal.)
    h_edge = h["brier_market_recal"] - h["brier_market_cond"]
    d_edge = d["brier_market_recal"] - d["brier_market_cond"]
    canary = h["brier_market_recal"] - h["brier_market_rpr"]

    if hn < THIN_HOLDOUT_N:
        return "thin", f"holdout n={hn:,} < {THIN_HOLDOUT_N:,}."
    if not (canary > BRIER_EPS):
        return "inconclusive", (
            f"POWER CHECK FAILED: even the post-race rpr canary does not beat the "
            f"recalibrated market on Brier ({canary:+.5f}) -- the test cannot see a "
            f"conditioning signal, so a null result is uninformative.")
    if h_edge > BRIER_EPS and d_edge > BRIER_EPS:
        return "ruled-in", (
            f"conditions beat the recalibrated market prob on holdout Brier by "
            f"{h_edge:+.5f} (> {BRIER_EPS:g}), corroborated on discovery ({d_edge:+.5f}) "
            f"-- a real conditioning edge beyond what the price already encodes "
            f"(canary rpr margin {canary:+.5f} confirms power).")
    return "priced", (
        f"conditions do NOT beat the recalibrated market probability on holdout Brier "
        f"(margin {h_edge:+.5f} <= {BRIER_EPS:g}); the post-race rpr canary DOES "
        f"({canary:+.5f}), so the test has power -- the conditioning that predicts when "
        f"the 2nd-fav is right is ALREADY in the price that made it the 2nd-fav.")


# --------------------------------------------------------------------------- #
# Main.                                                                        #
# --------------------------------------------------------------------------- #
def main():
    print("Rebuilding non-fav sub-races + 2nd-favourite correctness label ...")
    rows = build()
    y, mlogit, Xcond, rpr, is_disc, feat_names = design(rows)
    di, ho = is_disc, ~is_disc
    nd, nh = int(di.sum()), int(ho.sum())
    print(f"  sub-races: {len(rows):,}  (discovery {nd:,} | holdout {nh:,})")
    print(f"  2nd-fav correctness: discovery {y[di].mean():.4%} | holdout {y[ho].mean():.4%}")
    mkt_disc = float(np.mean([r["market_p"] for r, dd in zip(rows, di) if dd]))
    print(f"  mean market_p (2nd-fav implied), discovery: {mkt_disc:.4%}")

    M = mlogit.reshape(-1, 1)
    Xmc = np.column_stack([mlogit, Xcond])
    Xmr = np.column_stack([mlogit, rpr.reshape(-1, 1)])

    # fit all models on DISCOVERY only
    base_rate = float(y[di].mean())
    w_b1c = fit_logit(M[di], y[di])                 # market recalibrated
    w_cond = fit_logit(Xcond[di], y[di])            # conditions only (no market)
    w_mc = fit_logit(Xmc[di], y[di])                # market + conditions
    w_mr = fit_logit(Xmr[di], y[di])                # market + rpr (canary)

    def block(mask):
        raw_market = np.array([r["market_p"] for r in rows])[mask]
        yy = y[mask]
        return {
            "n": int(mask.sum()),
            "rate_2ndfav_correct": float(yy.mean()),
            "brier_uniform": brier(np.full(mask.sum(), base_rate), yy),
            "brier_market_raw": brier(raw_market, yy),
            "brier_market_recal": brier(predict(w_b1c, M[mask]), yy),
            "brier_cond_only": brier(predict(w_cond, Xcond[mask]), yy),
            "brier_market_cond": brier(predict(w_mc, Xmc[mask]), yy),
            "brier_market_rpr": brier(predict(w_mr, Xmr[mask]), yy),
            "logloss_market_recal": logloss(predict(w_b1c, M[mask]), yy),
            "logloss_market_cond": logloss(predict(w_mc, Xmc[mask]), yy),
            "logloss_market_rpr": logloss(predict(w_mr, Xmr[mask]), yy),
        }

    res = {
        "target": "C_ext_2ndfav_conditional_reliability",
        "split_cutoff": SPLIT_CUTOFF,
        "n_subraces": len(rows),
        "base_rate_discovery": base_rate,
        "conditions": feat_names,
        "discovery": block(di),
        "holdout": block(ho),
        "cond_coefficients": dict(zip(feat_names, [float(v) for v in w_mc[1 + 1:]])),
        "subset_probe": subset_probe(rows, is_disc),
    }
    vd, reason = verdict(res)
    res["verdict"], res["verdict_reason"] = vd, reason
    with open(OUT_JSON, "w") as f:
        json.dump(res, f, indent=2, default=float)

    _report(res)
    print(f"\nwrote {os.path.relpath(OUT_JSON, _ROOT)}")


def _report(res):
    d, h = res["discovery"], res["holdout"]
    p5 = lambda x: f"{x:.5f}"
    print("\n" + "=" * 74)
    print("TARGET C EXT -- is the 2nd-favourite's ranking conditionally reliable?")
    print("=" * 74)
    print(f"{'':<34}{'discovery':>18}{'holdout':>18}")
    print(f"{'2nd-fav correct rate':<34}{d['rate_2ndfav_correct']:>18.4%}"
          f"{h['rate_2ndfav_correct']:>18.4%}")
    print("\n-- Brier (lower better); GATE = market+cond vs market-recal --")
    for k, lab in [("brier_uniform", "uniform base-rate"),
                   ("brier_market_raw", "market raw (2nd-fav implied)"),
                   ("brier_market_recal", "market recalibrated  [B1c]"),
                   ("brier_cond_only", "conditions only (no market)"),
                   ("brier_market_cond", "market + conditions  [M2]"),
                   ("brier_market_rpr", "market + rpr (POST-RACE canary)")]:
        print(f"  {lab:<32}{p5(d[k]):>18}{p5(h[k]):>18}")
    he = h["brier_market_recal"] - h["brier_market_cond"]
    de = d["brier_market_recal"] - d["brier_market_cond"]
    can = h["brier_market_recal"] - h["brier_market_rpr"]
    print(f"\n  M2 vs B1c margin (cond beyond price): disc {de:+.5f} | holdout {he:+.5f}"
          f"   (>1e-4 = edge)")
    print(f"  canary rpr vs B1c margin (power check): holdout {can:+.5f}   (must be >1e-4)")

    sp = res["subset_probe"]
    print(f"\n-- subset probe (holdout base rate {sp['base_rate_holdout']:.4%} "
          f"+/-{sp['base_se']:.4%}); deviation in SE units --")
    for pr in sp["probes"]:
        print(f"  [{pr['label']}]")
        for b in pr["bins"]:
            ds = (f"{b['dev_sigma']:+.1f}sd" if b["dev_sigma"] is not None else "  -- ")
            print(f"    {str(b['bin']):<10} disc {b['disc_rate']:>7.2%} "
                  f"(n{b['disc_n']:>6,})  hold {b['hold_rate']:>7.2%} "
                  f"(n{b['hold_n']:>6,})  {ds}")
    print("\n" + "=" * 74)
    print(f"VERDICT: {res['verdict'].upper()}")
    print(res["verdict_reason"])
    print("=" * 74)


if __name__ == "__main__":
    main()

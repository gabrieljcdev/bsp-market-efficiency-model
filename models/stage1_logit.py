"""
stage1_logit.py -- Stage-1 fundamental win-probability model.

A CONDITIONAL LOGIT (McFadden's discrete-choice model), grouped by race:
each race is one "choice set" of runners, exactly one of which won. The model
learns weights `beta` on pre-race runner features so that, within each race,
    utility_i = beta . x_i
    P(win_i)  = softmax over the race = exp(u_i) / sum_j exp(u_j)
and the per-race probabilities sum to 1.0 by construction.

Implemented from scratch in pure Python (no numpy/sklearn) so every step is
visible and runs anywhere. The maths is standard softmax cross-entropy:
    negative log-likelihood  NLL = -sum_races log P(actual winner)
    gradient wrt beta_k      = sum_runners (p_i - y_i) * x_ik   (+ L2)
fit by gradient descent with a backtracking step.

LEAKAGE GUARD (the cardinal rule)
---------------------------------
Only pre-race, runner-varying features are allowed. Two findings drive this:
  * `rpr` in our results-sourced data is the POST-RACE Racing Post Rating
    (the highest-rpr horse wins 72.9% of races -- impossible for a forecast),
    so it is LEAKAGE and excluded. We use `or` (Official Rating, the handicap
    mark carried INTO the race -- highest-or wins 23%, a genuine pre-race signal).
  * In a conditional logit, features constant within a race (going, class,
    dist, type) cancel in the within-race softmax, so they are not identified
    and are dropped. The real inputs are runner-varying: or, draw, lbs, age.
An explicit assertion hard-fails if any forbidden column reaches the matrix.
"""
import os
import csv
import math
import random
from collections import defaultdict

random.seed(42)  # reproducibility (init is deterministic, but pin it anyway)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOINED = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026.csv")
OUT = os.path.join(_ROOT, "models", "stage1_scored.csv")

# Runner-varying pre-race features actually fed to the model.
FEATURES = ["or", "draw", "lbs", "age"]

# Allowed-feature whitelist + an explicit blacklist of result/market columns.
# Updated for the 2018-2026 schema: the old Betfair stream columns
# (bf_last_preoff_ltp, bf_runner_status) no longer exist; the market/result
# columns that must never become features are now `bsp` plus the BSP-CSV
# price/volume fields (pre/ip min/max/vol).
ALLOWED = set(FEATURES)
FORBIDDEN = {"rpr", "bsp", "pos", "dec", "secs", "time", "ovr_btn", "btn",
             "prize", "pre_min", "pre_max", "ip_min", "ip_max",
             "pre_vol", "ip_vol", "wap", "morning_wap", "morning_vol"}

# Columns carried into the scored file as NON-features (for later scoring only).
# Prefixed `score_` so they can never be mistaken for model inputs.
#   bsp / pos         -> scorers (pos is also how we identify the winner now).
#   wap               -> PPWAP, the pre-off volume-weighted avg traded price: the
#                        REAL interim struck price for CLV (default STRUCK_MODE).
#   pre_min / pre_max -> pre-off traded-price range; alternative struck proxies
#                        (geomean/pre_min/pre_max) kept for comparison.
CARRY = ["bsp", "pos", "wap", "pre_min", "pre_max"]


def race_key(r):
    """Canonical race id from (date, course, off) -> one stable string.

    Replaces the gone `bf_market_id`. Verification found 0 duplicate
    (date, course, off, horse) keys across 2018-2026, so (date, course, off)
    is a clean per-race choice-set key.
    """
    return f"{r['date']}|{r['course']}|{r['off']}"


def is_winner(r):
    """Winner flag from finishing position (`pos == '1'`).

    Replaces the gone `bf_runner_status == 'WINNER'`. Non-finishers
    (PU/F/UR/RR/...) and blanks are not '1' and so score as losers.
    """
    return (r.get("pos") or "").strip() == "1"


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# 1. Load + group into per-race choice sets.                                  #
# --------------------------------------------------------------------------- #
def load_races():
    rows = list(csv.DictReader(open(JOINED, newline="")))
    races = defaultdict(list)
    for r in rows:
        races[race_key(r)].append(r)
    return races


# --------------------------------------------------------------------------- #
# 2. Build feature matrix: impute (race-mean) then standardise (z-score).     #
# --------------------------------------------------------------------------- #
def build_matrix(races):
    # global means for fallback imputation (races with no value at all)
    global_mean = {}
    for f in FEATURES:
        vals = [fnum(r[f]) for rs in races.values() for r in rs]
        vals = [v for v in vals if v is not None]
        global_mean[f] = sum(vals) / len(vals)

    imputed = {f: 0 for f in FEATURES}
    raw = []  # per runner: dict of feature -> value (post-impute), + bookkeeping
    for mid, rs in races.items():
        for f in FEATURES:
            present = [fnum(r[f]) for r in rs if fnum(r[f]) is not None]
            race_mean = sum(present) / len(present) if present else global_mean[f]
            for r in rs:
                v = fnum(r[f])
                if v is None:
                    v = race_mean          # neutral within the race
                    imputed[f] += 1
                    r["_imp_" + f] = True
                r["_feat_" + f] = v

    # z-score standardisation across all runners (optimizer stability)
    stats = {}
    flat = [r for rs in races.values() for r in rs]
    for f in FEATURES:
        xs = [r["_feat_" + f] for r in flat]
        mu = sum(xs) / len(xs)
        sd = (sum((x - mu) ** 2 for x in xs) / len(xs)) ** 0.5 or 1.0
        stats[f] = (mu, sd)
        for r in flat:
            r["_z_" + f] = (r["_feat_" + f] - mu) / sd
    return imputed, stats


def leakage_guard(feature_names):
    """Hard-fail if anything outside the whitelist (or in the blacklist) appears."""
    used = set(feature_names)
    assert used <= ALLOWED, f"NON-WHITELISTED feature(s): {used - ALLOWED}"
    bad = used & FORBIDDEN
    assert not bad, f"LEAKAGE: forbidden feature(s) in matrix: {bad}"
    print("LEAKAGE GUARD PASSED. Features in matrix:", feature_names)


# --------------------------------------------------------------------------- #
# 3. Conditional-logit fit (gradient descent on the NLL).                     #
# --------------------------------------------------------------------------- #
def race_probs(runners, beta):
    """Softmax of utilities within one race; returns list of P(win) per runner."""
    us = [sum(beta[k] * r["_z_" + f] for k, f in enumerate(FEATURES))
          for r in runners]
    m = max(us)                                  # subtract max for stability
    exps = [math.exp(u - m) for u in us]
    s = sum(exps)
    return [e / s for e in exps]


def nll_and_grad(races, beta, l2):
    """Negative log-likelihood and its gradient over all races."""
    nll = 0.0
    grad = [0.0] * len(FEATURES)
    for runners in races.values():
        ps = race_probs(runners, beta)
        for r, p in zip(runners, ps):
            y = 1.0 if is_winner(r) else 0.0
            if y:
                nll -= math.log(max(p, 1e-12))
            for k, f in enumerate(FEATURES):
                grad[k] += (p - y) * r["_z_" + f]   # softmax cross-entropy grad
    # L2 regularisation keeps weights finite / well-conditioned
    nll += l2 * sum(b * b for b in beta)
    for k in range(len(beta)):
        grad[k] += 2 * l2 * beta[k]
    return nll, grad


def fit(races, l2=1.0, iters=600):
    beta = [0.0] * len(FEATURES)
    lr = 0.5
    nll, grad = nll_and_grad(races, beta, l2)
    for it in range(iters):
        trial = [beta[k] - lr * grad[k] for k in range(len(beta))]
        new_nll, new_grad = nll_and_grad(races, trial, l2)
        if new_nll < nll:                 # accept; gently grow the step
            beta, nll, grad, lr = trial, new_nll, new_grad, lr * 1.05
        else:                             # reject; shrink the step (backtrack)
            lr *= 0.5
            if lr < 1e-8:
                break
    return beta, nll


# --------------------------------------------------------------------------- #
# 4/5. Score, write, and report.                                              #
# --------------------------------------------------------------------------- #
def main():
    races = load_races()
    print(f"Loaded {sum(len(v) for v in races.values())} runners in "
          f"{len(races)} races.\n")

    # feature build + leakage assertion
    imputed, stats = build_matrix(races)
    leakage_guard(FEATURES)
    print("\nFeatures USED (runner-varying, pre-race):", FEATURES)
    print("Dropped (with reason):")
    print("  rpr            -> POST-RACE rating (leakage: top-rpr wins 72.9%)")
    print("  going,class,dist,type -> constant within race (cancels in cond. logit)")
    print("  days_since_run -> not present in the joined data")
    print("Imputed missing (race-mean):",
          {f: imputed[f] for f in FEATURES if imputed[f]})

    beta, nll = fit(races)
    print("\nFitted conditional logit (standardised coefficients):")
    for f, b in zip(FEATURES, beta):
        print(f"  {f:5} : {b:+.3f}")
    print(f"  final NLL: {nll:.1f}")

    # score every runner + per-race sanity
    sums = []
    out_rows = []
    fav_match = 0
    for mid, runners in races.items():
        ps = race_probs(runners, beta)
        sums.append(sum(ps))
        # market favourite = lowest BSP; model favourite = highest prob
        mkt_fav = min(runners, key=lambda r: fnum(r["bsp"]) or 1e9)
        mdl_fav = runners[max(range(len(ps)), key=lambda i: ps[i])]
        fav_match += int(mkt_fav is mdl_fav)
        # BSP-implied prob, renormalised within the race (for reporting/carry)
        inv = [1.0 / (fnum(r["bsp"]) or 1e9) for r in runners]
        z = sum(inv)
        for r, p, q in zip(runners, ps, inv):
            row = {
                "race_id": mid, "date": r["date"], "course": r["course"],
                "off": r["off"], "horse": r["horse"],
                "model_prob": round(p, 6),
                "bsp_implied_prob": round(q / z, 6),
            }
            for f in FEATURES:                       # raw feature values used
                row["feat_" + f] = r["_feat_" + f]
            for c in CARRY:                          # non-features, clearly tagged
                row["score_" + c] = r[c]
            out_rows.append(row)

    cols = (["race_id", "date", "course", "off", "horse",
             "model_prob", "bsp_implied_prob"]
            + ["feat_" + f for f in FEATURES]
            + ["score_" + c for c in CARRY])
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    lo, hi = min(sums), max(sums)
    print("\n--- CHECKPOINT: per-race probability sums ---")
    print(f"  min={lo:.6f}  max={hi:.6f}  mean={sum(sums)/len(sums):.6f}  "
          f"(should all be 1.000000)")
    print(f"  model favourite == market favourite: {fav_match}/{len(races)} "
          f"({100*fav_match/len(races):.1f}%)")

    # 3 sample races side by side
    print("\n--- sample races: model prob vs BSP-implied prob ---")
    for mid in list(races)[:3]:
        runners = races[mid]
        ps = race_probs(runners, beta)
        inv = [1.0 / (fnum(r["bsp"]) or 1e9) for r in runners]
        z = sum(inv)
        r0 = runners[0]
        print(f"\n  {r0['date']} {r0['course']} {r0['off']}  ({len(runners)} runners)")
        order = sorted(range(len(runners)), key=lambda i: -ps[i])
        print(f"    {'horse':<22}{'model':>8}{'bsp_impl':>10}{'won':>5}")
        for i in order:
            r = runners[i]
            print(f"    {r['horse'][:22]:<22}{ps[i]:>8.1%}{inv[i]/z:>10.1%}"
                  f"{'  W' if is_winner(r) else '':>5}")

    print(f"\nWrote scored table -> {OUT}")


if __name__ == "__main__":
    main()

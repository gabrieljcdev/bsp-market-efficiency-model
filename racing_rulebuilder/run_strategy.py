"""
run_strategy.py -- the UI<->pipeline BRIDGE.

The rule-builder UI emits a strategy.json (a `selection_rules` combinator tree
over the joined dataset's columns). This script reads that, FILTERS the ~726k
joined runner set, and SCORES the qualifying runners with the project's EXISTING
CLV harness. It does NOT reinvent scoring / CLV / leakage logic -- it imports and
reuses what is already in the repo:

  * CLV  : backtest/clv.py  -- closing_line_value / back_bet_pnl / summarise,
           plus _fnum / _race_id / _won. CLV = struck/bsp - 1, P&L net 5% comm.
  * STRUCK price = the `wap` column ; BENCHMARK = `bsp`. (The STRUCK_MODE=wap
    convention used throughout models/score_*_clv.py and stage2_blend.py.)
  * MODEL (optional): models/stage1_scored.csv -- the conditional-logit pipeline's
    scored output (model_prob per race_id+horse). We READ it; we do not refit a
    new model. Live refit lives in models/stage1_logit.py if ever needed.

LEAKAGE (enforced server-side, independent of the UI):
  selection rules may only reference PRE-RACE / derived-materialised columns.
  Any rule touching a post_race column (pos, bsp, wap, rpr, ...) is REJECTED and
  the strategy is NOT scored. The post_race set is read from field_manifest.json
  (with a hard-coded fallback). wap/bsp are still used INTERNALLY as scorers --
  they are forbidden only as *selection criteria*.

USAGE
-----
    # one-shot: read a strategy file, write results.json next to it
    python3 run_strategy.py strategy.json [--out results.json] [--count-only]

    # serve the local endpoint the UI's buttons call (stdlib http.server)
    python3 run_strategy.py --serve [--port 8765]
        POST /run   body = strategy.json (+ optional "mode":"count"|"backtest")
                    -> results.json
"""
import os
import re
import csv
import sys
import json
import argparse

# --- locate the repo and reuse the existing CLV harness ---------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(_ROOT, "backtest"))
import clv  # noqa: E402  -- the project's CLV harness; we call its pure functions

csv.field_size_limit(1 << 24)

DEFAULT_CSV = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026.csv")
MANIFEST = os.path.join(_HERE, "field_manifest.json")
STAGE1_SCORED = os.path.join(_ROOT, "models", "stage1_scored.csv")
DEFAULT_STRUCK_COL = "wap"          # struck price convention (STRUCK_MODE=wap)
DEFAULT_COMMISSION = clv.DEFAULT_COMMISSION   # 0.05, reuse the harness default

# Verdict thresholds. The verdict is decided on the HOLDOUT partition, and the
# headline number is @BSP -- specifically edge_bsp = strategy ROI@BSP minus the
# same-period back-all@BSP baseline. Settling at BSP removes the wap-vs-bsp
# timing offset; differencing the back-all baseline removes overround/commission
# drag and favourite-longshot composition -- so neither convexity nor the timing
# artifact can masquerade as harvestable edge.
THIN_HOLDOUT_N = 2000               # fewer scored holdout bets than this -> can't confirm
EDGE_TOL = 0.01                     # +/-1pp band around the efficient close (BSP baseline)

# Hard-coded fallback if field_manifest.json is missing: post-race / market
# columns that must never drive a SELECTION. Mirrors stage1_logit.FORBIDDEN +
# the manifest's post_race classification (comment/time/morning_* included).
_FALLBACK_POSTRACE = {
    "pos", "ovr_btn", "btn", "time", "secs", "dec", "rpr", "comment",
    "bsp", "pre_min", "pre_max", "ip_min", "ip_max", "pre_vol", "ip_vol",
    "wap", "morning_wap", "morning_vol", "wap_valid",
}


# --------------------------------------------------------------------------- #
# Manifest -> field classification sets (for leakage + materialisation checks) #
# --------------------------------------------------------------------------- #
def load_manifest_sets():
    """Return (post_race_names, derived_names) from field_manifest.json.

    Falls back to the hard-coded post-race set if the manifest can't be read,
    so the leakage guard is never silently disabled.
    """
    try:
        with open(MANIFEST) as fh:
            m = json.load(fh)
        post = {f["name"] for f in m.get("fields", []) if f.get("stage") == "post_race"}
        derived = {d["name"] for d in m.get("derived_features", [])}
        return (post or set(_FALLBACK_POSTRACE)), derived
    except Exception:
        return set(_FALLBACK_POSTRACE), set()


# --------------------------------------------------------------------------- #
# Value coercion + per-rule / per-node evaluation of the combinator tree.      #
# --------------------------------------------------------------------------- #
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _coerce_num(x):
    """Tolerant numeric coercion for object-typed columns (or, dist_f, ...).

    Plain float() first; on failure pull the leading numeric token (e.g. '7.5f'
    -> 7.5, '85+' -> 85). Returns None for blanks / non-numeric cells.
    """
    f = clv._fnum(x)                      # reuse the harness parser
    if f is not None:
        return f
    if x is None:
        return None
    mo = _NUM_RE.search(str(x))
    return float(mo.group()) if mo else None


def _eval_rule(rule, row):
    """True iff `row` satisfies a single leaf rule. Unparseable cell -> False."""
    field, op, val, typ = rule["field"], rule["op"], rule["value"], rule["type"]
    raw = row.get(field)

    if typ == "numeric" or rule.get("coerce"):
        x = _coerce_num(raw)
        if x is None:
            return False
        if op in ("<",):            return x < val
        if op in ("≤", "<="):       return x <= val
        if op in ("=", "=="):       return x == val
        if op in ("≥", ">="):       return x >= val
        if op in (">",):            return x > val
        if op == "range":           return val[0] <= x <= val[1]
        return False

    if typ == "date":
        # ISO-8601 dates (YYYY-MM-DD) sort lexically, so string comparison is
        # exact. This is a SELECTION rule on the race date -- independent of the
        # discovery/holdout split and date_from/date_to slicing.
        s = ("" if raw is None else str(raw)).strip()
        if not s:
            return False
        if op in ("<", "before"):    return s < val
        if op in ("≤", "<="):        return s <= val
        if op in ("=", "==", "on"):  return s == val
        if op in ("≥", ">="):        return s >= val
        if op in (">", "after"):     return s > val
        if op == "range":            return val[0] <= s <= val[1]
        return False

    if typ == "categorical":
        # racecard JSON carries native ints (e.g. class=3) where the historical
        # CSV is all strings -- coerce to str so .strip()/.lower() never blow up.
        s = ("" if raw is None else str(raw)).strip().lower()
        if op == "is":
            return s == str(val).strip().lower()
        if op == "in":
            return s in {str(v).strip().lower() for v in val}
        return False

    if typ == "flag":
        # raw may be a JSON bool (True/False) on racecards, or a string in CSV.
        truthy = ("" if raw is None else str(raw)).strip().lower() in ("1", "true", "yes", "y", "t")
        return truthy == bool(val)

    return False


def _eval_node(node, row):
    """Recursively evaluate a combinator node (All=AND / Any=OR) or a leaf rule.

    An empty group is vacuously True (no constraint) so an empty root matches
    every runner rather than nothing.
    """
    if "children" in node:
        kids = node["children"]
        if not kids:
            return True
        if node.get("combinator") == "any":
            return any(_eval_node(c, row) for c in kids)
        return all(_eval_node(c, row) for c in kids)   # default / "all"
    return _eval_rule(node, row)


def _collect_fields(node, acc):
    """Gather every column name referenced anywhere in the rule tree."""
    if "children" in node:
        for c in node["children"]:
            _collect_fields(c, acc)
    else:
        acc.add(node["field"])
    return acc


# --------------------------------------------------------------------------- #
# The bridge itself.                                                           #
# --------------------------------------------------------------------------- #
def check_fields(referenced, columns, post_race, derived):
    """Classify each referenced field; the strategy is runnable only if every
    field is `ok` (a real, selectable column of the chosen CSV)."""
    report = {"ok": [], "leakage": [], "unsupported_derived": [], "unknown": []}
    for f in sorted(referenced):
        if f in post_race:
            report["leakage"].append(f)
        elif f in columns:
            report["ok"].append(f)
        elif f in derived:
            report["unsupported_derived"].append(f)     # named but not materialised
        else:
            report["unknown"].append(f)
    return report


def run_strategy(strategy, mode="backtest"):
    """Filter + score one strategy dict. Returns a results dict (-> results.json).

    mode "count"    -> qualifier count only (fast; the UI's preview button).
    mode "backtest" -> full CLV via backtest/clv.summarise (struck=wap vs bsp).
    """
    src = strategy.get("source_csv") or DEFAULT_CSV
    if not os.path.isabs(src):
        src = os.path.join(_ROOT, src)
    rules = strategy.get("selection_rules") or {"combinator": "all", "children": []}
    struck_col = strategy.get("struck_col", DEFAULT_STRUCK_COL)
    commission = float(strategy.get("commission", DEFAULT_COMMISSION))
    date_from = strategy.get("date_from")          # optional holdout slice (ISO)
    date_to = strategy.get("date_to")

    res = {
        "ok": False, "mode": mode, "source_csv": os.path.relpath(src, _ROOT),
        "struck_col": struck_col, "commission": commission,
        "qualifier_count": 0, "rows_scanned": 0, "errors": [],
    }
    if not os.path.exists(src):
        res["errors"].append(f"source_csv not found: {src}")
        return res

    post_race, derived = load_manifest_sets()
    with open(src, newline="") as f:
        columns = set(next(csv.reader(f)))         # header row

    referenced = _collect_fields(rules, set())
    field_check = check_fields(referenced, columns, post_race, derived)
    res["field_check"] = field_check
    bad = field_check["leakage"] + field_check["unsupported_derived"] + field_check["unknown"]
    if bad:
        if field_check["leakage"]:
            res["errors"].append(
                "leakage: selection rules reference post-race column(s): "
                + ", ".join(field_check["leakage"]))
        if field_check["unsupported_derived"]:
            res["errors"].append(
                "unsupported: derived feature(s) not materialised in this CSV "
                "(needs features/build_*.py): "
                + ", ".join(field_check["unsupported_derived"]))
        if field_check["unknown"]:
            res["errors"].append(
                "unknown column(s): " + ", ".join(field_check["unknown"]))
        return res                                  # refuse to score an invalid strategy

    # --- discovery/holdout split -------------------------------------------- #
    split = strategy.get("split") or {}
    cutoff = split.get("date_cutoff")
    do_split = bool(cutoff)
    res["split"] = ({"mode": split.get("mode", "date"), "date_cutoff": cutoff}
                    if do_split else None)
    want_scoring = (mode != "count")

    # --- optional staking / bankroll simulation (SECONDARY to the verdict) ---- #
    # Order-dependent compounding; computed server-side so the browser never sees
    # the CSV. Kelly reads model_prob from the EXISTING stage-1 scored output.
    staking_cfg = strategy.get("staking") or None
    prob_map = None
    if staking_cfg and want_scoring and staking_cfg.get("model") == "kelly":
        prob_map = _load_prob_map()

    parts = ["discovery", "holdout"] if do_split else ["all"]
    qual = {p: 0 for p in parts}
    bets = {p: [] for p in parts}
    base_pnl = {p: 0.0 for p in parts}      # back-ALL @BSP -> the efficient-close baseline
    base_n = {p: 0 for p in parts}
    skipped_price = {p: 0 for p in parts}
    race_Z = {}    # per-race sum(1/bsp) over priced runners = overround (calibrated null)
    rows = 0
    skipped_no_date = 0

    def partition_of(d):
        if not do_split:
            return "all"
        if not d:
            return None                      # undated rows can't be placed in a split
        return "discovery" if d <= cutoff else "holdout"

    # --- single streaming pass over the joined set ---------------------------
    with open(src, newline="") as f:
        for r in csv.DictReader(f):
            rows += 1
            d = r.get("date") or ""
            if date_from and d < date_from:
                continue
            if date_to and d > date_to:
                continue
            p = partition_of(d)
            if p is None:
                skipped_no_date += 1
                continue

            struck = clv._fnum(r.get(struck_col))      # struck = wap (convention)
            bsp = clv._fnum(r.get("bsp"))              # benchmark = bsp
            priced = bool(struck and bsp and struck > 1.0 and bsp > 1.0)
            won = clv._won(r)                          # reuse harness settlement
            rid = clv._race_id(r) if priced else None

            if want_scoring and priced:
                # old full-field baseline: back EVERY priced runner @BSP
                base_pnl[p] += clv.back_bet_pnl(bsp, won, commission)
                base_n[p] += 1
                # per-race overround (sum of raw BSP-implied probs) for the calibrated null
                race_Z[rid] = race_Z.get(rid, 0.0) + 1.0 / bsp

            # the strategy's own selection
            if not _eval_node(rules, r):
                continue
            qual[p] += 1
            if not want_scoring:
                continue
            if not priced:
                skipped_price[p] += 1
                continue
            bets[p].append({
                "race_id": rid, "horse": r.get("horse"), "date": d,
                "type": r.get("type"), "struck": struck, "bsp": bsp, "won": won,
            })

    res.update(ok=True, rows_scanned=rows)
    if skipped_no_date:
        res["skipped_no_date"] = skipped_no_date

    def block(p):
        """Per-partition result: qualifiers, CLV (reuse clv.summarise), and TWO
        @BSP baselines with their edges:
          * full-field : back-all@BSP over the whole field (composition-BLIND).
          * fair null  : the SELECTION's own horses settled at BSP under a
                         BSP-calibrated, overround-removed null -- 'what these
                         exact horses return if BSP is perfectly efficient'.
        edge_bsp (the verdict headline) is the COMPOSITION-FAIR one.
        """
        b = {"qualifiers": qual[p]}
        if not want_scoring:
            return b
        b["scored_bets"] = len(bets[p])
        b["skipped_no_price"] = skipped_price[p]
        b["clv"] = clv.summarise(bets[p], commission) if bets[p] else None
        roi = b["clv"]["roi_bsp"] if b["clv"] else None

        # OLD composition-BLIND baseline: back-all @BSP over the full field.
        ff_roi = (base_pnl[p] / base_n[p]) if base_n[p] else None
        b["bsp_baseline_fullfield"] = {"n": base_n[p], "roi_bsp": ff_roi}
        b["edge_bsp_fullfield"] = ((roi - ff_roi)
                                   if (roi is not None and ff_roi is not None) else None)

        # NEW composition-FAIR baseline: the SAME horses under a BSP-calibrated null.
        # p_i = (1/bsp_i)/Z_race (overround removed) -> E[@BSP P&L] if BSP is the truth.
        null_pnl, nb = 0.0, 0
        for bet in bets[p]:
            Z = race_Z.get(bet["race_id"])
            if not Z:
                continue
            pi = (1.0 / bet["bsp"]) / Z
            null_pnl += pi * (bet["bsp"] - 1.0) * (1.0 - commission) - (1.0 - pi)
            nb += 1
        fair_roi = (null_pnl / nb) if nb else None
        b["bsp_baseline_fair"] = {"n": nb, "roi_bsp": fair_roi}
        b["edge_bsp_fair"] = ((roi - fair_roi)
                              if (roi is not None and fair_roi is not None) else None)

        b["edge_bsp"] = b["edge_bsp_fair"]      # headline / verdict metric
        if b["clv"]:
            b["by_type"] = _by_type(bets[p], commission)
        if staking_cfg and bets[p]:
            b["staking"] = _staking_curves(bets[p], commission, staking_cfg, prob_map)
        return b

    # --- assemble + verdict --------------------------------------------------
    if do_split:
        disc, hold = block("discovery"), block("holdout")
        res["discovery_qualifiers"] = qual["discovery"]
        res["holdout_qualifiers"] = qual["holdout"]
        res["discovery"], res["holdout"] = disc, hold
        res["discovery_clv"], res["holdout_clv"] = disc.get("clv"), hold.get("clv")
        if want_scoring:
            res["verdict"], res["verdict_reason"] = _verdict(disc, hold)
            res["verdict_metric"] = ("holdout edge_bsp = selection ROI@BSP - composition-fair "
                                     "BSP-calibrated null on the SAME horses (net commission); "
                                     "BSP strips the wap timing offset, the calibrated null "
                                     "strips price-mix composition")
            res["thresholds"] = {"thin_holdout_n": THIN_HOLDOUT_N, "edge_tol": EDGE_TOL}
        return res

    # single-population (no split) -- preserves the original result shape
    a = block("all")
    res["qualifier_count"] = qual["all"]
    if want_scoring:
        res["scored_bets"] = a["scored_bets"]
        res["skipped_no_price"] = a["skipped_no_price"]
        res["clv"] = a["clv"]
        res["bsp_baseline_fullfield"] = a["bsp_baseline_fullfield"]
        res["bsp_baseline_fair"] = a["bsp_baseline_fair"]
        res["edge_bsp_fullfield"] = a["edge_bsp_fullfield"]
        res["edge_bsp_fair"] = a["edge_bsp_fair"]
        res["edge_bsp"] = a["edge_bsp"]
        if a.get("staking"):
            res["staking"] = a["staking"]
        if a["clv"]:
            res["by_type"] = a["by_type"]
        else:
            res["errors"].append("no qualifying runners had a valid struck+bsp price")
        if strategy.get("score_with_model") and bets["all"]:
            res["model"] = _model_overlay(bets["all"], commission)
    return res


def _verdict(disc, hold):
    """Decide the verdict on the HOLDOUT partition, benchmarked to BSP.

    The deciding number is edge_bsp = strategy ROI@BSP - back-all@BSP baseline.
      * thin       -> holdout too small to judge and discovery not compelling.
      * to-holdout -> discovery edge looks good but holdout too thin to confirm.
      * priced     -> holdout edge collapses onto the efficient close (<= +tol):
                      only the wap timing offset / convexity, not real edge.
      * ruled-in   -> holdout edge holds the discovery direction beyond the floor.
    """
    he, de = hold.get("edge_bsp"), disc.get("edge_bsp")
    hn = hold.get("scored_bets", 0) or 0

    if he is None or hn < THIN_HOLDOUT_N:
        if de is not None and de > EDGE_TOL:
            return "to-holdout", (
                f"discovery edge vs BSP {de:+.2%} looks good, but holdout "
                f"n={hn:,} < {THIN_HOLDOUT_N:,} -- too thin to confirm.")
        d_txt = f"{de:+.2%}" if de is not None else "n/a"
        return "thin", (
            f"holdout n={hn:,} < {THIN_HOLDOUT_N:,}; discovery edge {d_txt} "
            "not compelling -- not enough holdout sample to judge.")

    if he <= EDGE_TOL:
        return "priced", (
            f"holdout edge vs BSP {he:+.2%} collapses onto the efficient close "
            f"(<= +{EDGE_TOL:.0%}) -- timing offset/convexity, not harvestable edge.")

    if de is not None and de > EDGE_TOL:
        return "ruled-in", (
            f"holdout edge vs BSP {he:+.2%} holds the discovery direction "
            f"({de:+.2%}) beyond the +{EDGE_TOL:.0%} floor on n={hn:,}.")

    d_txt = f"{de:+.2%}" if de is not None else "n/a"
    return "priced", (
        f"holdout edge {he:+.2%} not corroborated by discovery ({d_txt}).")


def _by_type(bets, commission):
    """Per race-type CLV table, reusing clv.summarise (mirrors score_stage1_clv)."""
    from collections import defaultdict
    groups = defaultdict(list)
    for b in bets:
        groups[b.get("type") or "?"].append(b)
    out = []
    for t, bs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        s = clv.summarise(bs, commission)
        out.append({"type": t, "n_bets": s["n_bets"], "mean_clv": s["mean_clv"],
                    "pct_beating_bsp": s["pct_beating_bsp"],
                    "roi_struck": s["roi_struck"], "roi_bsp": s["roi_bsp"]})
    return out


def _model_overlay(bets, commission):
    """OPTIONAL value-filter using the EXISTING stage-1 scored output (read, not
    refit): keep bets where the model's fair price < struck (model thinks the
    runner likelier than the price implies), then re-CLV. Mirrors the selection
    rule in models/score_stage1_clv.py. Returns None if the scored file is absent.
    """
    if not os.path.exists(STAGE1_SCORED):
        return {"available": False,
                "note": "models/stage1_scored.csv not found -- run the stage-1 pipeline first."}
    prob = {}
    for r in csv.DictReader(open(STAGE1_SCORED, newline="")):
        prob[(r["race_id"], r["horse"])] = clv._fnum(r.get("model_prob"))
    value = []
    for b in bets:
        p = prob.get((b["race_id"], b["horse"]))
        if p and p > 0 and b["struck"] > 1.0 / p:        # struck > fair_price
            value.append(b)
    if not value:
        return {"available": True, "n_value_bets": 0,
                "note": "no model-value selections among the qualifiers."}
    s = clv.summarise(value, commission)
    return {"available": True, "n_value_bets": len(value), "clv": s,
            "note": "value = model fair price < struck (stage-1 scored output, read-only)."}


# --------------------------------------------------------------------------- #
# Staking / bankroll simulation.  SECONDARY to the edge verdict, by design:    #
# this is order-dependent compounding P&L, NOT a fresh edge test. A 'priced'   #
# rule will grind the @BSP curve down -- compounding amplifies variance/drag,  #
# it can never manufacture edge. CLV / verdict / leakage logic is untouched.   #
# --------------------------------------------------------------------------- #
_CURVE_POINTS = 120          # downsample target for the equity curve sent to the UI


def _load_prob_map():
    """(race_id, horse) -> model_prob from the EXISTING stage-1 scored output.

    Read-only; we never refit. Returns None if the scored file is absent (Kelly
    then degrades to 'no model prob -> no stake', reported via kelly_coverage).
    """
    if not os.path.exists(STAGE1_SCORED):
        return None
    prob = {}
    with open(STAGE1_SCORED, newline="") as fh:
        for r in csv.DictReader(fh):
            p = clv._fnum(r.get("model_prob"))
            if p is not None:
                prob[(r.get("race_id"), r.get("horse"))] = p
    return prob


def _downsample_pairs(pts, k):
    """Even-stride downsample to <= k (x, y) pairs, always keeping first & last."""
    n = len(pts)
    if n <= k:
        return [[x, y] for (x, y) in pts]
    step = (n - 1) / float(k - 1)
    idx = sorted({int(round(i * step)) for i in range(k)} | {0, n - 1})
    return [[pts[i][0], pts[i][1]] for i in idx]


def _staking_curves(bets, commission, staking, prob_map):
    """Back-side bankroll simulation over the qualifying bets.

    Stakes are decided at the STRUCK price (the price you'd actually take); the
    SAME stake sequence is then settled twice -- at struck (wap, the timing
    artifact) and at bsp (the honest close) -- so the two curves are directly
    comparable. fixed_pct and kelly compound on the running bank; flat is a
    constant unit. Bets are sorted chronologically first (the joined CSV is NOT
    globally date-sorted, so naive row order would corrupt the compound path).

    Returns {config, n_bets, struck:{...}, bsp:{...}[, kelly_coverage]} where each
    settle block carries a downsampled equity curve plus final bank / ROI /
    max-drawdown / ruin.
    """
    model = staking.get("model", "fixed_pct")
    bank0 = float(staking.get("bankroll", 1000.0) or 1000.0)
    pct = float(staking.get("pct", 0.03) or 0.0)
    flat = float(staking.get("flat", 0.0) or 0.0)
    kf = float(staking.get("kelly_fraction", 0.25) or 0.0)

    sb = sorted(bets, key=lambda b: (b.get("date") or "", str(b.get("race_id") or "")))

    # Per-bet stake FRACTION of current bank (None for flat, which is absolute).
    #   fixed_pct -> constant pct ; kelly -> fractional-Kelly at struck odds vs p.
    fracs = []
    kelly_cov = {"n_with_prob": 0, "n_total": len(sb)}
    for b in sb:
        if model == "kelly":
            p = prob_map.get((b["race_id"], b["horse"])) if prob_map else None
            o = b["struck"]
            if p and p > 0 and o > 1.0:
                kelly_cov["n_with_prob"] += 1
                f_full = (o * p - 1.0) / (o - 1.0)     # full-Kelly fraction at struck odds
                fracs.append(max(0.0, kf * f_full))    # clamp negatives -> no bet
            else:
                fracs.append(0.0)                      # no model prob -> stand aside
        elif model == "flat":
            fracs.append(None)
        else:                                          # fixed_pct (default)
            fracs.append(pct)

    def simulate(price_key):
        bank = peak = bank0
        max_dd = 0.0
        n_staked = 0
        ruin = False
        pts = [(0, round(bank0, 2))]
        for i, b in enumerate(sb):
            if bank <= 0:
                ruin = True
                break
            stake = (min(flat, bank) if flat > 0 else 0.0) if model == "flat" \
                else fracs[i] * bank
            if stake > 0:
                n_staked += 1
                price = b[price_key]
                bank += (stake * (price - 1.0) * (1.0 - commission)) if b["won"] else -stake
            if bank > peak:
                peak = bank
            if peak > 0:
                max_dd = max(max_dd, (peak - bank) / peak)
            pts.append((i + 1, round(bank, 2)))
        return {
            "final_bank": round(bank, 2),
            "roi": (bank / bank0 - 1.0) if bank0 else None,
            "growth": (bank / bank0) if bank0 else None,
            "max_drawdown": max_dd,
            "n_staked": n_staked,
            "ruin": ruin,
            "curve": _downsample_pairs(pts, _CURVE_POINTS),
        }

    out = {
        "config": {"model": model, "bankroll": bank0, "pct": pct,
                   "flat": flat, "kelly_fraction": kf},
        "n_bets": len(sb),
        "struck": simulate("struck"),
        "bsp": simulate("bsp"),
    }
    if model == "kelly":
        out["kelly_coverage"] = kelly_cov
    return out


# --------------------------------------------------------------------------- #
# Stage 3 scan endpoint -- the SAME scan_today.scan() path, over HTTP.         #
# Tier 1 only: validated rule -> today's qualifying races (no price/CLV).      #
# --------------------------------------------------------------------------- #
def scan_today_endpoint(strategy):
    """Resolve today's racecard file and run the Stage 3 scanner over it.

    Same filter + leakage discipline as /run (scan_today.scan reuses _eval_node /
    check_fields). If the cards aren't pulled yet, returns a structured
    cards_missing response carrying the pull command (not an error to spew).
    """
    import datetime
    sys.path.insert(0, _HERE)          # ensure scan_today is importable when served
    import scan_today                  # lazy: avoids a circular import at module load

    date_str = strategy.get("date") or datetime.date.today().isoformat()
    path = scan_today.find_cards(date_str, strategy.get("cards"))
    if not path:
        searched = [os.path.relpath(os.path.join(d, f"{date_str}.json"), _ROOT)
                    for d in scan_today.CARD_DIRS]
        return {
            "ok": False, "cards_missing": True, "date": date_str, "searched": searched,
            "pull_cmd": "cd vendor/rpscrape/scripts && python racecards.py --day 1 --region gb",
            "errors": [f"no racecard file for {date_str} -- pull today's cards first"],
        }
    with open(path) as fh:
        cards = json.load(fh)
    res = scan_today.scan(strategy, cards)
    res["date"] = date_str
    res["source"] = os.path.relpath(path, _ROOT)
    return res


# --------------------------------------------------------------------------- #
# Race view (Task 2) -- per-course race list. A DISPLAY surface: browse what is #
# on at a course. It NEVER filters by a rule and NEVER feeds the selection      #
# engine. Today's cards are price-free / pre-race only; the historical fallback #
# may carry race-level POST-RACE facts (winner, winning time) DISPLAY-ONLY.     #
# --------------------------------------------------------------------------- #
def _finish_courses(by_course):
    """Sort each course's races by off-time; return courses sorted by name."""
    courses = []
    for cname in sorted(by_course, key=lambda c: str(c)):
        races = sorted(by_course[cname], key=lambda x: str(x.get("off") or ""))
        courses.append({"course": cname, "n_races": len(races), "races": races})
    return {"courses": courses}


def _races_from_cards(cards):
    """Race rows from a {region:{course:{off: racecard}}} pull -- price-free,
    pre-race only (the race has not run, so no winner/time/price exist)."""
    by_course = {}
    for region, courses in cards.items():
        for course, offs in courses.items():
            for off, card in offs.items():
                cname = card.get("course", course)
                active = sum(1 for r in card.get("runners", [])
                             if not (r.get("non_runner") or r.get("reserve")))
                by_course.setdefault(cname, []).append({
                    "key": f"{card.get('date')}|{cname}|{card.get('off_time', off)}",
                    "off": card.get("off_time", off),
                    "race_name": card.get("race_name"),
                    "type": card.get("race_type"),
                    "class": card.get("race_class"),
                    "going": card.get("going"),
                    "dist": card.get("distance"),
                    "field_size": card.get("field_size") or active,
                    "n_runners": active,
                    # no display_only block: there is no result yet.
                })
    return _finish_courses(by_course)


def _races_from_csv(src, date_str):
    """Race rows for one historical date, grouped by course. Post-race race-level
    facts (winner, winning time) ride along in a `display_only` block -- shown to
    a human, never offered as a selection input."""
    races = {}
    with open(src, newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("date") or "") != date_str:
                continue
            rid = clv._race_id(r)
            rc = races.get(rid)
            if rc is None:
                rc = races[rid] = {
                    "key": rid, "course": r.get("course"),
                    "off": r.get("off"), "race_name": r.get("race_name"),
                    "type": r.get("type"), "class": r.get("class"),
                    "going": r.get("going"), "dist": r.get("dist"),
                    "field_size": clv._fnum(r.get("ran")), "n_runners": 0,
                    "_winner": None, "_wtime": None,
                }
            rc["n_runners"] += 1
            if clv._won(r):
                rc["_winner"] = r.get("horse")
                wt = (r.get("time") or "").strip()
                rc["_wtime"] = wt if wt and wt != "-" else None
    by_course = {}
    for rc in races.values():
        row = {k: rc[k] for k in ("key", "off", "race_name", "type", "class",
                                  "going", "dist", "field_size", "n_runners")}
        if row["field_size"] is not None:
            row["field_size"] = int(row["field_size"])
        row["display_only"] = {            # POST-RACE -- display surface only
            "winner": rc["_winner"], "winning_time": rc["_wtime"],
        }
        by_course.setdefault(rc["course"], []).append(row)
    return _finish_courses(by_course)


def races_endpoint(req):
    """Resolve a date to a per-course race list. Cards if pulled (price-free),
    else the historical joined set (winner/time display-only)."""
    import datetime
    sys.path.insert(0, _HERE)
    import scan_today

    date_str = req.get("date") or datetime.date.today().isoformat()
    missing = lambda: {
        "ok": False, "cards_missing": True, "date": date_str,
        "searched": [os.path.relpath(os.path.join(d, f"{date_str}.json"), _ROOT)
                     for d in scan_today.CARD_DIRS],
        "pull_cmd": "cd vendor/rpscrape/scripts && python racecards.py --day 1 --region gb",
        "courses": [],
        "errors": [f"no racecard for {date_str} and no historical races on that date"],
    }

    path = scan_today.find_cards(date_str, req.get("cards"))
    if path:
        with open(path) as fh:
            cards = json.load(fh)
        res = _races_from_cards(cards)
        res.update(ok=True, date=date_str, mode="today",
                   source=os.path.relpath(path, _ROOT))
        return res

    src = DEFAULT_CSV
    if not os.path.exists(src):
        return missing()
    res = _races_from_csv(src, date_str)
    if not res["courses"]:
        return missing()
    res.update(ok=True, date=date_str, mode="historical",
               source=os.path.relpath(src, _ROOT))
    return res


# --------------------------------------------------------------------------- #
# Runner view (Task 3) -- per-runner detail for ONE race. Same DISPLAY-vs-      #
# SELECTION discipline, now at runner level:                                   #
#   * SELECTION-INPUT columns  -> pre-race fields a rule could touch.           #
#   * DISPLAY-ONLY columns     -> post-race (position, BSP) shown on HISTORICAL #
#     runners under a "never selectable" banner; EMPTY on today's cards (the    #
#     racecard has no such fields). Reuses Task 2's card/CSV resolution path.   #
# Layer 2 (history-join fields: OR trajectory, class-change, C/D/CD flags,      #
# DSLR, win%/place%) is NOT built here -- it needs the strictly-prior,          #
# date-sorted join shared with the scanner's Tier 2. Marked 'pending'.          #
# --------------------------------------------------------------------------- #
RUNNER_SELECTION_COLS = ["num", "draw", "horse", "age", "sex", "lbs", "or", "hg", "form"]
RUNNER_DISPLAY_COLS = ["position", "bsp"]      # post-race; winning_time is race-level
RUNNER_LAYER2_COLS = ["or_trajectory", "class_change", "cd_flags", "dslr", "win_pct", "place_pct"]


def _intkey(v):
    """Sort key that orders numeric cloth numbers naturally, blanks/strings last."""
    try:
        return (0, int(v))
    except (TypeError, ValueError):
        return (1, str(v if v is not None else "~"))


def _runner_view_meta(extra):
    base = {"selection_columns": RUNNER_SELECTION_COLS,
            "display_columns": RUNNER_DISPLAY_COLS,
            "layer2_columns": RUNNER_LAYER2_COLS,
            "layer2_status": "pending"}
    base.update(extra)
    return base


def _runners_from_cards(cards, key, date_str, path):
    """Today's runners from the matching racecard -- pre-race only; the display-
    only post-race columns are EMPTY (the race has not run). Reuses scan_today."""
    import scan_today
    for region, courses in cards.items():
        for course, offs in courses.items():
            for off, card in offs.items():
                cname = card.get("course", course)
                k = f"{card.get('date')}|{cname}|{card.get('off_time', off)}"
                if k != key:
                    continue
                rows, _ = scan_today._runner_rows(card)       # active runners only
                runners = []
                for inp, disp in rows:
                    runners.append({
                        "num": disp.get("no"), "draw": disp.get("draw"),
                        "horse": disp.get("horse"), "age": disp.get("age"),
                        "sex": disp.get("sex"), "lbs": disp.get("lbs"),
                        "or": disp.get("or"), "hg": disp.get("hg"),
                        "form": disp.get("form"), "jockey": disp.get("jockey"),
                        "trainer": disp.get("trainer"),
                        "display_only": {"position": None, "bsp": None},   # race not run
                        "history": None,                                   # Layer 2 pending
                    })
                runners.sort(key=lambda x: _intkey(x.get("num")))
                return _runner_view_meta({
                    "ok": True, "mode": "today", "date": date_str,
                    "source": os.path.relpath(path, _ROOT),
                    "race": {
                        "course": cname, "off": card.get("off_time", off),
                        "race_name": card.get("race_name"), "type": card.get("race_type"),
                        "going": card.get("going"), "dist": card.get("distance"),
                        "n_runners": len(runners),
                        "display_only": {"winner": None, "winning_time": None},
                    },
                    "runners": runners,
                })
    return {"ok": False, "errors": [f"race {key} not found in cards for {date_str}"]}


def _runners_from_csv(src, key, date_str):
    """Historical runners for one race (matched by race id). Post-race position
    and BSP ride along DISPLAY-ONLY; winner/winning-time are race-level."""
    rows = []
    with open(src, newline="") as f:
        for r in csv.DictReader(f):
            if clv._race_id(r) == key:
                rows.append(r)
    if not rows:
        return {"ok": False, "errors": [f"race {key} not found in history"]}

    winner, wtime = None, None
    runners = []
    for r in rows:
        if clv._won(r):
            winner = r.get("horse")
            wt = (r.get("time") or "").strip()
            wtime = wt if wt and wt != "-" else None
        pos = (r.get("pos") or "").strip() or None
        runners.append({
            "num": r.get("num"), "draw": r.get("draw"), "horse": r.get("horse"),
            "age": r.get("age"), "sex": r.get("sex"), "lbs": r.get("lbs"),
            "or": r.get("or"), "hg": r.get("hg"), "form": None,   # no form col in joined set
            "jockey": r.get("jockey"), "trainer": r.get("trainer"),
            "display_only": {"position": pos, "bsp": clv._fnum(r.get("bsp"))},
            "history": None,                                       # Layer 2 pending
        })
    runners.sort(key=lambda x: _intkey(x.get("num")))
    r0 = rows[0]
    return _runner_view_meta({
        "ok": True, "mode": "historical", "date": date_str,
        "source": os.path.relpath(src, _ROOT),
        "race": {
            "course": r0.get("course"), "off": r0.get("off"),
            "race_name": r0.get("race_name"), "type": r0.get("type"),
            "going": r0.get("going"), "dist": r0.get("dist"),
            "n_runners": len(runners),
            "display_only": {"winner": winner, "winning_time": wtime},
        },
        "runners": runners,
    })


def runners_endpoint(req):
    """Per-runner detail for one race. Cards if pulled (price-free, display-only
    columns empty) else the historical joined set (post-race display-only)."""
    import datetime
    sys.path.insert(0, _HERE)
    import scan_today

    date_str = req.get("date") or datetime.date.today().isoformat()
    key = req.get("key")
    if not key:
        return {"ok": False, "errors": ["missing race key"]}

    path = scan_today.find_cards(date_str, req.get("cards"))
    if path:
        with open(path) as fh:
            cards = json.load(fh)
        return _runners_from_cards(cards, key, date_str, path)

    src = DEFAULT_CSV
    if not os.path.exists(src):
        return {"ok": False, "errors": [f"no racecard for {date_str} and CSV missing"]}
    return _runners_from_csv(src, key, date_str)


# --------------------------------------------------------------------------- #
# Minimal local endpoint (stdlib http.server -- no Flask).                     #
# --------------------------------------------------------------------------- #
def serve(port=8765):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class Handler(BaseHTTPRequestHandler):
        def _cors(self):
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")

        def _json(self, code, obj):
            body = json.dumps(obj).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self._cors()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self):
            self.send_response(204)
            self._cors()
            self.end_headers()

        def do_GET(self):
            self._json(200, {
                "status": "ok", "service": "run_strategy bridge",
                "post": {
                    "/run":   "body=strategy.json (+ optional mode: count|backtest)",
                    "/scan":  "body=strategy.json (+ optional date) -> today's qualifying races (Tier 1)",
                    "/races":   "body={date?} -> per-course race list (browse/display; no rule filtering)",
                    "/runners": "body={date?, key} -> per-runner detail for one race (display vs selection)",
                },
                "default_csv": os.path.relpath(DEFAULT_CSV, _ROOT),
                "struck_col": DEFAULT_STRUCK_COL, "commission": DEFAULT_COMMISSION,
            })

        def do_POST(self):
            p = self.path.rstrip("/")
            if p not in ("", "/run", "/scan", "/races", "/runners"):
                return self._json(404, {"ok": False, "errors": [f"no route {self.path}"]})
            try:
                n = int(self.headers.get("Content-Length", 0))
                strategy = json.loads(self.rfile.read(n) or b"{}")
            except Exception as e:
                return self._json(400, {"ok": False, "errors": [f"bad JSON: {e}"]})
            try:
                if p == "/scan":
                    self._json(200, scan_today_endpoint(strategy))
                elif p == "/races":
                    self._json(200, races_endpoint(strategy))
                elif p == "/runners":
                    self._json(200, runners_endpoint(strategy))
                else:
                    self._json(200, run_strategy(strategy, mode=strategy.get("mode", "backtest")))
            except Exception as e:
                self._json(500, {"ok": False, "errors": [f"{type(e).__name__}: {e}"]})

        def log_message(self, fmt, *a):            # quieter console
            sys.stderr.write("  [bridge] " + (fmt % a) + "\n")

    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"run_strategy bridge listening on http://127.0.0.1:{port}  (POST /run, /scan)")
    print(f"  default dataset : {os.path.relpath(DEFAULT_CSV, _ROOT)}")
    print(f"  struck=wap  benchmark=bsp  commission={DEFAULT_COMMISSION:.0%}  (Ctrl-C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")


# --------------------------------------------------------------------------- #
# CLI.                                                                         #
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Rule-builder <-> CLV pipeline bridge.")
    ap.add_argument("strategy", nargs="?", help="path to strategy.json")
    ap.add_argument("--out", help="write results JSON here (default: results.json beside input)")
    ap.add_argument("--count-only", action="store_true", help="qualifier count only")
    ap.add_argument("--serve", action="store_true", help="run the local HTTP endpoint")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args()

    if args.serve:
        return serve(args.port)
    if not args.strategy:
        ap.error("provide a strategy.json, or use --serve")

    strategy = json.load(open(args.strategy))
    mode = "count" if args.count_only else strategy.get("mode", "backtest")
    res = run_strategy(strategy, mode=mode)

    out = args.out or os.path.join(os.path.dirname(os.path.abspath(args.strategy)), "results.json")
    json.dump(res, open(out, "w"), indent=2)

    # short console summary
    if not res["ok"]:
        print("STRATEGY NOT RUN:")
        for e in res["errors"]:
            print("  -", e)
    elif res.get("split"):
        _print_split(res)
    else:
        print(f"qualifiers: {res['qualifier_count']:,} / {res['rows_scanned']:,} runners")
        c = res.get("clv")
        if c:
            print(f"bets scored: {c['n_bets']:,}  (winners {c['n_winners']:,}, "
                  f"skipped {res['skipped_no_price']:,})")
            print(f"mean CLV   : {c['mean_clv']:+.2%}   beat BSP: {c['pct_beating_bsp']:.1%}")
            print(f"ROI @struck: {c['roi_struck']:+.2%}   ROI @BSP: {c['roi_bsp']:+.2%}")
            ff = res.get("bsp_baseline_fullfield", {}).get("roi_bsp")
            fair = res.get("bsp_baseline_fair", {}).get("roi_bsp")
            if ff is not None:
                print(f"baseline full-field@BSP: {ff:+.2%}   edge: {res['edge_bsp_fullfield']:+.2%}")
            if fair is not None:
                print(f"baseline fair-null@BSP : {fair:+.2%}   edge: {res['edge_bsp_fair']:+.2%}  (headline)")
    print(f"wrote {out}")


def _print_split(res):
    """Two-column discovery|holdout table + the verdict, both baselines shown."""
    d, h = res["discovery"], res["holdout"]
    co = res["split"]["date_cutoff"]
    pct = lambda x: f"{x:+.2%}" if x is not None else "    --"
    g = lambda blk, k: (blk["clv"][k] if blk.get("clv") else None)
    bl = lambda blk, key: blk.get(key, {}).get("roi_bsp")
    print(f"split @ {co}   (discovery: date <= cutoff   |   holdout: date > cutoff)")
    print(f"{'':<26}{'discovery':>13}{'holdout':>13}")
    print(f"{'qualifiers':<26}{d['qualifiers']:>13,}{h['qualifiers']:>13,}")
    if d.get("clv") or h.get("clv"):
        print(f"{'scored bets':<26}{d.get('scored_bets',0):>13,}{h.get('scored_bets',0):>13,}")
        print(f"{'ROI @struck (wap)':<26}{pct(g(d,'roi_struck')):>13}{pct(g(h,'roi_struck')):>13}")
        print(f"{'ROI @BSP (selection)':<26}{pct(g(d,'roi_bsp')):>13}{pct(g(h,'roi_bsp')):>13}")
        print("  -- OLD full-field baseline (composition-blind) --")
        print(f"{'  baseline @BSP':<26}"
              f"{pct(bl(d,'bsp_baseline_fullfield')):>13}{pct(bl(h,'bsp_baseline_fullfield')):>13}")
        print(f"{'  edge vs BSP':<26}{pct(d.get('edge_bsp_fullfield')):>13}{pct(h.get('edge_bsp_fullfield')):>13}")
        print("  -- NEW composition-fair null (same horses @BSP) --")
        print(f"{'  baseline @BSP':<26}"
              f"{pct(bl(d,'bsp_baseline_fair')):>13}{pct(bl(h,'bsp_baseline_fair')):>13}")
        print(f"{'  edge vs BSP (HEADLINE)':<26}{pct(d.get('edge_bsp_fair')):>13}{pct(h.get('edge_bsp_fair')):>13}")
    print(f"\nVERDICT: {res['verdict'].upper()}  --  {res['verdict_reason']}")


if __name__ == "__main__":
    main()

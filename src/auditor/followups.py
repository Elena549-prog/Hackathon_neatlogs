"""Follow-ups F1-F4 (AUDITOR_SPEC section 4): robustness checks run in code on the frozen plan v0.

The Naysayer picks up to 3 that apply; the Mathematician runs them here. Each returns a record with the code-written
`result` line and `downgrade` (the follow-up's rule was met). A met rule only turns `promising` into `inconclusive`;
verdict.py applies it and leaves every other verdict unchanged.
"""
import numpy as np
import pandas as pd

from . import backtest, checks

MENU = {
    "F1": ("Earnings excluded", "re-run without trades whose holding window contains an earnings date "
                                "(10 trading days for straddles, the plan's horizon for stock_long)",
           "the validation mean becomes <= 0"),
    "F2": ("Per-year stability", "train mean per calendar year",
           "the yearly train mean has the opposite sign to the validation mean in more than half the train years"),
    "F3": ("Horizon sensitivity", "horizons 5 and 20 trading days (stock_long only)",
           "both have validation mean <= 0"),
    "F4": ("Concentration", "re-run without the single ticker that contributes most to validation profit",
           "the validation mean becomes <= 0"),
}
MAX_FOLLOWUPS = 3
F3_HORIZONS = (5, 20)
SPLITS = ("train", "validation")
EMPTY = checks.stats(pd.DataFrame(), None)


def applicable(family):
    return [f for f in MENU if f != "F3" or family == "stock_long"]


def choose(requested, family):
    """Naysayer picks -> (chosen, ignored). Chosen: at most 3 distinct, known, applicable ids in the order asked."""
    chosen, ignored = [], []
    for r in requested or []:
        fid = str((r or {}).get("id", "")).strip().upper()
        reason = str((r or {}).get("reason", ""))
        if fid not in MENU:
            ignored.append({"id": fid, "why": "not on the follow-up menu"})
        elif fid not in applicable(family):
            ignored.append({"id": fid, "why": "not run for %s" % family})
        elif any(c["id"] == fid for c in chosen):
            continue
        elif len(chosen) >= MAX_FOLLOWUPS:
            ignored.append({"id": fid, "why": "at most %d follow-ups per audit" % MAX_FOLLOWUPS})
        else:
            chosen.append({"id": fid, "reason": reason})
    return chosen, ignored


def _record(fid, result, downgrade, split_stats, **extra):
    title, _, rule = MENU[fid]
    out = {"id": fid, "title": title, "result": result, "downgrade": bool(downgrade),
           "cause": "%s %s: %s" % (fid, title.lower(), rule) if downgrade else None,
           "train": split_stats.get("train") or dict(EMPTY), "validation": split_stats.get("validation") or dict(EMPTY)}
    out.update(extra)
    return out


def _stats(trades, calendar):
    return {s: checks.stats(trades[s], calendar) for s in SPLITS}


def f1_earnings_excluded(trades, plan, prices, earnings, calendar):
    """Drops v0's trades whose own holding window (entry, entry + hold] contains a report date; no new entries are
    opened in their place. Trades on tickers without earnings coverage are left out and counted."""
    hold = backtest.HOLD if plan["family"].startswith("straddle") else int(plan["exit"]["horizon_days"])
    eps = {t: prices[t].index.searchsorted(pd.DatetimeIndex(d)) for t, d in earnings.items() if d and t in prices}
    if not eps:
        return _record("F1", "skipped: no earnings data for any ticker in the group", False, {}, skipped=True)
    kept, left_out = {}, {}
    for split in SPLITS:
        t = trades[split]
        no_cov = in_window = 0
        keep = np.zeros(len(t), dtype=bool)
        for i, (ticker, day) in enumerate(zip(t["ticker"], t["entry_date"])):
            if ticker not in eps:
                no_cov += 1
                continue
            pos = prices[ticker].index.get_loc(pd.Timestamp(day))
            if ((eps[ticker] > pos) & (eps[ticker] <= pos + hold)).any():
                in_window += 1
                continue
            keep[i] = True
        kept[split] = t[keep]
        left_out[split] = {"earnings_in_window": in_window, "no_earnings_coverage": no_cov}
    st = _stats(kept, calendar)
    v, lo = st["validation"], left_out["validation"]
    dropped = "%d left out: earnings in the holding window; %d: no earnings coverage" % (
        lo["earnings_in_window"], lo["no_earnings_coverage"])
    if not v["n"]:      # an earnings idea keeps no trades: there is no mean to compare, so the rule is not met
        return _record("F1", "no validation trades left (%s), so the rule cannot be evaluated" % dropped, False, st,
                       left_out=left_out)
    result = "validation mean %s over %d trades (%s)" % (_pct(v["mean"]), v["n"], dropped)
    return _record("F1", result, v["mean"] <= 0, st, left_out=left_out)


def f2_per_year(trades, base, calendar):
    tr = trades["train"]
    if not len(tr):
        return _record("F2", "skipped: no train trades", False, base, skipped=True)
    val_mean = base["validation"]["mean"]
    years = tr.groupby(pd.DatetimeIndex(tr["entry_date"]).year)["ret"].agg(["count", "mean"])
    opposite = int((np.sign(years["mean"]) == -np.sign(val_mean)).sum()) if val_mean else 0
    per_year = {str(y): {"n": int(r["count"]), "mean": float(r["mean"])} for y, r in years.iterrows()}
    result = "train mean has the opposite sign to the validation mean (%s) in %d of %d train years" % (
        _pct(val_mean), opposite, len(years))
    return _record("F2", result, opposite > len(years) / 2, base, per_year=per_year, opposite_years=opposite)


def f3_horizons(plan, prices, features, earnings, calendar):
    """train/validation are the 5-day run; both runs are in `variants`."""
    if plan["family"] != "stock_long":
        return _record("F3", "skipped: horizon sensitivity applies to stock_long only", False, {}, skipped=True)
    variants = {}
    for h in F3_HORIZONS:
        p = dict(plan, exit=dict(plan["exit"], horizon_days=h))
        variants[str(h)] = _stats({s: backtest.run_backtest(prices, features, p, earnings, s)[0] for s in SPLITS}, calendar)
    means = {h: variants[str(h)]["validation"]["mean"] for h in F3_HORIZONS}
    result = "; ".join("horizon %d days: validation mean %s over %d trades" % (h, _pct(means[h]), variants[str(h)]["validation"]["n"])
                       for h in F3_HORIZONS)
    return _record("F3", result, all(m <= 0 for m in means.values()), variants[str(F3_HORIZONS[0])], variants=variants)


def f4_concentration(trades, calendar):
    """Dropping one ticker's trades equals a re-run without it: the one-open-trade rule is per ticker."""
    val = trades["validation"]
    if not len(val):
        return _record("F4", "skipped: no validation trades", False, {}, skipped=True)
    contrib = val.groupby("ticker")["ret"].sum()
    top = str(contrib.idxmax())
    st = _stats({s: trades[s][trades[s]["ticker"] != top] for s in SPLITS}, calendar)
    v = st["validation"]
    result = ("without the top-contributing ticker (its validation trades sum to %s; all validation trades sum to %s): "
              "validation mean %s over %d trades" % (_pct(float(contrib[top])), _pct(float(val["ret"].sum())), _pct(v["mean"]), v["n"]))
    return _record("F4", result, v["mean"] <= 0, st, ticker=top)


def run(fid, trades, plan, base, prices, features, earnings, calendar):
    if fid == "F1":
        return f1_earnings_excluded(trades, plan, prices, earnings, calendar)
    if fid == "F2":
        return f2_per_year(trades, base, calendar)
    if fid == "F3":
        return f3_horizons(plan, prices, features, earnings, calendar)
    if fid == "F4":
        return f4_concentration(trades, calendar)
    raise ValueError("unknown follow-up %r" % fid)


def _pct(x):
    return "%+.2f%%" % (100 * x)

"""Statistics, the paired baseline test, tail risk, and follow-ups F1-F4 (spec sections 4, 7).

Intervals come from bootstrap_mean: a block bootstrap over 10-trading-day blocks of entry dates,
2000 resamples, reporting the 2.5th and 97.5th percentiles. Block numbers come from the panel's
trading calendar, so the same date is always in the same block for v0 and its baselines.
"""
import numpy as np
import pandas as pd

BLOCK_DAYS = 10
N_BOOT = 2000
SEED = 0
MIN_N, MIN_BLOCKS = 30, 6
SELL_WORST_PREMIUMS = 5
FOLLOWUPS = ("F1", "F2", "F3", "F4")
MAX_FOLLOWUPS = 3


def block_ids(dates, calendar):
    """10-trading-day block number of each date on the calendar."""
    pos = calendar.searchsorted(pd.DatetimeIndex(dates))
    return np.asarray(pos) // BLOCK_DAYS


def _block_sums(blocks, returns, universe):
    s = pd.Series(returns).groupby(np.asarray(blocks)).agg(["sum", "count"]).reindex(universe, fill_value=0)
    return s["sum"].to_numpy(float), s["count"].to_numpy(float)


def bootstrap_mean(blocks, returns, n_boot=N_BOOT, seed=SEED):
    """95% interval (2.5th, 97.5th percentile) of the mean return, resampling whole blocks."""
    returns = np.asarray(returns, float)
    if not len(returns):
        return None, None
    universe = np.unique(blocks)
    sums, counts = _block_sums(blocks, returns, universe)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(universe), size=(n_boot, len(universe)))
    tot, cnt = sums[idx].sum(1), counts[idx].sum(1)
    means = tot[cnt > 0] / cnt[cnt > 0]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def paired_lower_bound(blocks_a, returns_a, blocks_b, returns_b, n_boot=N_BOOT, seed=SEED):
    """2.5th percentile of mean(a) - mean(b), resampling the same blocks for both."""
    if not len(returns_a) or not len(returns_b):
        return None
    universe = np.union1d(np.unique(blocks_a), np.unique(blocks_b))
    sa, ca = _block_sums(blocks_a, np.asarray(returns_a, float), universe)
    sb, cb = _block_sums(blocks_b, np.asarray(returns_b, float), universe)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(universe), size=(n_boot, len(universe)))
    na, nb = ca[idx].sum(1), cb[idx].sum(1)
    ok = (na > 0) & (nb > 0)
    diff = sa[idx].sum(1)[ok] / na[ok] - sb[idx].sum(1)[ok] / nb[ok]
    return float(np.percentile(diff, 2.5)) if len(diff) else None


def worst_window(dates, returns, calendar):
    """Most negative sum of trade returns entered within any 10 consecutive trading days."""
    if not len(returns):
        return None
    pos = np.asarray(calendar.searchsorted(pd.DatetimeIndex(dates)))
    daily = pd.Series(np.asarray(returns, float)).groupby(pos).sum()
    full = daily.reindex(range(int(pos.min()), int(pos.max()) + 1), fill_value=0.0)
    return float(full.rolling(BLOCK_DAYS, min_periods=1).sum().min())


def stats(trades, calendar):
    """Per-split statistics for one run."""
    out = {}
    for split in ("train", "validation"):
        t = trades[trades["split"] == split] if len(trades) else trades
        r = t["ret"].to_numpy(float) if len(t) else np.array([])
        b = block_ids(t["date"], calendar) if len(t) else np.array([])
        lo, hi = bootstrap_mean(b, r)
        out[split] = {"n": int(len(r)), "blocks": int(len(np.unique(b))),
                      "win_rate": float((r > 0).mean()) if len(r) else None,
                      "mean": float(r.mean()) if len(r) else None,
                      "median": float(np.median(r)) if len(r) else None,
                      "ci_low": lo, "ci_high": hi,
                      "worst_trade": float(r.min()) if len(r) else None,
                      "worst_window": worst_window(t["date"], r, calendar) if len(r) else None}
    return out


def paired(trades, base_trades, calendar, split="validation"):
    a = trades[trades["split"] == split] if len(trades) else trades
    b = base_trades[base_trades["split"] == split] if len(base_trades) else base_trades
    if not len(a) or not len(b):
        return None
    return paired_lower_bound(block_ids(a["date"], calendar), a["ret"], block_ids(b["date"], calendar), b["ret"])


def tail_risk(family, trades, calendar):
    """Worst trade and worst 10-day window on train plus validation. For straddle_sell, losses in
    average premiums and % of price, and whether the tail-risk rule downgrades `promising`."""
    if not len(trades):
        return {"worst_trade": None, "worst_window": None, "downgrade": False}
    r = trades["ret"].to_numpy(float)
    out = {"worst_trade": float(r.min()), "worst_window": worst_window(trades["date"], r, calendar),
           "downgrade": False, "reasons": []}
    if family == "straddle_sell":
        loss_price = (trades["payoff"] - trades["premium"]).to_numpy(float)    # share of stock price
        avg_prem = float(trades["premium"].mean())
        out["avg_premium_pct_price"] = 100 * avg_prem
        out["worst_loss_pct_price"] = 100 * float(loss_price.max())
        out["worst_loss_premiums"] = float(loss_price.max() / avg_prem)
        val = trades[trades["split"] == "validation"]["ret"].sum()
        out["validation_total_gain"] = float(val)
        if out["worst_loss_premiums"] > SELL_WORST_PREMIUMS:
            out["downgrade"] = True
            out["reasons"].append("worst single trade lost %.1f average premiums (limit %d)"
                                  % (out["worst_loss_premiums"], SELL_WORST_PREMIUMS))
        if out["worst_window"] is not None and -out["worst_window"] > val:
            out["downgrade"] = True
            out["reasons"].append("worst 10-day window lost %.2f, more than the total validation gain %.2f"
                                  % (-out["worst_window"], val))
    return out


def equity_curve(trades, split, max_points=300):
    t = trades[trades["split"] == split] if len(trades) else trades
    if not len(t):
        return []
    curve = np.cumsum(t["ret"].to_numpy(float))
    dates = t["date"].dt.strftime("%Y-%m-%d").to_numpy()
    step = max(1, int(np.ceil(len(curve) / max_points)))
    idx = list(range(0, len(curve), step))
    if idx[-1] != len(curve) - 1:
        idx.append(len(curve) - 1)
    return [[dates[i], round(float(curve[i]), 6)] for i in idx]


def histogram(trades, bins=20):
    """20 equal-width bins between the 1st and 99th percentile, plus underflow and overflow."""
    if not len(trades):
        return {"edges": [], "counts": [], "underflow": 0, "overflow": 0}
    r = trades["ret"].to_numpy(float)
    lo, hi = np.percentile(r, 1), np.percentile(r, 99)
    if hi <= lo:
        hi = lo + 1e-9
    counts, edges = np.histogram(r[(r >= lo) & (r <= hi)], bins=bins, range=(lo, hi))
    return {"edges": [round(float(e), 6) for e in edges], "counts": [int(c) for c in counts],
            "underflow": int((r < lo).sum()), "overflow": int((r > hi).sum())}


def evidence_ok(val):
    return val["n"] >= MIN_N and val["blocks"] >= MIN_BLOCKS


# ------------------------------------------------------------------------------------ follow-ups

def allowed_followups(family):
    return [f for f in FOLLOWUPS if not (f == "F3" and family != "stock_long")]


def pick_followups(requested, family):
    """Valid, unique follow-ups in the requested order, at most 3; F3 only for stock_long."""
    out, allowed = [], allowed_followups(family)
    for item in requested:
        fid = item.get("id") if isinstance(item, dict) else item
        reason = item.get("reason", "") if isinstance(item, dict) else ""
        if fid in allowed and fid not in [o["id"] for o in out]:
            out.append({"id": fid, "reason": str(reason)})
        if len(out) == MAX_FOLLOWUPS:
            break
    return out


def run_followup(fid, panel, plan, base_trades, base_stats, backtest_run):
    """One follow-up on v0. Returns {id, result, downgrade, note}. `backtest_run` is backtest.run."""
    val_mean = base_stats["validation"]["mean"]
    if fid == "F1":
        if not any(panel.earnings.values()):
            return {"id": fid, "result": None, "downgrade": False, "note": "skipped: no earnings data"}
        trades, drops = backtest_run(panel, plan, exclude_earnings=True)
        s = stats(trades, panel.calendar)
        m = s["validation"]["mean"]
        return {"id": fid, "result": {"validation": s["validation"],
                                      "tickers_without_coverage": drops["f1_no_earnings_coverage"]},
                "downgrade": m is None or m <= 0,
                "note": "validation mean without earnings windows: %s" % _pct(m)}
    if fid == "F2":
        train = base_trades[base_trades["split"] == "train"] if len(base_trades) else base_trades
        if not len(train) or val_mean is None:
            return {"id": fid, "result": None, "downgrade": False, "note": "skipped: no trades"}
        yearly = train.groupby(train["date"].dt.year)["ret"].mean()
        opposite = int((np.sign(yearly) == -np.sign(val_mean)).sum()) if val_mean != 0 else 0
        return {"id": fid, "result": {"yearly_train_mean": {int(y): float(v) for y, v in yearly.items()},
                                      "opposite_sign_years": opposite, "years": int(len(yearly))},
                "downgrade": opposite > len(yearly) / 2,
                "note": "%d of %d train years have the opposite sign to validation" % (opposite, len(yearly))}
    if fid == "F3":
        if plan["family"] != "stock_long":
            return {"id": fid, "result": None, "downgrade": False, "note": "not run: stock_long only"}
        res = {}
        for h in (5, 20):
            trades, _ = backtest_run(panel, plan, horizon=h)
            res[h] = stats(trades, panel.calendar)["validation"]
        bad = all(res[h]["mean"] is None or res[h]["mean"] <= 0 for h in res)
        return {"id": fid, "result": {"horizon_5": res[5], "horizon_20": res[20]}, "downgrade": bad,
                "note": "validation mean at 5 days %s, at 20 days %s" % (_pct(res[5]["mean"]), _pct(res[20]["mean"]))}
    if fid == "F4":
        val = base_trades[base_trades["split"] == "validation"] if len(base_trades) else base_trades
        if not len(val):
            return {"id": fid, "result": None, "downgrade": False, "note": "skipped: no validation trades"}
        top = val.groupby("ticker")["ret"].sum().idxmax()
        trades, _ = backtest_run(panel, plan, exclude_tickers=(top,))
        s = stats(trades, panel.calendar)["validation"]
        return {"id": fid, "result": {"removed_ticker": top, "validation": s},
                "downgrade": s["mean"] is None or s["mean"] <= 0,
                "note": "without %s the validation mean is %s" % (top, _pct(s["mean"]))}
    raise ValueError("unknown follow-up %r" % fid)


def _pct(x):
    return "n/a" if x is None else "%+.2f%%" % (100 * x)

"""Statistics and coded checks (AUDITOR_SPEC section 7).

bootstrap_mean: block bootstrap over 10-trading-day blocks of entry dates, 2000 resamples, reporting the 2.5th
and 97.5th percentiles of the mean. paired_lower_bound resamples the same blocks for two trade sets.
"""
import numpy as np
import pandas as pd

BLOCK_DAYS = 10
N_BOOT = 2000
VALIDATION_END = pd.Timestamp("2026-06-30")
MIN_N, MIN_BLOCKS = 30, 6
FIVE_PCT_LINE = ("About 5% of plans with no real edge pass this test by chance; testing many variants of one "
                 "idea raises that.")


class LeakageError(AssertionError):
    pass


def assert_no_leakage(dates, cutoff=VALIDATION_END):
    """Raise LeakageError if any setup/feature date is after the validation window."""
    dates = pd.to_datetime(pd.Series(dates))
    if len(dates) and dates.max() > cutoff:
        raise LeakageError("date %s is after the cutoff %s" % (dates.max().date(), cutoff.date()))


def _positions(dates, calendar):
    return np.asarray(calendar.searchsorted(pd.DatetimeIndex(dates)), dtype=int)


def block_ids(dates, calendar):
    return _positions(dates, calendar) // BLOCK_DAYS


def _block_sums(dates, returns, calendar, block_index):
    """Per-block (sum, count) arrays aligned to block_index (a dict block id -> position)."""
    sums, counts = np.zeros(len(block_index)), np.zeros(len(block_index))
    for b, r in zip(block_ids(dates, calendar), np.asarray(returns, dtype=float)):
        sums[block_index[b]] += r
        counts[block_index[b]] += 1
    return sums, counts


def bootstrap_mean(dates, returns, calendar, n_boot=N_BOOT, seed=0):
    """(2.5th, 97.5th percentile) of the mean under a block bootstrap. (nan, nan) with no trades."""
    returns = np.asarray(returns, dtype=float)
    if len(returns) == 0:
        return (float("nan"), float("nan"))
    blocks = sorted(set(block_ids(dates, calendar)))
    if len(blocks) < 2:
        m = float(returns.mean())
        return (m, m)
    index = {b: i for i, b in enumerate(blocks)}
    sums, counts = _block_sums(dates, returns, calendar, index)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(blocks), size=(n_boot, len(blocks)))
    means = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    return (float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)))


def paired_lower_bound(dates_a, ret_a, dates_b, ret_b, calendar, n_boot=N_BOOT, seed=0):
    """2.5th percentile of (mean_a - mean_b) over the same resampled blocks (the union of both block sets)."""
    ret_a, ret_b = np.asarray(ret_a, dtype=float), np.asarray(ret_b, dtype=float)
    if len(ret_a) == 0 or len(ret_b) == 0:
        return float("nan")
    blocks = sorted(set(block_ids(dates_a, calendar)) | set(block_ids(dates_b, calendar)))
    index = {b: i for i, b in enumerate(blocks)}
    sa, ca = _block_sums(dates_a, ret_a, calendar, index)
    sb, cb = _block_sums(dates_b, ret_b, calendar, index)
    if len(blocks) < 2:
        return float(ret_a.mean() - ret_b.mean())
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, len(blocks), size=(n_boot, len(blocks)))
    with np.errstate(invalid="ignore", divide="ignore"):
        diff = sa[picks].sum(axis=1) / ca[picks].sum(axis=1) - sb[picks].sum(axis=1) / cb[picks].sum(axis=1)
    diff = diff[np.isfinite(diff)]
    return float(np.percentile(diff, 2.5)) if len(diff) else float("nan")


def worst_window(trades, calendar):
    """Worst sum of trade returns over any 10-trading-day window of entry dates (0 with no trades)."""
    if len(trades) == 0:
        return 0.0
    pos = _positions(trades["entry_date"], calendar)
    daily = np.zeros(pos.max() + BLOCK_DAYS + 1)
    np.add.at(daily, pos, trades["ret"].to_numpy(float))
    rolling = np.convolve(daily, np.ones(BLOCK_DAYS), mode="valid")
    return float(min(rolling.min(), 0.0))


def stats(trades, calendar):
    if len(trades) == 0:
        return {"n": 0, "blocks": 0, "win_rate": 0.0, "mean": 0.0, "median": 0.0, "ci_low": 0.0, "ci_high": 0.0,
                "worst_trade": 0.0, "worst_window": 0.0}
    r = trades["ret"].to_numpy(float)
    lo, hi = bootstrap_mean(trades["entry_date"], r, calendar)
    return {"n": int(len(r)), "blocks": int(len(set(block_ids(trades["entry_date"], calendar)))),
            "win_rate": float((r > 0).mean()), "mean": float(r.mean()), "median": float(np.median(r)),
            "ci_low": lo, "ci_high": hi, "worst_trade": float(r.min()), "worst_window": worst_window(trades, calendar)}


def equity_curve(trades, max_points=300):
    """[[entry date iso, cumulative return], ...] by entry date, downsampled evenly to at most max_points."""
    if len(trades) == 0:
        return []
    t = trades.sort_values("entry_date")
    cum = t["ret"].to_numpy(float).cumsum()
    dates = [d.date().isoformat() for d in pd.DatetimeIndex(t["entry_date"])]
    idx = np.unique(np.linspace(0, len(cum) - 1, min(max_points, len(cum))).round().astype(int))
    return [[dates[i], float(cum[i])] for i in idx]


def histogram(returns, bins=20):
    r = np.asarray(returns, dtype=float)
    r = r[np.isfinite(r)]
    if len(r) == 0:
        return {"edges": [], "counts": []}
    p1, p99 = np.percentile(r, 1), np.percentile(r, 99)
    if p99 <= p1:
        p99 = p1 + 1e-9
    edges = np.linspace(p1, p99, bins + 1)
    inner, _ = np.histogram(r[(r >= p1) & (r <= p99)], bins=edges)
    counts = [int((r < p1).sum())] + [int(c) for c in inner] + [int((r > p99).sum())]
    return {"edges": [float(e) for e in edges], "counts": counts}


def tail_risk(all_trades, family, validation_total_gain, calendar=None):
    """Worst trade and worst 10-day window on train plus validation; the straddle_sell downgrade rule."""
    calendar = calendar if calendar is not None else pd.DatetimeIndex(sorted(set(pd.DatetimeIndex(all_trades["entry_date"])))) if len(all_trades) else pd.DatetimeIndex([])
    if len(all_trades) == 0:
        return {"worst_trade": 0.0, "worst_window": 0.0, "fails": False}
    r = all_trades["ret"].to_numpy(float)
    out = {"worst_trade": float(r.min()), "worst_window": worst_window(all_trades, calendar), "fails": False}
    if family == "straddle_sell":
        premium = all_trades["premium"].to_numpy(float)
        avg = float(premium.mean()) if len(premium) else 0.0
        loss_pct = r * premium                        # return x premium share = % of stock price
        out["worst_trade_pct"] = float(loss_pct.min())
        out["worst_trade_premiums"] = float((loss_pct / avg).min()) if avg else float(r.min())
        out["worst_window_vs_gain"] = {"worst_window": out["worst_window"], "validation_total_gain": float(validation_total_gain)}
        out["fails"] = bool(out["worst_trade_premiums"] < -5 or -out["worst_window"] > validation_total_gain)
    return out


def coded_checks(results, registry_count):
    """The 7 always-run Naysayer checks as {check, passed, value, note}."""
    plan = results["plan"]
    val, train = results["base"]["validation"], results["base"]["train"]
    out = []
    out.append({"check": "evidence", "passed": bool(val["n"] >= MIN_N and val["blocks"] >= MIN_BLOCKS),
                "value": {"n": val["n"], "blocks": val["blocks"]},
                "note": "validation needs n >= %d and at least %d distinct 10-trading-day blocks" % (MIN_N, MIN_BLOCKS)})
    dates_max = results.get("dates_max")
    out.append({"check": "leakage", "passed": True, "value": str(pd.Timestamp(dates_max).date()) if dates_max is not None else None,
                "note": "no feature or trade date after %s (earnings features exempt, see caveat)" % VALIDATION_END.date()})
    decay_ok = bool(val["mean"] > 0 and val["mean"] >= 0.5 * train["mean"])
    out.append({"check": "decay", "passed": decay_ok, "value": {"train_mean": train["mean"], "validation_mean": val["mean"]},
                "note": "validation mean %+.2f%% vs train mean %+.2f%%" % (100 * val["mean"], 100 * train["mean"])})
    out.append({"check": "shared_window", "passed": True, "value": int(registry_count),
                "note": "%d earlier audit(s) used this validation window. %s" % (registry_count, FIVE_PCT_LINE)})
    if plan["family"].startswith("straddle"):
        drops = results.get("drops", {}).get("validation", {})
        share = drops.get("earnings_in_window", 0) / val["n"] if val["n"] else 0.0
        stricter = results.get("stricter") or {}
        s_val = stricter.get("validation") if stricter else None
        passed = bool(s_val and s_val.get("ci_low", 0) > 0)
        out.append({"check": "cost_realism", "passed": passed,
                    "value": {"earnings_share": share, "stricter_ci_low": s_val.get("ci_low") if s_val else None},
                    "note": "%.0f%% of validation trades had earnings in the window (priced x1.20); stricter-cost lower bound %s"
                            % (100 * share, "%+.2f%%" % (100 * s_val["ci_low"]) if s_val else "n/a")})
    else:
        out.append({"check": "cost_realism", "passed": True, "value": None, "note": "stock_long: no fees or slippage modeled"})
    tail = results.get("tail") or {}
    out.append({"check": "tail_risk", "passed": not tail.get("fails", False),
                "value": {k: v for k, v in tail.items() if k != "fails"},
                "note": "worst trade %+.2f%%, worst 10-day window %+.2f%% (train plus validation)"
                        % (100 * tail.get("worst_trade", 0), 100 * tail.get("worst_window", 0))})
    out.append({"check": "data_drops", "passed": True, "value": results.get("drops", {}),
                "note": "setups dropped for exits past the cutoff or the data, stale implied vol, missing earnings coverage"})
    return out

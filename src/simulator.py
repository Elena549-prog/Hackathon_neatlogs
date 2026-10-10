"""Paper-trade simulator, plus the first-hit rule shared with the backtest tool.

The rule is the label rule from src/labels.py, generalized to any stop and target:
a long position wins if High reaches the target before Low reaches the stop, loses if
the stop comes first or both happen on the same day (conservative), and expires at the
Adj Close on the last day of the horizon if neither happens.
"""


def first_hit(close, high, low, t_index, entry, stop, target, horizon):
    """(outcome, exit_price) for a long opened at `entry` on row t_index.

    `close`, `high`, `low` are sequences on the Adj Close scale (see labels.adjusted_high_low).
    Only rows t_index+1 .. t_index+horizon are read.
    """
    if t_index + horizon >= len(close):
        raise ValueError("row %d has no t+%d in the data" % (t_index, horizon))
    for i in range(t_index + 1, t_index + horizon + 1):
        if low[i] <= stop:      # covers "stop first" and "both on the same day"
            return "loss", stop
        if high[i] >= target:
            return "win", target
    return "expired", float(close[t_index + horizon])


def simulate(plan, market, ticker, date):
    """Close an approved plan on future prices. Call only after the decision is logged."""
    close, high, low = market.arrays[ticker]
    t_index = market.row_index(ticker, date)
    outcome, exit_price = first_hit(close, high, low, t_index, plan["entry"], plan["stop"],
                                    plan["target"], plan["horizon_days"])
    return {"trade_outcome": outcome, "pnl_pct": exit_price / plan["entry"] - 1}

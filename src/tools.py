"""The swarm's market data and its two tools: get_prices and backtest.

Leakage guard: both tools only use information available at the decision date.
get_prices never returns rows after it, and backtest only counts past setups whose
whole 10-day outcome window ended before it.
"""
import math
import operator
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.data import TICKERS, load_prices
from src.labels import HORIZON, SETUPS_PATH, adjusted_high_low

OPS = {">": operator.gt, "<": operator.lt, ">=": operator.ge, "<=": operator.le}
Z95 = 1.96


@dataclass
class Market:
    prices: dict            # ticker -> DataFrame indexed by date: Adj Close, High, Low (High/Low adjusted)
    setups: pd.DataFrame    # data/labels/setups.csv
    arrays: dict = field(init=False)

    def __post_init__(self):
        self.arrays = {t: (df["Adj Close"].to_numpy(float), df["High"].to_numpy(float),
                           df["Low"].to_numpy(float)) for t, df in self.prices.items()}
        # Date on which each setup's label became known: the last day of its outcome window.
        self.setups["outcome_end"] = [self._outcome_end(t, d) for t, d in
                                      zip(self.setups["ticker"], self.setups["date"])]

    def _outcome_end(self, ticker, date):
        dates = self.prices[ticker].index
        i = dates.get_loc(pd.Timestamp(date)) + HORIZON
        return dates[i] if i < len(dates) else pd.NaT

    def row_index(self, ticker, date):
        return self.prices[ticker].index.get_loc(pd.Timestamp(date))


def prepare_prices(raw):
    """Yahoo prices -> Adj Close plus High/Low on the Adj Close scale."""
    high, low = adjusted_high_low(raw)
    return pd.DataFrame({"Adj Close": raw["Adj Close"], "High": high, "Low": low})


def load_market(setups_path=SETUPS_PATH, tickers=TICKERS):
    prices = {t: prepare_prices(load_prices(t)) for t in tickers}
    return Market(prices, pd.read_csv(setups_path))


def get_prices(market, ticker, end_date, lookback_days=20):
    """The last `lookback_days` rows up to and including end_date. Never anything later."""
    return market.prices[ticker].loc[: pd.Timestamp(end_date)].tail(lookback_days)


def wilson_low(wins, n, z=Z95):
    """Lower end of the 95% Wilson interval for wins / n. None when n is 0."""
    if n == 0:
        return None
    p = wins / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre - margin) / (1 + z * z / n)


def matches(df, conditions):
    """Rows of df whose feature values satisfy every condition {feature: [op, value]}."""
    keep = np.ones(len(df), dtype=bool)
    for feature, (op, value) in conditions.items():
        keep &= OPS[op](df[feature], value).to_numpy()
    return keep


def backtest(plan, market, decision_date, split="train"):
    """Train setups that satisfy the plan's conditions: n, hit rate, and its Wilson lower bound.

    Uses the labels, which answer the same fixed +5%/-3%/10-day bet every plan makes.
    Eligible setups are train setups whose label was known before decision_date;
    n counts the eligible ones that also match the conditions.
    """
    if split != "train":
        raise ValueError("backtest runs on the train split only")
    train = market.setups[market.setups["split"] == "train"]
    known = (train["outcome_end"] < pd.Timestamp(decision_date)).to_numpy()
    labels = train.loc[known & matches(train, plan["conditions"]), "label"]
    n, wins = len(labels), int(labels.sum())
    return {"n": n, "eligible": int(known.sum()), "hit_rate": wins / n if n else None,
            "hit_rate_low": wilson_low(wins, n), "conditions": plan["conditions"]}

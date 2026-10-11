"""Universe groups (AUDITOR_SPEC section 2): the 50 tickers of the 50-stock spike, as of 2025-12-31.

Survivorship bias (today's large caps) is stated in every report. The six sector groups split the 50
with no overlap; all_50 and mega_cap overlap them.
"""

ALL = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
       "JNJ", "UNH", "XOM", "PG", "MA", "HD", "CVX", "MRK", "ABBV", "PEP",
       "KO", "AVGO", "COST", "LLY", "WMT", "BAC", "PFE", "TMO", "CSCO", "MCD",
       "ABT", "CRM", "DIS", "ACN", "ADBE", "NFLX", "WFC", "TXN", "NKE", "AMD",
       "INTC", "QCOM", "HON", "UNP", "IBM", "CAT", "GS", "BA", "AMGN", "SBUX"]

GROUPS = {
    "all_50": list(ALL),
    "tech": ["AAPL", "MSFT", "NVDA", "AVGO", "CSCO", "CRM", "ACN", "ADBE", "TXN", "AMD", "INTC", "QCOM", "IBM",
             "GOOGL", "META", "NFLX", "DIS"],
    "financials": ["BRK-B", "JPM", "V", "MA", "BAC", "WFC", "GS"],
    "healthcare": ["JNJ", "UNH", "MRK", "ABBV", "LLY", "PFE", "TMO", "ABT", "AMGN"],
    "energy": ["XOM", "CVX"],
    "consumer": ["AMZN", "TSLA", "HD", "MCD", "NKE", "SBUX", "PG", "KO", "PEP", "COST", "WMT"],
    "industrials": ["HON", "UNP", "CAT", "BA"],
    "mega_cap": ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "AVGO", "TSLA", "BRK-B", "LLY"],
}
MARKET = ["SPY", "^VIX"]
SMALL_GROUPS = {"energy", "industrials"}     # usually end inconclusive for lack of trades (section 2)

assert len(ALL) == 50 == len(set(ALL))
assert sorted(t for g in ("tech", "financials", "healthcare", "energy", "consumer", "industrials")
              for t in GROUPS[g]) == sorted(ALL)

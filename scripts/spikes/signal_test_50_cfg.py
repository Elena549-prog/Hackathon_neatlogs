TICKERS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B", "JPM", "V",
           "JNJ", "UNH", "XOM", "PG", "MA", "HD", "CVX", "MRK", "ABBV", "PEP",
           "KO", "AVGO", "COST", "LLY", "WMT", "BAC", "PFE", "TMO", "CSCO", "MCD",
           "ABT", "CRM", "DIS", "ACN", "ADBE", "NFLX", "WFC", "TXN", "NKE", "AMD",
           "INTC", "QCOM", "HON", "UNP", "IBM", "CAT", "GS", "BA", "AMGN", "SBUX"]
assert len(TICKERS) == 50 == len(set(TICKERS))
TRAIN = ("2015-01-01", "2025-12-31")
VALID = ("2026-01-01", "2026-06-30")

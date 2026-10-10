"""The four swarm agents. Researcher, Planner, and Naysayer call an LLM; Mathematician is code."""

# Every LLM agent sees anonymized, normalized data, so it can't recall what happened next
# to a named stock on a known date (the validation split predates the models' knowledge cutoff).
DATA_NOTE = (
    "The data is anonymized: the asset is unnamed, no dates are given, and prices are scaled "
    "so the setup-day close is 100. Use only the data given. Do not guess the asset or use "
    "outside knowledge. This is paper trading for research, not financial advice."
)

FEATURE_GUIDE = (
    "Features: ret_Nd = close today / close N trading days ago - 1. "
    "vol_20d = standard deviation of the last 20 daily returns. "
    "close_to_maN = close today / average close of the last N days. "
    "recent_closes = the last 20 closes, scaled so today's close is 100."
)

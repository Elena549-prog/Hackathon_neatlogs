"""Mathematician: position size, max loss, and a cautious expected value. Plain arithmetic, no LLM."""
import math

ACCOUNT = 100_000   # paper account, simulated currency
RISK = 0.02         # risk per trade, share of the account
MIN_MATCHES = 30    # fewer matching past setups than this is too little evidence
MAX_SHARE = 0.80    # matching more than this share of eligible setups is no real thesis (judgment call, SWARM_SPEC 14.8)


def run(plan, backtest, account=ACCOUNT, risk=RISK):
    """p is the Wilson lower bound of the matched hit rate, not the plain rate (SWARM_SPEC section 7)."""
    entry, stop, target = plan["entry"], plan["stop"], plan["target"]
    risk_per_share = entry - stop
    size = math.floor(account * risk / risk_per_share)
    n, eligible = backtest["n"], backtest["eligible"]
    p = backtest["hit_rate_low"]
    ev = None if p is None else p * (target - entry) - (1 - p) * (entry - stop)
    return {
        "n": n,
        "eligible": eligible,
        "match_share": n / eligible if eligible else None,
        "hit_rate": backtest["hit_rate"],
        "hit_rate_low": p,
        "conditions": backtest["conditions"],
        "ev_per_share": ev,
        "ev_pct": None if ev is None else ev / entry,
        "reward_risk": (target - entry) / risk_per_share,
        "size": size,
        "max_loss": size * risk_per_share,
        "gate_passed": n >= MIN_MATCHES and n <= MAX_SHARE * eligible and ev is not None and ev > 0,
    }

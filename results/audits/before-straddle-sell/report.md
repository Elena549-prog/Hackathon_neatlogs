# Strategy Auditor report: KILLED

straddle_sell on mega_cap (10 tickers): enter when vol_20d < 0.02; hold 10 days. Not tested: Transaction costs, bid-ask spreads, margin requirements, and capital requirements; Assignment and early exercise risk; Earnings risk, dividends, and interest rate effects; Implied volatility dynamics; trigger is based only on realized volatility; Intraday timing and option pricing beyond using the close.

## 1. What was tested and the verdict

**Verdict: KILLED.** validation mean <= 0 with enough evidence

Headline: validation n = 70, mean per trade -10.18%, lower bound -23.94%, paired lower bound vs baseline -21.37%.

## 2. Idea, plan v0, assumptions

Idea: sell straddles on low-volatility mega-caps

Plan v0 (frozen before any backtest), SHA-256 `b74d3ad7f116e97f32370423749c125f3c5cf73c9f5d32f7f5c07382eb0fd484`:

```json
{
  "assumptions": [
    "'low-volatility' is read as trailing 20-day daily return standard deviation (vol_20d) below 0.02.",
    "'sell straddles' is read as selling an at-the-money straddle at the close and holding for 10 days with no exit management.",
    "Universe is limited to the mega_cap group as specified."
  ],
  "conditions": {
    "vol_20d": [
      "<",
      0.02
    ]
  },
  "core_trigger_tested": true,
  "family": "straddle_sell",
  "hypothesis": "Selling at-the-money straddles on mega-cap stocks with low 20-day realized volatility is profitable over a 10-day holding period.",
  "not_tested": [
    "Transaction costs, bid-ask spreads, margin requirements, and capital requirements",
    "Assignment and early exercise risk",
    "Earnings risk, dividends, and interest rate effects",
    "Implied volatility dynamics; trigger is based only on realized volatility",
    "Intraday timing and option pricing beyond using the close"
  ],
  "refused": false,
  "universe_group": "mega_cap"
}
```

Assumptions: 'low-volatility' is read as trailing 20-day daily return standard deviation (vol_20d) below 0.02.; 'sell straddles' is read as selling an at-the-money straddle at the close and holding for 10 days with no exit management.; Universe is limited to the mega_cap group as specified..
Not tested: Transaction costs, bid-ask spreads, margin requirements, and capital requirements; Assignment and early exercise risk; Earnings risk, dividends, and interest rate effects; Implied volatility dynamics; trigger is based only on realized volatility; Intraday timing and option pricing beyond using the close.
Universe: mega_cap = AAPL, MSFT, NVDA, GOOGL, AMZN, META, AVGO, TSLA, BRK-B, LLY.

## 3. Data coverage

| Ticker | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AAPL | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| MSFT | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| NVDA | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| GOOGL | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| AMZN | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| META | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| AVGO | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| TSLA | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| BRK-B | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| LLY | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |

Skipped tickers (under 200 rows): none.
Implied vol rows: 11321, 2019-06-01 to 2026-06-30.
Earliest earnings date per ticker: AAPL 2002-04-17, AMZN 2002-04-23, AVGO 2009-12-03, BRK-B 2010-05-07, GOOGL 2004-10-21, LLY 2002-01-24, META 2012-07-26, MSFT 2002-01-17, NVDA 2002-05-22, TSLA 2010-11-09.
Dropped train setups: exit_after_cutoff 34, exit_past_data 0, stale_iv 400, earnings_in_window 140.
Dropped validation setups: exit_after_cutoff 0, exit_past_data 0, stale_iv 0, earnings_in_window 11.

## 4. Results

| Run | n | blocks | win | mean | median | 95% interval | worst trade / 10-day window |
|---|---|---|---|---|---|---|---|
| v0 train | 780 | 144 | 58% | -4.44% | +16.26% | [-11.83%, +2.56%] | -437.80% / -1276.54% |
| v0 validation | 70 | 12 | 53% | -10.18% | +2.57% | [-23.94%, +4.18%] | -208.37% / -440.97% |
| no-condition baseline, train | 1267 | 143 | 58% | -5.22% | +15.60% | [-12.76%, +1.80%] | -634.49% / -1729.75% |
| no-condition baseline, validation | 120 | 12 | 59% | +2.02% | +18.41% | [-12.69%, +18.35%] | -204.22% / -482.46% |
| random selection at the same rate, validation (reported only) | 76 | 12 | 62% | +8.23% | +24.51% | [-5.91%, +23.84%] | -204.22% / -210.23% |
| stricter cost (+10% buyer / -10% seller), validation | 70 | 12 | 46% | -22.42% | -8.25% | [-37.71%, -6.47%] | -242.63% / -556.64% |

Paired lower bound (v0 minus baseline, validation, 2.5th percentile): -21.37%.
Tail risk (train plus validation): worst trade -437.80%, worst 10-trading-day window -1276.54%. Seller losses: worst trade -5.9 average premiums (-25.26% of stock price); worst window -1276.54% vs total validation gain -712.45%.

## 5. Coded checks and follow-ups

| Check | Passed | Note |
|---|---|---|
| evidence | yes | validation needs n >= 30 and at least 6 distinct 10-trading-day blocks |
| leakage | yes | no feature or trade date after 2026-06-30 (earnings features exempt, see caveat) |
| decay | no | validation mean -10.18% vs train mean -4.44% |
| shared_window | yes | 2 earlier audit(s) used this validation window. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that. |
| cost_realism | no | 16% of validation trades had earnings in the window (priced x1.20); stricter-cost lower bound -37.71% |
| tail_risk | no | worst trade -437.80%, worst 10-day window -1276.54% (train plus validation) |
| data_drops | yes | setups dropped for exits past the cutoff or the data, stale implied vol, missing earnings coverage |

Follow-ups: none run.
Note: follow-ups disabled for this run (--no-followups, the M1 behaviour).

## 6. Shared validation window

2 audit(s) have used this validation window before this one. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that.

## 7. Naysayer critique and Reporter prose

Naysayer: This backtest does not support the strategy. The validation mean is more negative than the training mean and the no-condition baseline is positive in validation, so the low-vol trigger appears to subtract value rather than add it. Costs were not included; once a stricter cost assumption is applied, both training and validation means become significantly negative. The tail risk is severe, with a worst 10-day window far larger than the entire validation gain, and earnings exposure in 16% of validation trades adds understated risk. The validation sample is small (70 trades, 12 blocks) and the shared validation window raises multiple-testing concerns. The high stale-IV drop count in training also suggests the trigger may be selecting illiquid or stale-priced options.

Reporter: This report tested a rule for selling at-the-money straddles on ten large-cap stocks only when their recent 20-day realized volatility was below 0.02, holding each trade for 10 days. The numbers shown say the validation sample averaged a loss of about 10.18% per trade, and once a stricter cost assumption was added that average fell further, while a no-condition baseline in the same period was slightly positive. That means, in this run, the low-volatility filter did not improve results and the range of outcomes included very large losing trades and 10-day windows. The report also flags that transaction costs, spreads, margin, assignment and early-exercise risk, dividends, and implied volatility were not tested, so any hobby trader should read these figures as a limited, cost-ignorant backtest rather than a complete picture. This is not financial advice.

## 8. Recoveries

none

## 9. Cost and trace

LLM calls: 3 (prompt tokens 5965, completion tokens 2886), cost $0.0161 (upper bound). neatlogs trace: bc31519223fc7c69c530c8fef758d552.

## 10. Disclaimer

Not financial advice. Survivorship bias: the universe is today's large caps. One validation window (2026-01-01 to 2026-06-30) shared by every audit. Costs are approximated (no fees for stocks; straddle costs from an ATM formula with haircuts). No position sizing is given.

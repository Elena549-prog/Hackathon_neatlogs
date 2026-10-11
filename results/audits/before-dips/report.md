# Strategy Auditor report: INCONCLUSIVE

stock_long on all_50 (50 tickers): enter when close_to_ma200 > 1.0 and ret_5d < 0.0; exit at +5% / -5% / 10 days. Not tested: Intraday entry/exit timing; Alternative trend definitions such as moving average crossovers or slope; Transaction costs and slippage; Fundamental or news context.

## 1. What was tested and the verdict

**Verdict: INCONCLUSIVE.** positive but not convincing: lower bound of the validation mean is not above 0; paired lower bound against the no-condition baseline is not above 0; train mean is not above the train baseline mean

*inconclusive: a strategy with no real edge lands here about half the time*

Headline: validation n = 400, mean per trade +0.43%, lower bound -0.23%, paired lower bound vs baseline -0.47%.

## 2. Idea, plan v0, assumptions

Idea: buy dips in an uptrend

Plan v0 (frozen before any backtest), SHA-256 `5ae9d55123b8d31db456409187645001160aa4eab5739dceb6fe095748ae7c63`:

```json
{
  "assumptions": [
    "'Buy dips' read as buying after a negative 5-day return.",
    "'Uptrend' read as close above its 200-day moving average.",
    "Universe defaulted to all_50 because none was specified.",
    "Exit after 10 trading days unless a 5% gain target or 5% stop loss triggers."
  ],
  "conditions": {
    "close_to_ma200": [
      ">",
      1.0
    ],
    "ret_5d": [
      "<",
      0.0
    ]
  },
  "core_trigger_tested": true,
  "exit": {
    "horizon_days": 10,
    "stop_pct": 0.05,
    "target_pct": 0.05
  },
  "family": "stock_long",
  "hypothesis": "Buying stocks in an uptrend (close above 200-day average) after a short-term dip (negative 5-day return) will outperform over a 10-day horizon.",
  "not_tested": [
    "Intraday entry/exit timing",
    "Alternative trend definitions such as moving average crossovers or slope",
    "Transaction costs and slippage",
    "Fundamental or news context"
  ],
  "refused": false,
  "universe_group": "all_50"
}
```

Assumptions: 'Buy dips' read as buying after a negative 5-day return.; 'Uptrend' read as close above its 200-day moving average.; Universe defaulted to all_50 because none was specified.; Exit after 10 trading days unless a 5% gain target or 5% stop loss triggers..
Not tested: Intraday entry/exit timing; Alternative trend definitions such as moving average crossovers or slope; Transaction costs and slippage; Fundamental or news context.
Universe: all_50 = AAPL, MSFT, GOOGL, AMZN, NVDA, META, TSLA, BRK-B, JPM, V, JNJ, UNH, XOM, PG, MA, HD, CVX, MRK, ABBV, PEP, KO, AVGO, COST, LLY, WMT, BAC, PFE, TMO, CSCO, MCD, ABT, CRM, DIS, ACN, ADBE, NFLX, WFC, TXN, NKE, AMD, INTC, QCOM, HON, UNP, IBM, CAT, GS, BA, AMGN, SBUX.

## 3. Data coverage

| Ticker | 2014 | 2015 | 2016 | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AAPL | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| MSFT | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| GOOGL | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| AMZN | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| NVDA | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| META | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| TSLA | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| BRK-B | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| JPM | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| V | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| JNJ | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| UNH | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| XOM | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| PG | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| MA | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| HD | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| CVX | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| MRK | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| ABBV | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| PEP | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| KO | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| AVGO | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| COST | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| LLY | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| WMT | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| BAC | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| PFE | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| TMO | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| CSCO | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| MCD | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| ABT | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| CRM | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| DIS | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| ACN | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| ADBE | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| NFLX | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| WFC | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| TXN | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| NKE | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| AMD | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| INTC | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| QCOM | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| HON | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| UNP | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| IBM | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| CAT | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| GS | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| BA | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| AMGN | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |
| SBUX | 252 | 252 | 252 | 251 | 251 | 252 | 253 | 252 | 251 | 250 | 252 | 250 | 143 |

Skipped tickers (under 200 rows): none.
Earliest earnings date per ticker: AAPL 2002-04-17, ABBV 2013-03-15, ABT 2002-01-16, ACN 2002-04-11, ADBE 2002-03-14, AMD 2002-01-16, AMGN 2002-04-25, AMZN 2002-04-23, AVGO 2009-12-03, BA 2002-01-23, BAC 2002-04-15, BRK-B 2010-05-07, CAT 2002-01-23, COST 2002-03-05, CRM 2004-08-19, CSCO 2002-05-07, CVX 2002-01-29, DIS 2002-01-31, GOOGL 2004-10-21, GS 2001-12-20, HD 2002-02-26, HON 2002-04-18, IBM 2002-01-17, INTC 2002-04-16, JNJ 2002-01-22, JPM 2002-01-16, KO 2002-01-29, LLY 2002-01-24, MA 2006-08-02, MCD 2002-01-24, META 2012-07-26, MRK 2002-01-22, MSFT 2002-01-17, NFLX 2002-07-24, NKE 2002-03-21, NVDA 2002-05-22, PEP 2002-02-06, PFE 2002-01-23, PG 2002-01-31, QCOM 2002-01-24, SBUX 2002-04-25, TMO 2002-02-13, TSLA 2010-11-09, TXN 2002-01-28, UNH 2002-01-24, UNP 2002-01-24, V 2008-04-28, WFC 2002-01-15, WMT 2002-05-14, XOM 2002-01-23.
Dropped train setups: exit_after_cutoff 106, exit_past_data 0.
Dropped validation setups: exit_after_cutoff 0, exit_past_data 0.

## 4. Results

| Run | n | blocks | win | mean | median | 95% interval | worst trade / 10-day window |
|---|---|---|---|---|---|---|---|
| v0 train | 8062 | 277 | 56% | +0.43% | +0.79% | [+0.18%, +0.66%] | -17.21% / -367.87% |
| v0 validation | 400 | 14 | 56% | +0.43% | +1.11% | [-0.23%, +1.07%] | -12.70% / -101.44% |
| no-condition baseline, train | 17781 | 277 | 56% | +0.46% | +0.86% | [+0.24%, +0.66%] | -29.66% / -846.97% |
| no-condition baseline, validation | 977 | 14 | 53% | +0.31% | +0.85% | [-0.34%, +0.96%] | -16.40% / -223.10% |
| random selection at the same rate, validation (reported only) | 359 | 14 | 49% | -0.09% | -0.09% | [-0.93%, +0.82%] | -14.66% / -106.43% |

Paired lower bound (v0 minus baseline, validation, 2.5th percentile): -0.47%.
Tail risk (train plus validation): worst trade -17.21%, worst 10-trading-day window -367.87%.

## 5. Coded checks and follow-ups

| Check | Passed | Note |
|---|---|---|
| evidence | yes | validation needs n >= 30 and at least 6 distinct 10-trading-day blocks |
| leakage | yes | no feature or trade date after 2026-06-30 (earnings features exempt, see caveat) |
| decay | yes | validation mean +0.43% vs train mean +0.43% |
| shared_window | yes | 0 earlier audit(s) used this validation window. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that. |
| cost_realism | yes | stock_long: no fees or slippage modeled |
| tail_risk | yes | worst trade -17.21%, worst 10-day window -367.87% (train plus validation) |
| data_drops | yes | setups dropped for exits past the cutoff or the data, stale implied vol, missing earnings coverage |

Follow-ups: none run.
Note: follow-ups disabled for this run (--no-followups, the M1 behaviour).

## 6. Shared validation window

0 audit(s) have used this validation window before this one. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that.

## 7. Naysayer critique and Reporter prose

Naysayer: The validation evidence is thin: only 400 trades across 14 blocks, with a confidence interval spanning zero and negative values, so the out-of-sample mean is not clearly distinguishable from zero. The strategy's edge over the no-condition baseline is weak or reversed on training (0.427% vs 0.456% mean), and the paired difference's lower bound is negative, suggesting the entry condition may not add reliable value. Reported returns assume no fees or slippage, which likely consumes most of the 0.43% average gain in a long-only, 10-day holding setup. Tail risk is severe with a worst trade of -17.2% despite a -5% stop and a worst 10-day window of -367.9%, pointing to gap or compounding risk. Dropped exits and the single tested rule among many possible variants also raise concern that the result is optimistic or curve-fit.

Reporter: This test checked whether buying large-cap stocks after a 5-day dip while they were above their 200-day average would lead to gains over the next 10 days or until a 5% profit or loss was hit. The average result was slightly positive, but the statistical range still includes negative outcomes, so the evidence is not strong enough to say the pattern reliably works. The strategy did not clearly beat a simple baseline of buying without the dip condition. These numbers are historical only and do not predict future results; this is not financial advice.

## 8. Recoveries

none

## 9. Cost and trace

LLM calls: 3 (prompt tokens 7695, completion tokens 4612), cost $0.0232 (upper bound). neatlogs trace: 94803f1af610b26a654915d8c031c83e.

## 10. Disclaimer

Not financial advice. Survivorship bias: the universe is today's large caps. One validation window (2026-01-01 to 2026-06-30) shared by every audit. Costs are approximated (no fees for stocks; straddle costs from an ATM formula with haircuts). No position sizing is given.

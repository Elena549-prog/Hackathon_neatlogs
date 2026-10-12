# Strategy Auditor report: INCONCLUSIVE

stock_long on all_50 (50 tickers): enter when close_to_ma200 > 1 and ret_5d < 0; exit at +10% / -10% / 10 days. Not tested: intraday timing or buying at the exact low; fundamental or news catalysts; position sizing or portfolio allocation.

## 1. What was tested and the verdict

**Verdict: INCONCLUSIVE.** positive but not convincing: lower bound of the validation mean is not above 0; paired lower bound against the no-condition baseline is not above 0; train mean is not above the train baseline mean

*inconclusive: a strategy with no real edge lands here about half the time*

Headline: validation n = 303, mean per trade +0.96%, lower bound -0.25%, paired lower bound vs baseline -0.85%.

## 2. Idea, plan v0, assumptions

Idea: buy dips in an uptrend

Plan v0 (frozen before any backtest), SHA-256 `f750097799e4a98b2bfeb5940aaf5f3009ab8956f4b5347d9aef0f9552aeec4f`:

```json
{
  "assumptions": [
    "'uptrend' read as close above its 200-day average",
    "'dips' read as a negative 5-day return at the close",
    "long-only entry at the close"
  ],
  "conditions": {
    "close_to_ma200": [
      ">",
      1
    ],
    "ret_5d": [
      "<",
      0
    ]
  },
  "core_trigger_tested": true,
  "exit": {
    "horizon_days": 10,
    "stop_pct": 0.1,
    "target_pct": 0.1
  },
  "family": "stock_long",
  "hypothesis": "Buying stocks that are above their 200-day moving average after a short-term negative 5-day return will lead to positive forward returns.",
  "not_tested": [
    "intraday timing or buying at the exact low",
    "fundamental or news catalysts",
    "position sizing or portfolio allocation"
  ],
  "refused": false,
  "universe_group": "all_50"
}
```

Assumptions: 'uptrend' read as close above its 200-day average; 'dips' read as a negative 5-day return at the close; long-only entry at the close.
Not tested: intraday timing or buying at the exact low; fundamental or news catalysts; position sizing or portfolio allocation.
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
Dropped train setups: exit_after_cutoff 109, exit_past_data 0.
Dropped validation setups: exit_after_cutoff 0, exit_past_data 0.

Earnings caveat: actual report dates are used; companies usually announce dates weeks ahead, so the look-ahead is small but not zero.

## 4. Results

| Run | n | blocks | win | mean | median | 95% interval | worst trade / 10-day window |
|---|---|---|---|---|---|---|---|
| v0 train | 6940 | 276 | 57% | +0.52% | +0.71% | [+0.16%, +0.88%] | -24.26% / -512.35% |
| v0 validation | 303 | 14 | 56% | +0.96% | +0.85% | [-0.25%, +2.09%] | -14.74% / -108.46% |
| no-condition baseline, train | 13457 | 277 | 57% | +0.63% | +0.77% | [+0.27%, +0.95%] | -31.10% / -1169.87% |
| no-condition baseline, validation | 657 | 14 | 54% | +0.63% | +0.66% | [-0.39%, +1.65%] | -25.71% / -188.90% |
| random selection at the same rate, validation (reported only) | 282 | 13 | 56% | +0.44% | +0.90% | [-1.13%, +1.79%] | -25.71% / -112.47% |

Paired lower bound (v0 minus baseline, validation, 2.5th percentile): -0.85%.
Tail risk (train plus validation): worst trade -24.26%, worst 10-trading-day window -512.35%.

## 5. Coded checks and follow-ups

| Check | Passed | Note |
|---|---|---|
| evidence | yes | validation needs n >= 30 and at least 6 distinct 10-trading-day blocks |
| leakage | yes | no feature or trade date after 2026-06-30 (earnings features exempt, see caveat) |
| decay | yes | validation mean +0.96% vs train mean +0.52% |
| shared_window | yes | 3 earlier audit(s) used this validation window. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that. |
| cost_realism | yes | stock_long: no fees or slippage modeled |
| tail_risk | yes | worst trade -24.26%, worst 10-day window -512.35% (train plus validation) |
| data_drops | yes | setups dropped for exits past the cutoff or the data, stale implied vol, missing earnings coverage |

Follow-ups (chosen by the Naysayer, run in code on plan v0; a met rule only turns promising into inconclusive):
- F1 Earnings excluded. Naysayer's reason: The +0.96% validation mean over 303 trades may be inflated by earnings jumps inside the 10-day holding window, so excluding earnings tests whether the non-news signal remains positive. Result: validation mean +0.98% over 261 trades (42 left out: earnings in the holding window; 0: no earnings coverage). Downgrade rule not met.
- F3 Horizon sensitivity. Naysayer's reason: The strategy is built around a 10-day exit and shows a small validation mean (+0.96%), so if 5- and 20-day horizons both fail, the result is likely horizon-specific overfitting. Result: horizon 5 days: validation mean +0.42% over 424 trades; horizon 20 days: validation mean +0.89% over 213 trades. Downgrade rule not met.
- F4 Concentration. Naysayer's reason: With 303 validation trades across 50 tickers and a mean near +1%, a single ticker's outsized contribution could drive the entire result. Result: without the top-contributing ticker (its validation trades sum to +57.58%; all validation trades sum to +289.66%): validation mean +0.79% over 293 trades. Top-contributing ticker: AMD. Downgrade rule not met.

## 6. Shared validation window

3 audit(s) have used this validation window before this one. About 5% of plans with no real edge pass this test by chance; testing many variants of one idea raises that.

## 7. Naysayer critique and Reporter prose

Naysayer's doubts before the follow-ups: Validation CI includes zero (mean +0.00956, CI -0.00249 to +0.02092), so the positive validation mean is not statistically reliable.; The base validation mean is only slightly above the baseline validation mean (+0.00635) and paired_ci_low is -0.00854, so the edge over baseline is not confirmed.; No fees or slippage are modeled, and with only 14 validation blocks the small gross edge could easily disappear after costs or under temporal clustering.; Shared_window note says 3 earlier audits used this window; multiple testing raises the chance this is a false positive..

Naysayer: The validation evidence is thin: only 303 trades across 14 blocks, and the mean's confidence interval spans zero. The conditional strategy adds little over the no-condition baseline; validation mean is 0.96% versus 0.63% for baseline, and the paired lower confidence bound is negative, so the entry rule may not be a real improvement. Reported results ignore fees and slippage, which could easily erase a per-trade edge of this size. Tail risk is material, with a -24.26% worst trade and a -512.35% worst 10-day window. One ticker contributes about 19.9% of the validation profit sum, so the result is not well diversified, and 109 dropped train exits may bias the sample.

Reporter: The test checked whether buying big-name stocks after a short-term dip while they trade above their 200-day average tends to produce a positive return over the next 10 days. In the validation sample of 303 trades, the average gain was +0.96%, but the statistical range around that figure stretches below zero, and the strategy barely beat a simple baseline that ignores the dip condition. That combination is why the verdict is INCONCLUSIVE rather than a clear pass: the evidence is too thin to tell a real edge apart from chance. Separately, the worst single trade lost about 24%, a reminder that individual outcomes can be far worse than the average suggests. There is no recommendation here, only a description of what the numbers show.

## 8. Recoveries

none

## 9. Cost and trace

LLM calls: 4 (prompt tokens 9800, completion tokens 9912), cost $0.0466 (upper bound). neatlogs trace: 66f9d2d4745323068e43c84d01c9bad1.

## 10. Disclaimer

Not financial advice. Survivorship bias: the universe is today's large caps. One validation window (2026-01-01 to 2026-06-30) shared by every audit. Costs are approximated (no fees for stocks; straddle costs from an ATM formula with haircuts). No position sizing is given.

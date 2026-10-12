# Strategy Auditor: before (M1, no follow-ups) vs after (M2, follow-ups F1-F4)

Metrics fixed in AUDITOR_SPEC section 17 before any run: verdict per idea, downgrades with reasons, LLM calls, cost and wall time per audit. Expected verdicts were written in section 13 first. Cost is the wrapper's upper bound; check it against the neatlogs traces.

| Idea | Expected | Run | Verdict | Downgrades | Follow-ups (rule) | LLM calls | Cost | Wall time |
|---|---|---|---|---|---|---|---|---|
| buy dips in an uptrend | kill | before | inconclusive | none | none | 3 | $0.0232 | 45 s |
| buy dips in an uptrend | kill | after | inconclusive | none | F1 (not met), F3 (not met), F4 (not met) | 4 | $0.0466 | 87 s |
| buy straddles on tech before earnings | kill | before | kill | none | none | 3 | $0.0174 | 31 s |
| buy straddles on tech before earnings | kill | after | kill | none | none | 4 | $0.0222 | 34 s |
| sell straddles on low-volatility mega-caps | inconclusive or promising (tail risk decides) | before | kill | none | none | 3 | $0.0161 | 25 s |
| sell straddles on low-volatility mega-caps | inconclusive or promising (tail risk decides) | after | kill | none | none | 4 | $0.0365 | 66 s |

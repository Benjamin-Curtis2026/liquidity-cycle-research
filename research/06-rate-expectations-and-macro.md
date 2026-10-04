# Rate expectations, policy rules, and recession risk

<!-- REPO_ONLY -->
> This file holds the method and narrative. Results, charts, and tables are generated weekly and published on the project site.
<!-- /REPO_ONLY -->

**Question.** What path for the federal funds rate are markets pricing, how does current policy compare with standard policy rules, and what do the yield curve and the labor market say about recession risk?

## Key findings (current build)

<!-- KEY_FINDINGS -->

## Prediction markets as a rate forecast

Kalshi, a CFTC-regulated exchange, lists contracts that pay $1 if the upper bound of the federal funds target range is above a given level after a given FOMC meeting. A ladder of these contracts at 25 basis-point steps is a market-priced survival function, P(rate ≥ level), for each meeting. Differencing adjacent rungs gives the full probability distribution of the post-meeting rate, from which the study reports the expected rate, the most likely outcome, and the 10th to 90th percentile range for every listed meeting.

Polymarket lists a separate market on the next decision (hold, cut, or hike by size). Comparing the two venues is a basic consistency check: large disagreements usually reflect thin trading in one market rather than information.

Method details:

- Each contract's price is the midpoint of the best bid and ask when the spread is 10 cents or less. A contract with no bid and an ask of 5 cents or less is priced at half the ask, and one bid at 95 cents or more with no ask at halfway to $1. Otherwise the last trade is used if the contract has traded; empty or very wide books are excluded rather than read as a 50% probability.
- A meeting is reported only if its ladder has at least four priced rungs and spans both tails (one rung at 85% or higher, one at 15% or lower), and only for meetings within roughly 15 months, where contracts trade actively enough to be informative.
- Where prices on adjacent rungs violate monotonicity (a higher strike priced above a lower one), the survival function is forced to be non-increasing before differencing.
- Probabilities are normalized to sum to one.

These are risk-neutral prices, not pure forecasts. They embed risk premia and are only as reliable as the liquidity behind them; fed funds futures and SOFR options remain the institutional benchmark.

## Policy rules

Taylor (1993) proposed a simple benchmark for the policy rate:

**i = r\* + π + 0.5 (π − 2) + 0.5 (output gap)**

where π is inflation and r\* the neutral real rate. The study computes three variants using core PCE inflation and the output gap against the Congressional Budget Office's estimate of potential GDP: Taylor's original r\* of 2%, the same rule with r\* of 1% (closer to recent estimates of the neutral rate), and the "balanced approach" rule, which doubles the weight on the output gap. Comparing the actual policy rate with these benchmarks shows whether policy is tight or loose relative to the economy, and how much that judgment depends on the assumed neutral rate.

## Recession signals

- **Yield curve.** The New York Fed's published model converts the monthly average spread between the 10-year Treasury yield and the 3-month bill into a 12-month-ahead recession probability with a probit: P = Φ(−0.5333 − 0.6330 × spread). This study applies the same specification to FRED's constant-maturity spread (T10Y3M), a close approximation to the bond-equivalent bill yield the New York Fed uses.
- **Sahm rule.** The real-time Sahm rule indicator measures the rise in the three-month average unemployment rate above its low of the previous 12 months. Readings of 0.50 points or more have historically coincided with the early months of U.S. recessions, though the rule is a statistical regularity rather than a guarantee.

## Data

| Source | Series |
|:---|:---|
| Kalshi public API | KXFED rate contracts for each upcoming FOMC meeting |
| Polymarket public API | "Fed decision" market for the next meeting |
| FRED | PCEPILFE, CPIAUCSL, CPILFESL, UNRATE, PAYEMS, SAHMREALTIME, GDPC1, GDPPOT, T10Y3M, T10YIE, T5YIFR, USREC, DFEDTARU, DFEDTARL |

## Results

<!-- RESULTS -->

## Limitations

- **Prediction-market liquidity.** Contracts on distant meetings trade thinly, so their implied probabilities are noisier than those for the next meeting.
- **Rule inputs are revised.** GDP, potential output, and inflation are revised after release; the rules use current vintages, not the data available in real time (Orphanides, 2003).
- **The neutral rate is unobserved.** Policy-rule prescriptions shift one-for-one with the assumed r\*, which is why three variants are shown.
- **One-variable recession model.** The yield-curve probit ignores credit, labor, and survey data, and its coefficients were estimated on decades in which the term premium behaved differently.

## References

- Taylor, J. B. (1993). Discretion versus policy rules in practice. *Carnegie-Rochester Conference Series on Public Policy*, 39, 195–214.
- Estrella, A., and Mishkin, F. S. (1998). Predicting U.S. recessions: Financial variables as leading indicators. *Review of Economics and Statistics*, 80(1), 45–61.
- Estrella, A., and Trubin, M. R. (2006). The yield curve as a leading indicator: Some practical issues. *Current Issues in Economics and Finance*, 12(5), Federal Reserve Bank of New York.
- Sahm, C. (2019). Direct stimulus payments to individuals. In *Recession Ready: Fiscal Policies to Stabilize the American Economy*, The Hamilton Project.
- Orphanides, A. (2003). Historical monetary policy analysis and the Taylor rule. *Journal of Monetary Economics*, 50(5), 983–1022.

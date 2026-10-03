# Liquidity regime and trend: a rules-based test

<!-- REPO_ONLY -->
> This file holds the method and narrative. Results, charts, and tables are generated weekly and published on the project site.
<!-- /REPO_ONLY -->

**Question.** Does holding Bitcoin, the Nasdaq-100, or semiconductors only when Fed liquidity is expanding, the trend is up, or both, improve risk-adjusted returns relative to buy-and-hold after costs?

## Key findings (current build)

<!-- KEY_FINDINGS -->

## Rules

All rules are evaluated at the Friday weekly close and applied to the following week's return.

| Rule | Invested when | Otherwise |
|:---|:---|:---|
| Buy and hold | Always | |
| Trend | Weekly close above its 50-week SMA | 3-month T-bills |
| Liquidity | 13-week change in net liquidity is positive | 3-month T-bills |
| Liquidity and trend | Both conditions hold | 3-month T-bills |

Each switch between the asset and T-bills costs 10 basis points. Cash earns the 3-month Treasury bill rate (FRED DTB3), so time out of the market is not treated as free.

## Measures

Compound annual growth rate, annualized volatility, Sharpe ratio (excess return over T-bills divided by volatility, annualized from weekly data), maximum drawdown, share of weeks invested, and number of switches. Sharpe ratios are also reported for each half of the sample as a basic stability check: a rule whose advantage appears in only one half is more likely to reflect a single episode than a durable effect.

A separate table compares the asset's average weekly return in the week after an expanding reading with the week after a contracting reading, using Welch's t-test. Weekly returns do not overlap, so the test's assumptions are closer to satisfied than they would be for multi-week windows.

## Results

<!-- RESULTS -->

## Limitations

- **In-sample design.** The 13-week and 50-week windows were chosen before testing but were not validated out of sample. A walk-forward test that re-selects parameters on past data only is the right next step.
- **Short crypto history.** Bitcoin's usable sample begins in 2015 once the 50-week average exists, which covers roughly three full cycles.
- **Taxes and slippage.** Switching realizes gains; a taxable investor's results would differ from the pre-tax figures shown.
- **One liquidity definition.** The regime uses U.S. net liquidity only.


## References

- Moskowitz, T., Ooi, Y. H., and Pedersen, L. H. (2012). Time series momentum. *Journal of Financial Economics*, 104(2), 228–250.
- Faber, M. (2007). A quantitative approach to tactical asset allocation. *Journal of Wealth Management*, 9(4), 69–79.

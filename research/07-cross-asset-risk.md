# Cross-asset risk and financial conditions

<!-- REPO_ONLY -->
> This file holds the method and narrative. Results, charts, and tables are generated weekly and published on the project site.
<!-- /REPO_ONLY -->

**Question.** How tight are financial conditions, how much risk is each asset carrying, and are the relationships between crypto, equities, bonds, and gold stable enough to diversify across?

## Key findings (current build)

<!-- KEY_FINDINGS -->

## Why it matters

Liquidity and policy affect asset prices through financial conditions: the cost of credit, the price of volatility insurance, and the value of the dollar. Credit spreads and implied volatility tend to widen before and during drawdowns in risk assets, and the Chicago Fed's National Financial Conditions Index summarizes more than 100 money-market, debt, equity, and banking indicators in a single reading.

Correlations matter for portfolio construction. For two decades before 2022, Treasuries tended to rise when stocks fell, which made a stock-bond portfolio self-hedging. When inflation is the dominant risk, that correlation can turn positive and the hedge weakens. Bitcoin's correlation with technology stocks, and its relationship with gold, determine whether it behaves as a risk asset or as a diversifier.

## Method

- **Financial conditions.** For the VIX, high-yield and investment-grade credit spreads, the NFCI, the broad dollar index, WTI crude, and the 10-year minus 2-year spread: the latest reading, its 13-week change, and its percentile and z-score within the last five years, or within the full history available if shorter. The ICE BofA credit-spread series on FRED currently cover roughly the last three years, and the table reports the window used for each indicator.
- **Risk table.** For each asset, 13 and 52-week returns, realized volatility annualized from weekly returns, the three-year Sharpe ratio in excess of T-bills, the current drawdown from its high, and the worst drawdown of the last three years.
- **Correlations.** A matrix of weekly log-return correlations over the last two years, plus rolling 26-week correlations for Bitcoin against the Nasdaq-100, Bitcoin against gold, and the S&P 500 against long Treasuries.

## Results

<!-- RESULTS -->

## Limitations

- **Correlations are unstable.** Rolling estimates on 26 weeks of data are noisy, and correlations tend to rise toward one in market stress, when diversification is most needed.
- **Volatility is backward-looking.** Realized volatility describes the recent past; the VIX is the only forward-looking measure here.
- **Percentiles depend on the window.** A five-year window includes both the 2020 shock and the 2022 tightening, which shapes what counts as "high."

## References

- Brave, S., and Butters, R. A. (2011). Monitoring financial stability: A financial conditions index approach. *Economic Perspectives*, 35(1), Federal Reserve Bank of Chicago.
- Campbell, J. Y., Sunderam, A., and Viceira, L. M. (2017). Inflation bets or deflation hedges? The changing risks of nominal bonds. *Critical Finance Review*, 6(2), 263–301.

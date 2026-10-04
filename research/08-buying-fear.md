# Buying fear: testing fear and greed extremes

<!-- REPO_ONLY -->
> This file holds the method and narrative. Results, charts, and tables are generated weekly and published on the project site.
<!-- /REPO_ONLY -->

**Question.** Is buying when sentiment readings show fear or extreme fear rewarded? Specifically, do Bitcoin and U.S. stocks earn higher forward returns after fearful readings than on an average day, and does a rule that buys only in fear beat steady dollar-cost averaging?

## Key findings (current build)

<!-- KEY_FINDINGS -->

## Hypothesis

Contrarian investors argue that fear pushes prices below fair value, so buying when sentiment is most pessimistic should earn above-average returns. Behavioral finance gives the idea some support: Baker and Wurgler (2006) find that when investor sentiment is low, subsequent returns are relatively high for the stocks most exposed to sentiment. The counterargument is that fear often arrives early in a decline, so a buyer at the first fearful reading can face a further large drawdown before any recovery.

The study tests three versions of the claim:

1. **Regime returns.** Average forward returns at 1, 3, 6, and 12 months for every day in each sentiment regime, compared with all days.
2. **Entry events.** Forward returns from the first day the index drops into fear (below 45) or extreme fear (below 25), compared with randomly chosen days through a 5,000-draw permutation test, along with how much further the price fell over the next month.
3. **Dollar-cost averaging.** $100 set aside every week and invested immediately, only when the index shows fear, or only when it shows extreme fear, with uninvested cash earning T-bill rates.

## Sentiment measures

**Crypto Fear & Greed Index.** Published daily by Alternative.me since February 2018 from Bitcoin volatility, momentum and volume, social media activity, Bitcoin dominance, and search trends. It is tested against Bitcoin and Ether.

**Equity fear-and-greed composite.** CNN publishes a widely followed index built from seven market indicators, but not all of its inputs are freely available and its history is not distributed as a dataset. This study builds a transparent composite from four of the same ideas, each available in public data:

| Component | Measure | Greed when |
|:---|:---|:---|
| Momentum | S&P 500 relative to its 125-day average | Price is well above its average |
| Volatility | VIX relative to its 50-day average | VIX is below its average |
| Safe-haven demand | 20-day S&P 500 return minus 20-day long-Treasury (TLT) return | Stocks are outperforming bonds |
| Junk-bond demand | High-yield option-adjusted spread | Spreads are narrow |

Each component is converted to its percentile rank within the trailing two years (0 = most fearful), so the score at any date uses only data available on that date. The composite is the average of the available components. The high-yield spread series available on FRED covers roughly the last three years, so for most of the sample the composite is built from the other three components. It is tested against the S&P 500 and the Nasdaq-100.

Both indexes use the same regime bands: below 25 extreme fear, 25 to 44 fear, 45 to 55 neutral, 56 to 75 greed, and above 75 extreme greed.

## Results

<!-- RESULTS -->

## Limitations

- **Short crypto history.** The crypto index begins in 2018, which covers only two full Bitcoin cycles. Extreme-fear episodes cluster in a few drawdowns, so the effective number of independent observations is small.
- **Overlapping returns.** Daily regime returns at 6 and 12 months overlap heavily, which makes differences between regimes look more precise than they are; the entry-event test with a permutation p-value is the more conservative read.
- **Index construction.** Alternative.me's methodology and inputs may have changed over time, and its history is not guaranteed to be what was published in real time. The equity composite is this study's own construction and is not CNN's index.
- **Survivorship.** Bitcoin and the Nasdaq-100 are among the best-performing assets of the period. Buying the dip in an asset that keeps rising is rewarded almost regardless of timing; the same rule applied to an asset in secular decline would not be.
- **No costs or taxes** are included in the dollar-cost-averaging comparison.

## References

- Baker, M., and Wurgler, J. (2006). Investor sentiment and the cross-section of stock returns. *Journal of Finance*, 61(4), 1645–1680.
- Alternative.me. Crypto Fear & Greed Index, methodology and API documentation.

# Buying retracements to the 50, 100, and 200-week averages

<!-- REPO_ONLY -->
> This file holds the method and narrative. Results, charts, and tables are generated weekly and published on the project site.
<!-- /REPO_ONLY -->

**Question.** When an asset in an established uptrend pulls back to a major weekly moving average, are the returns that follow better than those from a randomly chosen week?

## Key findings (current build)

<!-- KEY_FINDINGS -->

## Background

The 50, 100, and 200-week simple moving averages are widely watched reference levels. Bitcoin's 200-week average in particular has marked or sat near the lows of several cycles, and many investors treat a retest of a long-term average after a strong advance as an entry point. If enough participants place bids at the same levels, those levels can become self-reinforcing pools of liquidity. If they do not, a touch of the average is just another week.

The academic record on simple technical rules is mixed. Brock, Lakonishok, and LeBaron (1992) found that moving-average rules had predictive power in a century of Dow data, while later work showed much of that edge faded after publication and after costs. Time-series momentum (Moskowitz, Ooi, and Pedersen, 2012) gives a theoretical reason for trend persistence. This study tests a narrow version of the idea on the assets I follow.

## Event definition

A week counts as a retracement event for a given average when all three conditions hold:

1. **Touch.** The weekly low trades within 3% of the average or below it.
2. **Arrival from above.** The prior week closed above that 3% zone.
3. **Prior extension.** At some point in the previous 26 weeks the weekly close was at least 10% above the average. This separates a pullback within an uptrend from price chopping around a flat average.

After an event, further touches of the same average are ignored for 13 weeks so that one extended test is counted once. Weekly bars close on Friday for equities and on Sunday for crypto, matching how most charting platforms draw them.

## Measurement

For each event the study records the forward return from the event week's close at 4, 13, 26, and 52 weeks; the worst low over the next 13 weeks relative to the entry close; and whether the next four weekly closes held within 3% of the average.

**Baseline.** Each asset's average forward return from every week where the same moving average exists. An event is only interesting if it beats what an investor would have earned on a random week in the same market.

**Significance.** A random-entry permutation test draws as many weeks as there are events, at random from all eligible weeks, 5,000 times, and reports the share of draws whose average 26-week return is at least as high as the events' average. A low p-value means the event average is hard to reproduce by chance.

## Level maps

The level map for each asset collects the price levels that discretionary traders tend to watch, so that confluence can be measured rather than eyeballed:

- **Moving averages:** 50, 100, and 200-week SMA.
- **Fibonacci retracements** (38.2%, 50%, 61.8%, 78.6%) of the latest major advance, defined as the highest weekly high of the last two years and the lowest low in the two years before it.
- **Swing pivots:** confirmed weekly swing highs and lows (the extreme of a nine-week window) from the last three years.
- **Volume profile:** the price with the most traded volume over the last two years (point of control) and other high-volume nodes, estimated from daily volume at each day's typical price.

Each level's confluence count is the number of other levels within 2.5% of it. A support at which an average, a Fibonacci level, and a volume node coincide is the kind of "major liquidity level" this study is designed to find.

## Results

<!-- RESULTS -->

## Limitations

- **Small samples.** A 200-week average needs four years of data before it exists; for Bitcoin that leaves a handful of tests. Averages on fewer than five events are shown but should not be relied on.
- **Overlapping outcomes.** Forward returns from nearby events overlap in time, and the permutation test does not preserve the clustering of returns, so its p-values are indicative.
- **Entry assumption.** Entries are at the weekly close, not at the average itself. A limit order resting at the average would have different fills.
- **Selection.** The assets studied are prominent today partly because they went up. Results do not generalize to assets that failed.
- **Parameter sensitivity.** The 3% band, 10% extension, 26-week lookback, and 13-week cooldown are reasonable but untuned choices. A robustness grid is a planned extension.


## References

- Brock, W., Lakonishok, J., and LeBaron, B. (1992). Simple technical trading rules and the stochastic properties of stock returns. *Journal of Finance*, 47(5), 1731–1764.
- Moskowitz, T., Ooi, Y. H., and Pedersen, L. H. (2012). Time series momentum. *Journal of Financial Economics*, 104(2), 228–250.

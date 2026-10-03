# Net liquidity and risk assets

<!-- REPO_ONLY -->
> This file holds the method and narrative. Results, charts, and tables are generated weekly and published on the project site.
<!-- /REPO_ONLY -->

**Question.** Do changes in the Federal Reserve's net liquidity lead returns in Bitcoin and the Nasdaq-100, and if so, at what horizon?

## Key findings (current build)

<!-- KEY_FINDINGS -->

## Background

Market participants often track a "net liquidity" measure built from the Fed's weekly balance sheet:

**Net liquidity = Fed total assets − Treasury General Account (TGA) − overnight reverse repo (ON RRP)**

The logic runs through bank reserves. Asset purchases (QE) add reserves; runoff (QT) removes them. When the Treasury builds its cash balance at the Fed, the TGA rises and reserves fall, so a tax date or a debt-ceiling resolution can drain liquidity without any change in Fed policy. Cash that money market funds place in the ON RRP facility also sits at the Fed rather than in the private financial system. The ON RRP balance rose above $2 trillion in 2022 and drained toward zero over 2023–2025; that drain released cash back to markets and offset much of QT's effect on reserves.

The measure is a heuristic, not an official aggregate, and the mechanism linking it to asset prices is debated. Treating it as a hypothesis to test, rather than a law, is the point of this study.

## Data

| Series | Source | Frequency | Use |
|:---|:---|:---|:---|
| WALCL | FRED (H.4.1) | Weekly, Wednesday | Fed total assets |
| WTREGEN | FRED (H.4.1) | Weekly | Treasury General Account |
| RRPONTSYD | FRED (New York Fed) | Daily | ON RRP balance |
| Asset prices | Yahoo Finance, adjusted | Daily, resampled to Friday | BTC-USD, QQQ, SPY, SMH |

All series are converted to billions of dollars. Balance-sheet data reference Wednesday and are published Thursday afternoon, so each observation is dated to the following Friday. A Friday signal therefore uses only information that was public by that Friday's close.

## Method

1. Build weekly net liquidity and its 13-week change (the "liquidity impulse").
2. Sample net liquidity and each asset's weekly close every four weeks, counting back from the latest week, and take log changes. Each four-week block is non-overlapping.
3. For leads of 0 to 24 weeks, correlate the liquidity change in block *t* with the asset's return in block *t + L*. Report Pearson's *r*, its p-value, and the number of blocks.
4. Plot a rolling 52-week correlation of overlapping four-week changes to show whether the relationship is stable or concentrated in particular periods.

Non-overlapping blocks matter. Overlapping rolling returns share most of their data, which inflates apparent significance; sampling every four weeks keeps the standard p-value roughly valid.

## Results

<!-- RESULTS -->

## Limitations

- **Correlation is not causation.** Liquidity and risk assets respond jointly to growth, inflation, and policy news. A positive correlation is consistent with a liquidity channel but does not establish one.
- **Multiple comparisons.** Seven leads across four assets is 28 tests; roughly one or two would clear p < 0.05 by chance alone. The key findings apply a Bonferroni threshold for that reason.
- **Regime dependence.** The sample is dominated by two episodes, 2020–21 QE and 2022–24 QT, and the ON RRP balance has since been largely drained, so the composition of the measure has changed.
- **Global liquidity is excluded.** ECB, BoJ, and PBoC balance sheets, and the dollar, plausibly matter for Bitcoin. Adding them is a natural extension.

<!--
## Discussion

AUTHOR: Write this section yourself after reviewing the live results. Questions to address:
- Which lead (if any) stands out, and does it survive the Bonferroni threshold?
- Is Bitcoin more liquidity-sensitive than QQQ? Does that fit how you think about the crypto trade?
- Does the rolling correlation show the relationship is stable, or driven by 2020-2022?
- What would you change or add next (global liquidity, the dollar, reserves instead of assets)?
Delete this comment block's opening and closing markers once the section is written.
-->

## References

- Board of Governors of the Federal Reserve System. *Factors Affecting Reserve Balances (H.4.1)*, weekly release.
- Federal Reserve Bank of St. Louis. FRED series WALCL, WTREGEN, and RRPONTSYD.

# Fed policy monitor and FOMC event study

<!-- REPO_ONLY -->
> This file holds the method and narrative. Results, charts, and tables are generated weekly and published on the project site.
<!-- /REPO_ONLY -->

**Question.** Where does Fed policy stand, what is the market pricing next, and how have Bitcoin, the Nasdaq-100, the S&P 500, and long Treasuries moved on FOMC decision days?

## Key findings (current build)

<!-- KEY_FINDINGS -->

## Policy monitor

The monitor tracks the indicators that summarize the policy stance and the market's expectations for it:

- **Target range and effective fed funds rate:** the current policy setting.
- **2-year Treasury minus fed funds:** the 2-year yield approximates the average expected policy rate over the next two years plus a term premium. A clearly negative spread is consistent with markets pricing cuts; a positive one with hikes.
- **10-year minus 2-year:** the slope of the curve. Inversion has historically preceded recessions, though with long and variable lags.
- **10-year TIPS real yield:** the inflation-adjusted discount rate that long-duration assets, including growth stocks, are most sensitive to.
- **Fed total assets and net liquidity:** the balance-sheet side of policy; the 13-week change shows the pace of runoff or expansion.

## Event study design

Decision dates are the statement days listed in `reference/fomc_decision_dates.csv`, including the unscheduled cuts of March 2020. Each decision is classified as a hike, cut, or hold from the change in the upper bound of the target range. Statements are released at 2:00 p.m. ET, before the equity close and before the 00:00 UTC daily crypto close used by Yahoo Finance, so the decision-day return captures the immediate reaction.

For each asset the study reports the average return from the prior close to the decision-day close, the share of decision days with a positive return, and the average return through five further sessions, each alongside the asset's unconditional average over the same number of sessions.

## Results

<!-- RESULTS -->

## Limitations

- **Decisions are not surprises.** Most decisions are fully priced before they are announced, so grouping by hike, cut, or hold mixes expected and unexpected outcomes. The standard approach measures the surprise from the change in fed funds futures around the announcement (Kuttner, 2001); intraday futures data would be needed to replicate it.
- **Daily data miss the pre-announcement drift.** Lucca and Moench (2015) document that U.S. equities earned large excess returns in the 24 hours before scheduled FOMC announcements. Measuring that requires intraday prices.
- **Small groups.** Hikes and cuts are clustered in a few cycles, so their averages rest on a small number of observations.


## References

- Kuttner, K. N. (2001). Monetary policy surprises and interest rates: Evidence from the Fed funds futures market. *Journal of Monetary Economics*, 47(3), 523–544.
- Lucca, D. O., and Moench, E. (2015). The pre-FOMC announcement drift. *Journal of Finance*, 70(1), 329–371.
- Board of Governors of the Federal Reserve System. Meeting calendars, statements, and minutes.

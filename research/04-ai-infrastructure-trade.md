# The AI infrastructure trade

<!-- REPO_ONLY -->
> This file holds the method and narrative. Results, charts, and tables are generated weekly and published on the project site.
<!-- /REPO_ONLY -->

**Question.** Artificial-intelligence capital spending flows through a physical stack: chips, the optical links between them, the power that runs them, and the software that monetizes them. How do those segments compare on trend, momentum, market sensitivity, and sensitivity to Fed liquidity, and which are leading or lagging now?

## Key findings (current build)

<!-- KEY_FINDINGS -->

## The stack

| Segment | Role in the build-out | Basket members |
|:---|:---|:---|
| AI compute | Accelerators, custom silicon, memory, foundry, lithography | NVDA, AVGO, AMD, TSM, MU, ASML |
| Photonics and optical networking | Transceivers, lasers, optical systems, and fiber that connect GPU clusters within and between data centers | COHR, LITE, CIEN, FN, AAOI, GLW, MRVL |
| Nuclear and power | Uranium supply and enrichment, reactor components, and the generators selling power to data centers | CCJ, CEG, VST, BWXT, LEU, OKLO, SMR |
| Software | Platforms and applications that turn compute into revenue | MSFT, ORCL, NOW, CRM, PLTR, ADBE |
| Crypto | A liquidity-sensitive comparison asset that competes for the same speculative capital | BTC, ETH, SOL |

The segments respond to different constraints. Compute is supply-limited by foundry and memory capacity. Optical networking scales with cluster size, since every added accelerator needs more high-speed links. Power has become a binding constraint on new data-center capacity, which is why long-term power purchase agreements with nuclear and gas generators have drawn attention. Software is where the spending has to earn a return.

## Method

Each basket is equal-weighted and rebalanced weekly. A stock enters when its price history begins, so the nuclear basket includes companies that listed recently (OKLO, SMR) only from their first trading week. Statistics reported for each basket:

- Returns over 4, 13, 26, and 52 weeks and year to date.
- 26-week return relative to QQQ.
- Distance from the 52-week high and from the 50 and 200-week SMAs.
- Three-year weekly beta to QQQ.
- Correlation of non-overlapping four-week basket returns with four-week changes in net liquidity.

Sector ETFs (SMH, IGV, URA) are shown alongside as a cross-check, since their holdings are set by index rules rather than chosen today.

## Results

<!-- RESULTS -->

## Limitations

- **Hindsight in membership.** The baskets list companies that are associated with these themes in 2026. Many were small or unrelated to AI five years ago, and companies that failed are absent. Historical basket returns therefore overstate what an investor could have captured in real time; the trend and relative-strength readings for recent periods are more informative than long-run returns.
- **Equal weighting** gives small, volatile names (AAOI, OKLO, SMR) the same weight as the largest companies.
- **No fundamentals.** Valuation, earnings revisions, and capital-spending guidance drive these stocks and are not modeled here. Adding hyperscaler capex and forward EV/sales is a planned extension.

<!--
## Discussion

AUTHOR: Write this section yourself after reviewing the live results. Questions to address:
- Which layer of the stack is leading and which is lagging, and why do you think that is?
- Is photonics behaving like a higher-beta version of compute, or does it have its own drivers?
- What would change your view on the nuclear trade (policy, power contracts, uranium supply)?
- How does the software layer's trend compare with the hardware layers?
Delete this comment block's opening and closing markers once the section is written.
-->

# Liquidity Cycle Research

Independent research on how Federal Reserve liquidity and long-term trend structure shape returns in crypto and technology-led equity markets, by Benjamin Curtis.

**Live site: [benjamin-curtis2026.github.io/liquidity-cycle-research](https://benjamin-curtis2026.github.io/liquidity-cycle-research/)**

The site is rebuilt every weekend by GitHub Actions from public data, so every chart, table, and key finding reflects the latest week rather than a one-time snapshot.

## Research

| Study | Question | Methods |
|:---|:---|:---|
| [Net liquidity and risk assets](research/01-net-liquidity-and-risk-assets.md) | Does Fed net liquidity (total assets − TGA − ON RRP) lead Bitcoin and the Nasdaq-100, and at what horizon? | Lead-lag correlation on non-overlapping blocks, Bonferroni adjustment, rolling stability |
| [Buying retracements to the 50, 100, and 200-week averages](research/02-weekly-moving-average-retracements.md) | When an asset in an uptrend pulls back to a major weekly average, do returns beat a random week? | Event study, random-entry permutation test, level maps with confluence scoring |
| [Liquidity regime and trend](research/03-liquidity-regime-and-trend.md) | Does conditioning exposure on the liquidity impulse and the 50-week trend improve risk-adjusted returns? | Rules-based backtest with costs and T-bill cash yield, sub-period Sharpe, Welch's t-test |
| [The AI infrastructure trade](research/04-ai-infrastructure-trade.md) | How do compute, software, photonics, nuclear power, and crypto compare on trend, momentum, and liquidity sensitivity? | Equal-weight baskets, relative strength, beta, ETF cross-check |
| [Fed policy monitor and FOMC event study](research/05-fed-policy-monitor.md) | Where does policy stand, what is priced, and how do assets move on decision days? | Policy dashboard, decision-day event study by hike, cut, or hold |

Each study states its question, data, and method, reports results against a baseline, and lists its limitations.

## How it works

```
FRED + Yahoo Finance  →  src/ (studies)  →  run_all.py  →  site/ (HTML, charts, CSV)  →  GitHub Pages
```

1. `src/data.py` downloads FRED series through the official FRED API and adjusted daily prices, caching each so a failed download falls back to the last good copy.
2. The study modules compute net liquidity and its regime (`liquidity.py`), weekly moving averages, retracement events, and level maps (`technicals.py`), rules-based backtests (`backtest.py`), thematic baskets (`themes.py`), and the policy monitor and FOMC event study (`fed.py`).
3. `run_all.py` runs every study, writes charts and downloadable CSV tables, and merges the generated results into the narrative files in `research/`.
4. `.github/workflows/weekly-update.yml` runs the tests and the build every Saturday and on every push, then publishes `site/` to GitHub Pages.

## Repository layout

```
liquidity-cycle-research/
├── research/                 Narrative for each study (question, method, limitations)
│   └── about.md              About section shown on the site
├── src/
│   ├── config.py             Universe, FRED series, and every study parameter
│   ├── data.py               FRED and Yahoo Finance download with cache fallback
│   ├── liquidity.py          Net liquidity, regime, lead-lag tests
│   ├── technicals.py         Weekly bars, moving averages, retracement events, level maps
│   ├── backtest.py           Regime and trend rules, costs, performance statistics
│   ├── themes.py             Thematic baskets and statistics
│   ├── fed.py                Policy monitor and FOMC event study
│   ├── stats.py              Permutation test, correlation, performance metrics
│   ├── charts.py             Matplotlib charts
│   ├── fmt.py                Number formatting and Markdown tables
│   └── site.py               HTML template and styles
├── reference/
│   └── fomc_decision_dates.csv
├── tests/test_pipeline.py    Unit tests and an end-to-end build on synthetic data
└── run_all.py                Builds the site
```

## Run locally

Requires Python 3.10 or later.

```bash
pip install -r requirements.txt
pytest -q                          # offline tests on synthetic data
export FRED_API_KEY=your_key_here  # free key from fred.stlouisfed.org
python run_all.py                  # downloads data and writes the site to ./site
```

Then open `site/index.html` in a browser.

## Configuration

Tickers, basket membership, and every parameter (moving-average windows, retracement band, liquidity window, transaction cost, and so on) live in [`src/config.py`](src/config.py). Change a value and the next build uses it.

## Data

- Federal Reserve Bank of St. Louis, FRED: WALCL, WTREGEN, RRPONTSYD, DFEDTARU, DFEDTARL, DFF, DTB3, DGS2, DGS10, T10Y2Y, DFII10, M2SL.
- Yahoo Finance via `yfinance`: split- and dividend-adjusted daily prices.
- Board of Governors of the Federal Reserve System: FOMC meeting calendars.

## Disclaimer

For research and education only. Nothing here is investment advice or a recommendation to buy or sell any security. Data may contain errors or later revisions.

## License

Code is released under the [MIT License](LICENSE).

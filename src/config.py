"""Universe, data series, and study parameters.

Everything the site covers is defined here. Edit tickers or parameters in this file and
the next build (local or GitHub Actions) picks them up.
"""

AUTHOR = "Doug Curtis"
SITE_TITLE = "Liquidity Cycle Research"
SITE_DESCRIPTION = (
    "Federal Reserve liquidity, weekly trend structure, and the AI-infrastructure, "
    "nuclear, and crypto trades. Rebuilt weekly from public data."
)

START_DATE = "2010-01-01"

# ---------------------------------------------------------------------------
# FRED series (downloaded without an API key from fredgraph.csv)
# ---------------------------------------------------------------------------
FRED_SERIES = {
    "WALCL": "Federal Reserve total assets, Wednesday level",
    "WTREGEN": "Treasury General Account, week ending Wednesday",
    "RRPONTSYD": "Overnight reverse repurchase agreements, daily",
    "M2SL": "M2 money stock, monthly, seasonally adjusted",
    "DFEDTARU": "Federal funds target range, upper bound",
    "DFEDTARL": "Federal funds target range, lower bound",
    "DFF": "Effective federal funds rate",
    "DTB3": "3-month Treasury bill, secondary market",
    "DGS2": "2-year Treasury, constant maturity",
    "DGS10": "10-year Treasury, constant maturity",
    "T10Y2Y": "10-year minus 2-year Treasury spread",
    "DFII10": "10-year TIPS real yield",
    "CBBTCUSD": "Coinbase bitcoin price (fallback source)",
    "CBETHUSD": "Coinbase ether price (fallback source)",
}

# Used only if Yahoo Finance and the local cache both fail.
FRED_PRICE_FALLBACK = {"BTC-USD": "CBBTCUSD", "ETH-USD": "CBETHUSD"}

# ---------------------------------------------------------------------------
# Market universe
# ---------------------------------------------------------------------------
CRYPTO = {"BTC-USD", "ETH-USD", "SOL-USD"}

# Assets used for the moving-average, level-map, and regime studies.
CORE_ASSETS = {
    "BTC-USD": "Bitcoin",
    "ETH-USD": "Ether",
    "SPY": "S&P 500 (SPY)",
    "QQQ": "Nasdaq-100 (QQQ)",
    "SMH": "Semiconductors (SMH)",
    "IGV": "Software (IGV)",
    "URA": "Uranium and nuclear (URA)",
}

# Equal-weight thematic baskets. Membership reflects 2026 relevance, which builds
# hindsight into historical basket returns; the themes report discusses this bias.
THEMES = {
    "AI compute": ["NVDA", "AVGO", "AMD", "TSM", "MU", "ASML"],
    "Software": ["MSFT", "ORCL", "NOW", "CRM", "PLTR", "ADBE"],
    "Photonics and optical networking": ["COHR", "LITE", "CIEN", "FN", "AAOI", "GLW", "MRVL"],
    "Nuclear and power": ["CCJ", "CEG", "VST", "BWXT", "LEU", "OKLO", "SMR"],
    "Crypto": ["BTC-USD", "ETH-USD", "SOL-USD"],
}
THEME_ETFS = {
    "AI compute": "SMH",
    "Software": "IGV",
    "Nuclear and power": "URA",
}
BENCHMARK = "QQQ"
FOMC_TICKERS = ["BTC-USD", "QQQ", "SPY", "TLT"]
REGIME_TEST_ASSETS = ["BTC-USD", "QQQ", "SMH"]
LEAD_LAG_ASSETS = ["BTC-USD", "QQQ", "SPY", "SMH"]

# ---------------------------------------------------------------------------
# Study parameters
# ---------------------------------------------------------------------------
MA_WINDOWS = (50, 100, 200)          # weekly simple moving averages
RETRACE_BAND = 0.03                  # weekly low within 3% of the MA counts as a test
RETRACE_PRIOR_EXTENSION = 0.10       # price must have closed >= 10% above the MA ...
RETRACE_LOOKBACK = 26                # ... at some point in the prior 26 weeks
RETRACE_COOLDOWN = 13                # weeks before another test of the same MA is counted
FORWARD_HORIZONS = (4, 13, 26, 52)   # weeks
PERMUTATION_DRAWS = 5000

LIQUIDITY_WINDOW = 13                # weeks, for the liquidity impulse / regime
LEAD_LAG_BLOCK = 4                   # weeks per non-overlapping block
LEAD_LAG_MAX_BLOCKS = 6              # test leads of 0..24 weeks

TREND_MA = 50                        # weekly SMA used by the trend filter
COST_BPS = 10                        # one-way cost per position change, basis points

LEVEL_CONFLUENCE_TOL = 0.025         # levels within 2.5% of each other are "confluent"
VOLUME_PROFILE_DAYS = 730            # calendar-day lookback for the volume profile
FIB_LOOKBACK_WEEKS = 104


def all_tickers():
    tickers = list(CORE_ASSETS) + [BENCHMARK] + FOMC_TICKERS + list(THEME_ETFS.values())
    for members in THEMES.values():
        tickers += members
    seen, ordered = set(), []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered

"""Universe, data series, and study parameters.

Everything the site covers is defined here. Edit tickers or parameters in this file and
the next build (local or GitHub Actions) picks them up.
"""

AUTHOR = "Benjamin Curtis"
SITE_TITLE = "Liquidity Cycle Research"
SITE_DESCRIPTION = (
    "Federal Reserve liquidity, weekly trend structure, and the AI-infrastructure, "
    "nuclear, and crypto trades. Rebuilt weekly from public data."
)

START_DATE = "2010-01-01"
# Series that need a longer history than START_DATE (recession model covers three recessions)
SERIES_START = {"T10Y3M": "2000-01-01", "USREC": "2000-01-01"}

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
    # Macro: inflation, labor, growth, recession signals
    "CPIAUCSL": "Consumer price index, all items",
    "CPILFESL": "Consumer price index, less food and energy",
    "PCEPILFE": "Core PCE price index",
    "UNRATE": "Unemployment rate",
    "PAYEMS": "Nonfarm payrolls",
    "SAHMREALTIME": "Real-time Sahm rule recession indicator",
    "GDPC1": "Real GDP",
    "GDPPOT": "Real potential GDP (CBO)",
    "T10Y3M": "10-year minus 3-month Treasury spread",
    "T10YIE": "10-year breakeven inflation",
    "T5YIFR": "5-year, 5-year forward inflation expectation",
    "USREC": "NBER recession indicator",
    # Financial conditions
    "VIXCLS": "CBOE VIX",
    "BAMLH0A0HYM2": "ICE BofA US high yield option-adjusted spread",
    "BAMLC0A0CM": "ICE BofA US corporate (investment grade) option-adjusted spread",
    "NFCI": "Chicago Fed National Financial Conditions Index",
    "DTWEXBGS": "Broad trade-weighted U.S. dollar index",
    "DCOILWTICO": "WTI crude oil spot price",
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
RISK_ASSETS = {
    "BTC-USD": "Bitcoin", "ETH-USD": "Ether", "SPY": "S&P 500", "QQQ": "Nasdaq-100",
    "SMH": "Semis", "IGV": "Software", "URA": "Uranium", "TLT": "Long Treasuries", "GLD": "Gold",
}
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

# Policy-rule and recession-model parameters
# Each Taylor-type rule: (neutral real rate r*, inflation-gap weight, output-gap weight)
TAYLOR_RULES = {
    "Taylor (1993)": (2.0, 0.5, 0.5),
    "Taylor with r* = 1%": (1.0, 0.5, 0.5),
    "Balanced approach (r* = 1%)": (1.0, 0.5, 1.0),
}
INFLATION_TARGET = 2.0
# Probit on the monthly-average 10-year minus 3-month spread, 12 months ahead
# (Estrella and Trubin specification used in the New York Fed's published model)
RECESSION_PROBIT = (-0.5333, -0.6330)
CONDITIONS_LOOKBACK_YEARS = 5

LEVEL_CONFLUENCE_TOL = 0.025         # levels within 2.5% of each other are "confluent"
VOLUME_PROFILE_DAYS = 730            # calendar-day lookback for the volume profile
FIB_LOOKBACK_WEEKS = 104


def all_tickers():
    tickers = (list(CORE_ASSETS) + [BENCHMARK] + FOMC_TICKERS + list(THEME_ETFS.values())
               + list(RISK_ASSETS))
    for members in THEMES.values():
        tickers += members
    seen, ordered = set(), []
    for t in tickers:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered

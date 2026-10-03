"""Data access: FRED and Yahoo Finance via yfinance, with a local CSV cache.

FRED is read through its official API when a FRED_API_KEY environment variable is set
(the GitHub Actions build supplies it from a repository secret). FRED's website
download endpoint tends to stall requests from cloud servers, so it is only a fallback
for local runs without a key.

If a download fails, the last cached copy is used, so a weekly rebuild degrades
gracefully instead of failing outright.
"""
from __future__ import annotations

import io
import logging
import os
import re
import time
from pathlib import Path

import pandas as pd
import requests

from . import config

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FRED_API = "https://api.stlouisfed.org/fred/series/observations"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; liquidity-cycle-research/1.0)"}
BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"),
    "Accept": "text/csv,text/plain,*/*",
}
OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _cache_path(kind: str, key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
    return DATA_DIR / kind / f"{safe}.csv"


def _http_get(url: str, params: dict | None = None, headers: dict | None = None,
              retries: int = 3, timeout: int = 20) -> requests.Response:
    """GET with retries. Error messages omit the query string so an API key never reaches the log."""
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, headers=headers or HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp
        except requests.RequestException as err:
            status = getattr(getattr(err, "response", None), "status_code", None)
            last_err = f"{type(err).__name__}" + (f" (HTTP {status})" if status else "")
            if status in (400, 401, 403, 404):
                break
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed: {last_err}")


# ---------------------------------------------------------------------------
# FRED
# ---------------------------------------------------------------------------
def _fred_api(series_id: str, key: str) -> pd.Series:
    params = {"series_id": series_id, "api_key": key, "file_type": "json",
              "observation_start": "2000-01-01"}
    obs = _http_get(FRED_API, params=params).json()["observations"]
    dates = pd.to_datetime([o["date"] for o in obs])
    values = pd.to_numeric(pd.Series([o["value"] for o in obs]), errors="coerce")
    return pd.Series(values.to_numpy(), index=pd.DatetimeIndex(dates), name=series_id)


def _fred_csv(series_id: str) -> pd.Series:
    text = _http_get(FRED_CSV.format(sid=series_id), headers=BROWSER_HEADERS, retries=2, timeout=15).text
    raw = pd.read_csv(io.StringIO(text))
    dates = pd.to_datetime(raw.iloc[:, 0])
    values = pd.to_numeric(raw.iloc[:, 1], errors="coerce")
    return pd.Series(values.to_numpy(), index=pd.DatetimeIndex(dates), name=series_id)


def fred_series(series_id: str, start: str = config.START_DATE) -> pd.Series:
    """Download one FRED series as a float Series indexed by date."""
    cache = _cache_path("fred", series_id)
    key = os.environ.get("FRED_API_KEY", "").strip()
    try:
        s = (_fred_api(series_id, key) if key else _fred_csv(series_id)).dropna()
        if s.empty:
            raise ValueError("empty series")
        cache.parent.mkdir(parents=True, exist_ok=True)
        s.to_csv(cache, header=True)
        log.info("FRED %-9s %5d observations (%s)", series_id, len(s), "API" if key else "CSV")
    except Exception as err:  # noqa: BLE001 - any failure falls back to cache
        if not cache.exists():
            raise
        log.warning("FRED %s download failed (%s); using cached copy", series_id, err)
        s = pd.read_csv(cache, index_col=0, parse_dates=True).iloc[:, 0].astype(float)
        s.name = series_id
    s.index.name = "date"
    return s[s.index >= pd.Timestamp(start)]


def load_fred(series_ids) -> dict[str, pd.Series]:
    out = {}
    for sid in series_ids:
        try:
            out[sid] = fred_series(sid, config.SERIES_START.get(sid, config.START_DATE))
        except Exception as err:  # noqa: BLE001
            log.error("FRED %s unavailable: %s", sid, err)
    return out


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------
def _yahoo_daily(ticker: str, start: str) -> pd.DataFrame:
    import yfinance as yf

    df = yf.Ticker(ticker).history(start=start, auto_adjust=True, actions=False)
    if df is None or df.empty:
        raise ValueError(f"no data returned for {ticker}")
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)
    df.index = idx.normalize()
    df = df[[c for c in OHLCV if c in df.columns]].astype(float)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df.index.name = "date"
    return df


def daily_prices(ticker: str, start: str = config.START_DATE) -> pd.DataFrame:
    """Daily split- and dividend-adjusted OHLCV for one ticker."""
    cache = _cache_path("prices", ticker)
    try:
        df = _yahoo_daily(ticker, start)
        cache.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache)
        log.info("Prices %-8s %5d days", ticker, len(df))
        return df
    except Exception as err:  # noqa: BLE001
        log.warning("Yahoo Finance %s failed (%s)", ticker, err)
    if cache.exists():
        log.warning("Using cached prices for %s", ticker)
        return pd.read_csv(cache, index_col=0, parse_dates=True).astype(float)
    sid = config.FRED_PRICE_FALLBACK.get(ticker)
    if sid:
        log.warning("Using FRED %s as the price source for %s", sid, ticker)
        close = fred_series(sid, start)
        return pd.DataFrame({"Open": close, "High": close, "Low": close, "Close": close})
    raise RuntimeError(f"no price source available for {ticker}")


def load_prices(tickers) -> dict[str, pd.DataFrame]:
    out = {}
    for t in tickers:
        try:
            out[t] = daily_prices(t)
        except Exception as err:  # noqa: BLE001
            log.error("Skipping %s: %s", t, err)
        time.sleep(0.25)
    return out

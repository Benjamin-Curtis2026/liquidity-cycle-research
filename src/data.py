"""Data access: FRED (no API key) and Yahoo Finance via yfinance, with a local CSV cache.

If a download fails, the last cached copy is used, so a weekly rebuild degrades
gracefully instead of failing outright.
"""
from __future__ import annotations

import io
import logging
import re
import time
from pathlib import Path

import pandas as pd
import requests

from . import config

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
FRED_CSV = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; liquidity-cycle-research/1.0)"}
OHLCV = ["Open", "High", "Low", "Close", "Volume"]


def _cache_path(kind: str, key: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", key)
    return DATA_DIR / kind / f"{safe}.csv"


def _http_get(url: str, retries: int = 3, timeout: int = 30) -> str:
    last_err = None
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.text
        except requests.RequestException as err:
            last_err = err
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} attempts: {url}") from last_err


# ---------------------------------------------------------------------------
# FRED
# ---------------------------------------------------------------------------
def fred_series(series_id: str, start: str = config.START_DATE) -> pd.Series:
    """Download one FRED series as a float Series indexed by date."""
    cache = _cache_path("fred", series_id)
    try:
        raw = pd.read_csv(io.StringIO(_http_get(FRED_CSV.format(sid=series_id))))
        dates = pd.to_datetime(raw.iloc[:, 0])
        values = pd.to_numeric(raw.iloc[:, 1], errors="coerce")
        s = pd.Series(values.to_numpy(), index=pd.DatetimeIndex(dates), name=series_id).dropna()
        if s.empty:
            raise ValueError("empty series")
        cache.parent.mkdir(parents=True, exist_ok=True)
        s.to_csv(cache, header=True)
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
            out[sid] = fred_series(sid)
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

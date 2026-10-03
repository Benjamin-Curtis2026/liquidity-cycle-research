"""Cross-asset risk: financial conditions, volatility, drawdowns, and correlations."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import config
from .technicals import to_weekly

CONDITIONS = [
    ("VIXCLS", "VIX (equity implied volatility)", "level"),
    ("BAMLH0A0HYM2", "High-yield credit spread (%)", "level"),
    ("BAMLC0A0CM", "Investment-grade credit spread (%)", "level"),
    ("NFCI", "Chicago Fed financial conditions (0 = average; + = tighter)", "level"),
    ("DTWEXBGS", "Broad U.S. dollar index", "level"),
    ("DCOILWTICO", "WTI crude oil ($/bbl)", "level"),
    ("T10Y2Y", "10-year minus 2-year Treasury spread (pp)", "level"),
]


def conditions_table(fred: dict, years: int = config.CONDITIONS_LOOKBACK_YEARS) -> pd.DataFrame:
    """Latest reading, 13-week change, and where it sits in its own recent history."""
    rows = []
    for key, label, _ in CONDITIONS:
        if key not in fred:
            continue
        s = fred[key].dropna()
        if len(s) < 50:
            continue
        last_date = s.index[-1]
        window = s[s.index >= last_date - pd.DateOffset(years=years)]
        prior = s[s.index <= last_date - pd.Timedelta(weeks=13)]
        z = (s.iloc[-1] - window.mean()) / window.std() if window.std() > 0 else np.nan
        rows.append({
            "Indicator": label, "series": key, "Latest": float(s.iloc[-1]), "As of": last_date,
            "13W change": float(s.iloc[-1] - prior.iloc[-1]) if len(prior) else np.nan,
            "Percentile": float((window <= s.iloc[-1]).mean()),
            "z-score": float(z),
            "Window low": float(window.min()), "Window high": float(window.max()),
        })
    return pd.DataFrame(rows)


def weekly_closes(prices: dict, tickers) -> pd.DataFrame:
    return pd.DataFrame({t: to_weekly(prices[t], "W-FRI")["Close"] for t in tickers if t in prices})


def asset_risk_table(prices: dict, rf_weekly: pd.Series | None = None) -> pd.DataFrame:
    closes = weekly_closes(prices, config.RISK_ASSETS)
    rows = []
    for t in closes:
        c = closes[t].dropna()
        if len(c) < 60:
            continue
        r = c / c.shift(1) - 1
        r3 = r.iloc[-156:]
        ex = r3 - (rf_weekly.reindex(r3.index).ffill().fillna(0) if rf_weekly is not None else 0)
        rows.append({
            "Asset": config.RISK_ASSETS[t],
            "13W": c.iloc[-1] / c.iloc[-14] - 1,
            "52W": c.iloc[-1] / c.iloc[-53] - 1 if len(c) > 53 else np.nan,
            "Vol 13W": r.iloc[-13:].std() * math.sqrt(52),
            "Vol 52W": r.iloc[-52:].std() * math.sqrt(52),
            "Sharpe 3Y": ex.mean() / ex.std() * math.sqrt(52) if ex.std() > 0 else np.nan,
            "Drawdown from high": c.iloc[-1] / c.cummax().iloc[-1] - 1,
            "Max drawdown 3Y": float((c.iloc[-156:] / c.iloc[-156:].cummax() - 1).min()),
        })
    return pd.DataFrame(rows)


def correlation_matrix(prices: dict, weeks: int = 104) -> pd.DataFrame:
    closes = weekly_closes(prices, config.RISK_ASSETS).iloc[-(weeks + 1):]
    rets = np.log(closes).diff().iloc[1:]
    corr = rets.corr(min_periods=int(weeks * 0.6))
    names = [config.RISK_ASSETS[t] for t in corr.columns]
    corr.index, corr.columns = names, names
    return corr


def rolling_pair_correlations(prices: dict, pairs, window: int = 26) -> dict[str, pd.Series]:
    closes = weekly_closes(prices, {t for p in pairs for t in p})
    rets = np.log(closes).diff()
    out = {}
    for a, b in pairs:
        if a in rets and b in rets:
            label = f"{config.RISK_ASSETS.get(a, a)} vs {config.RISK_ASSETS.get(b, b)}"
            out[label] = rets[a].rolling(window).corr(rets[b]).dropna()
    return out

"""Fear and greed: does buying when sentiment is fearful pay?

Two sentiment measures:
- Crypto Fear & Greed Index from Alternative.me (daily since February 2018; public API).
- An equity fear-and-greed composite built here from public data, in the spirit of
  CNN's index: S&P 500 momentum, VIX relative to its average, stocks vs. bonds, and
  high-yield credit spreads, each scored as a trailing two-year percentile.

Three tests: forward returns by sentiment regime, an event study of entries into fear
and extreme fear, and a dollar-cost-averaging comparison.
"""
from __future__ import annotations

import logging

import numpy as np
import pandas as pd
import requests
from scipy.optimize import brentq

from . import config
from .data import _cache_path
from .stats import random_entry_pvalue

log = logging.getLogger(__name__)

FNG_URL = "https://api.alternative.me/fng/"
REGIMES = ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]
BANDS = [(25, "Extreme Fear"), (45, "Fear"), (56, "Neutral"), (76, "Greed"), (101, "Extreme Greed")]


def classify(values: pd.Series) -> pd.Series:
    out = pd.Series(index=values.index, dtype=object)
    for upper, label in reversed(BANDS):
        out[values < upper] = label
    return out.where(values.notna())


# ---------------------------------------------------------------------------
# Indexes
# ---------------------------------------------------------------------------
def crypto_fear_greed() -> pd.Series | None:
    cache = _cache_path("sentiment", "crypto_fear_greed")
    try:
        resp = requests.get(FNG_URL, params={"limit": 0, "format": "json"},
                            headers={"User-Agent": "liquidity-cycle-research/1.0"}, timeout=30)
        resp.raise_for_status()
        rows = resp.json()["data"]
        idx = pd.to_datetime([int(r["timestamp"]) for r in rows], unit="s").normalize()
        s = pd.Series([float(r["value"]) for r in rows], index=idx, name="crypto_fng").sort_index()
        s = s[~s.index.duplicated(keep="last")]
        cache.parent.mkdir(parents=True, exist_ok=True)
        s.to_csv(cache, header=True)
        log.info("Crypto Fear & Greed %d days", len(s))
        return s
    except Exception as err:  # noqa: BLE001
        log.warning("Crypto Fear & Greed download failed (%s)", err)
        if cache.exists():
            return pd.read_csv(cache, index_col=0, parse_dates=True).iloc[:, 0]
        return None


def equity_fear_greed(prices: dict, fred: dict, window: int = 504) -> tuple[pd.Series, pd.DataFrame] | None:
    if "SPY" not in prices:
        return None
    spy = prices["SPY"]["Close"].dropna()
    comps = {"Momentum: S&P 500 vs. 125-day average": spy / spy.rolling(125).mean() - 1}
    if "VIXCLS" in fred:
        vix = fred["VIXCLS"].reindex(spy.index).ffill(limit=5)
        comps["Volatility: VIX vs. 50-day average (inverted)"] = -(vix / vix.rolling(50).mean() - 1)
    if "TLT" in prices:
        tlt = prices["TLT"]["Close"].reindex(spy.index).ffill(limit=5)
        comps["Safe-haven demand: stocks minus bonds, 20 days"] = (spy / spy.shift(20)) - (tlt / tlt.shift(20))
    if "BAMLH0A0HYM2" in fred:
        hy = fred["BAMLH0A0HYM2"].reindex(spy.index).ffill(limit=5)
        comps["Junk-bond demand: high-yield spread (inverted)"] = -hy
    scores = pd.DataFrame({k: v.rolling(window, min_periods=252).rank(pct=True) * 100 for k, v in comps.items()})
    n = scores.notna().sum(axis=1)
    composite = scores.mean(axis=1).where(n >= min(3, scores.shape[1])).dropna()
    composite.name = "equity_fng"
    return composite, scores


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def forward_returns(close: pd.Series, horizons: dict[str, int]) -> pd.DataFrame:
    return pd.DataFrame({lab: close.shift(-h) / close - 1 for lab, h in horizons.items()})


def regime_table(close: pd.Series, sentiment: pd.Series, horizons: dict[str, int],
                 hit_horizon: str) -> pd.DataFrame:
    df = forward_returns(close, horizons).join(classify(sentiment).rename("regime"), how="inner")
    df = df.dropna(subset=["regime"])
    rows = []
    for label in REGIMES + ["All days"]:
        g = df if label == "All days" else df[df["regime"] == label]
        if g.empty:
            continue
        row = {"Regime": label, "Share of days": len(g) / len(df)}
        for lab in horizons:
            row[f"Avg {lab}"] = g[lab].mean()
        row[f"Hit rate {hit_horizon}"] = (g[hit_horizon].dropna() > 0).mean() if g[hit_horizon].notna().any() else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def entry_events(sentiment: pd.Series, threshold: float, cooldown: int) -> list[pd.Timestamp]:
    """Days the index first drops below `threshold`, ignoring re-entries within `cooldown` rows."""
    below = sentiment < threshold
    crosses = below & ~below.shift(1, fill_value=False)
    events, last = [], -10**9
    for i, (dt, flag) in enumerate(crosses.items()):
        if flag and i - last >= cooldown:
            events.append(dt)
            last = i
    return events


def event_study(close: pd.Series, sentiment: pd.Series, threshold: float, horizons: dict[str, int],
                primary: str, dd_rows: int, cooldown: int) -> tuple[pd.DataFrame, dict]:
    s = sentiment.reindex(close.index).ffill(limit=3)
    fwd = forward_returns(close, horizons)
    dates = [d for d in entry_events(s.dropna(), threshold, cooldown) if d in close.index]
    vals = close.to_numpy()
    pos = {d: i for i, d in enumerate(close.index)}
    rows = []
    for d in dates:
        i = pos[d]
        end = min(i + dd_rows, len(vals) - 1)
        rows.append({"date": d, "index": float(s.loc[d]), "close": vals[i],
                     **{lab: fwd.loc[d, lab] for lab in horizons},
                     "further_drawdown": vals[i + 1:end + 1].min() / vals[i] - 1 if end > i else np.nan})
    ev = pd.DataFrame(rows)
    pool = fwd[primary].dropna()
    pool = pool[pool.index >= s.dropna().index[0]]
    summary = {"n": len(ev)}
    if len(ev):
        for lab in horizons:
            summary[f"Avg {lab}"] = ev[lab].mean()
            summary[f"Baseline {lab}"] = fwd[lab][fwd.index >= s.dropna().index[0]].mean()
        summary[f"Hit rate {primary}"] = (ev[primary].dropna() > 0).mean() if ev[primary].notna().any() else np.nan
        summary["p"] = random_entry_pvalue(ev[primary], pool)
        summary["Avg further drawdown"] = ev["further_drawdown"].mean()
    return ev, summary


def _irr_weekly(flows: np.ndarray) -> float:
    t = np.arange(len(flows)) / 52
    f = lambda r: float(np.sum(flows / (1 + r) ** t))  # noqa: E731
    try:
        return brentq(f, -0.99, 10.0)
    except ValueError:
        return float("nan")


def dca_compare(close: pd.Series, sentiment: pd.Series, rf_weekly: pd.Series | None,
                rule: str = "W-FRI", amount: float = 100.0):
    """Weekly contributions of `amount`, invested always, only in fear, or only in extreme fear.

    Sentiment is lagged one day so each decision uses the reading known before that close.
    Uninvested cash earns the 3-month T-bill rate.
    """
    sig = sentiment.shift(1)
    wk = pd.concat({"price": close.resample(rule).last(), "fng": sig.resample(rule).last()}, axis=1).dropna()
    wk = wk[wk.index >= sentiment.dropna().index[0]]
    if len(wk) < 52:
        return None, None
    rf = (rf_weekly.reindex(wk.index, method="ffill").fillna(0) if rf_weekly is not None
          else pd.Series(0.0, index=wk.index))
    rules = {"Every week": None, "Only in fear (index below 45)": 45, "Only in extreme fear (below 25)": 25}
    curves, rows = {}, []
    for name, level in rules.items():
        units = cash = invested = 0.0
        vals, weeks_bought = [], 0
        for dt, r in wk.iterrows():
            cash = cash * (1 + rf.loc[dt]) + amount
            if level is None or r["fng"] < level:
                units += cash / r["price"]
                invested += cash
                cash = 0.0
                weeks_bought += 1
            vals.append(units * r["price"] + cash)
        curve = pd.Series(vals, index=wk.index)
        curves[name] = curve
        contributed = amount * len(wk)
        flows = np.full(len(wk), -amount)
        flows[-1] += curve.iloc[-1]
        rows.append({
            "Rule": name, "Weeks buying": weeks_bought, "Contributed": contributed,
            "Ending value": curve.iloc[-1], "Gain": curve.iloc[-1] / contributed - 1,
            "Money-weighted return": _irr_weekly(flows),
            "Average cost vs. average price": (invested / units) / wk["price"].mean() - 1 if units else np.nan,
            "Cash at end": cash,
        })
    return pd.DataFrame(curves), pd.DataFrame(rows)

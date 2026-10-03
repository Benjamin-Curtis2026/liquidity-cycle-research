"""Equal-weight thematic baskets and their trend, momentum, and liquidity statistics."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .liquidity import align_weekly
from .stats import pearson
from .technicals import to_weekly


def weekly_closes(prices: dict, tickers, rule: str = "W-FRI") -> pd.DataFrame:
    cols = {t: to_weekly(prices[t], rule)["Close"] for t in tickers if t in prices}
    return pd.DataFrame(cols)


def basket_index(prices: dict, members, min_members: int = 2) -> tuple[pd.Series, pd.Series]:
    """Equal-weight index rebalanced weekly; members join as their price history begins.

    Returns (index level starting at 100, number of members in each week).
    """
    closes = weekly_closes(prices, members)
    if closes.empty:
        return pd.Series(dtype=float), pd.Series(dtype=float)
    rets = closes / closes.shift(1) - 1
    count = rets.notna().sum(axis=1)
    basket = rets.mean(axis=1, skipna=True).where(count >= min(min_members, closes.shape[1]))
    first = basket.first_valid_index()
    if first is None:
        return pd.Series(dtype=float), count
    basket = basket.loc[first:].fillna(0)
    level = 100 * (1 + basket).cumprod()
    return level, count.loc[first:]


def _ret(level: pd.Series, weeks: int) -> float:
    if len(level) <= weeks:
        return float("nan")
    return float(level.iloc[-1] / level.iloc[-1 - weeks] - 1)


def _ytd(level: pd.Series) -> float:
    prior = level[level.index.year < level.index[-1].year]
    return float(level.iloc[-1] / prior.iloc[-1] - 1) if len(prior) else float("nan")


def _vs_sma(level: pd.Series, n: int) -> float:
    if len(level) < n:
        return float("nan")
    return float(level.iloc[-1] / level.rolling(n).mean().iloc[-1] - 1)


def _beta(level: pd.Series, bench: pd.Series, weeks: int = 156) -> float:
    df = pd.concat([level, bench], axis=1, join="inner").dropna()
    r = (df / df.shift(1) - 1).dropna().iloc[-weeks:]
    if len(r) < 52:
        return float("nan")
    cov = np.cov(r.iloc[:, 0], r.iloc[:, 1])
    return float(cov[0, 1] / cov[1, 1])


def liquidity_corr(level: pd.Series, net_liq: pd.Series, block: int = config.LEAD_LAG_BLOCK):
    """Same-period correlation of non-overlapping 4-week log changes."""
    df = align_weekly(net_liq, level)
    sampled = df.iloc[::-1].iloc[::block].iloc[::-1]
    r, p, n = pearson(np.log(sampled["liq"]).diff(), np.log(sampled["px"]).diff())
    return r, p, n


def theme_summary(indices: dict[str, pd.Series], bench: pd.Series, net_liq: pd.Series) -> pd.DataFrame:
    rows = []
    for name, level in indices.items():
        if level.empty:
            continue
        r_liq, p_liq, _ = liquidity_corr(level, net_liq)
        rel = level / bench.reindex(level.index).ffill()
        rows.append({
            "Theme": name,
            "4W": _ret(level, 4),
            "13W": _ret(level, 13),
            "26W": _ret(level, 26),
            "52W": _ret(level, 52),
            "YTD": _ytd(level),
            f"Rel. to {config.BENCHMARK} 26W": _ret(rel.dropna(), 26),
            "From 52W high": float(level.iloc[-1] / level.iloc[-52:].max() - 1),
            "vs 50W SMA": _vs_sma(level, 50),
            "vs 200W SMA": _vs_sma(level, 200),
            f"Beta to {config.BENCHMARK} (3Y)": _beta(level, bench),
            "Liquidity corr.": r_liq,
            "Liquidity p": p_liq,
        })
    return pd.DataFrame(rows)


def member_table(prices: dict, members) -> pd.DataFrame:
    closes = weekly_closes(prices, members)
    rows = []
    for t in closes:
        s = closes[t].dropna()
        if len(s) < 5:
            continue
        rows.append({
            "Ticker": t,
            "13W": _ret(s, 13),
            "52W": _ret(s, 52),
            "From 52W high": float(s.iloc[-1] / s.iloc[-52:].max() - 1),
            "vs 50W SMA": _vs_sma(s, 50),
            "vs 200W SMA": _vs_sma(s, 200),
            "History (yrs)": len(s) / 52,
        })
    return pd.DataFrame(rows)

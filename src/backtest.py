"""Weekly rules-based allocation tests: liquidity regime, trend, and both combined.

Conventions
- Signals are computed from data known at the Friday close of week t and applied to the
  return of week t + 1 (positions are shifted one week).
- When out of the market, the strategy earns the 3-month T-bill rate.
- Each change in position costs `cost_bps` basis points.
"""
from __future__ import annotations

import pandas as pd

from . import config
from .stats import perf_stats


def weekly_rf(dtb3: pd.Series) -> pd.Series:
    annual = dtb3.resample("W-FRI").last().ffill() / 100
    return (1 + annual) ** (1 / 52) - 1


def build_signals(close_w: pd.Series, expanding: pd.Series, trend_ma: int = config.TREND_MA) -> dict:
    sma = close_w.rolling(trend_ma, min_periods=trend_ma).mean()
    trend = (close_w > sma).astype(float).where(sma.notna())
    liq = expanding.reindex(close_w.index)
    both = (trend * liq).where(trend.notna() & liq.notna())
    ones = pd.Series(1.0, index=close_w.index)
    return {
        "Buy and hold": ones,
        f"Trend (close above {trend_ma}W SMA)": trend,
        f"Liquidity ({config.LIQUIDITY_WINDOW}W impulse positive)": liq,
        "Liquidity and trend": both,
    }


def run_backtest(close_w: pd.Series, signals: dict, rf_w: pd.Series,
                 cost_bps: float = config.COST_BPS):
    """Return (equity curves DataFrame, stats DataFrame, weekly returns DataFrame)."""
    ret = close_w / close_w.shift(1) - 1
    positions = pd.DataFrame({k: v.shift(1) for k, v in signals.items()})
    frame = pd.concat([ret.rename("ret"), rf_w.rename("rf"), positions], axis=1, sort=True)
    frame["rf"] = frame["rf"].ffill()
    frame = frame.dropna()
    if len(frame) < 104:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    strat_returns = {}
    for name in signals:
        pos = frame[name]
        turnover = pos.diff().abs().fillna(0)
        strat_returns[name] = pos * frame["ret"] + (1 - pos) * frame["rf"] - turnover * cost_bps / 1e4
    rets = pd.DataFrame(strat_returns)
    curves = (1 + rets).cumprod()

    rows = []
    for name in rets:
        s = perf_stats(rets[name], frame["rf"])
        pos = frame[name]
        s["Time invested"] = pos.mean()
        s["Switches"] = int((pos.diff().abs() > 0).sum())
        rows.append({"Strategy": name, **s})
    return curves, pd.DataFrame(rows), rets.assign(rf=frame["rf"])


def subperiod_sharpe(rets: pd.DataFrame) -> pd.DataFrame:
    """Sharpe ratio in the full sample and each half, as a basic stability check."""
    rf = rets["rf"]
    strat = rets.drop(columns="rf")
    mid = len(strat) // 2
    halves = {
        "Full sample": slice(None),
        f"{strat.index[0]:%Y}–{strat.index[mid - 1]:%Y}": slice(0, mid),
        f"{strat.index[mid]:%Y}–{strat.index[-1]:%Y}": slice(mid, None),
    }
    rows = []
    for name in strat:
        row = {"Strategy": name}
        for label, sl in halves.items():
            s = perf_stats(strat[name].iloc[sl], rf.iloc[sl])
            row[label] = s.get("Sharpe", float("nan"))
        rows.append(row)
    return pd.DataFrame(rows)

"""Federal Reserve net liquidity: construction, regime, and lead-lag tests.

Net liquidity = Fed total assets - Treasury General Account - overnight reverse repo.

The balance sheet supplies reserves; cash the Treasury holds in the TGA and cash money
funds park in the ON RRP facility sit at the Fed rather than in the banking system.
This is a market heuristic, not an official monetary aggregate.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .stats import pearson


def _to_billions(s: pd.Series) -> pd.Series:
    """FRED reports WALCL and WTREGEN in millions and RRPONTSYD in billions.

    Rather than hard-code units, convert any series whose typical value is too large
    to be in billions (> 50,000), which guards against a future unit change.
    """
    return s / 1000 if s.median() > 50_000 else s


def net_liquidity(fred: dict[str, pd.Series]) -> pd.DataFrame:
    """Weekly net liquidity in billions of USD, dated to the Friday it is known.

    Balance-sheet data reference Wednesday and are published Thursday afternoon (H.4.1),
    so each Wednesday observation is re-dated to the following Friday. This keeps every
    downstream test free of look-ahead.
    """
    assets = _to_billions(fred["WALCL"]).resample("W-WED").last()
    tga = _to_billions(fred["WTREGEN"]).resample("W-WED").last()
    rrp = _to_billions(fred["RRPONTSYD"]).resample("W-WED").last()
    df = pd.concat({"fed_assets": assets, "tga": tga, "rrp": rrp}, axis=1)
    observed = df["fed_assets"].notna()  # keep only weeks with a published balance sheet
    df["tga"] = df["tga"].ffill()
    df["rrp"] = df["rrp"].ffill().fillna(0.0)
    df = df[observed].dropna()
    df["net_liquidity"] = df["fed_assets"] - df["tga"] - df["rrp"]
    df.index = df.index + pd.Timedelta(days=2)
    df.index.name = "date"
    return df[df.index >= pd.Timestamp(config.START_DATE)]


def add_regime(liq: pd.DataFrame, window: int = config.LIQUIDITY_WINDOW) -> pd.DataFrame:
    out = liq.copy()
    nl = out["net_liquidity"]
    out["impulse_bn"] = nl - nl.shift(window)
    out["impulse_pct"] = nl / nl.shift(window) - 1
    missing = out["impulse_pct"].isna()
    out["expanding"] = np.where(missing, np.nan, (out["impulse_pct"] > 0).astype(float))
    out["regime"] = pd.Series(
        np.where(missing, None, np.where(out["impulse_pct"] > 0, "Expanding", "Contracting")),
        index=out.index, dtype=object,
    )
    return out


def align_weekly(liq: pd.Series, close_w: pd.Series) -> pd.DataFrame:
    """Join a Friday-dated liquidity series with Friday weekly closes."""
    return pd.concat({"liq": liq, "px": close_w}, axis=1, join="inner").dropna()


def lead_lag(liq: pd.Series, close_w: pd.Series, block: int = config.LEAD_LAG_BLOCK,
             max_blocks: int = config.LEAD_LAG_MAX_BLOCKS) -> pd.DataFrame:
    """Correlation of liquidity changes with later asset returns, on non-overlapping blocks.

    Both series are sampled every `block` weeks (counting back from the latest week)
    and converted to log changes. Row L correlates the liquidity change in block t with
    the asset return in block t + L. Non-overlapping blocks keep the usual p-value
    approximately valid, which overlapping rolling windows would not.
    """
    df = align_weekly(liq, close_w)
    sampled = df.iloc[::-1].iloc[::block].iloc[::-1]
    d_liq = np.log(sampled["liq"]).diff()
    d_px = np.log(sampled["px"]).diff()
    rows = []
    for lead in range(0, max_blocks + 1):
        r, p, n = pearson(d_liq, d_px.shift(-lead))
        rows.append({"lead_weeks": lead * block, "corr": r, "p_value": p, "n": n})
    return pd.DataFrame(rows)


def rolling_correlation(liq: pd.Series, close_w: pd.Series, change_weeks: int = 4,
                        window: int = 52) -> pd.Series:
    """Rolling correlation of overlapping 4-week log changes. Descriptive only."""
    df = align_weekly(liq, close_w)
    d_liq = np.log(df["liq"]).diff(change_weeks)
    d_px = np.log(df["px"]).diff(change_weeks)
    return d_liq.rolling(window).corr(d_px)

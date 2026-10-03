"""Weekly trend structure: moving averages, retracement events, and price-level maps."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config


def week_rule(ticker: str) -> str:
    """Crypto trades seven days a week; its weekly bar closes Sunday, equities close Friday."""
    return "W-SUN" if ticker in config.CRYPTO else "W-FRI"


def to_weekly(daily: pd.DataFrame, rule: str = "W-FRI") -> pd.DataFrame:
    agg = {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"}
    agg = {c: f for c, f in agg.items() if c in daily.columns}
    weekly = daily.resample(rule).agg(agg)
    return weekly.dropna(subset=["Close"])


def add_moving_averages(weekly: pd.DataFrame, windows=config.MA_WINDOWS) -> pd.DataFrame:
    out = weekly.copy()
    for n in windows:
        out[f"SMA{n}"] = out["Close"].rolling(n, min_periods=n).mean()
    return out


def weekly_with_mas(daily: pd.DataFrame, ticker: str) -> pd.DataFrame:
    return add_moving_averages(to_weekly(daily, week_rule(ticker)))


# ---------------------------------------------------------------------------
# Retracement events
# ---------------------------------------------------------------------------
def retracement_events(
    weekly: pd.DataFrame,
    ma_col: str,
    band: float = config.RETRACE_BAND,
    prior_extension: float = config.RETRACE_PRIOR_EXTENSION,
    lookback: int = config.RETRACE_LOOKBACK,
    cooldown: int = config.RETRACE_COOLDOWN,
) -> list[int]:
    """Positional indices of weeks where price retraces from above into a moving average.

    A week qualifies when (1) its low trades within `band` of the MA or below it,
    (2) the prior week closed above that zone, so price is arriving from above, and
    (3) at some point in the prior `lookback` weeks the close was at least
    `prior_extension` above the MA, so the move is a pullback within an uptrend rather
    than chop around a flat average. After an event, the same MA is ignored for
    `cooldown` weeks so a single test is not counted repeatedly.
    """
    ma = weekly[ma_col]
    low = weekly["Low"] if "Low" in weekly else weekly["Close"]
    close = weekly["Close"]
    zone_top = ma * (1 + band)

    in_zone = low <= zone_top
    from_above = close.shift(1) > zone_top.shift(1)
    extension = (close / ma - 1).rolling(lookback, min_periods=1).max().shift(1)
    extended = extension >= prior_extension
    candidates = (in_zone & from_above & extended & ma.notna()).to_numpy()

    events, last = [], -10**9
    for i, flag in enumerate(candidates):
        if flag and i - last >= cooldown:
            events.append(i)
            last = i
    return events


def event_table(
    weekly: pd.DataFrame,
    ma_col: str,
    idxs: list[int],
    horizons=config.FORWARD_HORIZONS,
    band: float = config.RETRACE_BAND,
) -> pd.DataFrame:
    """Forward outcomes for each retracement event, measured from the event week's close."""
    close = weekly["Close"].to_numpy()
    low = (weekly["Low"] if "Low" in weekly else weekly["Close"]).to_numpy()
    ma = weekly[ma_col].to_numpy()
    n = len(close)
    rows = []
    for i in idxs:
        row = {
            "date": weekly.index[i],
            "close": close[i],
            "ma": ma[i],
            "low_vs_ma": low[i] / ma[i] - 1,
            "close_vs_ma": close[i] / ma[i] - 1,
        }
        for h in horizons:
            row[f"fwd_{h}w"] = close[i + h] / close[i] - 1 if i + h < n else np.nan
        end = min(i + 13, n - 1)
        row["max_drawdown_13w"] = low[i + 1 : end + 1].min() / close[i] - 1 if end > i else np.nan
        if i + 4 < n:
            held = np.all(close[i + 1 : i + 5] >= ma[i + 1 : i + 5] * (1 - band))
            row["held_4w"] = float(held)
        else:
            row["held_4w"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def unconditional_forward_returns(weekly: pd.DataFrame, ma_col: str, horizon: int) -> pd.Series:
    """Forward returns from every week where the MA is defined: the comparison baseline."""
    close = weekly["Close"]
    fwd = close.shift(-horizon) / close - 1
    return fwd[weekly[ma_col].notna()].dropna()


# ---------------------------------------------------------------------------
# Level map: moving averages, Fibonacci retracements, swing pivots, volume nodes
# ---------------------------------------------------------------------------
def pivot_points(weekly: pd.DataFrame, left: int = 4, right: int = 4):
    """Confirmed swing highs and lows: extremes of a centered (left + right + 1)-week window."""
    span = left + right + 1
    highs = weekly["High"] if "High" in weekly else weekly["Close"]
    lows = weekly["Low"] if "Low" in weekly else weekly["Close"]
    ph = highs[highs == highs.rolling(span, center=True).max()]
    pl = lows[lows == lows.rolling(span, center=True).min()]
    return ph.dropna(), pl.dropna()


def fib_retracements(weekly: pd.DataFrame, lookback: int = config.FIB_LOOKBACK_WEEKS,
                     ratios=(0.382, 0.5, 0.618, 0.786)) -> dict:
    """Retracement levels of the most recent major advance.

    Swing high: highest weekly high in the last `lookback` weeks.
    Swing low: lowest weekly low in the `lookback` weeks ending at that high.
    """
    highs = weekly["High"] if "High" in weekly else weekly["Close"]
    lows = weekly["Low"] if "Low" in weekly else weekly["Close"]
    recent = highs.iloc[-lookback:]
    if recent.empty:
        return {}
    hi_date = recent.idxmax()
    hi = float(recent.max())
    window = lows.loc[:hi_date].iloc[-lookback:]
    lo_date = window.idxmin()
    lo = float(window.min())
    if hi <= lo:
        return {}
    return {
        "swing_high": (hi_date, hi),
        "swing_low": (lo_date, lo),
        "levels": {r: hi - r * (hi - lo) for r in ratios},
    }


def volume_profile(daily: pd.DataFrame, days: int = config.VOLUME_PROFILE_DAYS, bins: int = 60):
    """Volume-at-price histogram using each day's typical price.

    Returns (profile Series indexed by bin mid-price, point of control, list of
    high-volume nodes), or None when volume data is unavailable.
    """
    if "Volume" not in daily or daily["Volume"].fillna(0).sum() <= 0:
        return None
    d = daily[daily.index >= daily.index[-1] - pd.Timedelta(days=days)].dropna(subset=["Close"])
    if len(d) < 50:
        return None
    typical = (d["High"] + d["Low"] + d["Close"]) / 3
    edges = np.linspace(float(d["Low"].min()), float(d["High"].max()), bins + 1)
    hist, _ = np.histogram(typical, bins=edges, weights=d["Volume"].fillna(0))
    mids = (edges[:-1] + edges[1:]) / 2
    poc = float(mids[hist.argmax()])
    threshold = np.percentile(hist, 75)
    hvns = [
        float(mids[i])
        for i in range(1, len(hist) - 1)
        if hist[i] >= threshold and hist[i] >= hist[i - 1] and hist[i] >= hist[i + 1]
        and not np.isclose(mids[i], poc)
    ]
    hvns = sorted(hvns, key=lambda m: -hist[np.argmin(np.abs(mids - m))])[:4]
    return pd.Series(hist, index=mids), poc, hvns


def level_map(daily: pd.DataFrame, weekly: pd.DataFrame,
              tol: float = config.LEVEL_CONFLUENCE_TOL) -> pd.DataFrame:
    """All tracked levels with distance from the latest close and a confluence count."""
    last = float(weekly["Close"].iloc[-1])
    levels = []
    for n in config.MA_WINDOWS:
        col = f"SMA{n}"
        if col in weekly and pd.notna(weekly[col].iloc[-1]):
            levels.append((f"{n}W SMA", float(weekly[col].iloc[-1])))
    fib = fib_retracements(weekly)
    for r, v in fib.get("levels", {}).items():
        levels.append((f"Fib {r:.3f}", float(v)))
    ph, pl = pivot_points(weekly)
    horizon = weekly.index[-1] - pd.Timedelta(weeks=156)
    for dt, v in pl[pl.index >= horizon].items():
        levels.append((f"Swing low {dt:%b %Y}", float(v)))
    for dt, v in ph[ph.index >= horizon].items():
        levels.append((f"Swing high {dt:%b %Y}", float(v)))
    vp = volume_profile(daily)
    if vp is not None:
        _, poc, hvns = vp
        levels.append(("Volume POC", poc))
        levels += [("High-volume node", h) for h in hvns]

    df = pd.DataFrame(levels, columns=["level", "price"])
    if df.empty:
        return df
    df["distance"] = df["price"] / last - 1
    prices = df["price"].to_numpy()
    df["confluence"] = [int(np.sum(np.abs(prices / p - 1) <= tol)) - 1 for p in prices]
    return df.sort_values("price", ascending=False).reset_index(drop=True)


def nearest_levels(levels: pd.DataFrame, side: str = "support", k: int = 3) -> pd.DataFrame:
    if levels.empty:
        return levels
    if side == "support":
        sub = levels[levels["distance"] < 0].sort_values("distance", ascending=False)
    else:
        sub = levels[levels["distance"] > 0].sort_values("distance")
    return sub.head(k)

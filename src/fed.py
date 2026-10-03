"""Federal Reserve policy monitor and FOMC decision-day event study."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FOMC_FILE = ROOT / "reference" / "fomc_decision_dates.csv"


def _asof(s: pd.Series, when: pd.Timestamp) -> float:
    s = s.dropna()
    s = s[s.index <= when]
    return float(s.iloc[-1]) if len(s) else float("nan")


def policy_table(fred: dict, net_liq: pd.Series) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Latest level and changes over 4, 13, and 52 weeks for the policy indicators."""
    series = {}

    def add(label, key, scale=1.0):
        if key in fred:
            series[label] = fred[key] * scale

    add("Fed funds target, upper bound (%)", "DFEDTARU")
    add("Effective fed funds rate (%)", "DFF")
    add("3-month T-bill (%)", "DTB3")
    add("2-year Treasury (%)", "DGS2")
    add("10-year Treasury (%)", "DGS10")
    add("10-year minus 2-year (pp)", "T10Y2Y")
    add("10-year real yield, TIPS (%)", "DFII10")
    if "DGS2" in fred and "DFF" in fred:
        df = pd.concat([fred["DGS2"], fred["DFF"]], axis=1).dropna()
        series["2-year minus fed funds (pp)"] = df.iloc[:, 0] - df.iloc[:, 1]
    if "WALCL" in fred:
        walcl = fred["WALCL"]
        series["Fed total assets ($bn)"] = walcl / 1000 if walcl.median() > 50_000 else walcl
    # Net liquidity is dated to the Friday it becomes known; show its Wednesday reference date.
    series["Net liquidity ($bn)"] = net_liq.set_axis(net_liq.index - pd.Timedelta(days=2))

    asof = min(s.dropna().index[-1] for s in series.values())
    rows = []
    for label, s in series.items():
        latest_date = s.dropna().index[-1]
        latest = _asof(s, latest_date)
        rows.append({
            "Indicator": label,
            "Latest": latest,
            "As of": latest_date,
            "4W change": latest - _asof(s, latest_date - pd.Timedelta(weeks=4)),
            "13W change": latest - _asof(s, latest_date - pd.Timedelta(weeks=13)),
            "52W change": latest - _asof(s, latest_date - pd.Timedelta(weeks=52)),
        })
    return pd.DataFrame(rows), asof


def load_fomc_dates(upper_bound: pd.Series | None = None) -> pd.DataFrame:
    """Decision dates (statement day) with the decision classified from the target range."""
    df = pd.read_csv(FOMC_FILE, parse_dates=["date"], comment="#")
    df = df.sort_values("date").reset_index(drop=True)
    if upper_bound is not None and not upper_bound.empty:
        changes = []
        for d in df["date"]:
            before = _asof(upper_bound, d - pd.Timedelta(days=1))
            after = _asof(upper_bound, d + pd.Timedelta(days=3))
            if np.isnan(before) or np.isnan(after) or upper_bound.index[-1] < d + pd.Timedelta(days=1):
                changes.append(np.nan)
            else:
                changes.append(round((after - before) * 100))
        df["change_bp"] = changes
        df["decision"] = np.select(
            [df["change_bp"] > 0, df["change_bp"] < 0, df["change_bp"] == 0],
            ["Hike", "Cut", "Hold"], default="Pending",
        )
    return df


def fomc_event_returns(close: pd.Series, dates: pd.DataFrame, after: int = 5) -> pd.DataFrame:
    """Return from the prior close to the decision-day close, and to `after` sessions later.

    Decisions are announced at 2:00 p.m. ET. U.S. equity closes (4:00 p.m. ET) and the
    Yahoo Finance daily crypto close (00:00 UTC, 8:00 p.m. ET) both fall after it.
    For unscheduled weekend actions the first session after the announcement is day 0.
    """
    close = close.dropna()
    idx = close.index
    vals = close.to_numpy()
    rows = []
    for _, ev in dates.iterrows():
        d = ev["date"]
        pos = idx.searchsorted(d)
        if pos == 0 or pos >= len(idx) or idx[pos] - d > pd.Timedelta(days=3):
            continue
        base = vals[pos - 1]
        rows.append({
            "date": d,
            "decision": ev.get("decision", "n/a"),
            "day0": vals[pos] / base - 1,
            f"day0_to_{after}": vals[pos + after] / base - 1 if pos + after < len(vals) else np.nan,
        })
    return pd.DataFrame(rows)


def baseline_returns(close: pd.Series, sessions: int) -> pd.Series:
    """All (sessions)-day returns, prior close to close: the comparison baseline."""
    close = close.dropna()
    return (close.shift(-(sessions - 1)) / close.shift(1) - 1).dropna()

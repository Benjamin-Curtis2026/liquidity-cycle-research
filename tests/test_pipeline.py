"""Offline tests. Synthetic data only exercise the code paths; they say nothing about markets.

    pytest -q
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src import config, technicals as tech

LISTINGS = {"BTC-USD": "2014-09-17", "ETH-USD": "2017-11-09", "SOL-USD": "2020-04-10",
            "OKLO": "2024-05-10", "SMR": "2022-05-03", "CEG": "2022-02-02", "PLTR": "2020-09-30"}
END = "2026-09-25"


def _gbm(index, seed, drift=0.10, vol=0.30, periods=252):
    rng = np.random.default_rng(seed)
    r = rng.normal(drift / periods, vol / np.sqrt(periods), len(index))
    return 100 * np.exp(np.cumsum(r))


def synthetic_prices(tickers) -> dict:
    out = {}
    for i, t in enumerate(tickers):
        crypto = t in config.CRYPTO
        start = LISTINGS.get(t, config.START_DATE)
        idx = pd.date_range(start, END, freq="D" if crypto else "B")
        close = _gbm(idx, seed=i, drift=0.4 if crypto else 0.12, vol=0.7 if crypto else 0.3,
                     periods=365 if crypto else 252)
        rng = np.random.default_rng(100 + i)
        spread = np.abs(rng.normal(0, 0.01, len(idx)))
        out[t] = pd.DataFrame({
            "Open": close * (1 - spread / 2), "High": close * (1 + spread), "Low": close * (1 - spread),
            "Close": close, "Volume": rng.integers(1_000, 10_000, len(idx)).astype(float),
        }, index=idx)
    return out


def synthetic_fred() -> dict:
    rng = np.random.default_rng(42)
    wed = pd.date_range(config.START_DATE, END, freq="W-WED")
    day = pd.date_range(config.START_DATE, END, freq="B")
    walcl = pd.Series(2_300_000 * np.exp(np.cumsum(rng.normal(0.002, 0.01, len(wed)))), index=wed)
    tga = pd.Series(np.clip(400_000 + np.cumsum(rng.normal(0, 30_000, len(wed))), 20_000, 1_000_000), index=wed)
    rrp = pd.Series(np.clip(np.cumsum(rng.normal(0, 15, len(day))), 0, 2500), index=day)
    upper = pd.Series(np.select([day < "2016-01-01", day < "2019-08-01", day < "2020-03-04", day < "2022-03-17",
                                 day < "2023-07-27", day < "2024-09-19"],
                                [0.25, 2.5, 2.0, 0.25, 5.5, 5.5], 4.0), index=day)
    dff = upper - 0.17
    dgs2 = upper + rng.normal(-0.2, 0.2, len(day))
    dgs10 = dgs2 + 0.5
    return {
        "WALCL": walcl, "WTREGEN": tga, "RRPONTSYD": rrp, "DFEDTARU": upper, "DFEDTARL": upper - 0.25,
        "DFF": dff, "DTB3": dff - 0.05, "DGS2": dgs2, "DGS10": dgs10, "T10Y2Y": dgs10 - dgs2,
        "DFII10": dgs10 - 2.2,
    }


def test_retracement_event_detection():
    idx = pd.date_range("2015-01-02", periods=300, freq="W-FRI")
    rise = 100 * 1.01 ** np.arange(250)
    close = np.concatenate([rise, np.linspace(rise[-1], rise[-1] * 0.6, 50)])
    w = pd.DataFrame({"Close": close, "High": close * 1.01, "Low": close * 0.99}, index=idx)
    w = tech.add_moving_averages(w, (50,))
    events = tech.retracement_events(w, "SMA50")
    assert len(events) >= 1
    first = events[0]
    assert w["Low"].iloc[first] <= w["SMA50"].iloc[first] * (1 + config.RETRACE_BAND)
    assert w["Close"].iloc[first - 1] > w["SMA50"].iloc[first - 1] * (1 + config.RETRACE_BAND)


def test_no_events_without_prior_extension():
    idx = pd.date_range("2015-01-02", periods=200, freq="W-FRI")
    close = 100 + np.sin(np.arange(200) / 3)
    w = pd.DataFrame({"Close": close, "High": close + 0.5, "Low": close - 0.5}, index=idx)
    w = tech.add_moving_averages(w, (50,))
    assert tech.retracement_events(w, "SMA50") == []


def test_level_map_has_confluence_column():
    prices = synthetic_prices(["QQQ"])
    w = tech.weekly_with_mas(prices["QQQ"], "QQQ")
    lv = tech.level_map(prices["QQQ"], w)
    assert {"level", "price", "distance", "confluence"} <= set(lv.columns)
    assert (lv["confluence"] >= 0).all()


def test_full_build(tmp_path, monkeypatch):
    import run_all
    from src import data

    monkeypatch.setattr(data, "load_fred", lambda ids: synthetic_fred())
    monkeypatch.setattr(data, "load_prices", lambda tickers: synthetic_prices(tickers))
    monkeypatch.setattr(run_all, "OUT", tmp_path / "site")
    monkeypatch.setattr(run_all, "ASSETS", tmp_path / "site" / "assets")
    monkeypatch.setattr(run_all, "TABLES", tmp_path / "site" / "data")
    run_all.main()
    out = tmp_path / "site"
    assert (out / "index.html").exists()
    for key, *_ in run_all.REPORTS:
        page = (out / "research" / f"{key}.html").read_text()
        assert "<!-- RESULTS -->" not in page and "<!-- KEY_FINDINGS -->" not in page
    assert len(list((out / "assets").glob("*.png"))) >= 10


if __name__ == "__main__":
    pytest.main([__file__, "-q"])

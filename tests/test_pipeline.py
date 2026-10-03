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
    month = pd.date_range(config.START_DATE, END, freq="MS")
    quarter = pd.date_range(config.START_DATE, END, freq="QS")
    week_fri = pd.date_range(config.START_DATE, END, freq="W-FRI")
    gdp = pd.Series(15000 * np.exp(np.cumsum(rng.normal(0.005, 0.006, len(quarter)))), index=quarter)
    return {
        "WALCL": walcl, "WTREGEN": tga, "RRPONTSYD": rrp, "DFEDTARU": upper, "DFEDTARL": upper - 0.25,
        "DFF": dff, "DTB3": dff - 0.05, "DGS2": dgs2, "DGS10": dgs10, "T10Y2Y": dgs10 - dgs2,
        "DFII10": dgs10 - 2.2,
        "CPIAUCSL": pd.Series(220 * np.exp(np.cumsum(rng.normal(0.002, 0.002, len(month)))), index=month),
        "CPILFESL": pd.Series(225 * np.exp(np.cumsum(rng.normal(0.002, 0.001, len(month)))), index=month),
        "PCEPILFE": pd.Series(100 * np.exp(np.cumsum(rng.normal(0.0018, 0.001, len(month)))), index=month),
        "UNRATE": pd.Series(np.clip(5 + np.cumsum(rng.normal(0, 0.1, len(month))), 3, 10), index=month),
        "PAYEMS": pd.Series(130000 + np.cumsum(rng.normal(150, 80, len(month))), index=month),
        "SAHMREALTIME": pd.Series(np.abs(rng.normal(0.2, 0.15, len(month))), index=month),
        "GDPC1": gdp, "GDPPOT": gdp * (1 + rng.normal(0, 0.01, len(quarter))),
        "T10Y3M": dgs10 - (dff - 0.05), "T10YIE": pd.Series(2.2 + rng.normal(0, 0.1, len(day)), index=day),
        "T5YIFR": pd.Series(2.3 + rng.normal(0, 0.1, len(day)), index=day),
        "USREC": pd.Series(((month >= "2020-03-01") & (month <= "2020-04-01")).astype(float), index=month),
        "VIXCLS": pd.Series(np.abs(18 + np.cumsum(rng.normal(0, 0.5, len(day)))) % 40 + 10, index=day),
        "BAMLH0A0HYM2": pd.Series(np.clip(4 + np.cumsum(rng.normal(0, 0.03, len(day))), 2.5, 10), index=day),
        "BAMLC0A0CM": pd.Series(np.clip(1.2 + np.cumsum(rng.normal(0, 0.01, len(day))), 0.8, 3), index=day),
        "NFCI": pd.Series(rng.normal(-0.4, 0.2, len(week_fri)), index=week_fri),
        "DTWEXBGS": pd.Series(110 + np.cumsum(rng.normal(0, 0.2, len(day))), index=day),
        "DCOILWTICO": pd.Series(np.clip(70 + np.cumsum(rng.normal(0, 1, len(day))), 20, 140), index=day),
    }


TODAY = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
MEETING_1 = TODAY + pd.Timedelta(days=25)
MEETING_2 = TODAY + pd.Timedelta(days=67)


def kalshi_payload():
    """Mimics GET /events?series_ticker=KXFED&with_nested_markets=true (documented fields)."""
    def ev(code, date, probs):
        return {"event_ticker": f"KXFED-{code}", "strike_date": f"{date}T18:00:00Z", "markets": [
            {"ticker": f"KXFED-{code}-T{k:.2f}", "floor_strike": k, "strike_type": "greater",
             "yes_bid_dollars": f"{max(p - 0.01, 0):.4f}", "yes_ask_dollars": f"{min(p + 0.01, 1):.4f}",
             "last_price_dollars": f"{p:.4f}", "volume_fp": "1000.00"} for k, p in probs.items()]}
    return {"events": [
        ev("M1", f"{MEETING_1:%Y-%m-%d}", {3.25: 0.99, 3.50: 0.97, 3.75: 0.80, 4.00: 0.10, 4.25: 0.02}),
        ev("M2", f"{MEETING_2:%Y-%m-%d}", {3.25: 0.97, 3.50: 0.85, 3.75: 0.55, 4.00: 0.15, 4.25: 0.04}),
    ], "cursor": ""}


def polymarket_payload():
    return {"events": [{"title": f"Fed decision in {MEETING_1:%B}?", "endDate": f"{MEETING_1:%Y-%m-%d}T00:00:00Z",
                        "closed": False, "slug": "fed-decision", "markets": [
        {"groupItemTitle": "50+ bps decrease", "outcomes": "[\"Yes\", \"No\"]", "outcomePrices": "[\"0.02\", \"0.98\"]"},
        {"groupItemTitle": "25 bps decrease", "outcomes": "[\"Yes\", \"No\"]", "outcomePrices": "[\"0.18\", \"0.82\"]"},
        {"groupItemTitle": "No change", "outcomes": "[\"Yes\", \"No\"]", "outcomePrices": "[\"0.72\", \"0.28\"]"},
        {"groupItemTitle": "25+ bps increase", "outcomes": "[\"Yes\", \"No\"]", "outcomePrices": "[\"0.08\", \"0.92\"]"},
    ]}]}


def synthetic_crypto_fng():
    idx = pd.date_range("2018-02-01", END, freq="D")
    rng = np.random.default_rng(5)
    v = 50 + 30 * np.sin(np.arange(len(idx)) / 60) + rng.normal(0, 8, len(idx))
    return pd.Series(np.clip(v, 1, 99), index=idx, name="crypto_fng")


def test_sentiment_regimes_events_and_dca():
    from src import sentiment as se
    assert list(se.classify(pd.Series([10, 30, 50, 60, 90])).values) == \
        ["Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"]
    s = pd.Series([50, 20, 18, 30, 50, 22, 50], index=pd.date_range("2024-01-01", periods=7))
    assert se.entry_events(s, 25, cooldown=1) == [s.index[1], s.index[5]]
    assert se.entry_events(s, 25, cooldown=10) == [s.index[1]]
    fng = synthetic_crypto_fng()
    close = synthetic_prices(["BTC-USD"])["BTC-USD"]["Close"]
    curves, stats = se.dca_compare(close, fng, None, rule="W-SUN")
    assert curves.shape[1] == 3 and (stats["Contributed"] == stats["Contributed"].iloc[0]).all()
    assert stats.iloc[0]["Weeks buying"] == len(curves)


def test_kalshi_ladder_to_distribution():
    from src import expectations as ex
    path = ex.parse_kalshi_events(kalshi_payload()["events"], current_upper=4.00)
    assert path is not None and len(path) == 2
    oct_ = path.iloc[0]
    assert abs(oct_["dist"].sum() - 1) < 1e-9
    # "above 3.75" -> P(upper >= 4.00) = 0.80, "above 4.00" -> P(>= 4.25) = 0.10, so P(4.00) = 0.70
    assert abs(oct_["dist"][4.00] - 0.70) < 0.02
    assert oct_["mode"] == 4.00
    b = ex.to_buckets(pd.Series(oct_["dist"].to_numpy(), index=oct_["dist"].index - 4.00))
    assert abs(b["Hold"] - 0.70) < 0.02 and abs(b.sum() - 1) < 1e-9


def test_polymarket_buckets():
    from src import expectations as ex
    b = ex.parse_polymarket_event(polymarket_payload()["events"][0])
    assert abs(b["Hold"] - 0.72) < 1e-9 and abs(b["Cut 50+ bp"] - 0.02) < 1e-9 and abs(b["Hike 25 bp"] - 0.08) < 1e-9


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

    from src import expectations as ex

    def fake_get_json(url, params=None, timeout=20):
        return kalshi_payload() if "kalshi" in url else polymarket_payload()

    monkeypatch.setattr(ex, "_get_json", fake_get_json)
    from src import sentiment as se
    monkeypatch.setattr(se, "crypto_fear_greed", synthetic_crypto_fng)
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
    assert len(list((out / "assets").glob("*.png"))) >= 18
    index = (out / "index.html").read_text()
    assert "Rate expectations" in index and "Financial conditions" in index and "Sentiment" in index
    fg = (out / "research" / "fear-and-greed.html").read_text()
    assert "Dollar-cost averaging" in fg and "Entries into fear" in fg


if __name__ == "__main__":
    pytest.main([__file__, "-q"])

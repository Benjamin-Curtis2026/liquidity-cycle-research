"""Rate expectations and macro models.

- Prediction markets: Kalshi's KXFED contracts ("upper bound above X% after meeting M")
  are turned into a full probability distribution for the policy rate at each upcoming
  FOMC meeting. Polymarket's "Fed decision" market gives a second read on the next meeting.
- Policy rules: Taylor-type rules from core PCE inflation and the CBO output gap.
- Recession risk: the yield-curve probit used in the New York Fed's published model, and
  the real-time Sahm rule.

Network calls fail soft: if a source is unavailable, the function returns None and the
page reports the source as unavailable for that build.
"""
from __future__ import annotations

import json
import logging
import math
import re

import numpy as np
import pandas as pd
import requests
from scipy.stats import norm

from . import config

log = logging.getLogger(__name__)

KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
GAMMA = "https://gamma-api.polymarket.com"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; liquidity-cycle-research/1.0)",
           "Accept": "application/json"}
GRID = 0.25
BUCKETS = ["Cut 50+ bp", "Cut 25 bp", "Hold", "Hike 25 bp", "Hike 50+ bp"]
BUCKET_PHRASES = {"Cut 50+ bp": "a cut of 50 bp or more", "Cut 25 bp": "a 25 bp cut", "Hold": "a hold",
                  "Hike 25 bp": "a 25 bp hike", "Hike 50+ bp": "a hike of 50 bp or more"}


def _get_json(url: str, params: dict | None = None, timeout: int = 20):
    resp = requests.get(url, params=params, headers=HEADERS, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def _f(x) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


# ---------------------------------------------------------------------------
# Kalshi
# ---------------------------------------------------------------------------
def kalshi_price(m: dict) -> float:
    """Implied probability for a Kalshi market, or NaN when the book carries no information.

    - Two-sided market with a spread of 10 cents or less: the midpoint.
    - Deep out-of-the-money (no bid, ask of 5 cents or less): half the ask.
    - Near-certain (bid of 95 cents or more, no ask): halfway between the bid and $1.
    - Otherwise the last trade, if the contract has traded and the trade sits inside the quotes.
    Empty or very wide books return NaN instead of a meaningless 50-cent midpoint.
    """
    bid, ask, last = (_f(m.get("yes_bid_dollars")), _f(m.get("yes_ask_dollars")),
                      _f(m.get("last_price_dollars")))
    if math.isnan(bid) and "yes_bid" in m:  # older cent-denominated fields
        bid, ask, last = _f(m.get("yes_bid")) / 100, _f(m.get("yes_ask")) / 100, _f(m.get("last_price")) / 100
    bid = 0.0 if math.isnan(bid) else bid
    ask = 0.0 if math.isnan(ask) else ask
    if bid > 0 and 0 < ask <= 1 and ask >= bid and ask - bid <= 0.10:
        return (bid + ask) / 2
    if bid == 0 and 0 < ask <= 0.05:
        return ask / 2
    if bid >= 0.95 and (ask == 0 or ask >= 1):
        return (bid + 1) / 2
    volume = _f(m.get("volume_fp", m.get("volume")))
    if last > 0 and (math.isnan(volume) or volume > 0):
        if ask > 0 and not (bid - 0.02 <= last <= ask + 0.02):
            return float("nan")
        return last
    return float("nan")


def _strike(m: dict) -> float:
    s = _f(m.get("floor_strike"))
    if math.isnan(s):
        hit = re.search(r"-T(\d+(?:\.\d+)?)$", str(m.get("ticker", "")))
        s = float(hit.group(1)) if hit else float("nan")
    return s


def _threshold_level(strike: float, strike_type: str | None) -> float:
    """Convert a contract strike to 'upper bound >= level' on the 25 bp grid."""
    eps = 1e-9
    if strike_type == "greater_or_equal":
        return math.ceil(strike / GRID - eps) * GRID
    return (math.floor(strike / GRID + eps) + 1) * GRID


def _naive_day(x) -> pd.Timestamp:
    ts = pd.Timestamp(x)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("UTC").tz_localize(None)
    return ts.normalize()


def _meeting_date(event: dict) -> pd.Timestamp | None:
    if event.get("strike_date"):
        return _naive_day(event["strike_date"])
    closes = [m.get("close_time") for m in event.get("markets", []) or [] if m.get("close_time")]
    return min(_naive_day(c) for c in closes) if closes else None


def ladder_distribution(markets: list[dict]) -> pd.Series | None:
    """Probability distribution of the post-meeting upper bound from a ladder of
    'above X%' contracts. Index: upper-bound level (%); values sum to 1."""
    surv = {}
    for m in markets:
        if m.get("strike_type") not in (None, "greater", "greater_or_equal"):
            continue  # only 'above X' ladders define a survival function
        s, p = _strike(m), kalshi_price(m)
        if math.isnan(s) or math.isnan(p):
            continue
        lvl = round(_threshold_level(s, m.get("strike_type")), 4)
        surv[lvl] = max(surv.get(lvl, 0.0), min(max(p, 0.0), 1.0))
    # Require a ladder that spans both tails; otherwise the distribution is not identified.
    if len(surv) < 4 or max(surv.values()) < 0.85 or min(surv.values()) > 0.15:
        return None
    levels = sorted(surv)
    s_vals, prev = [], 1.0
    for lvl in levels:                       # survival function must be non-increasing
        prev = min(prev, surv[lvl])
        s_vals.append(prev)
    probs = {round(levels[0] - GRID, 4): 1.0 - s_vals[0]}
    for i, lvl in enumerate(levels):
        nxt = s_vals[i + 1] if i + 1 < len(levels) else 0.0
        probs[lvl] = s_vals[i] - nxt
    dist = pd.Series(probs).sort_index()
    dist = dist.clip(lower=0)
    total = dist.sum()
    return dist / total if total > 0 else None


def dist_summary(dist: pd.Series, current_upper: float) -> dict:
    cdf = dist.cumsum()
    q = lambda x: float(dist.index[np.searchsorted(cdf.to_numpy(), x)])  # noqa: E731
    return {
        "expected": float((dist.index * dist).sum()),
        "mode": float(dist.idxmax()),
        "mode_p": float(dist.max()),
        "p10": q(0.10), "p90": q(0.90),
        "p_lower": float(dist[dist.index < current_upper - 1e-9].sum()),
        "p_same": float(dist[np.isclose(dist.index, current_upper)].sum()),
        "p_higher": float(dist[dist.index > current_upper + 1e-9].sum()),
    }


def to_buckets(changes: pd.Series) -> pd.Series:
    """Map a distribution over rate changes (percentage points) to decision buckets."""
    out = dict.fromkeys(BUCKETS, 0.0)
    for chg, p in changes.items():
        bp = round(chg * 100)
        if bp <= -50:
            out["Cut 50+ bp"] += p
        elif bp < 0:
            out["Cut 25 bp"] += p
        elif bp == 0:
            out["Hold"] += p
        elif bp < 50:
            out["Hike 25 bp"] += p
        else:
            out["Hike 50+ bp"] += p
    return pd.Series(out)


def kalshi_rate_path(current_upper: float) -> pd.DataFrame | None:
    """One row per upcoming FOMC meeting with the market-implied rate distribution."""
    try:
        events, cursor = [], None
        for _ in range(5):
            params = {"series_ticker": "KXFED", "status": "open", "with_nested_markets": "true", "limit": 100}
            if cursor:
                params["cursor"] = cursor
            js = _get_json(f"{KALSHI}/events", params)
            events += js.get("events", []) or []
            cursor = js.get("cursor")
            if not cursor:
                break
    except Exception as err:  # noqa: BLE001
        log.warning("Kalshi unavailable: %s", err)
        return None
    return parse_kalshi_events(events, current_upper)


def parse_kalshi_events(events: list[dict], current_upper: float) -> pd.DataFrame | None:
    rows = []
    today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
    for ev in events:
        date = _meeting_date(ev)
        dist = ladder_distribution(ev.get("markets", []) or [])
        if date is None or dist is None or date < today or date > today + pd.Timedelta(days=455):
            continue
        summ = dist_summary(dist, current_upper)
        volume = sum(_f(m.get("volume_fp", m.get("volume"))) for m in ev.get("markets", [])
                     if not math.isnan(_f(m.get("volume_fp", m.get("volume")))))
        rows.append({"meeting": date, "event": ev.get("event_ticker"), "dist": dist,
                     "volume": volume, **summ})
    if not rows:
        return None
    return pd.DataFrame(rows).sort_values("meeting").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Polymarket
# ---------------------------------------------------------------------------
def _label_to_change(label: str) -> float | None:
    s = label.lower()
    if "no change" in s or s.strip() in ("hold", "pause", "unchanged"):
        return 0.0
    hit = re.search(r"(\d+)\s*\+?\s*(?:bps?|basis)", s)
    if not hit:
        return None
    bp = int(hit.group(1))
    if any(w in s for w in ("decrease", "cut", "lower")):
        return -bp / 100
    if any(w in s for w in ("increase", "hike", "raise")):
        return bp / 100
    return None


def _jsonish(x):
    if isinstance(x, str):
        try:
            return json.loads(x)
        except json.JSONDecodeError:
            return None
    return x


def parse_polymarket_event(event: dict) -> pd.Series | None:
    """Decision-bucket probabilities from a Polymarket 'Fed decision' event."""
    changes = {}
    for m in event.get("markets", []) or []:
        if m.get("closed") is True:
            continue
        chg = _label_to_change(m.get("groupItemTitle") or m.get("question") or "")
        prices, outcomes = _jsonish(m.get("outcomePrices")), _jsonish(m.get("outcomes"))
        if chg is None or not prices:
            continue
        idx = 0
        if isinstance(outcomes, list) and "Yes" in outcomes:
            idx = outcomes.index("Yes")
        p = _f(prices[idx]) if idx < len(prices) else float("nan")
        if not math.isnan(p):
            changes[chg] = changes.get(chg, 0.0) + p
    if not changes:
        return None
    s = pd.Series(changes)
    s = s[s >= 0]
    return to_buckets(s / s.sum()) if s.sum() > 0 else None


def polymarket_next_meeting(meeting: pd.Timestamp) -> pd.Series | None:
    month = meeting.strftime("%B")
    try:
        js = _get_json(f"{GAMMA}/public-search", {"q": f"Fed decision in {month}"})
        events = js.get("events", []) or []
        candidates = []
        for ev in events:
            title = str(ev.get("title", "")).lower()
            if "fed" not in title or month.lower() not in title or ev.get("closed"):
                continue
            end = _naive_day(ev["endDate"]) if ev.get("endDate") else None
            gap = abs((end - meeting).days) if end is not None else 999
            if gap <= 20:
                candidates.append((gap, ev))
        if not candidates:
            return None
        ev = sorted(candidates, key=lambda t: t[0])[0][1]
        if not ev.get("markets"):
            full = _get_json(f"{GAMMA}/events", {"slug": ev.get("slug")})
            ev = full[0] if isinstance(full, list) and full else ev
        return parse_polymarket_event(ev)
    except Exception as err:  # noqa: BLE001
        log.warning("Polymarket unavailable: %s", err)
        return None


# ---------------------------------------------------------------------------
# Policy rules, recession probability, macro table
# ---------------------------------------------------------------------------
def _complete_months(monthly: pd.Series) -> pd.Series:
    """Drop the current calendar month, which is still incomplete."""
    this_month = pd.Timestamp.now(tz="UTC").tz_localize(None).to_period("M").to_timestamp()
    return monthly[monthly.index < this_month]


def _yoy(s: pd.Series) -> pd.Series:
    return (s / s.shift(12) - 1) * 100


def taylor_rules(fred: dict) -> pd.DataFrame | None:
    need = ("PCEPILFE", "GDPC1", "GDPPOT", "DFEDTARU", "DFEDTARL")
    if any(k not in fred for k in need):
        return None
    infl = _yoy(fred["PCEPILFE"].resample("MS").last())
    gap_q = (fred["GDPC1"] / fred["GDPPOT"].reindex(fred["GDPC1"].index) - 1) * 100
    gap = gap_q.resample("MS").last().reindex(infl.index).ffill(limit=5)
    mid = ((fred["DFEDTARU"] + fred["DFEDTARL"]) / 2).resample("MS").mean()
    df = pd.DataFrame({"inflation": infl, "output_gap": gap, "actual": mid.reindex(infl.index)})
    for name, (rstar, a, b) in config.TAYLOR_RULES.items():
        df[name] = rstar + df["inflation"] + a * (df["inflation"] - config.INFLATION_TARGET) + b * df["output_gap"]
    return df.dropna(subset=["inflation", "output_gap"])


def recession_probability(fred: dict) -> pd.Series | None:
    if "T10Y3M" not in fred:
        return None
    a, b = config.RECESSION_PROBIT
    spread = _complete_months(fred["T10Y3M"].resample("MS").mean().dropna())
    return pd.Series(norm.cdf(a + b * spread), index=spread.index, name="recession_prob")


def macro_table(fred: dict) -> pd.DataFrame:
    rows = []

    def add(label, s, unit, note=""):
        s = s.dropna()
        if s.empty:
            return
        prev = s[s.index <= s.index[-1] - pd.DateOffset(months=3)]
        yr = s[s.index <= s.index[-1] - pd.DateOffset(months=12)]
        rows.append({"Indicator": label, "Latest": s.iloc[-1], "As of": s.index[-1],
                     "3 months ago": prev.iloc[-1] if len(prev) else np.nan,
                     "12 months ago": yr.iloc[-1] if len(yr) else np.nan, "unit": unit, "note": note})

    if "CPIAUCSL" in fred:
        add("CPI inflation, y/y (%)", _yoy(fred["CPIAUCSL"].resample("MS").last()), "pct")
    if "CPILFESL" in fred:
        add("Core CPI inflation, y/y (%)", _yoy(fred["CPILFESL"].resample("MS").last()), "pct")
    if "PCEPILFE" in fred:
        add("Core PCE inflation, y/y (%)", _yoy(fred["PCEPILFE"].resample("MS").last()), "pct")
    if "T10YIE" in fred:
        add("10-year breakeven inflation (%)", _complete_months(fred["T10YIE"].resample("MS").mean()), "pct")
    if "T5YIFR" in fred:
        add("5y5y forward inflation expectation (%)", _complete_months(fred["T5YIFR"].resample("MS").mean()), "pct")
    if "UNRATE" in fred:
        add("Unemployment rate (%)", fred["UNRATE"], "pct")
    if "PAYEMS" in fred:
        add("Payroll growth, 3-month average (thousands)", fred["PAYEMS"].diff().rolling(3).mean(), "k")
    if "SAHMREALTIME" in fred:
        add("Sahm rule indicator (pp; 0.50 = recession signal)", fred["SAHMREALTIME"], "pp")
    if "GDPC1" in fred:
        add("Real GDP growth, y/y (%)", (fred["GDPC1"] / fred["GDPC1"].shift(4) - 1) * 100, "pct")
    if "GDPC1" in fred and "GDPPOT" in fred:
        add("Output gap vs. CBO potential (%)",
            (fred["GDPC1"] / fred["GDPPOT"].reindex(fred["GDPC1"].index) - 1) * 100, "pct")
    rp = recession_probability(fred)
    if rp is not None:
        add("Recession probability, next 12 months (yield-curve model, %)", rp * 100, "pct")
    return pd.DataFrame(rows)

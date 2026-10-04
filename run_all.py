#!/usr/bin/env python
"""Build the research site: download data, run every study, write charts, tables, and pages.

    python run_all.py            # output in ./site, open site/index.html
"""
from __future__ import annotations

import logging
import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats as st

from src import backtest, charts, config, data, expectations, fed, fmt, liquidity, risk, sentiment, site, themes
from src import technicals as tech
from src.stats import random_entry_pvalue

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "site"
ASSETS = OUT / "assets"
TABLES = OUT / "data"
RESEARCH = ROOT / "research"

REPORTS = [
    ("net-liquidity", "01-net-liquidity-and-risk-assets.md",
     "Net liquidity and risk assets",
     "Does the Fed's net liquidity lead Bitcoin and the Nasdaq-100, and at what horizon?"),
    ("ma-retracements", "02-weekly-moving-average-retracements.md",
     "Buying retracements to the 50, 100, and 200-week averages",
     "Event study of pullbacks into major weekly moving averages, with a level map of current supports."),
    ("regime-model", "03-liquidity-regime-and-trend.md",
     "Liquidity regime and trend: a rules-based test",
     "Does conditioning exposure on the liquidity impulse and the 50-week trend improve risk-adjusted returns?"),
    ("ai-infrastructure", "04-ai-infrastructure-trade.md",
     "The AI infrastructure trade",
     "Compute, software, photonics, and nuclear power compared on trend, momentum, and liquidity sensitivity."),
    ("fed-policy", "05-fed-policy-monitor.md",
     "Fed policy monitor and FOMC event study",
     "Policy rates, curve, real yields, balance sheet, and asset returns on decision days."),
    ("rate-expectations", "06-rate-expectations-and-macro.md",
     "Rate expectations, policy rules, and recession risk",
     "Prediction-market odds for every upcoming FOMC meeting, Taylor-rule benchmarks, inflation, labor, and recession signals."),
    ("cross-asset-risk", "07-cross-asset-risk.md",
     "Cross-asset risk and financial conditions",
     "Credit spreads, volatility, the dollar, drawdowns, and shifting correlations across crypto, equities, bonds, and gold."),
    ("fear-and-greed", "08-buying-fear.md",
     "Buying fear: testing fear and greed extremes",
     "Do Bitcoin and U.S. stocks pay off when bought in fear or extreme fear? Regime returns, entry events, and dollar-cost averaging."),
]

log = logging.getLogger("build")


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def img(name: str, alt: str, root: str = "../") -> str:
    return f"\n![{alt}]({root}assets/{name})\n"


def save_csv(df: pd.DataFrame, name: str) -> str:
    df.to_csv(TABLES / name, index=False)
    return f"[Download the table as CSV](../data/{name})"


def weekly_close(prices: dict, ticker: str) -> pd.Series:
    return tech.to_weekly(prices[ticker], "W-FRI")["Close"]


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------
def load_context() -> dict:
    required = ["WALCL", "WTREGEN", "RRPONTSYD"]
    fred = data.load_fred(required)
    missing = [sid for sid in required if sid not in fred]
    if missing:
        hint = "" if os.environ.get("FRED_API_KEY") else (
            " FRED_API_KEY is not set; add it as a repository secret (see SETUP.md).")
        raise SystemExit(f"Required FRED series unavailable: {', '.join(missing)}.{hint}")
    fred.update(data.load_fred([sid for sid in config.FRED_SERIES if sid not in fred]))
    prices = data.load_prices(config.all_tickers())
    liq = liquidity.add_regime(liquidity.net_liquidity(fred))
    weekly = {t: tech.weekly_with_mas(prices[t], t) for t in config.CORE_ASSETS if t in prices}
    return {"fred": fred, "prices": prices, "liq": liq, "weekly": weekly}


def asset_name(t: str) -> str:
    return config.CORE_ASSETS.get(t, t)


# ---------------------------------------------------------------------------
# Study 1: net liquidity
# ---------------------------------------------------------------------------
def study_liquidity(ctx) -> tuple[str, str]:
    liq, prices = ctx["liq"], ctx["prices"]
    nl = liq["net_liquidity"]
    charts.net_liquidity(liq, ASSETS / "net_liquidity.png")

    tables, rolling = {}, {}
    for t in config.LEAD_LAG_ASSETS:
        if t not in prices:
            continue
        cw = weekly_close(prices, t)
        tables[asset_name(t)] = liquidity.lead_lag(nl, cw)
        rolling[asset_name(t)] = liquidity.rolling_correlation(nl, cw)
    if tables:
        charts.lead_lag_bars(tables, ASSETS / "lead_lag.png")
        charts.rolling_corr(rolling, ASSETS / "rolling_corr.png")
    for t in ("BTC-USD", "QQQ"):
        if t in prices:
            charts.liquidity_vs_asset(nl, weekly_close(prices, t), asset_name(t),
                                      ASSETS / f"liquidity_vs_{slug(t)}.png")

    n_tests = sum(len(v) for v in tables.values())
    bonf = 0.05 / n_tests if n_tests else float("nan")

    wide = None
    long_rows = []
    for name, t in tables.items():
        col = t.assign(cell=[f"{fmt.num(r, 2, sign=True)} (p {fmt.pval(p)})" for r, p in zip(t["corr"], t["p_value"])])
        part = col[["lead_weeks", "cell"]].rename(columns={"cell": name})
        wide = part if wide is None else wide.merge(part, on="lead_weeks")
        long_rows.append(t.assign(asset=name))
    findings = []
    last = liq.dropna(subset=["impulse_bn"]).iloc[-1]
    findings.append(
        f"Net liquidity was ${fmt.num(last['net_liquidity'], 0)} billion as of {fmt.date(last.name - pd.Timedelta(days=2))}, "
        f"{'up' if last['impulse_bn'] >= 0 else 'down'} ${fmt.num(abs(last['impulse_bn']), 0)} billion "
        f"({fmt.pct(last['impulse_pct'])}) over {config.LIQUIDITY_WINDOW} weeks. The regime reads {last['regime'].lower()}."
    )
    for name, t in tables.items():
        if t["corr"].notna().any():
            best = t.loc[t["corr"].abs().idxmax()]
            sig = "significant" if best["p_value"] < bonf else "not significant"
            findings.append(
                f"{name}: the largest correlation is at a +{int(best['lead_weeks'])}-week lead "
                f"(r = {fmt.num(best['corr'], 2, sign=True)}, p = {fmt.pval(best['p_value'])}, n = {int(best['n'])} blocks); "
                f"{sig} after a Bonferroni adjustment for {n_tests} tests (threshold p < {bonf:.4f})."
            )

    results = []
    results.append("### Net liquidity and its components" + img("net_liquidity.png", "Net liquidity chart"))
    comp = liq.dropna(subset=["impulse_bn"])
    snap = []
    for col, label in [("fed_assets", "Fed total assets"), ("tga", "Treasury General Account"),
                       ("rrp", "Overnight reverse repo"), ("net_liquidity", "Net liquidity")]:
        s = comp[col]
        snap.append({"Component ($bn)": label, "Latest": fmt.num(s.iloc[-1], 0),
                     "4W change": fmt.num(s.iloc[-1] - s.iloc[-5], 0, sign=True),
                     "13W change": fmt.num(s.iloc[-1] - s.iloc[-14], 0, sign=True),
                     "52W change": fmt.num(s.iloc[-1] - s.iloc[-53], 0, sign=True) if len(s) > 53 else fmt.DASH})
    results.append(fmt.md_table(pd.DataFrame(snap)))
    for t in ("BTC-USD", "QQQ"):
        if t in prices:
            results.append(img(f"liquidity_vs_{slug(t)}.png", f"Net liquidity and {asset_name(t)}"))
    if wide is not None:
        results.append("### Lead-lag correlations" + img("lead_lag.png", "Lead-lag correlations"))
        wide = wide.rename(columns={"lead_weeks": "Asset return lead (weeks)"})
        wide["Asset return lead (weeks)"] = wide["Asset return lead (weeks)"].map(lambda x: f"+{x}")
        results.append(fmt.md_table(wide))
        results.append(save_csv(pd.concat(long_rows), "lead_lag.csv") + "\n")
        results.append("### Stability over time" + img("rolling_corr.png", "Rolling correlation"))
    liq.reset_index().to_csv(TABLES / "net_liquidity.csv", index=False)
    results.append("[Download the weekly net liquidity series as CSV](../data/net_liquidity.csv)\n")
    return bullets(findings), "\n".join(results)


def bullets(items) -> str:
    return "\n".join(f"- {s}" for s in items) + "\n" if items else "_No findings in this build._\n"


# ---------------------------------------------------------------------------
# Study 2: moving-average retracements and level maps
# ---------------------------------------------------------------------------
def study_retracements(ctx) -> tuple[str, str, pd.DataFrame, pd.DataFrame]:
    prices, weekly = ctx["prices"], ctx["weekly"]
    summary, events_all, level_sections, testing_now, structure = [], [], [], [], []
    for t, w in weekly.items():
        name = asset_name(t)
        ev_by_ma = {}
        for n in config.MA_WINDOWS:
            col = f"SMA{n}"
            if w[col].notna().sum() < 10:
                continue
            idxs = tech.retracement_events(w, col)
            ev_by_ma[col] = idxs
            et = tech.event_table(w, col, idxs)
            baseline = tech.unconditional_forward_returns(w, col, 26)
            row = {"Asset": name, "Average": f"{n}W", "Events": len(idxs)}
            if not et.empty:
                events_all.append(et.assign(asset=name, average=f"{n}W"))
                row.update({
                    "Avg 13W": et["fwd_13w"].mean(),
                    "Avg 26W": et["fwd_26w"].mean(),
                    "Baseline 26W": baseline.mean(),
                    "Hit rate 26W": (et["fwd_26w"].dropna() > 0).mean() if et["fwd_26w"].notna().any() else np.nan,
                    "p (26W)": random_entry_pvalue(et["fwd_26w"], baseline),
                    "Avg 52W": et["fwd_52w"].mean(),
                    "Avg max DD 13W": et["max_drawdown_13w"].mean(),
                    "Held 4W": et["held_4w"].mean(),
                    "_n26": int(et["fwd_26w"].notna().sum()),
                })
            else:
                row["Baseline 26W"] = baseline.mean()
            summary.append(row)
            low = w["Low"].iloc[-1] if "Low" in w else w["Close"].iloc[-1]
            close_last, ma_last = w["Close"].iloc[-1], w[col].iloc[-1]
            band = config.RETRACE_BAND
            if pd.notna(ma_last) and low <= ma_last * (1 + band) and close_last >= ma_last * (1 - band):
                testing_now.append(f"{name} at the {n}W SMA ({fmt.price(ma_last)})")

        levels = tech.level_map(prices[t], w)
        supports = tech.nearest_levels(levels, "support", 3)
        resist = tech.nearest_levels(levels, "resistance", 3)
        charts.asset_structure(w, ev_by_ma, supports, name, ASSETS / f"structure_{slug(t)}.png")
        lv = pd.concat([resist.iloc[::-1], supports])
        lv_fmt = pd.DataFrame({
            "Level": lv["level"], "Price": lv["price"].map(fmt.price),
            "Distance": lv["distance"].map(fmt.pct), "Confluent levels": lv["confluence"],
        })
        last_close = w["Close"].iloc[-1]
        level_sections.append(
            f"### {name}\n\nLast weekly close {fmt.price(last_close)} ({fmt.date(w.index[-1])})."
            + img(f"structure_{slug(t)}.png", f"{name} weekly structure") + "\n" + fmt.md_table(lv_fmt)
        )
        structure.append({
            "Asset": name,
            "Last": fmt.price(last_close),
            **{f"vs {n}W": fmt.pct(last_close / w[f'SMA{n}'].iloc[-1] - 1) for n in config.MA_WINDOWS},
            "Nearest support": (f"{supports.iloc[0]['level']} {fmt.price(supports.iloc[0]['price'])} "
                                f"({fmt.pct(supports.iloc[0]['distance'])})") if len(supports) else fmt.DASH,
        })

    sm = pd.DataFrame(summary)
    ev = pd.concat(events_all) if events_all else pd.DataFrame()
    if not ev.empty:
        ev.to_csv(TABLES / "retracement_events.csv", index=False)
    sm.drop(columns=[c for c in sm.columns if c.startswith("_")]).to_csv(TABLES / "retracement_summary.csv", index=False)

    findings = []
    with_events = sm[sm["Events"] > 0] if "Avg 26W" in sm else pd.DataFrame()
    if not with_events.empty:
        valid = with_events.dropna(subset=["Avg 26W"])
        beat = int((valid["Avg 26W"] > valid["Baseline 26W"]).sum())
        findings.append(
            f"In {beat} of {len(valid)} asset–average pairs with completed 26-week outcomes, the average "
            f"26-week return after a retracement exceeded the all-weeks baseline for the same asset."
        )
        robust = valid[valid["_n26"] >= 5].sort_values("p (26W)").head(3)
        for _, r in robust.iterrows():
            findings.append(
                f"{r['Asset']} at the {r['Average']} SMA: {r['_n26']} events, average 26-week return "
                f"{fmt.pct(r['Avg 26W'])} vs. {fmt.pct(r['Baseline 26W'])} baseline, hit rate "
                f"{fmt.pct(r['Hit rate 26W'], 0, sign=False)}, permutation p = {fmt.pval(r['p (26W)'])}."
            )
        thin = int((with_events["Events"] < 5).sum())
        if thin:
            findings.append(f"{thin} pairs have fewer than five events; their averages are reported but carry little statistical weight.")
    findings.append("Currently testing an average: " + ("; ".join(testing_now) + "." if testing_now else "none this week."))

    show = sm.copy()
    for c in ("Avg 13W", "Avg 26W", "Baseline 26W", "Avg 52W", "Avg max DD 13W"):
        if c in show:
            show[c] = show[c].map(fmt.pct)
    for c in ("Hit rate 26W", "Held 4W"):
        if c in show:
            show[c] = show[c].map(lambda x: fmt.pct(x, 0, sign=False))
    if "p (26W)" in show:
        show["p (26W)"] = show["p (26W)"].map(fmt.pval)
    show = show.drop(columns=[c for c in show.columns if c.startswith("_") or c == "Avg 13W"])
    show = show.rename(columns={"Avg max DD 13W": "Max DD 13W"})

    results = ["### Event study summary\n", fmt.md_table(show),
               save_csv(sm.drop(columns=[c for c in sm.columns if c.startswith("_")]), "retracement_summary.csv") + "\n"]
    if not ev.empty:
        recent = ev.sort_values("date", ascending=False).head(15)
        rec = pd.DataFrame({
            "Week of": recent["date"].map(fmt.date), "Asset": recent["asset"], "Average": recent["average"],
            "Low vs. MA": recent["low_vs_ma"].map(fmt.pct), "13W after": recent["fwd_13w"].map(fmt.pct),
            "26W after": recent["fwd_26w"].map(fmt.pct), "52W after": recent["fwd_52w"].map(fmt.pct),
        })
        results += ["### Most recent events\n", fmt.md_table(rec), "[Download every event as CSV](../data/retracement_events.csv)\n"]
    results += ["### Level maps\n",
                "Nearest three levels above and below the latest weekly close. \"Confluent levels\" counts other "
                f"tracked levels within {config.LEVEL_CONFLUENCE_TOL:.1%} of the same price.\n"]
    results += level_sections
    return bullets(findings), "\n".join(results), pd.DataFrame(structure), pd.Series(testing_now, dtype=object)


# ---------------------------------------------------------------------------
# Study 3: regime and trend rules
# ---------------------------------------------------------------------------
def study_regime(ctx) -> tuple[str, str]:
    prices, liq, fred = ctx["prices"], ctx["liq"], ctx["fred"]
    if "DTB3" not in fred:
        return bullets(["T-bill data unavailable; regime study skipped this build."]), ""
    rf = backtest.weekly_rf(fred["DTB3"])
    findings, results, all_stats = [], [], []
    cond_rows = []
    for t in config.REGIME_TEST_ASSETS:
        if t not in prices:
            continue
        name = asset_name(t)
        cw = weekly_close(prices, t)
        signals = backtest.build_signals(cw, liq["expanding"])
        curves, stats_df, rets = backtest.run_backtest(cw, signals, rf)
        if stats_df.empty:
            continue
        charts.equity_curves(curves, name, ASSETS / f"equity_{slug(t)}.png")
        all_stats.append(stats_df.assign(asset=name, start=curves.index[0], end=curves.index[-1]))
        disp = stats_df.copy()
        for c in ("CAGR", "Volatility", "Max drawdown", "Total return"):
            disp[c] = disp[c].map(lambda x: fmt.pct(x, 1, sign=False) if c != "Max drawdown" else fmt.pct(x))
        disp["Sharpe"] = disp["Sharpe"].map(lambda x: fmt.num(x, 2))
        disp["Time invested"] = disp["Time invested"].map(lambda x: fmt.pct(x, 0, sign=False))
        sub = backtest.subperiod_sharpe(rets)
        for c in sub.columns[1:]:
            sub[c] = sub[c].map(lambda x: fmt.num(x, 2))
        current = {k: v.dropna().iloc[-1] if v.notna().any() else np.nan for k, v in signals.items()}
        state = "; ".join(f"{k}: {'invested' if v == 1 else 'in T-bills'}" for k, v in current.items()
                          if k != "Buy and hold" and pd.notna(v))
        results.append(
            f"### {name}\n\nSample {fmt.date(curves.index[0])} to {fmt.date(curves.index[-1])}, weekly, "
            f"{config.COST_BPS} bp per switch, cash earns the 3-month T-bill rate.\n"
            + img(f"equity_{slug(t)}.png", f"{name} equity curves") + "\n"
            + fmt.md_table(disp[["Strategy", "CAGR", "Volatility", "Sharpe", "Max drawdown", "Time invested", "Switches"]])
            + "\nSharpe ratio by sub-period:\n\n" + fmt.md_table(sub)
            + f"\nSignals as of the latest week: {state}.\n"
        )
        bh = stats_df.iloc[0]
        combo = stats_df[stats_df["Strategy"] == "Liquidity and trend"].iloc[0]
        findings.append(
            f"{name}: the combined liquidity-and-trend rule produced a Sharpe ratio of {fmt.num(combo['Sharpe'], 2)} "
            f"vs. {fmt.num(bh['Sharpe'], 2)} for buy-and-hold, with a maximum drawdown of {fmt.pct(combo['Max drawdown'])} "
            f"vs. {fmt.pct(bh['Max drawdown'])}, while invested {fmt.pct(combo['Time invested'], 0, sign=False)} of weeks."
        )
        # Conditional weekly returns by regime (non-overlapping weekly returns)
        r = (cw / cw.shift(1) - 1).rename("ret")
        reg = liq["expanding"].shift(1).reindex(r.index)
        df = pd.concat([r, reg.rename("exp")], axis=1).dropna()
        a, b = df.loc[df["exp"] == 1, "ret"], df.loc[df["exp"] == 0, "ret"]
        if len(a) > 20 and len(b) > 20:
            tstat, p = st.ttest_ind(a, b, equal_var=False)
            cond_rows.append({"Asset": name,
                              "Expanding: weeks": len(a), "Expanding: ann. return": fmt.pct(a.mean() * 52),
                              "Contracting: weeks": len(b), "Contracting: ann. return": fmt.pct(b.mean() * 52),
                              "Welch t": fmt.num(tstat, 2), "p": fmt.pval(p)})
    if cond_rows:
        results.insert(0, "### Returns by liquidity regime\n\nMean weekly return in the week after each regime reading, annualized "
                          "(simple × 52). Welch's t-test compares the two groups.\n\n" + fmt.md_table(pd.DataFrame(cond_rows)))
    if all_stats:
        pd.concat(all_stats).to_csv(TABLES / "regime_backtests.csv", index=False)
        results.append("[Download all backtest statistics as CSV](../data/regime_backtests.csv)\n")
    return bullets(findings), "\n".join(results)


# ---------------------------------------------------------------------------
# Study 4: thematic baskets
# ---------------------------------------------------------------------------
def study_themes(ctx) -> tuple[str, str, pd.DataFrame]:
    prices, liq = ctx["prices"], ctx["liq"]
    if config.BENCHMARK not in prices:
        return bullets(["Benchmark data unavailable; themes study skipped this build."]), "", pd.DataFrame()
    bench = weekly_close(prices, config.BENCHMARK)
    indices, counts = {}, {}
    for name, members in config.THEMES.items():
        level, count = themes.basket_index(prices, members)
        if not level.empty:
            indices[name], counts[name] = level, count
    summary = themes.theme_summary(indices, bench, liq["net_liquidity"])
    charts.theme_indices(indices, bench, config.BENCHMARK, ASSETS / "themes.png")
    summary.to_csv(TABLES / "theme_summary.csv", index=False)

    findings = []
    if not summary.empty:
        ranked = summary.sort_values("26W", ascending=False)
        findings.append("26-week return ranking: " + "; ".join(
            f"{r['Theme']} {fmt.pct(r['26W'])}" for _, r in ranked.iterrows()) + ".")
        above = summary[(summary["vs 50W SMA"] > 0) & (summary["vs 200W SMA"] > 0)]["Theme"].tolist()
        below = summary[(summary["vs 50W SMA"] < 0)]["Theme"].tolist()
        findings.append("Above both the 50W and 200W SMA: " + (", ".join(above) if above else "none") + ". "
                        "Below the 50W SMA: " + (", ".join(below) if below else "none") + ".")
        bcol = f"Beta to {config.BENCHMARK} (3Y)"
        hb = summary.loc[summary[bcol].idxmax()] if summary[bcol].notna().any() else None
        if hb is not None:
            findings.append(f"Highest 3-year beta to {config.BENCHMARK}: {hb['Theme']} ({fmt.num(hb[bcol], 2)}).")
        lc = summary.dropna(subset=["Liquidity corr."])
        if not lc.empty:
            sig = lc[lc["Liquidity p"] < 0.05]
            if sig.empty:
                largest = lc["Liquidity corr."].abs().max()
                findings.append(
                    "No basket shows a statistically significant same-period correlation with 4-week changes "
                    f"in net liquidity (largest |r| = {largest:.2f}).")
            else:
                findings.append("Significant same-period correlation with 4-week net liquidity changes: " + "; ".join(
                    f"{r['Theme']} (r = {fmt.num(r['Liquidity corr.'], 2, sign=True)}, p = {fmt.pval(r['Liquidity p'])})"
                    for _, r in sig.iterrows()) + ".")

    disp = summary.copy()
    for c in disp.columns:
        if c in ("Theme",):
            continue
        if c.startswith("Beta") or c == "Liquidity corr.":
            disp[c] = disp[c].map(lambda x: fmt.num(x, 2))
        elif c == "Liquidity p":
            disp[c] = disp[c].map(fmt.pval)
        else:
            disp[c] = disp[c].map(fmt.pct)
    results = ["### Basket performance" + img("themes.png", "Thematic baskets"), fmt.md_table(disp),
               "[Download as CSV](../data/theme_summary.csv)\n", "### Constituents\n"]
    for name, members in config.THEMES.items():
        mt = themes.member_table(prices, members)
        if mt.empty:
            continue
        mt_disp = mt.copy()
        for c in ("13W", "52W", "From 52W high", "vs 50W SMA", "vs 200W SMA"):
            mt_disp[c] = mt_disp[c].map(fmt.pct)
        mt_disp["History (yrs)"] = mt_disp["History (yrs)"].map(lambda x: fmt.num(x, 1))
        start = counts[name].index[0] if name in counts else None
        results.append(f"**{name}** (basket begins {fmt.date(start)})\n\n" + fmt.md_table(mt_disp))
    etfs = [e for e in set(config.THEME_ETFS.values()) if e in prices]
    if etfs:
        et = themes.member_table(prices, sorted(etfs))
        for c in ("13W", "52W", "From 52W high", "vs 50W SMA", "vs 200W SMA"):
            et[c] = et[c].map(fmt.pct)
        et["History (yrs)"] = et["History (yrs)"].map(lambda x: fmt.num(x, 1))
        results.append("**Sector ETF cross-check** (market-cap weighted, no hindsight selection)\n\n" + fmt.md_table(et))
    return bullets(findings), "\n".join(results), summary


# ---------------------------------------------------------------------------
# Study 5: Fed policy
# ---------------------------------------------------------------------------
def study_fed(ctx) -> tuple[str, str, pd.DataFrame, dict]:
    fred, prices, liq = ctx["fred"], ctx["prices"], ctx["liq"]
    table, _ = fed.policy_table(fred, liq["net_liquidity"])
    charts.fed_rates(fred, ASSETS / "fed_rates.png")
    charts.curve_and_spread(fred, ASSETS / "curve.png")
    fomc = fed.load_fomc_dates(fred.get("DFEDTARU"))
    today = pd.Timestamp(datetime.now(timezone.utc).date())
    upcoming = fomc[fomc["date"] > today]
    next_fomc = upcoming["date"].iloc[0] if len(upcoming) else None
    done = fomc[fomc.get("decision", pd.Series("Hold", index=fomc.index)) != "Pending"]

    rows, raw = [], []
    for t in config.FOMC_TICKERS:
        if t not in prices:
            continue
        close = prices[t]["Close"]
        ev = fed.fomc_event_returns(close, done)
        if ev.empty:
            continue
        raw.append(ev.assign(asset=t))
        b1, b6 = fed.baseline_returns(close, 1).mean(), fed.baseline_returns(close, 6).mean()
        groups = [("All decisions", ev)] + [(d, ev[ev["decision"] == d]) for d in ("Cut", "Hold", "Hike")]
        for label, g in groups:
            if g.empty:
                continue
            rows.append({"Asset": t, "Decision": label, "n": len(g),
                         "Avg day 0": fmt.pct(g["day0"].mean(), 2), "Day 0 up": fmt.pct((g["day0"] > 0).mean(), 0, sign=False),
                         "Avg day 0 to +5": fmt.pct(g["day0_to_5"].mean(), 2),
                         "Baseline 1 session": fmt.pct(b1, 2), "Baseline 6 sessions": fmt.pct(b6, 2)})
    if raw:
        pd.concat(raw).to_csv(TABLES / "fomc_events.csv", index=False)

    tbl = table.copy()
    usd = tbl["Indicator"].str.contains(r"\$bn")
    for c in ("Latest", "4W change", "13W change", "52W change"):
        tbl[c] = [fmt.num(v, 0, sign=(c != "Latest")) if u else fmt.num(v, 2, sign=(c != "Latest"))
                  for v, u in zip(tbl[c], usd)]
    tbl["As of"] = tbl["As of"].map(fmt.date)
    table.to_csv(TABLES / "policy_monitor.csv", index=False)

    def val(label):
        s = table.loc[table["Indicator"] == label, "Latest"]
        return float(s.iloc[0]) if len(s) else float("nan")

    def chg(label, col="52W change"):
        s = table.loc[table["Indicator"] == label, col]
        return float(s.iloc[0]) if len(s) else float("nan")

    findings = []
    upper = val("Fed funds target, upper bound (%)")
    if not np.isnan(upper):
        findings.append(f"Target range upper bound {fmt.num(upper, 2)}%, a change of "
                        f"{fmt.num(chg('Fed funds target, upper bound (%)') * 100, 0, sign=True)} bp over 52 weeks.")
    spread = val("2-year minus fed funds (pp)")
    if not np.isnan(spread):
        if spread < -0.25:
            read = "consistent with markets pricing a lower policy rate over the next two years"
        elif spread > 0.25:
            read = "consistent with markets pricing a higher policy rate over the next two years"
        else:
            read = "consistent with little net change in the policy rate priced over two years"
        findings.append(f"The 2-year Treasury yield sits {fmt.num(spread, 2, sign=True)} pp from the effective fed funds rate, {read}.")
    real = val("10-year real yield, TIPS (%)")
    if not np.isnan(real):
        findings.append(f"10-year real yield {fmt.num(real, 2)}% ({fmt.num(chg('10-year real yield, TIPS (%)', '13W change'), 2, sign=True)} pp over 13 weeks).")
    assets_13 = chg("Fed total assets ($bn)", "13W change")
    if not np.isnan(assets_13):
        findings.append(f"Fed total assets changed {fmt.num(assets_13, 0, sign=True)} billion over 13 weeks "
                        f"(annualized pace {fmt.num(assets_13 * 4, 0, sign=True)} billion).")
    if "decision" in fomc:
        past = fomc[fomc["decision"] != "Pending"]
        if len(past):
            ld = past.iloc[-1]
            if ld["decision"] == "Hold":
                action = "held the target range unchanged"
            else:
                verb = "raised" if ld["decision"] == "Hike" else "lowered"
                action = f"{verb} the target range by {abs(int(ld['change_bp']))} bp"
            findings.append(f"The most recent decision ({fmt.date(ld['date'])}) {action}.")
    if next_fomc is not None:
        findings.append(f"Next scheduled FOMC decision: {fmt.date(next_fomc)}.")

    results = ["### Policy monitor\n", fmt.md_table(tbl), "[Download as CSV](../data/policy_monitor.csv)\n",
               img("fed_rates.png", "Policy rate and Treasury yields"), img("curve.png", "Curve and policy spread"),
               "### FOMC decision-day returns\n",
               "Day 0 runs from the prior close to the close on decision day; day 0 to +5 adds five further sessions "
               "(calendar days for crypto). Baselines are the average return over the same number of sessions across all days.\n",
               fmt.md_table(pd.DataFrame(rows))]
    if raw:
        results.append("[Download every decision-day return as CSV](../data/fomc_events.csv)\n")
    meta = {"next_fomc": next_fomc}
    return bullets(findings), "\n".join(results), tbl, meta


# ---------------------------------------------------------------------------
# Study 6: rate expectations, policy rules, recession risk
# ---------------------------------------------------------------------------
def _pct_pts(x, d=2):
    return fmt.DASH if fmt._missing(x) else f"{x:.{d}f}%"


def study_expectations(ctx, next_fomc) -> tuple[str, str, dict]:
    fred = ctx["fred"]
    meta, findings, results = {}, [], []
    current = float(fred["DFEDTARU"].dropna().iloc[-1]) if "DFEDTARU" in fred else float("nan")
    path = expectations.kalshi_rate_path(current) if not np.isnan(current) else None

    # Next-meeting odds from both venues
    buckets, meeting = {}, next_fomc
    if path is not None:
        first = path.iloc[0]
        meeting = first["meeting"]
        changes = pd.Series(first["dist"].to_numpy(), index=first["dist"].index - current)
        buckets["Kalshi"] = expectations.to_buckets(changes)
    poly = expectations.polymarket_next_meeting(pd.Timestamp(meeting)) if meeting is not None else None
    if poly is not None:
        buckets["Polymarket"] = poly
    results.append("### Next FOMC decision\n")
    if buckets:
        charts.rate_odds_bars(buckets, meeting, ASSETS / "rate_odds.png")
        odds = pd.DataFrame(buckets)
        odds.index.name = "Outcome"
        tbl = odds.reset_index()
        for c in buckets:
            tbl[c] = tbl[c].map(lambda x: fmt.pct(x, 0, sign=False))
        results += [img("rate_odds.png", "Prediction-market odds"), fmt.md_table(tbl)]
        odds.reset_index().to_csv(TABLES / "next_meeting_odds.csv", index=False)
        for src, b in buckets.items():
            top = b.idxmax()
            findings.append(f"{src} prices {fmt.article(fmt.pct(b.max(), 0, sign=False))} {fmt.pct(b.max(), 0, sign=False)} probability of "
                            f"{expectations.BUCKET_PHRASES[top]} at the {fmt.date(meeting)} FOMC meeting.")
        k = buckets.get("Kalshi", next(iter(buckets.values())))
        src = "Kalshi" if "Kalshi" in buckets else next(iter(buckets))
        pk = fmt.pct(k.max(), 0, sign=False)
        meta["odds_text"] = f"{src} prices {fmt.article(pk)} {pk} probability of {expectations.BUCKET_PHRASES[k.idxmax()]}."
        meta["odds_table"] = tbl
    else:
        results.append("_Prediction-market data was unavailable for this build._\n")

    # Full implied path
    results.append("### Market-implied path for the policy rate\n")
    if path is not None:
        charts.implied_path(path, current, ASSETS / "implied_path.png")
        ptab = pd.DataFrame({
            "Meeting": path["meeting"].map(fmt.date),
            "Expected upper bound": path["expected"].map(lambda x: _pct_pts(x)),
            "Most likely": [f"{m:.2f}% ({fmt.pct(p, 0, sign=False)})" for m, p in zip(path["mode"], path["mode_p"])],
            "10th–90th percentile": [f"{a:.2f}–{b:.2f}%" for a, b in zip(path["p10"], path["p90"])],
            "P(below today)": path["p_lower"].map(lambda x: fmt.pct(x, 0, sign=False)),
            "P(above today)": path["p_higher"].map(lambda x: fmt.pct(x, 0, sign=False)),
        })
        results += [img("implied_path.png", "Implied policy path"), fmt.md_table(ptab)]
        path.drop(columns=["dist"]).to_csv(TABLES / "kalshi_rate_path.csv", index=False)
        long = pd.concat([pd.DataFrame({"meeting": r["meeting"], "upper_bound": r["dist"].index,
                                        "probability": r["dist"].to_numpy()}) for _, r in path.iterrows()])
        long.to_csv(TABLES / "kalshi_rate_distributions.csv", index=False)
        results.append("[Download the path](../data/kalshi_rate_path.csv) and "
                       "[the full probability distribution for each meeting](../data/kalshi_rate_distributions.csv) as CSV.\n")
        last = path.iloc[-1]
        findings.append(
            f"Kalshi contracts imply an expected upper bound of {last['expected']:.2f}% after the "
            f"{fmt.date(last['meeting'])} meeting, {fmt.num((last['expected'] - current) * 100, 0, sign=True)} bp "
            f"from today's {current:.2f}%, with an 80% range of {last['p10']:.2f}–{last['p90']:.2f}%.")
        meta["path"] = path
        meta["current_upper"] = current
    else:
        results.append("_Kalshi rate contracts were unavailable for this build._\n")

    # Policy rules
    tr = expectations.taylor_rules(fred)
    results.append("### Policy rules\n")
    if tr is not None and not tr.empty:
        charts.taylor_chart(tr, list(config.TAYLOR_RULES), ASSETS / "taylor.png")
        latest = tr.iloc[-1]
        rows = [{"Rule": n, "r*": f"{r:.1f}%", "Inflation wt.": a, "Gap wt.": b,
                 "Prescribed rate": _pct_pts(latest[n]), "Actual midpoint": _pct_pts(latest["actual"]),
                 "Actual minus rule": fmt.num(latest["actual"] - latest[n], 2, sign=True)}
                for n, (r, a, b) in config.TAYLOR_RULES.items()]
        results += [img("taylor.png", "Taylor rules"),
                    f"Inputs as of {fmt.date(latest.name)}: core PCE inflation {latest['inflation']:.2f}%, "
                    f"output gap {latest['output_gap']:+.2f}%.\n", fmt.md_table(pd.DataFrame(rows))]
        tr.reset_index().to_csv(TABLES / "taylor_rules.csv", index=False)
        base = next(iter(config.TAYLOR_RULES))
        gap = latest["actual"] - latest[base]
        findings.append(
            f"With core PCE inflation at {latest['inflation']:.2f}% and an output gap of {latest['output_gap']:+.2f}%, "
            f"the {base} rule prescribes {latest[base]:.2f}%; the actual midpoint is "
            f"{abs(gap):.2f} pp {'above' if gap > 0 else 'below'} it.")
        meta["taylor"] = (base, float(latest[base]), float(latest["actual"]))

    # Recession signals and macro table
    rp = expectations.recession_probability(fred)
    if rp is not None and len(rp):
        charts.recession_chart(rp, fred.get("USREC"), ASSETS / "recession.png")
        spread = fred["T10Y3M"].resample("MS").mean().dropna().reindex(rp.index)
        findings.append(
            f"The yield-curve model puts the probability of a recession within 12 months at "
            f"{fmt.pct(rp.iloc[-1], 0, sign=False)}, from a 10-year minus 3-month spread averaging "
            f"{spread.iloc[-1]:+.2f} pp in {rp.index[-1]:%B %Y}.")
        meta["recession_prob"] = float(rp.iloc[-1])
    if "SAHMREALTIME" in fred and len(fred["SAHMREALTIME"].dropna()):
        sahm = fred["SAHMREALTIME"].dropna()
        state = "above" if sahm.iloc[-1] >= 0.5 else "below"
        findings.append(f"The real-time Sahm rule reads {sahm.iloc[-1]:.2f} pp ({sahm.index[-1]:%B %Y}), "
                        f"{state} the 0.50 recession threshold.")
    mt = expectations.macro_table(fred)
    results.append("### Inflation, labor, and growth\n")
    charts.inflation_labor(fred, ASSETS / "inflation_labor.png")
    results.append(img("inflation_labor.png", "Inflation and labor"))
    if not mt.empty:
        disp = pd.DataFrame({
            "Indicator": mt["Indicator"],
            "Latest": [fmt.num(v, 0) if u == "k" else fmt.num(v, 2) for v, u in zip(mt["Latest"], mt["unit"])],
            "As of": mt["As of"].map(lambda d: f"{pd.Timestamp(d):%b %Y}"),
            "3 months ago": [fmt.num(v, 0) if u == "k" else fmt.num(v, 2) for v, u in zip(mt["3 months ago"], mt["unit"])],
            "12 months ago": [fmt.num(v, 0) if u == "k" else fmt.num(v, 2) for v, u in zip(mt["12 months ago"], mt["unit"])],
        })
        results.append(fmt.md_table(disp))
        mt.drop(columns=["note"]).to_csv(TABLES / "macro_dashboard.csv", index=False)
        meta["macro_table"] = disp
    if rp is not None and len(rp):
        results.append(img("recession.png", "Recession probability"))
    return bullets(findings), "\n".join(results), meta


# ---------------------------------------------------------------------------
# Study 7: cross-asset risk and financial conditions
# ---------------------------------------------------------------------------
def study_risk(ctx) -> tuple[str, str, pd.DataFrame]:
    fred, prices = ctx["fred"], ctx["prices"]
    findings, results = [], []
    ct = risk.conditions_table(fred)
    results.append("### Financial conditions\n")
    if charts.conditions_panel(fred, ASSETS / "conditions.png"):
        results.append(img("conditions.png", "Financial conditions"))
    if not ct.empty:
        disp = pd.DataFrame({
            "Indicator": ct["Indicator"], "Latest": ct["Latest"].map(lambda v: fmt.num(v, 2)),
            "As of": ct["As of"].map(fmt.date), "13W change": ct["13W change"].map(lambda v: fmt.num(v, 2, sign=True)),
            "Percentile": ct["Percentile"].map(fmt.ordinal),
            "z-score": ct["z-score"].map(lambda v: fmt.num(v, 2, sign=True)),
            "Range": [f"{fmt.num(a, 2)} to {fmt.num(b, 2)}" for a, b in zip(ct["Window low"], ct["Window high"])],
            "Window": ct["Window years"].map(lambda v: f"{v:.1f} yrs"),
        })
        results.append(fmt.md_table(disp))
        ct.to_csv(TABLES / "financial_conditions.csv", index=False)
        for key in ("BAMLH0A0HYM2", "VIXCLS"):
            r = ct[ct["series"] == key]
            if len(r):
                r = r.iloc[0]
                findings.append(f"{r['Indicator']} at {r['Latest']:.2f}, the {fmt.ordinal(r['Percentile'])} "
                                f"percentile of its last {r['Window years']:.0f} years "
                                f"({fmt.num(r['13W change'], 2, sign=True)} over 13 weeks).")
        r = ct[ct["series"] == "NFCI"]
        if len(r):
            v = r.iloc[0]["Latest"]
            findings.append(f"The Chicago Fed NFCI reads {v:+.2f}: financial conditions are "
                            f"{'tighter' if v > 0 else 'looser'} than their long-run average.")

    rf = backtest.weekly_rf(fred["DTB3"]) if "DTB3" in fred else None
    at = risk.asset_risk_table(prices, rf)
    results.append("### Volatility, drawdowns, and risk-adjusted returns\n")
    if not at.empty:
        disp = at.copy()
        for c in ("13W", "52W", "From peak", "Max drawdown 3Y"):
            disp[c] = disp[c].map(fmt.pct)
        for c in ("Vol 13W", "Vol 52W"):
            disp[c] = disp[c].map(lambda v: fmt.pct(v, 1, sign=False))
        disp["Sharpe 3Y"] = disp["Sharpe 3Y"].map(lambda v: fmt.num(v, 2))
        results.append(fmt.md_table(disp))
        at.to_csv(TABLES / "asset_risk.csv", index=False)
        hv = at.loc[at["Vol 52W"].idxmax()]
        bs = at.loc[at["Sharpe 3Y"].idxmax()]
        findings.append(f"Highest 52-week volatility: {hv['Asset']} ({fmt.pct(hv['Vol 52W'], 1, sign=False)} annualized). "
                        f"Best 3-year Sharpe ratio: {bs['Asset']} ({bs['Sharpe 3Y']:.2f}).")
    corr = risk.correlation_matrix(prices)
    results.append("### Correlations\n")
    if corr.shape[0] >= 3:
        charts.corr_heatmap(corr, ASSETS / "correlations.png")
        results.append(img("correlations.png", "Correlation matrix"))
        corr.to_csv(TABLES / "correlation_matrix.csv")
        if "Bitcoin" in corr:
            b = corr["Bitcoin"].drop("Bitcoin").dropna()
            if len(b):
                findings.append(f"Over two years, Bitcoin's weekly returns correlate most with {b.idxmax()} "
                                f"({b.max():+.2f}) and least with {b.idxmin()} ({b.min():+.2f}).")
    pairs = [("BTC-USD", "QQQ"), ("BTC-USD", "GLD"), ("SPY", "TLT")]
    rc = risk.rolling_pair_correlations(prices, pairs)
    rc = {k: v[v.index >= v.index[-1] - pd.DateOffset(years=8)] for k, v in rc.items() if len(v)}
    if rc:
        charts.rolling_corr(rc, ASSETS / "rolling_pairs.png", title="Rolling 26-week correlation of weekly returns")
        results.append(img("rolling_pairs.png", "Rolling pair correlations"))
        sb = rc.get("S&P 500 vs Long Treasuries")
        if sb is not None and len(sb):
            findings.append(f"The 26-week stock-bond correlation (S&P 500 vs. long Treasuries) is {sb.iloc[-1]:+.2f}; "
                            f"{'positive, so long bonds have not been hedging equity declines' if sb.iloc[-1] > 0 else 'negative, so long bonds have been offsetting equity moves'}.")
    return bullets(findings), "\n".join(results), ct


# ---------------------------------------------------------------------------
# Study 8: fear and greed
# ---------------------------------------------------------------------------
CRYPTO_H = {"1 month": 30, "3 months": 91, "6 months": 182, "12 months": 365}
EQUITY_H = {"1 month": 21, "3 months": 63, "6 months": 126, "12 months": 252}


def _regime_display(t: pd.DataFrame) -> pd.DataFrame:
    d = t.copy()
    for c in d.columns[1:]:
        d[c] = d[c].map(lambda v: fmt.pct(v, 0, sign=False) if not fmt._missing(v) else fmt.DASH) \
            if (c.startswith("Share") or c.startswith("Hit")) else d[c].map(fmt.pct)
    return d


def study_sentiment(ctx) -> tuple[str, str, pd.DataFrame | None]:
    fred, prices = ctx["fred"], ctx["prices"]
    findings, results = [], []
    rf = backtest.weekly_rf(fred["DTB3"]) if "DTB3" in fred else None
    cfg = sentiment.crypto_fear_greed()
    eq = sentiment.equity_fear_greed(prices, fred)
    efg, comps = (eq if eq is not None else (None, None))

    # Current readings
    cur = []
    for label, s in [("Crypto Fear & Greed Index (Alternative.me)", cfg), ("Equity fear-and-greed composite", efg)]:
        if s is None or s.dropna().empty:
            continue
        s = s.dropna()
        yr = s[s.index >= s.index[-1] - pd.DateOffset(years=1)]
        cur.append({"Index": label, "Latest": f"{s.iloc[-1]:.0f}",
                    "Regime": sentiment.classify(s.iloc[-1:]).iloc[0], "As of": fmt.date(s.index[-1]),
                    "30-day average": f"{s.iloc[-30:].mean():.0f}",
                    "1-year low / high": f"{yr.min():.0f} / {yr.max():.0f}"})
        findings.append(f"{label}: {s.iloc[-1]:.0f} ({sentiment.classify(s.iloc[-1:]).iloc[0].lower()}) "
                        f"as of {fmt.date(s.index[-1])}.")
    cur_df = pd.DataFrame(cur)
    results += ["### Current readings\n", fmt.md_table(cur_df)]

    pairs = []
    if cfg is not None:
        pairs += [("BTC-USD", cfg, CRYPTO_H, "Crypto Fear & Greed Index", 30), ("ETH-USD", cfg, CRYPTO_H, "Crypto Fear & Greed Index", 30)]
    if efg is not None:
        pairs += [("SPY", efg, EQUITY_H, "equity fear-and-greed composite", 21), ("QQQ", efg, EQUITY_H, "equity fear-and-greed composite", 21)]
    pairs = [p for p in pairs if p[0] in prices]

    regime_rows, event_rows, recent_events, dca_rows = [], [], [], []
    sections = {}
    for t, sent, hz, iname, dd in pairs:
        name = asset_name(t)
        close = prices[t]["Close"].dropna()
        close = close[close.index >= sent.dropna().index[0] - pd.Timedelta(days=5)]
        tbl = sentiment.regime_table(close, sent, hz, "6 months")
        regime_rows.append(tbl.assign(Asset=name))
        sec = [f"#### {name}\n", fmt.md_table(_regime_display(tbl))]
        if t in ("BTC-USD", "SPY"):
            charts.sentiment_history(close, sent, name, iname, ASSETS / f"sentiment_{slug(t)}.png")
            charts.regime_bars(tbl, list(hz), name, ASSETS / f"sentiment_regimes_{slug(t)}.png")
            sec = [f"#### {name}\n", img(f"sentiment_{slug(t)}.png", f"{name} and sentiment"),
                   img(f"sentiment_regimes_{slug(t)}.png", f"{name} returns by regime"),
                   fmt.md_table(_regime_display(tbl))]
        sections.setdefault(iname, []).extend(sec)
        ef = tbl[tbl["Regime"] == "Extreme Fear"]
        al = tbl[tbl["Regime"] == "All days"]
        if len(ef) and len(al) and not fmt._missing(ef.iloc[0]["Avg 6 months"]):
            findings.append(
                f"{name}: average 6-month return of {fmt.pct(ef.iloc[0]['Avg 6 months'])} after extreme-fear days "
                f"vs. {fmt.pct(al.iloc[0]['Avg 6 months'])} across all days "
                f"(positive {fmt.pct(ef.iloc[0]['Hit rate 6 months'], 0, sign=False)} of the time).")
        for thr, lab in [(25, "Extreme fear (below 25)"), (45, "Fear (below 45)")]:
            ev, summ = sentiment.event_study(close, sent, thr, hz, "6 months", dd, cooldown=dd)
            if summ.get("n", 0) == 0:
                continue
            event_rows.append({"Asset": name, "Entry into": lab, "Events": summ["n"],
                               "Avg 3 months": fmt.pct(summ.get("Avg 3 months")),
                               "Avg 6 months": fmt.pct(summ.get("Avg 6 months")),
                               "Baseline 6 months": fmt.pct(summ.get("Baseline 6 months")),
                               "Hit rate 6 months": fmt.pct(summ.get("Hit rate 6 months"), 0, sign=False),
                               "p (6 months)": fmt.pval(summ.get("p")),
                               "Further drawdown, next month": fmt.pct(summ.get("Avg further drawdown"))})
            if thr == 25:
                recent_events.append(ev.assign(Asset=name))
                if summ["n"] >= 3:
                    findings.append(
                        f"{name}, entries into extreme fear: {summ['n']} events, average 6-month return "
                        f"{fmt.pct(summ.get('Avg 6 months'))} vs. {fmt.pct(summ.get('Baseline 6 months'))} baseline, "
                        f"permutation p = {fmt.pval(summ.get('p'))}; the average further decline in the following "
                        f"month was {fmt.pct(summ.get('Avg further drawdown'))}.")
        if t in ("BTC-USD", "SPY"):
            curves, stats = sentiment.dca_compare(close, sent, rf, rule="W-SUN" if t in config.CRYPTO else "W-FRI")
            if curves is not None:
                charts.dca_chart(curves, 100, name, ASSETS / f"dca_{slug(t)}.png")
                dca_rows.append((name, curves, stats))
                base, ext = stats.iloc[0], stats.iloc[-1]
                findings.append(
                    f"{name}, $100 a week since {fmt.date(curves.index[0])}: buying only in extreme fear ended at "
                    f"${ext['Ending value']:,.0f} (money-weighted return {fmt.pct(ext['Money-weighted return'])} a year) "
                    f"vs. ${base['Ending value']:,.0f} ({fmt.pct(base['Money-weighted return'])}) for buying every week.")

    for iname, sec in sections.items():
        title = "Crypto Fear & Greed Index" if iname.startswith("Crypto") else "Equity fear-and-greed composite"
        results.append(f"### Forward returns by regime: {title}\n")
        results += sec
    if comps is not None and not comps.dropna(how="all").empty:
        last = comps.dropna(how="all").iloc[-1]
        results.append("#### Equity composite components (latest percentile score, 0 = most fearful)\n")
        results.append(fmt.md_table(pd.DataFrame({"Component": last.index, "Score": [f"{v:.0f}" if not np.isnan(v) else fmt.DASH for v in last]})))
    if event_rows:
        results += ["### Entries into fear and extreme fear\n",
                    "Each event is the first day the index drops below the threshold, with re-entries inside one month ignored. "
                    "Returns run from that day's close. The p-value compares the events' average 6-month return with "
                    "5,000 sets of randomly chosen days.\n", fmt.md_table(pd.DataFrame(event_rows))]
    if recent_events:
        rec = pd.concat(recent_events).sort_values("date", ascending=False).head(12)
        hz_cols = [c for c in ("1 month", "3 months", "6 months", "12 months") if c in rec]
        rd = pd.DataFrame({"Date": rec["date"].map(fmt.date), "Asset": rec["Asset"], "Index": rec["index"].map(lambda v: f"{v:.0f}"),
                           **{c: rec[c].map(fmt.pct) for c in hz_cols}})
        results += ["#### Most recent entries into extreme fear\n", fmt.md_table(rd)]
        pd.concat(recent_events).to_csv(TABLES / "sentiment_events.csv", index=False)
    if dca_rows:
        results.append("### Dollar-cost averaging by sentiment\n")
        results.append("Each rule sets aside $100 every week. \"Every week\" invests it immediately; the other two hold it in "
                       "T-bills until the index (as of the prior day) is below the threshold, then invest all accumulated cash. "
                       "Money-weighted return is the annualized internal rate of return on the weekly contributions.\n")
        all_stats = []
        for name, curves, stats in dca_rows:
            disp = stats.copy()
            for c in ("Contributed", "Ending value", "Cash at end"):
                disp[c] = disp[c].map(lambda v: f"${v:,.0f}")
            disp["Gain"] = disp["Gain"].map(fmt.pct)
            disp["Money-weighted return"] = disp["Money-weighted return"].map(fmt.pct)
            disp["Average cost vs. average price"] = disp["Average cost vs. average price"].map(fmt.pct)
            results += [f"#### {name}\n", img(f"dca_{slug([k for k, v in config.CORE_ASSETS.items() if v == name][0])}.png",
                                                 f"{name} dollar-cost averaging"), fmt.md_table(disp)]
            all_stats.append(stats.assign(Asset=name))
        pd.concat(all_stats).to_csv(TABLES / "sentiment_dca.csv", index=False)
    if regime_rows:
        pd.concat(regime_rows).to_csv(TABLES / "sentiment_regimes.csv", index=False)
        results.append("[Download regime returns](../data/sentiment_regimes.csv), "
                       "[entry events](../data/sentiment_events.csv), and "
                       "[dollar-cost-averaging results](../data/sentiment_dca.csv) as CSV.\n")
    if cfg is not None:
        cfg.rename("value").to_frame().assign(regime=sentiment.classify(cfg)).to_csv(TABLES / "crypto_fear_greed.csv")
    if efg is not None:
        comps.assign(composite=efg).dropna(subset=["composite"]).to_csv(TABLES / "equity_fear_greed.csv")
    if not pairs:
        results.append("_Sentiment data was unavailable for this build._\n")
    return bullets(findings), "\n".join(results), cur_df


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def build_report(key, filename, title, findings_md, results_md, footer) -> None:
    src = (RESEARCH / filename).read_text(encoding="utf-8")
    src = site.strip_repo_only(src)
    if "<!-- KEY_FINDINGS -->" not in src or "<!-- RESULTS -->" not in src:
        log.warning("%s is missing a KEY_FINDINGS or RESULTS marker", filename)
    md = src.replace("<!-- KEY_FINDINGS -->", findings_md).replace("<!-- RESULTS -->", results_md)
    page = site.render(md, f"{title} | {config.SITE_TITLE}", "../", "research", footer)
    (OUT / "research").mkdir(exist_ok=True)
    (OUT / "research" / f"{key}.html").write_text(page, encoding="utf-8")


def build_index(ctx, structure, themes_summary, fed_tbl, fed_meta, testing_now, footer,
                exp_meta=None, conditions=None, sentiment_now=None) -> None:
    exp_meta = exp_meta or {}
    liq = ctx["liq"].dropna(subset=["impulse_bn"])
    last = liq.iloc[-1]
    regime = str(last["regime"]).lower()
    direction = "up" if last["impulse_bn"] >= 0 else "down"
    next_fomc = fed_meta.get("next_fomc")
    hero = (
        f'<p class="regime {regime}">Net liquidity is ${fmt.num(last["net_liquidity"], 0)} billion, '
        f'{direction} ${fmt.num(abs(last["impulse_bn"]), 0)} billion over {config.LIQUIDITY_WINDOW} weeks.</p>\n'
        f'<p class="regime-note">Liquidity regime: {regime}. Fed balance sheet as of {fmt.date(last.name - pd.Timedelta(days=2))}.'
        + (f" Next FOMC decision: {fmt.date(next_fomc)}." if next_fomc is not None else "")
        + (f" {exp_meta['odds_text']}" if exp_meta.get("odds_text") else "") + "</p>\n"
    )
    parts = ["# Market monitor\n", hero,
             f"{config.SITE_DESCRIPTION}\n",
             "## Liquidity\n", img("net_liquidity.png", "Net liquidity", root=""),
             f"Net liquidity is Fed total assets minus the Treasury General Account and overnight reverse repo. "
             f"The regime is expanding when the {config.LIQUIDITY_WINDOW}-week change is positive. "
             f"[Full study](research/net-liquidity.html).\n",
             "## Policy\n"]
    keep = ["Fed funds target, upper bound (%)", "Effective fed funds rate (%)", "2-year Treasury (%)",
            "2-year minus fed funds (pp)", "10-year Treasury (%)", "10-year real yield, TIPS (%)",
            "10-year minus 2-year (pp)"]
    parts.append(fmt.md_table(fed_tbl[fed_tbl["Indicator"].isin(keep)][["Indicator", "Latest", "13W change", "52W change"]]))
    parts.append("[Fed policy monitor and FOMC event study](research/fed-policy.html).\n")
    if exp_meta.get("odds_table") is not None or exp_meta.get("path") is not None:
        parts.append("## Rate expectations\n")
        if exp_meta.get("odds_table") is not None:
            parts.append("Prediction-market odds for the next FOMC decision.\n")
            parts.append(fmt.md_table(exp_meta["odds_table"]))
        if exp_meta.get("path") is not None:
            parts.append(img("implied_path.png", "Implied policy path", root=""))
        parts.append("[Rate expectations, policy rules, and recession risk](research/rate-expectations.html).\n")
    if exp_meta.get("macro_table") is not None:
        parts.append("## Macro\n")
        keep_rows = exp_meta["macro_table"][exp_meta["macro_table"]["Indicator"].str.contains(
            "Core PCE|Unemployment|Sahm|Recession|Payroll")]
        parts.append(fmt.md_table(keep_rows[["Indicator", "Latest", "As of", "12 months ago"]]))
    if conditions is not None and not conditions.empty:
        parts.append("## Financial conditions\n")
        c = conditions[["Indicator", "Latest", "13W change", "Percentile"]].copy()
        c["Latest"] = c["Latest"].map(lambda v: fmt.num(v, 2))
        c["13W change"] = c["13W change"].map(lambda v: fmt.num(v, 2, sign=True))
        c["Percentile"] = conditions["Percentile"].map(fmt.ordinal)
        c = c.rename(columns={"Percentile": "Percentile (up to 5 years)"})
        parts.append(fmt.md_table(c))
        parts.append("[Cross-asset risk and financial conditions](research/cross-asset-risk.html).\n")
    if sentiment_now is not None and not sentiment_now.empty:
        parts.append("## Sentiment\n")
        parts.append(fmt.md_table(sentiment_now[["Index", "Latest", "Regime", "As of", "30-day average"]]))
        parts.append("[Buying fear: testing fear and greed extremes](research/fear-and-greed.html).\n")
    parts.append("## Trend structure\n")
    parts.append("Distance from the 50, 100, and 200-week simple moving averages and the nearest tracked support level. "
                 + ("Testing an average this week: " + "; ".join(testing_now) + "." if len(testing_now) else
                    "No asset is testing an average this week.") + "\n")
    parts.append(fmt.md_table(structure))
    parts.append("[Retracement event study and level maps](research/ma-retracements.html).\n")
    if not themes_summary.empty:
        parts.append("## Themes\n")
        cols = ["Theme", "13W", "26W", "YTD", f"Rel. to {config.BENCHMARK} 26W", "vs 50W SMA", "vs 200W SMA"]
        t = themes_summary[cols].copy()
        for c in cols[1:]:
            t[c] = t[c].map(fmt.pct)
        parts.append(fmt.md_table(t))
        parts.append("[The AI infrastructure trade](research/ai-infrastructure.html).\n")
    parts.append('## Research {#research}\n')
    items = "".join(f'<p><strong><a href="research/{key}.html">{title}</a></strong><br>{blurb}</p>'
                    for key, _f, title, blurb in REPORTS)
    parts.append(f'<div class="report-list">{items}</div>\n')
    about = (RESEARCH / "about.md").read_text(encoding="utf-8") if (RESEARCH / "about.md").exists() else ""
    parts.append("## About {#about}\n")
    parts.append(about)
    page = site.render("\n".join(parts), config.SITE_TITLE, "", "index", footer)
    (OUT / "index.html").write_text(page, encoding="utf-8")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in (OUT, ASSETS, TABLES):
        d.mkdir(parents=True, exist_ok=True)
    site.write_css(OUT)
    (OUT / ".nojekyll").write_text("")

    ctx = load_context()
    now = datetime.now(timezone.utc)
    built = f"{now:%b} {now.day}, {now:%Y} {now:%H:%M} UTC"
    footer = f"Built {built}. {config.AUTHOR}."
    url = site.repo_url()
    if url:
        footer += f' <a href="{url}">Source code and methodology</a>.'

    f1, r1 = study_liquidity(ctx)
    f2, r2, structure, testing_now = study_retracements(ctx)
    f3, r3 = study_regime(ctx)
    f4, r4, theme_summary = study_themes(ctx)
    f5, r5, fed_tbl, fed_meta = study_fed(ctx)
    f6, r6, exp_meta = study_expectations(ctx, fed_meta.get("next_fomc"))
    f7, r7, conditions = study_risk(ctx)
    f8, r8, sentiment_now = study_sentiment(ctx)

    outputs = {"net-liquidity": (f1, r1), "ma-retracements": (f2, r2), "regime-model": (f3, r3),
               "ai-infrastructure": (f4, r4), "fed-policy": (f5, r5), "rate-expectations": (f6, r6),
               "cross-asset-risk": (f7, r7), "fear-and-greed": (f8, r8)}
    for key, filename, title, _blurb in REPORTS:
        findings, results = outputs[key]
        build_report(key, filename, title, findings, results, footer)
    build_index(ctx, structure, theme_summary, fed_tbl, fed_meta, list(testing_now), footer,
                exp_meta, conditions, sentiment_now)
    log.info("Site written to %s", OUT)


if __name__ == "__main__":
    main()

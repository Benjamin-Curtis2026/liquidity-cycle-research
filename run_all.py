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

from src import backtest, charts, config, data, fed, fmt, liquidity, site, themes
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
        f"Net liquidity was ${fmt.num(last['net_liquidity'], 0)} billion as of {fmt.date(last.name)}, "
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
        if summary["Liquidity corr."].notna().any():
            hl = summary.loc[summary["Liquidity corr."].idxmax()]
            findings.append(
                f"Highest same-period correlation with 4-week net liquidity changes: {hl['Theme']} "
                f"(r = {fmt.num(hl['Liquidity corr.'], 2, sign=True)}, p = {fmt.pval(hl['Liquidity p'])}).")

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


def build_index(ctx, structure, themes_summary, fed_tbl, fed_meta, testing_now, footer) -> None:
    liq = ctx["liq"].dropna(subset=["impulse_bn"])
    last = liq.iloc[-1]
    regime = str(last["regime"]).lower()
    direction = "up" if last["impulse_bn"] >= 0 else "down"
    next_fomc = fed_meta.get("next_fomc")
    hero = (
        f'<p class="regime {regime}">Net liquidity is ${fmt.num(last["net_liquidity"], 0)} billion, '
        f'{direction} ${fmt.num(abs(last["impulse_bn"]), 0)} billion over {config.LIQUIDITY_WINDOW} weeks.</p>\n'
        f'<p class="regime-note">Liquidity regime: {regime}. Balance-sheet data through {fmt.date(last.name)}.'
        + (f" Next FOMC decision: {fmt.date(next_fomc)}." if next_fomc is not None else "") + "</p>\n"
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

    outputs = {"net-liquidity": (f1, r1), "ma-retracements": (f2, r2), "regime-model": (f3, r3),
               "ai-infrastructure": (f4, r4), "fed-policy": (f5, r5)}
    for key, filename, title, _blurb in REPORTS:
        findings, results = outputs[key]
        build_report(key, filename, title, findings, results, footer)
    build_index(ctx, structure, theme_summary, fed_tbl, fed_meta, list(testing_now), footer)
    log.info("Site written to %s", OUT)


if __name__ == "__main__":
    main()

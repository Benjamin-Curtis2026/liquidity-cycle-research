"""Charts. Every function writes a PNG and returns nothing."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

INK = "#15233B"
MUTED = "#5B6676"
GRID = "#E3E7EC"
EXPAND = "#1D6F6A"
CONTRACT = "#A8631A"
BLUE = "#2B5C9E"
PLUM = "#6E4C8C"
SERIES = [INK, EXPAND, CONTRACT, BLUE, PLUM, "#B03A48", "#8A8F98"]

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9.5,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
    "axes.titlelocation": "left",
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "legend.frameon": False,
    "legend.fontsize": 8.5,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "savefig.facecolor": "white",
})


def _style(ax):
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _log_axis(ax, formatter):
    ax.set_yscale("log")
    ax.yaxis.set_major_locator(mticker.LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(formatter))
    ax.yaxis.set_minor_formatter(mticker.NullFormatter())


def _legend_below(ax, ncol):
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=ncol)


def _usd(x, _pos=None):
    if abs(x) >= 1000:
        return f"{x:,.0f}"
    if abs(x) >= 10:
        return f"{x:,.0f}"
    return f"{x:,.2f}"


def _shade_regime(ax, regime: pd.Series):
    """Shade contracting weeks behind a time-series plot."""
    contracting = (regime == "Contracting").astype(int)
    starts = contracting.index[(contracting.diff() == 1)]
    ends = contracting.index[(contracting.diff() == -1)]
    if len(contracting) and contracting.iloc[0] == 1:
        starts = starts.insert(0, contracting.index[0])
    if len(starts) > len(ends):
        ends = ends.append(pd.DatetimeIndex([contracting.index[-1]]))
    for s, e in zip(starts, ends):
        ax.axvspan(s, e, color=CONTRACT, alpha=0.09, linewidth=0)


def net_liquidity(liq: pd.DataFrame, path):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6.2), sharex=True,
                                   gridspec_kw={"height_ratios": [2.2, 1]})
    _shade_regime(ax1, liq["regime"])
    ax1.plot(liq.index, liq["fed_assets"], color=MUTED, lw=1.1, label="Fed total assets")
    ax1.plot(liq.index, liq["net_liquidity"], color=INK, lw=1.8, label="Net liquidity")
    ax1.set_title("Fed total assets and net liquidity ($bn); shaded weeks = contracting 13W impulse")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(_usd))
    ax1.legend(loc="upper left")
    ax2.plot(liq.index, liq["tga"], color=BLUE, lw=1.3, label="Treasury General Account")
    ax2.plot(liq.index, liq["rrp"], color=CONTRACT, lw=1.3, label="Overnight reverse repo")
    ax2.set_title("Drains on reserves ($bn)")
    ax2.yaxis.set_major_formatter(mticker.FuncFormatter(_usd))
    ax2.legend(loc="upper left")
    for ax in (ax1, ax2):
        _style(ax)
    _save(fig, path)


def liquidity_vs_asset(liq: pd.Series, close_w: pd.Series, name: str, path):
    df = pd.concat({"liq": liq, "px": close_w}, axis=1, join="inner").dropna()
    fig, ax1 = plt.subplots(figsize=(9, 4.2))
    ax1.plot(df.index, df["liq"], color=INK, lw=1.6, label="Net liquidity ($bn, left)")
    ax1.yaxis.set_major_formatter(mticker.FuncFormatter(_usd))
    ax2 = ax1.twinx()
    ax2.plot(df.index, df["px"], color=EXPAND, lw=1.3, label=f"{name} (log, right)")
    _log_axis(ax2, _usd)
    ax2.spines["top"].set_visible(False)
    ax1.set_title(f"Net liquidity and {name}")
    lines = ax1.get_lines() + ax2.get_lines()
    ax1.legend(lines, [ln.get_label() for ln in lines], loc="upper left")
    _style(ax1)
    _save(fig, path)


def lead_lag_bars(tables: dict[str, pd.DataFrame], path):
    names = list(tables)
    leads = tables[names[0]]["lead_weeks"].to_numpy()
    width = 0.8 / max(len(names), 1)
    fig, ax = plt.subplots(figsize=(9, 4))
    for i, n in enumerate(names):
        t = tables[n]
        ax.bar(np.arange(len(leads)) + i * width, t["corr"], width=width,
               color=SERIES[i % len(SERIES)], label=n)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks(np.arange(len(leads)) + width * (len(names) - 1) / 2)
    ax.set_xticklabels([f"+{w}w" for w in leads])
    ax.set_xlabel("Asset return measured this many weeks after the liquidity change")
    ax.set_ylabel("Correlation")
    ax.set_title("Net liquidity 4-week change vs. later 4-week asset return")
    ax.legend(ncol=len(names), loc="upper center", bbox_to_anchor=(0.5, -0.2))
    _style(ax)
    _save(fig, path)


def rolling_corr(series: dict[str, pd.Series], path,
                 title: str = "Rolling 52-week correlation, 4-week changes (descriptive)"):
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for i, (n, s) in enumerate(series.items()):
        ax.plot(s.index, s, lw=1.3, color=SERIES[i % len(SERIES)], label=n)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_ylim(-1, 1)
    ax.set_title(title)
    _legend_below(ax, len(series))
    _style(ax)
    _save(fig, path)


def asset_structure(weekly: pd.DataFrame, events: dict[str, list[int]], supports: pd.DataFrame,
                    name: str, path, years: int = 8):
    w = weekly[weekly.index >= weekly.index[-1] - pd.Timedelta(weeks=52 * years)]
    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.plot(w.index, w["Close"], color=INK, lw=1.4, label="Weekly close")
    ma_colors = {"SMA50": BLUE, "SMA100": PLUM, "SMA200": CONTRACT}
    for col, color in ma_colors.items():
        if col in w and w[col].notna().any():
            ax.plot(w.index, w[col], color=color, lw=1.2, label=col.replace("SMA", "") + "W SMA")
    for col, idxs in events.items():
        dates = [weekly.index[i] for i in idxs if weekly.index[i] >= w.index[0]]
        if dates:
            ax.scatter(dates, weekly.loc[dates, col], s=26, color=ma_colors.get(col, MUTED),
                       edgecolor="white", linewidth=0.8, zorder=5)
    lines = []
    for _, lv in supports.sort_values("price", ascending=False).iterrows():
        ax.axhline(lv["price"], color=EXPAND, lw=0.9, ls=(0, (4, 3)))
        lines.append(f"{lv['level']}: {_usd(lv['price'])}")
    if lines:
        ax.text(0.99, 0.03, "Nearest supports (dashed)\n" + "\n".join(lines), transform=ax.transAxes,
                ha="right", va="bottom", fontsize=7.8, color=EXPAND, linespacing=1.5,
                bbox={"facecolor": "white", "edgecolor": GRID, "boxstyle": "square,pad=0.5"})
    _log_axis(ax, _usd)
    ax.set_title(f"{name}: weekly structure; dots mark retracement tests, dashed lines nearest supports")
    _legend_below(ax, 4)
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    _style(ax)
    _save(fig, path)


def equity_curves(curves: pd.DataFrame, name: str, path):
    fig, ax = plt.subplots(figsize=(9, 4))
    for i, col in enumerate(curves):
        ax.plot(curves.index, curves[col], lw=1.5 if i == 0 else 1.3,
                color=SERIES[i % len(SERIES)], label=col)
    _log_axis(ax, lambda x, _p: f"{x:,.1f}x" if x < 10 else f"{x:,.0f}x")
    ax.set_title(f"{name}: growth of $1 by rule, after costs (log scale)")
    ax.legend(loc="upper left")
    _style(ax)
    _save(fig, path)


def theme_indices(indices: dict[str, pd.Series], bench: pd.Series, bench_name: str, path, weeks: int = 156):
    fig, ax = plt.subplots(figsize=(9, 4.4))
    start = max(s.index[-1] for s in indices.values() if len(s)) - pd.Timedelta(weeks=weeks)
    for i, (n, s) in enumerate(indices.items()):
        s = s[s.index >= start]
        if len(s) < 10:
            continue
        ax.plot(s.index, 100 * s / s.iloc[0], lw=1.5, color=SERIES[(i + 1) % len(SERIES)], label=n)
    b = bench[bench.index >= start].dropna()
    if len(b):
        ax.plot(b.index, 100 * b / b.iloc[0], lw=1.2, color=MUTED, ls="--", label=bench_name)
    _log_axis(ax, lambda x, _p: f"{x:,.0f}")
    ax.set_title("Thematic baskets, equal weight, rebased to 100 three years ago (log scale)")
    ax.legend(loc="upper left", ncol=2)
    _style(ax)
    _save(fig, path)


def fed_rates(fred: dict, path, start="2015-01-01"):
    fig, ax = plt.subplots(figsize=(9, 4))
    spec = [("DFEDTARU", "Target, upper bound", INK, 1.8, "-"),
            ("DFF", "Effective fed funds", MUTED, 1.0, "-"),
            ("DGS2", "2-year Treasury", BLUE, 1.3, "-"),
            ("DGS10", "10-year Treasury", CONTRACT, 1.3, "-"),
            ("DFII10", "10-year real (TIPS)", EXPAND, 1.2, "--")]
    for key, label, color, lw, ls in spec:
        if key in fred:
            s = fred[key][fred[key].index >= start]
            ax.plot(s.index, s, color=color, lw=lw, ls=ls, label=label)
    ax.axhline(0, color=MUTED, lw=0.6)
    ax.set_title("Policy rate and Treasury yields (%)")
    ax.legend(loc="upper left", ncol=3)
    _style(ax)
    _save(fig, path)


def curve_and_spread(fred: dict, path, start="2015-01-01"):
    fig, ax = plt.subplots(figsize=(9, 3.4))
    if "T10Y2Y" in fred:
        s = fred["T10Y2Y"][fred["T10Y2Y"].index >= start]
        ax.plot(s.index, s, color=INK, lw=1.3, label="10-year minus 2-year")
    if "DGS2" in fred and "DFF" in fred:
        df = pd.concat([fred["DGS2"], fred["DFF"]], axis=1).dropna()
        df = df[df.index >= start]
        ax.plot(df.index, df.iloc[:, 0] - df.iloc[:, 1], color=BLUE, lw=1.2,
                label="2-year minus fed funds (market-implied direction)")
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_title("Curve slope and market-implied policy direction (pp)")
    ax.legend(loc="lower left")
    _style(ax)
    _save(fig, path)


# ---------------------------------------------------------------------------
# Rate expectations and macro
# ---------------------------------------------------------------------------
def rate_odds_bars(buckets: dict[str, pd.Series], meeting, path):
    labels = list(next(iter(buckets.values())).index)
    width = 0.8 / len(buckets)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    for i, (src, b) in enumerate(buckets.items()):
        x = np.arange(len(labels)) + i * width
        bars = ax.bar(x, b.reindex(labels).fillna(0) * 100, width=width, color=[INK, BLUE, EXPAND][i % 3], label=src)
        for rect, v in zip(bars, b.reindex(labels).fillna(0) * 100):
            if v >= 1:
                ax.annotate(f"{v:.0f}%", (rect.get_x() + rect.get_width() / 2, v), ha="center", va="bottom",
                            fontsize=8, color=INK, xytext=(0, 2), textcoords="offset points")
    ax.set_xticks(np.arange(len(labels)) + width * (len(buckets) - 1) / 2)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Implied probability (%)")
    ts = pd.Timestamp(meeting)
    ax.set_title(f"Prediction-market odds for the {ts:%b} {ts.day}, {ts:%Y} FOMC decision")
    ax.legend(loc="upper right")
    _style(ax)
    _save(fig, path)


def implied_path(path_df: pd.DataFrame, current_upper: float, path):
    fig, ax = plt.subplots(figsize=(9, 4))
    x = path_df["meeting"]
    ax.fill_between(x, path_df["p10"], path_df["p90"], color=BLUE, alpha=0.15, step=None,
                    label="10th to 90th percentile")
    ax.plot(x, path_df["expected"], color=INK, lw=1.8, marker="o", label="Expected upper bound")
    ax.plot(x, path_df["mode"], color=EXPAND, lw=1.0, ls="--", marker=".", label="Most likely upper bound")
    ax.axhline(current_upper, color=CONTRACT, lw=1.0, ls=":", label=f"Current upper bound ({current_upper:.2f}%)")
    ax.set_ylabel("Fed funds target, upper bound (%)")
    ax.set_title("Market-implied policy path from Kalshi rate contracts")
    ax.set_xticks(list(x))
    ax.set_xticklabels([f"{pd.Timestamp(d):%b} {pd.Timestamp(d).day}\n{pd.Timestamp(d):%Y}" for d in x], fontsize=8)
    _legend_below(ax, 2)
    _style(ax)
    _save(fig, path)


def taylor_chart(df: pd.DataFrame, rule_names, path, start="2012-01-01"):
    d = df[df.index >= start]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.plot(d.index, d["actual"], color=INK, lw=2.0, label="Fed funds target, midpoint")
    for i, n in enumerate(rule_names):
        ax.plot(d.index, d[n], lw=1.2, color=[BLUE, EXPAND, CONTRACT][i % 3], ls=["-", "--", "-."][i % 3], label=n)
    ax.axhline(0, color=MUTED, lw=0.6)
    ax.set_ylabel("%")
    ax.set_title("Policy rate vs. Taylor-type rules (core PCE inflation, CBO output gap)")
    _legend_below(ax, 2)
    _style(ax)
    _save(fig, path)


def recession_chart(prob: pd.Series, usrec: pd.Series | None, path, start="2000-01-01"):
    p = prob[prob.index >= start] * 100
    fig, ax = plt.subplots(figsize=(9, 3.6))
    if usrec is not None and len(usrec):
        rec = usrec[usrec.index >= start]
        ax.fill_between(rec.index, 0, 100, where=rec > 0.5, color=MUTED, alpha=0.15, step="post",
                        label="NBER recession")
    ax.plot(p.index, p, color=INK, lw=1.6, label="Probability of recession in 12 months")
    ax.axhline(30, color=CONTRACT, lw=0.9, ls=":", label="30% reference level")
    ax.set_ylim(0, 100)
    ax.set_ylabel("%")
    ax.set_title("Yield-curve recession probability (10-year minus 3-month probit)")
    _legend_below(ax, 3)
    _style(ax)
    _save(fig, path)


def inflation_labor(fred: dict, path, start="2015-01-01"):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True)
    yoy = lambda s: (s.resample("MS").last() / s.resample("MS").last().shift(12) - 1) * 100  # noqa: E731
    for key, label, color in [("CPIAUCSL", "CPI", MUTED), ("CPILFESL", "Core CPI", BLUE), ("PCEPILFE", "Core PCE", INK)]:
        if key in fred:
            v = yoy(fred[key])
            v = v[v.index >= start]
            ax1.plot(v.index, v, color=color, lw=1.5 if key == "PCEPILFE" else 1.1, label=label)
    ax1.axhline(2, color=EXPAND, lw=0.9, ls=":", label="2% target")
    ax1.set_title("Inflation, year over year (%)")
    ax1.legend(loc="upper left", ncol=4)
    if "UNRATE" in fred:
        u = fred["UNRATE"][fred["UNRATE"].index >= start]
        ax2.plot(u.index, u, color=INK, lw=1.5, label="Unemployment rate (%)")
    if "SAHMREALTIME" in fred:
        sr = fred["SAHMREALTIME"][fred["SAHMREALTIME"].index >= start]
        ax2b = ax2.twinx()
        ax2b.plot(sr.index, sr, color=CONTRACT, lw=1.1, label="Sahm rule (pp, right)")
        ax2b.axhline(0.5, color=CONTRACT, lw=0.8, ls=":")
        ax2b.spines["top"].set_visible(False)
        lines = ax2.get_lines() + ax2b.get_lines()[:1]
        ax2.legend(lines, [ln.get_label() for ln in lines], loc="upper right")
    ax2.set_title("Labor market")
    for ax in (ax1, ax2):
        _style(ax)
    _save(fig, path)


def conditions_panel(fred: dict, path, start="2018-01-01"):
    keys = [("VIXCLS", "VIX"), ("BAMLH0A0HYM2", "High-yield spread (%)"), ("NFCI", "Chicago Fed NFCI")]
    keys = [(k, l) for k, l in keys if k in fred]
    if not keys:
        return False
    fig, axes = plt.subplots(len(keys), 1, figsize=(9, 2.3 * len(keys) + 0.6), sharex=True)
    axes = np.atleast_1d(axes)
    for ax, (k, label) in zip(axes, keys):
        s = fred[k][fred[k].index >= start]
        ax.plot(s.index, s, color=INK, lw=1.2)
        ax.axhline(s.median(), color=MUTED, lw=0.8, ls=":")
        ax.set_title(f"{label}; dotted line = median since {pd.Timestamp(start):%Y}")
        _style(ax)
    _save(fig, path)
    return True


def corr_heatmap(corr: pd.DataFrame, path):
    fig, ax = plt.subplots(figsize=(7.6, 6.4))
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("rb", [CONTRACT, "#FFFFFF", BLUE])
    im = ax.imshow(corr.to_numpy(), cmap=cmap, vmin=-1, vmax=1)
    ax.set_xticks(range(len(corr.columns)))
    ax.set_xticklabels(corr.columns, rotation=45, ha="right")
    ax.set_yticks(range(len(corr.index)))
    ax.set_yticklabels(corr.index)
    for i in range(corr.shape[0]):
        for j in range(corr.shape[1]):
            v = corr.iat[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=7.5,
                        color="white" if abs(v) > 0.6 else INK)
    ax.set_title("Correlation of weekly returns, last two years")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    _save(fig, path)


# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------
def sentiment_history(close: pd.Series, sentiment: pd.Series, name: str, index_name: str, path):
    s = sentiment.dropna()
    c = close[close.index >= s.index[0]].dropna()
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9, 6), sharex=True, gridspec_kw={"height_ratios": [1.6, 1]})
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("fg", [CONTRACT, "#E8E2D0", BLUE])
    col = s.reindex(c.index).ffill()
    ax1.plot(c.index, c, color=MUTED, lw=0.6, zorder=1)
    sc = ax1.scatter(c.index, c, c=col, cmap=cmap, vmin=0, vmax=100, s=4, zorder=2)
    _log_axis(ax1, _usd)
    ax1.set_title(f"{name}, colored by the {index_name} (amber = fear, blue = greed)")
    fig.colorbar(sc, ax=ax1, fraction=0.03, pad=0.01)
    ax2.plot(s.index, s, color=INK, lw=0.8)
    for lo, hi, color in [(0, 25, CONTRACT), (25, 45, CONTRACT), (75, 100, BLUE), (55, 75, BLUE)]:
        ax2.axhspan(lo, hi, color=color, alpha=0.12 if (lo == 0 or hi == 100) else 0.05, lw=0)
    ax2.set_ylim(0, 100)
    ax2.set_title(f"{index_name[0].upper() + index_name[1:]} (shaded: below 25 extreme fear, above 75 extreme greed)")
    for ax in (ax1, ax2):
        _style(ax)
    _save(fig, path)


def regime_bars(table: pd.DataFrame, horizons, name: str, path):
    t = table[table["Regime"] != "All days"].set_index("Regime")
    base = table[table["Regime"] == "All days"].iloc[0] if (table["Regime"] == "All days").any() else None
    width = 0.8 / len(horizons)
    fig, ax = plt.subplots(figsize=(9, 4))
    for i, h in enumerate(horizons):
        vals = t[f"Avg {h}"] * 100
        ax.bar(np.arange(len(t)) + i * width, vals, width=width, color=[INK, BLUE, EXPAND, CONTRACT][i % 4], label=h)
        if base is not None:
            ax.hlines(base[f"Avg {h}"] * 100, -0.4, len(t) - 0.2, colors=[INK, BLUE, EXPAND, CONTRACT][i % 4],
                      linestyles=":", lw=0.9)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_xticks(np.arange(len(t)) + width * (len(horizons) - 1) / 2)
    ax.set_xticklabels(t.index)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda x, _p: f"{x:.0f}%"))
    ax.set_title(f"{name}: average forward return by sentiment regime (dotted = all days)")
    ax.legend(ncol=len(horizons), loc="upper center", bbox_to_anchor=(0.5, -0.1))
    _style(ax)
    _save(fig, path)


def dca_chart(curves: pd.DataFrame, contributed_per_week: float, name: str, path):
    fig, ax = plt.subplots(figsize=(9, 4))
    for i, col in enumerate(curves):
        ax.plot(curves.index, curves[col], lw=1.5 if i == 0 else 1.3, color=[INK, CONTRACT, BLUE][i % 3], label=col)
    contributed = pd.Series(np.arange(1, len(curves) + 1) * contributed_per_week, index=curves.index)
    ax.plot(contributed.index, contributed, color=MUTED, lw=1.0, ls=":", label="Total contributed")
    _log_axis(ax, lambda x, _p: f"${x:,.0f}")
    ax.set_title(f"{name}: ${contributed_per_week:,.0f} a week, invested on three sentiment rules (log scale)")
    ax.legend(loc="upper left")
    _style(ax)
    _save(fig, path)

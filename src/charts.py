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


def rolling_corr(series: dict[str, pd.Series], path):
    fig, ax = plt.subplots(figsize=(9, 3.6))
    for i, (n, s) in enumerate(series.items()):
        ax.plot(s.index, s, lw=1.3, color=SERIES[i % len(SERIES)], label=n)
    ax.axhline(0, color=MUTED, lw=0.8)
    ax.set_ylim(-1, 1)
    ax.set_title("Rolling 52-week correlation, 4-week changes (descriptive)")
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

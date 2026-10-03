"""Statistical helpers shared across the studies."""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy import stats as st

from . import config


def random_entry_pvalue(event_values, pool_values, n_draws: int = config.PERMUTATION_DRAWS,
                        seed: int = 7) -> float:
    """One-sided p-value: how often does a random set of entry weeks match the event mean?

    Draws `len(event_values)` weeks at random from the pool of all eligible weeks,
    `n_draws` times, and reports the share of draws whose mean forward return is at
    least the event mean. Random draws keep the return distribution but not its
    time clustering, so treat the result as indicative rather than exact.
    """
    ev = pd.Series(event_values).dropna().to_numpy()
    pool = pd.Series(pool_values).dropna().to_numpy()
    if len(ev) < 3 or len(pool) < 20:
        return float("nan")
    rng = np.random.default_rng(seed)
    sims = rng.choice(pool, size=(n_draws, len(ev)), replace=True).mean(axis=1)
    return float((np.sum(sims >= ev.mean()) + 1) / (n_draws + 1))


def pearson(x, y):
    df = pd.concat([pd.Series(x), pd.Series(y)], axis=1).dropna()
    if len(df) < 8:
        return float("nan"), float("nan"), len(df)
    r, p = st.pearsonr(df.iloc[:, 0], df.iloc[:, 1])
    return float(r), float(p), len(df)


def max_drawdown(equity: pd.Series) -> float:
    return float((equity / equity.cummax() - 1).min())


def perf_stats(returns: pd.Series, rf: pd.Series | None = None, periods: int = 52) -> dict:
    r = returns.dropna()
    if len(r) < periods:
        return {}
    equity = (1 + r).cumprod()
    years = len(r) / periods
    excess = r - rf.reindex(r.index).fillna(0) if rf is not None else r
    vol = r.std() * math.sqrt(periods)
    sharpe = excess.mean() / excess.std() * math.sqrt(periods) if excess.std() > 0 else float("nan")
    return {
        "CAGR": equity.iloc[-1] ** (1 / years) - 1,
        "Volatility": vol,
        "Sharpe": sharpe,
        "Max drawdown": max_drawdown(equity),
        "Total return": equity.iloc[-1] - 1,
    }

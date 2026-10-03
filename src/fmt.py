"""Number formatting and Markdown table output."""
from __future__ import annotations

import math

import pandas as pd

DASH = "–"


def _missing(x) -> bool:
    try:
        return x is None or pd.isna(x) or (isinstance(x, float) and math.isinf(x))
    except (TypeError, ValueError):
        return False


def pct(x, digits: int = 1, sign: bool = True) -> str:
    if _missing(x):
        return DASH
    return f"{x * 100:+.{digits}f}%" if sign else f"{x * 100:.{digits}f}%"


def num(x, digits: int = 2, sign: bool = False) -> str:
    if _missing(x):
        return DASH
    return f"{x:+,.{digits}f}" if sign else f"{x:,.{digits}f}"


def price(x) -> str:
    if _missing(x):
        return DASH
    return f"{x:,.0f}" if abs(x) >= 1000 else f"{x:,.2f}"


def pval(x) -> str:
    if _missing(x):
        return DASH
    return "<0.001" if x < 0.001 else f"{x:.3f}"


def date(x) -> str:
    if _missing(x):
        return DASH
    ts = pd.Timestamp(x)
    return f"{ts:%b} {ts.day}, {ts:%Y}"


def md_table(df: pd.DataFrame) -> str:
    """Render a DataFrame of preformatted strings as a Markdown table."""
    if df is None or df.empty:
        return "_No observations met the criteria in this build._\n"
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |",
             "|" + "|".join(":---" if i == 0 else "---:" for i in range(len(cols))) + "|"]
    for row in df.astype(object).itertuples(index=False):
        cells = [DASH if _missing(v) else str(v).replace("|", "\\|") for v in row]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"

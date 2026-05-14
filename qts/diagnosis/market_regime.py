"""Market regime classifier — assigns one of 6 state labels to each trading day.

All labels use ONLY data up to and including the current date. No future peeking.

States (in priority order):
    tail_risk   — extreme single/multi-day drop
    bear_trend  — sustained downtrend
    bull_trend  — strong uptrend
    recovery    — post-bear repair with confirmation signals
    bull_range  — above MA60 but not trending strongly
    bear_range  — below MA60, not bear_trend, not recovery
"""

import pandas as pd
import numpy as np


def classify_regime(index_df: pd.DataFrame) -> pd.DataFrame:
    """Classify each trading day into one of 6 regime states.

    Args:
        index_df: [trade_date, close] sorted ascending.

    Returns:
        DataFrame with columns: trade_date, close, label, tail_risk, bear_trend,
        bull_trend, recovery, bear_range, bull_range (all boolean).
    """
    df = index_df[["trade_date", "close"]].copy()
    close = df["close"]

    # ── Pre-compute indicators (all using rolling windows, no future data) ──
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    ma60_slope_20d = (ma60 - ma60.shift(20)) / ma60.shift(20).replace(0, np.nan)
    ret_1d = close.pct_change()
    ret_5d = close / close.shift(5) - 1
    ret_20d = close / close.shift(20) - 1
    ma20_slope_5d = (ma20 - ma20.shift(5)) / ma20.shift(5).replace(0, np.nan)
    rolling_max_20 = close.rolling(20).max()
    rolling_max_250 = close.rolling(250).max()
    dd_20d = (close - rolling_max_20) / rolling_max_20
    dd_250d = (close - rolling_max_250) / rolling_max_250

    # ── State flags (boolean masks, evaluated in priority order) ──
    df["tail_risk"] = (ret_1d <= -0.07) | (ret_5d <= -0.08) | (dd_20d.fillna(0) <= -0.12)

    above_ma60 = close > ma60
    slope_up = ma60_slope_20d > 0.005
    slope_down = ma60_slope_20d < -0.005

    df["bear_trend"] = (
        ~above_ma60
        & slope_down.fillna(False)
        & (dd_250d.fillna(0) < -0.15)
        & ~df["tail_risk"]
    )

    df["bull_trend"] = (
        above_ma60
        & slope_up.fillna(False)
        & (dd_250d.fillna(0) > -0.15)
        & ~df["tail_risk"]
        & ~df["bear_trend"]
    )

    # Recovery: post-bear repair WITH confirmation signals
    df["recovery"] = (
        (close > ma20.fillna(0))              # 1. above short-term MA
        & (ret_20d.fillna(0) > 0.02)           # 2. 20-day gain > 2%
        & ((ret_5d.fillna(0) > 0) | (ma20_slope_5d.fillna(0) > 0))  # 3. short-term stopped falling
        & (dd_20d.fillna(0) > -0.10)           # 4. recent DD not extreme
        & ~df["tail_risk"]
        & ~df["bear_trend"]
        & ~df["bull_trend"]
    )

    df["bull_range"] = (
        above_ma60
        & ~df["tail_risk"]
        & ~df["bear_trend"]
        & ~df["bull_trend"]
        & ~df["recovery"]
    )

    # Remainder: bear_range
    df["bear_range"] = (
        ~df["tail_risk"]
        & ~df["bear_trend"]
        & ~df["bull_trend"]
        & ~df["recovery"]
        & ~df["bull_range"]
    )

    # ── Human-readable label ──
    conditions = [
        ("tail_risk", df["tail_risk"]),
        ("bear_trend", df["bear_trend"]),
        ("bull_trend", df["bull_trend"]),
        ("recovery", df["recovery"]),
        ("bull_range", df["bull_range"]),
        ("bear_range", df["bear_range"]),
    ]
    df["label"] = "unknown"
    for label, mask in conditions:
        df.loc[mask, "label"] = label

    # Fill warmup period (first 60 days — max rolling window needed)
    warmup = close.rolling(60).max().isna()
    df.loc[warmup, "label"] = "warmup"

    return df[["trade_date", "close", "label",
               "tail_risk", "bear_trend", "bull_trend",
               "recovery", "bear_range", "bull_range"]]


def summarize_by_year(regime_df: pd.DataFrame) -> pd.DataFrame:
    """Count days in each regime state per year."""
    df = regime_df.copy()
    df["year"] = pd.to_datetime(df["trade_date"]).dt.year
    cols = ["tail_risk", "bear_trend", "bull_trend", "recovery", "bear_range", "bull_range"]
    yearly = df.groupby("year")[cols].sum()
    yearly.columns = [f"{c}_days" for c in cols]
    return yearly.reset_index()

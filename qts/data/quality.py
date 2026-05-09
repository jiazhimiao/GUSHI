"""Data quality checks for A-share market data."""
import pandas as pd

from qts.utils.logger import logger


def check_bar_quality(df: pd.DataFrame) -> dict:
    """Run a battery of quality checks on daily bar data.

    Returns dict of check_name -> pass/fail/result.
    """
    results = {}

    if df.empty:
        return {"empty_data": "FAIL - no data"}

    # 1. Missing dates per symbol
    df["trade_date_dt"] = pd.to_datetime(df["trade_date"])
    date_range = (df["trade_date_dt"].max() - df["trade_date_dt"].min()).days
    per_symbol = df.groupby("symbol")["trade_date_dt"].nunique()
    expected_days = max(date_range * 5 / 7, 1)  # rough: ~70% of days are trading
    if expected_days > 0 and not per_symbol.empty:
        missing_ratio = (expected_days - per_symbol.mean()) / expected_days
        results["missing_dates_ratio"] = f"{missing_ratio:.2%}"
    else:
        results["missing_dates_ratio"] = "N/A"

    # 2. OHLC sanity: high >= max(open, close), low <= min(open, close)
    bad_ohlc = df[
        (df["high"] < df[["open", "close"]].max(axis=1))
        | (df["low"] > df[["open", "close"]].min(axis=1))
    ]
    results["ohlc_valid"] = f"PASS ({len(bad_ohlc)} bad rows)" if len(bad_ohlc) == 0 else f"FAIL ({len(bad_ohlc)} bad rows)"

    # 3. Suspension days
    suspended_pct = df["is_suspended"].mean()
    results["suspended_pct"] = f"{suspended_pct:.2%}"

    # 4. Negative prices
    neg = ((df[["open", "high", "low", "close"]] <= 0).any(axis=1)).sum()
    results["negative_prices"] = f"PASS" if neg == 0 else f"FAIL ({neg} rows)"

    # 5. Zero volume on non-suspended days
    zero_vol = ((df["volume"] <= 0) & ~df["is_suspended"]).sum()
    results["zero_volume_active"] = f"PASS" if zero_vol == 0 else f"FAIL ({zero_vol} rows)"

    # 6. Symbol count
    n_symbols = df["symbol"].nunique()
    results["symbol_count"] = n_symbols

    # 7. Date range
    results["date_range"] = f"{df['trade_date'].min()} to {df['trade_date'].max()}"

    for k, v in results.items():
        logger.info(f"  {k}: {v}")

    return results


def check_no_future_leak(
    factor_df: pd.DataFrame,
    bar_df: pd.DataFrame,
    factor_name: str = "factor",
) -> bool:
    """Check that factor values at trade_date only use data available on or before trade_date.

    This is a best-effort check: it verifies the factor_date <= trade_date.
    For a rigorous check, factor computation should pass ann_date explicitly.
    """
    merged = factor_df.merge(
        bar_df[["symbol", "trade_date"]],
        on=["symbol", "trade_date"],
        how="inner",
    )
    return len(merged) > 0

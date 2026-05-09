"""Momentum and return-based factors."""
import pandas as pd


def momentum_factor(
    prices: pd.DataFrame, period: int = 20, skip_recent: int = 1
) -> pd.DataFrame:
    """N-day price momentum: (close_t / close_{t-period}) - 1.

    Args:
        prices: DataFrame with trade_date index, symbol columns, close prices.
        period: Lookback period in trading days.
        skip_recent: Days to skip (1 = skip today, avoid micro-structure bias).

    Returns:
        DataFrame of momentum values, same shape as prices.
    """
    return prices.pct_change(period).shift(skip_recent)


def excess_return_factor(
    prices: pd.DataFrame,
    benchmark_prices: pd.Series,
    period: int = 20,
    skip_recent: int = 1,
) -> pd.DataFrame:
    """N-day excess return over benchmark."""
    stock_ret = prices.pct_change(period).shift(skip_recent)
    bench_ret = benchmark_prices.pct_change(period).shift(skip_recent)
    return stock_ret.subtract(bench_ret, axis=0)


def turnover_factor(
    volumes: pd.DataFrame, period: int = 20
) -> pd.DataFrame:
    """Average daily turnover (volume) over past N days, normalized."""
    avg_vol = volumes.rolling(window=period).mean()
    return avg_vol / avg_vol.rolling(window=60).mean()  # relative to 60-day avg

"""Volatility-based factors."""
import pandas as pd
import numpy as np


def volatility_factor(
    prices: pd.DataFrame, period: int = 60, skip_recent: int = 1
) -> pd.DataFrame:
    """N-day annualized volatility from daily log returns.

    Args:
        prices: DataFrame with trade_date index, symbol columns, close prices.
        period: Rolling window in trading days.
        skip_recent: Days to skip (avoid look-ahead bias).

    Returns:
        DataFrame of annualized volatility values.
    """
    log_ret = np.log(prices / prices.shift(1))
    vol = log_ret.rolling(window=period).std().shift(skip_recent)
    return vol * np.sqrt(252)


def downside_volatility_factor(
    prices: pd.DataFrame, period: int = 60, skip_recent: int = 1
) -> pd.DataFrame:
    """N-day downside deviation (semideviation of negative returns only)."""
    log_ret = np.log(prices / prices.shift(1))
    neg_ret = log_ret.clip(upper=0)
    # Rolling sum of squared negative returns
    downside_var = (neg_ret ** 2).rolling(window=period).sum().shift(skip_recent)
    downside_vol = np.sqrt(downside_var / period)
    return downside_vol * np.sqrt(252)

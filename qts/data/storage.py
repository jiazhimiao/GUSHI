"""Parquet-based data storage layer."""
from pathlib import Path

import pandas as pd

from qts.utils.logger import logger

# Standard OHLCV column schema
BAR_COLUMNS = [
    "symbol", "trade_date", "open", "high", "low", "close",
    "volume", "amount", "adj_factor", "is_suspended",
    "limit_up", "limit_down", "is_st",
]


def save_bars(df: pd.DataFrame, path: str | Path) -> None:
    """Save daily bars to Parquet, partitioned by year."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)
    logger.debug(f"Saved {len(df)} bars to {p}")


def load_bars(
    path: str | Path,
    start_date: str | None = None,
    end_date: str | None = None,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """Load daily bars from Parquet with optional filtering."""
    p = Path(path)
    if not p.exists():
        logger.warning(f"Bar file not found: {p}")
        return pd.DataFrame(columns=BAR_COLUMNS)

    df = pd.read_parquet(p)
    if start_date:
        df = df[df["trade_date"] >= start_date]
    if end_date:
        df = df[df["trade_date"] <= end_date]
    if symbols:
        df = df[df["symbol"].isin(symbols)]
    return df.reset_index(drop=True)


def load_bars_pivot(
    path: str | Path,
    field: str = "close",
    start_date: str | None = None,
    end_date: str | None = None,
    symbols: list[str] | None = None,
) -> pd.DataFrame:
    """Load bars and pivot into (trade_date x symbol) matrix.

    Useful for factor computation and vectorized backtesting.
    """
    df = load_bars(path, start_date, end_date, symbols)
    if df.empty:
        return pd.DataFrame()
    return df.pivot(index="trade_date", columns="symbol", values=field)


def save_factors(df: pd.DataFrame, name: str, factors_dir: str = "data/factors") -> None:
    """Save factor values to Parquet."""
    p = Path(factors_dir) / f"{name}.parquet"
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(p, index=False)


def load_factors(name: str, factors_dir: str = "data/factors") -> pd.DataFrame:
    """Load factor values from Parquet."""
    p = Path(factors_dir) / f"{name}.parquet"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_parquet(p)

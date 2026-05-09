"""A-share trading calendar via AKShare."""
import pandas as pd
from pathlib import Path

from qts.utils.logger import logger


def fetch_trade_calendar(start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch A-share trading calendar from AKShare.

    Returns DataFrame with columns: trade_date, is_trading_day
    """
    import akshare as ak

    logger.info(f"Fetching trade calendar: {start_date} to {end_date}")
    raw = ak.tool_trade_date_hist_sina()
    raw["trade_date"] = pd.to_datetime(raw["trade_date"])
    cal = raw.rename(columns={"trade_date": "trade_date"})
    cal["is_trading_day"] = True
    cal = cal.sort_values("trade_date").reset_index(drop=True)

    mask = (cal["trade_date"] >= pd.Timestamp(start_date)) & (
        cal["trade_date"] <= pd.Timestamp(end_date)
    )
    result = cal.loc[mask].copy()
    result["trade_date"] = result["trade_date"].dt.strftime("%Y-%m-%d")
    logger.info(f"Calendar fetched: {len(result)} trading days")
    return result[["trade_date", "is_trading_day"]]


def load_or_fetch_calendar(
    start_date: str,
    end_date: str,
    cache_path: str = "data/raw/calendar.parquet",
) -> pd.DataFrame:
    """Load calendar from cache if fresh, otherwise fetch and cache."""
    path = Path(cache_path)
    if path.exists():
        existing = pd.read_parquet(path)
        existing_dates = set(existing["trade_date"])
        needed_start = pd.Timestamp(start_date)
        needed_end = pd.Timestamp(end_date)
        has_start = any(
            pd.Timestamp(d) <= needed_start for d in existing["trade_date"]
        )
        has_end = any(
            pd.Timestamp(d) >= needed_end for d in existing["trade_date"]
        )
        if has_start and has_end:
            mask = (pd.to_datetime(existing["trade_date"]) >= needed_start) & (
                pd.to_datetime(existing["trade_date"]) <= needed_end
            )
            return existing.loc[mask].reset_index(drop=True)

    cal = fetch_trade_calendar("2000-01-01", end_date)
    path.parent.mkdir(parents=True, exist_ok=True)
    cal.to_parquet(path, index=False)
    mask = (pd.to_datetime(cal["trade_date"]) >= pd.Timestamp(start_date)) & (
        pd.to_datetime(cal["trade_date"]) <= pd.Timestamp(end_date)
    )
    return cal.loc[mask].reset_index(drop=True)

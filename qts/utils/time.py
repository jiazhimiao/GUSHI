"""Trading calendar and time utilities."""
import pandas as pd


def get_next_trade_date(date: str, calendar: pd.DataFrame, n: int = 1) -> str:
    """Get the nth next trading day from date. n=1 means next trading day."""
    dates = calendar["trade_date"].values
    idx = dates.searchsorted(date, side="right")
    target_idx = min(idx + n - 1, len(dates) - 1)
    return str(dates[target_idx])


def get_prev_trade_date(date: str, calendar: pd.DataFrame, n: int = 1) -> str:
    """Get the nth previous trading day from date."""
    dates = calendar["trade_date"].values
    idx = dates.searchsorted(date, side="left")
    target_idx = max(idx - n, 0)
    return str(dates[target_idx])


def generate_rebalance_dates(
    start: str, end: str, calendar: pd.DataFrame, freq: str = "weekly"
) -> list[str]:
    """Generate rebalance dates according to frequency.

    Args:
        freq: 'daily', 'weekly' (every Monday), 'monthly' (first trading day of month)
    """
    cal = calendar.copy()
    cal["trade_date"] = pd.to_datetime(cal["trade_date"])
    mask = (cal["trade_date"] >= pd.Timestamp(start)) & (
        cal["trade_date"] <= pd.Timestamp(end)
    )
    sub = cal.loc[mask].copy()

    if freq == "daily":
        return [str(d.date()) for d in sub["trade_date"]]

    if freq == "weekly":
        sub["weekday"] = sub["trade_date"].dt.weekday
        sub["week"] = sub["trade_date"].dt.isocalendar().week.astype(int)
        sub["year"] = sub["trade_date"].dt.year
        dates = []
        for (year, week), group in sub.groupby(["year", "week"], sort=True):
            # Pick Monday (weekday 0) if exists, else first day of week
            mon = group[group["weekday"] == 0]
            d = mon.iloc[0] if len(mon) > 0 else group.iloc[0]
            dates.append(str(d["trade_date"].date()))
        return dates

    if freq == "monthly":
        sub["month"] = sub["trade_date"].dt.month
        sub["year"] = sub["trade_date"].dt.year
        dates = []
        for (year, month), group in sub.groupby(["year", "month"], sort=True):
            dates.append(str(group.iloc[0]["trade_date"].date()))
        return dates

    raise ValueError(f"Unknown frequency: {freq}")

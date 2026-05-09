"""Performance metrics for backtest results."""
import pandas as pd
import numpy as np

from qts.utils.logger import logger


def compute_metrics(nav_df: pd.DataFrame, trades_df: pd.DataFrame, initial_cash: float = 1_000_000) -> dict:
    """Compute comprehensive performance metrics.

    Args:
        nav_df: Daily NAV with columns: date, total_value, cash, position_value
        trades_df: Trade records
        initial_cash: Starting capital

    Returns:
        Dict of metric_name -> value
    """
    metrics = {}

    if nav_df.empty:
        return {"error": "No NAV data"}, nav_df, pd.DataFrame()

    nav = nav_df.copy()
    nav = nav.sort_values("date")
    nav["daily_return"] = nav["total_value"].pct_change()
    nav["cum_return_pct"] = (nav["total_value"] / initial_cash - 1) * 100

    returns = nav["daily_return"].dropna()

    final_value = nav["total_value"].iloc[-1]

    # Core metrics
    metrics["start_date"] = nav["date"].iloc[0]
    metrics["end_date"] = nav["date"].iloc[-1]
    metrics["initial_cash"] = initial_cash
    metrics["final_value"] = round(final_value, 2)
    metrics["total_return_pct"] = round((final_value / initial_cash - 1) * 100, 2)

    n_days = len(nav)
    n_years = n_days / 252
    if n_years > 0 and final_value > 0:
        metrics["annual_return_pct"] = round(
            ((final_value / initial_cash) ** (1 / n_years) - 1) * 100, 2
        )
    else:
        metrics["annual_return_pct"] = 0.0

    # Drawdown
    nav["peak"] = nav["total_value"].cummax()
    nav["drawdown"] = (nav["total_value"] - nav["peak"]) / nav["peak"]
    max_dd = nav["drawdown"].min()
    metrics["max_drawdown_pct"] = round(max_dd * 100, 2)

    # Sharpe ratio (annualized)
    if len(returns) > 1 and returns.std() > 0:
        metrics["sharpe_ratio"] = round(
            returns.mean() / returns.std() * np.sqrt(252), 3
        )
    else:
        metrics["sharpe_ratio"] = 0.0

    # Calmar ratio
    if abs(max_dd) > 0 and metrics["annual_return_pct"] != 0:
        metrics["calmar_ratio"] = round(
            metrics["annual_return_pct"] / 100 / abs(max_dd), 3
        )
    else:
        metrics["calmar_ratio"] = 0.0

    # Win rate
    if len(returns) > 0:
        metrics["win_rate_pct"] = round((returns > 0).mean() * 100, 2)
        metrics["avg_win_pct"] = round(returns[returns > 0].mean() * 100, 4) if (returns > 0).any() else 0
        metrics["avg_loss_pct"] = round(returns[returns < 0].mean() * 100, 4) if (returns < 0).any() else 0
    else:
        metrics["win_rate_pct"] = 0
        metrics["avg_win_pct"] = 0
        metrics["avg_loss_pct"] = 0

    # Max consecutive losses
    if len(returns) > 0:
        is_loss = (returns < 0).astype(int)
        streak = (is_loss.groupby((is_loss != is_loss.shift()).cumsum()).cumsum())
        metrics["max_consecutive_losses"] = int(streak.max()) if not streak.empty else 0
    else:
        metrics["max_consecutive_losses"] = 0

    # Recovery time (longest period below previous peak)
    below_peak = nav["drawdown"] < -0.001
    recovery_periods = below_peak.groupby((~below_peak).cumsum()).sum()
    metrics["max_recovery_days"] = int(recovery_periods.max()) if not recovery_periods.empty else 0

    # Monthly returns
    nav["month"] = pd.to_datetime(nav["date"]).dt.to_period("M")
    monthly = nav.groupby("month").agg(
        start_value=("total_value", "first"),
        end_value=("total_value", "last"),
    )
    monthly["monthly_return_pct"] = (
        (monthly["end_value"] / monthly["start_value"] - 1) * 100
    )
    metrics["positive_months_pct"] = round(
        (monthly["monthly_return_pct"] > 0).mean() * 100, 2
    ) if len(monthly) > 0 else 0
    metrics["best_month_pct"] = round(monthly["monthly_return_pct"].max(), 2) if len(monthly) > 0 else 0
    metrics["worst_month_pct"] = round(monthly["monthly_return_pct"].min(), 2) if len(monthly) > 0 else 0
    metrics["monthly_returns"] = monthly  # Keep for heatmap

    # Trade statistics
    if not trades_df.empty:
        trades = trades_df.copy()
        metrics["total_trades"] = len(trades)
        metrics["buy_trades"] = int((trades["side"] == "BUY").sum())
        metrics["sell_trades"] = int((trades["side"] == "SELL").sum())

        total_commission = trades["commission"].sum()
        total_stamp = trades.get("stamp_tax", pd.Series(0)).sum()
        metrics["total_commission"] = round(total_commission, 2)
        metrics["total_stamp_tax"] = round(total_stamp, 2)
        metrics["total_slippage_cost_pct"] = round(
            (total_commission + total_stamp) / initial_cash * 100, 4
        )

        # Turnover (one-sided)
        if len(trades) > 0:
            buy_value = trades[trades["side"] == "BUY"]["cost"].sum() if "cost" in trades.columns else 0
            metrics["turnover_ratio"] = round(
                buy_value / initial_cash, 4
            )
    else:
        metrics["total_trades"] = 0
        metrics["turnover_ratio"] = 0

    return metrics, nav, monthly

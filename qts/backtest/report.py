"""Backtest report generation."""
import json
from pathlib import Path

import pandas as pd

from qts.utils.logger import logger


def generate_report(
    metrics: dict,
    nav_df: pd.DataFrame,
    trades_df: pd.DataFrame,
    output_path: str | None = None,
) -> dict:
    """Generate a structured backtest report.

    Args:
        metrics: Dict from compute_metrics()
        nav_df: Daily NAV DataFrame
        trades_df: Trade records DataFrame
        output_path: If set, save report as JSON.

    Returns:
        Report dict ready for serialization.
    """
    monthly = metrics.pop("monthly_returns", None)

    report = {
        "summary": {
            k: v for k, v in metrics.items()
            if not isinstance(v, pd.DataFrame)
        },
        "nav_summary": {
            "n_days": len(nav_df),
            "max_nav": round(nav_df["total_value"].max(), 2),
            "min_nav": round(nav_df["total_value"].min(), 2),
            "final_nav": round(nav_df["total_value"].iloc[-1], 2) if len(nav_df) > 0 else 0,
        },
        "monthly_returns": _monthly_to_dict(monthly) if monthly is not None else {},
        "trade_summary": {
            "total_trades": len(trades_df),
            "unique_symbols_traded": int(trades_df["symbol"].nunique()) if not trades_df.empty else 0,
        },
    }

    if output_path:
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        report_serializable = _make_serializable(report)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(report_serializable, f, indent=2, ensure_ascii=False, default=str)
        logger.info(f"Report saved to {p}")

    # Put monthly back
    metrics["monthly_returns"] = monthly

    return report


def _monthly_to_dict(monthly: pd.DataFrame) -> list[dict]:
    """Convert monthly returns DataFrame to list of dicts."""
    if monthly is None or monthly.empty:
        return []
    result = []
    for idx, row in monthly.iterrows():
        result.append({
            "month": str(idx),
            "return_pct": round(row["monthly_return_pct"], 2),
        })
    return result


def _make_serializable(obj):
    """Convert numpy types to Python native types for JSON serialization."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: _make_serializable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_make_serializable(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    return obj

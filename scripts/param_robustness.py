"""Parameter robustness testing and grid search optimization.

Usage:
    python scripts/param_robustness.py                    # Quick robustness check
    python scripts/param_robustness.py --mode grid        # Grid search (slow!)
    python scripts/param_robustness.py --mode sensitivity  # One-param sensitivity

Checks how sensitive strategy returns are to parameter changes.
If small parameter changes cause large return swings, the strategy may be overfit.
"""
import sys
from pathlib import Path
import json
import time
import itertools

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.backtest.performance import compute_metrics
from qts.utils.config import get_project_root
from qts.utils.logger import logger, setup_file_log


BASE_PARAMS = {
    "breakout_days": 20,
    "support_days": 10,
    "ma_days": 20,
    "volume_ratio": 1.5,
    "max_loss_pct": 0.08,
    "min_breadth": 0.50,
    "breadth_half": 0.30,
    "atr_multiple": 2.0,
    "atr_period": 14,
    "profit_lock_pct": 0.15,
    "breadth_ma_days": 30,
    "strategy_max_dd": 0.15,
    "top_n": 5,
    "max_weight_per_stock": 0.15,
}

# Parameters to test and their ranges
SENSITIVITY_GRID = {
    "breakout_days": [15, 20, 25, 30],
    "support_days": [5, 10, 15, 20],
    "ma_days": [15, 20, 30, 60],
    "volume_ratio": [1.2, 1.5, 2.0],
    "max_loss_pct": [0.06, 0.08, 0.12, 0.15],
    "min_breadth": [0.40, 0.50, 0.60],
    "breadth_half": [0.20, 0.30, 0.40],
    "atr_multiple": [1.5, 2.0, 3.0],
    "profit_lock_pct": [0.0, 0.10, 0.15, 0.25],
    "breadth_ma_days": [10, 20, 30, 60],
    "strategy_max_dd": [0.10, 0.15, 0.25, 0.99],
    "top_n": [3, 5, 10, 15],
    "max_weight_per_stock": [0.10, 0.15, 0.20],
}


def _make_strategy(params):
    s = TrendBreakoutStrategy(
        breakout_days=params["breakout_days"],
        support_days=params["support_days"],
        ma_days=params["ma_days"],
        volume_ratio=params["volume_ratio"],
        max_loss_pct=params["max_loss_pct"],
        min_breadth=params["min_breadth"],
        breadth_half=params["breadth_half"],
        atr_multiple=params["atr_multiple"],
        atr_period=params["atr_period"],
        profit_lock_pct=params["profit_lock_pct"],
        top_n=params["top_n"],
        max_weight_per_stock=params["max_weight_per_stock"],
    )
    s.breadth_ma_days = params["breadth_ma_days"]
    s.strategy_max_dd = params["strategy_max_dd"]
    s.use_dow_filter = False
    return s


def _run_single(params, start, end):
    root = get_project_root()
    strategy = _make_strategy(params)
    strategy.use_dow_filter = False  # disable for speed
    strategy.strategy_max_dd = 0.30  # high threshold to avoid interference
    engine = BacktestEngine(
        bar_path=str(root / "data/raw/HS300_daily.parquet"),
        calendar_path=str(root / "data/raw/calendar.parquet"),
        start_date=start, end_date=end,
        initial_cash=1_000_000,
        execution_price="intraday_close",
        intraday_spread_bps=15,
    )
    results = engine.run(strategy=strategy, rebalance_freq="daily", min_turnover=0.0)
    metrics, _, _ = compute_metrics(results["nav"], results["trades"], 1_000_000)
    return {
        "return_pct": metrics.get("total_return_pct", 0),
        "max_dd_pct": metrics.get("max_drawdown_pct", 0),
        "sharpe": metrics.get("sharpe_ratio", 0),
        "trades": metrics.get("total_trades", 0),
    }


def run_sensitivity(base_params, start, end):
    """Test each parameter independently: vary one, keep others at base."""
    results = {}
    base_result = _run_single(base_params, start, end)
    logger.info(f"Base: return={base_result['return_pct']:.1f}% DD={base_result['max_dd_pct']:.1f}% Sharpe={base_result['sharpe']:.3f}")
    results["_base_"] = {"params": base_params, "result": base_result}

    for param_name, values in SENSITIVITY_GRID.items():
        logger.info(f"--- Testing {param_name} ---")
        param_results = []
        for val in values:
            if val == base_params.get(param_name):
                continue  # skip base value
            p = base_params.copy()
            p[param_name] = val
            r = _run_single(p, start, end)
            param_results.append({"value": val, "result": r})
            logger.info(f"  {param_name}={val}: return={r['return_pct']:.1f}% DD={r['max_dd_pct']:.1f}% Sharpe={r['sharpe']:.3f}")
        results[param_name] = param_results

    return results


def run_grid_search(base_params, start, end):
    """Grid search over a small subset of key parameters."""
    grid_params = {
        "breakout_days": [15, 20, 25],
        "ma_days": [15, 20, 30],
        "top_n": [3, 5, 10],
        "max_weight_per_stock": [0.10, 0.15, 0.20],
    }

    keys = list(grid_params.keys())
    values = list(grid_params.values())
    combinations = list(itertools.product(*values))

    logger.info(f"Grid search: {len(combinations)} combinations")
    best = None
    best_score = -999

    for combo in combinations:
        p = base_params.copy()
        for k, v in zip(keys, combo):
            p[k] = v
        r = _run_single(p, start, end)
        # Score: return - 0.5 * DD (penalize drawdown)
        score = r["return_pct"] - 0.5 * abs(r["max_dd_pct"])
        if score > best_score:
            best_score = score
            best = {"params": dict(zip(keys, combo)), "result": r, "score": score}
        logger.info(f"  {dict(zip(keys, combo))} -> return={r['return_pct']:.1f}% DD={r['max_dd_pct']:.1f}% score={score:.1f}")

    logger.info(f"Best: {best['params']} -> return={best['result']['return_pct']:.1f}% DD={best['result']['max_dd_pct']:.1f}%")
    return best


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="sensitivity", choices=["sensitivity", "grid"])
    parser.add_argument("--start", default="2024-01-01")
    parser.add_argument("--end", default="2025-12-31")
    parser.add_argument("--output", default="data/robustness_results.json")
    args = parser.parse_args()

    setup_file_log()
    t0 = time.time()

    if args.mode == "sensitivity":
        logger.info("Running parameter sensitivity analysis...")
        results = run_sensitivity(BASE_PARAMS, args.start, args.end)
    else:
        logger.info("Running grid search...")
        results = run_grid_search(BASE_PARAMS, args.start, args.end)

    elapsed = time.time() - t0
    logger.info(f"Done in {elapsed:.0f}s")

    # Analyze sensitivity
    if args.mode == "sensitivity" and "_base_" in results:
        base_ret = results["_base_"]["result"]["return_pct"]
        logger.info("\n=== Sensitivity Summary ===")
        for param_name, param_results in results.items():
            if param_name == "_base_":
                continue
            returns = [r["result"]["return_pct"] for r in param_results]
            ret_range = max(returns) - min(returns)
            sensitivity = "HIGH" if ret_range > 50 else "MEDIUM" if ret_range > 20 else "LOW"
            logger.info(f"  {param_name}: range={ret_range:.0f}% [{sensitivity}]")

    # Save results
    root = get_project_root()
    out_path = root / args.output
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Saved to {out_path}")


if __name__ == "__main__":
    main()

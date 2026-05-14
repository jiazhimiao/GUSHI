"""Robustness sweep: pullback_max_alloc_pct = [0.2, 0.3, 0.4, 0.5, 0.6].

Runs each in parallel via ProcessPoolExecutor (4 workers).
Compares all thresholds vs A baseline.
"""

import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from concurrent.futures import ProcessPoolExecutor, as_completed
import pandas as pd
from qts.utils.config import get_project_root

ROOT = get_project_root()
START, END = "2018-01-01", "2026-05-08"
GATE_VALUES = [0.2, 0.3, 0.4, 0.5, 0.6]

def _run_one(gate_val):
    """Standalone: run one backtest with given gate."""
    from qts.backtest.engine import BacktestEngine
    from qts.strategies.trend_breakout import TrendBreakoutStrategy
    from qts.strategies.regime_engine import RegimeEngine
    from qts.backtest.performance import compute_metrics
    import json
    root = get_project_root()
    with open(str(sorted((root / "data" / "ga_results").glob("*.json"))[-1])) as f:
        ga = json.load(f)
    genes = ga.get("best_genes", {})
    params = ga["best_params"]
    params["score_high"] = 0.72

    regime = RegimeEngine(**{k: v for k, v in params.items() if k != "score_high"})
    s = TrendBreakoutStrategy(
        breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
        max_loss_pct=genes["max_loss_pct"], min_breadth=0.50, breadth_half=0.30,
        atr_multiple=2.0, atr_period=int(genes["atr_period"]),
        profit_lock_pct=genes["profit_lock_pct"], top_n=10,
        max_weight_per_stock=genes["max_weight_per_stock"],
    )
    s.regime_engine = regime; s.use_dow_filter = False
    s.breadth_ma_days = int(genes["breadth_ma_days"])
    s.strategy_max_dd = genes["strategy_max_dd"]
    s.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}
    s.enable_rank_buffer = False
    s.enable_pullback_entry = True
    s.pullback_max_alloc_pct = gate_val

    engine = BacktestEngine(
        bar_path=str(root / "data/raw/HS300_daily.parquet"),
        calendar_path=str(root / "data/raw/calendar.parquet"),
        start_date=START, end_date=END, initial_cash=1_000_000,
        execution_price="intraday_close", intraday_spread_bps=15,
    )
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    metrics, nav, _ = compute_metrics(results["nav"], results["trades"], 1_000_000)
    trades = results["trades"]
    buys = trades[trades["side"] == "BUY"]
    pb_buys = len(buys[buys["reason"] == "pullback_entry"])
    pb_2024 = len(buys[(buys["reason"] == "pullback_entry") & (pd.to_datetime(buys["date"]).dt.year == 2024)])

    # no_2024
    nav_df = nav.copy()
    nav_df["date_dt"] = pd.to_datetime(nav_df["date"])
    nav_df["year"] = nav_df["date_dt"].dt.year
    sn24 = nav_df[nav_df["year"] == 2024]
    ret_2024 = 0
    if len(sn24) >= 2:
        ret_2024 = (sn24["total_value"].iloc[-1] / sn24["total_value"].iloc[0] - 1) * 100
    total_ret = metrics.get("total_return_pct", 0)
    no24 = ((1 + total_ret/100) / (1 + ret_2024/100) - 1) * 100 if ret_2024 > -99 else total_ret

    # Yearly
    yearly = {}
    for yr in [2019, 2020, 2018, 2022]:
        sn = nav_df[nav_df["year"] == yr]
        if len(sn) >= 2:
            yr_ret = (sn["total_value"].iloc[-1] / sn["total_value"].iloc[0] - 1) * 100
            peak = sn["total_value"].cummax()
            yr_dd = (sn["total_value"] - peak) / peak
            yearly[f"ret_{yr}"] = round(yr_ret, 2)
            yearly[f"dd_{yr}"] = round(yr_dd.min() * 100, 2)
        else:
            yearly[f"ret_{yr}"] = 0
            yearly[f"dd_{yr}"] = 0

    return {
        "gate": gate_val,
        "total_return": round(total_ret, 2),
        "annual_return": round(metrics.get("annual_return_pct", 0), 2),
        "max_drawdown": round(metrics.get("max_drawdown_pct", 0), 2),
        "calmar": round(metrics.get("calmar_ratio", 0), 3),
        "no_2024": round(no24, 2),
        "total_trades": len(trades),
        "failed_entry_rate": "—",  # computed later
        "pb_buys": pb_buys,
        "pb_2024": pb_2024,
        **yearly,
    }

if __name__ == "__main__":
    results = []
    t0 = time.time()
    with ProcessPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_run_one, gv): gv for gv in GATE_VALUES}
        for fut in as_completed(futures):
            r = fut.result()
            results.append(r)

    results.sort(key=lambda x: x["gate"])

    print(f"\nTotal: {time.time()-t0:.0f}s")

    df = pd.DataFrame(results)
    print("\n" + "=" * 70)
    print("ROBUSTNESS SWEEP: pullback_max_alloc_pct")
    print("=" * 70)
    print(df.to_string(index=False))

    print("\nA baseline: ret=83.1% dd=-8.1% calmar=0.97 trades=1231 no24=14.9%")
    print("19: ret2019=4.1%  20: ret2020=-1.6%  18dd=-1.1%  22dd=-6.2%")

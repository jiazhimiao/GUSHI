"""score_high sensitivity sweep — parallel via ProcessPoolExecutor.

Verifies if lowering score_high improves 2019/2020 bull exposure
without harming 2018/2022 bear defense.

Usage:
    python scripts/diagnose_score_high_sensitivity.py
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.utils.config import get_project_root
from qts.utils.logger import logger, setup_file_log

SCORE_HIGH_VALUES = [0.76, 0.72, 0.70, 0.68, 0.66, 0.64, 0.62]
START, END = "2018-01-01", "2026-05-08"
TARGET_YEARS = [2018, 2019, 2020, 2022, 2024]
WORKERS = 6


def _genes_to_params(genes: dict) -> dict:
    return {
        "w_breadth": genes["w_breadth"],
        "w_trend": genes["w_trend"],
        "w_stability": genes["w_stability"],
        "w_volume": genes["w_volume"],
        "score_low": genes["score_low"],
        "score_high": genes["score_high"],
        "breakout_bull": int(genes["breakout_bull"]),
        "breakout_bear": int(genes["breakout_bear"]),
        "atr_bull": genes["atr_bull"],
        "atr_bear": genes["atr_bear"],
        "vol_ratio_bull": genes["vol_ratio_bull"],
        "vol_ratio_bear": genes["vol_ratio_bear"],
        "top_n_bull": int(genes["top_n_bull"]),
        "top_n_bear": int(genes["top_n_bear"]),
        "support_bull": int(genes["support_bull"]),
        "support_bear": int(genes["support_bear"]),
        "ma_days_bull": int(genes["ma_bull"]),
        "ma_days_bear": int(genes["ma_bear"]),
    }


def _run_one_task(args: tuple) -> dict:
    """Standalone worker: runs a single backtest in a subprocess."""
    genes, score_high = args

    # Re-import inside subprocess (required for Windows spawn)
    from qts.backtest.engine import BacktestEngine
    from qts.strategies.trend_breakout import TrendBreakoutStrategy
    from qts.strategies.regime_engine import RegimeEngine
    from qts.backtest.performance import compute_metrics
    from qts.utils.config import get_project_root
    import pandas as pd
    root = get_project_root()

    p = _genes_to_params(genes)
    p["score_high"] = score_high

    regime = RegimeEngine(**p)
    s = TrendBreakoutStrategy(
        breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
        max_loss_pct=genes["max_loss_pct"],
        min_breadth=0.50, breadth_half=0.30,
        atr_multiple=2.0, atr_period=int(genes["atr_period"]),
        profit_lock_pct=genes["profit_lock_pct"],
        top_n=10, max_weight_per_stock=genes["max_weight_per_stock"],
    )
    s.regime_engine = regime
    s.use_dow_filter = False
    s.breadth_ma_days = int(genes["breadth_ma_days"])
    s.strategy_max_dd = genes["strategy_max_dd"]
    s.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}

    engine = BacktestEngine(
        bar_path=str(root / "data/raw/HS300_daily.parquet"),
        calendar_path=str(root / "data/raw/calendar.parquet"),
        start_date=START, end_date=END,
        initial_cash=1_000_000,
        execution_price="intraday_close",
        intraday_spread_bps=15,
    )
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    metrics, nav, _ = compute_metrics(results["nav"], results["trades"], 1_000_000)
    trades = results["trades"]

    nav_df = nav.copy()
    nav_df["date_dt"] = pd.to_datetime(nav_df["date"])
    nav_df["position_weight"] = nav_df["position_value"] / nav_df["total_value"]
    total_days = len(nav_df)
    empty_days = int((nav_df["n_positions"] == 0).sum())
    avg_exposure = nav_df["position_weight"].mean() * 100

    nav_df["year"] = nav_df["date_dt"].dt.year
    yearly = {}
    for yr in TARGET_YEARS:
        sn = nav_df[nav_df["year"] == yr]
        if len(sn) >= 2:
            yr_ret = (sn["total_value"].iloc[-1] / sn["total_value"].iloc[0] - 1) * 100
            peak_s = sn["total_value"].cummax()
            sdd = (sn["total_value"] - peak_s) / peak_s
            yr_dd = sdd.min() * 100
            yr_exposure = sn["position_weight"].mean() * 100
            yr_days_mkt = len(sn) - int((sn["n_positions"] == 0).sum())
            yearly[str(yr)] = {
                "return_pct": round(yr_ret, 2),
                "max_dd_pct": round(yr_dd, 2),
                "avg_exposure_pct": round(yr_exposure, 2),
                "days_in_market": yr_days_mkt,
            }
        else:
            yearly[str(yr)] = {"return_pct": 0, "max_dd_pct": 0, "avg_exposure_pct": 0, "days_in_market": 0}

    return {
        "score_high": score_high,
        "total_return_pct": metrics.get("total_return_pct", 0),
        "annual_return_pct": metrics.get("annual_return_pct", 0),
        "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
        "calmar": metrics.get("calmar_ratio", 0),
        "sharpe": metrics.get("sharpe_ratio", 0),
        "total_trades": len(trades),
        "avg_exposure_pct": round(avg_exposure, 2),
        "days_in_market": total_days - empty_days,
        "empty_days": empty_days,
        "yearly": yearly,
    }


def main():
    setup_file_log()
    t0 = time.time()

    logger.info("=" * 70)
    logger.info(f"score_high Sensitivity Sweep ({WORKERS} workers)")
    logger.info(f"  Values: {SCORE_HIGH_VALUES}")
    logger.info(f"  Period: {START} to {END}")
    logger.info("=" * 70)

    root = get_project_root()
    ga_dir = root / "data" / "ga_results"
    jsons = sorted(ga_dir.glob("*.json"))
    with open(str(jsons[-1])) as f:
        ga = json.load(f)
    genes = ga.get("best_genes", {})

    # Build task list
    tasks = [(genes, sh) for sh in SCORE_HIGH_VALUES]

    # Parallel execution
    rows = []
    with ProcessPoolExecutor(max_workers=WORKERS) as pool:
        futures = {pool.submit(_run_one_task, t): t for t in tasks}
        for fut in as_completed(futures):
            r = fut.result()
            rows.append(r)
            logger.info(f"sh={r['score_high']}: ret={r['total_return_pct']:.1f}% "
                         f"ann={r['annual_return_pct']:.1f}% dd={r['max_drawdown_pct']:.1f}% "
                         f"exposure={r['avg_exposure_pct']:.1f}% trades={r['total_trades']}")
            for yr in TARGET_YEARS:
                y = r["yearly"][str(yr)]
                logger.info(f"  {yr}: ret={y['return_pct']:+.1f}% dd={y['max_dd_pct']:.1f}% "
                             f"exposure={y['avg_exposure_pct']:.1f}%")

    # Sort by score_high descending
    rows.sort(key=lambda x: x["score_high"], reverse=True)

    # Build comparison tables
    period_cols = ["score_high", "total_return_pct", "annual_return_pct",
                   "max_drawdown_pct", "calmar", "sharpe", "total_trades",
                   "avg_exposure_pct", "days_in_market"]
    df_full = pd.DataFrame(rows)[period_cols]

    print("\n" + "=" * 70)
    print("FULL PERIOD COMPARISON")
    print("=" * 70)
    print(df_full.to_string(index=False))

    yearly_rows = []
    for r in rows:
        for yr in TARGET_YEARS:
            y = r["yearly"][str(yr)]
            yearly_rows.append({
                "score_high": r["score_high"],
                "year": yr,
                "return_pct": y["return_pct"],
                "max_dd_pct": y["max_dd_pct"],
                "avg_exposure_pct": y["avg_exposure_pct"],
                "days_in_market": y["days_in_market"],
            })
    df_yearly = pd.DataFrame(yearly_rows)

    print("\n" + "=" * 70)
    print("YEARLY DETAIL")
    print("=" * 70)
    print(df_yearly.to_string(index=False))

    # Save CSV
    out_dir = root / "data" / "diagnosis"
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    df_full.to_csv(out_dir / f"score_high_sensitivity_{ts}.csv", index=False)
    df_yearly.to_csv(out_dir / f"score_high_sensitivity_yearly_{ts}.csv", index=False)

    # Conclusion
    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)

    baseline_row = df_full[df_full["score_high"] == 0.76]
    if len(baseline_row) > 0:
        b = baseline_row.iloc[0]
        print(f"Baseline (sh=0.76): ret={b['total_return_pct']:.1f}% "
              f"dd={b['max_drawdown_pct']:.1f}% exp={b['avg_exposure_pct']:.1f}%")

    best_calm = df_full.loc[df_full["calmar"].idxmax()]
    best_ret = df_full.loc[df_full["total_return_pct"].idxmax()]
    print(f"Best Calmar: sh={best_calm['score_high']} ret={best_calm['total_return_pct']:.1f}% "
          f"dd={best_calm['max_drawdown_pct']:.1f}%")
    print(f"Best Return: sh={best_ret['score_high']} ret={best_ret['total_return_pct']:.1f}% "
          f"dd={best_ret['max_drawdown_pct']:.1f}%")

    # 2019/2020 improvement
    for yr in ["2019", "2020"]:
        yr_data = df_yearly[df_yearly["year"] == int(yr)]
        base = yr_data[yr_data["score_high"] == 0.76]
        best = yr_data.loc[yr_data["return_pct"].idxmax()]
        if len(base) > 0:
            print(f"{yr}: baseline ret={base['return_pct'].iloc[0]:+.1f}% "
                  f"exp={base['avg_exposure_pct'].iloc[0]:.1f}% -> "
                  f"best sh={best['score_high']} ret={best['return_pct']:+.1f}% "
                  f"exp={best['avg_exposure_pct']:.1f}%")

    # 2018/2022 defense
    for yr in ["2018", "2022"]:
        yr_data = df_yearly[df_yearly["year"] == int(yr)]
        base = yr_data[yr_data["score_high"] == 0.76]
        worst = yr_data.loc[yr_data["return_pct"].idxmin()]
        if len(base) > 0:
            print(f"{yr}: baseline ret={base['return_pct'].iloc[0]:+.1f}% "
                  f"dd={base['max_dd_pct'].iloc[0]:.1f}% -> "
                  f"worst sh={worst['score_high']} ret={worst['return_pct']:+.1f}% "
                  f"dd={worst['max_dd_pct']:.1f}%")

    elapsed = time.time() - t0
    print(f"\nTotal: {elapsed:.0f}s ({elapsed/60:.1f}m)")
    logger.info(f"Done in {elapsed:.0f}s")


if __name__ == "__main__":
    main()

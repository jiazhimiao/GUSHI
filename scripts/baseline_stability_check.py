"""A baseline reproducibility check: run A twice, compare nav/trades/positions.

Outputs:
    - Yearly return table (2018-2026) for both runs
    - First divergent date in NAV/trades/positions
    - Full data saved to data/stability_check/run1/ and run2/
"""

import sys, json, hashlib, shutil
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.backtest.performance import compute_metrics
from qts.utils.config import get_project_root

ROOT = get_project_root()
START, END = "2018-01-01", "2026-05-08"

with open(str(sorted((ROOT / "data" / "ga_results").glob("*.json"))[-1])) as f:
    ga = json.load(f)
genes = ga.get("best_genes", {})
params = ga["best_params"]
params["score_high"] = 0.72

def run_a():
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
    s.enable_pullback_entry = False

    engine = BacktestEngine(
        bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
        calendar_path=str(ROOT / "data/raw/calendar.parquet"),
        start_date=START, end_date=END, initial_cash=1_000_000,
        execution_price="intraday_close", intraday_spread_bps=15,
    )
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    return results["nav"], results["trades"], results["positions"]

# Data hashes
data_hashes = {}
for f in ["data/historical_constituents.json", "data/raw/HS300_daily.parquet", "data/raw/calendar.parquet"]:
    fp = ROOT / f
    data_hashes[f] = hashlib.md5(fp.read_bytes()).hexdigest()

timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

for run_label in ["run1", "run2"]:
    print(f"\nRunning {run_label}...")
    nav, trades, positions = run_a()

    out_dir = ROOT / "data" / "stability_check" / timestamp / run_label
    out_dir.mkdir(parents=True, exist_ok=True)
    nav.to_csv(out_dir / "nav.csv", index=False)
    trades.to_csv(out_dir / "trades.csv", index=False)
    positions.to_csv(out_dir / "positions.csv", index=False)

    # Yearly metrics
    nav["date_dt"] = pd.to_datetime(nav["date"])
    nav["year"] = nav["date_dt"].dt.year
    nav["position_weight"] = nav["position_value"] / nav["total_value"]

    print(f"  NAV rows: {len(nav)}  Trades: {len(trades)}  Positions: {len(positions)}")

    metrics, _, _ = compute_metrics(nav, trades, 1_000_000)
    print(f"  total_return: {metrics['total_return_pct']:.1f}%")
    print(f"  total_trades: {len(trades)}")
    print(f"  max_dd: {metrics['max_drawdown_pct']:.1f}%")

    print(f"\n  Yearly breakdown ({run_label}):")
    for yr in range(2018, 2027):
        sn = nav[nav["year"] == yr]
        yt = trades[pd.to_datetime(trades["date"]).dt.year == yr]
        if len(sn) < 2:
            continue
        yr_ret = (sn["total_value"].iloc[-1] / sn["total_value"].iloc[0] - 1) * 100
        peak = sn["total_value"].cummax()
        yr_dd = (sn["total_value"] - peak) / peak
        yr_dd_pct = yr_dd.min() * 100
        yr_exp = sn["position_weight"].mean() * 100
        yr_trades = len(yt)
        print(f"    {yr}: ret={yr_ret:+.1f}%  dd={yr_dd_pct:.1f}%  exp={yr_exp:.1f}%  trades={yr_trades}")

    # Save config
    config = {
        "run_label": run_label,
        "data_hashes": data_hashes,
        "score_high": 0.72,
        "enable_pullback_entry": False,
        "enable_rank_buffer": False,
        "strategy_params": params,
    }
    with open(out_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False, default=str)

    if run_label == "run1":
        nav1, trades1, positions1 = nav, trades, positions
    else:
        nav2, trades2, positions2 = nav, trades, positions

# Compare
print(f"\n{'='*60}")
print("COMPARISON: run1 vs run2")
print(f"{'='*60}")

# Yearly comparison
print("\nYearly return comparison:")
for yr in range(2018, 2027):
    s1 = nav1[nav1["year"] == yr]
    s2 = nav2[nav2["year"] == yr]
    if len(s1) < 2 or len(s2) < 2:
        continue
    r1 = (s1["total_value"].iloc[-1] / s1["total_value"].iloc[0] - 1) * 100
    r2 = (s2["total_value"].iloc[-1] / s2["total_value"].iloc[0] - 1) * 100
    diff = r2 - r1
    marker = " <-- DIFF" if abs(diff) > 0.5 else ""
    print(f"  {yr}: run1={r1:+.1f}%  run2={r2:+.1f}%  diff={diff:+.1f}%{marker}")

# First NAV divergence
nav1_d = nav1[["date", "total_value"]].rename(columns={"total_value": "nav1"})
nav2_d = nav2[["date", "total_value"]].rename(columns={"total_value": "nav2"})
nav_m = nav1_d.merge(nav2_d, on="date")
nav_m["diff"] = abs(nav_m["nav1"] - nav_m["nav2"])
first_nav_diff = nav_m[nav_m["diff"] > 0.01]
if len(first_nav_diff) > 0:
    fd = first_nav_diff.iloc[0]
    print(f"\nFirst NAV divergence: {fd['date']}  (nav1={fd['nav1']:.2f}, nav2={fd['nav2']:.2f}, diff={fd['diff']:.2f})")
else:
    print("\nNAV identical across both runs!")

# First trade divergence
t1 = trades1[["date", "symbol", "side"]].copy()
t2 = trades2[["date", "symbol", "side"]].copy()
t1["idx"] = range(len(t1))
t2["idx"] = range(len(t2))
# Merge on date+symbol+side
tm = t1.merge(t2, on=["date", "symbol", "side"], how="outer", indicator=True)
only1 = tm[tm["_merge"] == "left_only"]
only2 = tm[tm["_merge"] == "right_only"]
if len(only1) > 0:
    print(f"\nFirst trade only in run1: {only1.iloc[0]['date']} {only1.iloc[0]['symbol']} {only1.iloc[0]['side']}")
if len(only2) > 0:
    print(f"First trade only in run2: {only2.iloc[0]['date']} {only2.iloc[0]['symbol']} {only2.iloc[0]['side']}")
if len(only1) == 0 and len(only2) == 0:
    print("\nTrades identical across both runs!")
else:
    print(f"Trades diff: {len(only1)} only in run1, {len(only2)} only in run2")

print(f"\nData saved to: data/stability_check/{timestamp}/")

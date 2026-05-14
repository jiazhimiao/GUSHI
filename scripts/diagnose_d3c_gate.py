"""D3c: alloc_pct gate simulation for pullback entry."""

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.diagnosis.signal_report import fifo_match
from qts.utils.config import get_project_root

ROOT = get_project_root()
START, END = "2018-01-01", "2026-05-08"

with open(str(sorted((ROOT / "data" / "ga_results").glob("*.json"))[-1])) as f:
    ga = json.load(f)
genes = ga.get("best_genes", {})
params = ga["best_params"]
params["score_high"] = 0.72

pb_records = []

class DiagStrategy(TrendBreakoutStrategy):
    pass

regime_obj = RegimeEngine(**{k: v for k, v in params.items() if k != "score_high"})
s = DiagStrategy(
    breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
    max_loss_pct=genes["max_loss_pct"], min_breadth=0.50, breadth_half=0.30,
    atr_multiple=2.0, atr_period=int(genes["atr_period"]),
    profit_lock_pct=genes["profit_lock_pct"], top_n=10,
    max_weight_per_stock=genes["max_weight_per_stock"],
)
s.regime_engine = regime_obj; s.use_dow_filter = False
s.breadth_ma_days = int(genes["breadth_ma_days"])
s.strategy_max_dd = genes["strategy_max_dd"]
s.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}
s.enable_rank_buffer = False
s.enable_pullback_entry = True

_orig = s.generate_signals
def _patched(current_date, market_data, factor_data, current_positions):
    result = _orig(current_date, market_data, factor_data, current_positions)
    if result is not None and not result.empty:
        pb = result[result["reason"] == "pullback_entry"]
        for _, row in pb.iterrows():
            pb_records.append({
                "date": current_date,
                "symbol": row["symbol"],
                "score": row["score"],
                "total_targets": len(result),
                "bk_in_result": len(result[result["reason"] == "breakout_entry"]),
                "pb_in_result": len(pb),
                "current_pos": len(current_positions) if current_positions is not None else 0,
            })
    return result
s.generate_signals = _patched

engine = BacktestEngine(
    bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
    calendar_path=str(ROOT / "data/raw/calendar.parquet"),
    start_date=START, end_date=END, initial_cash=1_000_000,
    execution_price="intraday_close", intraday_spread_bps=15,
)
results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
trades = results["trades"]
nav = results["nav"]

# Get alloc_pct from strategy's regime engine
# Re-run a lightweight pass to get alloc_pct for each date
# Actually, use the nav data to estimate: alloc_pct ≈ target_value / total_value
# But we need the actual alloc_pct from generate_signals.
# Let's instead back-calculate from the target weights on pb buy dates.

# Simpler: get alloc_pct from the strategy object's state during the run.
# The strategy computes alloc_pct in generate_signals. Let me extract it from the
# pb_records by getting it from the strategy during the patched call.
# Since the patched function is called AFTER _orig, alloc_pct is already computed.
# But _orig doesn't return alloc_pct. Let me get it indirectly.

# Approach: on each pb buy date, estimate alloc_pct from nav:
# alloc_pct ≈ (target_positions * target_weight) / total_value
# Not accurate. Better: add alloc_pct capture to the monkey patch.

# Re-run with alloc_pct capture
pb_records2 = []

def _patched2(current_date, market_data, factor_data, current_positions):
    result = _orig(current_date, market_data, factor_data, current_positions)
    if result is not None and len(result) > 0:
        w = result["target_weight"].iloc[0] if "target_weight" in result.columns else 0
        n = len(result)
        est_alloc = w * n
    else:
        est_alloc = 0

    if result is not None and not result.empty:
        pb = result[result["reason"] == "pullback_entry"]
        for _, row in pb.iterrows():
            pb_records2.append({
                "date": current_date,
                "symbol": row["symbol"],
                "est_alloc_pct": est_alloc,
                "total_targets": len(result),
                "current_pos": len(current_positions) if current_positions is not None else 0,
            })
    return result

# Re-run
pb_records2.clear()
s2 = DiagStrategy(
    breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
    max_loss_pct=genes["max_loss_pct"], min_breadth=0.50, breadth_half=0.30,
    atr_multiple=2.0, atr_period=int(genes["atr_period"]),
    profit_lock_pct=genes["profit_lock_pct"], top_n=10,
    max_weight_per_stock=genes["max_weight_per_stock"],
)
s2.regime_engine = regime_obj; s2.use_dow_filter = False
s2.breadth_ma_days = int(genes["breadth_ma_days"])
s2.strategy_max_dd = genes["strategy_max_dd"]
s2.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}
s2.enable_rank_buffer = False
s2.enable_pullback_entry = True
s2.generate_signals = _patched2

engine2 = BacktestEngine(
    bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
    calendar_path=str(ROOT / "data/raw/calendar.parquet"),
    start_date=START, end_date=END, initial_cash=1_000_000,
    execution_price="intraday_close", intraday_spread_bps=15,
)
results2 = engine2.run(strategy=s2, rebalance_freq="daily", min_turnover=0.0)
trades2 = results2["trades"]

# Build context DataFrame
ctx = pd.DataFrame(pb_records2)
ctx["year"] = pd.to_datetime(ctx["date"]).dt.year

# Add P&L from matched trades
matched2, _ = fifo_match(trades2)
pb_buys2 = trades2[trades2["side"] == "BUY"]
pb_buys2 = pb_buys2[pb_buys2["reason"] == "pullback_entry"]

print(f"Pullback unique BUY trades: {len(pb_buys2)}")
print(f"Pullback records from generate_signals: {len(ctx)}")

# Match context to trades for exit data
for i, row in ctx.iterrows():
    bt = pb_buys2[(pb_buys2["symbol"] == row["symbol"]) & (pb_buys2["date"] == row["date"])]
    ym = matched2[(matched2["symbol"] == row["symbol"]) &
                  (matched2["buy_date"] >= row["date"])]
    if len(ym) > 0:
        ym = ym.sort_values("buy_date")
        ctx.at[i, "pnl_pct"] = ym.iloc[0]["pnl_pct"]
        ctx.at[i, "holding_days"] = ym.iloc[0]["holding_days"]
        ctx.at[i, "exit_reason"] = str(ym.iloc[0]["exit_reason"]) if pd.notna(ym.iloc[0].get("exit_reason")) else "rebalance"

# Output per-buy table
print(f"\n{'='*80}")
print("PER-PULLBACK-BUY DETAIL (first 25)")
print(f"{'='*80}")
disp = ctx[["date", "year", "symbol", "est_alloc_pct", "total_targets",
            "current_pos", "pnl_pct", "holding_days", "exit_reason"]].head(25)
for _, r in disp.iterrows():
    print(f"  {r['date']}  {r['year']}  {r['symbol']}  "
          f"alloc={r['est_alloc_pct']:.2f}  targets={int(r['total_targets'])}  "
          f"pos={int(r['current_pos'])}  "
          f"pnl={r['pnl_pct']*100 if pd.notna(r.get('pnl_pct')) else 0:+.2f}%  "
          f"hold={r['holding_days']:.0f}d  exit={r['exit_reason']}")

# D3c gate simulation
print(f"\n{'='*80}")
print("D3c: ALLOC_PCT GATE SIMULATION")
print(f"{'='*80}")

thresholds = [0.2, 0.4, 0.5, 0.6]
valid = ctx[ctx["pnl_pct"].notna()].copy()
print(f"Total pb buys with P&L data: {len(valid)}")

for thresh in thresholds:
    kept = valid[valid["est_alloc_pct"] <= thresh]
    filtered = valid[valid["est_alloc_pct"] > thresh]

    kw = kept["pnl_pct"].mean() * 100 if len(kept) > 0 else 0
    kwr = (kept["pnl_pct"] > 0).mean() * 100 if len(kept) > 0 else 0
    fw = filtered["pnl_pct"].mean() * 100 if len(filtered) > 0 else 0
    fwr = (filtered["pnl_pct"] > 0).mean() * 100 if len(filtered) > 0 else 0

    print(f"\n  alloc_pct <= {thresh}:")
    print(f"    kept: {len(kept)} buys  win={kwr:.0f}%  avg_pnl={kw:+.2f}%")
    print(f"    filtered: {len(filtered)} buys  win={fwr:.0f}%  avg_pnl={fw:+.2f}%")

    for yr in [2019, 2020, 2024]:
        ky = kept[kept["year"] == yr]
        fy = filtered[filtered["year"] == yr]
        k_wn = (ky["pnl_pct"] > 0).mean() * 100 if len(ky) > 0 else 0
        k_pnl = ky["pnl_pct"].mean() * 100 if len(ky) > 0 else 0
        f_wn = (fy["pnl_pct"] > 0).mean() * 100 if len(fy) > 0 else 0
        f_pnl = fy["pnl_pct"].mean() * 100 if len(fy) > 0 else 0
        print(f"      {yr}: kept={len(ky)} (win={k_wn:.0f}% pnl={k_pnl:+.2f}%)  "
              f"filtered={len(fy)} (win={f_wn:.0f}% pnl={f_pnl:+.2f}%)")

print(f"\n{'='*80}")
print("CONCLUSION")
print(f"{'='*80}")
for thresh in thresholds:
    kept = valid[valid["est_alloc_pct"] <= thresh]
    k19 = kept[kept["year"] == 2019]
    k20 = kept[kept["year"] == 2020]
    k24 = kept[kept["year"] == 2024]
    f24 = valid[(valid["est_alloc_pct"] > thresh) & (valid["year"] == 2024)]
    print(f"  alloc<={thresh}: keep 2019={len(k19)}/{len(valid[valid['year']==2019])} "
          f"2020={len(k20)}/{len(valid[valid['year']==2020])} "
          f"2024={len(k24)}/{len(valid[valid['year']==2024])} "
          f"(filter 2024 bad={len(f24)})")

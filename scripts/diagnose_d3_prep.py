"""D3 prep: analyze pullback buy context, test filtering rules.

Captures per-buy context from a D2 run, then simulates 3 filtering rules
without running full backtests.
"""

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

# Patch to record per-buy context
_pb_context = []

class DiagStrategy(TrendBreakoutStrategy):
    pass  # inherit everything, we'll monkey-patch generate_signals

regime = RegimeEngine(**{k: v for k, v in params.items() if k != "score_high"})
s = DiagStrategy(
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

# Monkey-patch to capture per-buy details
_orig_gen = s.generate_signals
def _patched_gen(current_date, market_data, factor_data, current_positions):
    result = _orig_gen(current_date, market_data, factor_data, current_positions)
    if result is not None and not result.empty:
        pb_in_result = result[result["reason"] == "pullback_entry"]
        # count breakout in filters_ok
        from qts.strategies.trend_breakout import TrendBreakoutStrategy
        filters_ok = s._apply_filters(
            market_data[market_data["trade_date"] == current_date],
            market_data, current_date
        )
        bk_scores = s._evaluate_breakout_batch(current_date, filters_ok)
        for _, row in pb_in_result.iterrows():
            _pb_context.append({
                "date": current_date,
                "symbol": row["symbol"],
                "score": row["score"],
                "bk_candidates": len(bk_scores),
                "bk_selected": len(result[result["reason"] == "breakout_entry"]),
                "pb_candidates": len([x for x in s._pb_funnel if x["date"] == current_date]),
                "total_targets": len(result),
                "alloc_pct": None,  # filled below
                "current_positions": len(current_positions) if current_positions is not None else 0,
            })
    return result
s.generate_signals = _patched_gen

engine = BacktestEngine(
    bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
    calendar_path=str(ROOT / "data/raw/calendar.parquet"),
    start_date=START, end_date=END, initial_cash=1_000_000,
    execution_price="intraday_close", intraday_spread_bps=15,
)
results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
trades = results["trades"]
buys = trades[trades["side"] == "BUY"]
pb_buys = buys[buys["reason"] == "pullback_entry"]

# Get alloc_pct from strategy's funnel records
funnel_df = pd.DataFrame(s._pb_funnel)
# Merge with pb_context
ctx_df = pd.DataFrame(_pb_context)

# Add entry from matched trades
matched, _ = fifo_match(trades)
pb_matched = matched[matched["symbol"].isin(set(pb_buys["symbol"]))]

# Find the pb_buy entry for each symbol+date
for i, row in ctx_df.iterrows():
    # Find matching BUY trade
    bt = pb_buys[(pb_buys["symbol"] == row["symbol"]) & (pb_buys["date"] == row["date"])]
    if len(bt) > 0:
        ctx_df.at[i, "buy_price"] = bt.iloc[0]["price"]

# Match funnel to context by date
for i, row in ctx_df.iterrows():
    fd = funnel_df[funnel_df["date"] == row["date"]]
    if len(fd) > 0:
        fr = fd.iloc[0]
        # get branch_entered from the funnel
        pass

# Add year
ctx_df["year"] = pd.to_datetime(ctx_df["date"]).dt.year

# Add post-entry P&L
# For each pb buy, find matching sell in matched
for i, row in ctx_df.iterrows():
    ym = pb_matched[(pb_matched["symbol"] == row["symbol"]) &
                    (pb_matched["buy_date"] >= row["date"])]
    if len(ym) > 0:
        ym = ym.sort_values("buy_date")
        ctx_df.at[i, "pnl_pct"] = ym.iloc[0]["pnl_pct"]
        ctx_df.at[i, "holding_days"] = ym.iloc[0]["holding_days"]

print("=" * 60)
print("PULLBACK BUY CONTEXT (first 20)")
print("=" * 60)
disp = ctx_df[["date", "year", "symbol", "bk_candidates", "bk_selected",
                "total_targets", "current_positions"]].head(20)
print(disp.to_string(index=False))

# ---- D3 rule simulations ----
print(f"\n{'='*60}")
print("D3 RULE SIMULATIONS")
print(f"{'='*60}")

# D3a: max 1 pullback per day
ctx_df["d3a_keep"] = False
for dt, grp in ctx_df.groupby("date"):
    grp = grp.sort_values("score", ascending=False)
    keep_idx = grp.head(1).index
    ctx_df.loc[keep_idx, "d3a_keep"] = True

# D3b: only when breakout + hold < top_n (i.e. slots not filled)
ctx_df["slots_used"] = ctx_df["bk_selected"] + ctx_df["current_positions"]
ctx_df["slots_available"] = 5 - ctx_df["slots_used"]  # top_n=5
ctx_df["d3b_keep"] = ctx_df["slots_available"] > 0

# D3c: alloc_pct gate (use funnel.added > 0 as proxy — pb only fires when alloc>0)

for rule_name, keep_col, desc in [
    ("D3a: max 1 pb/day", "d3a_keep", "最多1个pullback/天"),
    ("D3b: only when slots<top_n", "d3b_keep", "仅breakout不足时补位"),
]:
    kept = ctx_df[ctx_df[keep_col]]
    filtered = ctx_df[~ctx_df[keep_col]]
    print(f"\n{desc}:")
    print(f"  kept: {len(kept)} buys  filtered: {len(filtered)} buys")

    for yr in [2019, 2020, 2023, 2024]:
        ky = kept[kept["year"] == yr]
        fy = filtered[filtered["year"] == yr]
        kw = ky["pnl_pct"].mean() * 100 if len(ky) > 0 and ky["pnl_pct"].notna().any() else 0
        kwr = (ky["pnl_pct"] > 0).mean() * 100 if len(ky) > 0 and ky["pnl_pct"].notna().any() else 0
        fw = fy["pnl_pct"].mean() * 100 if len(fy) > 0 and fy["pnl_pct"].notna().any() else 0
        fwr = (fy["pnl_pct"] > 0).mean() * 100 if len(fy) > 0 and fy["pnl_pct"].notna().any() else 0
        print(f"  {yr}: kept={len(ky)} (win={kwr:.0f}% pnl={kw:+.2f}%)  "
              f"filtered={len(fy)} (win={fwr:.0f}% pnl={fw:+.2f}%)")

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
print(f"Total pb buys: {len(ctx_df)}")
print(f"D3a keeps: {ctx_df['d3a_keep'].sum()} ({ctx_df['d3a_keep'].mean()*100:.0f}%)")
print(f"D3b keeps: {ctx_df['d3b_keep'].sum()} ({ctx_df['d3b_keep'].mean()*100:.0f}%)")
print("\nDone.")

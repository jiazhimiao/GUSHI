"""D2 failure attribution: why did pullback_entry hurt portfolio returns?"""

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.backtest.performance import compute_metrics
from qts.diagnosis.signal_report import fifo_match
from qts.utils.config import get_project_root

ROOT = get_project_root()
START, END = "2018-01-01", "2026-05-08"

with open(str(sorted((ROOT / "data" / "ga_results").glob("*.json"))[-1])) as f:
    ga = json.load(f)
genes = ga.get("best_genes", {})
params = ga["best_params"]
params["score_high"] = 0.72

def run(enable_pb):
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
    s.enable_pullback_entry = enable_pb

    engine = BacktestEngine(
        bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
        calendar_path=str(ROOT / "data/raw/calendar.parquet"),
        start_date=START, end_date=END, initial_cash=1_000_000,
        execution_price="intraday_close", intraday_spread_bps=15,
    )
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    return results, s

print("Running A (no pb)...")
resA, sA = run(False)
print("Running D2 (pb)...")
resD, sD = run(True)

# Q1: 48 vs 262
buysD = resD["trades"][resD["trades"]["side"] == "BUY"]
pb_buys = buysD[buysD["reason"] == "pullback_entry"]
print(f"\n{'='*60}")
print("Q1: 48 actual buys vs 262 matched trades")
print(f"{'='*60}")
print(f"  pullback BUY trades: {len(pb_buys)} (unique buys)")
matchedD, _ = fifo_match(resD["trades"])
pb_matched = matchedD[matchedD["symbol"].isin(set(pb_buys["symbol"]))]
# Only count pairs that correspond to pullback buys (rough: any symbol that ever had a pullback buy)
print(f"  fifo matched pairs for pullback symbols: {len(pb_matched)}")
print(f"  Ratio: {len(pb_matched)/len(pb_buys):.1f}x (each BUY fragments into ~{len(pb_matched)/max(len(pb_buys),1):.1f} sell segments)")
print(f"  -> 48 = actual unique BUY orders")
print(f"  -> 262 = FIFO-matched sell segments for those symbols")

# Q2: pullback yearly
print(f"\n{'='*60}")
print("Q2: pullback_entry yearly performance")
print(f"{'='*60}")
for yr in range(2018, 2027):
    yb = pb_buys[pd.to_datetime(pb_buys["date"]).dt.year == yr]
    yb_syms = set(yb["symbol"])
    ym = matchedD[matchedD["symbol"].isin(yb_syms)]
    ym_valid = ym[ym["pnl_pct"].notna()]
    if len(yb) == 0:
        continue
    win_r = (ym_valid["pnl_pct"] > 0).mean() * 100 if len(ym_valid) > 0 else 0
    avg_pnl = ym_valid["pnl_pct"].mean() * 100 if len(ym_valid) > 0 else 0
    total_pnl = ym_valid["pnl_pct"].sum() * 100 if len(ym_valid) > 0 else 0
    avg_h = ym_valid["holding_days"].mean() if len(ym_valid) > 0 else 0
    is_reb = ym_valid["exit_reason"].isna() | (ym_valid["exit_reason"] == "")
    reb_r = is_reb.sum() / len(ym_valid) * 100 if len(ym_valid) > 0 else 0
    stop_kw = ["止损", "stop", "loss", "atr", "跌破"]
    es = ((ym_valid["holding_days"] <= 10) &
          ym_valid["exit_reason"].apply(lambda r: any(k in str(r).lower() for k in stop_kw)))
    bl = ym_valid["pnl_pct"] < -0.05
    fer = len(ym_valid[es | bl]) / len(ym_valid) * 100 if len(ym_valid) > 0 else 0
    print(f"  {yr}: buys={len(yb):3d}  matched={len(ym_valid):4d}  win={win_r:.0f}%  "
          f"avg_pnl={avg_pnl:+.2f}%  total_pnl={total_pnl:+.1f}%  fer={fer:.0f}%  "
          f"hold={avg_h:.1f}d  reb_sell={reb_r:.0f}%")

# Q3: Yearly return differences
print(f"\n{'='*60}")
print("Q3: D2 vs A yearly return difference")
print(f"{'='*60}")
for results, label in [(resA, "A"), (resD, "D2")]:
    nav = results["nav"]
    nav["date_dt"] = pd.to_datetime(nav["date"])
    nav["year"] = nav["date_dt"].dt.year

for yr in range(2018, 2027):
    sa = resA["nav"]
    sa["date_dt"] = pd.to_datetime(sa["date"])
    sa = sa[sa["date_dt"].dt.year == yr]
    sd = resD["nav"]
    sd["date_dt"] = pd.to_datetime(sd["date"])
    sd = sd[sd["date_dt"].dt.year == yr]
    if len(sa) < 2 or len(sd) < 2:
        continue
    ra = (sa["total_value"].iloc[-1] / sa["total_value"].iloc[0] - 1) * 100
    rd = (sd["total_value"].iloc[-1] / sd["total_value"].iloc[0] - 1) * 100
    peak_a = sa["total_value"].cummax()
    dd_a = (sa["total_value"] - peak_a) / peak_a
    peak_d = sd["total_value"].cummax()
    dd_d = (sd["total_value"] - peak_d) / peak_d
    diff = rd - ra
    marker = " <-- MAIN LOSS" if diff < -2 else (" <-- GAIN" if diff > 2 else "")
    print(f"  {yr}: A={ra:+.1f}%  D2={rd:+.1f}%  diff={diff:+.1f}%  "
          f"dd_A={dd_a.min()*100:.1f}%  dd_D2={dd_d.min()*100:.1f}%{marker}")

# Q4: displacement check
print(f"\n{'='*60}")
print("Q4: Did pullback displace breakout?")
print(f"{'='*60}")
funnel = sD._pb_funnel if hasattr(sD, '_pb_funnel') else []
pb_date_set = {f["date"] for f in funnel if f["bought"] > 0}
print(f"  Days with pullback buys: {len(pb_date_set)}")
print(f"  Pullback buys total: {sum(f['bought'] for f in funnel)}")
# For pullback buys, the score was *0.8 — check if breakout candidates scored higher
print(f"  Pullback score multiplier: 0.8 (disadvantaged vs breakout)")
print(f"  -> If pullback still got into top_5 with 0.8x score,")
print(f"     the displaced breakout candidates had lower scores.")

# Q5: Post-entry analysis
print(f"\n{'='*60}")
print("Q5: Post-entry performance (pullback vs breakout)")
print(f"{'='*60}")
for label, buys_subset in [("breakout", buysD[buysD["reason"] == "breakout_entry"]),
                            ("pullback", buysD[buysD["reason"] == "pullback_entry"])]:
    if len(buys_subset) == 0:
        continue
    syms = set(buys_subset["symbol"])
    ym = matchedD[matchedD["symbol"].isin(syms)]
    ym_valid = ym[ym["pnl_pct"].notna()]
    if len(ym_valid) == 0:
        print(f"  {label}: no matched trades")
        continue
    win5 = (ym_valid[ym_valid["holding_days"] <= 5]["pnl_pct"] > 0).mean() * 100
    win10 = (ym_valid[ym_valid["holding_days"] <= 10]["pnl_pct"] > 0).mean() * 100
    avg5 = ym_valid[ym_valid["holding_days"] <= 5]["pnl_pct"].mean() * 100
    avg10 = ym_valid[ym_valid["holding_days"] <= 10]["pnl_pct"].mean() * 100
    print(f"  {label}: n={len(ym_valid)}")
    print(f"    ≤5d: win={win5:.0f}% avg_pnl={avg5:+.2f}%")
    print(f"    ≤10d: win={win10:.0f}% avg_pnl={avg10:+.2f}%")
    print(f"    overall: win={(ym_valid['pnl_pct']>0).mean()*100:.0f}% avg_pnl={ym_valid['pnl_pct'].mean()*100:+.2f}%")

print("\nDone.")

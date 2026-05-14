"""A baseline fitness decomposition — compute all sub-scores."""

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
TRAIN = ("2018-01-01", "2021-12-31")
VAL   = ("2022-01-01", "2024-12-31")
FULL  = ("2018-01-01", "2026-05-08")

with open(str(sorted((ROOT / "data" / "ga_results").glob("*.json"))[-1])) as f:
    ga = json.load(f)
genes = ga.get("best_genes", {})
params = ga["best_params"]
params["score_high"] = 0.72

def _run(period):
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
        start_date=period[0], end_date=period[1], initial_cash=1_000_000,
        execution_price="intraday_close", intraday_spread_bps=15,
    )
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    metrics, nav, _ = compute_metrics(results["nav"], results["trades"], 1_000_000)
    return metrics, nav, results["trades"], results["positions"]

# Run all three periods
print("Running TRAIN (2018-2021)...")
mt, nt, tt, pt = _run(TRAIN)
print("Running VAL (2022-2024)...")
mv, nv, tv, pv = _run(VAL)
print("Running FULL (2018-2026)...")
mf, nf, tf, pf = _run(FULL)

# ── Raw metrics ──
M = {}

# Calmar
M["train_calmar"] = round(mt.get("calmar_ratio", 0), 3)
M["val_calmar"]   = round(mv.get("calmar_ratio", 0), 3)

# no_2024
# full_no_2024: FULL period (2018-2026), chain-remove 2024
full_ret = mf["total_return_pct"]
nf["date_dt"] = pd.to_datetime(nf["date"])
nf["year"] = nf["date_dt"].dt.year
sn24 = nf[nf["year"] == 2024]
ret_2024_full = 0
if len(sn24) >= 2:
    ret_2024_full = (sn24["total_value"].iloc[-1] / sn24["total_value"].iloc[0] - 1) * 100
full_no24_p = ((1 + full_ret/100) / (1 + ret_2024_full/100) - 1) * 100 if ret_2024_full > -99 else full_ret
full_no24_years = (len(nf) - len(sn24)) / 252
M["full_no_2024_pct"] = round(full_no24_p, 2)

# val_no_2024: VAL period (2022-2024), chain-remove 2024
val_ret = mv["total_return_pct"]
nv["date_dt"] = pd.to_datetime(nv["date"])
nv["year"] = nv["date_dt"].dt.year
sv24 = nv[nv["year"] == 2024]
ret_2024_val = 0
if len(sv24) >= 2:
    ret_2024_val = (sv24["total_value"].iloc[-1] / sv24["total_value"].iloc[0] - 1) * 100
val_no24_p = ((1 + val_ret/100) / (1 + ret_2024_val/100) - 1) * 100 if ret_2024_val > -99 else val_ret
M["val_no_2024_pct"] = round(val_no24_p, 2)

# Yearly returns from FULL
nf["position_weight"] = nf["position_value"] / nf["total_value"]
for yr in [2019, 2020, 2018, 2022]:
    sn = nf[nf["year"] == yr]
    if len(sn) >= 2:
        yr_ret = (sn["total_value"].iloc[-1] / sn["total_value"].iloc[0] - 1) * 100
        peak = sn["total_value"].cummax()
        yr_dd = (sn["total_value"] - peak) / peak
        M[f"ret_{yr}"] = round(yr_ret, 2)
        M[f"dd_{yr}"] = round(yr_dd.min() * 100, 2)
    else:
        M[f"ret_{yr}"] = 0; M[f"dd_{yr}"] = 0

# failed_entry_rate from FULL
matched, _ = fifo_match(tf)
valid = matched[matched["pnl_pct"].notna()]
if len(valid) > 0:
    stop_kw = ["stop", "loss", "atr", "???"]
    early = (valid["holding_days"] <= 10) & valid["exit_reason"].apply(
        lambda r: any(k in str(r).lower() for k in stop_kw))
    big = valid["pnl_pct"] < -0.05
    M["failed_entry_rate"] = round(len(valid[early | big]) / len(valid) * 100, 1)
else:
    M["failed_entry_rate"] = 0

# turnover
buys = tf[tf["side"] == "BUY"]
buy_val = buys["cost"].sum() if "cost" in buys.columns else 0
avg_nav = nf["total_value"].mean()
M["annual_turnover"] = round(buy_val / avg_nav / (len(nf) / 252), 2) if avg_nav > 0 else 0

# max_year_profit_pct
nf["year"] = nf["date_dt"].dt.year
total_profit = nf["total_value"].iloc[-1] - nf["total_value"].iloc[0]
yearly_profits = {}
for yr in range(2018, 2027):
    sn = nf[nf["year"] == yr]
    if len(sn) >= 2:
        yearly_profits[yr] = sn["total_value"].iloc[-1] - sn["total_value"].iloc[0]
if total_profit > 0:
    pos_profits = [v for v in yearly_profits.values() if v > 0]
    max_yr = max(pos_profits) if pos_profits else total_profit
    M["max_year_profit_pct"] = round(max_yr / total_profit * 100, 1)
else:
    M["max_year_profit_pct"] = 100

# Annual return / total_trades / avg_position from FULL
M["annual_return_pct"] = round(mf.get("annual_return_pct", 0), 2)
M["total_trades"] = len(tf)
M["avg_position"] = round(nf["position_weight"].mean() * 100, 2)

# ── Normalized scores ──
S = {}
S["calmar_score"] = round(np.clip(M["train_calmar"] * 0.5 + M["val_calmar"] * 0.5, -1.0, 3.0), 3)

# no_2024: use full_no_2024 (priority)
no24_pct = M["full_no_2024_pct"]
S["no_2024_score"] = round(min(no24_pct / 15.0, 2.0), 3)
S["full_no_2024_pct"] = no24_pct
S["val_no_2024_pct"] = M["val_no_2024_pct"]

# recovery
rec = (max(0, M["ret_2019"] - 2.0) + max(0, M["ret_2020"] + 5.0)) / 20.0
S["recovery_score"] = round(min(rec, 1.0), 3)

# bear penalty
bear = (max(0, abs(M["dd_2018"]) - 1.5) / 10.0 + max(0, abs(M["dd_2022"]) - 7.0) / 10.0) / 2
S["bear_penalty"] = round(bear, 3)

# failed_entry penalty
fer_p = max(0, M["failed_entry_rate"] - 20) / 30.0
S["failed_entry_penalty"] = round(fer_p, 3)

# turnover penalty
to_p = max(0, M["annual_turnover"] - 12) / 20.0
S["turnover_penalty"] = round(to_p, 3)

# dependency penalty
dep_p = max(0, M["max_year_profit_pct"] - 50) / 50.0
S["dependency_penalty"] = round(dep_p, 3)

# Final
fitness = (1.0 * S["calmar_score"] + 0.6 * S["no_2024_score"] + 0.3 * S["recovery_score"]
           - 0.5 * S["bear_penalty"] - 0.3 * S["failed_entry_penalty"]
           - 0.2 * S["turnover_penalty"] - 0.5 * S["dependency_penalty"])
S["final_fitness"] = round(fitness, 3)

# ── Output ──
print("\n" + "="*60)
print("A BASELINE FITNESS DECOMPOSITION")
print("="*60)
print("\n--- Raw Metrics ---")
for k, v in M.items():
    print(f"  {k}: {v}")
print("\n--- Normalized Scores ---")
for k, v in S.items():
    print(f"  {k}: {v}")
print(f"\n  >>> FINAL FITNESS = {S['final_fitness']}")

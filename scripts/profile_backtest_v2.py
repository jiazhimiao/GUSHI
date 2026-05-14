"""Profile actual backtest engine — instrument key methods."""

import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.backtest.performance import compute_metrics
from qts.utils.config import get_project_root

ROOT = get_project_root()
START, END = "2018-01-01", "2026-05-08"

_timers = {}
def t(key):
    _timers.setdefault(key, [0, 0])  # [total_time, count]
    return time.time()

def p(key, t0):
    elapsed = time.time() - t0
    _timers[key][0] += elapsed
    _timers[key][1] += 1

# Load params
with open(str(sorted((ROOT / "data" / "ga_results").glob("*.json"))[-1])) as f:
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
s.enable_rank_buffer = False; s.enable_pullback_entry = False

# Monkey-patch key methods
_orig_gen = s.generate_signals
def _patched(current_date, market_data, factor_data, current_positions):
    t0 = t("generate_signals")
    r = _orig_gen(current_date, market_data, factor_data, current_positions)
    p("generate_signals", t0)
    return r
s.generate_signals = _patched

_orig_exit = s.check_exit
def _patched_exit(sym, date, md, ep, entry_price=0):
    t0 = t("check_exit")
    r = _orig_exit(sym, date, md, ep, entry_price)
    p("check_exit", t0)
    return r
s.check_exit = _patched_exit

engine = BacktestEngine(
    bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
    calendar_path=str(ROOT / "data/raw/calendar.parquet"),
    start_date=START, end_date=END, initial_cash=1_000_000,
    execution_price="intraday_close", intraday_spread_bps=15,
)

# Patch engine methods
_orig_mtm = engine._mark_to_market
def _patched_mtm(date):
    t0 = t("mark_to_market")
    r = _orig_mtm(date)
    p("mark_to_market", t0)
    return r
engine._mark_to_market = _patched_mtm

_orig_exec = engine._execute_rebalance
def _patched_exec(target, date, use_open=False):
    t0 = t("execute_rebalance")
    r = _orig_exec(target, date, use_open)
    p("execute_rebalance", t0)
    return r
engine._execute_rebalance = _patched_exec

_orig_ck_exits = engine._check_and_execute_exits
def _patched_ck(strat, date, eps):
    t0 = t("check_all_exits")
    r = _orig_ck_exits(strat, date, eps)
    p("check_all_exits", t0)
    return r
engine._check_and_execute_exits = _patched_ck

_orig_end_day = engine.broker.end_of_day
def _patched_eod():
    t0 = t("broker_eod")
    r = _orig_end_day()
    p("broker_eod", t0)
    return r
engine.broker.end_of_day = _patched_eod

# Phase labels
t0_total = t("=== TOTAL ===")
t0_init = time.time()

# Run init phase (engine.__init__ already called, but run() does loading)
t0_run = t("run_method")
results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
p("run_method", t0_run)

t0_metrics = t("compute_metrics")
metrics, nav, monthly = compute_metrics(results["nav"], results["trades"], 1_000_000)
p("compute_metrics", t0_metrics)
p("=== TOTAL ===", t0_total)

print("\n" + "="*70)
print("BACKTEST PROFILING (2018-2026, instrumented)")
print("="*70)
for key, (total, count) in sorted(_timers.items(), key=lambda x: -x[1][0]):
    bar = "#" * int(total / max(t[0] for t in _timers.values()) * 40)
    if count > 1:
        print(f"  {key:30s}: {total:7.1f}s  x{count:5d}  avg={total/count*1000:5.0f}ms  {bar}")
    else:
        print(f"  {key:30s}: {total:7.1f}s  {bar}")

total_time = _timers["=== TOTAL ==="][0]
print(f"\n  {'TOTAL':30s}: {total_time:7.0f}s ({total_time/60:.1f}m)")

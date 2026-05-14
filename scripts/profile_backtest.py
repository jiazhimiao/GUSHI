"""Backtest performance profiler: instrument key sections, output timing breakdown."""

import sys, json, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
from qts.utils.config import get_project_root
from qts.data.storage import load_bars

ROOT = get_project_root()
START, END = "2018-01-01", "2026-05-08"

timings = {}

def tic(label):
    timings[label] = time.time()

def toc(label):
    timings[label] = time.time() - timings[label]

# ── Phase 1: Data loading ──
tic("load_bars")
bars = load_bars(str(ROOT / "data/raw/HS300_daily.parquet"), START, END)
toc("load_bars")

tic("load_calendar")
cal = pd.read_parquet(ROOT / "data/raw/calendar.parquet")
toc("load_calendar")

tic("load_constituents")
with open(ROOT / "data/historical_constituents.json") as f:
    const_data = json.load(f)
toc("load_constituents")

# ── Phase 2: Pivot ──
tic("pivot_all")
prices     = bars.pivot(index="trade_date", columns="symbol", values="close")
volumes    = bars.pivot(index="trade_date", columns="symbol", values="volume")
highs      = bars.pivot(index="trade_date", columns="symbol", values="high")
opens_p    = bars.pivot(index="trade_date", columns="symbol", values="open")
lows       = bars.pivot(index="trade_date", columns="symbol", values="low")
toc("pivot_all")

# ── Phase 3: Pre-compute regime dimensions ──
tic("regime_precompute")
# Use first-quarter constituents for the full period
hs300 = const_data["indices"]["HS300"]
quarterly = hs300["quarterly"]
sorted_q = sorted(quarterly.keys())
# Pick first quarter snapshot
first_q = quarterly[sorted_q[0]]
b_cols = [c for c in first_q if c in prices.columns]
prices_b = prices[b_cols]
volumes_b = volumes[b_cols]

# Breadth
bma = 30
ma_br = prices_b.rolling(bma).mean()
breadth_series = (prices_b > ma_br).mean(axis=1)

# Trend
rets_20 = prices_b.pct_change(20, fill_method=None)
trend_series = (rets_20.median(axis=1) / 0.05).clip(0, 1)

# Stability
rets_d = prices_b.pct_change(fill_method=None)
vol_20 = rets_d.rolling(20).std().median(axis=1)
vol_60 = rets_d.rolling(60).std().median(axis=1)
stability_series = (1.0 - ((vol_20 / vol_60.replace(0, float("nan"))) - 0.5).clip(0, 1)).fillna(0.5)

# Volume energy
vm20 = volumes_b.rolling(20).mean().median(axis=1)
vm60 = volumes_b.rolling(60).mean().median(axis=1)
volume_series = (((vm20 / vm60.replace(0, float("nan"))) - 0.7) / 0.6).clip(0, 1).fillna(0.5)
toc("regime_precompute")

# ── Phase 4: Simulate main loop (1/5 of dates) ──
tic("bars_by_symbol")
bars_by_sym = {sym: g.sort_values("trade_date") for sym, g in bars.groupby("symbol")}
toc("bars_by_symbol")

dates = sorted(prices.index)
sample_dates = dates[::5]  # every 5th date (995 → ~199 dates)
n_samples = len(sample_dates)

tic("main_loop_sample")
# Simulate generate_signals for each sample date (breakout batch only)
for i, date in enumerate(sample_dates):
    date_str = str(date)[:10]
    # Find constituents
    allowed = None
    for q_date in reversed(sorted_q):
        if q_date <= date_str:
            allowed = quarterly[q_date]
            break
    if not allowed:
        continue
    filt_cols = [c for c in allowed if c in prices.columns]
    cp = prices.loc[:date, filt_cols]
    vp = volumes.loc[:date, filt_cols]
    hp = highs.loc[:date, filt_cols]
    # Simulate breakout batch (the expensive part)
    if len(cp) > 20:
        tc = cp.iloc[-1]
        tv = vp.iloc[-1]
        valid = tv > 0
        n_day_high = hp.iloc[-(20+1):-1].max()
        cond1 = tc > n_day_high
        avg_vol = vp.iloc[-(20+1):-1].mean()
        cond2 = (avg_vol > 0) & (tv >= avg_vol * 1.5)
        ma60 = cp.iloc[-(60+1):-1].mean()
        cond3 = tc > ma60
        _ = valid & cond1 & cond2 & cond3
toc("main_loop_sample")

main_loop_est = timings["main_loop_sample"] * 5  # scale to full
total_est = sum(v for k, v in timings.items() if k != "main_loop_sample") + main_loop_est

print("\n" + "="*60)
print("BACKTEST PROFILING (2018-2026)")
print("="*60)
print(f"\n  Field count: {prices.shape[0]} trading days x {prices.shape[1]} stocks = {prices.shape[0]*prices.shape[1]:,} cells\n")

for k, v in sorted(timings.items(), key=lambda x: -x[1]):
    pct = v / total_est * 100
    bar = "#" * int(pct / 2)
    print(f"  {k:30s}: {v:6.1f}s ({pct:5.1f}%) {bar}")

print(f"\n  {'ESTIMATED TOTAL':30s}: {total_est:6.0f}s ({total_est/60:.0f}m)")

# Key breakdowns
print("\n--- KEY INSIGHTS ---")
loop_pct = main_loop_est / total_est * 100
pivot_pct = timings["pivot_all"] / total_est * 100
regime_pct = timings["regime_precompute"] / total_est * 100
load_pct = timings["load_bars"] / total_est * 100
print(f"  Main loop (signal generation): {main_loop_est:.0f}s ({loop_pct:.0f}%)")
print(f"  Pivot operations: {timings['pivot_all']:.0f}s ({pivot_pct:.0f}%)")
print(f"  Regime pre-compute: {timings['regime_precompute']:.0f}s ({regime_pct:.0f}%)")
print(f"  Data loading: {timings['load_bars']:.0f}s ({load_pct:.0f}%)")
print(f"  bars_by_symbol: {timings['bars_by_symbol']:.0f}s")
print(f"  Main loop per date: {timings['main_loop_sample']/n_samples*1000:.0f}ms")
print(f"    x {len(dates)} dates = {timings['main_loop_sample']/n_samples*len(dates):.0f}s estimated")

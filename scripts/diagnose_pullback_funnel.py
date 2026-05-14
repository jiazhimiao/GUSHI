"""Pullback condition ablation: which conditions kill all signals?

Runs a light scan over 2018-2026, checking each pullback condition
independently. Does NOT run backtest — just counts stock-date combinations.

Outputs stepwise funnel + individual condition hits + parameter sweep.
"""

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from qts.utils.config import get_project_root
from qts.strategies.regime_engine import RegimeEngine

ROOT = get_project_root()
START, END = "2018-01-01", "2026-05-08"

# Load GA params
with open(str(sorted((ROOT / "data" / "ga_results").glob("*.json"))[-1])) as f:
    ga = json.load(f)
genes = ga.get("best_genes", {})
params = ga["best_params"]
params["score_high"] = 0.72

# Load data
bars = pd.read_parquet(ROOT / "data/raw/HS300_daily.parquet")
# Filter by date range
bars = bars[(bars["trade_date"] >= START) & (bars["trade_date"] <= END)].copy()

# Load constituents
with open(ROOT / "data/historical_constituents.json") as f:
    const_data = json.load(f)
hs300 = const_data["indices"]["HS300"]
quarterly = hs300["quarterly"]

# Pivot matrices
prices = bars.pivot(index="trade_date", columns="symbol", values="close")
opens_p = bars.pivot(index="trade_date", columns="symbol", values="open")
highs = bars.pivot(index="trade_date", columns="symbol", values="high")
lows = bars.pivot(index="trade_date", columns="symbol", values="low")
volumes = bars.pivot(index="trade_date", columns="symbol", values="volume")

# Build regime engine
regime = RegimeEngine(**{k: v for k, v in params.items() if k != "score_high"})

dates = sorted(prices.index)
results = []

for i, date in enumerate(dates):
    if i < 61:
        continue  # warmup

    # Get constituents for this date
    date_str = str(date)[:10]
    sorted_q = sorted(quarterly.keys())
    allowed = None
    for q_date in reversed(sorted_q):
        if q_date <= date_str:
            allowed = quarterly[q_date]
            break
    if not allowed:
        continue

    # Basic filters: ST, suspended
    day_bars = bars[bars["trade_date"] == date_str]
    raw_n = len(day_bars[day_bars["symbol"].isin(allowed)])
    filt = day_bars[day_bars["symbol"].isin(allowed)]
    filt = filt[~filt["is_st"].fillna(False)]
    filt = filt[~filt["is_suspended"].fillna(False)]
    eligible = filt["symbol"].tolist()
    eligible_n = len(eligible)

    if eligible_n == 0:
        continue

    common = [s for s in eligible if s in prices.columns]
    if not common:
        continue

    close_slice = prices.loc[:date, common]
    open_slice = opens_p.loc[:date, common]
    high_slice = highs.loc[:date, common]
    low_slice = lows.loc[:date, common]
    vol_slice = volumes.loc[:date, common]

    if len(close_slice) < 61:
        continue

    # ---- Pullback conditions ----
    today_close = close_slice.iloc[-1]
    today_open = open_slice.iloc[-1]
    today_vol = vol_slice.iloc[-1]

    ma20 = close_slice.iloc[-21:-1].mean()
    avg_vol_20 = vol_slice.iloc[-21:-1].mean()

    # ret_20d (shift 1 to avoid today)
    ret_20d = close_slice.iloc[-2] / close_slice.iloc[-22] - 1

    max_high_20 = high_slice.iloc[-21:-1].max()
    max_high_before_20 = high_slice.iloc[-61:-21].max()

    low_pullback = low_slice.iloc[-6:-1].min()
    vol_pullback = vol_slice.iloc[-6:-1].mean()

    valid = today_vol > 0

    cond_trend = (ret_20d > 0) | (max_high_20 > max_high_before_20)
    cond_above_ma = today_close > ma20
    cond_near_ma_3 = abs(low_pullback / ma20 - 1).fillna(1) < 0.03
    cond_near_ma_5 = abs(low_pullback / ma20 - 1).fillna(1) < 0.05
    cond_near_ma_8 = abs(low_pullback / ma20 - 1).fillna(1) < 0.08
    cond_shrink_08 = vol_pullback.fillna(0) < avg_vol_20 * 0.8
    cond_shrink_10 = vol_pullback.fillna(0) < avg_vol_20 * 1.0
    cond_shrink_12 = vol_pullback.fillna(0) < avg_vol_20 * 1.2
    cond_pos_candle = today_close > today_open
    cond_pos_close = today_close > close_slice.iloc[-2]
    cond_confirm_08 = today_vol >= avg_vol_20 * 0.8
    cond_confirm_06 = today_vol >= avg_vol_20 * 0.6

    v = valid.values if hasattr(valid, 'values') else valid

    year = pd.Timestamp(date).year

    # Count each condition independently
    def cnt(c):
        return int(c[v].sum()) if isinstance(c, pd.Series) else 0

    row = {
        "date": date_str, "year": year,
        "raw_universe": raw_n,
        "eligible": eligible_n,
        "cond_trend": cnt(cond_trend),
        "cond_above_ma": cnt(cond_above_ma),
        "cond_near_ma_3": cnt(cond_near_ma_3),
        "cond_near_ma_5": cnt(cond_near_ma_5),
        "cond_near_ma_8": cnt(cond_near_ma_8),
        "cond_shrink_08": cnt(cond_shrink_08),
        "cond_shrink_10": cnt(cond_shrink_10),
        "cond_shrink_12": cnt(cond_shrink_12),
        "cond_pos_candle": cnt(cond_pos_candle),
        "cond_pos_close": cnt(cond_pos_close),
        "cond_confirm_08": cnt(cond_confirm_08),
        "cond_confirm_06": cnt(cond_confirm_06),
        # V1 all
        "v1_all": cnt(cond_trend & cond_above_ma & cond_near_ma_3 & cond_shrink_08 & cond_pos_candle & cond_confirm_08),
        # Alternatives
        "alt_near5": cnt(cond_trend & cond_above_ma & cond_near_ma_5 & cond_shrink_08 & cond_pos_candle & cond_confirm_08),
        "alt_n5_sh1": cnt(cond_trend & cond_above_ma & cond_near_ma_5 & cond_shrink_10 & cond_pos_candle & cond_confirm_08),
        "alt_n5_sh1_pc": cnt(cond_trend & cond_above_ma & cond_near_ma_5 & cond_shrink_10 & cond_pos_close & cond_confirm_08),
        "alt_n5_noshrink": cnt(cond_trend & cond_above_ma & cond_near_ma_5 & cond_confirm_08),
        "alt_n8_sh1": cnt(cond_trend & cond_above_ma & cond_near_ma_8 & cond_shrink_10 & cond_pos_candle & cond_confirm_08),
        # Breakout overlap
        "breakout_today": 0,  # filled below
    }
    results.append(row)

df = pd.DataFrame(results)

# ---- Yearly aggregation ----
print("=" * 70)
print("ANNUAL STEPWISE FUNNEL (median stock-days per month)")
print("=" * 70)
cond_cols = ["cond_trend", "cond_above_ma", "cond_near_ma_3", "cond_near_ma_5",
             "cond_shrink_08", "cond_pos_candle", "cond_confirm_08", "v1_all"]
for yr in range(2018, 2027):
    yd = df[df["year"] == yr]
    if len(yd) == 0:
        continue
    print(f"\n{yr}: {len(yd)} trading days")
    print(f"  raw universe (median): {yd['raw_universe'].median():.0f}")
    print(f"  eligible (median):     {yd['eligible'].median():.0f}")
    for c in cond_cols:
        med = yd[c].median()
        total = yd[c].sum()
        print(f"  {c:25s}: median={med:5.0f}  total={total:8d}")

print("\n" + "=" * 70)
print("INDIVIDUAL CONDITION HIT RATES (stock-days per year)")
print("=" * 70)
indiv_cols = ["cond_trend", "cond_above_ma", "cond_near_ma_3", "cond_near_ma_5",
              "cond_near_ma_8", "cond_shrink_08", "cond_shrink_10", "cond_shrink_12",
              "cond_pos_candle", "cond_pos_close", "cond_confirm_08", "cond_confirm_06"]
for yr in range(2018, 2027):
    yd = df[df["year"] == yr]
    if len(yd) == 0:
        continue
    print(f"\n{yr}:")
    for c in indiv_cols:
        total = yd[c].sum()
        days = len(yd)
        print(f"  {c:25s}: total={total:8d}  avg/day={total/days:.1f}")

print("\n" + "=" * 70)
print("PARAMETER ABLATION: candidate counts per year")
print("=" * 70)
ablation_cols = ["v1_all", "alt_near5", "alt_n5_sh1", "alt_n5_sh1_pc",
                 "alt_n5_noshrink", "alt_n8_sh1"]
abl_names = {
    "v1_all": "V1: near3% shrink0.8 candle confirm0.8",
    "alt_near5": "near5% shrink0.8 candle confirm0.8",
    "alt_n5_sh1": "near5% shrink1.0 candle confirm0.8",
    "alt_n5_sh1_pc": "near5% shrink1.0 prev_close confirm0.8",
    "alt_n5_noshrink": "near5% NO shrink confirm0.8",
    "alt_n8_sh1": "near8% shrink1.0 candle confirm0.8",
}
for ab in ablation_cols:
    name = abl_names.get(ab, ab)
    print(f"\n  {name}:")
    for yr in [2019, 2020, 2024]:
        yd = df[df["year"] == yr]
        if len(yd) == 0:
            continue
        total = yd[ab].sum()
        days = len(yd)
        print(f"    {yr}: total={total:6d}  avg/day={total/days:.1f}")
    all_total = df[ab].sum()
    print(f"    ALL: total={all_total:6d}")

print("\n" + "=" * 70)
print("BOTTLENECK ANALYSIS")
print("=" * 70)
# Which condition eliminates the most stocks?
for yr in [2019, 2020, 2024]:
    yd = df[df["year"] == yr]
    if len(yd) == 0:
        continue
    avg_eligible = yd["eligible"].mean()
    print(f"\n{yr} (avg eligible/stock-day: {avg_eligible:.0f}):")
    # What % of eligible stocks pass each condition?
    for c in indiv_cols:
        pct = yd[c].sum() / (avg_eligible * len(yd)) * 100
        print(f"  {c:25s}: {pct:.1f}%")

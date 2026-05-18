"""A0.5: Walk-forward pair feasibility recheck.

Key fixes vs A0:
- Formation window: 250 trading days, rolling quarterly
- T+1 open entry (not same-day close)
- Non-overlapping position states
- Trade filters: suspended, limit up/down, liquidity
- Beta/regime separation
"""
import json, sys, warnings
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path(__file__).resolve().parent.parent

warnings.filterwarnings("ignore")

# ── Config ──
FORMATION_DAYS = 250
REBALANCE_MONTHS = 3  # quarterly
CORR_THRESHOLD = 0.7
MIN_OBS_FORMATION = 200
Z_LOOKBACK = 120
Z_ENTRY = 2.0
Z_EXIT = 0.5
MAX_HOLD_DAYS = 60
STOP_LOSS = -0.10
MIN_AVG_AMOUNT = 50_000_000  # 50M CNY daily

# ── Load data ──
print("=== Loading data ===")
with open(ROOT / "data/historical_constituents.json", encoding="utf-8") as f:
    const_data = json.load(f)
const_q = const_data["indices"]["HS300"]["quarterly"]

bars = pd.read_parquet(ROOT / "data/raw/HS300_daily.parquet")
bars["trade_date"] = pd.to_datetime(bars["trade_date"])
bars = bars[(bars["trade_date"] >= "2020-01-01") & (bars["trade_date"] <= "2026-05-15")]
print(f"Bars: {len(bars)} rows, {bars['symbol'].nunique()} symbols")

calendar = pd.read_parquet(ROOT / "data/raw/calendar.parquet")
calendar["trade_date"] = pd.to_datetime(calendar["trade_date"])
trading_days_all = sorted(calendar[calendar["is_trading_day"]]["trade_date"].tolist())
trading_days_all = [d for d in trading_days_all if d >= pd.Timestamp("2020-01-01")]

idx_bars = pd.read_parquet(ROOT / "data/raw/index/sh000300_daily.parquet")
idx_bars["trade_date"] = pd.to_datetime(idx_bars["trade_date"])
idx_close = idx_bars.set_index("trade_date")["close"]

# ── Pivot ──
print("Pivoting...")
close_raw = bars.pivot(index="trade_date", columns="symbol", values="close")
open_raw = bars.pivot(index="trade_date", columns="symbol", values="open")
high_raw = bars.pivot(index="trade_date", columns="symbol", values="high")
low_raw = bars.pivot(index="trade_date", columns="symbol", values="low")
volume_raw = bars.pivot(index="trade_date", columns="symbol", values="volume")
amount_raw = bars.pivot(index="trade_date", columns="symbol", values="amount")
suspended_raw = bars.pivot(index="trade_date", columns="symbol", values="is_suspended")
limit_up_raw = bars.pivot(index="trade_date", columns="symbol", values="limit_up")
limit_down_raw = bars.pivot(index="trade_date", columns="symbol", values="limit_down")
is_st_raw = bars.pivot(index="trade_date", columns="symbol", values="is_st")

# ── Generate rebalance periods ──
# Start from 2022-07-01 (first formation window: 2021-07 ~ 2022-06)
rebalance_dates = []
for yr in range(2022, 2027):
    for mo in [1, 4, 7, 10]:
        d = pd.Timestamp(f"{yr}-{mo:02d}-01")
        if d >= pd.Timestamp("2022-07-01") and d <= pd.Timestamp("2026-05-15"):
            rebalance_dates.append(d)

print(f"\nRebalance periods: {len(rebalance_dates)}")
print(f"First: {rebalance_dates[0].date()}, Last: {rebalance_dates[-1].date()}")

# ── Walk-forward loop ──
all_trades = []
period_stats = []

for period_idx, rb_date in enumerate(rebalance_dates):
    rb_str = rb_date.strftime("%Y-%m-%d")

    # Formation window: previous 250 trading days before rb_date
    form_end = rb_date - pd.Timedelta(days=1)
    form_dates = [d for d in trading_days_all if d <= form_end]
    if len(form_dates) < FORMATION_DAYS + 50:
        continue
    form_dates = form_dates[-FORMATION_DAYS:]
    form_start = form_dates[0]
    form_end_dt = form_dates[-1]

    # Trading window: from rb_date to next rebalance (or data end)
    next_rb_idx = period_idx + 1
    if next_rb_idx < len(rebalance_dates):
        trade_end = rebalance_dates[next_rb_idx] - pd.Timedelta(days=1)
    else:
        trade_end = pd.Timestamp("2026-05-15")

    trade_dates = [d for d in trading_days_all if rb_date <= d <= trade_end]
    if len(trade_dates) < 20:
        continue

    # ── Get HS300 constituents for this period ──
    sorted_cd = sorted(const_q.keys())
    const_syms = None
    for q_date in reversed(sorted_cd):
        if q_date <= rb_str:
            const_syms = set(const_q[q_date])
            break
    if const_syms is None:
        const_syms = set(const_q[sorted_cd[0]])

    # ── Filter to constituents with enough data ──
    avail_syms = []
    for sym in const_syms:
        if sym not in close_raw.columns:
            continue
        sym_close = close_raw[sym].loc[form_start:form_end_dt].dropna()
        if len(sym_close) >= MIN_OBS_FORMATION:
            # Check liquidity
            sym_amount = amount_raw[sym].loc[form_start:form_end_dt].dropna()
            if len(sym_amount) > 0 and sym_amount.mean() >= MIN_AVG_AMOUNT:
                avail_syms.append(sym)

    if len(avail_syms) < 20:
        continue

    # ── Compute pair correlations from formation window ──
    form_close = close_raw.loc[form_start:form_end_dt, avail_syms]
    form_rets = form_close.pct_change().dropna(how="all")
    # Filter columns with enough returns
    valid_cols = [c for c in form_rets.columns if form_rets[c].count() >= MIN_OBS_FORMATION * 0.8]
    form_rets = form_rets[valid_cols]

    if len(valid_cols) < 10:
        continue

    corr = form_rets.corr()

    # Select pairs
    period_pairs = []
    for i in range(len(corr.columns)):
        for j in range(i + 1, len(corr.columns)):
            r = corr.iloc[i, j]
            if r >= CORR_THRESHOLD:
                period_pairs.append({
                    "sym_a": corr.columns[i],
                    "sym_b": corr.columns[j],
                    "correlation": r,
                })

    if len(period_pairs) < 10:
        period_stats.append({
            "period": rb_str,
            "form_start": form_start.strftime("%Y-%m-%d"),
            "form_end": form_end_dt.strftime("%Y-%m-%d"),
            "trade_start": rb_str,
            "trade_end": trade_end.strftime("%Y-%m-%d"),
            "n_stocks": len(valid_cols),
            "n_pairs": len(period_pairs),
            "n_trades": 0,
        })
        continue

    # ── Simulate trades in trading window ──
    # Track position state: (sym_a, sym_b) -> "in_position" or None
    position_state = {}  # key: (sym_a, sym_b), value: {"entry_date", "direction": "A"/"B", "entry_price", "sym"}

    for td in trade_dates:
        td_str = td.strftime("%Y-%m-%d")
        if td_str not in close_raw.index:
            continue

        # Get T+1
        td_idx = trading_days_all.index(td)
        if td_idx + 1 >= len(trading_days_all):
            continue
        t1 = trading_days_all[td_idx + 1]
        t1_str = t1.strftime("%Y-%m-%d")

        if t1_str not in open_raw.index:
            continue

        for pair in period_pairs:
            s1, s2 = pair["sym_a"], pair["sym_b"]
            pair_key = (min(s1, s2), max(s1, s2))

            # Skip if this pair already has an active position
            if pair_key in position_state:
                pos = position_state[pair_key]
                entry_date = pos["entry_date"]
                hold_days = (td - entry_date).days

                # Check exit conditions
                should_exit = False
                exit_reason = ""

                # Recompute z-score using data up to td
                c1 = close_raw[s1].loc[:td_str].dropna()
                c2 = close_raw[s2].loc[:td_str].dropna()
                common_idx = c1.index.intersection(c2.index)
                if len(common_idx) < Z_LOOKBACK:
                    continue
                c1 = c1[common_idx]
                c2 = c2[common_idx]

                log_ratio = np.log(c1 / c2)
                if len(log_ratio) < Z_LOOKBACK:
                    continue
                roll_mean = log_ratio.rolling(Z_LOOKBACK).mean()
                roll_std = log_ratio.rolling(Z_LOOKBACK).std()
                z_now = (log_ratio.iloc[-1] - roll_mean.iloc[-1]) / roll_std.iloc[-1] if roll_std.iloc[-1] > 0 else 0

                current_price = close_raw.at[td_str, pos["sym"]] if pos["sym"] in close_raw.columns else np.nan

                # Exit: |z| < Z_EXIT
                if abs(z_now) < Z_EXIT:
                    should_exit = True
                    exit_reason = "z_reversion"

                # Exit: max hold
                if hold_days >= MAX_HOLD_DAYS:
                    should_exit = True
                    exit_reason = "max_hold"

                # Exit: stop loss
                if pd.notna(current_price) and pos["entry_price"] > 0:
                    pnl = current_price / pos["entry_price"] - 1
                    if pos["direction"] == "A":
                        pnl = current_price / pos["entry_price"] - 1
                    if pnl <= STOP_LOSS:
                        should_exit = True
                        exit_reason = "stop_loss"

                if should_exit:
                    # Close position at T+1 open
                    exit_price = open_raw.at[t1_str, pos["sym"]] if t1_str in open_raw.index and pos["sym"] in open_raw.columns else np.nan

                    tradable = True
                    # Check suspensions
                    if t1_str in suspended_raw.index and pos["sym"] in suspended_raw.columns:
                        if suspended_raw.at[t1_str, pos["sym"]]:
                            tradable = False

                    if pd.notna(exit_price) and tradable and pos["entry_price"] > 0:
                        ret = exit_price / pos["entry_price"] - 1

                        # HS300 return over same period
                        entry_hs = idx_close.get(pos["entry_date"].strftime("%Y-%m-%d"), np.nan)
                        exit_hs = idx_close.get(t1_str, np.nan)
                        hs_ret = exit_hs / entry_hs - 1 if pd.notna(entry_hs) and pd.notna(exit_hs) and entry_hs > 0 else np.nan

                        all_trades.append({
                            "period": rb_str,
                            "pair": f"{s1}/{s2}",
                            "sym_a": s1, "sym_b": s2,
                            "direction": pos["direction"],
                            "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                            "exit_date": t1_str,
                            "entry_price": pos["entry_price"],
                            "exit_price": exit_price,
                            "return": ret,
                            "hs300_return": hs_ret,
                            "excess_return": ret - hs_ret if pd.notna(hs_ret) else np.nan,
                            "hold_days": hold_days,
                            "exit_reason": exit_reason,
                            "correlation": pair["correlation"],
                        })

                    del position_state[pair_key]

            # Try to enter if no active position for this pair
            if pair_key not in position_state:
                # Compute z-score using data up to TD (not T+1)
                c1 = close_raw[s1].loc[:td_str].dropna()
                c2 = close_raw[s2].loc[:td_str].dropna()
                common_idx = c1.index.intersection(c2.index)
                if len(common_idx) < Z_LOOKBACK:
                    continue
                c1 = c1[common_idx]
                c2 = c2[common_idx]

                log_ratio = np.log(c1 / c2)
                if len(log_ratio) < Z_LOOKBACK:
                    continue
                roll_mean = log_ratio.rolling(Z_LOOKBACK).mean()
                roll_std = log_ratio.rolling(Z_LOOKBACK).std()
                z_now = (log_ratio.iloc[-1] - roll_mean.iloc[-1]) / roll_std.iloc[-1] if roll_std.iloc[-1] > 0 else 0

                entry_sym = None
                direction = None

                if z_now < -Z_ENTRY:
                    entry_sym = s1  # A is cheap, long A
                    direction = "A"
                elif z_now > Z_ENTRY:
                    entry_sym = s2  # B is cheap, long B
                    direction = "B"

                if entry_sym is None:
                    continue

                # ── Trade filters ──
                td_str_check = td_str

                # Filter: ST
                if td_str_check in is_st_raw.index and entry_sym in is_st_raw.columns:
                    if is_st_raw.at[td_str_check, entry_sym]:
                        continue

                # Filter: T suspended
                if td_str_check in suspended_raw.index and entry_sym in suspended_raw.columns:
                    if suspended_raw.at[td_str_check, entry_sym]:
                        continue

                # Filter: T limit up (can't expect to buy)
                if td_str_check in close_raw.index and td_str_check in limit_up_raw.index:
                    if entry_sym in close_raw.columns and entry_sym in limit_up_raw.columns:
                        close_t = close_raw.at[td_str_check, entry_sym]
                        lu_t = limit_up_raw.at[td_str_check, entry_sym]
                        if pd.notna(close_t) and pd.notna(lu_t) and lu_t > 0:
                            if close_t >= lu_t - 1e-6:
                                continue

                # Filter: T+1 suspended
                if t1_str in suspended_raw.index and entry_sym in suspended_raw.columns:
                    if suspended_raw.at[t1_str, entry_sym]:
                        continue

                # Filter: T+1 limit up (can't buy)
                if t1_str in limit_up_raw.index and entry_sym in limit_up_raw.columns:
                    t1_open = open_raw.at[t1_str, entry_sym] if t1_str in open_raw.index and entry_sym in open_raw.columns else np.nan
                    t1_lu = limit_up_raw.at[t1_str, entry_sym]
                    if pd.notna(t1_open) and pd.notna(t1_lu) and t1_lu > 0:
                        if t1_open >= t1_lu - 1e-6:
                            continue

                # Get entry price at T+1 open
                entry_price = open_raw.at[t1_str, entry_sym] if t1_str in open_raw.index and entry_sym in open_raw.columns else np.nan

                if pd.isna(entry_price) or entry_price <= 0:
                    continue

                # Filter: liquidity (avg amount in formation)
                sym_amt = amount_raw[entry_sym].loc[form_start:form_end_dt].dropna()
                if len(sym_amt) == 0 or sym_amt.mean() < MIN_AVG_AMOUNT:
                    continue

                # Enter position
                position_state[pair_key] = {
                    "entry_date": t1,
                    "direction": direction,
                    "entry_price": entry_price,
                    "sym": entry_sym,
                }

    # Close any remaining positions at end of trading window
    for pair_key, pos in list(position_state.items()):
        last_date = trade_dates[-1]
        last_date_str = last_date.strftime("%Y-%m-%d")
        if last_date_str in close_raw.index and pos["sym"] in close_raw.columns:
            exit_price = close_raw.at[last_date_str, pos["sym"]]
            if pd.notna(exit_price) and pos["entry_price"] > 0:
                ret = exit_price / pos["entry_price"] - 1
                entry_hs = idx_close.get(pos["entry_date"].strftime("%Y-%m-%d"), np.nan)
                exit_hs = idx_close.get(last_date_str, np.nan)
                hs_ret = exit_hs / entry_hs - 1 if pd.notna(entry_hs) and pd.notna(exit_hs) and entry_hs > 0 else np.nan

                s1, s2 = pair_key
                pair_obj = next((p for p in period_pairs if (p["sym_a"] == s1 and p["sym_b"] == s2) or (p["sym_a"] == s2 and p["sym_b"] == s1)), None)

                all_trades.append({
                    "period": rb_str,
                    "pair": f"{s1}/{s2}",
                    "sym_a": s1, "sym_b": s2,
                    "direction": pos["direction"],
                    "entry_date": pos["entry_date"].strftime("%Y-%m-%d"),
                    "exit_date": last_date_str,
                    "entry_price": pos["entry_price"],
                    "exit_price": exit_price,
                    "return": ret,
                    "hs300_return": hs_ret,
                    "excess_return": ret - hs_ret if pd.notna(hs_ret) else np.nan,
                    "hold_days": (last_date - pos["entry_date"]).days,
                    "exit_reason": "period_end",
                    "correlation": pair_obj["correlation"] if pair_obj else 0,
                })

        del position_state[pair_key]

    period_stats.append({
        "period": rb_str,
        "form_start": form_start.strftime("%Y-%m-%d"),
        "form_end": form_end_dt.strftime("%Y-%m-%d"),
        "trade_start": rb_str,
        "trade_end": trade_end.strftime("%Y-%m-%d"),
        "n_stocks": len(valid_cols),
        "n_pairs": len(period_pairs),
        "n_trades": sum(1 for t in all_trades if t["period"] == rb_str),
    })

# ── Results ──
trades_df = pd.DataFrame(all_trades)
periods_df = pd.DataFrame(period_stats)

print(f"\n=== WALK-FORWARD SUMMARY ===")
print(f"Periods: {len(periods_df)}")
print(f"Total trades: {len(trades_df)}")

if len(trades_df) == 0:
    print("NO TRADES GENERATED. Check parameters.")
    sys.exit(1)

# ── Per-period stats ──
print(f"\n--- Per-Period Pair Counts ---")
for _, row in periods_df.iterrows():
    print(f"  {row['period']}: {row['n_stocks']} stocks, {row['n_pairs']} pairs, {row['n_trades']} trades")

# ── Trade statistics ──
print(f"\n--- Trade Statistics ---")
trades_df["return_pct"] = trades_df["return"] * 100
trades_df["excess_pct"] = trades_df["excess_return"] * 100
trades_df["year"] = pd.to_datetime(trades_df["entry_date"]).dt.year

win_rate = (trades_df["return"] > 0).mean()
win_rate_excess = (trades_df["excess_return"] > 0).mean()
mean_ret = trades_df["return"].mean()
mean_excess = trades_df["excess_return"].mean()
median_excess = trades_df["excess_return"].median()
mean_hold = trades_df["hold_days"].mean()
median_hold = trades_df["hold_days"].median()

print(f"Win rate (raw): {win_rate:.1%}")
print(f"Win rate (excess): {win_rate_excess:.1%}")
print(f"Mean return: {mean_ret:.4%}")
print(f"Mean excess: {mean_excess:.4%}")
print(f"Median excess: {median_excess:.4%}")
print(f"Mean hold days: {mean_hold:.1f}")
print(f"Median hold days: {median_hold:.1f}")

# Exit reason breakdown
print(f"\n--- Exit Reason Breakdown ---")
exit_counts = trades_df["exit_reason"].value_counts()
for reason, count in exit_counts.items():
    print(f"  {reason}: {count} ({count/len(trades_df):.1%})")

# ── Year-by-year ──
print(f"\n--- Year-by-Year Excess Return ---")
for yr in sorted(trades_df["year"].unique()):
    yr_trades = trades_df[trades_df["year"] == yr]
    if len(yr_trades) < 5:
        continue
    print(f"  {int(yr)}: n={len(yr_trades)}, mean_excess={yr_trades['excess_return'].mean():.4%}, "
          f"win_rate={ (yr_trades['excess_return'] > 0).mean():.1%}")

# ── Direction split ──
print(f"\n--- Long A vs Long B ---")
for d in ["A", "B"]:
    sub = trades_df[trades_df["direction"] == d]
    if len(sub) > 0:
        print(f"  Long {d}: n={len(sub)}, mean_excess={sub['excess_return'].mean():.4%}, "
              f"win_rate={(sub['excess_return'] > 0).mean():.1%}")

# ── Regime separation ──
print(f"\n--- Regime Separation ---")
# Approximate: 2022 = bear, 2023 = mixed, 2024(first 8mo) = bear/sideways, 2024(last 4mo) = bull, 2025-26 = bull
regimes = {
    "2022 Bear": ("2022-01-01", "2022-12-31"),
    "2023 Mixed": ("2023-01-01", "2023-12-31"),
    "2024 Pre-924": ("2024-01-01", "2024-09-23"),
    "2024 Post-924": ("2024-09-24", "2024-12-31"),
    "2025-26 Bull": ("2025-01-01", "2026-05-15"),
}
for regime_name, (start, end) in regimes.items():
    sub = trades_df[(trades_df["entry_date"] >= start) & (trades_df["entry_date"] <= end)]
    if len(sub) >= 5:
        print(f"  {regime_name}: n={len(sub)}, mean_excess={sub['excess_return'].mean():.4%}, "
              f"win_rate={(sub['excess_return'] > 0).mean():.1%}, mean_raw={sub['return'].mean():.4%}")

# ── Cost-adjusted ──
cost_bps = 0.003  # 30bps round-trip
trades_df["return_after_cost"] = trades_df["return"] - cost_bps
trades_df["excess_after_cost"] = trades_df["excess_return"] - cost_bps
print(f"\n--- After Cost (30bps) ---")
print(f"Mean excess after cost: {trades_df['excess_after_cost'].mean():.4%}")
print(f"Win rate after cost: {(trades_df['excess_after_cost'] > 0).mean():.1%}")

# ── Concentration ──
print(f"\n--- Pair Concentration ---")
pair_counts = trades_df.groupby("pair").size().sort_values(ascending=False)
top5_pct = pair_counts.head(5).sum() / len(trades_df)
top10_pct = pair_counts.head(10).sum() / len(trades_df)
print(f"Top 5 pairs: {top5_pct:.1%} of trades")
print(f"Top 10 pairs: {top10_pct:.1%} of trades")
print(f"Unique pairs traded: {trades_df['pair'].nunique()}")

# ── Pass/Fail assessment ──
print(f"\n=== PASS/FAIL ASSESSMENT ===")
checks = []

# Check 1: >= 50 pairs per period on average
avg_pairs = periods_df["n_pairs"].mean()
checks.append((">=50 pairs/period", avg_pairs >= 50, f"{avg_pairs:.0f}"))

# Check 2: 3/5 years positive excess
yr_excess = trades_df.groupby("year")["excess_return"].mean()
yrs_positive = (yr_excess > 0).sum()
yrs_total = len(yr_excess)
checks.append((">=3/5 yrs excess>0", yrs_positive >= 3, f"{yrs_positive}/{yrs_total}"))

# Check 3: 2022 bear excess not negative
yr_2022 = yr_excess.get(2022, -1)
checks.append(("2022 excess not negative", yr_2022 > 0, f"{yr_2022:.4%}"))

# Check 4: Win rate > 52%
checks.append(("Win rate > 52% (excess)", win_rate_excess > 0.52, f"{win_rate_excess:.1%}"))

# Check 5: Mean excess > 0 after cost
checks.append(("Mean excess > 0 after cost", trades_df["excess_after_cost"].mean() > 0, f"{trades_df['excess_after_cost'].mean():.4%}"))

# Check 6: Avg hold <= 30 days
checks.append(("Avg hold <= 30d", mean_hold <= 30, f"{mean_hold:.1f}d"))

# Check 7: Top 5 pairs < 30% of trades
checks.append(("Top5 pairs < 30%", top5_pct < 0.30, f"{top5_pct:.1%}"))

# Check 8: 2024 doesn't dominate
yr_2024 = trades_df[trades_df["year"] == 2024]
pct_2024 = len(yr_2024) / len(trades_df) if len(trades_df) > 0 else 0
excess_2024 = yr_2024["excess_return"].mean() if len(yr_2024) > 0 else 0
non_2024 = trades_df[trades_df["year"] != 2024]
excess_non2024 = non_2024["excess_return"].mean() if len(non_2024) > 0 else 0
checks.append(("Non-2024 excess still positive", excess_non2024 > 0, f"{excess_non2024:.4%}"))

n_pass = sum(1 for _, p, _ in checks if p)
for name, passed, value in checks:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {name}: {value}")

if n_pass >= 7:
    verdict = "A"
elif n_pass >= 5:
    verdict = "B"
else:
    verdict = "C"

print(f"\n=== VERDICT: {verdict} ===")
print(f"Passed {n_pass}/{len(checks)} checks")
if verdict == "A":
    print("PASS — can enter A1 offline signal validation")
elif verdict == "B":
    print("MARGINAL — needs industry classification fix or pair formation rule adjustment")
else:
    print("FAIL — pivot to B Industry Rotation")

# ── Save ──
trades_df.to_csv(ROOT / "data/pair_walkforward_trades.csv", index=False)
periods_df.to_csv(ROOT / "data/pair_walkforward_periods.csv", index=False)
print(f"\nSaved trades ({len(trades_df)}) and periods ({len(periods_df)})")
print("Done.")

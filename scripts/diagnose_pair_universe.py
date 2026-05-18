"""A0: Pair universe feasibility audit — mean reversion + long-only diagnostics."""
import json, sys, warnings
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path(__file__).resolve().parent.parent
warnings.filterwarnings("ignore")

# ── Load HS300 constituents ──
with open(ROOT / "data/historical_constituents.json", encoding="utf-8") as f:
    d = json.load(f)
q = d["indices"]["HS300"]["quarterly"]
latest_k = sorted(q.keys())[-1]
hs300_syms = sorted(set(q[latest_k]))
print(f"HS300 constituents: {len(hs300_syms)}")

# ── Load bars ──
bars = pd.read_parquet(ROOT / "data/raw/HS300_daily.parquet")
bars["trade_date"] = pd.to_datetime(bars["trade_date"])
bars = bars[(bars["trade_date"] >= "2022-01-01") & (bars["trade_date"] <= "2026-05-15")]
bars = bars[bars["symbol"].isin(hs300_syms)]
print(f"Bars: {len(bars)} rows, {bars['symbol'].nunique()} symbols")

close = bars.pivot(index="trade_date", columns="symbol", values="close")
amount = bars.pivot(index="trade_date", columns="symbol", values="amount")
rets = close.pct_change().dropna(how="all")
min_obs = 500
valid_cols = rets.columns[rets.count() >= min_obs]
rets = rets[valid_cols]
close = close[valid_cols]
amount = amount[valid_cols]
print(f"Valid stocks: {len(valid_cols)} (>= {min_obs} return days)")

# ── Industry map (partial due to API limits) ──
try:
    with open(ROOT / "data/pair_industry_map.json", encoding="utf-8") as f:
        ind_data = json.load(f)
    ind_lookup = ind_data.get("stock_industries", {})
    # Filter to API errors
    ind_ok = {k: v for k, v in ind_lookup.items() if "ERROR" not in str(v) and v != "UNKNOWN"}
    print(f"Industry map: {len(ind_ok)} classified, {len(ind_lookup) - len(ind_ok)} unknown/error")
except Exception:
    ind_lookup = {}
    ind_ok = {}
    print("No industry map available")

# ── Pairwise correlation ──
print("Computing pairwise correlations...")
corr = rets.corr()
print(f"Correlation matrix: {corr.shape}")

# ── Form pairs ──
corr_thresholds = [0.6, 0.7, 0.8]
pair_counts = {}
for thresh in corr_thresholds:
    count = 0
    for i in range(len(corr.columns)):
        for j in range(i + 1, len(corr.columns)):
            if corr.iloc[i, j] >= thresh:
                count += 1
    pair_counts[thresh] = count
print(f"\nPairs per threshold: {pair_counts}")

# Use 0.7 as working threshold
pairs = []
for i in range(len(corr.columns)):
    for j in range(i + 1, len(corr.columns)):
        r = corr.iloc[i, j]
        if r >= 0.7:
            s1, s2 = corr.columns[i], corr.columns[j]
            # Industry check
            i1 = ind_lookup.get(s1, "UNKNOWN")
            i2 = ind_lookup.get(s2, "UNKNOWN")
            same_ind = (i1 == i2) and ("ERROR" not in str(i1)) and (i1 != "UNKNOWN")
            # Liquidity: avg daily amount
            amt1 = amount[s1].dropna().mean() if s1 in amount.columns else 0
            amt2 = amount[s2].dropna().mean() if s2 in amount.columns else 0
            pairs.append({
                "sym_a": s1, "sym_b": s2, "correlation": r,
                "same_industry": same_ind,
                "ind_a": i1, "ind_b": i2,
                "avg_amount_a": float(amt1), "avg_amount_b": float(amt2),
            })

pairs_df = pd.DataFrame(pairs).sort_values("correlation", ascending=False).reset_index(drop=True)
print(f"Pairs with corr >= 0.7: {len(pairs_df)}")

# Industry breakdown
same_ind_n = pairs_df["same_industry"].sum()
print(f"Same-industry pairs: {same_ind_n}/{len(pairs_df)}")

# ── Mean reversion diagnostics (top 50 pairs) ──
print("\n=== MEAN REVERSION DIAGNOSTICS (top 50 pairs) ===")

# HS300 index
idx_bars = pd.read_parquet(ROOT / "data/raw/index/sh000300_daily.parquet")
idx_bars["trade_date"] = pd.to_datetime(idx_bars["trade_date"])
idx_close = idx_bars.set_index("trade_date")["close"]
idx_close = idx_close[idx_close.index.isin(close.index)]

top50 = pairs_df.head(50)
pair_stats = []

for idx, row in top50.iterrows():
    s1, s2 = row["sym_a"], row["sym_b"]
    c1 = close[s1].dropna()
    c2 = close[s2].dropna()
    common_idx = c1.index.intersection(c2.index)
    c1 = c1[common_idx]
    c2 = c2[common_idx]
    if len(common_idx) < 250:
        continue

    # Log ratio and z-score
    log_ratio = np.log(c1 / c2)
    roll_mean = log_ratio.rolling(120).mean()
    roll_std = log_ratio.rolling(120).std()
    z_score = (log_ratio - roll_mean) / roll_std
    valid_z = z_score.dropna()

    # Half-life of mean reversion (OU process approx)
    # Regression: delta_ratio_t = a + b * ratio_t-1 + e
    delta = log_ratio.diff().dropna()
    lag = log_ratio.shift(1).dropna()
    common = delta.index.intersection(lag.index)
    if len(common) > 100:
        from numpy import polyfit
        b = polyfit(lag[common].values, delta[common].values, 1)[0]
        half_life = -np.log(2) / b if b < 0 else np.inf
        half_life = min(half_life, 500)  # cap
    else:
        half_life = np.inf

    # Trigger counts
    high_trig = (valid_z > 2).sum()
    low_trig = (valid_z < -2).sum()

    # Reversion analysis (label-based)
    reversion_events = []
    all_dates = valid_z.index.tolist()
    for date in valid_z[valid_z.abs() > 2].index:
        try:
            d_pos = all_dates.index(date)
            forward_dates = all_dates[d_pos : d_pos + 60]
            if len(forward_dates) < 2:
                continue
            forward = valid_z.loc[forward_dates]
            trigger_sign = "high" if valid_z.loc[date] > 2 else "low"
            returned = (forward.abs() < 0.5).any()
            if returned:
                ret_date = forward[forward.abs() < 0.5].index[0]
                days_n = all_dates.index(ret_date) - d_pos
            else:
                days_n = 60
            reversion_events.append({
                "trigger": trigger_sign, "returned": returned, "days": min(days_n, 60),
            })
        except Exception:
            pass

    rev_df = pd.DataFrame(reversion_events) if reversion_events else pd.DataFrame()

    # Long-only returns: buy when z<-2 (A cheap), or z>2 (B cheap)
    # Use label-based indexing to avoid positional mismatch
    long_rets = {"A": defaultdict(list), "B": defaultdict(list)}
    for date in valid_z[valid_z < -2].index:
        entry_p = c1.get(date, np.nan)
        if pd.isna(entry_p) or entry_p <= 0:
            continue
        for h in [5, 10, 20]:
            future_dates = close.index[close.index > date]
            if len(future_dates) >= h:
                exit_date = future_dates[h - 1]
                exit_p = close.at[exit_date, s1] if s1 in close.columns else np.nan
                if pd.notna(exit_p):
                    long_rets["A"][h].append(exit_p / entry_p - 1)

    for date in valid_z[valid_z > 2].index:
        entry_p = c2.get(date, np.nan)
        if pd.isna(entry_p) or entry_p <= 0:
            continue
        for h in [5, 10, 20]:
            future_dates = close.index[close.index > date]
            if len(future_dates) >= h:
                exit_date = future_dates[h - 1]
                exit_p = close.at[exit_date, s2] if s2 in close.columns else np.nan
                if pd.notna(exit_p):
                    long_rets["B"][h].append(exit_p / entry_p - 1)

    # HS300 comparison (label-based)
    hs300_rets = defaultdict(list)
    for date in valid_z[valid_z.abs() > 2].index:
        entry = idx_close.get(date, np.nan)
        if pd.isna(entry) or entry <= 0:
            continue
        for h in [5, 10, 20]:
            future_dates = idx_close.index[idx_close.index > date]
            if len(future_dates) >= h:
                exit_v = idx_close.at[future_dates[h - 1]]
                if pd.notna(exit_v):
                    hs300_rets[h].append(exit_v / entry - 1)

    stat = {
        "pair": f"{s1}/{s2}",
        "sym_a": s1, "sym_b": s2,
        "correlation": row["correlation"],
        "n_days": len(common_idx),
        "half_life": float(half_life) if half_life < 500 else None,
        "z_gt_2": int(high_trig),
        "z_lt_minus2": int(low_trig),
        "total_triggers": int(high_trig + low_trig),
    }

    if len(rev_df) > 0:
        stat["reversion_rate"] = float(rev_df["returned"].mean())
        returned_sub = rev_df[rev_df["returned"]]
        stat["avg_reversion_days"] = float(returned_sub["days"].mean()) if len(returned_sub) > 0 else 60
    else:
        stat["reversion_rate"] = 0.0
        stat["avg_reversion_days"] = 60.0

    for side in ["A", "B"]:
        for h in [5, 10, 20]:
            vals = long_rets[side][h]
            stat[f"long_{side}_{h}d_mean"] = float(np.mean(vals)) if vals else None
            stat[f"long_{side}_{h}d_n"] = len(vals)

    for h in [5, 10, 20]:
        vals = hs300_rets[h]
        stat[f"hs300_{h}d_mean"] = float(np.mean(vals)) if vals else None

    pair_stats.append(stat)

stats_df = pd.DataFrame(pair_stats)
print(f"Pairs analyzed: {len(stats_df)}")

# Summary
print(f"\n--- SUMMARY ---")
print(f"Avg correlation: {stats_df['correlation'].mean():.3f}")
print(f"Avg triggers per pair: {stats_df['total_triggers'].mean():.1f}")
has_trig = stats_df[stats_df["total_triggers"] > 0]
print(f"Pairs with any trigger: {len(has_trig)}/{len(stats_df)}")
print(f"Avg reversion rate: {stats_df['reversion_rate'].mean():.1%}")
print(f"Avg reversion days: {stats_df['avg_reversion_days'].mean():.1f}")

for h in [5, 10, 20]:
    a_vals = stats_df[f"long_A_{h}d_mean"].dropna()
    b_vals = stats_df[f"long_B_{h}d_mean"].dropna()
    hs_vals = stats_df[f"hs300_{h}d_mean"].dropna()
    print(f"\n--- {h}d hold ---")
    print(f"  Long A: mean={a_vals.mean():.4%}, median={a_vals.median():.4%}, n_pairs={len(a_vals)}")
    print(f"  Long B: mean={b_vals.mean():.4%}, median={b_vals.median():.4%}, n_pairs={len(b_vals)}")
    print(f"  HS300:  mean={hs_vals.mean():.4%}")

# Aggregate all A/B trades for t-test
all_a_10 = []
all_b_10 = []
all_hs_10 = []
for stat in pair_stats:
    if stat.get("long_A_10d_n", 0) > 0:
        all_a_10.append(stat["long_A_10d_mean"])
    if stat.get("long_B_10d_n", 0) > 0:
        all_b_10.append(stat["long_B_10d_mean"])
    if stat.get("hs300_10d_mean") is not None:
        all_hs_10.append(stat["hs300_10d_mean"])

if all_a_10:
    print(f"\n--- Combined Long-Only (10d) ---")
    print(f"  Long A+B: mean={np.mean(all_a_10 + all_b_10):.4%}")
    print(f"  vs HS300:  mean={np.mean(all_hs_10):.4%}")
    print(f"  Excess over HS300: {np.mean(all_a_10 + all_b_10) - np.mean(all_hs_10):.4%}")

# Half-life stats
hl_vals = stats_df["half_life"].dropna()
print(f"\n--- Half-Life ---")
print(f"  Pairs with valid half-life: {len(hl_vals)}/{len(stats_df)}")
if len(hl_vals) > 0:
    print(f"  Median half-life: {hl_vals.median():.1f} days")
    print(f"  P25/P75: {hl_vals.quantile(0.25):.1f} / {hl_vals.quantile(0.75):.1f}")

# Top pairs by reversion rate
print(f"\n--- TOP 15 BY REVERSION RATE ---")
top_rev = stats_df[stats_df["total_triggers"] >= 5].nlargest(15, "reversion_rate")
for _, row in top_rev.iterrows():
    la10 = f"{row['long_A_10d_mean']:.3%}" if pd.notna(row.get('long_A_10d_mean')) else "N/A"
    lb10 = f"{row['long_B_10d_mean']:.3%}" if pd.notna(row.get('long_B_10d_mean')) else "N/A"
    print(f"  {row['pair']}: rev={row['reversion_rate']:.0%}, "
          f"days={row['avg_reversion_days']:.0f}, trig={int(row['total_triggers'])}, "
          f"longA10={la10}, longB10={lb10}")

stats_df.to_csv(ROOT / "data/pair_diagnostics_top50.csv", index=False)
print(f"\nSaved to data/pair_diagnostics_top50.csv")
print("Done.")

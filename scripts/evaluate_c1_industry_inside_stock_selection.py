"""C1 — Industry-Inside Stock Selection Evaluation.

Evaluates within-industry stock-level alpha by computing stock momentum
relative to industry peers (C1-A signal), then selecting Top-N stocks
across all industries with equal-weight holding.

Phases:
  Phase 1a: Variance decomposition — cross-sectional regression of stock
            returns on industry dummies. Diagnostic only, not a blocking gate.
  Phase 1b: C1-A Top-20 and Top-10 evaluation with full gate suite.

Usage:
  python scripts/evaluate_c1_industry_inside_stock_selection.py --smoke  # 2024 only, Top-20
  python scripts/evaluate_c1_industry_inside_stock_selection.py           # full run

Known limitations (documented in output):
  1. Industry classification is 2026-05-18 snapshot — look-ahead bias for historical periods.
  2. Constituent data has survivorship bias (~5-10% annual turnover not captured).
  3. pre_close is mostly null — limit checks use limit_up / limit_down columns.
  4. is_st / is_suspended fields barely populated — ST check uses symbol name,
     suspended check uses volume == 0.
  5. Benchmark uses close-to-close HS300 EW while portfolio uses open-to-open —
     minor timing mismatch documented.
"""

from __future__ import annotations

import json
import sys
import warnings
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

ROOT = Path(__file__).resolve().parent.parent
BAR_PATH = ROOT / "data/raw/HS300_daily.parquet"
CAL_PATH = ROOT / "data/raw/calendar.parquet"
IDX_PATH = ROOT / "data/raw/index/sh000300_daily.parquet"
CONST_PATH = ROOT / "data/historical_constituents.json"
IND_PATH = ROOT / "data/meta/industry_classification.csv"

# --- Config ---
COST_BPS = 0.0020      # 20 bps/month
LOOKBACK = 60           # trading days for stock/industry momentum
MIN_STK = 3             # minimum stocks per industry (base)
TOP_N_LIST = [20, 10]   # Top-20 and Top-10 selection
B1_BASELINE_RC = 0.63   # B1 cap_20 EW+AWH baseline

SPLITS = [
    ("Ex-2025",     "2022-01-01", "2024-12-31"),
    ("2024 only",   "2024-01-01", "2024-12-31"),
    ("2025-2026",   "2025-01-01", "2026-05-15"),
    ("full",         "2022-01-01", "2026-05-15"),
]

# --- Data Loading ---

def load_constituent_map():
    """Load quarterly HS300 constituent snapshots into {quarter_date: [symbols]}."""
    with open(CONST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    raw = data["indices"]["HS300"]["quarterly"]
    return {k: sorted(set(v)) for k, v in raw.items()}


def get_constituents(date_str, const_map):
    """Get HS300 constituent symbols for a given date (most recent quarter)."""
    sorted_dates = sorted(const_map.keys())
    for q_date in reversed(sorted_dates):
        if q_date <= date_str:
            return const_map[q_date]
    return const_map[sorted_dates[0]] if sorted_dates else []


def load_industry_map():
    """Return {symbol_str: industry_name} mapping. Symbols zero-padded to 6 digits."""
    df = pd.read_csv(IND_PATH)
    df["symbol_str"] = df["symbol"].apply(lambda x: str(int(x)).zfill(6))
    return dict(zip(df["symbol_str"], df["industry_raw"]))


# --- Calendar Utilities ---

def get_month_ends(trading_dates):
    """Return last trading day of each month from the trading calendar."""
    df = pd.DataFrame({"d": pd.to_datetime(trading_dates)})
    df["ym"] = df["d"].dt.to_period("M")
    return sorted(df.groupby("ym")["d"].max().dt.strftime("%Y-%m-%d").tolist())


def get_next_trading_day(date_str, trading_dates):
    """Return the first trading day strictly after date_str, or None."""
    for d in trading_dates:
        if d > date_str:
            return d
    return None


def get_prev_trading_day(date_str, trading_dates):
    """Return the last trading day strictly before date_str, or None."""
    result = None
    for d in trading_dates:
        if d >= date_str:
            break
        result = d
    return result


def find_date_in_series(target_date, series_index, trading_dates, direction="backward"):
    """Find nearest trading date <= or >= target_date in the series index."""
    if target_date in series_index:
        return target_date
    if direction == "backward":
        for d in reversed([x for x in trading_dates if x <= target_date]):
            if d in series_index:
                return d
    else:
        for d in [x for x in trading_dates if x >= target_date]:
            if d in series_index:
                return d
    return None


# --- Benchmark ---

def compute_hs300_ew(bars, const_map, trading_dates):
    """Compute HS300 equal-weight daily cumulative return series.

    Returns a Series indexed by trade_date with cumulative return (starting at 1.0).
    Uses pre-indexed data and constituent-date lookup for efficiency.
    """
    bars = bars.copy()
    bars["td"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "td"])
    bars["ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["ret"])

    # Only keep dates that appear in bars (not all 1900+ calendar dates)
    bar_dates = sorted(set(bars["td"].unique()) & set(trading_dates))
    if not bar_dates:
        return pd.Series(dtype=float)

    # Precompute constituent lookup for all needed dates
    date_const = {}
    for d in bar_dates:
        date_const[d] = set(get_constituents(d, const_map))

    r = {}
    bars_by_date = bars.set_index("td")
    for d in bar_dates:
        const_syms = date_const.get(d, set())
        if not const_syms:
            continue
        day = bars_by_date.loc[d] if d in bars_by_date.index else pd.DataFrame()
        if isinstance(day, pd.Series):
            day = day.to_frame().T
        if len(day) == 0:
            continue
        in_const = day[day["symbol"].isin(const_syms)]
        if len(in_const) > 0:
            r[d] = in_const["ret"].mean()

    s = pd.Series(r).sort_index().dropna()
    if len(s) == 0:
        return pd.Series(dtype=float)
    return (1 + s).cumprod()


# --- Phase 1a: Variance Decomposition ---

def _daily_variance_decomposition(day_data, im, const_map, date_str):
    """Cross-sectional regression of stock returns on industry dummies for one day.

    Returns R-squared or None if insufficient data.
    """
    const_syms = set(get_constituents(date_str, const_map))
    day_data = day_data[day_data["symbol"].isin(const_syms)]

    if len(day_data) < 30:
        return None

    day_data = day_data.copy()
    day_data["industry"] = day_data["symbol"].map(im)
    day_data = day_data.dropna(subset=["industry"])

    ind_counts = day_data.groupby("industry").size()
    valid_inds = ind_counts[ind_counts >= 2].index
    day_data = day_data[day_data["industry"].isin(valid_inds)]

    if len(day_data) < 30 or day_data["industry"].nunique() < 3:
        return None

    dummies = pd.get_dummies(day_data["industry"], drop_first=True).astype(float)
    n_stocks = len(dummies)
    n_industries = dummies.shape[1]

    if n_industries < 2 or n_stocks < n_industries + 10:
        return None

    X = np.column_stack([np.ones(n_stocks), dummies.values])
    y = day_data.set_index(dummies.index)["ret"].values

    try:
        xtx = X.T @ X
        xty = X.T @ y
        beta = np.linalg.lstsq(xtx, xty, rcond=None)[0]
        y_pred = X @ beta
        ss_res = np.sum((y - y_pred) ** 2)
        ss_tot = np.sum((y - np.mean(y)) ** 2)
        if ss_tot > 1e-12:
            r2 = 1 - ss_res / ss_tot
            return max(min(r2, 1.0), 0.0)
    except (np.linalg.LinAlgError, ValueError):
        return None

    return None


def run_variance_decomposition(bars, cm, im, trading_dates, sample_every=5):
    """Phase 1a: Cross-sectional variance decomposition.

    On every Nth trading day, regress stock returns on industry dummies.
    Returns dict with R-squared statistics and interpretation tier.
    """
    print("\n--- Phase 1a: Variance Decomposition ---")

    bars = bars.copy()
    bars["td"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "td"])
    bars["ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["ret"])

    eval_dates = [d for d in trading_dates if "2022-01-01" <= d <= "2026-05-15"]
    sampled_dates = eval_dates[::sample_every]

    print(f"  Evaluating {len(sampled_dates)} sampled days "
          f"(every {sample_every}th trading day)...")

    r2_values = []
    r2_by_year = {}

    for i, ds in enumerate(sampled_dates):
        if (i + 1) % 50 == 0:
            print(f"    {i + 1}/{len(sampled_dates)} days processed...")

        day_data = bars[bars["td"] == ds]
        if len(day_data) < 30:
            continue

        r2 = _daily_variance_decomposition(day_data, im, cm, ds)
        if r2 is not None:
            r2_values.append(r2)
            yr = ds[:4]
            r2_by_year.setdefault(yr, []).append(r2)

    if not r2_values:
        print("  WARNING: No valid R-squared values computed.")
        return {"mean_r2": None, "by_year": {}, "tier": "unknown",
                "n_days": 0, "n_years": 0}

    mean_r2 = np.mean(r2_values)
    print(f"  Overall mean R-squared: {mean_r2:.1%}")
    print(f"  Valid days: {len(r2_values)}")
    print()

    print(f"  {'Year':<8} {'Mean R2':>10} {'Median R2':>10} {'N Days':>8}")
    print(f"  {'-'*40}")
    for yr in sorted(r2_by_year.keys()):
        vals = r2_by_year[yr]
        print(f"  {yr:<8} {np.mean(vals):>10.1%} {np.median(vals):>10.1%} {len(vals):>8}")

    if mean_r2 < 0.30:
        tier = "good -- stock-specific dominates, C1 has room"
    elif mean_r2 <= 0.60:
        tier = "moderate -- C1 still valid but reduced expectation"
    else:
        tier = "limited -- industry dominates, within-industry alpha space constrained"

    print(f"\n  Interpretation: {tier}")
    print(f"  (Not a blocking gate -- Phase 1b proceeds regardless.)")

    return {"mean_r2": mean_r2, "by_year": r2_by_year, "tier": tier,
            "n_days": len(r2_values), "n_years": len(r2_by_year)}


# --- Filters ---

def filter_stocks_at_date(bars, cm, im, date_str, trading_dates, min_stk=MIN_STK,
                          lookback=LOOKBACK):
    """Filter stocks at a given date for signal computation.

    Returns tuple of (filtered_df, stats_dict).
    """
    stats = {"n_total": 0, "n_constituent": 0, "n_st": 0, "n_suspended": 0,
             "n_limit": 0, "n_listed": 0, "n_industry": 0}

    day_data = bars[bars["td"] == date_str].copy()
    stats["n_total"] = len(day_data)
    if len(day_data) == 0:
        return day_data, stats

    const_syms = set(get_constituents(date_str, cm))
    day_data = day_data[day_data["symbol"].isin(const_syms)]
    stats["n_constituent"] = len(day_data)
    if len(day_data) == 0:
        return day_data, stats

    before_len = len(day_data)
    day_data = day_data[~day_data["symbol"].str.contains("ST", na=False)]
    stats["n_st"] = before_len - len(day_data)
    before_len = len(day_data)

    day_data = day_data[day_data["volume"].notna() & (day_data["volume"] > 0)]
    stats["n_suspended"] = before_len - len(day_data)
    before_len = len(day_data)

    day_data["_at_limit_up"] = day_data["close"] >= day_data["limit_up"] * 0.995
    day_data["_at_limit_down"] = day_data["close"] <= day_data["limit_down"] * 1.005
    day_data = day_data[~day_data["_at_limit_up"] & ~day_data["_at_limit_down"]]
    stats["n_limit"] = before_len - len(day_data)
    before_len = len(day_data)

    stock_dates_before = bars[bars["td"] <= date_str].groupby("symbol").size()
    eligible_stocks = stock_dates_before[stock_dates_before >= lookback].index
    day_data = day_data[day_data["symbol"].isin(eligible_stocks)]
    stats["n_listed"] = before_len - len(day_data)

    if len(day_data) == 0:
        return day_data, stats

    day_data["ind"] = day_data["symbol"].map(im)
    day_data = day_data.dropna(subset=["ind"])

    before_len = len(day_data)
    ind_counts = day_data.groupby("ind").size()
    valid_inds = ind_counts[ind_counts >= min_stk].index
    day_data = day_data[day_data["ind"].isin(valid_inds)]
    stats["n_industry"] = before_len - len(day_data)

    return day_data, stats


# --- Signal Computation ---

def compute_c1a_signal(eligible_df):
    """Compute C1-A signal: stock_60d_mom - industry_ew_mom."""
    df = eligible_df.copy()
    ind_ew_mom = df.groupby("ind")["mom_60d"].mean()
    df["signal"] = df.apply(
        lambda row: row["mom_60d"] - ind_ew_mom.get(row["ind"], 0.0), axis=1
    )
    return df.sort_values("signal", ascending=False)



# --- Simulation ---

def simulate_c1a(bars, cm, im, trading_dates, top_n, min_stk,
                 lookback, hs300_ew):
    """Simulate C1-A Top-N stock selection with equal-weight holding.

    Returns dict with keys: monthly_excess, turnovers, metrics,
    selections, filter_stats. Returns None if < 3 valid months.
    """
    month_ends = get_month_ends(trading_dates)
    month_ends = [me for me in month_ends if me in trading_dates]

    # Precompute stock 60d momentum for all dates
    print(f"    Precomputing stock {lookback}d momentum...")
    bars_sorted = bars.sort_values(["symbol", "td"]).reset_index(drop=True)
    bars_sorted["mom_60d"] = bars_sorted.groupby("symbol")["close"].transform(
        lambda x: x.pct_change(periods=lookback)
    )

    if "ind" not in bars_sorted.columns:
        bars_sorted["ind"] = bars_sorted["symbol"].map(im)

    monthly_excess = []
    turnovers = []
    all_selections = []
    all_filter_stats = []
    prev_selection = None
    nm = 0
    skipped_entries = 0
    total_entries = 0
    skipped_dates = 0

    for i, me in enumerate(month_ends):
        if i + 1 >= len(month_ends):
            continue
        next_me = month_ends[i + 1]

        entry_date = get_next_trading_day(me, trading_dates)
        exit_date = get_next_trading_day(next_me, trading_dates)
        if entry_date is None or exit_date is None:
            skipped_dates += 1
            continue
        if entry_date not in trading_dates or exit_date not in trading_dates:
            skipped_dates += 1
            continue
        if entry_date not in bars_sorted["td"].values:
            skipped_dates += 1
            continue

        # --- Filter at month-end T ---
        eligible, fstats = filter_stocks_at_date(
            bars_sorted, cm, im, me, trading_dates, min_stk, lookback)
        all_filter_stats.append({"month": me, "top_n": top_n, "min_stk": min_stk,
                                  **{k: fstats[k] for k in fstats}})

        if len(eligible) < top_n:
            skipped_dates += 1
            continue

        eligible = eligible.dropna(subset=["mom_60d"])
        if len(eligible) < top_n:
            skipped_dates += 1
            continue

        # Re-check min_stk after dropping NaN mom
        ind_counts = eligible.groupby("ind").size()
        valid_inds = ind_counts[ind_counts >= min_stk].index
        eligible = eligible[eligible["ind"].isin(valid_inds)]
        if len(eligible) < top_n:
            skipped_dates += 1
            continue

        ranked = compute_c1a_signal(eligible)
        selected = ranked.head(top_n)["symbol"].tolist()
        all_selections.append({"month": me, "stocks": selected,
                                "n_industries": ranked.head(top_n)["ind"].nunique()})

        # --- Entry / Exit ---
        total_entries += len(selected)
        entry_data = bars_sorted[bars_sorted["td"] == entry_date].set_index("symbol")
        exit_open_data = bars_sorted[bars_sorted["td"] == exit_date].set_index("symbol")

        stock_rets = []
        for sym in selected:
            if sym not in entry_data.index:
                skipped_entries += 1
                continue
            if sym not in exit_open_data.index:
                skipped_entries += 1
                continue

            entry_row = entry_data.loc[sym]
            if isinstance(entry_row, pd.DataFrame):
                entry_row = entry_row.iloc[0]

            if pd.notna(entry_row.get("open")) and pd.notna(entry_row.get("limit_up")):
                if entry_row["open"] >= entry_row["limit_up"] * 0.995:
                    skipped_entries += 1
                    continue

            exit_row = exit_open_data.loc[sym]
            if isinstance(exit_row, pd.DataFrame):
                exit_row = exit_row.iloc[0]

            entry_price = entry_row.get("open", np.nan)
            exit_price = exit_row.get("open", np.nan)

            if pd.isna(entry_price) or pd.isna(exit_price) or entry_price <= 0:
                skipped_entries += 1
                continue

            stock_ret = exit_price / entry_price - 1
            stock_rets.append(stock_ret)

        if len(stock_rets) == 0:
            skipped_dates += 1
            continue

        port_ret = np.mean(stock_rets)

        # --- Benchmark return over holding period ---
        bench_ret = 0.0
        if hs300_ew is not None and len(hs300_ew) > 0:
            pre_entry = find_date_in_series(entry_date, hs300_ew.index,
                                            trading_dates, "backward")
            prev_entry = get_prev_trading_day(entry_date, trading_dates)
            if pre_entry is None and prev_entry:
                pre_entry = find_date_in_series(prev_entry, hs300_ew.index,
                                                trading_dates, "backward")
            pre_exit = find_date_in_series(exit_date, hs300_ew.index,
                                           trading_dates, "backward")
            if pre_entry and pre_exit:
                val_entry = hs300_ew.get(pre_entry, 1.0)
                val_exit = hs300_ew.get(pre_exit, 1.0)
                if val_entry > 0:
                    bench_ret = val_exit / val_entry - 1

        excess_raw = port_ret - bench_ret

        # --- Cost ---
        if prev_selection is not None:
            overlap = len(set(selected) & set(prev_selection))
            turnover_rate = 1.0 - overlap / top_n
        else:
            turnover_rate = 1.0

        cost = COST_BPS * turnover_rate
        excess_after_cost = excess_raw - cost

        monthly_excess.append(excess_after_cost)
        turnovers.append(turnover_rate)

        prev_selection = selected
        nm += 1

    if nm < 3 or len(monthly_excess) < 3:
        return None

    # --- Compute metrics ---
    xs = pd.Series(monthly_excess, dtype=float)
    cum_xs = (1 + xs).prod() - 1
    ann_excess = (1 + cum_xs) ** (12 / max(nm, 1)) - 1 if cum_xs > -1 else -1.0

    ir = xs.mean() / xs.std() * np.sqrt(12) if xs.std() > 1e-12 else 0.0
    wr = float((xs > 0).mean())
    cs = (1 + xs).cumprod()
    max_dd = float((cs / cs.cummax() - 1).min())
    rc = ann_excess / abs(max_dd) if max_dd < 0 and ann_excess > 0 else 0.0
    avg_to = np.mean(turnovers) if turnovers else 0.0

    xs_sorted = xs.sort_values(ascending=False)
    t10_n = max(1, int(len(xs) * 0.1))
    t20_n = max(1, int(len(xs) * 0.2))
    t10_contrib = float(xs_sorted.head(t10_n).sum() / xs_sorted.sum()
                        if xs_sorted.sum() > 1e-12 else 1.0)
    t20_contrib = float(xs_sorted.head(t20_n).sum() / xs_sorted.sum()
                        if xs_sorted.sum() > 1e-12 else 1.0)

    # Single-industry and single-stock contribution
    industry_contrib = {}
    stock_contrib = {}
    for xs_val, sel_info in zip(monthly_excess, all_selections):
        n_valid = len(sel_info["stocks"])
        if n_valid == 0:
            continue
        per_stock_excess = xs_val / n_valid
        for sym in sel_info["stocks"]:
            ind = im.get(sym, "Unknown")
            industry_contrib[ind] = industry_contrib.get(ind, 0.0) + per_stock_excess
            stock_contrib[sym] = stock_contrib.get(sym, 0.0) + per_stock_excess

    total_excess = sum(monthly_excess)
    top_ind_contrib = 0.0
    top_stk_contrib = 0.0
    if abs(total_excess) > 1e-12 and industry_contrib:
        top_ind_contrib = float(max(abs(v) for v in industry_contrib.values())
                                / abs(total_excess))
    if abs(total_excess) > 1e-12 and stock_contrib:
        top_stk_contrib = float(max(abs(v) for v in stock_contrib.values())
                                / abs(total_excess))

    metrics = {
        "ann_excess": ann_excess,
        "ir": ir,
        "wr": wr,
        "max_dd": max_dd,
        "rc": rc,
        "avg_to": avg_to,
        "nm": nm,
        "t10_contrib": t10_contrib,
        "t20_contrib": t20_contrib,
        "top_ind_contrib": top_ind_contrib,
        "top_stk_contrib": top_stk_contrib,
        "skipped_dates": skipped_dates,
        "skipped_entries": skipped_entries,
        "total_entries": total_entries,
    }

    return {
        "monthly_excess": monthly_excess,
        "turnovers": turnovers,
        "metrics": metrics,
        "selections": all_selections,
        "filter_stats": all_filter_stats,
    }


# --- Gate Checking ---

def check_gates(all_results, base_min_stk=MIN_STK):
    """Check C1-A against all MUST and SHOULD gates.

    Returns dict keyed by (split, top_n, min_stk) with gate results.
    """
    gate_results = {}

    for r in all_results:
        key = (r["split"], r["top_n"], r["min_stk"])
        if key not in gate_results:
            gate_results[key] = {}

    for r in all_results:
        if r["split"] != "Ex-2025":
            continue
        m = r["metrics"]
        key = (r["split"], r["top_n"], r["min_stk"])

        r24 = next((x for x in all_results
                    if x["split"] == "2024 only"
                    and x["top_n"] == r["top_n"]
                    and x["min_stk"] == r["min_stk"]), None)
        m24_excess = r24["metrics"]["ann_excess"] if r24 else None

        gates = {}
        gates["rc >= 1.0"] = m["rc"] >= 1.0
        gates["ir > 0.3"] = m["ir"] > 0.3
        gates["wr > 0.55"] = m["wr"] > 0.55
        gates["to < 0.50"] = m["avg_to"] < 0.50
        gates["dd > -0.30"] = m["max_dd"] > -0.30
        gates["2024 excess > 0"] = m24_excess is not None and m24_excess > 0
        gates["t10_contrib < 0.80"] = m["t10_contrib"] < 0.80
        gates["after-cost excess > 0"] = m["ann_excess"] > 0
        gates["ind_contrib < 0.50"] = m["top_ind_contrib"] < 0.50   # SHOULD
        gates["stk_contrib < 0.30"] = m["top_stk_contrib"] < 0.30   # SHOULD

        gate_results[key]["gates"] = gates

    # MinStk=5 sensitivity
    for r3 in [x for x in all_results if x["min_stk"] == base_min_stk]:
        r5 = next((x for x in all_results
                   if x["split"] == r3["split"]
                   and x["top_n"] == r3["top_n"]
                   and x["min_stk"] == 5), None)
        key3 = (r3["split"], r3["top_n"], r3["min_stk"])
        if key3 not in gate_results:
            gate_results[key3] = {}
        if r5 and r3["metrics"]["rc"] > 1e-8:
            rc_decay = r5["metrics"]["rc"] / r3["metrics"]["rc"]
            gate_results[key3]["rc_decay_ms5"] = rc_decay
            gate_results[key3]["ms5_fragile"] = rc_decay < 0.5
        else:
            gate_results[key3]["rc_decay_ms5"] = None
            gate_results[key3]["ms5_fragile"] = True

    # Overall determination per variant
    for key, info in gate_results.items():
        if "gates" not in info:
            info["overall"] = "FAIL"
            continue
        g = info["gates"]
        must_keys = ["rc >= 1.0", "ir > 0.3", "wr > 0.55", "to < 0.50",
                     "dd > -0.30", "2024 excess > 0", "t10_contrib < 0.80",
                     "after-cost excess > 0"]
        must_pass = all(g.get(k, False) for k in must_keys)
        ms5_fragile = info.get("ms5_fragile", True)

        if must_pass and not ms5_fragile:
            info["overall"] = "PASS"
        elif must_pass and ms5_fragile:
            info["overall"] = "FRAGILE"
        else:
            info["overall"] = "FAIL"

    return gate_results


# --- Reliability ---

def reliability_label(result):
    """Assign reliability label based on skipped-day and skipped-entry ratios."""
    if result is None:
        return "not reliable"
    m = result["metrics"]
    total_months = m["nm"] + m["skipped_dates"]
    if total_months == 0:
        return "not reliable"
    skip_ratio = m["skipped_dates"] / total_months
    if skip_ratio == 0 and m["skipped_entries"] == 0:
        return "fully reliable"
    elif skip_ratio < 0.10:
        return "partially reliable"
    else:
        return "not reliable"


# --- Report Generation ---

def _fmt_pct(v):
    if v is None:
        return "  N/A"
    return f"{v:>6.1%}"


def _fmt_float(v, decimals=2):
    if v is None:
        return "  N/A"
    return f"{v:>{2 + decimals}.{decimals}f}"


def generate_report(var_results, all_results, gate_results, hs300_ew):
    """Generate markdown evaluation report."""
    L = []
    w = L.append

    w("# C1 -- Industry-Inside Stock Selection Evaluation")
    w(f"\n**RESEARCH OBSERVATION ONLY** -- not for trading or production use.")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"\nB1 baseline RC = {B1_BASELINE_RC} (EW+AWH Industry Momentum, Top-5 industries)")

    # --- 1. Variance Decomposition ---
    w("\n---\n## 1. Phase 1a: Variance Decomposition\n")
    if var_results.get("mean_r2") is not None:
        w(f"**Overall mean R-squared: {var_results['mean_r2']:.1%}** "
          f"(N={var_results['n_days']} days, {var_results['n_years']} years)")
        w(f"\nInterpretation: **{var_results['tier']}**")
        w(f"\nThis is a diagnostic only -- not a blocking gate.\n")

        w("| Year | Mean R2 | Median R2 | N Days |")
        w("|------|---------|-----------|--------|")
        for yr in sorted(var_results["by_year"].keys()):
            vals = var_results["by_year"][yr]
            mu = np.mean(vals)
            md = np.median(vals)
            w(f"| {yr} | {mu:.1%} | {md:.1%} | {len(vals)} |")
    else:
        w("**Variance decomposition could not be computed.** "
          "Insufficient data or all regressions failed.\n")

    # --- 2. C1-A Results ---
    w("\n---\n## 2. C1-A Evaluation: Stock-Level Relative Momentum\n")
    w("\n### Signal: stock_60d_mom - industry_ew_mom")
    w("### Selection: Top-N across all industries, equal-weight holding")
    w("### Cost: 20 bps/month applied on turnover portion\n")

    for split_name, split_start, split_end in SPLITS:
        split_results = [r for r in all_results if r["split"] == split_name]
        if not split_results:
            continue

        w(f"\n### Split: {split_name} ({split_start} to {split_end})\n")
        w("| TopN | MinStk | Ann.Excess | IR | WR | MaxDD | RC | "
          "TO | T10% | T20% | IndC | StkC | Months | Reliable |")
        w("|------|--------|------------|-----|-----|-------|-----|"
          "-----|------|------|------|------|--------|----------|")

        for r in sorted(split_results, key=lambda x: (x["top_n"], x["min_stk"])):
            m = r["metrics"]
            rel = reliability_label(r)
            w(f"| {r['top_n']} | {r['min_stk']} | {_fmt_pct(m['ann_excess'])} | "
              f"{_fmt_float(m['ir'])} | {_fmt_pct(m['wr'])} | "
              f"{_fmt_pct(m['max_dd'])} | {_fmt_float(m['rc'])} | "
              f"{_fmt_pct(m['avg_to'])} | {_fmt_pct(m['t10_contrib'])} | "
              f"{_fmt_pct(m['t20_contrib'])} | {_fmt_pct(m['top_ind_contrib'])} | "
              f"{_fmt_pct(m['top_stk_contrib'])} | {m['nm']} | {rel} |")

    # --- 3. Gate Summary ---
    w("\n---\n## 3. Gate Evaluation -- Ex-2025\n")

    must_gate_names = [
        ("rc >= 1.0", "RC >= 1.0"),
        ("ir > 0.3", "IR > 0.3"),
        ("wr > 0.55", "Win Rate > 55%"),
        ("to < 0.50", "Turnover < 50%"),
        ("dd > -0.30", "Max DD > -30%"),
        ("2024 excess > 0", "2024 Annual Excess > 0"),
        ("t10_contrib < 0.80", "T10% Contrib < 80%"),
        ("after-cost excess > 0", "After-Cost Excess > 0"),
    ]
    should_gate_names = [
        ("ind_contrib < 0.50", "Single-Ind Contrib < 50%"),
        ("stk_contrib < 0.30", "Single-Stk Contrib < 30%"),
    ]

    w("### MUST Gates\n")
    w("| Variant | " + " | ".join(name for _, name in must_gate_names) +
      " | MS5 Decay | Overall |")
    w("|---------|" + "|".join("-----" for _ in must_gate_names) +
      "|-----------|---------|")

    for key, info in sorted(gate_results.items()):
        split_name, top_n, min_stk = key
        if split_name != "Ex-2025":
            continue
        if "gates" not in info:
            continue
        g = info["gates"]

        cells = []
        for gate_key, _ in must_gate_names:
            val = g.get(gate_key, None)
            cells.append("PASS" if val else "FAIL")

        ms5_decay = info.get("rc_decay_ms5", None)
        if ms5_decay is not None:
            ms5_str = f"{ms5_decay:.2f} {'⚠️' if info.get('ms5_fragile') else 'OK'}"
        else:
            ms5_str = "N/A ⚠️"

        overall = info.get("overall", "FAIL")
        ov_str = f"**{overall}**"

        w(f"| Top{top_n} S{min_stk} | " + " | ".join(cells) +
          f" | {ms5_str} | {ov_str} |")

    w("\n### SHOULD Gates\n")
    w("| Variant | " + " | ".join(name for _, name in should_gate_names) + " |")
    w("|---------|" + "|".join("-----" for _ in should_gate_names) + "|")
    for key, info in sorted(gate_results.items()):
        split_name, top_n, min_stk = key
        if split_name != "Ex-2025":
            continue
        if "gates" not in info:
            continue
        g = info["gates"]
        cells = []
        for gate_key, _ in should_gate_names:
            val = g.get(gate_key, None)
            cells.append("PASS" if val else "FAIL")
        w(f"| Top{top_n} S{min_stk} | " + " | ".join(cells) + " |")

    # --- 4. MinStk=5 Sensitivity ---
    w("\n---\n## 4. MinStk=5 Sensitivity Analysis\n")
    w("\n| Split | TopN | RC(S3) | RC(S5) | Decay Ratio | Status |")
    w("|-------|------|--------|--------|-------------|--------|")

    for r3 in sorted(all_results, key=lambda x: (x["split"], x["top_n"])):
        if r3["min_stk"] != MIN_STK:
            continue
        r5 = next((x for x in all_results
                   if x["split"] == r3["split"]
                   and x["top_n"] == r3["top_n"]
                   and x["min_stk"] == 5), None)
        if r5:
            rc3 = r3["metrics"]["rc"]
            rc5 = r5["metrics"]["rc"]
            if rc3 > 1e-8:
                decay = rc5 / rc3
                status = "FRAGILE" if decay < 0.5 else "STABLE"
            else:
                decay = 0.0
                status = "N/A"
            w(f"| {r3['split']} | {r3['top_n']} | {rc3:.2f} | {rc5:.2f} | "
              f"{decay:.2f} | {status} |")

    # --- 5. Comparison vs B1 ---
    w("\n---\n## 5. Comparison vs B1 Baseline\n")
    w(f"B1 baseline: RC = {B1_BASELINE_RC} "
      "(EW+AWH Industry Momentum, cap_20, Top-5 industries)\n")
    w("| Variant | Split | C1-A RC | B1 RC | vs B1 |")
    w("|---------|-------|---------|-------|-------|")

    for r in sorted(all_results, key=lambda x: (x["split"], x["top_n"], x["min_stk"])):
        if r["min_stk"] != MIN_STK:
            continue
        m = r["metrics"]
        direction = "WIN" if m["rc"] > B1_BASELINE_RC else "LOSE"
        delta = m["rc"] - B1_BASELINE_RC
        w(f"| Top{r['top_n']} S{r['min_stk']} | {r['split']} | "
          f"{m['rc']:.2f} | {B1_BASELINE_RC} | {direction} ({delta:+.2f}) |")

    # --- 6. Verdict ---
    w("\n---\n## 6. Verdict\n")

    ex25_results = [r for r in all_results
                    if r["split"] == "Ex-2025" and r["min_stk"] == MIN_STK]
    if not ex25_results:
        w("No Ex-2025 results available -- evaluation incomplete.\n")
    else:
        for r in ex25_results:
            key = (r["split"], r["top_n"], r["min_stk"])
            info = gate_results.get(key, {})
            overall = info.get("overall", "FAIL")
            m = r["metrics"]
            w(f"**C1-A Top-{r['top_n']} S{r['min_stk']}: {overall}**")
            w(f"- RC: {m['rc']:.2f} (gate: >= 1.0)")
            w(f"- IR: {m['ir']:.2f} (gate: > 0.3)")
            w(f"- Win Rate: {m['wr']:.0%} (gate: > 55%)")
            w(f"- Turnover: {m['avg_to']:.0%} (gate: < 50%)")
            w(f"- Max DD: {m['max_dd']:.1%} (gate: > -30%)")
            w(f"- T10%: {m['t10_contrib']:.0%} (gate: < 80%)")
            w(f"- Single-Ind: {m['top_ind_contrib']:.0%} (should: < 50%)")
            w(f"- Single-Stk: {m['top_stk_contrib']:.0%} (should: < 30%)")
            ms5 = info.get("rc_decay_ms5", None)
            if ms5 is not None:
                w(f"- MinStk=5 RC decay: {ms5:.2f} " +
                  ("(FRAGILE)" if info.get("ms5_fragile") else "(STABLE)"))
            else:
                w("- MinStk=5: N/A")
            w("")

    # --- 7. C1-B / C1-C Eligibility ---
    w("---\n## 7. C1-B / C1-C Eligibility\n")

    any_pass = any(gate_results.get((r["split"], r["top_n"], r["min_stk"]), {})
                   .get("overall") in ("PASS", "FRAGILE")
                   for r in ex25_results)
    all_t10_ok = all(r["metrics"]["t10_contrib"] < 0.80 for r in ex25_results)

    if not any_pass:
        w("**C1-A did not PASS any variant. C1-B and C1-C are NOT eligible.**")
        w("Recommend: stop C1. Stock-level within-industry alpha not viable.\n")
    elif not all_t10_ok:
        w("**C1-A T10% > 80% on some variants. C1-B and C1-C are NOT eligible** "
          "(per B2 lesson: time-concentrated returns amplify.)\n")
    else:
        w("**C1-A passed gates. C1-B and C1-C are eligible for evaluation.**\n")
        w("Proceed with caution:")
        w("- C1-B: Trend quality (efficiency + up-day ratio + drawdown recovery)")
        w("- C1-C: Volume-price confirmation "
          "(volume-confirmed momentum + amount share trend)\n")

    # --- 8. Known Limitations ---
    w("---\n## 8. Known Limitations\n")
    w("1. **Industry classification look-ahead bias**: The industry map is a "
      "2026-05-18 snapshot applied to historical periods (2022-2026). "
      "Industry assignments may differ from what was known historically.")
    w("2. **Constituent survivorship bias**: historical_constituents.json has "
      "quarterly snapshots -- interim changes (~5-10% annual turnover) "
      "not captured.")
    w("3. **pre_close is mostly NaN**: Limit-up/down filtering uses the "
      "limit_up/limit_down columns directly, which are populated.")
    w("4. **ST detection**: The `is_st` field is not populated; ST check "
      "relies on symbol name containing 'ST', which may miss some cases "
      "and produce false positives.")
    w("5. **Suspension detection**: `is_suspended` field barely populated; "
      "suspension check uses volume == 0, which may not catch all suspensions.")
    w("6. **Listed-days filter**: Uses trading-day count in the dataset, "
      "not actual IPO date. Stocks with data gaps may be filtered incorrectly.")
    w("7. **Benchmark timing mismatch**: Portfolio returns use open-to-open "
      "prices while HS300 EW benchmark uses close-to-close daily returns. "
      "The ~1-day timing difference is standard in offline evaluations.")
    w("8. **Single-industry contribution**: Uses industry map at signal date, "
      "which has look-ahead bias. Industry concentration may be understated.\n")

    w("---\n*Generated by evaluate_c1_industry_inside_stock_selection.py*")
    return "\n".join(L)


# --- Main ---

def main():
    import argparse
    p = argparse.ArgumentParser(
        description="C1-A Industry-Inside Stock Selection Evaluation")
    p.add_argument("--smoke", action="store_true",
                   help="Quick test: 2024 only, Top-20 only, MinStk=3")
    p.add_argument("--no-var", action="store_true",
                   help="Skip Phase 1a variance decomposition")
    args = p.parse_args()

    smoke = args.smoke
    skip_var = args.no_var

    top_n_list = [20] if smoke else TOP_N_LIST
    min_stk_list = [3] if smoke else [3, 5]
    splits = [("2024 only", "2024-01-01", "2024-12-31")] if smoke else SPLITS

    print("=" * 64)
    print(f"C1-A Industry-Inside Stock Selection {'SMOKE' if smoke else 'FULL'}")
    print(f"Top-N: {top_n_list} | MinStk: {min_stk_list}")
    print(f"Splits: {[s[0] for s in splits]}")
    print("=" * 64)

    # --- Load data ---
    print("\n[1/5] Loading data...")
    bars = pd.read_parquet(BAR_PATH)
    bars["trade_date"] = pd.to_datetime(bars["trade_date"])
    bars = bars[bars["trade_date"] >= "2019-01-01"]
    bars = bars.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    calendar = pd.read_parquet(CAL_PATH)
    calendar["trade_date"] = pd.to_datetime(calendar["trade_date"])
    all_dates = sorted(
        calendar[calendar["is_trading_day"]]["trade_date"]
        .dt.strftime("%Y-%m-%d").tolist()
    )
    all_dates = [d for d in all_dates if d >= "2019-01-01"]

    bars["td"] = bars["trade_date"].astype(str)

    cm = load_constituent_map()
    im = load_industry_map()
    print(f"  Bars: {len(bars)} rows, {bars['symbol'].nunique()} symbols")
    print(f"  Calendar: {len(all_dates)} trading days (from {all_dates[0]})")
    print(f"  Constituents: {len(cm)} quarterly snapshots")
    print(f"  Industries: {len(set(im.values()))} unique industries in map")

    # --- Phase 1a: Variance Decomposition ---
    var_results = {}
    if not skip_var:
        var_results = run_variance_decomposition(bars, cm, im, all_dates,
                                                  sample_every=5)
    else:
        print("\n--- Phase 1a: Skipped (--no-var) ---")
        var_results = {"mean_r2": None, "by_year": {}, "tier": "skipped",
                       "n_days": 0, "n_years": 0}

    # --- Benchmark ---
    print("\n[2/5] Computing HS300 EW benchmark...")
    hs300_ew = compute_hs300_ew(bars, cm, all_dates)
    print(f"  HS300 EW cumulative: {len(hs300_ew)} days")

    # --- Phase 1b: C1-A Simulation ---
    print("\n[3/5] Running C1-A simulations...")
    all_results = []

    total_configs = len(top_n_list) * len(min_stk_list) * len(splits)
    done = 0

    for min_stk in min_stk_list:
        for top_n in top_n_list:
            for split_name, split_start, split_end in splits:
                done += 1
                ed = [d for d in all_dates if split_start <= d <= split_end]
                if len(ed) < 20:
                    print(f"  [{done}/{total_configs}] {split_name} Top{top_n} "
                          f"S{min_stk}: SKIP (<20 trading days)")
                    continue

                print(f"  [{done}/{total_configs}] {split_name} Top{top_n} "
                      f"S{min_stk}...")
                result = simulate_c1a(bars, cm, im, ed, top_n, min_stk,
                                      LOOKBACK, hs300_ew)

                if result is not None:
                    m = result["metrics"]
                    rel = reliability_label(result)
                    all_results.append({
                        "split": split_name,
                        "top_n": top_n,
                        "min_stk": min_stk,
                        "metrics": m,
                        "selections": result["selections"],
                        "filter_stats": result["filter_stats"],
                        "reliability": rel,
                    })
                    print(f"    RC={m['rc']:.2f} IR={m['ir']:.2f} "
                          f"WR={m['wr']:.0%} DD={m['max_dd']:.1%} "
                          f"T10={m['t10_contrib']:.0%} TO={m['avg_to']:.0%} "
                          f"[n={m['nm']}m, {rel}]")
                else:
                    print(f"    FAILED (<3 valid months)")

    # --- Check gates ---
    print("\n[4/5] Evaluating gates...")
    gate_results = check_gates(all_results)

    # --- Generate report ---
    print("\n[5/5] Generating report...")
    report = generate_report(var_results, all_results, gate_results, hs300_ew)

    report_path = ROOT / "reports" / "c1_industry_inside_stock_selection_20260519.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport written to: {report_path}")
    print("\n" + "=" * 64)
    print("REPORT SUMMARY")
    print("=" * 64)
    print(report)


if __name__ == "__main__":
    main()


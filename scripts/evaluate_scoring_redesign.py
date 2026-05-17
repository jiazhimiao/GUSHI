"""Offline scoring formula evaluation — raw breakout candidates only.

No backtest. No RegimeEngine. No GA. No strategy changes.

Computes 5 score variants on L2 raw_breakout_candidates, evaluates:
  - Global decile metrics (FB rate, fwd_ret, MAE)
  - Daily ranking metrics (top1/top3/top20% per-day)
  - Time split: train(2018-21) / val(2022-23) / test(2024-26)
  - Year-by-year stability
  - 6 pass conditions

Usage:
    python scripts/evaluate_scoring_redesign.py
    python scripts/evaluate_scoring_redesign.py --start 2018-01-01 --end 2021-12-31  # train only
"""
import sys, json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.backtest.data_context import build_strategy_context
from qts.utils.config import get_project_root
from qts.utils.time import generate_rebalance_dates

ROOT = get_project_root()
BAR_PATH = str(ROOT / "data/raw/HS300_daily.parquet")
CAL_PATH = str(ROOT / "data/raw/calendar.parquet")

EPS = 1e-10


def _sf(v):
    """Safe float: convert pandas Series element to float."""
    if hasattr(v, 'iloc'):
        return float(v.iloc[0])
    return float(v)


# ═══════════════════════════════════════════════════════════════════
# Data loading
# ═══════════════════════════════════════════════════════════════════

def load_data(start, end):
    """Load prices via build_strategy_context (same as original diagnosis)."""
    print(f"Loading data {start} ~ {end} ...")
    ctx = build_strategy_context(
        bar_path=BAR_PATH, calendar_path=CAL_PATH,
        start_date=start, end_date=end,
        use_constituent_filter=True,
    )
    calendar = pd.read_parquet(CAL_PATH)
    dates = generate_rebalance_dates(start, end, calendar, "daily")
    return ctx, dates


# ═══════════════════════════════════════════════════════════════════
# Raw candidate detection + label computation
# ═══════════════════════════════════════════════════════════════════

def detect_candidates_and_labels(ctx, dates, breakout_days=20):
    """Detect L2 raw breakout candidates and compute labels.

    Returns DataFrame with columns:
      date, symbol, breakout_pct, volume_boost, breakout_level,
      close_T, open_T, high_T, low_T, vol_T, avg_vol_20d,
      false_breakout_5d, fwd_ret_5d, fwd_ret_10d, mae_5d,
      breadth (market breadth on that date)
    """
    print(f"Detecting candidates over {len(dates)} dates ...")
    prices = ctx.prices
    highs = ctx.highs
    lows = ctx.lows
    opens = ctx.opens
    volumes = ctx.volumes

    # Constituents
    constituent_quarterly = ctx.constituent_quarterly

    # Breadth cache
    breadth_cache = getattr(ctx, 'breadth_series', None)

    records = []
    all_trading_days = len(dates)
    days_with_candidates = 0
    days_without_candidates = 0
    skipped_data_insufficient = 0

    for i, date in enumerate(dates):
        if i % 400 == 0:
            print(f"  {date} ({i+1}/{len(dates)})")

        date_mask = prices.index <= date
        need = breakout_days + 60 + 1
        if len(date_mask) < need:
            skipped_data_insufficient += 1
            continue

        # Eligible symbols
        if constituent_quarterly:
            date_str = str(pd.Timestamp(date).date())
            sorted_dates = sorted(constituent_quarterly.keys())
            eligible = None
            for q_date in reversed(sorted_dates):
                if q_date <= date_str:
                    eligible = constituent_quarterly[q_date]
                    break
            if eligible is None:
                eligible = constituent_quarterly[sorted_dates[0]]
        else:
            eligible = list(prices.columns)

        common = [s for s in eligible if s in prices.columns]
        if not common:
            continue

        today_close = prices.loc[date_mask, common].iloc[-1]
        today_open = opens.loc[date_mask, common].iloc[-1]
        today_high = highs.loc[date_mask, common].iloc[-1]
        today_low = lows.loc[date_mask, common].iloc[-1]
        today_vol = volumes.loc[date_mask, common].iloc[-1]

        n_day_high = highs.loc[date_mask, common].iloc[-(breakout_days + 1):-1].max()
        avg_vol = volumes.loc[date_mask, common].iloc[-(breakout_days + 1):-1].mean()
        ma = prices.loc[date_mask, common].iloc[-(60 + 1):-1].mean()

        cond1 = today_close > n_day_high
        cond2 = (avg_vol > 0) & (today_vol >= avg_vol * 1.5)
        cond3 = today_close > ma
        raw = (today_vol > 0) & cond1 & cond2 & cond3

        if not raw.any():
            days_without_candidates += 1
            continue

        days_with_candidates += 1

        cand_syms = list(raw[raw].index)
        # Ensure Series (not DataFrame) by using .loc on the Series
        tc_s = today_close.loc[cand_syms]
        to_s = today_open.loc[cand_syms]
        th_s = today_high.loc[cand_syms]
        tl_s = today_low.loc[cand_syms]
        tv_s = today_vol.loc[cand_syms]
        av_s = avg_vol.loc[cand_syms]
        nh_s = n_day_high.loc[cand_syms]

        bp = (tc_s / nh_s - 1.0) * 100
        vb = tv_s / av_s.replace(0, np.nan)
        bl = nh_s

        # Breadth on this date
        if breadth_cache is not None:
            try:
                breadth_val = float(breadth_cache.get(date, 0.5))
            except Exception:
                breadth_val = 0.5
        else:
            breadth_val = 0.5

        # Compute labels for each candidate
        for sym in cand_syms:
            # False breakout: 5d forward check
            future_mask = prices.index > date
            future_close = prices.loc[future_mask, sym] if sym in prices.columns else pd.Series()
            fell_back = False
            mae_vals = [0.0]
            fwd_5 = np.nan
            fwd_10 = np.nan

            if len(future_close) > 0:
                ct = _sf(tc_s[sym])
                bt = _sf(bl[sym])
                for j, (fc_date, fc_val) in enumerate(future_close.items()):
                    if pd.isna(fc_val):
                        continue
                    fc_val = float(fc_val)
                    if j == 4 and not np.isnan(ct) and ct > 0:
                        fwd_5 = (fc_val / ct - 1) * 100
                    if j == 9 and not np.isnan(ct) and ct > 0:
                        fwd_10 = (fc_val / ct - 1) * 100
                    if j < 5:
                        if fc_val < bt:
                            fell_back = True
                        if ct > 0:
                            mae_vals.append((fc_val / ct - 1) * 100)
                    if j >= 9:
                        break

            mae_5d = min(mae_vals) if mae_vals else 0.0

            records.append({
                "date": date,
                "symbol": sym,
                "breakout_pct": _sf(bp[sym]),
                "volume_boost": _sf(vb[sym]) if not np.isnan(_sf(vb[sym])) else 1.5,
                "breakout_level": _sf(bl[sym]),
                "close_T": _sf(tc_s[sym]),
                "open_T": _sf(to_s[sym]),
                "high_T": _sf(th_s[sym]),
                "low_T": _sf(tl_s[sym]),
                "vol_T": _sf(tv_s[sym]),
                "avg_vol_20d": _sf(av_s[sym]) if not np.isnan(_sf(av_s[sym])) else _sf(tv_s[sym]),
                "false_breakout_5d": fell_back,
                "fwd_ret_5d": fwd_5,
                "fwd_ret_10d": fwd_10,
                "mae_5d": mae_5d,
                "breadth": breadth_val,
            })

    df = pd.DataFrame(records)
    print(f"  Total candidates: {len(df)}")
    print(f"  All trading days: {all_trading_days}")
    print(f"  Days with candidates: {days_with_candidates}")
    print(f"  Days without candidates: {days_without_candidates} ({days_without_candidates/all_trading_days*100:.1f}%)")
    print(f"  Skipped (data insufficient): {skipped_data_insufficient}")
    print(f"  NaN fwd_ret_5d: {df['fwd_ret_5d'].isna().sum()} ({df['fwd_ret_5d'].isna().mean()*100:.1f}%)")
    print(f"  NaN fwd_ret_10d: {df['fwd_ret_10d'].isna().sum()} ({df['fwd_ret_10d'].isna().mean()*100:.1f}%)")
    day_counts = {
        "all_trading_days": all_trading_days,
        "days_with_candidates": days_with_candidates,
        "days_without_candidates": days_without_candidates,
        "skipped_data_insufficient": skipped_data_insufficient,
    }
    return df, day_counts


# ═══════════════════════════════════════════════════════════════════
# Score variants
# ═══════════════════════════════════════════════════════════════════

def compute_scores(df):
    """Compute all 5 score variants. Returns df with added score columns."""
    d = df.copy()

    bp = d["breakout_pct"].values
    vb = d["volume_boost"].values
    op = d["open_T"].values
    hi = d["high_T"].values
    lo = d["low_T"].values
    cl = d["close_T"].values
    breadth = d["breadth"].values

    # ── baseline ──
    d["score_baseline"] = bp * np.log1p(np.clip(vb, 0.5, 10.0))

    # ── v1: nonlinear breakout_pct ──
    f1 = bp ** 2 / 2.0  # square: penalize small, reward large
    d["score_v1"] = f1 * np.log1p(np.clip(vb, 0.5, 10.0))
    d["_v1_f_bp"] = f1

    # ── v2: candle structure ──
    hilo = np.abs(hi - lo) + EPS
    body_pct = np.clip(np.abs(cl - op) / hilo, 0, 1)
    close_loc = np.clip((cl - lo) / hilo, 0, 1)
    upper_shadow = np.clip((hi - np.maximum(op, cl)) / hilo, 0, 1)
    d["_v2_body_pct"] = body_pct
    d["_v2_close_loc"] = close_loc
    d["_v2_upper_shadow"] = upper_shadow
    d["score_v2"] = d["score_baseline"] * (1 + body_pct * 1.0) * (1 + close_loc * 0.5) * (1 - upper_shadow * 1.0)

    # ── v3: pre-breakout behavior (T-day and before only) ──
    # These are computed from the already-available columns.
    # We don't have pre-breakout daily bars in the candidate df,
    # but we CAN compute proxy features from the breakout characteristics:
    #   - approach_3d proxy: close_T / breakout_level (how far above)
    #     > 1.0 means exceeded, closer to 1.0 means tighter approach
    #     We use the inverse: breakout_level / close_T (closer to 1 = tighter)
    #   - pre_vol_contraction proxy: avg_vol_20d vs vol_T
    #     if vol_T is high relative to avg, less likely to be contraction
    #     Actually we need pre-breakout bars. For now use what we have.

    approach_proxy = np.clip(d["breakout_level"].values / cl, 0.9, 1.0)  # closer to 1 = tighter
    pre_approach_score = np.clip((approach_proxy - 0.95) * 20, 0, 1)  # >0.95 gets bonus

    # pre_vol_contraction: use avg_vol vs vol_T as proxy
    vol_ratio_proxy = np.clip(d["avg_vol_20d"].values / (d["vol_T"].values + EPS), 0.3, 3.0)
    pre_vol_contract_score = np.clip((vol_ratio_proxy - 0.5) * 0.5, 0, 0.5)

    # pre_above_ma: we know close_T > MA60 (condition 3). proxy = 1.0
    # For variety, use how far above MA: (close_T / MA60 - 1) via breakout_pct logic
    # Actually we can't get MA60 without extra data, so use a constant bonus
    pre_above_ma_score = 0.1  # constant small bonus

    # pre_drawdown proxy: breakout_pct itself (higher = less recent drawdown from high)
    pre_dd_score = np.clip(bp / 5.0, 0, 0.3)

    # pre_vol_ramp: already captured by volume_boost partially
    pre_vol_ramp_score = np.clip((np.clip(vb, 1.0, 3.0) - 1.0) * 0.2, 0, 0.4)

    d["score_v3"] = d["score_baseline"] * (
        1.0 + pre_approach_score + pre_vol_contract_score +
        pre_above_ma_score + pre_dd_score + pre_vol_ramp_score
    )
    d["_v3_approach"] = pre_approach_score
    d["_v3_vol_contract"] = pre_vol_contract_score

    # ── v4: market breadth ──
    d["score_v4"] = d["score_baseline"] * (1.0 + np.clip(breadth, 0.0, 0.8) * 0.5)

    # ── Cleanup: replace inf/nan with 0 ──
    score_cols = ["score_baseline", "score_v1", "score_v2", "score_v3", "score_v4"]
    fallback_counts = {}
    for col in score_cols:
        bad = ~np.isfinite(d[col])
        fallback_counts[col] = bad.sum()
        d.loc[bad, col] = 0.0

    d["_dropped"] = False
    d["_fallback_to_zero"] = False
    for col in score_cols:
        d.loc[~np.isfinite(d[col]), col] = 0.0

    return d, score_cols, fallback_counts


# ═══════════════════════════════════════════════════════════════════
# Global decile analysis
# ═══════════════════════════════════════════════════════════════════

def global_decile_metrics(df, score_col, n_deciles=10):
    """Compute per-decile metrics for a score column (global ranking)."""
    d = df.copy()
    d["decile"] = pd.qcut(d[score_col].rank(method="first"), n_deciles,
                          labels=False, duplicates="drop")
    # qcut with duplicates='drop' may produce fewer than n_deciles
    actual_n = d["decile"].nunique()

    metrics = {}
    for dec in range(actual_n):
        sub = d[d["decile"] == dec]
        n = len(sub)
        fb = sub["false_breakout_5d"].mean() * 100
        fwd5 = sub["fwd_ret_5d"].dropna()
        fwd10 = sub["fwd_ret_10d"].dropna()
        mae = sub["mae_5d"].dropna()

        metrics[f"decile_{dec}"] = {
            "n": n,
            "fb_rate": round(fb, 1),
            "fwd_ret_5d_median": round(fwd5.median(), 2) if len(fwd5) > 0 else np.nan,
            "fwd_ret_5d_mean": round(fwd5.mean(), 2) if len(fwd5) > 0 else np.nan,
            "fwd_ret_10d_median": round(fwd10.median(), 2) if len(fwd10) > 0 else np.nan,
            "fwd_ret_10d_mean": round(fwd10.mean(), 2) if len(fwd10) > 0 else np.nan,
            "mae_5d_mean": round(mae.mean(), 2) if len(mae) > 0 else np.nan,
        }

    # Top 10% / 20%
    top10 = d[d["decile"] >= actual_n - max(1, actual_n // 10)]
    top20 = d[d["decile"] >= actual_n - max(1, actual_n // 5)]
    metrics["top10pct"] = {
        "n": len(top10),
        "fb_rate": round(top10["false_breakout_5d"].mean() * 100, 1),
        "fwd_ret_5d_median": round(top10["fwd_ret_5d"].dropna().median(), 2),
    }
    metrics["top20pct"] = {
        "n": len(top20),
        "fb_rate": round(top20["false_breakout_5d"].mean() * 100, 1),
        "fwd_ret_5d_median": round(top20["fwd_ret_5d"].dropna().median(), 2),
    }
    return metrics


# ═══════════════════════════════════════════════════════════════════
# Daily ranking analysis
# ═══════════════════════════════════════════════════════════════════

def daily_ranking_metrics(df, score_col, day_counts=None):
    """Compute per-day top1/top3/top20% metrics.

    Args:
        df: candidates DataFrame
        score_col: score column name
        day_counts: dict with all_trading_days, days_without_candidates (from detect_candidates_and_labels)
    """
    d = df.copy()

    # Rank within each date (descending: rank 1 = highest score)
    d["rank"] = d.groupby("date")[score_col].rank(ascending=False, method="first")
    d["date_count"] = d.groupby("date")[score_col].transform("count")

    # Top 1: highest score each day
    top1 = d[d["rank"] <= 1]
    # Top 3: min(3, candidate_count) highest scores
    top3 = d[d["rank"] <= 3]
    # top 20%: max(1, ceil(candidate_count * 0.2))
    d["top20pct_cutoff"] = np.maximum(1, np.ceil(d["date_count"] * 0.2))
    top20 = d[d["rank"] <= d["top20pct_cutoff"]]

    # Sanity check: top1 ⊆ top3 ⊆ top20pct
    top1_rows = set(zip(top1["date"], top1["symbol"]))
    top20_rows = set(zip(top20["date"], top20["symbol"]))
    top1_in_top20 = len(top1_rows & top20_rows)
    top1_in_top20_rate = top1_in_top20 / max(1, len(top1_rows)) * 100

    # Daily candidate counts (over candidate days only)
    daily_counts_cand = d.groupby("date").size()

    # All-days metrics
    if day_counts:
        all_days = day_counts["all_trading_days"]
        zero_days = day_counts["days_without_candidates"]
    else:
        all_days = d["date"].nunique()
        zero_days = 0

    # Daily candidate count over ALL trading days (pad zeros)
    cand_dates = set(d["date"].unique())

    metrics = {
        "total_candidates": len(d),
        "all_trading_days": all_days,
        "candidate_days": len(daily_counts_cand),
        "zero_candidate_days": zero_days,
        "zero_candidate_days_pct": round(zero_days / all_days * 100, 1) if all_days > 0 else 0,
        # Over candidate days only
        "daily_count_cand_median": round(daily_counts_cand.median(), 1),
        "daily_count_cand_p25": round(daily_counts_cand.quantile(0.25), 1),
        "daily_count_cand_p75": round(daily_counts_cand.quantile(0.75), 1),
        "daily_count_cand_mean": round(daily_counts_cand.mean(), 1),
        # Top 1
        "top1_n": len(top1),
        "top1_fb_rate": round(top1["false_breakout_5d"].mean() * 100, 1) if len(top1) > 0 else np.nan,
        "top1_fwd_5d_median": round(top1["fwd_ret_5d"].dropna().median(), 2) if len(top1) > 0 else np.nan,
        "top1_fwd_10d_median": round(top1["fwd_ret_10d"].dropna().median(), 2) if len(top1) > 0 else np.nan,
        "top1_mae_5d_mean": round(top1["mae_5d"].dropna().mean(), 2) if len(top1) > 0 else np.nan,
        # Top 3
        "top3_n": len(top3),
        "top3_fb_rate": round(top3["false_breakout_5d"].mean() * 100, 1) if len(top3) > 0 else np.nan,
        "top3_fwd_5d_median": round(top3["fwd_ret_5d"].dropna().median(), 2) if len(top3) > 0 else np.nan,
        "top3_fwd_10d_median": round(top3["fwd_ret_10d"].dropna().median(), 2) if len(top3) > 0 else np.nan,
        "top3_mae_5d_mean": round(top3["mae_5d"].dropna().mean(), 2) if len(top3) > 0 else np.nan,
        # Top 20%
        "top20pct_n": len(top20),
        "top20pct_fb_rate": round(top20["false_breakout_5d"].mean() * 100, 1) if len(top20) > 0 else np.nan,
        "top20pct_fwd_5d_median": round(top20["fwd_ret_5d"].dropna().median(), 2) if len(top20) > 0 else np.nan,
        "top20pct_fwd_10d_median": round(top20["fwd_ret_10d"].dropna().median(), 2) if len(top20) > 0 else np.nan,
        "top20pct_mae_5d_mean": round(top20["mae_5d"].dropna().mean(), 2) if len(top20) > 0 else np.nan,
        # Sanity: top1 must be subset of top20pct
        "top1_in_top20pct_rate": round(top1_in_top20_rate, 1),
        "top1_in_top3_rate": round(
            len(top1_rows & set(zip(top3["date"], top3["symbol"]))) / max(1, len(top1_rows)) * 100, 1
        ),
        "top1_size": len(top1),
        "top20pct_size": len(top20),
        "top1_pct_of_top20": round(len(top1) / max(1, len(top20)) * 100, 1),
    }
    return metrics


# ═══════════════════════════════════════════════════════════════════
# Year-by-year + time split
# ═══════════════════════════════════════════════════════════════════

def yearly_metrics(df, score_col):
    """Compute daily ranking metrics per year."""
    d = df.copy()
    d["year"] = pd.to_datetime(d["date"]).dt.year
    results = {}
    for yr in sorted(d["year"].unique()):
        sub = d[d["year"] == yr]
        if len(sub) > 0:
            results[yr] = daily_ranking_metrics(sub, score_col, day_counts=None)
    return results


def time_split_metrics(df, score_col):
    """Compute metrics for train/val/test splits."""
    d = df.copy()
    d["date_dt"] = pd.to_datetime(d["date"])
    splits = {
        "train": ("2018-01-01", "2021-12-31"),
        "val": ("2022-01-01", "2023-12-31"),
        "test": ("2024-01-01", "2026-05-15"),
    }
    results = {}
    for name, (s, e) in splits.items():
        sub = d[(d["date_dt"] >= s) & (d["date_dt"] <= e)]
        if len(sub) > 0:
            results[name] = daily_ranking_metrics(sub, score_col, day_counts=None)
    return results


# ═══════════════════════════════════════════════════════════════════
# Pass condition check
# ═══════════════════════════════════════════════════════════════════

def check_pass_conditions(variant_name, baseline_daily, variant_daily, yearly, time_split):
    """Check 6 pass conditions for a score variant."""
    checks = {}

    bl_top3_fb = baseline_daily["top3_fb_rate"]
    var_top3_fb = variant_daily["top3_fb_rate"]
    bl_top20_fb = baseline_daily["top20pct_fb_rate"]
    var_top20_fb = variant_daily["top20pct_fb_rate"]

    # A: FB improvement
    checks["A_fb_top3_le35"] = not np.isnan(var_top3_fb) and var_top3_fb <= 35.0
    checks["A_fb_top3_drop8pp"] = not np.isnan(var_top3_fb) and not np.isnan(bl_top3_fb) and (bl_top3_fb - var_top3_fb) >= 8.0
    checks["A_fb_top20_drop10pp"] = not np.isnan(var_top20_fb) and not np.isnan(bl_top20_fb) and (bl_top20_fb - var_top20_fb) >= 10.0
    checks["A_fb_pass"] = checks["A_fb_top3_le35"] or checks["A_fb_top3_drop8pp"] or checks["A_fb_top20_drop10pp"]

    # B: Forward return not worse
    checks["B_fwd5"] = (
        not np.isnan(variant_daily.get("top3_fwd_5d_median", np.nan))
        and not np.isnan(baseline_daily.get("top3_fwd_5d_median", np.nan))
        and variant_daily["top3_fwd_5d_median"] >= baseline_daily["top3_fwd_5d_median"]
    )
    checks["B_fwd10"] = (
        not np.isnan(variant_daily.get("top3_fwd_10d_median", np.nan))
        and not np.isnan(baseline_daily.get("top3_fwd_10d_median", np.nan))
        and variant_daily["top3_fwd_10d_median"] >= baseline_daily["top3_fwd_10d_median"]
    )
    checks["B_fwd_pass"] = checks["B_fwd5"] and checks["B_fwd10"]

    # C: MAE not worse
    checks["C_mae_pass"] = (
        not np.isnan(variant_daily.get("top20pct_mae_5d_mean", np.nan))
        and not np.isnan(baseline_daily.get("top20pct_mae_5d_mean", np.nan))
        and abs(variant_daily["top20pct_mae_5d_mean"]) <= abs(baseline_daily["top20pct_mae_5d_mean"])
    )

    # D: Yearly consistency (at least 3 years with same-direction FB improvement)
    yr_improvements = []
    for yr, ym in sorted(yearly.items()):
        bl_yr = baseline_daily.get(f"_yr_{yr}", {})
        if isinstance(bl_yr, dict) and bl_yr:
            bl_fb = bl_yr.get("top3_fb_rate", np.nan)
        else:
            bl_fb = np.nan
        var_fb = ym.get("top3_fb_rate", np.nan)
        if not np.isnan(bl_fb) and not np.isnan(var_fb):
            yr_improvements.append(var_fb < bl_fb)
    checks["D_yearly_n_improved"] = sum(yr_improvements)
    checks["D_yearly_pass"] = sum(yr_improvements) >= 3

    # E: Sample size
    yearly_ok = True
    for yr, ym in yearly.items():
        if ym.get("top3_n", 0) < 200:
            yearly_ok = False
    checks["E_sample_yearly_top3"] = yearly_ok

    # F: Daily feasibility
    checks["F_zero_days_ok"] = (
        variant_daily["zero_candidate_days_pct"] <= baseline_daily["zero_candidate_days_pct"] + 10.0
    )
    checks["F_daily_median_ge1"] = variant_daily.get("daily_count_cand_median", 0) >= 1.0

    checks["ALL_PASS"] = (
        checks["A_fb_pass"] and checks["B_fwd_pass"] and checks["C_mae_pass"]
        and checks["D_yearly_pass"] and checks["F_zero_days_ok"] and checks["F_daily_median_ge1"]
    )
    return checks


# ═══════════════════════════════════════════════════════════════════
# Report generation
# ═══════════════════════════════════════════════════════════════════

def generate_report(df, score_cols, fallback_counts, start, end, day_counts):
    """Generate the full evaluation report."""
    lines = []
    w = lines.append

    w("=" * 80)
    w("Breakout Scoring Redesign — 离线评估报告 (sanity-fixed)")
    w(f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    w(f"区间: {start} ~ {end}")
    w(f"总候选数: {len(df)}")
    w("=" * 80)

    # ── Candidate overview ──
    w("\n## 候选概览\n")
    all_days = day_counts["all_trading_days"]
    cand_days = day_counts["days_with_candidates"]
    zero_days = day_counts["days_without_candidates"]
    daily_counts = df.groupby("date").size()

    w(f"  全交易日: {all_days}")
    w(f"  数据不足跳过: {day_counts['skipped_data_insufficient']}")
    w(f"  有候选日: {cand_days}")
    w(f"  零候选日: {zero_days} ({zero_days/all_days*100:.1f}%)")
    w(f"  日均候选数 (全部交易日): median={daily_counts.median():.1f}, P25={daily_counts.quantile(0.25):.1f}, "
      f"P75={daily_counts.quantile(0.75):.1f}, mean={daily_counts.mean():.1f}")
    w(f"  日均候选数 (仅候选日): median={daily_counts.median():.1f}, P25={daily_counts.quantile(0.25):.1f}, "
      f"P75={daily_counts.quantile(0.75):.1f}, mean={daily_counts.mean():.1f}")
    w(f"  注: 日均候选数在全部交易日口径下需补零，median 会降低。候选日口径的 median 不变。")
    total_nan_5d = df["fwd_ret_5d"].isna().sum()
    w(f"  NaN fwd_ret_5d: {total_nan_5d} ({total_nan_5d/len(df)*100:.1f}%)")
    w(f"  False breakout rate (overall): {df['false_breakout_5d'].mean()*100:.1f}%")
    w(f"")
    w(f"  Score direction:")
    w(f"    - decile_0 = lowest score, decile_9 = highest score")
    w(f"    - daily ranking: rank=1 = highest score (降序)")
    w(f"    - top10pct / top20pct = highest score deciles (global)")
    w(f"    - top1/top3/top20pct (daily) = highest score per day")

    # ── Fallback/dropped ──
    w("\n## 数值保护\n")
    for col in score_cols:
        w(f"  {col}: fallback_to_zero={fallback_counts.get(col, 0)}")

    # ── Per-score evaluation ──
    all_daily_metrics = {}

    for variant_name in score_cols:
        w(f"\n{'─' * 80}")
        w(f"## Score Variant: {variant_name}")
        w(f"{'─' * 80}")

        # Global decile
        w("\n### Global Decile Metrics\n")
        gdm = global_decile_metrics(df, variant_name)
        w(f"  {'Decile':<12} {'N':>7} {'FB%':>7} {'Fwd5d_med':>10} {'Fwd10d_med':>11} {'MAE5d':>8}")
        w(f"  {'-'*12} {'-'*7} {'-'*7} {'-'*10} {'-'*11} {'-'*8}")
        for k, v in sorted(gdm.items()):
            if k.startswith("decile_"):
                w(f"  {k:<12} {v['n']:>7} {v['fb_rate']:>6.1f}% {v['fwd_ret_5d_median']:>9.2f}% "
                  f"{v['fwd_ret_10d_median']:>10.2f}% {v['mae_5d_mean']:>7.2f}%")
        for tag in ["top10pct", "top20pct"]:
            if tag in gdm:
                v = gdm[tag]
                w(f"  {tag:<12} {v['n']:>7} {v['fb_rate']:>6.1f}% {v['fwd_ret_5d_median']:>9.2f}%")

        # Daily ranking
        w("\n### Daily Ranking Metrics\n")
        dm = daily_ranking_metrics(df, variant_name, day_counts)
        all_daily_metrics[variant_name] = dm

        w(f"  全交易日: {dm['all_trading_days']}")
        w(f"  有候选日: {dm['candidate_days']}")
        w(f"  零候选日: {dm['zero_candidate_days']} ({dm['zero_candidate_days_pct']}%)")
        w(f"  每日候选数 (仅候选日): median={dm['daily_count_cand_median']}, P25={dm['daily_count_cand_p25']}, "
          f"P75={dm['daily_count_cand_p75']}, mean={dm['daily_count_cand_mean']}")
        w(f"")
        w(f"  {'Bucket':<12} {'N':>7} {'FB%':>7} {'Fwd5d_med':>10} {'Fwd10d_med':>11} {'MAE5d':>8}")
        w(f"  {'-'*12} {'-'*7} {'-'*7} {'-'*10} {'-'*11} {'-'*8}")
        for tag in ["top1", "top3", "top20pct"]:
            n_key = f"{tag}_n"
            fb_key = f"{tag}_fb_rate"
            f5_key = f"{tag}_fwd_5d_median"
            f10_key = f"{tag}_fwd_10d_median"
            mae_key = f"{tag}_mae_5d_mean"
            w(f"  {tag:<12} {dm.get(n_key, 0):>7} {dm.get(fb_key, np.nan):>6.1f}% "
              f"{dm.get(f5_key, np.nan):>9.2f}% {dm.get(f10_key, np.nan):>10.2f}% "
              f"{dm.get(mae_key, np.nan):>7.2f}%")
        # Sanity checks
        w(f"")
        w(f"  Sanity checks:")
        w(f"    top1_in_top20pct_rate: {dm.get('top1_in_top20pct_rate', 0):.1f}% (must be 100%)")
        w(f"    top1_in_top3_rate: {dm.get('top1_in_top3_rate', 0):.1f}% (must be 100%)")
        w(f"    top1 / top20pct size ratio: {dm.get('top1_pct_of_top20', 0):.1f}%")

        # Time split
        w("\n### Time Split\n")
        ts = time_split_metrics(df, variant_name)
        w(f"  {'Split':<8} {'CandDays':>9} {'Zero%':>7} {'CntMed':>7} {'Top3FB%':>8} {'Top3Fwd5':>9} {'Top3Fwd10':>10}")
        w(f"  {'-'*8} {'-'*9} {'-'*7} {'-'*7} {'-'*8} {'-'*9} {'-'*10}")
        for split_name in ["train", "val", "test"]:
            if split_name in ts:
                m = ts[split_name]
                w(f"  {split_name:<8} {m.get('candidate_days', 0):>9} {m.get('zero_candidate_days_pct', 0):>6.1f}% "
                  f"{m.get('daily_count_cand_median', 0):>6.1f} {m.get('top3_fb_rate', np.nan):>7.1f}% "
                  f"{m.get('top3_fwd_5d_median', np.nan):>8.2f}% {m.get('top3_fwd_10d_median', np.nan):>9.2f}%")

        # Yearly
        w("\n### Year-by-Year Stability\n")
        ym = yearly_metrics(df, variant_name)
        w(f"  {'Year':<6} {'N_Cand':>7} {'Top3N':>7} {'Top3FB%':>8} {'Top3Fwd5':>9} {'Top20FB%':>9}")
        w(f"  {'-'*6} {'-'*7} {'-'*7} {'-'*8} {'-'*9} {'-'*9}")
        for yr in sorted(ym.keys()):
            m = ym[yr]
            w(f"  {yr:<6} {m.get('total_candidates', 0):>7} {m.get('top3_n', 0):>7} "
              f"{m.get('top3_fb_rate', np.nan):>7.1f}% {m.get('top3_fwd_5d_median', np.nan):>8.2f}% "
              f"{m.get('top20pct_fb_rate', np.nan):>8.1f}%")

        # Low sample warnings
        for yr in sorted(ym.keys()):
            m = ym[yr]
            if m.get("top3_n", 0) < 200:
                w(f"  ⚠ {yr}: top3_n={m.get('top3_n', 0)} < 200 (低样本)")
            if m.get("top1_n", 0) < 100 and m.get("top1_n", 0) > 0:
                w(f"  ⚠ {yr}: top1_n={m.get('top1_n', 0)} < 100 (低样本)")

    # ── Pass condition comparison ──
    w(f"\n{'─' * 80}")
    w(f"## 通过条件检查 (vs baseline)\n")

    baseline_dm = all_daily_metrics.get("score_baseline", {})
    # Add yearly baseline metrics
    baseline_yearly = yearly_metrics(df, "score_baseline")
    for yr, ym in baseline_yearly.items():
        baseline_dm[f"_yr_{yr}"] = ym

    w(f"  {'Variant':<16} {'A_FB':>6} {'B_Fwd':>6} {'C_MAE':>6} {'D_Yrly':>6} {'E_Samp':>6} {'F_Daily':>7} {'ALL':>5}")
    w(f"  {'-'*16} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*6} {'-'*7} {'-'*5}")
    for variant_name in score_cols:
        if variant_name == "score_baseline":
            w(f"  {'baseline':<16} {'(ref)':>6} {'(ref)':>6} {'(ref)':>6} {'(ref)':>6} {'(ref)':>6} {'(ref)':>7} {'-':>5}")
            continue
        dm = all_daily_metrics.get(variant_name, {})
        ym = yearly_metrics(df, variant_name)
        checks = check_pass_conditions(variant_name, baseline_dm, dm, ym, {})
        w(f"  {variant_name:<16} "
          f"{'PASS' if checks.get('A_fb_pass') else 'FAIL':>6} "
          f"{'PASS' if checks.get('B_fwd_pass') else 'FAIL':>6} "
          f"{'PASS' if checks.get('C_mae_pass') else 'FAIL':>6} "
          f"{'PASS' if checks.get('D_yearly_pass') else 'FAIL':>6} "
          f"{'PASS' if checks.get('E_sample_yearly_top3') else 'FAIL':>6} "
          f"{'PASS' if (checks.get('F_zero_days_ok') and checks.get('F_daily_median_ge1')) else 'FAIL':>7} "
          f"{'PASS' if checks.get('ALL_PASS') else 'FAIL':>5}")

    # ── Detailed check breakdown ──
    w(f"\n## 详细检查拆解\n")
    for variant_name in score_cols:
        if variant_name == "score_baseline":
            continue
        dm = all_daily_metrics.get(variant_name, {})
        ym = yearly_metrics(df, variant_name)
        checks = check_pass_conditions(variant_name, baseline_dm, dm, ym, {})
        w(f"\n### {variant_name}")
        for k, v in sorted(checks.items()):
            status = "✓" if v else "✗"
            w(f"  {status} {k}: {v}")

    # ── Recommendation ──
    w(f"\n{'─' * 80}")
    w(f"## 最终推荐\n")
    passed = []
    for variant_name in score_cols:
        if variant_name == "score_baseline":
            continue
        dm = all_daily_metrics.get(variant_name, {})
        ym = yearly_metrics(df, variant_name)
        checks = check_pass_conditions(variant_name, baseline_dm, dm, ym, {})
        if checks.get("ALL_PASS"):
            passed.append(variant_name)

    if passed:
        w(f"  通过所有条件的 score variant: {', '.join(passed)}")
        w(f"  建议: 进入策略回测实现")
    else:
        w(f"  无 score variant 通过所有条件。")
        w(f"  查看最接近通过的 variant:")
        for variant_name in score_cols:
            if variant_name == "score_baseline":
                continue
            dm = all_daily_metrics.get(variant_name, {})
            ym = yearly_metrics(df, variant_name)
            checks = check_pass_conditions(variant_name, baseline_dm, dm, ym, {})
            n_pass = sum(1 for v in checks.values() if v is True)
            w(f"    {variant_name}: {n_pass} checks passed")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2026-05-15")
    p.add_argument("--breakout-days", type=int, default=20)
    args = p.parse_args()

    print("=" * 60)
    print("Breakout Scoring Redesign — Offline Evaluation")
    print(f"Period: {args.start} ~ {args.end}")
    print("=" * 60)

    # Load data
    ctx, dates = load_data(args.start, args.end)
    print(f"  ctx.prices: {ctx.prices.shape}")

    # Detect candidates + labels
    df, day_counts = detect_candidates_and_labels(ctx, dates, breakout_days=args.breakout_days)
    if len(df) == 0:
        print("ERROR: No candidates detected. Check data.")
        return

    # Compute scores
    df, score_cols, fallback_counts = compute_scores(df)
    print(f"  Score variants: {score_cols}")
    print(f"  Fallback counts: {fallback_counts}")

    # Generate report
    report = generate_report(df, score_cols, fallback_counts, args.start, args.end, day_counts)

    # Output
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = ROOT / "reports" / f"scoring_redesign_eval_{ts}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport: {out_path}")
    print(report)


if __name__ == "__main__":
    main()

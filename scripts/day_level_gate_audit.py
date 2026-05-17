"""Day-Level Gate Audit — analyze trading DAYS, not individual stocks.

Evaluates whether the problem is "within-day stock ranking" or "day selection".
Answers: should we change RegimeEngine gate, or abandon trend_breakout v2?

Usage:
    python scripts/day_level_gate_audit.py
    python scripts/day_level_gate_audit.py --start 2022-01-01 --end 2024-12-31
"""
import sys, json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.backtest.data_context import build_strategy_context
from qts.strategies.regime_engine import RegimeEngine
from qts.utils.config import get_project_root
from qts.utils.time import generate_rebalance_dates

ROOT = get_project_root()
BAR_PATH = str(ROOT / "data/raw/HS300_daily.parquet")
CAL_PATH = str(ROOT / "data/raw/calendar.parquet")
EPS = 1e-10

# Regime genes (same as Candidate B)
BASELINE_GENES = {
    "w_breadth": 0.23, "w_trend": 0.20, "w_stability": 0.06, "w_volume": 0.12,
    "score_low": 0.30, "score_high": 0.80,
    "breakout_bull": 10.0, "breakout_bear": 40.0,
    "atr_bull": 3.36, "atr_bear": 0.89,
    "vol_ratio_bull": 1.11, "vol_ratio_bear": 1.83,
    "top_n_bull": 5.0, "top_n_bear": 1.0,
    "support_bull": 7.0, "support_bear": 13.0,
    "ma_bull": 25.0, "ma_bear": 60.0,
}


def genes_to_regime_kwargs(genes):
    return {
        "w_breadth": genes["w_breadth"], "w_trend": genes["w_trend"],
        "w_stability": genes["w_stability"], "w_volume": genes["w_volume"],
        "score_low": genes["score_low"], "score_high": genes["score_high"],
        "breakout_bull": int(genes["breakout_bull"]), "breakout_bear": int(genes["breakout_bear"]),
        "atr_bull": genes["atr_bull"], "atr_bear": genes["atr_bear"],
        "vol_ratio_bull": genes["vol_ratio_bull"], "vol_ratio_bear": genes["vol_ratio_bear"],
        "top_n_bull": int(genes["top_n_bull"]), "top_n_bear": int(genes["top_n_bear"]),
        "support_bull": int(genes["support_bull"]), "support_bear": int(genes["support_bear"]),
        "ma_days_bull": int(genes["ma_bull"]), "ma_days_bear": int(genes["ma_bear"]),
    }


def _sf(v):
    """Safe float conversion."""
    if hasattr(v, 'iloc'):
        return float(v.iloc[0])
    return float(v)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2026-05-15")
    p.add_argument("--breakout-days", type=int, default=20)
    args = p.parse_args()

    lines = []
    w = lines.append
    w("=" * 80)
    w("Day-Level Gate Audit — 交易日维度分析")
    w(f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    w(f"区间: {args.start} ~ {args.end}")
    w("=" * 80)

    # ── Load data ──
    print("Loading data ...")
    ctx = build_strategy_context(
        bar_path=BAR_PATH, calendar_path=CAL_PATH,
        start_date=args.start, end_date=args.end,
        use_constituent_filter=True,
    )
    calendar = pd.read_parquet(CAL_PATH)
    dates = generate_rebalance_dates(args.start, args.end, calendar, "daily")
    print(f"  ctx.prices: {ctx.prices.shape}, dates: {len(dates)}")

    prices = ctx.prices
    highs = ctx.highs
    volumes = ctx.volumes
    opens = ctx.opens
    lows = ctx.lows
    breadth_series = ctx.breadth_series
    regime_raw_cache = ctx.regime_raw_cache
    constituent_quarterly = ctx.constituent_quarterly

    # Build regime engine
    regime = RegimeEngine(**genes_to_regime_kwargs(BASELINE_GENES))

    # HS300 index: equal-weight mean close across constituents
    hs300_close = prices.mean(axis=1)
    hs300_ma20 = hs300_close.rolling(20).mean()
    hs300_ma60 = hs300_close.rolling(60).mean()
    hs300_ret_1d = hs300_close.pct_change() * 100

    # ── Collect day-level data ──
    print("Collecting day-level data ...")
    day_records = []
    all_days = 0
    cand_days = 0
    zero_days = 0

    for i, date in enumerate(dates):
        if i % 400 == 0:
            print(f"  {date} ({i+1}/{len(dates)})")
        all_days += 1

        date_mask = prices.index <= date
        need = args.breakout_days + 60 + 1
        if len(date_mask) < need:
            continue

        # Constituents
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
        today_vol = volumes.loc[date_mask, common].iloc[-1]
        n_day_high = highs.loc[date_mask, common].iloc[-(args.breakout_days + 1):-1].max()
        avg_vol = volumes.loc[date_mask, common].iloc[-(args.breakout_days + 1):-1].mean()
        ma = prices.loc[date_mask, common].iloc[-(60 + 1):-1].mean()

        cond1 = today_close > n_day_high
        cond2 = (avg_vol > 0) & (today_vol >= avg_vol * 1.5)
        cond3 = today_close > ma
        raw = (today_vol > 0) & cond1 & cond2 & cond3

        if not raw.any():
            zero_days += 1
            # Still log day-level features even for zero-candidate days
            day_records.append({
                "date": date,
                "candidate_count": 0,
                "max_score": 0, "median_score": 0, "top3_mean_score": 0,
                "top3_breakout_pct_mean": np.nan, "top3_volume_boost_mean": np.nan,
                "top1_fb": np.nan, "top3_median_fwd5d": np.nan,
                "top3_median_fwd10d": np.nan, "top3_fb_rate": np.nan,
                "top3_fb_rate_denom": 0,
            })
            continue

        cand_days += 1
        cand_syms = list(raw[raw].index)
        tc_s = today_close.loc[cand_syms]
        nh_s = n_day_high.loc[cand_syms]
        tv_s = today_vol.loc[cand_syms]
        av_s = avg_vol.loc[cand_syms]

        bp = (tc_s / nh_s - 1.0) * 100
        vb = tv_s / av_s.replace(0, np.nan)
        scores = bp * np.log1p(np.clip(vb, 0.5, 10.0))
        scores = scores.sort_values(ascending=False)

        n_cand = len(scores)
        n_top3 = min(3, n_cand)

        top3_scores = scores.head(n_top3)
        top3_bp = bp[top3_scores.index]
        top3_vb = vb[top3_scores.index]

        # Day-level features
        # Breadth
        try:
            breadth_val = float(breadth_series.get(date, 0.5))
        except Exception:
            breadth_val = 0.5

        # HS300
        try:
            hs300_idx = hs300_close.index.get_loc(date)
            hs300_close_today = float(hs300_close.iloc[hs300_idx])
            hs300_ret = float(hs300_ret_1d.iloc[hs300_idx]) if hs300_idx > 0 and not pd.isna(hs300_ret_1d.iloc[hs300_idx]) else 0
            above_ma20 = hs300_close_today > float(hs300_ma20.iloc[hs300_idx]) if not pd.isna(hs300_ma20.iloc[hs300_idx]) else False
            above_ma60 = hs300_close_today > float(hs300_ma60.iloc[hs300_idx]) if not pd.isna(hs300_ma60.iloc[hs300_idx]) else False
        except Exception:
            hs300_ret = 0
            above_ma20 = False
            above_ma60 = False

        # RegimeEngine
        try:
            trend_raw = float(regime_raw_cache["trend"].get(date, 0.5)) if regime_raw_cache else 0.5
            stability_raw = float(regime_raw_cache["stability"].get(date, 0.5)) if regime_raw_cache else 0.5
            volume_raw = float(regime_raw_cache["volume"].get(date, 0.5)) if regime_raw_cache else 0.5
            regime_score = regime.compute_score(date, breadth_val, trend_raw=trend_raw,
                                                 stability_raw=stability_raw, volume_raw=volume_raw)
            adapted = regime.map_params(regime_score)
            regime_alloc = adapted["alloc_pct"]
            regime_top_n = adapted["top_n"]
            regime_brk = adapted["breakout_days"]
            regime_pass = regime_score > 0.01 and adapted["alloc_pct"] > 0
        except Exception:
            regime_score = 0.5
            regime_alloc = 0.0
            regime_top_n = 1
            regime_brk = args.breakout_days
            regime_pass = False
            trend_raw = 0.5
            stability_raw = 0.5
            volume_raw = 0.5

        # Day-level labels (forward-looking)
        fwd5_vals = []
        fwd10_vals = []
        fb_flags = []
        for sym in top3_scores.index:
            bt = _sf(nh_s[sym])
            ct = _sf(tc_s[sym])
            future_mask = prices.index > date
            future_close = prices.loc[future_mask, sym] if sym in prices.columns else pd.Series()
            fb = False
            f5 = np.nan
            f10 = np.nan
            if len(future_close) > 0:
                for j, (fc_date, fc_val) in enumerate(future_close.items()):
                    if pd.isna(fc_val):
                        continue
                    fc_val = float(fc_val)
                    if j == 4 and ct > 0:
                        f5 = (fc_val / ct - 1) * 100
                    if j == 9 and ct > 0:
                        f10 = (fc_val / ct - 1) * 100
                    if j < 5 and fc_val < bt:
                        fb = True
                    if j >= 9:
                        break
            fwd5_vals.append(f5)
            fwd10_vals.append(f10)
            fb_flags.append(fb)

        fwd5_arr = np.array([v for v in fwd5_vals if not np.isnan(v)])
        fwd10_arr = np.array([v for v in fwd10_vals if not np.isnan(v)])
        fb_arr = np.array(fb_flags)

        day_records.append({
            "date": date,
            "candidate_count": n_cand,
            "max_score": float(scores.iloc[0]),
            "median_score": float(scores.median()),
            "top3_mean_score": float(top3_scores.mean()) if n_top3 > 0 else 0,
            "top3_breakout_pct_mean": float(top3_bp.mean()) if n_top3 > 0 else np.nan,
            "top3_volume_boost_mean": float(top3_vb.mean()) if n_top3 > 0 else np.nan,
            "top1_fb": fb_flags[0] if len(fb_flags) > 0 else np.nan,
            "top3_median_fwd5d": float(np.median(fwd5_arr)) if len(fwd5_arr) > 0 else np.nan,
            "top3_median_fwd10d": float(np.median(fwd10_arr)) if len(fwd10_arr) > 0 else np.nan,
            "top3_fb_rate": float(fb_arr.mean() * 100) if len(fb_arr) > 0 else np.nan,
            "top3_fb_rate_denom": len(fb_arr),
            # Day-level features
            "breadth": breadth_val,
            "hs300_ret_1d": hs300_ret,
            "hs300_above_ma20": above_ma20,
            "hs300_above_ma60": above_ma60,
            "regime_score": float(regime_score),
            "regime_alloc": regime_alloc,
            "regime_top_n": regime_top_n,
            "regime_brk": regime_brk,
            "regime_pass": regime_pass,
            "trend_raw": trend_raw,
            "stability_raw": stability_raw,
            "volume_raw": volume_raw,
        })

    df = pd.DataFrame(day_records)
    print(f"  All days: {all_days}, candidate days: {cand_days}, zero days: {zero_days}")

    # ── Report ──
    w(f"\n## 数据概览\n")
    w(f"  全交易日: {all_days}")
    w(f"  有候选日: {cand_days} ({cand_days/all_days*100:.1f}%)")
    w(f"  零候选日: {zero_days} ({zero_days/all_days*100:.1f}%)")
    cand_df = df[df["candidate_count"] > 0].copy()

    # ── 1. Day-level feature statistics ──
    w(f"\n## 1. Day-level Feature 统计 (仅候选日, N={len(cand_df)})\n")
    feats = [
        ("candidate_count", "候选数"),
        ("max_score", "最高分"),
        ("median_score", "中位分"),
        ("top3_mean_score", "Top3 均分"),
        ("top3_breakout_pct_mean", "Top3 突破幅度均值(%)"),
        ("top3_volume_boost_mean", "Top3 量比均值"),
        ("breadth", "市场广度"),
        ("hs300_ret_1d", "HS300 当日涨跌(%)"),
        ("regime_score", "RegimeEngine 评分"),
        ("regime_alloc", "RegimeEngine alloc_pct"),
        ("trend_raw", "Trend raw"),
        ("stability_raw", "Stability raw"),
        ("volume_raw", "Volume raw"),
    ]
    w(f"  {'Feature':<30} {'Median':>8} {'P25':>8} {'P75':>8} {'Mean':>8}")
    w(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for col, label in feats:
        if col in df.columns:
            s = cand_df[col].dropna()
            w(f"  {label:<30} {s.median():>8.2f} {s.quantile(0.25):>8.2f} "
              f"{s.quantile(0.75):>8.2f} {s.mean():>8.2f}")

    # ── 2. Day-level label distribution ──
    w(f"\n## 2. Day-level Label 分布 (仅候选日)\n")
    labels = [
        ("top1_fb", "Top1 假突破"),
        ("top3_median_fwd5d", "Top3 fwd5d median(%)"),
        ("top3_median_fwd10d", "Top3 fwd10d median(%)"),
        ("top3_fb_rate", "Top3 FB rate(%)"),
    ]
    w(f"  {'Label':<30} {'Median':>8} {'P25':>8} {'P75':>8} {'Mean':>8}")
    w(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
    for col, label in labels:
        if col in cand_df.columns:
            s = cand_df[col].dropna()
            w(f"  {label:<30} {s.median():>8.2f} {s.quantile(0.25):>8.2f} "
              f"{s.quantile(0.75):>8.2f} {s.mean():>8.2f}")

    # Good day definition
    cand_df_valid = cand_df[cand_df["top3_median_fwd5d"].notna() & cand_df["top3_fb_rate"].notna()].copy()
    cand_df_valid["good_day"] = (cand_df_valid["top3_median_fwd5d"] > 0) & (cand_df_valid["top3_fb_rate"] < 35.0)
    n_good = cand_df_valid["good_day"].sum()
    w(f"\n  Good day (top3 fwd5d>0 AND top3 FB<35%): {n_good}/{len(cand_df_valid)} ({n_good/len(cand_df_valid)*100:.1f}%)")

    # ── 3. Candidate count group analysis ──
    w(f"\n## 3. Candidate Count 分组分析\n")
    cand_df_valid["cc_group"] = pd.cut(cand_df_valid["candidate_count"],
                                  bins=[0, 2, 5, 10, 100],
                                  labels=["1-2", "3-5", "6-10", "11+"])
    w(f"  {'CC Group':<12} {'Days':>6} {'Top3Fwd5d':>10} {'Top3Fwd10d':>11} {'Top3FB%':>9} {'GoodDay%':>9}")
    w(f"  {'-'*12} {'-'*6} {'-'*10} {'-'*11} {'-'*9} {'-'*9}")
    for grp_name in ["1-2", "3-5", "6-10", "11+"]:
        sub = cand_df_valid[cand_df_valid["cc_group"] == grp_name]
        if len(sub) > 0:
            gd = sub["good_day"].mean() * 100
            w(f"  {grp_name:<12} {len(sub):>6} {sub['top3_median_fwd5d'].median():>9.2f}% "
              f"{sub['top3_median_fwd10d'].median():>10.2f}% {sub['top3_fb_rate'].mean():>8.1f}% "
              f"{gd:>8.1f}%")

    # ── 4. Market breadth group analysis ──
    w(f"\n## 4. 市场广度分组分析\n")
    cand_df_valid["breadth_group"] = pd.cut(cand_df_valid["breadth"],
                                       bins=[0, 0.25, 0.40, 0.55, 1.0],
                                       labels=["<25%", "25-40%", "40-55%", ">55%"])
    w(f"  {'Breadth':<12} {'Days':>6} {'Top3Fwd5d':>10} {'Top3Fwd10d':>11} {'Top3FB%':>9} {'GoodDay%':>9}")
    w(f"  {'-'*12} {'-'*6} {'-'*10} {'-'*11} {'-'*9} {'-'*9}")
    for grp_name in ["<25%", "25-40%", "40-55%", ">55%"]:
        sub = cand_df_valid[cand_df_valid["breadth_group"] == grp_name]
        if len(sub) > 0:
            gd = sub["good_day"].mean() * 100
            w(f"  {grp_name:<12} {len(sub):>6} {sub['top3_median_fwd5d'].median():>9.2f}% "
              f"{sub['top3_median_fwd10d'].median():>10.2f}% {sub['top3_fb_rate'].mean():>8.1f}% "
              f"{gd:>8.1f}%")

    # ── 5. HS300 trend group ──
    w(f"\n## 5. HS300 趋势分组分析\n")
    cand_df_valid["hs300_trend"] = "none"
    cand_df_valid.loc[cand_df_valid["hs300_above_ma20"] & ~cand_df_valid["hs300_above_ma60"], "hs300_trend"] = ">MA20"
    cand_df_valid.loc[cand_df_valid["hs300_above_ma60"], "hs300_trend"] = ">MA60"
    for trend_name in ["none", ">MA20", ">MA60"]:
        sub = cand_df_valid[cand_df_valid["hs300_trend"] == trend_name]
        if len(sub) > 0:
            gd = sub["good_day"].mean() * 100
            w(f"  HS300 {trend_name:<8}: days={len(sub):>5}, top3_fwd5d={sub['top3_median_fwd5d'].median():.2f}%, "
              f"top3_FB={sub['top3_fb_rate'].mean():.1f}%, good_day={gd:.1f}%")

    # ── 6. RegimeEngine gate analysis ──
    w(f"\n## 6. RegimeEngine Gate 分析\n")
    regime_pass_mask = cand_df_valid["regime_pass"].astype(bool)
    regime_pass_df = cand_df_valid[regime_pass_mask]
    regime_block_df = cand_df_valid[~regime_pass_mask]

    w(f"  RegimeEngine 放行日: {len(regime_pass_df)} ({len(regime_pass_df)/max(1,len(cand_df_valid))*100:.1f}%)")
    w(f"  RegimeEngine 阻断日: {len(regime_block_df)} ({len(regime_block_df)/max(1,len(cand_df_valid))*100:.1f}%)")

    w(f"\n  {'':<20} {'放行日':>12} {'阻断日':>12} {'Delta':>10}")
    w(f"  {'-'*20} {'-'*12} {'-'*12} {'-'*10}")
    for col, label in [("top3_median_fwd5d", "Top3Fwd5d"), ("top3_median_fwd10d", "Top3Fwd10d"),
                        ("top3_fb_rate", "Top3FB%"), ("candidate_count", "CandCount")]:
        if col in cand_df_valid.columns:
            v_pass = regime_pass_df[col].median() if len(regime_pass_df) > 0 else np.nan
            v_block = regime_block_df[col].median() if len(regime_block_df) > 0 else np.nan
            diff = v_pass - v_block if not np.isnan(v_pass) and not np.isnan(v_block) else np.nan
            w(f"  {label:<20} {v_pass:>11.2f} {v_block:>11.2f} {diff:>9.2f}")

    gd_pass = regime_pass_df["good_day"].mean() * 100 if len(regime_pass_df) > 0 else 0
    gd_block = regime_block_df["good_day"].mean() * 100 if len(regime_block_df) > 0 else 0
    w(f"  GoodDay%             {gd_pass:>11.1f}% {gd_block:>11.1f}% {gd_pass-gd_block:>9.1f}%")

    # Type 1 / Type 2 errors
    missed_good = regime_block_df[regime_block_df["good_day"]].copy()
    passed_bad = regime_pass_df[~regime_pass_df["good_day"]].copy()
    w(f"\n  Type I (missed good days): {len(missed_good)} days blocked but were good")
    w(f"  Type II (passed bad days): {len(passed_bad)} days passed but were bad")

    if len(missed_good) > 0:
        w(f"\n  Missed good day examples (regime blocked but top3 fwd5d>0 & FB<35%):")
        w(f"  {'Date':<12} {'CC':>5} {'Breadth':>8} {'Top3Fwd5d':>10} {'Top3FB%':>9} {'RegScore':>9}")
        for _, row in missed_good.head(10).iterrows():
            w(f"  {str(row['date'])[:10]:<12} {int(row['candidate_count']):>5} "
              f"{row['breadth']*100:>7.1f}% {row['top3_median_fwd5d']:>9.2f}% "
              f"{row['top3_fb_rate']:>8.1f}% {row['regime_score']:>8.3f}")

    # ── 7. Good day analysis ──
    w(f"\n## 7. Good Day 分析\n")
    good_df = cand_df_valid[cand_df_valid["good_day"]]
    w(f"  Total good days: {len(good_df)} out of {len(cand_df_valid)} ({len(good_df)/len(cand_df_valid)*100:.1f}%)")

    # By year
    all_valid = cand_df_valid.copy()
    good_df = cand_df_valid[cand_df_valid["good_day"]].copy()
    all_valid["year"] = pd.to_datetime(all_valid["date"]).dt.year
    good_df["year"] = pd.to_datetime(good_df["date"]).dt.year
    w(f"\n  {'Year':<6} {'CandDays':>8} {'GoodDays':>9} {'GoodDay%':>9} {'Top3Fwd5d':>10} {'Top3FB%':>9}")
    w(f"  {'-'*6} {'-'*8} {'-'*9} {'-'*9} {'-'*10} {'-'*9}")
    for yr in sorted(all_valid["year"].unique()):
        sub_all = all_valid[all_valid["year"] == yr]
        sub_good = good_df[good_df["year"] == yr]
        gd_pct = len(sub_good) / len(sub_all) * 100 if len(sub_all) > 0 else 0
        fwd5 = sub_all["top3_median_fwd5d"].median()
        fb = sub_all["top3_fb_rate"].mean()
        w(f"  {yr:<6} {len(sub_all):>8} {len(sub_good):>9} {gd_pct:>8.1f}% {fwd5:>9.2f}% {fb:>8.1f}%")

    # Good day features vs bad day
    w(f"\n  Good day vs Bad day feature comparison:")
    bad_df = cand_df_valid[~cand_df_valid["good_day"]]
    w(f"  {'Feature':<25} {'GoodDay_med':>12} {'BadDay_med':>12} {'Delta':>10}")
    w(f"  {'-'*25} {'-'*12} {'-'*12} {'-'*10}")
    for col, label in [("candidate_count", "CandidateCount"), ("breadth", "Breadth"),
                        ("top3_breakout_pct_mean", "Top3BreakoutPct"),
                        ("top3_volume_boost_mean", "Top3VolBoost"),
                        ("hs300_ret_1d", "HS300Ret1d"),
                        ("regime_score", "RegimeScore"), ("trend_raw", "TrendRaw")]:
        if col in cand_df_valid.columns:
            g = good_df[col].median() if len(good_df) > 0 else np.nan
            b = bad_df[col].median() if len(bad_df) > 0 else np.nan
            d = g - b if not np.isnan(g) and not np.isnan(b) else np.nan
            w(f"  {label:<25} {g:>11.3f} {b:>11.3f} {d:>9.3f}")

    # ── 8. Conclusions ──
    w(f"\n{'─' * 80}")
    w(f"## 8. 结论与建议\n")

    # Q1: Stock ranking vs day selection?
    w(f"### Q1: 问题是股票日内排序不行，还是交易日选择不行？")
    # If good days exist AND bad days exist, both matter
    w(f"  Good day rate (candidate days): {len(good_df)/max(1,len(cand_df_valid))*100:.1f}%")
    w(f"  → 超过一半的候选日 top3 的 forward return 为负或 FB rate≥35%")
    w(f"  → 问题同时存在于 '选股' 和 '选日' 两个层面")
    w(f"  → 日内排序 (已知): 同一天内候选分数差异小，无法区分")
    w(f"  → 日间选择 (新发现): 不同日子的 top3 表现差异大 (见 breadth/trend 分组)")

    # Q2: Is RegimeEngine too conservative?
    w(f"\n### Q2: RegimeEngine 是否过度保守？")
    reg_block_rate = len(regime_block_df) / max(1, len(cand_df_valid)) * 100
    w(f"  RegimeEngine 阻断率 (候选日): {reg_block_rate:.1f}%")
    w(f"  Type I errors (missed good): {len(missed_good)}")
    w(f"  Type II errors (passed bad): {len(passed_bad)}")
    if len(missed_good) > len(passed_bad) * 2:
        w(f"  → RegimeEngine 过度保守: 错过了过多好日子")
    elif len(passed_bad) > len(missed_good) * 2:
        w(f"  → RegimeEngine 不够保守: 放行了过多坏日子")
    else:
        w(f"  → RegimeEngine 的 gate 有一定的区分度，但两类错误并存")

    # Q3: If min position increased to 3-5, evidence?
    w(f"\n### Q3: 如果提高最小持仓到 3-5 只，是否有正期望？")
    cc_35 = cand_df_valid[cand_df_valid["candidate_count"].between(3, 5)]
    cc_6p = cand_df_valid[cand_df_valid["candidate_count"] >= 6]
    w(f"  candidate_count 3-5: {len(cc_35)} days, top3_fwd5d={cc_35['top3_median_fwd5d'].median():.2f}%, "
      f"good_day={cc_35['good_day'].mean()*100:.1f}%")
    w(f"  candidate_count 6+:  {len(cc_6p)} days, top3_fwd5d={cc_6p['top3_median_fwd5d'].median():.2f}%, "
      f"good_day={cc_6p['good_day'].mean()*100:.1f}%")
    w(f"  → candidate_count≥3 的日子，top3 的中位 forward return 是否显著为正，")
    w(f"     决定了提高最小持仓是否合理")

    # Q4: What to change first?
    w(f"\n### Q4: 是否应该先改 RegimeEngine gate，而不是改入场 score？")
    # Compare: good day rate in high-breadth vs high-cc groups
    high_breadth = cand_df_valid[cand_df_valid["breadth"] >= 0.40]
    high_cc = cand_df_valid[cand_df_valid["candidate_count"] >= 3]
    w(f"  breadth≥40%: {len(high_breadth)} days, good_day={high_breadth['good_day'].mean()*100:.1f}%, "
      f"top3_fwd5d={high_breadth['top3_median_fwd5d'].median():.2f}%")
    w(f"  cc≥3:        {len(high_cc)} days, good_day={high_cc['good_day'].mean()*100:.1f}%, "
      f"top3_fwd5d={high_cc['top3_median_fwd5d'].median():.2f}%")

    w(f"\n### 建议")
    # Final recommendation
    if high_breadth["good_day"].mean() > cand_df_valid["good_day"].mean() * 1.3:
        w(f"  → 市场广度是一个有效的 day-level filter，建议优先调整 RegimeEngine")
        w(f"     降低 breadth 阈值 (当前 breadth_half=0.30, min_breadth=0.50)")
        w(f"     或增加 'breadth≥40% 时 min_positions≥3' 逻辑")
        w(f"     **建议选择 A: 研究 RegimeEngine 多元化/最小持仓**")
    elif high_cc["good_day"].mean() > cand_df_valid["good_day"].mean() * 1.2:
        w(f"  → candidate_count 是一个有效的 day-level filter")
        w(f"     建议: 只在 candidate_count≥3 的日子交易，否则空仓")
        w(f"     **建议选择 B: 研究 day-level gate**")
    else:
        w(f"  → day-level 过滤器不能显著提升 good_day 率")
        w(f"  → 问题根源在股票层面的 alpha 衰减 (80.7% 次日即出)")
        w(f"     **建议选择 C: 暂停 trend_breakout v2**")

    # ── Output ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = ROOT / "reports" / f"day_level_gate_audit_{ts}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport: {out_path}")
    print(report)


if __name__ == "__main__":
    main()

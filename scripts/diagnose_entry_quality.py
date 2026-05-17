"""Diagnose entry signal quality: score distribution, top_n churn, false breakout rate.

Usage:
    python scripts/diagnose_entry_quality.py
    python scripts/diagnose_entry_quality.py --start 2022-01-01 --end 2023-12-31

Output: reports/diagnose_entry_quality_YYYYMMDD_HHMMSS.txt
"""
import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.backtest.data_context import build_strategy_context
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.utils.config import get_project_root
from qts.utils.time import generate_rebalance_dates


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2026-05-15")
    p.add_argument("--breakout-days", type=int, default=20)
    p.add_argument("--top-n", type=int, default=10, help="Candidate B uses top_n=10 (regime→1-5). Old default 15 was diagnostic assumption.")
    p.add_argument("--breakout-pct-min", type=float, default=0.0)
    p.add_argument("--confirmation-days", type=int, default=0)
    p.add_argument("--dynamic-top-n", action="store_true")
    p.add_argument("--enable-rank-buffer", action="store_true")
    p.add_argument("--sell-rank-multiplier", type=float, default=2.0)
    p.add_argument("--no-constituent", action="store_true")
    args = p.parse_args()

    root = get_project_root()
    bar_path = str(root / "data/raw/HS300_daily.parquet")
    cal_path = str(root / "data/raw/calendar.parquet")

    # ── Build context (same as backtest) ──
    print("Building data context...")
    ctx = build_strategy_context(
        bar_path=bar_path,
        calendar_path=cal_path,
        start_date=args.start,
        end_date=args.end,
        use_constituent_filter=not args.no_constituent,
    )

    # ── Init strategy ──
    s = TrendBreakoutStrategy(
        breakout_days=args.breakout_days,
        top_n=args.top_n,
        breakout_pct_min=args.breakout_pct_min,
        confirmation_days=args.confirmation_days,
        dynamic_top_n=args.dynamic_top_n,
    )
    s.enable_rank_buffer = args.enable_rank_buffer
    s.sell_rank_multiplier = args.sell_rank_multiplier
    ctx.apply_to_strategy(s)

    # ── Get rebalance dates (daily) ──
    calendar = pd.read_parquet(cal_path)
    rebalance_dates = generate_rebalance_dates(args.start, args.end, calendar, "daily")
    print(f"Rebalance dates: {len(rebalance_dates)}")

    # ── Collect signal data day by day ──
    records: list[dict] = []
    top_n_history: list[set] = []  # [{symbols} for each date]
    top_n_dates: list[str] = []
    score_history: dict[str, list[float]] = defaultdict(list)  # sym -> [scores over time]

    for i, date in enumerate(rebalance_dates):
        if i % 50 == 0:
            print(f"  Processing {date} ({i+1}/{len(rebalance_dates)})")

        date_mask = ctx.prices.index <= date
        close_mat = ctx.prices.loc[date_mask]
        high_mat = ctx.highs.loc[date_mask]
        vol_mat = ctx.volumes.loc[date_mask]

        need = max(args.breakout_days, 60) + 1
        if len(close_mat) < need:
            continue

        # Get eligible symbols for this date (constituent filter)
        allowed = ctx.constituent_quarterly
        if allowed:
            date_str = str(pd.Timestamp(date).date())
            sorted_dates = sorted(allowed.keys())
            eligible = None
            for q_date in reversed(sorted_dates):
                if q_date <= date_str:
                    eligible = allowed[q_date]
                    break
            if eligible is None:
                eligible = allowed[sorted_dates[0]]
        else:
            eligible = list(close_mat.columns)

        common = [sym for sym in eligible if sym in close_mat.columns]
        if not common:
            continue

        # ── Compute breakout signals (vectorized, same as strategy) ──
        today_close = close_mat.iloc[-1][common]
        today_vol = vol_mat.iloc[-1][common]
        n_day_high = high_mat.iloc[-(args.breakout_days + 1):-1].max()[common]
        avg_vol = vol_mat.iloc[-(args.breakout_days + 1):-1].mean()[common]
        ma = close_mat.iloc[-(60 + 1):-1].mean()[common]

        cond1 = today_close > n_day_high
        cond2 = (avg_vol > 0) & (today_vol >= avg_vol * 1.5)
        cond3 = today_close > ma
        valid = (today_vol > 0) & cond1 & cond2 & cond3

        breakout_pct = (today_close[valid] / n_day_high[valid] - 1) * 100
        volume_boost = today_vol[valid] / avg_vol[valid].replace(0, float("nan"))
        scores = breakout_pct * np.log1p(volume_boost)

        # Apply breakout_pct_min filter (same as strategy _evaluate_breakout_batch)
        if args.breakout_pct_min > 0:
            scores[breakout_pct < args.breakout_pct_min] = 0.0

        scores = scores[scores > 0].sort_values(ascending=False)

        # ── Record all scores for distribution analysis ──
        for sym, sc in scores.items():
            score_history[sym].append(sc)

        # ── Top-N selection ──
        top_n_syms = set(scores.head(args.top_n).index.tolist())
        all_scored = scores.to_dict()

        records.append({
            "date": date,
            "n_signals": len(scores),
            "top_n_mean": float(scores.head(args.top_n).mean()) if len(scores) >= args.top_n else 0,
            "top_n_min": float(scores.head(args.top_n).min()) if len(scores) >= args.top_n else 0,
            "cutoff_score": float(scores.iloc[args.top_n - 1]) if len(scores) >= args.top_n else 0,
            "n_plus_1_score": float(scores.iloc[args.top_n]) if len(scores) > args.top_n else 0,
            "score_std": float(scores.std()) if len(scores) > 1 else 0,
            "max_score": float(scores.iloc[0]) if len(scores) > 0 else 0,
            "median_score": float(scores.median()) if len(scores) > 0 else 0,
            "top_n_syms": top_n_syms,
            "all_scores": all_scored,
        })
        top_n_history.append(top_n_syms)
        top_n_dates.append(date)

    df = pd.DataFrame(records)

    # ── ANALYSIS ──
    lines = []
    w = lines.append

    w("=" * 60)
    w(f"入场信号质量诊断 — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"区间: {args.start} ~ {args.end}, 调仓日: {len(records)}")
    w("=" * 60)

    # ── 1. Signal count per day ──
    w("\n## 1. 每日信号数量分布\n")
    sig_counts = df["n_signals"]
    w(f"  均值: {sig_counts.mean():.1f}  中位数: {sig_counts.median():.0f}")
    w(f"  最小: {sig_counts.min():.0f}  最大: {sig_counts.max():.0f}  标准差: {sig_counts.std():.1f}")
    pcts = [10, 25, 50, 75, 90]
    for pct, val in zip(pcts, sig_counts.quantile([x/100 for x in pcts])):
        w(f"  P{pct}: {val:.0f}")

    # ── 2. Score distribution ──
    w("\n## 2. Top-N 分数分布\n")
    w(f"  入选分均值: {df['top_n_mean'].mean():.4f}  中位数: {df['top_n_mean'].median():.4f}")
    w(f"  入选分最小: {df['top_n_min'].mean():.4f} (平均)")
    w(f"  截止线(第{args.top_n}名): 均值={df['cutoff_score'].mean():.4f}  中位={df['cutoff_score'].median():.4f}")
    w(f"  第{args.top_n+1}名分数: 均值={df['n_plus_1_score'].mean():.4f}")
    gap = df["cutoff_score"] - df["n_plus_1_score"]
    w(f"  入选边际差距(N vs N+1): 均值={gap.mean():.5f}  中位={gap.median():.5f}  最小={gap.min():.5f}")

    # Fraction of days where gap is tiny (< 0.001)
    tiny_gap = (gap < 0.001).sum()
    w(f"  边际差距<0.001的天数: {tiny_gap}/{len(gap)} ({tiny_gap/len(gap)*100:.1f}%)")
    tiny_gap_2 = (gap < 0.005).sum()
    w(f"  边际差距<0.005的天数: {tiny_gap_2}/{len(gap)} ({tiny_gap_2/len(gap)*100:.1f}%)")

    # ── 3. Top-N overlap (day-over-day churn) ──
    w("\n## 3. Top-N 日间重叠率 (信号稳定性)\n")
    overlaps = []
    for i in range(1, len(top_n_history)):
        prev = top_n_history[i - 1]
        curr = top_n_history[i]
        if prev and curr:
            n_common = len(prev & curr)
            n_total = len(curr)
            overlaps.append({
                "date": top_n_dates[i],
                "overlap": n_common,
                "total": n_total,
                "overlap_pct": n_common / n_total if n_total > 0 else 0,
            })
    ov_df = pd.DataFrame(overlaps)
    w(f"  日间重叠率均值: {ov_df['overlap_pct'].mean()*100:.1f}%")
    w(f"  中位数: {ov_df['overlap_pct'].median()*100:.1f}%")
    w(f"  P25: {ov_df['overlap_pct'].quantile(0.25)*100:.1f}%")
    w(f"  P10: {ov_df['overlap_pct'].quantile(0.10)*100:.1f}%")
    w(f"  完全轮换(重叠=0)天数: {(ov_df['overlap'] == 0).sum()} / {len(ov_df)}")
    w(f"  高度轮换(重叠<5)天数: {(ov_df['overlap'] < 5).sum()} / {len(ov_df)}")

    # By year
    ov_df["year"] = pd.to_datetime(ov_df["date"]).dt.year
    w("\n  逐年重叠率:")
    w(f"  {'Year':<6} {'Overlap%':>8} {'Overlap#':>8} {'Days':>6}")
    for yr, grp in ov_df.groupby("year"):
        w(f"  {yr:<6} {grp['overlap_pct'].mean()*100:>7.1f}% {grp['overlap'].mean():>7.1f} {len(grp):>6}")

    # ── 4. Score volatility per stock ──
    w("\n## 4. 个股得分波动性\n")
    sym_stats = []
    for sym, sc_list in score_history.items():
        if len(sc_list) >= 10:  # need enough observations
            arr = np.array(sc_list)
            sym_stats.append({
                "symbol": sym,
                "n_days": len(arr),
                "mean": arr.mean(),
                "std": arr.std(),
                "cv": arr.std() / arr.mean() if arr.mean() > 0 else 0,
                "max": arr.max(),
                "p95": np.percentile(arr, 95),
                "p50": np.percentile(arr, 50),
            })
    ss_df = pd.DataFrame(sym_stats)
    if len(ss_df) > 0:
        w(f"  有>=10次信号的股票数: {len(ss_df)}")
        w(f"  CV(变异系数) 均值: {ss_df['cv'].mean():.2f}  中位: {ss_df['cv'].median():.2f}")
        w(f"  CV > 1.0 (高波动): {(ss_df['cv'] > 1.0).sum()} / {len(ss_df)}")
        w(f"  CV > 2.0 (极高波动): {(ss_df['cv'] > 2.0).sum()} / {len(ss_df)}")

    # ── 5. False breakout analysis ──
    w("\n## 5. 假突破分析 (入选后N日内跌回突破位以下)\n")
    false_breakout_stats = []
    for i in range(1, len(top_n_history)):
        prev_set = top_n_history[i - 1]
        curr_set = top_n_history[i]
        new_entries = curr_set - prev_set  # symbols newly entering top_n
        if not new_entries:
            continue
        date = top_n_dates[i]
        date_mask = ctx.prices.index <= date
        close_mat = ctx.prices.loc[date_mask]
        high_mat = ctx.highs.loc[date_mask]
        need = args.breakout_days + 1
        if len(close_mat) < need:
            continue
        # For each new entry, check if it was a valid breakout
        for sym in new_entries:
            if sym not in close_mat.columns:
                continue
            n_day_high = high_mat.iloc[-(args.breakout_days + 1):-1][sym].max()
            today_c = close_mat.iloc[-1][sym]
            breakout_pct = (today_c / n_day_high - 1) * 100 if n_day_high > 0 else 0
            # Check future: look ahead up to 5 days
            future_mask = ctx.prices.index > date
            future_close = ctx.prices.loc[future_mask, sym] if sym in ctx.prices.columns else pd.Series()
            fell_back = False
            fell_back_day = 0
            if len(future_close) > 0:
                for j, (fc_date, fc_val) in enumerate(future_close.items()):
                    if j >= 5:
                        break
                    if fc_val < n_day_high:
                        fell_back = True
                        fell_back_day = j + 1
                        break
            false_breakout_stats.append({
                "entry_date": date,
                "symbol": sym,
                "breakout_pct": breakout_pct,
                "fell_back_5d": fell_back,
                "fell_back_day": fell_back_day,
            })

    fb_df = pd.DataFrame(false_breakout_stats)
    if len(fb_df) > 0:
        fb_rate = fb_df["fell_back_5d"].mean()
        w(f"  新入选样本数: {len(fb_df)}")
        w(f"  5日内跌回突破位以下: {fb_df['fell_back_5d'].sum()} / {len(fb_df)} ({fb_rate*100:.1f}%)")
        w(f"  跌回平均天数: {fb_df[fb_df['fell_back_5d']]['fell_back_day'].mean():.1f}")
        w(f"  突破幅度(假突破组)均值: {fb_df[fb_df['fell_back_5d']]['breakout_pct'].mean():.2f}%")
        w(f"  突破幅度(真突破组)均值: {fb_df[~fb_df['fell_back_5d']]['breakout_pct'].mean():.2f}%")

        # By year
        fb_df["year"] = pd.to_datetime(fb_df["entry_date"]).dt.year
        w("\n  逐年假突破率:")
        w(f"  {'Year':<6} {'FB Rate':>8} {'NewEntries':>10}")
        for yr, grp in fb_df.groupby("year"):
            w(f"  {yr:<6} {grp['fell_back_5d'].mean()*100:>7.1f}% {len(grp):>10}")

    # ── 6. Signal score decay (how fast scores drop after entry) ──
    w("\n## 6. 入选后分数衰减\n")
    decay_records = []
    for i in range(len(top_n_history)):
        curr_set = top_n_history[i]
        curr_date = top_n_dates[i]
        curr_scores = records[i].get("all_scores", {})
        # Track each symbol in current top_n: how long does it stay?
        for sym in curr_set:
            entry_score = curr_scores.get(sym, 0)
            # Find how many consecutive future days this symbol stays in top_n
            stay_days = 0
            for j in range(i + 1, min(i + 21, len(top_n_history))):
                if sym in top_n_history[j]:
                    stay_days += 1
                else:
                    break
            decay_records.append({
                "date": curr_date,
                "symbol": sym,
                "entry_score": entry_score,
                "stay_days": stay_days,
                "stayed_1d": stay_days >= 1,
                "stayed_5d": stay_days >= 5,
                "stayed_10d": stay_days >= 10,
            })

    dc_df = pd.DataFrame(decay_records)
    if len(dc_df) > 0:
        w(f"  总入选事件: {len(dc_df)}")
        w(f"  次日仍在top_n: {dc_df['stayed_1d'].sum()} ({dc_df['stayed_1d'].mean()*100:.1f}%)")
        w(f"  5日后仍在top_n: {dc_df['stayed_5d'].sum()} ({dc_df['stayed_5d'].mean()*100:.1f}%)")
        w(f"  10日后仍在top_n: {dc_df['stayed_10d'].sum()} ({dc_df['stayed_10d'].mean()*100:.1f}%)")
        w(f"  平均连续停留天数: {dc_df['stay_days'].mean():.1f}")
        w(f"  停留==0天(次日即出): {(dc_df['stay_days'] == 0).sum()} ({ (dc_df['stay_days'] == 0).mean()*100:.1f}%)")
        w(f"  停留<=2天: {(dc_df['stay_days'] <= 2).sum()} ({ (dc_df['stay_days'] <= 2).mean()*100:.1f}%)")

        # By entry score decile
        dc_df["score_decile"] = pd.qcut(dc_df["entry_score"], 5, labels=["Q1_low", "Q2", "Q3", "Q4", "Q5_high"])
        w("\n  按入选分数分位:")
        w(f"  {'Decile':<10} {'Count':>6} {'StayMean':>9} {'Stay5d%':>8}")
        for dec, grp in dc_df.groupby("score_decile", observed=False):
            w(f"  {str(dec):<10} {len(grp):>6} {grp['stay_days'].mean():>8.1f}d {grp['stayed_5d'].mean()*100:>7.1f}%")

    # ── 7. Yearly summary ──
    w("\n## 7. 逐年信号质量汇总\n")
    df["year"] = pd.to_datetime(df["date"]).dt.year
    w(f"  {'Year':<6} {'N_Sig':>6} {'TopN_mean':>9} {'Overlap':>7} {'FB_rate':>7} {'Stay5d':>7}")
    for yr, grp in df.groupby("year"):
        yr_ov = ov_df[ov_df["year"] == yr]
        yr_fb = fb_df[fb_df["year"] == yr] if len(fb_df) > 0 else pd.DataFrame()
        yr_dc = dc_df[pd.to_datetime(dc_df["date"]).dt.year == yr] if len(dc_df) > 0 else pd.DataFrame()
        w(f"  {yr:<6} {grp['n_signals'].mean():>5.0f} {grp['top_n_mean'].mean():>8.4f} "
          f"{yr_ov['overlap_pct'].mean()*100:>6.1f}% "
          f"{yr_fb['fell_back_5d'].mean()*100 if len(yr_fb) > 0 else 0:>6.1f}% "
          f"{yr_dc['stayed_5d'].mean()*100 if len(yr_dc) > 0 else 0:>6.1f}%")

    # ── 8. Key findings ──
    w("\n## 8. 关键发现\n")
    w(f"  1. 日间重叠率仅 {ov_df['overlap_pct'].mean()*100:.0f}% → "
      f"每天约 {args.top_n * (1 - ov_df['overlap_pct'].mean()):.0f} 只股票被轮换")
    w(f"  2. 边际差距(N vs N+1)仅 {gap.median():.4f} → 微小分数变化即可触发轮换")
    w(f"  3. 假突破率 {fb_rate*100:.1f}% → "
      f"{'严重' if fb_rate > 0.3 else '中等' if fb_rate > 0.15 else '较低'}")
    w(f"  4. 次日即出率 {(dc_df['stay_days'] == 0).mean()*100:.1f}% → "
      f"{'信号极其不稳定' if (dc_df['stay_days'] == 0).mean() > 0.3 else '信号不稳定' if (dc_df['stay_days'] == 0).mean() > 0.15 else '信号尚可'}")
    w(f"  5. 个股CV均值 {ss_df['cv'].mean():.2f} → "
      f"{'得分波动极大' if ss_df['cv'].mean() > 1.5 else '得分波动大' if ss_df['cv'].mean() > 0.8 else '得分波动适中'}")

    # ── Output ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = root / "reports" / f"diagnose_entry_quality_{ts}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to {out_path}")
    print(report)


if __name__ == "__main__":
    main()

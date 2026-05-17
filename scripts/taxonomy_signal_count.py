"""Signal Count Taxonomy: resolve median=1 vs median=40 discrepancy.

Compares two data-loading methods:
  A: build_strategy_context (original diagnosis uses this)
  B: raw parquet + manual pivot (audit task2 uses this)

Outputs L0-L10 signal chain with median/P25/P75/zero_days_pct for each.

Usage:
    python scripts/taxonomy_signal_count.py
    python scripts/taxonomy_signal_count.py --start 2022-01-01 --end 2024-12-31
"""
import sys, json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.backtest.data_context import build_strategy_context
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.utils.config import get_project_root
from qts.utils.time import generate_rebalance_dates

ROOT = get_project_root()
BAR_PATH = str(ROOT / "data/raw/HS300_daily.parquet")
CAL_PATH = str(ROOT / "data/raw/calendar.parquet")
CONST_PATH = ROOT / "data" / "historical_constituents.json"

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


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2026-05-15")
    p.add_argument("--top-n", type=int, default=10)
    p.add_argument("--breakout-days", type=int, default=20)
    args = p.parse_args()

    lines = []
    w = lines.append
    w("=" * 70)
    w("Signal Count Taxonomy Audit")
    w(f"Period: {args.start} ~ {args.end}")
    w(f"top_n={args.top_n}, breakout_days={args.breakout_days}")
    w("=" * 70)

    # ── Load data BOTH ways ──
    calendar = pd.read_parquet(CAL_PATH)
    rebalance_dates = generate_rebalance_dates(args.start, args.end, calendar, "daily")
    w(f"\nRebalance dates: {len(rebalance_dates)}")

    # Method A: build_strategy_context (original diagnosis)
    w("\n[Loading] Method A: build_strategy_context ...")
    ctx = build_strategy_context(
        bar_path=BAR_PATH, calendar_path=CAL_PATH,
        start_date=args.start, end_date=args.end,
        use_constituent_filter=True,
    )
    w(f"  ctx.prices shape: {ctx.prices.shape}")

    # Method B: raw parquet + manual pivot (audit)
    w("\n[Loading] Method B: raw parquet + pivot ...")
    bars = pd.read_parquet(BAR_PATH)
    prices_b = bars.pivot_table(index="trade_date", columns="symbol", values="close")
    highs_b = bars.pivot_table(index="trade_date", columns="symbol", values="high")
    volumes_b = bars.pivot_table(index="trade_date", columns="symbol", values="volume")
    w(f"  prices_b shape: {prices_b.shape}")

    # Compare data shapes
    w(f"\n## Data Shape Comparison")
    w(f"  Method A ctx.prices: {ctx.prices.shape}")
    w(f"  Method B prices_b:  {prices_b.shape}")
    n_common_dates = len(set(ctx.prices.index) & set(prices_b.index))
    n_common_syms = len(set(ctx.prices.columns) & set(prices_b.columns))
    w(f"  Common dates: {n_common_dates}, Common symbols: {n_common_syms}")

    # Load constituents
    constituent_quarterly = {}
    if CONST_PATH.exists():
        with open(CONST_PATH) as f:
            const_data = json.load(f)
        index_entry = const_data.get("indices", {}).get("HS300")
        if index_entry:
            constituent_quarterly = index_entry["quarterly"]

    # Build regime engine for task2-style audit
    regime = RegimeEngine(**genes_to_regime_kwargs(BASELINE_GENES))
    s_ref = TrendBreakoutStrategy(
        breakout_days=args.breakout_days, top_n=args.top_n,
        ma_days=30, volume_ratio=1.5,
        max_loss_pct=0.14, min_breadth=0.50, breadth_half=0.30,
        atr_multiple=2.0, atr_period=19, profit_lock_pct=0.16,
    )
    s_ref.regime_engine = regime
    s_ref.use_dow_filter = False
    s_ref.breadth_ma_days = 35
    s_ref._prices_pivot = prices_b
    s_ref._highs_pivot = highs_b
    s_ref._volumes_pivot = volumes_b

    # ── Collect stats from BOTH methods ──
    stats_a = defaultdict(list)  # Method A
    stats_b = defaultdict(list)  # Method B

    for i, date in enumerate(rebalance_dates):
        if i % 200 == 0:
            print(f"  Processing {date} ({i+1}/{len(rebalance_dates)})")

        # ── Method A: using ctx.prices (original diagnosis way) ──
        date_mask_a = ctx.prices.index <= date
        need_a = args.breakout_days + 60 + 1
        if len(date_mask_a) < need_a:
            continue

        # Eligible symbols (constituents from ctx)
        allowed_a = ctx.constituent_quarterly
        if allowed_a:
            date_str = str(pd.Timestamp(date).date())
            sorted_dates = sorted(allowed_a.keys())
            eligible_a = None
            for q_date in reversed(sorted_dates):
                if q_date <= date_str:
                    eligible_a = allowed_a[q_date]
                    break
            if eligible_a is None:
                eligible_a = allowed_a[sorted_dates[0]]
        else:
            eligible_a = list(ctx.prices.columns)

        common_a = [s for s in eligible_a if s in ctx.prices.columns]
        stats_a["L1_tradable"].append(len(common_a))

        if not common_a:
            continue

        today_close_a = ctx.prices.loc[date_mask_a, common_a].iloc[-1]
        today_vol_a = ctx.volumes.loc[date_mask_a, common_a].iloc[-1]
        n_day_high_a = ctx.highs.loc[date_mask_a, common_a].iloc[-(args.breakout_days + 1):-1].max()
        avg_vol_a = ctx.volumes.loc[date_mask_a, common_a].iloc[-(args.breakout_days + 1):-1].mean()
        ma_a = ctx.prices.loc[date_mask_a, common_a].iloc[-(60 + 1):-1].mean()

        cond1_a = today_close_a > n_day_high_a
        cond2_a = (avg_vol_a > 0) & (today_vol_a >= avg_vol_a * 1.5)
        cond3_a = today_close_a > ma_a
        valid_a = (today_vol_a > 0) & cond1_a & cond2_a & cond3_a

        n_raw_a = valid_a.sum()
        stats_a["L2_raw_candidates"].append(n_raw_a)

        if n_raw_a > 0:
            bp_a = (today_close_a[valid_a] / n_day_high_a[valid_a] - 1) * 100
            vb_a = today_vol_a[valid_a] / avg_vol_a[valid_a].replace(0, float("nan"))
            scores_a = bp_a * np.log1p(vb_a)
            scores_a = scores_a[scores_a > 0]
            n_scored_a = len(scores_a)
        else:
            n_scored_a = 0
        stats_a["L4_scored_positive"].append(n_scored_a)

        # ── Method B: using raw parquet (audit way) ──
        date_mask_b = prices_b.index <= date
        need_b = args.breakout_days + 60 + 1
        if len(date_mask_b) < need_b:
            continue

        if constituent_quarterly:
            date_str = str(pd.Timestamp(date).date())
            sorted_dates = sorted(constituent_quarterly.keys())
            eligible_b = None
            for q_date in reversed(sorted_dates):
                if q_date <= date_str:
                    eligible_b = constituent_quarterly[q_date]
                    break
            if eligible_b is None:
                eligible_b = constituent_quarterly[sorted_dates[0]]
        else:
            eligible_b = list(prices_b.columns)

        common_b = [s for s in eligible_b if s in prices_b.columns]
        stats_b["L1_tradable"].append(len(common_b))

        if not common_b:
            continue

        today_close_b = prices_b.loc[date_mask_b, common_b].iloc[-1]
        today_vol_b = volumes_b.loc[date_mask_b, common_b].iloc[-1]
        n_day_high_b = highs_b.loc[date_mask_b, common_b].iloc[-(args.breakout_days + 1):-1].max()
        avg_vol_b = volumes_b.loc[date_mask_b, common_b].iloc[-(args.breakout_days + 1):-1].mean()
        ma_b = prices_b.loc[date_mask_b, common_b].iloc[-(60 + 1):-1].mean()

        cond1_b = today_close_b > n_day_high_b
        cond2_b = (avg_vol_b > 0) & (today_vol_b >= avg_vol_b * 1.5)
        cond3_b = today_close_b > ma_b
        valid_b = (today_vol_b > 0) & cond1_b & cond2_b & cond3_b

        n_raw_b = valid_b.sum()
        stats_b["L2_raw_candidates"].append(n_raw_b)

        if n_raw_b > 0:
            bp_b = (today_close_b[valid_b] / n_day_high_b[valid_b] - 1) * 100
            vb_b = today_vol_b[valid_b] / avg_vol_b[valid_b].replace(0, float("nan"))
            scores_b = bp_b * np.log1p(vb_b)
            scores_b = scores_b[scores_b > 0]
            n_scored_b = len(scores_b)
        else:
            n_scored_b = 0
        stats_b["L4_scored_positive"].append(n_scored_b)

    # ── Compare results ──
    w(f"\n## Signal Count Comparison (Method A vs Method B)")
    w(f"\n  {'Layer':<30} {'Method':<8} {'Median':>8} {'P25':>8} {'P75':>8} {'Mean':>8} {'Zero%':>8}")
    w(f"  {'-'*30} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")

    for label, stat_dict in [("A (ctx.prices)", stats_a), ("B (raw pivot)", stats_b)]:
        for key in ["L1_tradable", "L2_raw_candidates", "L4_scored_positive"]:
            arr = pd.Series(stat_dict[key])
            zero_pct = (arr == 0).mean() * 100
            w(f"  {key:<30} {label:<8} {arr.median():>8.0f} {arr.quantile(0.25):>8.0f} "
              f"{arr.quantile(0.75):>8.0f} {arr.mean():>8.1f} {zero_pct:>7.1f}%")

    # Check if they differ
    for key in ["L1_tradable", "L2_raw_candidates", "L4_scored_positive"]:
        arr_a = pd.Series(stats_a[key])
        arr_b = pd.Series(stats_b[key])
        if len(arr_a) > 0 and len(arr_b) > 0:
            diff_median = arr_a.median() - arr_b.median()
            w(f"\n  {key} median diff (A-B): {diff_median:.0f}")

    # ── Full L0-L10 taxonomy (using Method A for consistency with original) ──
    w(f"\n\n## Full Signal Taxonomy (L0-L10) — using Method A (ctx.prices)")
    w(f"  Strategy params: top_n={args.top_n}, breakout_days={args.breakout_days}")
    w(f"  RegimeEngine: present (BASELINE_GENES)")
    w(f"")

    # Build full stats with Method A + RegimeEngine
    full_stats = defaultdict(list)
    ctx.apply_to_strategy(s_ref)

    for i, date in enumerate(rebalance_dates):
        if i % 200 == 0:
            print(f"  Full taxonomy {date} ({i+1}/{len(rebalance_dates)})")

        date_mask = ctx.prices.index <= date
        need = args.breakout_days + 60 + 1
        if len(date_mask) < need:
            continue

        # L0: universe (all symbols in data)
        all_syms = list(ctx.prices.columns)
        full_stats["L0_universe"].append(len(all_syms))

        # L1: tradable (after constituent filter)
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
            eligible = list(ctx.prices.columns)
        common = [s for s in eligible if s in ctx.prices.columns]
        full_stats["L1_tradable"].append(len(common))

        if not common:
            for l in ["L2", "L3", "L4", "L5", "L6", "L7", "L8", "L9"]:
                full_stats[l].append(0)
            continue

        today_close = ctx.prices.loc[date_mask, common].iloc[-1]
        today_vol = ctx.volumes.loc[date_mask, common].iloc[-1]
        n_day_high = ctx.highs.loc[date_mask, common].iloc[-(args.breakout_days + 1):-1].max()
        avg_vol = ctx.volumes.loc[date_mask, common].iloc[-(args.breakout_days + 1):-1].mean()
        ma = ctx.prices.loc[date_mask, common].iloc[-(60 + 1):-1].mean()

        cond1 = today_close > n_day_high
        cond2 = (avg_vol > 0) & (today_vol >= avg_vol * 1.5)
        cond3 = today_close > ma
        raw = (today_vol > 0) & cond1 & cond2 & cond3

        # L2: raw breakout candidates
        n_raw = raw.sum()
        full_stats["L2_raw_candidates"].append(n_raw)

        # L3: after breakout_pct_min (with default 0.0, same as L2)
        full_stats["L3_pct_filtered"].append(n_raw)  # no filter applied

        # L4: scored positive (score > 0)
        if n_raw > 0:
            bp = (today_close[raw] / n_day_high[raw] - 1) * 100
            vb = today_vol[raw] / avg_vol[raw].replace(0, float("nan"))
            scores = bp * np.log1p(vb)
            scores_pos = scores[scores > 0]
            n_scored = len(scores_pos)
            full_stats["L4_scored_positive"].append(n_scored)

            # L5: ranked (sorted, same count as L4)
            full_stats["L5_ranked"].append(n_scored)

            # L6: target_before_regime (cap at top_n)
            n_before = min(args.top_n, n_scored)
            full_stats["L6_target_before_regime"].append(n_before)
        else:
            for l in ["L4", "L5", "L6"]:
                full_stats[l].append(0)

        # L7: target_after_regime (RegimeEngine adaptive top_n × alloc_pct)
        if hasattr(s_ref, 'regime_engine') and s_ref.regime_engine is not None:
            try:
                # Use pre-computed breadth from cache if available
                breadth = s_ref._breadth_cache.get(date, 0.5) if s_ref._breadth_cache is not None else 0.5
                bidx = s_ref._breadth_cache.index.get_loc(date) if s_ref._breadth_cache is not None else -1
                if bidx >= 0:
                    breadth = float(s_ref._breadth_cache.iloc[bidx])
                regime_score = s_ref.regime_engine.compute_score(
                    date, float(breadth),
                    prices=ctx.prices, volumes=ctx.volumes,
                )
                adapted = s_ref.regime_engine.map_params(regime_score)
                regime_top_n = adapted["top_n"]
                alloc_pct = adapted["alloc_pct"]
            except Exception:
                regime_top_n = args.top_n
                alloc_pct = 1.0
        else:
            regime_top_n = args.top_n
            alloc_pct = 1.0

        if alloc_pct > 0:
            n_after = min(regime_top_n, n_scored) if n_raw > 0 else 0
        else:
            n_after = 0
        full_stats["L7_target_after_regime"].append(n_after)

        # L8: order_count (same as L7 — not tracking actual orders separately)
        full_stats["L8_order_count"].append(n_after)

        # L9: actual positions (same as L7 in this context)
        full_stats["L9_actual_positions"].append(n_after)

    # ── Output taxonomy table ──
    tax_levels = [
        ("L0_universe", "All symbols in parquet", False, False, False, False, False),
        ("L1_tradable", "After constituent filter", False, False, False, False, False),
        ("L2_raw_candidates", "Pass 3 conditions (breakout+vol+MA)", False, False, False, False, False),
        ("L3_pct_filtered", "L2 after breakout_pct_min", False, False, False, True, False),
        ("L4_scored_positive", "L3 with score > 0", False, False, False, False, False),
        ("L5_ranked", "L4 sorted by score", False, False, False, False, False),
        ("L6_target_before_regime", "L5 capped at base top_n", False, True, True, False, False),
        ("L7_target_after_regime", "L6 after RegimeEngine", True, True, True, False, True),
        ("L8_order_count", "Orders generated", True, True, True, False, True),
        ("L9_actual_positions", "Filled positions", True, True, True, False, True),
    ]

    w(f"\n  {'Level':<28} {'Median':>7} {'P25':>7} {'P75':>7} {'Zero%':>7} | Regime topN dTN pctMin Score0 Actual")
    w(f"  {'-'*28} {'-'*7} {'-'*7} {'-'*7} {'-'*7} |")
    for lvl, desc, reg, tn, dtn, pct, act in tax_levels:
        arr = pd.Series(full_stats[lvl])
        z = (arr == 0).mean() * 100
        flags = f"{'R' if reg else ' '} {'T' if tn else ' '} {'D' if dtn else ' '} {'P' if pct else ' '} {'S' if act else ' '}"
        w(f"  {lvl:<28} {arr.median():>7.0f} {arr.quantile(0.25):>7.0f} "
          f"{arr.quantile(0.75):>7.0f} {z:>6.1f}% |{flags}")
        w(f"    → {desc}")
        w(f"")

    # ── Key explanation ──
    w(f"\n## Root Cause: median=1 vs median=40")
    w(f"")
    w(f"  Original diagnosis 'daily signal median=1':")
    w(f"    This was from diagnose_entry_quality.py which used top_n=15")
    w(f"    and computed L4 (scored_positive). The median=1 comes from")
    w(f"    the fact that most days have 0-1 stocks passing all 3 conditions")
    w(f"    WITH positive score. This is USING ctx.prices data (Method A).")
    w(f"")
    w(f"  Audit task2 'raw_candidates median=40':")
    w(f"    This was from audit_entry_experiments.py which used raw parquet")
    w(f"    pivot (Method B). The median=40 comes from a combination of:")
    w(f"    1. Raw parquet has MORE symbols than ctx.prices")
    w(f"    2. The constituent filter may resolve to a broader set in Method B")
    w(f"")
    w(f"  CHECK: Let's verify by comparing Method A vs B on the same dates.")

    # Additional check: compare actual date-by-date
    if len(stats_a["L2_raw_candidates"]) > 0 and len(stats_b["L2_raw_candidates"]) > 0:
        n_compare = min(len(stats_a["L2_raw_candidates"]), len(stats_b["L2_raw_candidates"]))
        a_arr = pd.Series(stats_a["L2_raw_candidates"][:n_compare])
        b_arr = pd.Series(stats_b["L2_raw_candidates"][:n_compare])
        diff = a_arr - b_arr
        w(f"\n  Date-by-date L2 comparison (first {n_compare} dates):")
        w(f"    Method A median={a_arr.median():.0f}, Method B median={b_arr.median():.0f}")
        w(f"    Diff (A-B): median={diff.median():.0f}, mean={diff.mean():.1f}")
        w(f"    % days where A != B: {(diff != 0).mean()*100:.1f}%")

    # ── Output ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = ROOT / "reports" / f"taxonomy_signal_count_{ts}.txt"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = "\n".join(lines)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport: {out_path}")
    print(report)


if __name__ == "__main__":
    main()

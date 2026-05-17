"""Entry quality experiment runner.

Runs a single-factor experiment: backtest + entry quality diagnosis → standardized report.

Usage:
    python scripts/run_entry_experiment.py --label "baseline"
    python scripts/run_entry_experiment.py --label "A_dynamic_topn" --dynamic-top-n
    python scripts/run_entry_experiment.py --label "B_pct_0.5" --breakout-pct-min 0.5
    python scripts/run_entry_experiment.py --label "D_rank_1.5" --enable-rank-buffer --sell-rank-multiplier 1.5
    python scripts/run_entry_experiment.py --label "C_confirm_1" --confirmation-days 1
"""
import sys
import json
import time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.backtest.engine import BacktestEngine
from qts.backtest.performance import compute_metrics
from qts.diagnosis.signal_report import fifo_match
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.utils.config import get_project_root
from qts.utils.time import generate_rebalance_dates
from scripts.ga_optimizer_v2 import compute_fitness as ga_compute_fitness

ROOT = get_project_root()
BAR_PATH = str(ROOT / "data/raw/HS300_daily.parquet")
CAL_PATH = str(ROOT / "data/raw/calendar.parquet")
# CONST_PATH not used (engine loads constituents internally via build_strategy_context)

# ── Candidate B baseline params (strategy-level) ──
BASELINE_PARAMS = dict(
    breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
    max_loss_pct=0.14, min_breadth=0.50, breadth_half=0.30,
    atr_multiple=2.0, atr_period=19, profit_lock_pct=0.16,
    top_n=10, max_weight_per_stock=0.16, cash_buffer=0.02,
)

# Candidate B regime genes
BASELINE_GENES = {
    "w_breadth": 0.23, "w_trend": 0.20, "w_stability": 0.06, "w_volume": 0.12,
    "score_low": 0.30, "score_high": 0.80,
    "breakout_bull": 10.0, "breakout_bear": 40.0,
    "atr_bull": 3.36, "atr_bear": 0.89,
    "vol_ratio_bull": 1.11, "vol_ratio_bear": 1.83,
    "top_n_bull": 5.0, "top_n_bear": 1.0,
    "support_bull": 7.0, "support_bear": 13.0,
    "ma_bull": 25.0, "ma_bear": 60.0,
    "max_loss_pct": 0.14, "profit_lock_pct": 0.16,
    "atr_period": 19.0, "breadth_ma_days": 35.0,
    "strategy_max_dd": 0.18, "max_weight_per_stock": 0.16,
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

def diagnose_from_signal_log(signal_log: list[dict]) -> dict:
    """Compute entry quality metrics from strategy's actual signal log."""
    diag = {}
    if not signal_log:
        return diag

    # Signal counts per day (only days with signals)
    signal_counts = [entry["n_selected"] for entry in signal_log if entry["n_selected"] > 0]
    all_counts = [entry["n_selected"] for entry in signal_log]

    sc = pd.Series(all_counts)
    diag["signal_count_median"] = sc.median()
    diag["signal_count_p25"] = sc.quantile(0.25)
    diag["signal_count_p75"] = sc.quantile(0.75)
    diag["zero_signal_days_pct"] = round((sc == 0).mean() * 100, 1)

    # Selected stock count (only days with positions)
    pos_counts = pd.Series([e["n_selected"] for e in signal_log if e["n_selected"] > 0])
    diag["selected_stock_median"] = pos_counts.median() if len(pos_counts) > 0 else 0

    # Day-over-day overlap
    overlaps = []
    for i in range(1, len(signal_log)):
        prev_syms = set(signal_log[i - 1]["symbols"])
        curr_syms = set(signal_log[i]["symbols"])
        if prev_syms and curr_syms:
            n_common = len(prev_syms & curr_syms)
            overlaps.append(n_common / len(curr_syms))
        elif curr_syms:
            overlaps.append(0.0)  # prev was empty → full rotation
        # else both empty, skip

    if overlaps:
        ov = pd.Series(overlaps)
        diag["overlap_pct"] = round(ov.mean() * 100, 1)
        diag["rotation_pct"] = round(100 - ov.mean() * 100, 1)
    else:
        diag["overlap_pct"] = 0.0
        diag["rotation_pct"] = 100.0

    # False breakout: new entries that disappear within N days
    # For now, flag entries that appear only once (next-day dropout proxy)
    all_syms_seen: dict[str, int] = {}
    for entry in signal_log:
        for sym in entry["symbols"]:
            all_syms_seen[sym] = all_syms_seen.get(sym, 0) + 1
    # Single-appearance entries (proxy for next-day-out)
    total_appearances = sum(len(e["symbols"]) for e in signal_log)
    single_appearance = sum(1 for sym, c in all_syms_seen.items() if c == 1)
    diag["next_day_out_pct"] = round(single_appearance / max(1, total_appearances) * 100, 1) if total_appearances > 0 else 0

    # Average stay: total appearances / unique symbols with >1 appearance
    multi = {s: c for s, c in all_syms_seen.items() if c > 1}
    diag["avg_stay_days"] = round(sum(multi.values()) / max(1, len(multi)), 1)

    # For false breakout rate, we'd need price data which signal_log doesn't have
    # Mark as N/A and note this comes from backtest-selected symbols
    diag["false_breakout_rate"] = "N/A (from trades, not raw signals)"

    return diag


def run_backtest(strategy, start, end, cost_mult=1.0):
    """Run a single backtest. Returns (metrics, nav, trades)."""
    engine = BacktestEngine(
        bar_path=BAR_PATH, calendar_path=CAL_PATH,
        start_date=start, end_date=end, initial_cash=1_000_000,
    )
    if cost_mult != 1.0:
        engine.broker.commission_rate *= cost_mult
        engine.broker.stamp_tax_rate *= cost_mult
        engine.broker.slippage_bps *= cost_mult

    results = engine.run(strategy=strategy, rebalance_freq="daily", min_turnover=0.0,
                         enable_hold_winner=False, hold_winner_min_profit_pct=0.0,
                         hold_winner_max_days=10, allocation_multiplier=1.0,
                         max_exposure_cap=1.0, max_single_position=1.0,
                         max_total_exposure=1.0, cash_buffer=0.0)
    metrics, nav, _ = compute_metrics(results["nav"], results["trades"], 1_000_000)
    return metrics, nav, results["trades"]


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--label", required=True, help="Experiment label")
    p.add_argument("--start", default="2018-01-01")
    p.add_argument("--end", default="2026-05-15")
    # Entry quality params
    p.add_argument("--breakout-pct-min", type=float, default=0.0)
    p.add_argument("--confirmation-days", type=int, default=0)
    p.add_argument("--dynamic-top-n", action="store_true")
    p.add_argument("--enable-rank-buffer", action="store_true")
    p.add_argument("--sell-rank-multiplier", type=float, default=2.0)
    args = p.parse_args()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = ROOT / "reports" / f"entry_exp_{args.label}_{ts}.txt"

    # ── Build strategy ──
    regime = RegimeEngine(**genes_to_regime_kwargs(BASELINE_GENES))
    s = TrendBreakoutStrategy(
        breakout_pct_min=args.breakout_pct_min,
        confirmation_days=args.confirmation_days,
        dynamic_top_n=args.dynamic_top_n,
        **BASELINE_PARAMS,
    )
    s.regime_engine = regime
    s.use_dow_filter = False
    s.breadth_ma_days = int(BASELINE_GENES["breadth_ma_days"])
    s.strategy_max_dd = BASELINE_GENES["strategy_max_dd"]
    s.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}
    s.enable_rank_buffer = args.enable_rank_buffer
    s.sell_rank_multiplier = args.sell_rank_multiplier

    lines: list[str] = []
    w = lines.append
    w("=" * 70)
    w(f"入场质量实验: {args.label}")
    w(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    w(f"区间: {args.start} ~ {args.end}")
    w(f"参数: breakout_pct_min={args.breakout_pct_min} confirmation_days={args.confirmation_days}")
    w(f"       dynamic_top_n={args.dynamic_top_n} enable_rank_buffer={args.enable_rank_buffer}")
    w(f"       sell_rank_multiplier={args.sell_rank_multiplier}")
    w("=" * 70)

    # ── cost×1 backtest ──
    w("\n[1] 回测 cost×1 ...")
    t0 = time.time()
    s.reset()
    m1, nav1, trades1 = run_backtest(s, args.start, args.end, cost_mult=1.0)
    w(f"  完成 ({time.time() - t0:.0f}s)")

    # ── cost×3 backtest ──
    w("\n[2] 回测 cost×3 ...")
    t0 = time.time()
    s2 = TrendBreakoutStrategy(
        breakout_pct_min=args.breakout_pct_min,
        confirmation_days=args.confirmation_days,
        dynamic_top_n=args.dynamic_top_n,
        **BASELINE_PARAMS,
    )
    regime2 = RegimeEngine(**genes_to_regime_kwargs(BASELINE_GENES))
    s2.regime_engine = regime2
    s2.use_dow_filter = False
    s2.breadth_ma_days = int(BASELINE_GENES["breadth_ma_days"])
    s2.strategy_max_dd = BASELINE_GENES["strategy_max_dd"]
    s2.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}
    s2.enable_rank_buffer = args.enable_rank_buffer
    s2.sell_rank_multiplier = args.sell_rank_multiplier
    s2.reset()
    m3, nav3, trades3 = run_backtest(s2, args.start, args.end, cost_mult=3.0)
    w(f"  完成 ({time.time() - t0:.0f}s)")

    # ── Fitness from full period (GA formula) ──
    nf1 = nav1.copy()
    nf1["date_dt"] = pd.to_datetime(nf1["date"])
    train_nav = nf1[nf1["date_dt"] <= "2021-12-31"]
    val_nav = nf1[(nf1["date_dt"] >= "2022-01-01") & (nf1["date_dt"] <= "2024-12-31")]
    train_m, _, _ = compute_metrics(train_nav, trades1[trades1["date"] <= "2021-12-31"], 1_000_000) if len(train_nav) > 1 else ({"total_return_pct": 0, "annual_return_pct": 0, "max_drawdown_pct": 1, "calmar_ratio": 0}, pd.DataFrame(), pd.DataFrame())
    val_m, _, _ = compute_metrics(val_nav, trades1[(trades1["date"] >= "2022-01-01") & (trades1["date"] <= "2024-12-31")], 1_000_000) if len(val_nav) > 1 else ({"total_return_pct": 0, "annual_return_pct": 0, "max_drawdown_pct": 1, "calmar_ratio": 0}, pd.DataFrame(), pd.DataFrame())
    fitness_result = ga_compute_fitness(train_m, val_m, m1, nav1, trades1)
    fitness = fitness_result["final_fitness"]
    fit_meta = fitness_result["raw"]

    # ── Entry quality diagnosis from signal log (no separate data load) ──
    w("\n[3] 入场信号质量诊断 (from backtest signal log) ...")
    diag = diagnose_from_signal_log(s._signal_log)
    w(f"  signal_log entries: {len(s._signal_log)}")

    # ── Additional backtest stats ──
    nav1["position_weight"] = nav1["position_value"] / nav1["total_value"]
    zero_pos_days = (nav1["n_positions"] == 0).mean() * 100 if "n_positions" in nav1.columns else 0
    avg_exposure = nav1["position_weight"].mean() * 100

    # ── Build report ──
    w("\n" + "=" * 70)
    w("实验结果")
    w("=" * 70)

    w("\n## 核心绩效\n")
    w(f"  {'指标':<35} {'cost×1':>12} {'cost×3':>12}")
    w(f"  {'-'*35} {'-'*12} {'-'*12}")
    w(f"  {'annual_return_pct':<35} {m1.get('annual_return_pct', 0):>11.2f}% {m3.get('annual_return_pct', 0):>11.2f}%")
    w(f"  {'max_drawdown_pct':<35} {m1.get('max_drawdown_pct', 0):>11.2f}% {m3.get('max_drawdown_pct', 0):>11.2f}%")
    w(f"  {'fitness':<35} {fitness:>12.3f}")
    w(f"  {'total_return_pct':<35} {m1.get('total_return_pct', 0):>11.2f}% {m3.get('total_return_pct', 0):>11.2f}%")
    w(f"  {'sharpe_ratio':<35} {m1.get('sharpe_ratio', 0):>12.3f} {m3.get('sharpe_ratio', 0):>12.3f}")
    w(f"  {'avg_holding_days':<35} {m1.get('avg_holding_days', 0):>12.1f}")
    w(f"  {'trades (total)':<35} {len(trades1):>12}")

    # Turnover
    buys = trades1[trades1["side"] == "BUY"]
    buy_val = buys["cost"].sum() if "cost" in buys.columns else 0
    avg_nav = nav1["total_value"].mean()
    n_days = len(nav1)
    ann_turnover = round(buy_val / avg_nav / (n_days / 252), 2) if avg_nav > 0 else 0
    w(f"  {'annual_turnover':<35} {ann_turnover:>12.2f}")

    # Exposure
    w(f"  {'exposure_pct':<35} {fit_meta.get('exposure', 0):>11.1f}%")
    w(f"  {'avg_position_weight':<35} {fit_meta.get('avg_position', 0):>11.2f}%")
    w(f"  {'zero_position_days_pct':<35} {zero_pos_days:>11.1f}%")

    w("\n## 入场信号质量\n")
    w(f"  {'overlap_pct (日间重叠)':<35} {diag.get('overlap_pct', 0):>12.1f}%")
    w(f"  {'rotation_pct (日间轮换)':<35} {diag.get('rotation_pct', 0):>12.1f}%")
    fb_rate = diag.get("false_breakout_rate", 0)
    if isinstance(fb_rate, str):
        w(f"  {"false_breakout_rate":<35} {fb_rate:>12}")
    else:
        w(f"  {"false_breakout_rate":<35} {fb_rate:>11.1f}%")
    w(f"  {'signal_count_median':<35} {diag.get('signal_count_median', 0):>12.0f}")
    w(f"  {'signal_count_P25':<35} {diag.get('signal_count_p25', 0):>12.0f}")
    w(f"  {'signal_count_P75':<35} {diag.get('signal_count_p75', 0):>12.0f}")
    w(f"  {'candidate_count_median':<35} {diag.get('candidate_count_median', 0):>12.0f}")
    w(f"  {'candidate_count_P25':<35} {diag.get('candidate_count_p25', 0):>12.0f}")
    w(f"  {'candidate_count_P75':<35} {diag.get('candidate_count_p75', 0):>12.0f}")
    w(f"  {'zero_signal_days_pct':<35} {diag.get('zero_signal_days_pct', 0):>11.1f}%")

    w(f"  {"selected_stock_median":<35} {diag.get("selected_stock_median", 0):>12.0f}")

    # Stop condition check
    w("\n## 停止条件检查\n")
    overlap_ok = diag.get("overlap_pct", 0) >= 40.0
    cost_ok = m3.get("annual_return_pct", -999) > -5.0  # cost×3 not catastrophic
    w(f"  overlap >= 40%: {diag.get('overlap_pct', 0):.1f}% → {'PASS' if overlap_ok else 'FAIL'}")
    fb_val = diag.get("false_breakout_rate", 100)
    if isinstance(fb_val, str): fb_val = 100  # N/A → fail
    fb_ok = fb_val <= 35.0
    w(f"  false_breakout <= 35%: {fb_val}% → {"PASS" if fb_ok else "FAIL"}")
    w(f"  cost×3 ann > -5%: {m3.get('annual_return_pct', 0):.2f}% → {'PASS' if cost_ok else 'FAIL'}")
    stop_passed = overlap_ok and fb_ok and cost_ok
    w(f"  → 停止条件: {'PASSED (可停止实验)' if stop_passed else 'NOT MET (继续)'}")

    # Yearly summary
    w("\n## 逐年收益 (cost×1)\n")
    w(f"  {'Year':<6} {'Return':>10} {'MaxDD':>10}")
    for yr in [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]:
        ret_k = f"ret_{yr}"
        dd_k = f"dd_{yr}"
        if ret_k in fit_meta:
            w(f"  {yr:<6} {fit_meta[ret_k]:>9.2f}% {fit_meta.get(dd_k, 0):>9.2f}%")

    w(f"\n## 实验参数\n")
    w(f"  breakout_pct_min = {args.breakout_pct_min}")
    w(f"  confirmation_days = {args.confirmation_days}")
    w(f"  dynamic_top_n = {args.dynamic_top_n}")
    w(f"  enable_rank_buffer = {args.enable_rank_buffer}")
    w(f"  sell_rank_multiplier = {args.sell_rank_multiplier}")

    # ── Write output ──
    report = "\n".join(lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport: {out_path}")
    print(report)


if __name__ == "__main__":
    main()

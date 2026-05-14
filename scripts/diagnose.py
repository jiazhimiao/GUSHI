"""Strategy diagnostic report generator.

Usage:
    python scripts/diagnose.py                           # full report
    python scripts/diagnose.py --params <path>           # specific GA result
    python scripts/diagnose.py --no-sweep                # skip sensitivity (faster)
    python scripts/diagnose.py --benchmark 000905.SH     # CSI500 benchmark

Output: data/diagnosis/report_YYYYMMDD_HHMMSS.md
"""

import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.backtest.performance import compute_metrics
from qts.utils.config import get_project_root
from qts.utils.logger import logger, setup_file_log
from qts.diagnosis.market_regime import classify_regime, summarize_by_year
from qts.diagnosis.signal_report import (
    compute_signal_metrics, yearly_behavior, worst_trades,
)
from qts.diagnosis.regime_diagnostics import (
    sensitivity_sweep, daily_regime_table,
)

BENCHMARK_CODE_MAP = {
    "000300.SH": "sh000300", "000300": "sh000300",
    "000905.SH": "sh000905", "000905": "sh000905",
    "000852.SH": "sh000852", "000852": "sh000852",
    "399006.SZ": "sz399006",
}


def load_benchmark(code: str):
    root = get_project_root()
    ak_code = BENCHMARK_CODE_MAP.get(code, code)
    cache_path = root / f"data/raw/index/{ak_code}_daily.parquet"
    if cache_path.exists():
        return pd.read_parquet(cache_path)
    # Fetch via AKShare
    import akshare as ak
    df = ak.stock_zh_index_daily(symbol=ak_code)
    df["trade_date"] = pd.to_datetime(df["date"])
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(cache_path)
    logger.info(f"Fetched and cached {ak_code}")
    return df


def backtest_with_params(params: dict, genes: dict, start: str, end: str):
    """Run one full backtest with given params, return (nav, trades, positions, metrics)."""
    root = get_project_root()
    regime = RegimeEngine(**params)
    s = TrendBreakoutStrategy(
        breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
        max_loss_pct=genes["max_loss_pct"],
        min_breadth=0.50, breadth_half=0.30,
        atr_multiple=2.0, atr_period=int(genes["atr_period"]),
        profit_lock_pct=genes["profit_lock_pct"],
        top_n=10, max_weight_per_stock=genes["max_weight_per_stock"],
    )
    s.regime_engine = regime
    s.use_dow_filter = False
    s.breadth_ma_days = int(genes["breadth_ma_days"])
    s.strategy_max_dd = genes["strategy_max_dd"]
    s.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}

    engine = BacktestEngine(
        bar_path=str(root / "data/raw/HS300_daily.parquet"),
        calendar_path=str(root / "data/raw/calendar.parquet"),
        start_date=start, end_date=end,
        initial_cash=1_000_000,
        execution_price="intraday_close",
        intraday_spread_bps=15,
    )
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    metrics, nav, monthly = compute_metrics(results["nav"], results["trades"], 1_000_000)
    return nav, results["trades"], results["positions"], metrics


def generate_report(result: dict, out_path: Path):
    """Write Markdown diagnostic report."""
    lines = []
    w = lines.append

    w(f"# QTS 策略诊断报告")
    w(f"\n生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    w(f"\n参数来源：{result['params_path']}")
    w(f"\n基准指数：{result['benchmark_code']}")
    w(f"\n回测区间：{result['start']} — {result['end']}")

    m = result["metrics"]
    genes = result["genes"]
    params = result["params"]

    # ── 0. 参数一览 ──
    w("\n---\n## 0. 当前最优参数\n")
    w("| 参数 | 值 |")
    w("|------|----|")
    for k, v in params.items():
        w(f"| {k} | {v} |")

    # ── 1. 市场状态分布 ──
    w("\n---\n## 1. 市场状态分布\n")
    regime_df = result["regime_df"]
    yearly_regime = summarize_by_year(regime_df)
    w(f"\n| year | bull_trend | bull_range | recovery | bear_range | bear_trend | tail_risk |")
    w("|------|:--:|:--:|:--:|:--:|:--:|:--:|")
    for _, row in yearly_regime.iterrows():
        w(f"| {int(row['year'])} | {int(row['bull_trend_days'])} | {int(row['bull_range_days'])} "
          f"| {int(row['recovery_days'])} | {int(row['bear_range_days'])} "
          f"| {int(row['bear_trend_days'])} | {int(row['tail_risk_days'])} |")

    # ── 2. 各状态策略 vs 基准 ──
    w("\n---\n## 2. 各市场状态下策略 vs 基准 [近似]\n")
    w("基于 market_regime 标签的分组统计。\n")
    nav_d = result["nav"].copy()
    nav_d["date_dt"] = pd.to_datetime(nav_d["date"])
    bm = result["benchmark_df"].copy()
    bm["date_dt"] = pd.to_datetime(bm["trade_date"])
    merged = nav_d.merge(bm[["date_dt", "close"]], on="date_dt", how="left")
    merged = merged.rename(columns={"close": "bm_close"})
    merged = merged.merge(
        regime_df[["trade_date", "label"]],
        left_on="date_dt", right_on="trade_date", how="left"
    )
    merged["strat_ret"] = merged["total_value"].pct_change()
    merged["bm_ret"] = merged["bm_close"].pct_change()

    w("| 状态 | 天数 | 策略累计 | 基准累计 | 策略日均 | 基准日均 |")
    w("|------|:--:|--:|--:|--:|--:|")
    for label in ["bull_trend", "bull_range", "recovery", "bear_range", "bear_trend", "tail_risk"]:
        sub = merged[merged["label"] == label]
        if len(sub) > 1:
            s_cum = (sub["total_value"].iloc[-1] / sub["total_value"].iloc[0] - 1) * 100
            b_cum = (sub["bm_close"].iloc[-1] / sub["bm_close"].iloc[0] - 1) * 100
            s_avg = sub["strat_ret"].mean() * 100
            b_avg = sub["bm_ret"].mean() * 100
            w(f"| {label} | {len(sub)} | {s_cum:+.1f}% | {b_cum:+.1f}% | {s_avg:+.2f}% | {b_avg:+.2f}% |")

    # ── 3. 逐年绩效 ──
    w("\n---\n## 3. 逐年绩效 [精确]\n")
    nav_yr = nav_d.copy()
    nav_yr["year"] = nav_yr["date_dt"].dt.year
    # Benchmark yearly
    bm_yr = bm.copy()
    bm_yr["year"] = bm_yr["date_dt"].dt.year

    w("| year | 策略收益 | 基准收益 | 超额 | 策略DD | 基准DD |")
    w("|------|--:|--:|--:|--:|--:|")
    for yr in sorted(nav_yr["year"].unique()):
        sn = nav_yr[nav_yr["year"] == yr]
        bn = bm_yr[bm_yr["year"] == yr]
        if len(sn) >= 2 and len(bn) >= 2:
            sr = (sn["total_value"].iloc[-1] / sn["total_value"].iloc[0] - 1) * 100
            br = (bn["close"].iloc[-1] / bn["close"].iloc[0] - 1) * 100
            # strategy DD
            peak_s = sn["total_value"].cummax()
            sdd = (sn["total_value"] - peak_s) / peak_s
            sdd_pct = sdd.min() * 100
            # benchmark DD
            peak_b = bn["close"].cummax()
            bdd = (bn["close"] - peak_b) / peak_b
            bdd_pct = bdd.min() * 100
            w(f"| {yr} | {sr:+.1f}% | {br:+.1f}% | {sr-br:+.1f}% | {sdd_pct:.1f}% | {bdd_pct:.1f}% |")

    # ── 4. 每年交易行为 ──
    w("\n---\n## 4. 每年交易行为\n")
    yb = result["yearly_behavior"]
    w(yb.to_markdown(index=False))

    # ── 5. 2019/2020 不赚钱原因拆解 ──
    w("\n---\n## 5. 2019/2020 不赚钱原因拆解\n")
    for yr in [2019, 2020]:
        w(f"\n### {yr}\n")
        row = yb[yb["year"] == yr]
        if len(row) > 0:
            r = row.iloc[0]
            empty_pct = r["empty_position_days"] / result["total_trading_days"] * 100
            w(f"| 指标 | 值 | 判断 |")
            w(f"|------|----|------|")
            w(f"| 空仓天数 | {int(r['empty_position_days'])} | [精确] |")
            w(f"| 有持仓比例 | {r['exposure_ratio_pct']}% | [精确] |")
            w(f"| 平均仓位 | {r['avg_position_weight_pct']}% | [精确] |")
            w(f"| 买入次数 | {int(r['buy_count'])} | [精确] |")
            w(f"| 止损次数 | ~{r['stop_loss_count']} | [近似] |")
            w(f"| 平均持仓天数 | {r['avg_holding_days']} | [近似] |")
            w(f"| 胜率 | {r['win_rate_pct']}% | [近似] |")
            w(f"| failed_entry_rate | {r['failed_entry_rate_pct']}% | [近似] |")

        # Regime days
        yreg = yearly_regime[yearly_regime["year"] == yr]
        if len(yreg) > 0:
            yr_counts = yreg.iloc[0]
            bull_days = int(yr_counts["bull_trend_days"]) + int(yr_counts["bull_range_days"])
            bear_days = int(yr_counts["bear_trend_days"]) + int(yr_counts["bear_range_days"])
            w(f"\n| 牛市天数 | {bull_days} | [近似] |")
            w(f"| 熊市天数 | {bear_days} | [近似] |")

        # Diagnosis
        if empty_pct > 70:
            w(f"\n**主要结论：{yr} 年空仓比例 {empty_pct:.0f}%，策略绝大部分时间未入场。不是入场太晚或选股差，是 regime 评分未触发入场条件。[精确]**")
        else:
            w(f"\n**主要结论：{yr} 年较低仓位叠加较高的止损率，导致收益有限。[近似]**")

    # ── 6. 2024 单年贡献 ──
    w("\n---\n## 6. 2024 单年贡献诊断\n")
    total_ret = m["total_return_pct"]
    ret_2024 = None
    nav_yr2 = nav_d.copy()
    nav_yr2["year"] = nav_yr2["date_dt"].dt.year
    sn24 = nav_yr2[nav_yr2["year"] == 2024]
    if len(sn24) >= 2:
        ret_2024 = (sn24["total_value"].iloc[-1] / sn24["total_value"].iloc[0] - 1) * 100

    w(f"| 指标 | 全区间 | 去掉2024 |")
    w(f"|------|------|------|")
    w(f"| total_return | {total_ret:.1f}% | — |")

    if ret_2024 is not None:
        # Without 2024: subtract 2024 return from total
        w(f"| 2024 收益 | {ret_2024:.1f}% | — |")
        # Recalculate without 2024
        non24 = nav_yr2[nav_yr2["year"] != 2024]
        if len(non24) >= 2:
            ret_no24 = (non24["total_value"].iloc[-1] / non24["total_value"].iloc[0] - 1) * 100
            non24_days = len(non24)
            ann_no24 = ((non24["total_value"].iloc[-1] / non24["total_value"].iloc[0])
                        ** (365.25 / non24_days) - 1) * 100 if non24_days > 0 else 0
            peak_no24 = non24["total_value"].cummax()
            dd_no24 = (non24["total_value"] - peak_no24) / peak_no24
            maxdd_no24 = dd_no24.min() * 100
            calmar_no24 = ann_no24 / abs(maxdd_no24) if maxdd_no24 != 0 else 0
            w(f"| total_return (no 2024) | — | {ret_no24:.1f}% |")
            w(f"| annual_return (no 2024) | — | {ann_no24:.1f}% |")
            w(f"| max_drawdown (no 2024) | — | {maxdd_no24:.1f}% |")
            w(f"| calmar (no 2024) | — | {calmar_no24:.2f} |")

            if total_ret > 0:
                contrib = ret_2024 / total_ret * 100
                w(f"| **2024 贡献比例** | — | **{contrib:.0f}%** |")
                if contrib > 60:
                    w(f"\n> **稳定性警告：策略收益高度依赖 2024 单一年份（贡献 {contrib:.0f}%）。**")
            else:
                w(f"| 2024 贡献比例 | — | 不可用（总收益≤0） |")

    # ── 7. score_high / score_low 敏感性 ──
    w("\n---\n## 7. score_high / score_low 敏感性 [近似]\n")
    sweep_df = result.get("sensitivity_df")
    if sweep_df is not None and len(sweep_df) > 0:
        w(sweep_df.to_markdown(index=False, floatfmt=".2f"))
    else:
        w("敏感性测试未运行（使用 --no-sweep 跳过）。")

    # ── 8. failed_entry_rate ──
    w("\n---\n## 8. failed_entry_rate [近似]\n")
    sm = result["signal_metrics"]
    w(f"- 总匹配交易数：{sm.get('matched_trade_count', ('—',''))[0]}")
    w(f"- failed_entry_rate：{sm.get('failed_entry_rate_pct', ('—',''))[0]}%")
    w(f"- stop_loss_count：~{sm.get('stop_loss_count', ('—',''))[0]}")
    w(f"- big_loss_count：{sm.get('big_loss_count', ('—',''))[0]}")
    w(f"\n> 依赖 exit_reason 关键词匹配，为近似诊断。部分 SELL 记录无 reason 字段。")

    # ── 9. bull_capture ──
    w("\n---\n## 9. bull_capture [近似]\n")
    bull_days = merged[merged["label"] == "bull_trend"]
    if len(bull_days) > 1:
        s_bull = (bull_days["total_value"].iloc[-1] / bull_days["total_value"].iloc[0] - 1) * 100
        b_bull = (bull_days["bm_close"].iloc[-1] / bull_days["bm_close"].iloc[0] - 1) * 100
        if b_bull > 0:
            capture = s_bull / b_bull
            w(f"- 牛市区间策略收益：{s_bull:+.1f}%")
            w(f"- 牛市区间基准收益：{b_bull:+.1f}%")
            w(f"- **bull_capture = {capture:.2f}**")
        else:
            w(f"- 牛市区间基准收益 {b_bull:+.1f}% ≤ 0，bull_capture 不可用")
    else:
        w("- 无足够牛市数据，不可用")

    # ── 10. bear_loss_avoidance ──
    w("\n---\n## 10. bear_loss_avoidance [近似]\n")
    bear_days = merged[merged["label"] == "bear_trend"]
    if len(bear_days) > 1:
        s_bear = (bear_days["total_value"].iloc[-1] / bear_days["total_value"].iloc[0] - 1) * 100
        b_bear = (bear_days["bm_close"].iloc[-1] / bear_days["bm_close"].iloc[0] - 1) * 100
        if b_bear < 0:
            avoidance = 1 - abs(s_bear) / abs(b_bear)
            w(f"- 熊市区间策略收益：{s_bear:+.1f}%")
            w(f"- 熊市区间基准收益：{b_bear:+.1f}%")
            w(f"- **bear_loss_avoidance = {avoidance:.2f}** ({avoidance*100:.0f}% 的熊市跌幅被规避)")
        else:
            w(f"- 熊市区间基准收益 {b_bear:+.1f}% ≥ 0，bear_loss_avoidance 不可用")
    else:
        w("- 无足够熊市数据，不可用")

    # ── 11. max_drawdown_ratio ──
    w("\n---\n## 11. max_drawdown_ratio [精确]\n")
    bm_full = merged["bm_close"].dropna()
    if len(bm_full) > 1:
        bm_peak = bm_full.cummax()
        bm_dd = (bm_full - bm_peak) / bm_peak
        bm_maxdd = bm_dd.min() * 100
        s_maxdd = m["max_drawdown_pct"]
        if abs(bm_maxdd) > 0.5:
            ratio = s_maxdd / bm_maxdd
            w(f"- 策略最大回撤：{s_maxdd:.1f}%")
            w(f"- 基准最大回撤：{bm_maxdd:.1f}%")
            w(f"- **max_drawdown_ratio = {ratio:.2f}**")
        else:
            w(f"- 基准最大回撤 {bm_maxdd:.1f}% 接近 0，不可用")

    # ── 12. 最差 10 笔交易 ──
    w("\n---\n## 12. 最差 10 笔交易 [近似]\n")
    wt = result.get("worst_10")
    if wt is not None and len(wt) > 0:
        disp = wt[["symbol", "buy_date", "sell_date", "pnl_pct", "holding_days", "exit_reason"]].copy()
        if "pnl_pct" in disp.columns:
            disp["pnl_pct"] = disp["pnl_pct"].apply(lambda x: f"{x*100:.2f}%")
        w(disp.to_markdown(index=False))
    else:
        w("- 无匹配交易数据")

    # ── 13. 指标可信度 ──
    w("\n---\n## 13. 指标可信度汇总\n")
    w("| 指标 | 可信度 | 原因 |")
    w("|------|:--:|------|")
    rows = [
        ("total_return / ann_return / max_dd / sharpe / calmar", "精确", "NAV 逐日记录完整"),
        ("yearly_returns", "精确", "NAV 按年分组"),
        ("exposure_ratio / avg_position / empty_days", "精确", "positions 逐日记录"),
        ("buy_count / sell_count / trade_count", "精确", "trades 记录完整"),
        ("avg_holding_days", "近似", "FIFO 配对假设，无真实 position_id"),
        ("逐笔 P&L", "近似", "基于成交价，含滑点佣金，FIFO 假设"),
        ("stop_loss_count / take_profit", "近似", "依赖 exit_reason 关键词匹配"),
        ("failed_entry_rate", "近似", "依赖 stop_loss_count + 逐笔 P&L"),
        ("bull_capture / bear_loss_avoidance", "近似", "依赖 market_regime 分类准确性"),
        ("max_drawdown_ratio", "精确", "指数 DD 和 NAV DD 均可精确计算"),
        ("breadth_score / breadth_delta_10d", "暂不可用", "需个股数据，非指数数据"),
        ("momentum_20d / momentum_60d", "暂不可用", "需个股数据"),
        ("有信号但未入场", "暂不可用", "需 daily_signals 记录"),
    ]
    for name, label, reason in rows:
        w(f"| {name} | [{label}] | {reason} |")

    # ── Write file ──
    report = "\n".join(lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(report)
    logger.info(f"Report saved to {out_path}")
    return report


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--params", default=None,
                        help="Path to GA result JSON")
    parser.add_argument("--benchmark", default="000300.SH",
                        help="Benchmark code (000300.SH, 000905.SH, etc.)")
    parser.add_argument("--no-sweep", action="store_true",
                        help="Skip sensitivity sweep (faster)")
    parser.add_argument("--start", default="2018-01-01")
    parser.add_argument("--end", default="2026-05-08")
    args = parser.parse_args()

    setup_file_log()
    root = get_project_root()
    t0 = pd.Timestamp.now()

    # Load params
    if args.params:
        params_path = args.params
    else:
        # Find latest GA result
        ga_dir = root / "data" / "ga_results"
        jsons = sorted(ga_dir.glob("*.json"))
        if not jsons:
            logger.error("No GA result found. Run GA first or specify --params.")
            sys.exit(1)
        params_path = str(jsons[-1])
        logger.info(f"Using latest GA result: {params_path}")

    with open(params_path) as f:
        ga_result = json.load(f)
    params = ga_result["best_params"]
    genes = ga_result.get("best_genes", ga_result.get("genes", {}))

    # Step 1: Load benchmark
    logger.info(f"Loading benchmark: {args.benchmark}")
    bm_df = load_benchmark(args.benchmark)
    bm_range = bm_df[(bm_df["trade_date"] >= args.start) & (bm_df["trade_date"] <= args.end)]

    # Step 2: Market regime
    logger.info("Classifying market regime...")
    regime_df = classify_regime(bm_range)

    # Step 3: Full backtest with best params
    logger.info("Running full-period backtest...")
    nav, trades, positions, metrics = backtest_with_params(params, genes, args.start, args.end)

    # Step 4: Signal metrics
    logger.info("Computing signal metrics...")
    sig_m, matched, open_pos = compute_signal_metrics(trades, nav, positions)
    yb = yearly_behavior(trades, nav, positions)
    wt = worst_trades(matched, 10)

    # Step 5: Sensitivity sweep (optional)
    sweep_df = None
    if not args.no_sweep:
        logger.info("Running sensitivity sweep (7 combinations)...")
        sh_vals = [0.60, 0.65, 0.70, 0.76]
        sl_vals = [0.30, 0.35, 0.40]
        # Only: score_high sweep with score_low=0.30, and score_low sweep with score_high=0.76
        sweep_rows = []
        for sh in sh_vals:
            sweep_rows.append({"sh": sh, "sl": 0.30})
        for sl in sl_vals:
            if sl != 0.30:
                sweep_rows.append({"sh": 0.76, "sl": sl})
        sweep_df = sensitivity_sweep(genes, sh_vals, sl_vals, args.start, args.end)

    # Compile result
    result = {
        "params_path": params_path,
        "benchmark_code": args.benchmark,
        "start": args.start,
        "end": args.end,
        "params": params,
        "genes": genes,
        "metrics": metrics,
        "total_trading_days": len(nav),
        "nav": nav,
        "benchmark_df": bm_range,
        "regime_df": regime_df,
        "signal_metrics": dict(sig_m),
        "yearly_behavior": yb,
        "worst_10": wt,
        "sensitivity_df": sweep_df,
    }

    # Generate report
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = root / "data" / "diagnosis" / f"report_{ts}.md"
    generate_report(result, out_path)

    elapsed = (pd.Timestamp.now() - t0).total_seconds()
    logger.info(f"Diagnosis complete in {elapsed:.0f}s")


if __name__ == "__main__":
    main()

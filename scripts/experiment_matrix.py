"""Experiment matrix runner: A → F → D → G.

Usage:
    python scripts/experiment_matrix.py --experiment A
    python scripts/experiment_matrix.py --experiment F
    python scripts/experiment_matrix.py --experiment D
    python scripts/experiment_matrix.py --experiment G
    python scripts/experiment_matrix.py --experiment all

Each run: full backtest 2018-2026, 18 metrics, saved to data/experiments/.
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.backtest.performance import compute_metrics
from qts.diagnosis.signal_report import fifo_match
from qts.utils.config import get_project_root
from qts.utils.logger import logger, setup_file_log

ROOT = get_project_root()
START, END = "2018-01-01", "2026-05-08"
SCORE_HIGH = 0.72

EXPERIMENTS = {
    "A": {"enable_pullback_entry": False, "enable_rank_buffer": False, "sell_rank_multiplier": 2},
    "F": {"enable_pullback_entry": False, "enable_rank_buffer": True,  "sell_rank_multiplier": 2},
    "D": {"enable_pullback_entry": True,  "enable_rank_buffer": False, "sell_rank_multiplier": 2},
    "G": {"enable_pullback_entry": True,  "enable_rank_buffer": True,  "sell_rank_multiplier": 2},
}


def load_best_genes():
    ga_dir = ROOT / "data" / "ga_results"
    jsons = sorted(ga_dir.glob("*.json"))
    with open(str(jsons[-1])) as f:
        ga = json.load(f)
    return ga.get("best_genes", {}), ga["best_params"]


def build_strategy(genes, params, experiment_config):
    score_high = params.get("score_high", SCORE_HIGH)
    regime_kw = {
        "w_breadth": params["w_breadth"], "w_trend": params["w_trend"],
        "w_stability": params["w_stability"], "w_volume": params["w_volume"],
        "score_low": params["score_low"], "score_high": score_high,
        "breakout_bull": params["breakout_bull"], "breakout_bear": params["breakout_bear"],
        "atr_bull": params["atr_bull"], "atr_bear": params["atr_bear"],
        "vol_ratio_bull": params["vol_ratio_bull"], "vol_ratio_bear": params["vol_ratio_bear"],
        "top_n_bull": params["top_n_bull"], "top_n_bear": params["top_n_bear"],
        "support_bull": params["support_bull"], "support_bear": params["support_bear"],
        "ma_days_bull": params["ma_days_bull"], "ma_days_bear": params["ma_days_bear"],
    }
    regime = RegimeEngine(**regime_kw)
    s = TrendBreakoutStrategy(
        breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
        max_loss_pct=genes["max_loss_pct"], min_breadth=0.50, breadth_half=0.30,
        atr_multiple=2.0, atr_period=int(genes["atr_period"]),
        profit_lock_pct=genes["profit_lock_pct"], top_n=10,
        max_weight_per_stock=genes["max_weight_per_stock"],
    )
    s.regime_engine = regime
    s.use_dow_filter = False
    s.breadth_ma_days = int(genes["breadth_ma_days"])
    s.strategy_max_dd = genes["strategy_max_dd"]
    s.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}

    # Experiment switches
    s.enable_pullback_entry = experiment_config["enable_pullback_entry"]
    s.enable_rank_buffer = experiment_config["enable_rank_buffer"]
    s.sell_rank_multiplier = experiment_config["sell_rank_multiplier"]
    return s


def compute_18_metrics(nav_df, trades_df, positions_df):
    m = {}
    metrics, nav, _ = compute_metrics(nav_df, trades_df, 1_000_000)

    # 1-4: core
    m["total_return_pct"] = metrics.get("total_return_pct", 0)
    m["annual_return_pct"] = metrics.get("annual_return_pct", 0)
    m["max_drawdown_pct"] = metrics.get("max_drawdown_pct", 0)
    m["calmar"] = metrics.get("calmar_ratio", 0)

    # 5-8: no_2024 [稳定性诊断]
    nav_df = nav.copy()
    nav_df["date_dt"] = pd.to_datetime(nav_df["date"])
    nav_df["year"] = nav_df["date_dt"].dt.year
    sn24 = nav_df[nav_df["year"] == 2024]
    ret_2024 = 0
    if len(sn24) >= 2:
        ret_2024 = (sn24["total_value"].iloc[-1] / sn24["total_value"].iloc[0] - 1) * 100
    if ret_2024 > -99:
        total_ret = m["total_return_pct"]
        ret_no24 = ((1 + total_ret/100) / (1 + ret_2024/100) - 1) * 100
    else:
        ret_no24 = total_ret
    m["total_ret_no_2024"] = round(ret_no24, 2)

    # dd_no_2024: rebuild NAV by chaining non-2024 years
    non24 = nav_df[nav_df["year"] != 2024].copy()
    if len(non24) >= 2:
        non24_vals = non24["total_value"].values
        peak = np.maximum.accumulate(non24_vals)
        dd = (non24_vals - peak) / peak
        m["dd_no_2024"] = round(dd.min() * 100, 2)
        n_years_no24 = len(non24) / 252
        if n_years_no24 > 0:
            m["ann_no_2024"] = round(((non24_vals[-1] / non24_vals[0]) ** (1/n_years_no24) - 1) * 100, 2)
        else:
            m["ann_no_2024"] = 0
        m["calmar_no_2024"] = round(m["ann_no_2024"] / abs(m["dd_no_2024"]), 3) if m["dd_no_2024"] != 0 else 0
    else:
        m["ann_no_2024"] = 0
        m["dd_no_2024"] = 0
        m["calmar_no_2024"] = 0

    # 9-10: yearly
    nav_df["position_weight"] = nav_df["position_value"] / nav_df["total_value"]
    for yr in [2019, 2020]:
        sn = nav_df[nav_df["year"] == yr]
        if len(sn) >= 2:
            yr_ret = (sn["total_value"].iloc[-1] / sn["total_value"].iloc[0] - 1) * 100
            yr_exp = sn["position_weight"].mean() * 100
        else:
            yr_ret, yr_exp = 0, 0
        m[f"ret_{yr}"] = round(yr_ret, 2)
        m[f"exp_{yr}"] = round(yr_exp, 2)

    # 11: bear year DD
    for yr in [2018, 2022]:
        sn = nav_df[nav_df["year"] == yr]
        if len(sn) >= 2:
            vals = sn["total_value"].values
            peak_s = np.maximum.accumulate(vals)
            yr_dd = (vals - peak_s) / peak_s
            m[f"dd_{yr}"] = round(yr_dd.min() * 100, 2)
        else:
            m[f"dd_{yr}"] = 0

    # 12: trades
    m["total_trades"] = len(trades_df)

    # 13-16: signal metrics
    matched, _ = fifo_match(trades_df)
    valid = matched[matched["pnl_pct"].notna()]
    if len(valid) > 0:
        stop_kw = ["止损", "stop", "loss", "atr", "跌破"]
        early_stop = ((valid["holding_days"] <= 10) &
                      valid["exit_reason"].apply(lambda r: any(k in str(r).lower() for k in stop_kw)))
        big_loss = valid["pnl_pct"] < -0.05
        m["failed_entry_rate"] = round(len(valid[early_stop | big_loss]) / len(valid) * 100, 1)
        m["avg_holding_days"] = round(valid["holding_days"].mean(), 1)
        m["median_holding_days"] = round(valid["holding_days"].median(), 1)
        # rebalance_sell
        is_rebalance = valid["exit_reason"].isna() | (valid["exit_reason"] == "") | (valid["exit_reason"] == "nan")
        m["rebalance_sell_rate"] = round(is_rebalance.sum() / len(valid) * 100, 1)
        short_reb = is_rebalance & (valid["holding_days"] <= 5)
        m["short_rebalance_sell_rate"] = round(short_reb.sum() / len(valid) * 100, 1)
    else:
        m["failed_entry_rate"] = 0
        m["avg_holding_days"] = 0
        m["median_holding_days"] = 0
        m["rebalance_sell_rate"] = 0
        m["short_rebalance_sell_rate"] = 0

    # 17: turnover
    buys = trades_df[trades_df["side"] == "BUY"]
    avg_nav = nav_df["total_value"].mean()
    buy_value = buys["cost"].sum() if "cost" in buys.columns and len(buys) > 0 else 0
    buy_turnover = buy_value / avg_nav if avg_nav > 0 else 0
    m["buy_turnover"] = round(buy_turnover, 3)
    n_years = len(nav_df) / 252
    m["ann_buy_turnover"] = round(buy_turnover / n_years, 3) if n_years > 0 else 0

    # 18: exposure / avg_position
    total_days = len(nav_df)
    with_positions = int((nav_df["n_positions"] > 0).sum())
    m["exposure"] = round(with_positions / total_days * 100, 1) if total_days > 0 else 0
    m["avg_position"] = round(nav_df["position_weight"].mean() * 100, 2)

    return m, matched, nav_df


def print_18_metrics(exp_name, config, metrics):
    print(f"\n{'='*70}")
    print(f"Experiment {exp_name}")
    print(f"  enable_pullback_entry: {config['enable_pullback_entry']}")
    print(f"  enable_rank_buffer: {config['enable_rank_buffer']}")
    print(f"  sell_rank_multiplier: {config['sell_rank_multiplier']}")
    print(f"{'='*70}")

    labels = [
        ("1", "total_return_pct", "%"),
        ("2", "annual_return_pct", "%"),
        ("3", "max_drawdown_pct", "%"),
        ("4", "calmar", ""),
        ("5", "total_ret_no_2024", "% [稳定诊断]"),
        ("6", "ann_no_2024", "% [稳定诊断]"),
        ("7", "dd_no_2024", "% [稳定诊断]"),
        ("8", "calmar_no_2024", " [稳定诊断]"),
        ("9", "ret_2019", "%"), ("9b", "exp_2019", "%"),
        ("10", "ret_2020", "%"), ("10b", "exp_2020", "%"),
        ("11", "dd_2018", "%"), ("11b", "dd_2022", "%"),
        ("12", "total_trades", ""),
        ("13", "failed_entry_rate", "%"),
        ("14", "avg_holding_days", "d"), ("14b", "median_holding_days", "d"),
        ("15", "rebalance_sell_rate", "%"),
        ("16", "short_rebalance_sell_rate", "%"),
        ("17", "buy_turnover", "x"), ("17b", "ann_buy_turnover", "x"),
        ("18", "exposure", "%"), ("18b", "avg_position", "%"),
    ]
    for num, key, unit in labels:
        if key in metrics:
            val = metrics[key]
            print(f"  [{num}] {key}: {val}{unit}")


def run_experiment(exp_name: str) -> dict:
    config = EXPERIMENTS[exp_name]
    genes, params = load_best_genes()
    params = dict(params)
    params["score_high"] = SCORE_HIGH

    s = build_strategy(genes, params, config)

    engine = BacktestEngine(
        bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
        calendar_path=str(ROOT / "data/raw/calendar.parquet"),
        start_date=START, end_date=END,
        initial_cash=1_000_000,
        execution_price="intraday_close", intraday_spread_bps=15,
    )
    t0 = time.time()
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    elapsed = time.time() - t0
    logger.info(f"Backtest done in {elapsed:.0f}s")

    metrics, matched, nav_df = compute_18_metrics(results["nav"], results["trades"], results["positions"])
    print_18_metrics(exp_name, config, metrics)

    # Pullback split analysis
    if config["enable_pullback_entry"]:
        trades = results["trades"]
        buys = trades[trades["side"] == "BUY"]
        print(f"\n{'='*60}")
        print(f"PULLBACK vs BREAKOUT SPLIT")
        print(f"{'='*60}")

        # Funnel from strategy
        if hasattr(s, '_pb_funnel') and s._pb_funnel:
            funnel = s._pb_funnel
            entered_days = sum(f["branch_entered"] for f in funnel)
            cand_total = sum(f["candidates"] for f in funnel)
            added_total = sum(f["added_to_target"] for f in funnel)
            bought_total = sum(f["bought"] for f in funnel)
            gated_total = sum(f.get("gated_out", 0) for f in funnel)
            print(f"\n  PULLBACK BRANCH DIAGNOSTICS:")
            print(f"    branch entered days (alloc>0): {entered_days}")
            print(f"    candidates (passed 6 conditions): {cand_total}")
            print(f"    gated out (alloc_pct > max): {gated_total}")
            print(f"    added to target (after gate): {added_total}")
            print(f"    actual buys (survived top_n): {bought_total}")
            for yr in range(2018, 2027):
                yf = [f for f in funnel if f["date"].startswith(str(yr))]
                if not yf:
                    continue
                ye = sum(f["branch_entered"] for f in yf)
                yc = sum(f["candidates"] for f in yf)
                ya = sum(f["added_to_target"] for f in yf)
                yb = sum(f["bought"] for f in yf)
                print(f"    {yr}: branch_days={ye}  candidates={yc}  added={ya}  bought={yb}")

        if "reason" in buys.columns and len(buys) > 0:
            pb = buys[buys["reason"] == "pullback_entry"]
            bk = buys[buys["reason"] == "breakout_entry"]
            hold = buys[~buys["reason"].isin(["breakout_entry", "pullback_entry"])]
            print(f"\n  BUY reason distribution:")
            print(f"    breakout_entry: {len(bk)}")
            print(f"    pullback_entry: {len(pb)}")
            print(f"    hold/other: {len(hold)}")

            # Symbol-level overlap (note: not same-day signal overlap)
            pb_syms = set(pb["symbol"]) if len(pb) > 0 else set()
            bk_syms = set(bk["symbol"]) if len(bk) > 0 else set()
            if len(buys) > 0:
                sym_overlap = len(pb_syms & bk_syms)
                total_syms = len(buys["symbol"].unique())
                print(f"    symbol-level overlap: {sym_overlap}/{total_syms} ({sym_overlap/total_syms*100:.1f}%)")

            for yr in range(2018, 2027):
                yb = buys[pd.to_datetime(buys["date"]).dt.year == yr]
                ypb = yb[yb["reason"] == "pullback_entry"]
                ybk = yb[yb["reason"] == "breakout_entry"]
                if len(yb) > 0:
                    print(f"    {yr}: buys={len(yb)}  breakout={len(ybk)}  pullback={len(ypb)}")

            # Per-entry-type metrics
            for label, subset in [("breakout_entry", bk), ("pullback_entry", pb)]:
                if len(subset) == 0:
                    print(f"\n  {label}: NO TRADES")
                    continue
                sub_buy_syms = set(subset["symbol"])
                sub_matched = matched[matched["symbol"].isin(sub_buy_syms)] if len(matched) > 0 else pd.DataFrame()
                if len(sub_matched) > 0:
                    win_r = (sub_matched["pnl_pct"] > 0).mean() * 100
                    avg_pnl = sub_matched["pnl_pct"].mean() * 100
                    avg_h = sub_matched["holding_days"].mean()
                    is_reb = sub_matched["exit_reason"].isna() | (sub_matched["exit_reason"] == "") | (sub_matched["exit_reason"] == "nan")
                    reb_r = is_reb.sum() / len(sub_matched) * 100
                    stop_kw = ["止损", "stop", "loss", "atr", "跌破"]
                    early_stop = ((sub_matched["holding_days"] <= 10) &
                                  sub_matched["exit_reason"].apply(lambda r: any(k in str(r).lower() for k in stop_kw)))
                    big_loss = sub_matched["pnl_pct"] < -0.05
                    fer = len(sub_matched[early_stop | big_loss]) / len(sub_matched) * 100
                    print(f"\n  {label}: {len(sub_matched)} trades | win_rate={win_r:.0f}%")
                    print(f"    avg_pnl={avg_pnl:+.2f}% | avg_hold={avg_h:.1f}d")
                    print(f"    rebalance_sell_rate={reb_r:.0f}% | failed_entry_rate={fer:.1f}%")

    # Save
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "experiments" / f"experiment_matrix_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "experiment_name": exp_name,
        "score_high": SCORE_HIGH,
        "enable_pullback_entry": config["enable_pullback_entry"],
        "enable_rank_buffer": config["enable_rank_buffer"],
        "sell_top_n": int(s.top_n * config["sell_rank_multiplier"]),
        "strategy_params": params,
        "metrics": metrics,
        "result_path": str(out_dir / f"{exp_name}.json"),
    }
    with open(out_dir / f"{exp_name}.json", "w") as f:
        json.dump(record, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Saved to {out_dir / f'{exp_name}.json'}")

    return record


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--experiment", choices=["A", "F", "D", "G", "all"], default="A")
    args = parser.parse_args()

    setup_file_log()

    if args.experiment == "all":
        order = ["A", "F", "D", "G"]
    else:
        order = [args.experiment]

    records = []
    for exp in order:
        logger.info(f"\n{'#'*70}\n# Experiment {exp}\n{'#'*70}")
        rec = run_experiment(exp)
        records.append(rec)

    # Summary table
    if len(records) > 1:
        print(f"\n{'='*70}")
        print("SUMMARY TABLE")
        print(f"{'='*70}")
        summary_keys = ["total_return_pct", "annual_return_pct", "max_drawdown_pct",
                        "calmar", "total_ret_no_2024", "ret_2019", "exp_2019",
                        "ret_2020", "exp_2020", "dd_2018", "dd_2022",
                        "total_trades", "failed_entry_rate", "avg_holding_days",
                        "rebalance_sell_rate", "short_rebalance_sell_rate",
                        "buy_turnover", "exposure"]
        header = ["experiment"] + summary_keys
        rows = []
        for rec in records:
            row = [rec["experiment_name"]]
            for k in summary_keys:
                row.append(rec["metrics"].get(k, "-"))
            rows.append(row)
        df_summary = pd.DataFrame(rows, columns=header)
        print(df_summary.to_string(index=False))

        out_dir = Path(records[0]["result_path"]).parent
        df_summary.to_csv(out_dir / "summary.csv", index=False)
        logger.info(f"Summary saved to {out_dir / 'summary.csv'}")


if __name__ == "__main__":
    main()

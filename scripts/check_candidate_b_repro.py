"""Candidate B reproducibility check: 3 cross-process runs.

Usage:
    python scripts/check_candidate_b_repro.py --run-id 1
    python scripts/check_candidate_b_repro.py --run-id 2
    python scripts/check_candidate_b_repro.py --run-id 3
"""
import sys, json, time, hashlib
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
from qts.utils.logger import logger

ROOT = get_project_root()
FULL = ("2018-01-01", "2026-05-08")

CANDIDATE_B_GENES = {
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


def run_and_measure(genes, run_id):
    t0 = time.time()
    regime = RegimeEngine(**genes_to_regime_kwargs(genes))
    s = TrendBreakoutStrategy(
        breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
        max_loss_pct=genes["max_loss_pct"], min_breadth=0.50, breadth_half=0.30,
        atr_multiple=2.0, atr_period=int(genes["atr_period"]),
        profit_lock_pct=genes["profit_lock_pct"], top_n=10,
        max_weight_per_stock=genes["max_weight_per_stock"],
    )
    s.regime_engine = regime; s.use_dow_filter = False
    s.breadth_ma_days = int(genes["breadth_ma_days"])
    s.strategy_max_dd = genes["strategy_max_dd"]
    s.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}
    s.enable_rank_buffer = False; s.enable_pullback_entry = False

    engine = BacktestEngine(
        bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
        calendar_path=str(ROOT / "data/raw/calendar.parquet"),
        start_date=FULL[0], end_date=FULL[1], initial_cash=1_000_000,
        execution_price="intraday_close", intraday_spread_bps=15,
    )
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    m, nav, _ = compute_metrics(results["nav"], results["trades"], 1_000_000)

    # Compute fitness
    nf = nav.copy()
    nf["date_dt"] = pd.to_datetime(nf["date"]); nf["year"] = nf["date_dt"].dt.year
    nf["position_weight"] = nf["position_value"] / nf["total_value"]

    raw = {}
    full_ret = m["total_return_pct"]
    sn24 = nf[nf["year"] == 2024]
    ret_2024 = ((sn24["total_value"].iloc[-1] / sn24["total_value"].iloc[0] - 1) * 100) if len(sn24) >= 2 else 0
    raw["full_no_2024_pct"] = round(((1 + full_ret/100) / (1 + ret_2024/100) - 1) * 100, 2) if ret_2024 > -99 else full_ret

    for yr in range(2018, 2027):
        sn = nf[nf["year"] == yr]
        if len(sn) >= 2:
            raw[f"ret_{yr}"] = round((sn["total_value"].iloc[-1] / sn["total_value"].iloc[0] - 1) * 100, 2)
        else:
            raw[f"ret_{yr}"] = 0

    matched, _ = fifo_match(results["trades"])
    valid = matched[matched["pnl_pct"].notna()]
    if len(valid) > 0:
        stop_kw = ["stop", "loss", "atr"]
        early = (valid["holding_days"] <= 10) & valid["exit_reason"].apply(
            lambda r: any(k in str(r).lower() for k in stop_kw))
        big = valid["pnl_pct"] < -0.05
        raw["failed_entry_rate"] = round(len(valid[early | big]) / len(valid) * 100, 1)
    else:
        raw["failed_entry_rate"] = 0

    buys = results["trades"][results["trades"]["side"] == "BUY"]
    buy_val = buys["cost"].sum() if "cost" in buys.columns else 0
    avg_nav = nf["total_value"].mean()
    raw["annual_turnover"] = round(buy_val / avg_nav / (len(nf) / 252), 2) if avg_nav > 0 else 0

    total_profit = nf["total_value"].iloc[-1] - nf["total_value"].iloc[0]
    yearly_profits = {}
    for yr in range(2018, 2027):
        sn_yr = nf[nf["year"] == yr]
        if len(sn_yr) >= 2:
            yearly_profits[yr] = sn_yr["total_value"].iloc[-1] - sn_yr["total_value"].iloc[0]
    if total_profit > 0:
        pos_profits = [v for v in yearly_profits.values() if v > 0]
        raw["max_year_profit_pct"] = round(max(pos_profits) / total_profit * 100, 1) if pos_profits else 100
    else:
        raw["max_year_profit_pct"] = 100

    total_days = len(nf)
    with_pos = int((nf["n_positions"] > 0).sum()) if "n_positions" in nf.columns else 0
    raw["exposure"] = round(with_pos / total_days * 100, 1) if total_days > 0 else 0
    raw["avg_position"] = round(nf["position_weight"].mean() * 100, 2)

    elapsed = time.time() - t0

    metrics_out = {
        "run_id": run_id,
        "total_return_pct": round(m["total_return_pct"], 2),
        "annual_return_pct": round(m["annual_return_pct"], 2),
        "max_drawdown_pct": round(m["max_drawdown_pct"], 2),
        "calmar_ratio": round(m["calmar_ratio"], 3),
        "full_no_2024_pct": raw["full_no_2024_pct"],
        "max_year_profit_pct": raw["max_year_profit_pct"],
        "total_trades": len(results["trades"]),
        "exposure": raw["exposure"],
        "avg_position": raw["avg_position"],
        "failed_entry_rate": raw["failed_entry_rate"],
        "annual_turnover": raw["annual_turnover"],
        "yearly_returns": {f"ret_{yr}": raw.get(f"ret_{yr}", 0) for yr in range(2018, 2027)},
        "nav_hash": hashlib.md5(
            results["nav"]["total_value"].to_csv(index=False).encode()
        ).hexdigest()[:16],
        "trades_hash": hashlib.md5(
            results["trades"].to_csv(index=False).encode()
        ).hexdigest()[:16],
        "elapsed_s": round(elapsed, 0),
    }
    logger.info(f"  Run {run_id}: ret={metrics_out['total_return_pct']}% dd={metrics_out['max_drawdown_pct']}% "
                f"trades={metrics_out['total_trades']} calmar={metrics_out['calmar_ratio']} "
                f"nav_hash={metrics_out['nav_hash']} trades_hash={metrics_out['trades_hash']}")
    return metrics_out


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()
    metrics = run_and_measure(CANDIDATE_B_GENES, args.run_id)
    out_dir = Path("data/ga_results/candidate_b_final_check_20260514_124500")
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"run{args.run_id}_metrics.json", "w") as f:
        json.dump(metrics, f, indent=2)


if __name__ == "__main__":
    main()

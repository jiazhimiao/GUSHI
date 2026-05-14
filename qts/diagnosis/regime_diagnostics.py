"""Regime score diagnostics and sensitivity testing.

Outputs:
    1. Daily regime score timeline (2018-2026)
    2. Yearly regime state distribution
    3. score_high / score_low sensitivity sweep (7 combinations)
"""

import json
import pandas as pd
import numpy as np

from qts.utils.config import get_project_root
from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.backtest.performance import compute_metrics


def compute_regime_timeline(genes: dict, p: dict,
                            start: str = "2018-01-01",
                            end: str = "2026-05-08") -> pd.DataFrame:
    """Run one backtest and extract daily regime score + sub-scores.

    Returns DataFrame with: date, benchmark_close, regime_score, regime_label,
    breadth_score, trend_score, stability_score, volume_score
    """
    root = get_project_root()

    regime = RegimeEngine(**p)
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

    # Monkey-patch to capture per-date score breakdown
    _captured_scores: list[dict] = []
    _orig_compute = s.regime_engine.compute_score

    def _capture_score(date, breadth, trend_raw=None, stability_raw=None,
                       volume_raw=None, **kw):
        score = _orig_compute(date, breadth,
                              trend_raw=trend_raw, stability_raw=stability_raw,
                              volume_raw=volume_raw, **kw)
        _captured_scores.append({
            "date": date,
            "regime_score": round(score, 4),
            "breadth_score": round(s.regime_engine.w_breadth * breadth, 4),
            "trend_score": round(s.regime_engine.w_trend * (trend_raw or 0), 4),
            "stability_score": round(s.regime_engine.w_stability * (stability_raw or 0), 4),
            "volume_score": round(s.regime_engine.w_volume * (volume_raw or 0), 4),
        })
        return score

    s.regime_engine.compute_score = _capture_score

    engine = BacktestEngine(
        bar_path=str(root / "data/raw/HS300_daily.parquet"),
        calendar_path=str(root / "data/raw/calendar.parquet"),
        start_date=start, end_date=end,
        initial_cash=1_000_000,
        execution_price="intraday_close",
        intraday_spread_bps=15,
    )
    engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)

    return pd.DataFrame(_captured_scores)


def sensitivity_sweep(base_genes: dict, score_high_values: list[float],
                      score_low_values: list[float],
                      start: str = "2018-01-01",
                      end: str = "2026-05-08") -> pd.DataFrame:
    """Lightweight sensitivity sweep: 7 runs, serial, single-process.

    Returns DataFrame with metrics per (score_high, score_low) combination.
    """
    root = get_project_root()
    rows = []

    for sh in score_high_values:
        for sl in score_low_values:
            p = genes_to_regime_kwargs(base_genes)
            p["score_high"] = sh
            p["score_low"] = sl

            regime = RegimeEngine(**p)
            s = TrendBreakoutStrategy(
                breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
                max_loss_pct=base_genes["max_loss_pct"],
                min_breadth=0.50, breadth_half=0.30,
                atr_multiple=2.0, atr_period=int(base_genes["atr_period"]),
                profit_lock_pct=base_genes["profit_lock_pct"],
                top_n=10, max_weight_per_stock=base_genes["max_weight_per_stock"],
            )
            s.regime_engine = regime
            s.use_dow_filter = False
            s.breadth_ma_days = int(base_genes["breadth_ma_days"])
            s.strategy_max_dd = base_genes["strategy_max_dd"]
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

            # Yearly returns
            nav_df = nav.copy()
            nav_df["year"] = pd.to_datetime(nav_df["date"]).dt.year
            yearly_vals = {}
            for yr in [2019, 2020, 2024]:
                ynav = nav_df[nav_df["year"] == yr]
                if len(ynav) >= 2:
                    yr_ret = (ynav["total_value"].iloc[-1] / ynav["total_value"].iloc[0] - 1) * 100
                    yearly_vals[f"ret_{yr}"] = round(yr_ret, 2)
                else:
                    yearly_vals[f"ret_{yr}"] = 0

            # Bear year max DD
            bear_dd = 0
            for yr in [2018, 2022]:
                ynav = nav_df[nav_df["year"] == yr]
                if len(ynav) >= 2:
                    peak = ynav["total_value"].cummax()
                    dd = (ynav["total_value"] - peak) / peak
                    bear_dd = min(bear_dd, dd.min())
            bear_dd_pct = round(bear_dd * 100, 2)

            rows.append({
                "score_high": sh,
                "score_low": sl,
                "total_return_pct": metrics.get("total_return_pct", 0),
                "annual_return_pct": metrics.get("annual_return_pct", 0),
                "max_drawdown_pct": metrics.get("max_drawdown_pct", 0),
                "calmar": metrics.get("calmar_ratio", 0),
                **yearly_vals,
                "bear_year_max_dd_pct": bear_dd_pct,
            })

    return pd.DataFrame(rows)


def genes_to_regime_kwargs(genes: dict) -> dict:
    """Same mapping as ga_optimizer.py."""
    return {
        "w_breadth": genes["w_breadth"],
        "w_trend": genes["w_trend"],
        "w_stability": genes["w_stability"],
        "w_volume": genes["w_volume"],
        "score_low": genes["score_low"],
        "score_high": genes["score_high"],
        "breakout_bull": int(genes["breakout_bull"]),
        "breakout_bear": int(genes["breakout_bear"]),
        "atr_bull": genes["atr_bull"],
        "atr_bear": genes["atr_bear"],
        "vol_ratio_bull": genes["vol_ratio_bull"],
        "vol_ratio_bear": genes["vol_ratio_bear"],
        "top_n_bull": int(genes["top_n_bull"]),
        "top_n_bear": int(genes["top_n_bear"]),
        "support_bull": int(genes["support_bull"]),
        "support_bear": int(genes["support_bear"]),
        "ma_days_bull": int(genes["ma_bull"]),
        "ma_days_bear": int(genes["ma_bear"]),
    }


def daily_regime_table(regime_df, regime_timeline_df):
    """Merge market regime labels with daily regime scores.

    Note: breadth_delta_10d and momentum fields marked as unavailable
    since they require stock-level data.
    """
    if regime_df is None or regime_timeline_df is None:
        return pd.DataFrame()

    merged = regime_timeline_df.merge(
        regime_df[["trade_date", "close", "label"]],
        left_on="date", right_on="trade_date", how="left"
    )
    merged = merged.rename(columns={"close": "benchmark_close", "label": "regime_label"})

    # Fields we cannot compute from index data alone
    merged["breadth_delta_10d"] = None  # requires stock-level breadth
    merged["momentum_20d"] = None       # requires stock-level data
    merged["momentum_60d"] = None       # requires stock-level data
    merged["drawdown"] = None            # filled below from benchmark

    # Benchmark drawdown
    if "benchmark_close" in merged.columns:
        peak = merged["benchmark_close"].cummax()
        merged["drawdown"] = ((merged["benchmark_close"] - peak) / peak * 100).round(2)

    cols = ["date", "benchmark_close", "regime_score", "regime_label",
            "breadth_score", "trend_score", "stability_score", "volume_score",
            "drawdown", "momentum_20d", "momentum_60d", "breadth_delta_10d"]
    return merged[[c for c in cols if c in merged.columns]]

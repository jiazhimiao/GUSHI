"""Daily signal / paper trading report — read-only, no orders.

Usage:
    python scripts/generate_daily_signal.py --date 2026-05-14
    python scripts/generate_daily_signal.py --date 2026-05-14 --positions positions.json

Output:
    reports/daily_signal/YYYY-MM-DD_report.md
    reports/daily_signal/YYYY-MM-DD_signal.json
"""
import sys, json
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from qts.backtest.engine import load_bars
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.utils.config import get_project_root
from qts.utils.logger import logger

ROOT = get_project_root()

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


def build_strategy():
    genes = CANDIDATE_B_GENES
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
    return s


def load_positions(path):
    """Load current positions from JSON. Returns DataFrame with columns:
    symbol, quantity, avg_cost, entry_price, entry_date, current_weight."""
    if path is None or not Path(path).exists():
        return pd.DataFrame(columns=["symbol", "quantity", "avg_cost", "entry_price", "entry_date", "current_weight"])
    with open(path) as f:
        data = json.load(f)
    if not data:
        return pd.DataFrame(columns=["symbol", "quantity", "avg_cost", "entry_price", "entry_date", "current_weight"])
    return pd.DataFrame(data)


def get_constituents_for_date(target_date, constituent_quarterly):
    """Get index constituents for a given date (nearest prior quarterly snapshot)."""
    if not constituent_quarterly:
        return None
    sorted_dates = sorted(constituent_quarterly.keys())
    for q_date in reversed(sorted_dates):
        if q_date <= target_date:
            return constituent_quarterly[q_date]
    return constituent_quarterly[sorted_dates[0]]


def validate_data(target_date, bars, calendar, constituents):
    """Data integrity checks. Returns list of warnings."""
    warnings = []

    # Check if target_date is a trading day
    cal_dates = set(calendar[calendar["is_trading_day"] == True]["trade_date"].astype(str).str[:10])
    if target_date not in cal_dates:
        warnings.append(f"{target_date} is NOT a trading day in calendar.")

    # Check if we have market data for this date
    td_bars = bars[bars["trade_date"] == target_date]
    if td_bars.empty:
        warnings.append(f"No market data for {target_date}.")

    # Check constituent count
    if constituents:
        active = [s for s in constituents if s in bars["symbol"].unique()]
        n_active = len(active)
        if n_active < 200:
            warnings.append(f"Constituent count low: {n_active} (expected ~299).")
    else:
        warnings.append("No constituent data loaded.")

    # Check OHLCV integrity for target date
    if not td_bars.empty:
        missing_ohlcv = td_bars[["open", "high", "low", "close", "volume"]].isna().any(axis=1).sum()
        if missing_ohlcv > 0:
            warnings.append(f"{missing_ohlcv} symbols have missing OHLCV on {target_date}.")

        # Check for limit-up/down
        if "limit_up" in td_bars.columns and "limit_down" in td_bars.columns:
            limit_up_count = (td_bars["close"] >= td_bars["limit_up"]).sum()
            limit_down_count = (td_bars["close"] <= td_bars["limit_down"]).sum()
            if limit_up_count > 0:
                warnings.append(f"{limit_up_count} symbols at limit-up on {target_date}.")
            if limit_down_count > 0:
                warnings.append(f"{limit_down_count} symbols at limit-down on {target_date}.")

    return warnings


def generate(date_str, positions_path=None):
    target_date = date_str[:10]

    # ── Load data ──
    bar_path = ROOT / "data/raw/HS300_daily.parquet"
    calendar_path = ROOT / "data/raw/calendar.parquet"
    const_path = ROOT / "data/historical_constituents.json"

    bars = load_bars(str(bar_path), "2018-01-01", target_date)
    calendar = pd.read_parquet(calendar_path)

    with open(const_path) as f:
        const_data = json.load(f)
    index_entry = const_data.get("indices", {}).get("HS300")
    constituent_quarterly = index_entry.get("quarterly", {}) if index_entry else {}
    if constituent_quarterly:
        sorted_dates = sorted(constituent_quarterly.keys())
        logger.info(f"Loaded constituents: {len(sorted_dates)} quarters, {sorted_dates[0]} ~ {sorted_dates[-1]}")
    constituents_today = get_constituents_for_date(target_date, constituent_quarterly)

    # ── Build strategy + caches (matching BacktestEngine init) ──
    strategy = build_strategy()

    prices = bars.pivot(index="trade_date", columns="symbol", values="close")
    volumes = bars.pivot(index="trade_date", columns="symbol", values="volume")
    highs = bars.pivot(index="trade_date", columns="symbol", values="high")
    opens = bars.pivot(index="trade_date", columns="symbol", values="open")
    lows = bars.pivot(index="trade_date", columns="symbol", values="low")

    # Breadth
    if constituents_today:
        b_cols = [c for c in constituents_today if c in prices.columns]
        prices_b = prices[b_cols] if b_cols else prices
    else:
        prices_b = prices
    bma = strategy.breadth_ma_days
    ma_breadth = prices_b.rolling(bma).mean()
    breadth_series = (prices_b > ma_breadth).mean(axis=1)
    strategy._breadth_cache = breadth_series

    # Pivots + bars cache
    strategy._prices_pivot = prices
    strategy._volumes_pivot = volumes
    strategy._highs_pivot = highs
    strategy._opens_pivot = opens
    strategy._lows_pivot = lows
    strategy._bars_by_symbol = {
        sym: group.sort_values("trade_date") for sym, group in bars.groupby("symbol")
    }

    # Regime raw cache (pre-compute or leave for fallback)
    strategy._regime_raw_cache = None  # Use fallback pivot-based computation

    # ── Data integrity ──
    warnings = validate_data(target_date, bars, calendar, constituents_today)

    # ── Build market_data for target_date (P1a: only today's bars, constituent-filtered) ──
    td_bars_raw = bars[bars["trade_date"] == target_date].copy()
    if constituents_today:
        allowed = [s for s in constituents_today if s in td_bars_raw["symbol"].unique()]
        market_data = td_bars_raw[td_bars_raw["symbol"].isin(allowed)]
    else:
        market_data = td_bars_raw

    # ── Load current positions ──
    positions = load_positions(positions_path)
    has_positions = not positions.empty

    # ── Generate signals ──
    signals = strategy.generate_signals(
        current_date=target_date,
        market_data=market_data,
        factor_data=pd.DataFrame(),
        current_positions=positions,
    )

    # ── Extract regime info (compute score independently) ──
    regime_score = None
    if strategy.regime_engine is not None:
        b = breadth_series.get(target_date, 0)
        allowed_cols = list(market_data["symbol"].unique())
        p_slice = prices.loc[:target_date, [c for c in allowed_cols if c in prices.columns]]
        v_slice = volumes.loc[:target_date, [c for c in allowed_cols if c in volumes.columns]]
        if not p_slice.empty:
            regime_score = round(float(strategy.regime_engine.compute_score(
                target_date, b, prices=p_slice, volumes=v_slice)), 3)
    adapted = {
        "breakout_days": strategy.breakout_days,
        "support_days": strategy.support_days,
        "ma_days": strategy.ma_days,
        "atr_multiple": strategy.atr_multiple,
        "volume_ratio": strategy.volume_ratio,
        "top_n": strategy.top_n,
    }

    # ── Build candidate list and target portfolio ──
    candidate_list = []
    target_list = []
    actions_list = []
    if not signals.empty:
        for _, row in signals.iterrows():
            sym = row.get("symbol", "")
            tw = round(float(row.get("target_weight", 0)), 4)
            score = round(float(row.get("score", 0)), 4)
            reason = str(row.get("reason", ""))
            entry = {"symbol": sym, "target_weight": tw, "score": score, "reason": reason}
            candidate_list.append(entry)
            if tw > 0:
                target_list.append(entry)

    # Actions: compare current positions vs target_portfolio (weight>0 only)
    target_syms = set(t["symbol"] for t in target_list)
    current_syms = set(positions["symbol"]) if has_positions else set()

    # BUY: in target, not in current
    for sym in target_syms - current_syms:
        t = next(t for t in target_list if t["symbol"] == sym)
        actions_list.append({"symbol": sym, "action": "BUY",
                             "target_weight": t["target_weight"],
                             "reason": t["reason"]})
    # SELL: in current, not in target
    for sym in current_syms - target_syms:
        pos_row = positions[positions["symbol"] == sym].iloc[0]
        reason = "not in target portfolio"
        if not target_syms and candidate_list:
            reason = "regime too weak — candidates exist but alloc=0"
        elif not target_syms:
            reason = "empty target (regime score too low)"
        actions_list.append({"symbol": sym, "action": "SELL",
                             "current_weight": round(float(pos_row.get("current_weight", 0)), 4),
                             "reason": reason})
    # HOLD/ADJUST: in both
    for sym in target_syms & current_syms:
        t = next(t for t in target_list if t["symbol"] == sym)
        p_row = positions[positions["symbol"] == sym].iloc[0]
        tw = t["target_weight"]
        cw = round(float(p_row.get("current_weight", 0)), 4)
        if abs(tw - cw) > 0.001:
            actions_list.append({"symbol": sym, "action": "ADJUST",
                                 "current_weight": cw, "target_weight": tw,
                                 "reason": "weight change"})
        else:
            actions_list.append({"symbol": sym, "action": "HOLD",
                                 "current_weight": cw, "reason": "weight unchanged"})
    # Note: candidates with weight=0 don't produce BUY actions
    skipped = len(candidate_list) - len(target_list)
    if skipped > 0:
        actions_list.append({"symbol": f"({skipped} candidates)", "action": "SKIPPED",
                             "current_weight": "", "target_weight": "",
                             "reason": "alloc=0 — regime too weak"})

    # ── Risk checks ──
    if signals.empty:
        if not warnings:
            warnings.append("Empty target portfolio (normal if regime score is low).")
    if len(target_list) > 10:
        warnings.append(f"Target portfolio size ({len(target_list)}) exceeds top_n (10).")

    # ── Write outputs ──
    out_dir = ROOT / "reports" / "daily_signal"
    out_dir.mkdir(parents=True, exist_ok=True)

    # JSON
    signal_json = {
        "date": target_date,
        "generated_at": datetime.now().isoformat(),
        "time_context": "Based on close data of this date. For review or next-trading-day reference, not real-time intraday.",
        "baseline": "Candidate B (score_high=0.80, atr_bear=0.89, breakout_bear=40)",
        "regime": {
            "score": regime_score,
            "adapted_params": adapted,
        },
        "candidate_signals": candidate_list,
        "target_portfolio": target_list,
        "actions": actions_list,
        "alloc_zero_note": "Candidates exist but alloc=0 — no actual BUY orders" if (candidate_list and not target_list) else "",
        "warnings": warnings,
        "has_positions": has_positions,
    }
    with open(out_dir / f"{target_date}_signal.json", "w") as f:
        json.dump(signal_json, f, indent=2, ensure_ascii=False, default=str)

    # Markdown report
    lines = [
        f"# Daily Signal Report — {target_date}",
        f"",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Time context**: Based on {target_date} close data. For review or next-trading-day reference, not real-time intraday.",
        f"**Baseline**: Candidate B (score_high=0.80, atr_bear=0.89, breakout_bear=40)",
        f"",
        f"## Market Regime",
        f"",
    ]
    lines.append(f"- **Regime Score**: {regime_score:.3f}" if regime_score is not None else "- **Regime Score**: unavailable")
    if adapted:
        lines.append(f"- **Adaptive Params**: brk={adapted.get('breakout_days','?')}d, "
                     f"sup={adapted.get('support_days','?')}d, "
                     f"ma={adapted.get('ma_days','?')}d, "
                     f"atr_x={adapted.get('atr_multiple','?')}x, "
                     f"top_n={adapted.get('top_n','?')}")
    # Determine empty-signal reason
    empty_reason = ""
    if signals.empty:
        if regime_score is not None and regime_score <= 0.01:
            empty_reason = f"Regime score {regime_score:.3f} <= 0.01 — extreme bear, forced cash."
        elif regime_score is not None and regime_score < CANDIDATE_B_GENES["score_low"]:
            empty_reason = f"Regime score {regime_score:.3f} < score_low {CANDIDATE_B_GENES['score_low']} — bear regime, alloc=0, no breakouts met criteria."
        elif regime_score is not None:
            empty_reason = f"Regime score {regime_score:.3f} — no breakouts found among {len(market_data)} constituent stocks."
        else:
            empty_reason = "Regime score unavailable — possible data issue."

    if signals.empty:
        lines.append(f"- **Result**: EMPTY target")
        lines.append(f"- **Reason**: {empty_reason}")
    else:
        alloc = round(sum(t["target_weight"] for t in target_list) * 100, 1)
        lines.append(f"- **Allocation**: {alloc}% ({len(target_list)} actual targets)")
        if candidate_list and not target_list:
            lines.append(f"- **⚠ Alloc=0**: {len(candidate_list)} candidates exist but alloc_pct=0. No actual BUY orders.")
            lines.append(f"  Candidates are shown below for reference but are NOT actionable.")

    lines += [
        f"",
        f"## Candidate Signals (Breakout Detected)",
        f"",
    ]
    if candidate_list:
        lines.append("| Symbol | Score | Reason |")
        lines.append("|---|---|---|")
        for c in candidate_list:
            lines.append(f"| {c['symbol']} | {c['score']:.4f} | {c['reason']} |")
    else:
        lines.append(f"*(no breakout candidates today)*")

    lines += [
        f"",
        f"## Target Portfolio (Actual Positions, weight > 0)",
        f"",
    ]
    if target_list:
        lines.append(f"| Symbol | Target Weight | Score | Reason |")
        lines.append(f"|---|---:|---:|------|")
        for t in target_list:
            lines.append(f"| {t['symbol']} | {t['target_weight']:.4f} | {t['score']:.4f} | {t['reason']} |")
    elif candidate_list:
        lines.append(f"*(all {len(candidate_list)} candidates have weight=0 — regime too weak to allocate)*")
    else:
        lines.append(f"*(empty — no target positions)*")

    lines += [
        f"",
        f"## Actions",
        f"",
    ]
    if actions_list:
        lines.append(f"| Symbol | Action | Current Weight | Target Weight | Reason |")
        lines.append(f"|---|---:|---:|------|")
        for a in actions_list:
            cw = a.get("current_weight", "")
            tw = a.get("target_weight", "")
            lines.append(f"| {a['symbol']} | **{a['action']}** | "
                         f"{cw if cw != '' else '-'} | {tw if tw != '' else '-'} | {a['reason']} |")
    else:
        lines.append(f"*(no actions — positions unchanged)*")

    lines += [
        f"",
        f"## Data Integrity",
        f"",
    ]
    if constituents_today:
        lines.append(f"- Constituents: {len(constituents_today)} symbols for {target_date}")
    lines.append(f"- Market data: {len(market_data)} bars for {target_date}")
    if warnings:
        lines.append(f"")
        for w in warnings:
            lines.append(f"- ⚠ {w}")
    else:
        lines.append(f"- ✓ No data integrity warnings")

    lines += [
        f"",
        f"## Risk Notes",
        f"",
        f"- Strategy: Candidate B (trend_breakout, no pullback, no rank_buffer)",
        f"- Max DD threshold: {CANDIDATE_B_GENES['strategy_max_dd']*100:.0f}%",
        f"- pullback_entry: False | rank_buffer: False | use_dow_filter: False",
        f"- **This is a paper signal only. No orders submitted.**",
    ]

    with open(out_dir / f"{target_date}_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Signal report saved to {out_dir / f'{target_date}_report.md'}")
    logger.info(f"Signal JSON saved to {out_dir / f'{target_date}_signal.json'}")

    if signals.empty:
        logger.info(f"Regime: empty target (score={regime_score})")
    else:
        logger.info(f"Regime: score={regime_score}, {len(signals)} targets")
    for w in warnings:
        logger.warning(f"  {w}")

    return signal_json


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", required=True, help="Target date YYYY-MM-DD")
    parser.add_argument("--positions", default=None, help="Path to positions.json")
    parser.add_argument("--replay-last-n", type=int, default=None,
                        help="Replay last N trading days (future)")
    args = parser.parse_args()

    if args.replay_last_n:
        logger.info(f"Replay mode: last {args.replay_last_n} trading days")
        calendar = pd.read_parquet(ROOT / "data/raw/calendar.parquet")
        cal_dates = sorted(calendar[calendar["is_trading_day"] == True]["trade_date"].astype(str).str[:10])
        cal_dates = [d for d in cal_dates if d <= args.date]
        dates = cal_dates[-args.replay_last_n:]
        logger.info(f"Dates: {dates[0]} → {dates[-1]} ({len(dates)} days)")
        logger.info(f"NOTE: Each day uses empty positions. Signals are isolated snapshots, not continuous simulation.")
        for d in dates:
            logger.info(f"\n{'='*40}\n  {d}\n{'='*40}")
            generate(d, args.positions)
        logger.info(f"\nReplay complete. {len(dates)} reports generated in reports/daily_signal/")
        return

    generate(args.date, args.positions)


if __name__ == "__main__":
    main()

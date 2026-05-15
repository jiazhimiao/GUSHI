"""Daily signal / paper trading report — read-only, no orders.

Aligned with BacktestEngine behavior:
  - Breadth uses period-start constituent set (fixed, matching engine)
  - Exit check (strategy.check_exit) runs BEFORE signal generation each day
  - Empty target does NOT liquidate positions (matching engine skip behavior)
  - entry_price / peak tracked for exit simulation

Usage:
    python scripts/generate_daily_signal.py --date 2026-05-14
    python scripts/generate_daily_signal.py --date 2026-05-14 --positions positions.json
    python scripts/generate_daily_signal.py --replay-last-n 30

Output (single date):
    reports/daily_signal/YYYY-MM-DD_report.md
    reports/daily_signal/YYYY-MM-DD_signal.json

Output (replay mode):
    reports/paper_trading/replay_YYYYMMDD_HHMMSS/
"""
import sys, json, csv
from pathlib import Path
from datetime import datetime, timedelta
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from qts.backtest.engine import load_bars
from qts.backtest.data_context import build_strategy_context
from qts.backtest.paper_broker import PaperBroker
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
    if path is None or not Path(path).exists():
        return pd.DataFrame(columns=["symbol", "quantity", "locked_quantity", "avg_cost"])
    with open(path) as f:
        data = json.load(f)
    if not data:
        return pd.DataFrame(columns=["symbol", "quantity", "locked_quantity", "avg_cost"])
    return pd.DataFrame(data)


def positions_data_to_df(positions_data):
    """Convert weight-only paper positions to DataFrame matching broker format.

    BacktestEngine passes broker.get_all_positions() which has columns:
    symbol, quantity, locked_quantity, avg_cost.

    Paper positions are weight-only, so quantity is derived from weight × notional / price.
    """
    cols = ["symbol", "quantity", "locked_quantity", "avg_cost"]
    if not positions_data:
        return pd.DataFrame(columns=cols)
    df = pd.DataFrame(positions_data)
    # Ensure broker-compatible columns exist
    for col in cols:
        if col not in df.columns:
            df[col] = 0
    return df[cols]


def build_next_positions(current_positions_list, target_portfolio, date_str,
                         entry_prices=None, entry_peaks=None,
                         signals_empty=False):
    """Build next day's paper positions, aligned with BacktestEngine logic.

    Key alignment: when signals are empty (regime < score_low or no candidates),
    existing positions are NOT sold. The engine does broker.end_of_day(); continue
    — positions persist. Same when target is empty.
    """
    if entry_prices is None:
        entry_prices = {}
    if entry_peaks is None:
        entry_peaks = {}

    current_map = {p["symbol"]: p for p in (current_positions_list or [])}
    target_map = {t["symbol"]: t for t in (target_portfolio or [])}

    # If signals were empty, return current positions unchanged (no sells)
    if signals_empty:
        return list(current_positions_list), entry_prices, entry_peaks

    next_positions = []
    for sym, target in target_map.items():
        if sym in current_map:
            ep = current_map[sym].get("entry_price", 0)
            pk = current_map[sym].get("peak_price", 0)
            # Keep original entry_date
            entry_date = current_map[sym].get("entry_date", date_str)
        else:
            # New entry — entry_price from close price today (set by caller)
            ep = 0  # Will be filled by caller
            pk = 0
            entry_date = date_str
        next_positions.append({
            "symbol": sym,
            "entry_date": entry_date,
            "current_weight": target["target_weight"],
            "entry_price": ep,
            "peak_price": pk,
            "quantity": 0,
            "locked_quantity": 0,
            "avg_cost": ep if ep else 0.0,
        })
        entry_prices[sym] = ep
        entry_peaks[sym] = pk

    # Note: stocks not in target are dropped (sell). This matches engine's
    # _execute_rebalance behavior where current_symbols - target_symbols are sold.

    return next_positions, entry_prices, entry_peaks


def get_constituents_for_date(target_date, constituent_quarterly):
    if not constituent_quarterly:
        return None
    sorted_dates = sorted(constituent_quarterly.keys())
    for q_date in reversed(sorted_dates):
        if q_date <= target_date:
            return constituent_quarterly[q_date]
    return constituent_quarterly[sorted_dates[0]]


def validate_data(target_date, bars, calendar, constituents):
    warnings = []
    cal_dates = set(calendar[calendar["is_trading_day"] == True]["trade_date"].astype(str).str[:10])
    if target_date not in cal_dates:
        warnings.append(f"{target_date} is NOT a trading day in calendar.")
    td_bars = bars[bars["trade_date"] == target_date]
    if td_bars.empty:
        warnings.append(f"No market data for {target_date}.")
    if constituents:
        active = [s for s in constituents if s in bars["symbol"].unique()]
        n_active = len(active)
        if n_active < 200:
            warnings.append(f"Constituent count low: {n_active} (expected ~299).")
    else:
        warnings.append("No constituent data loaded.")
    if not td_bars.empty:
        missing_ohlcv = td_bars[["open", "high", "low", "close", "volume"]].isna().any(axis=1).sum()
        if missing_ohlcv > 0:
            warnings.append(f"{missing_ohlcv} symbols have missing OHLCV on {target_date}.")
        if "limit_up" in td_bars.columns and "limit_down" in td_bars.columns:
            limit_up_count = (td_bars["close"] >= td_bars["limit_up"]).sum()
            limit_down_count = (td_bars["close"] <= td_bars["limit_down"]).sum()
            if limit_up_count > 0:
                warnings.append(f"{limit_up_count} symbols at limit-up on {target_date}.")
            if limit_down_count > 0:
                warnings.append(f"{limit_down_count} symbols at limit-down on {target_date}.")
    return warnings


def generate(date_str, positions_path=None, positions_data=None, output_dir=None,
             breadth_ref_date=None, ctx=None, broker=None):
    """Generate daily signal for a single date.

    Two modes:
      1. PaperBroker mode (broker is not None): full execution simulation
         with exit checks, quantity/lot_size, T+1. Mirrors BacktestEngine.
      2. Legacy weight-only mode (broker is None): simple target_portfolio
         position mapping (backward compatible for single-date use).

    Args:
        date_str: Target date string YYYY-MM-DD.
        positions_path: Path to positions.json file (legacy).
        positions_data: List of position dicts (legacy weight-only format).
        output_dir: Override output directory (Path).
        breadth_ref_date: Date string for breadth constituent filtering (legacy).
        ctx: Pre-built DataContext.
        broker: PaperBroker instance. If provided, enables full simulation mode.

    Returns:
        dict with keys: signal_json, daily_summary, and (broker or next_positions).
    """
    target_date = date_str[:10]
    if breadth_ref_date is None:
        breadth_ref_date = target_date

    # ── Load data (or use pre-built context) ──
    if ctx is not None:
        bars = ctx.bars
        calendar = ctx.calendar
        constituent_quarterly = ctx.constituent_quarterly
        prices = ctx.prices
        volumes = ctx.volumes
        highs = ctx.highs
        opens = ctx.opens
        lows = ctx.lows
        breadth_series = ctx.breadth_series
    else:
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

        prices = bars.pivot(index="trade_date", columns="symbol", values="close")
        volumes = bars.pivot(index="trade_date", columns="symbol", values="volume")
        highs = bars.pivot(index="trade_date", columns="symbol", values="high")
        opens = bars.pivot(index="trade_date", columns="symbol", values="open")
        lows = bars.pivot(index="trade_date", columns="symbol", values="low")

        # Breadth (legacy per-call)
        breadth_constituents = get_constituents_for_date(breadth_ref_date, constituent_quarterly)
        if breadth_constituents:
            b_cols = [c for c in breadth_constituents if c in prices.columns]
            prices_b = prices[b_cols] if b_cols else prices
        else:
            prices_b = prices
        bma = 35
        ma_breadth = prices_b.rolling(bma).mean()
        breadth_series = (prices_b > ma_breadth).mean(axis=1)

    if constituent_quarterly:
        sorted_dates = sorted(constituent_quarterly.keys())
    constituents_today = get_constituents_for_date(target_date, constituent_quarterly)

    # ── Build strategy + caches ──
    strategy = build_strategy()

    if ctx is not None:
        # Use pre-built context directly
        ctx.apply_to_strategy(strategy)
    else:
        # Legacy: build caches manually
        strategy._breadth_cache = breadth_series
        strategy._prices_pivot = prices
        strategy._volumes_pivot = volumes
        strategy._highs_pivot = highs
        strategy._opens_pivot = opens
        strategy._lows_pivot = lows
        strategy._bars_by_symbol = {
            sym: group.sort_values("trade_date") for sym, group in bars.groupby("symbol")
        }
        strategy._regime_raw_cache = None

    # ── Data integrity ──
    warnings = validate_data(target_date, bars, calendar, constituents_today)

    # ── Build market_data for target_date ──
    if ctx is not None and target_date in ctx.daily_market_data:
        market_data = ctx.daily_market_data[target_date]
    else:
        td_bars_raw = bars[bars["trade_date"] == target_date].copy()
        if constituents_today:
            allowed = [s for s in constituents_today if s in td_bars_raw["symbol"].unique()]
            market_data = td_bars_raw[td_bars_raw["symbol"].isin(allowed)]
        else:
            market_data = td_bars_raw

    # ── Load current positions ──
    if positions_data is not None:
        positions = positions_data_to_df(positions_data)
        # Restore entry_prices and entry_peaks from position data
        entry_prices = {}
        entry_peaks = {}
        for p in (positions_data or []):
            sym = p["symbol"]
            ep = p.get("entry_price", 0.0) or 0.0
            pk = p.get("peak_price", 0.0) or 0.0
            entry_prices[sym] = ep
            entry_peaks[sym] = pk
    else:
        positions = load_positions(positions_path)
        entry_prices = {}
        entry_peaks = {}
    has_positions = not positions.empty

    # ═══════════════════════════════════════════════════════════════════════
    # Execution flow — PaperBroker mode or legacy mode
    # ═══════════════════════════════════════════════════════════════════════
    broker_fills = []  # fills from PaperBroker (BUY/SELL dicts)
    exit_actions = []  # exit descriptions for reporting
    price_map = {}
    if not market_data.empty:
        price_map = dict(zip(market_data["symbol"], market_data["close"]))

    if broker is not None:
        # ── PaperBroker mode: full execution simulation ──
        # STEP 1: Update peaks from today's prices
        for sym in list(broker.positions.keys()):
            pos = broker.positions[sym]
            if sym in price_map and price_map[sym] > pos.get("entry_peak", 0):
                broker.positions[sym]["entry_peak"] = price_map[sym]

        # STEP 2: Exit check (mirrors engine _check_and_execute_exits)
        exit_fills = broker.check_and_execute_exits(strategy, target_date, bars, price_map)
        for ef in exit_fills:
            exit_actions.append({
                "symbol": ef["symbol"], "action": "SELL",
                "reason": ef.get("reason", "strategy_exit"),
                "exit_type": "strategy_exit",
            })
            broker_fills.append(ef)
            logger.info(f"[{target_date}] 模拟卖出 {ef['symbol']} ({ef.get('reason','')})")

        # STEP 3: Generate signals (with current broker positions)
        current_positions_df = broker.get_all_positions()
        signals = strategy.generate_signals(
            current_date=target_date,
            market_data=market_data,
            factor_data=pd.DataFrame(),
            current_positions=current_positions_df,
        )

        # STEP 4: Build target portfolio, execute rebalance
        candidate_list = []
        target_list = []
        signals_empty = signals.empty
        if not signals_empty:
            for _, row in signals.iterrows():
                sym = row.get("symbol", "")
                tw = round(float(row.get("target_weight", 0)), 4)
                score = round(float(row.get("score", 0)), 4)
                reason = str(row.get("reason", ""))
                entry = {"symbol": sym, "target_weight": tw, "score": score, "reason": reason}
                candidate_list.append(entry)
                if tw > 0:
                    target_list.append(entry)
            # Execute weight-based rebalance
            rebalance_fills = broker.execute_weight_rebalance(target_list, price_map, target_date)
            broker_fills.extend(rebalance_fills)

        # STEP 5: end_of_day (clear T+1 locks)
        broker.end_of_day()

        # Build actions from fills
        actions_list = []
        for f in exit_fills:
            actions_list.append({"symbol": f["symbol"], "action": "SELL",
                                "reason": f.get("reason", "strategy_exit")})
        if not signals_empty:
            target_syms = set(t["symbol"] for t in target_list)
            current_syms = set(broker.positions.keys())
            for sym in target_syms - current_syms:
                t = next(t for t in target_list if t["symbol"] == sym)
                actions_list.append({"symbol": sym, "action": "BUY",
                                    "target_weight": t["target_weight"], "reason": t["reason"]})
            for sym in current_syms - target_syms:
                actions_list.append({"symbol": sym, "action": "SELL",
                                    "reason": "removed from target"})
            for sym in target_syms & current_syms:
                actions_list.append({"symbol": sym, "action": "HOLD",
                                    "reason": "in target"})
        elif not signals_empty and not target_list:
            actions_list.append({"symbol": f"({len(candidate_list)})", "action": "SKIPPED",
                                "reason": "alloc=0"})

        # Broker-based daily summary fields
        n_positions = len(broker.positions)
        has_positions_bool = n_positions > 0
        total_nav = broker.get_nav(price_map) if price_map else broker.cash
        position_value = broker.get_position_value(price_map) if price_map else 0
        gross_exposure = position_value / total_nav if total_nav > 0 else 0

    else:
        # ── Legacy weight-only mode ──
        exit_actions = []
        if not positions.empty:
            latest_bars = bars[bars["trade_date"] == target_date]
            if not latest_bars.empty:
                price_map_legacy = dict(zip(latest_bars["symbol"], latest_bars["close"]))
                for _, pos_row in positions.iterrows():
                    sym = pos_row["symbol"]
                    ep = entry_prices.get(sym, 0.0) or 0.0
                    peak = entry_peaks.get(sym, 0.0) or 0.0
                    if sym in price_map_legacy:
                        close_px = price_map_legacy[sym]
                        if close_px > peak:
                            entry_peaks[sym] = close_px
                            peak = close_px
                    should_exit, reason = strategy.check_exit(sym, target_date, bars, peak, ep)
                    if should_exit:
                        exit_actions.append({
                            "symbol": sym, "action": "SELL", "reason": reason,
                            "exit_type": "strategy_exit",
                        })
                        logger.info(f"[{target_date}] 模拟卖出 {sym} ({reason})")
            exited_syms = set(a["symbol"] for a in exit_actions)
            if exited_syms:
                positions = positions[~positions["symbol"].isin(exited_syms)]
                for sym in exited_syms:
                    entry_prices.pop(sym, None)
                    entry_peaks.pop(sym, None)

        signals = strategy.generate_signals(
            current_date=target_date,
            market_data=market_data,
            factor_data=pd.DataFrame(),
            current_positions=positions,
        )

        candidate_list = []
        target_list = []
        signals_empty = signals.empty
        actions_list = list(exit_actions)
        if not signals_empty:
            for _, row in signals.iterrows():
                sym = row.get("symbol", "")
                tw = round(float(row.get("target_weight", 0)), 4)
                score = round(float(row.get("score", 0)), 4)
                reason = str(row.get("reason", ""))
                entry = {"symbol": sym, "target_weight": tw, "score": score, "reason": reason}
                candidate_list.append(entry)
                if tw > 0:
                    target_list.append(entry)

        current_positions_for_comparison = positions
        if signals_empty:
            if has_positions and not current_positions_for_comparison.empty:
                for _, pos_row in current_positions_for_comparison.iterrows():
                    actions_list.append({
                        "symbol": pos_row["symbol"], "action": "HOLD",
                        "reason": "signals empty — positions persist"
                    })
        else:
            target_syms = set(t["symbol"] for t in target_list)
            current_syms = set(current_positions_for_comparison["symbol"]) if not current_positions_for_comparison.empty else set()
            for sym in target_syms - current_syms:
                t = next(t for t in target_list if t["symbol"] == sym)
                actions_list.append({"symbol": sym, "action": "BUY",
                                    "target_weight": t["target_weight"], "reason": t["reason"]})
            for sym in current_syms - target_syms:
                actions_list.append({"symbol": sym, "action": "SELL",
                                    "reason": "removed from target — rotation"})
            for sym in target_syms & current_syms:
                actions_list.append({"symbol": sym, "action": "HOLD",
                                    "reason": "in target — held"})

        has_positions_bool = has_positions
        n_positions = len(target_list) if not signals_empty else len(positions_data or [])
        gross_exposure = round(sum(t["target_weight"] for t in target_list), 4)

    # ── Extract regime info ──
    regime_score = None
    if strategy.regime_engine is not None:
        b = breadth_series.get(target_date, 0)
        # Use SAME fast path as TrendBreakoutStrategy: pass cached trend/stability/volume
        # dimensions instead of recomputing from raw pivots (which gives different results).
        if strategy._regime_raw_cache is not None:
            trend_raw = float(strategy._regime_raw_cache["trend"].get(target_date, 0.5))
            stability_raw = float(strategy._regime_raw_cache["stability"].get(target_date, 0.5))
            volume_raw = float(strategy._regime_raw_cache["volume"].get(target_date, 0.5))
            regime_score = round(float(strategy.regime_engine.compute_score(
                target_date, b,
                trend_raw=trend_raw, stability_raw=stability_raw, volume_raw=volume_raw,
            )), 3)
        else:
            regime_score = round(float(strategy.regime_engine.compute_score(
                target_date, b, prices=prices, volumes=volumes)), 3) if not prices.empty else None
    adapted = {
        "breakout_days": strategy.breakout_days,
        "support_days": strategy.support_days,
        "ma_days": strategy.ma_days,
        "atr_multiple": strategy.atr_multiple,
        "volume_ratio": strategy.volume_ratio,
        "top_n": strategy.top_n,
    }

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 3: Build candidate list and target portfolio
    # ═══════════════════════════════════════════════════════════════════════
    signals_empty = signals.empty
    candidate_list = []
    target_list = []
    actions_list = list(exit_actions)  # Start with exit actions
    if not signals_empty:
        for _, row in signals.iterrows():
            sym = row.get("symbol", "")
            tw = round(float(row.get("target_weight", 0)), 4)
            score = round(float(row.get("score", 0)), 4)
            reason = str(row.get("reason", ""))
            entry = {"symbol": sym, "target_weight": tw, "score": score, "reason": reason}
            candidate_list.append(entry)
            if tw > 0:
                target_list.append(entry)

    # ═══════════════════════════════════════════════════════════════════════
    # STEP 4: Compare current vs target (ALIGNED with engine rebalance logic)
    # Engine: when signals.empty → broker.end_of_day(); continue (positions persist)
    # Engine: when target non-empty → buy target-only, sell current-only
    # ═══════════════════════════════════════════════════════════════════════
    current_positions_for_comparison = positions  # After exits removed

    if signals_empty:
        # ALIGNED: Keep all existing positions (no sells due to empty target)
        # Engine does broker.end_of_day(); continue — positions persist
        if has_positions and not current_positions_for_comparison.empty:
            for _, pos_row in current_positions_for_comparison.iterrows():
                sym = pos_row["symbol"]
                actions_list.append({
                    "symbol": sym, "action": "HOLD",
                    "current_weight": 0,  # weight-only: unknown
                    "reason": "signals empty — positions persist (engine continue)"
                })
        if not exit_actions:
            # No exits, no signals — truly idle day
            if not warnings:
                warnings.append("Empty target portfolio (normal if regime score is low).")
    else:
        # Signals non-empty: compare target vs current
        target_syms = set(t["symbol"] for t in target_list)
        current_syms = set(current_positions_for_comparison["symbol"]) if not current_positions_for_comparison.empty else set()

        # BUY: in target, not in current
        for sym in target_syms - current_syms:
            t = next(t for t in target_list if t["symbol"] == sym)
            actions_list.append({"symbol": sym, "action": "BUY",
                                 "target_weight": t["target_weight"],
                                 "reason": t["reason"]})
        # SELL: in current, not in target (stock rotation)
        for sym in current_syms - target_syms:
            actions_list.append({"symbol": sym, "action": "SELL",
                                 "current_weight": 0,
                                 "reason": "removed from target — rotation"})
        # HOLD/ADJUST: in both
        for sym in target_syms & current_syms:
            t = next(t for t in target_list if t["symbol"] == sym)
            tw = t["target_weight"]
            actions_list.append({"symbol": sym, "action": "HOLD",
                                 "current_weight": tw,
                                 "reason": "in target — held"})

    # Skipped: candidates with weight=0
    skipped = len(candidate_list) - len(target_list)
    if skipped > 0:
        actions_list.append({"symbol": f"({skipped} candidates)", "action": "SKIPPED",
                             "current_weight": "", "target_weight": "",
                             "reason": "alloc=0 — regime too weak"})

    # Risk checks
    if signals_empty and not has_positions:
        if not warnings:
            warnings.append("Empty target portfolio (normal if regime score is low).")
    if len(target_list) > 10:
        warnings.append(f"Target portfolio size ({len(target_list)}) exceeds top_n (10).")

    # ── Determine output directory ──
    if output_dir is None:
        out_dir = ROOT / "reports" / "daily_signal"
    else:
        out_dir = output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── JSON ──
    signal_json = {
        "date": target_date,
        "generated_at": datetime.now().isoformat(),
        "time_context": "Based on close data of this date. Aligned with BacktestEngine behavior.",
        "baseline": "Candidate B (score_high=0.80, atr_bear=0.89, breakout_bear=40)",
        "regime": {
            "score": regime_score,
            "adapted_params": adapted,
        },
        "candidate_signals": candidate_list,
        "target_portfolio": target_list,
        "actions": actions_list,
        "exit_actions": exit_actions,
        "signals_empty": signals_empty,
        "alloc_zero_note": "Candidates exist but alloc=0 — no actual BUY orders" if (candidate_list and not target_list) else "",
        "warnings": warnings,
        "has_positions": has_positions,
        "breadth_ref_date": breadth_ref_date,
    }
    # Per-position price info (broker mode only)
    if broker is not None:
        pos_price_info = {}
        for sym, pos in broker.positions.items():
            has_price = sym in price_map and price_map.get(sym, 0) > 0
            pos_price_info[sym] = {
                "close": price_map.get(sym, 0),
                "price_date": target_date if has_price else "stale",
                "is_stale": not has_price,
                "stale_days": 0 if has_price else -1,
                "price_source": "current_close" if has_price else "last_close_or_missing",
            }
        signal_json["paper_positions_price_info"] = pos_price_info
    with open(out_dir / f"{target_date}_signal.json", "w") as f:
        json.dump(signal_json, f, indent=2, ensure_ascii=False, default=str)

    # ── Markdown report ──
    lines = [
        f"# Daily Signal Report — {target_date}",
        f"",
        f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Time context**: Based on {target_date} close data. Aligned with BacktestEngine.",
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

    empty_reason = ""
    if signals_empty:
        if regime_score is not None and regime_score <= 0.01:
            empty_reason = f"Regime score {regime_score:.3f} <= 0.01 — extreme bear, forced cash."
        elif regime_score is not None and regime_score < CANDIDATE_B_GENES["score_low"]:
            empty_reason = f"Regime score {regime_score:.3f} < score_low {CANDIDATE_B_GENES['score_low']} — bear regime, alloc=0."
        elif regime_score is not None:
            empty_reason = f"Regime score {regime_score:.3f} — no breakouts found among {len(market_data)} constituent stocks."
        else:
            empty_reason = "Regime score unavailable — possible data issue."

    if signals_empty:
        lines.append(f"- **Result**: EMPTY signals")
        lines.append(f"- **Reason**: {empty_reason}")
        if has_positions and not current_positions_for_comparison.empty:
            lines.append(f"- **Positions**: {len(current_positions_for_comparison)} held (engine would keep)")
    else:
        alloc = round(sum(t["target_weight"] for t in target_list) * 100, 1)
        lines.append(f"- **Allocation**: {alloc}% ({len(target_list)} actual targets)")

    lines += [f"", f"## Exit Check (Pre-Signal)", f""]
    if exit_actions:
        lines.append("| Symbol | Reason |")
        lines.append("|---|---|")
        for a in exit_actions:
            lines.append(f"| {a['symbol']} | {a['reason']} |")
    else:
        lines.append("*(no exits triggered)*")

    lines += [f"", f"## Candidate Signals", f""]
    if candidate_list:
        lines.append("| Symbol | Score | Reason |")
        lines.append("|---|---|---|")
        for c in candidate_list:
            lines.append(f"| {c['symbol']} | {c['score']:.4f} | {c['reason']} |")
    else:
        lines.append(f"*(no breakout candidates today)*")

    lines += [f"", f"## Target Portfolio", f""]
    if target_list:
        lines.append("| Symbol | Target Weight | Score | Reason |")
        lines.append("|---|---:|---:|------|")
        for t in target_list:
            lines.append(f"| {t['symbol']} | {t['target_weight']:.4f} | {t['score']:.4f} | {t['reason']} |")
    elif not signals_empty:
        lines.append(f"*(all candidates have weight=0)*")
    else:
        lines.append(f"*(empty — no signals)*")

    lines += [f"", f"## Actions", f""]
    if actions_list:
        lines.append("| Symbol | Action | Reason |")
        lines.append("|---|---|---|")
        for a in actions_list:
            lines.append(f"| {a.get('symbol','')} | **{a.get('action','')}** | {a.get('reason','')} |")
    else:
        lines.append(f"*(no actions — positions unchanged)*")

    lines += [f"", f"## Data Integrity", f""]
    if constituents_today:
        lines.append(f"- Constituents: {len(constituents_today)} symbols for {target_date}")
        lines.append(f"- DataContext: {len(ctx.breadth_series)} dates, ref {ctx.breadth_ref_date}" if ctx is not None else f"- Breadth ref: {breadth_ref_date}")
    lines.append(f"- Market data: {len(market_data)} bars for {target_date}")
    if warnings:
        for w in warnings:
            lines.append(f"- ⚠ {w}")
    else:
        lines.append(f"- ✓ No data integrity warnings")

    lines += [f"", f"## Risk Notes", f"",
              f"- Strategy: Candidate B (trend_breakout, no pullback, no rank_buffer)",
              f"- Max DD threshold: {CANDIDATE_B_GENES['strategy_max_dd']*100:.0f}%",
              f"- Exit check: ON (aligned with engine)",
              f"- Empty target: positions persist (aligned with engine)",
              f"- **This is a paper signal only. No orders submitted.**"]

    with open(out_dir / f"{target_date}_report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    logger.info(f"Signal report saved to {out_dir / f'{target_date}_report.md'}")

    if signals_empty:
        logger.info(f"Regime: empty signals (score={regime_score})")
    else:
        logger.info(f"Regime: score={regime_score}, {len(signals)} signals")
    for w in warnings:
        logger.warning(f"  {w}")

    # ── Build daily summary ──
    buy_count = len([a for a in actions_list if a.get("action") == "BUY"])
    sell_count = len([a for a in actions_list if a.get("action") == "SELL"])
    hold_count = len([a for a in actions_list if a.get("action") == "HOLD"])
    adjust_count = len([a for a in actions_list if a.get("action") == "ADJUST"])

    daily_summary = {
        "date": target_date,
        "regime_score": regime_score if regime_score is not None else "",
        "alloc_pct": round(sum(t["target_weight"] for t in target_list) * 100, 2),
        "candidate_count": len(candidate_list),
        "target_count": len(target_list),
        "buy_count": buy_count,
        "sell_count": sell_count,
        "hold_count": hold_count,
        "adjust_count": adjust_count,
        "skipped_count": skipped,
        "exit_count": len(exit_actions),
        "position_count": n_positions,
        "gross_exposure": gross_exposure,
        "symbols": ",".join(t["symbol"] for t in target_list),
        "warnings": "; ".join(warnings) if warnings else "",
        "signals_empty": signals_empty,
    }
    # Track PaperBroker fills in daily summary
    if broker is not None:
        daily_summary["broker_fills_count"] = len(broker_fills)
        daily_summary["broker_cash"] = round(broker.cash, 2)
        if price_map:
            daily_summary["broker_nav"] = round(broker.get_nav(price_map), 2)

    result = {
        "signal_json": signal_json,
        "daily_summary": daily_summary,
    }
    if broker is not None:
        result["broker"] = broker
    else:
        # Legacy weight-only
        td_close_map = {}
        if not market_data.empty:
            td_close_map = dict(zip(market_data["symbol"], market_data["close"]))
        for t in target_list:
            sym = t["symbol"]
            if sym not in entry_prices or entry_prices.get(sym, 0) <= 0:
                close_px = td_close_map.get(sym, 0)
                entry_prices[sym] = close_px
                entry_peaks[sym] = close_px
        next_positions, entry_prices, entry_peaks = build_next_positions(
            positions_data or [], target_list, target_date,
            entry_prices=entry_prices, entry_peaks=entry_peaks,
            signals_empty=signals_empty,
        )
        result["next_positions"] = next_positions
        result["entry_prices"] = entry_prices
        result["entry_peaks"] = entry_peaks

    return result


def run_replay(dates, initial_positions=None, output_dir=None):
    if initial_positions is None:
        initial_positions = []

    if output_dir is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = ROOT / "reports" / "paper_trading" / f"replay_{timestamp}"

    daily_dir = output_dir / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)

    # Breadth ref date = first date in period (matching engine ref_date = self.start_date)
    breadth_ref_date = dates[0]

    # ── Build unified DataContext (shared with BacktestEngine) ──
    from qts.backtest.data_context import build_strategy_context
    bar_path = str(ROOT / "data/raw/HS300_daily.parquet")
    calendar_path = str(ROOT / "data/raw/calendar.parquet")
    ctx = build_strategy_context(
        bar_path=bar_path,
        calendar_path=calendar_path,
        start_date=dates[0],
        end_date=dates[-1],
        use_constituent_filter=True,
    )

    logger.info(f"Replay output: {output_dir}")
    logger.info(f"Dates: {dates[0]} → {dates[-1]} ({len(dates)} days)")
    logger.info(f"DataContext: breadth_ref={ctx.breadth_ref_date}, {len(ctx.bars_by_date)} dates indexed")

    # ── Save replay config ──
    replay_config = {
        "mode": "paper trading replay (PaperBroker, DataContext-aligned, full execution sim)",
        "baseline": "Candidate B (score_high=0.80, atr_bear=0.89, breakout_bear=40)",
        "start_date": dates[0],
        "end_date": dates[-1],
        "n_days": len(dates),
        "genes": CANDIDATE_B_GENES,
        "generated_at": datetime.now().isoformat(),
        "time_context": "End-of-day close data replay, DataContext-aligned with BacktestEngine.",
        "weight_only_note": "Weight-only paper positions. Exit simulation via strategy.check_exit().",
        "breadth_ref_date": breadth_ref_date,
        "exit_check_enabled": True,
        "empty_signals_behavior": "positions persist (matching engine continue)",
        "data_context": "unified via qts.backtest.data_context.build_strategy_context()",
    }
    with open(output_dir / "replay_config.json", "w") as f:
        json.dump(replay_config, f, indent=2, ensure_ascii=False, default=str)

    # ── Initialize PaperBroker for full execution simulation ──
    broker = PaperBroker(
        initial_cash=1_000_000,
        commission_rate=0.00025,
        stamp_tax_rate=0.0005,
        min_commission=5.0,
        slippage_bps=10.0,
        lot_size=100,
    )
    # Load initial positions if provided
    if initial_positions:
        for p in initial_positions:
            sym = p["symbol"]
            qty = p.get("quantity", 0)
            if qty > 0:
                broker.positions[sym] = {
                    "quantity": qty,
                    "locked_quantity": p.get("locked_quantity", 0),
                    "avg_cost": p.get("avg_cost", 0.0),
                    "entry_price": p.get("entry_price", 0.0),
                    "entry_date": p.get("entry_date", ""),
                    "entry_peak": p.get("entry_peak", p.get("entry_price", 0.0)),
                }
                # Deduct from cash
                cost = qty * p.get("avg_cost", 0.0)
                broker.cash -= cost if cost > 0 else 0

    summary_list = []

    for i, d in enumerate(dates):
        n_positions = len(broker.positions)
        logger.info(f"[{i+1}/{len(dates)}] {d}  (positions: {n_positions}, cash: {broker.cash:,.0f})")

        result = generate(
            date_str=d,
            output_dir=daily_dir,
            ctx=ctx,
            broker=broker,
        )

        summary_list.append(result["daily_summary"])

        n_targets = result["daily_summary"]["target_count"]
        n_exits = result["daily_summary"]["exit_count"]
        n_actions = result["daily_summary"]["buy_count"] + result["daily_summary"]["sell_count"]
        if n_actions > 0 or n_exits > 0 or i == 0 or i == len(dates) - 1:
            logger.info(f"  → targets={n_targets}, exits={n_exits}, "
                        f"actions={n_actions}, alloc={result['daily_summary']['alloc_pct']}%")

    # ── Save final positions ──
    with open(output_dir / "final_positions.json", "w") as f:
        json.dump(broker.get_positions_as_dicts(), f, indent=2, ensure_ascii=False, default=str)

    # ── Save broker trades ──
    with open(output_dir / "broker_trades.json", "w") as f:
        json.dump(broker.trades, f, indent=2, ensure_ascii=False, default=str)

    # ── Save replay summary CSV ──
    csv_path = output_dir / "replay_summary.csv"
    if summary_list:
        fieldnames = [
            "date", "regime_score", "alloc_pct",
            "candidate_count", "target_count",
            "buy_count", "sell_count", "hold_count", "adjust_count",
            "exit_count", "skipped_count",
            "position_count", "gross_exposure", "symbols", "warnings",
            "signals_empty",
        ]
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(summary_list)

    # ── Save replay summary JSON ──
    summary_json = {
        "config": replay_config,
        "summary": summary_list,
        "final_positions": broker.get_positions_as_dicts(),
        "broker_trades_count": len(broker.trades),
        "final_cash": broker.cash,
        "aggregates": _compute_replay_aggregates(summary_list),
    }
    with open(output_dir / "replay_summary.json", "w") as f:
        json.dump(summary_json, f, indent=2, ensure_ascii=False, default=str)

    logger.info(f"\nReplay complete. {len(dates)} days processed.")
    logger.info(f"Output: {output_dir}")

    return {
        "config": replay_config,
        "summary_list": summary_list,
        "final_positions": broker.get_positions_as_dicts(),
        "broker": broker,
        "output_dir": output_dir,
    }


def _compute_replay_aggregates(summary_list):
    if not summary_list:
        return {}
    n_days = len(summary_list)
    days_with_positions = sum(1 for s in summary_list if s["position_count"] > 0)
    days_with_candidates = sum(1 for s in summary_list if s["candidate_count"] > 0)
    days_with_warnings = sum(1 for s in summary_list if s["warnings"])
    total_buys = sum(s["buy_count"] for s in summary_list)
    total_sells = sum(s["sell_count"] for s in summary_list)
    total_exits = sum(s.get("exit_count", 0) for s in summary_list)
    avg_alloc = sum(s["alloc_pct"] for s in summary_list) / n_days if n_days else 0
    regimes = [s["regime_score"] for s in summary_list if s["regime_score"] != ""]
    avg_regime = sum(regimes) / len(regimes) if regimes else 0
    max_alloc = max(s["alloc_pct"] for s in summary_list)
    return {
        "n_days": n_days,
        "days_with_positions": days_with_positions,
        "days_with_candidates": days_with_candidates,
        "days_with_warnings": days_with_warnings,
        "total_buys": total_buys,
        "total_sells": total_sells,
        "total_exits": total_exits,
        "total_turnover_events": total_buys + total_sells,
        "avg_alloc_pct": round(avg_alloc, 2),
        "avg_regime_score": round(avg_regime, 3),
        "max_alloc_pct": round(max_alloc, 2),
        "final_position_count": summary_list[-1]["position_count"] if summary_list else 0,
    }


# ═══════════════════════════════════════════════════════════════════════════
# Paper Trading Daily Mode — state persistence for production use
# ═══════════════════════════════════════════════════════════════════════════

PAPER_DIR = ROOT / "data" / "paper_trading"


def load_paper_state():
    """Load paper trading state from disk. Returns dict or None."""
    state_path = PAPER_DIR / "paper_state.json"
    if not state_path.exists():
        return None
    with open(state_path) as f:
        return json.load(f)


def save_paper_state(state):
    """Save paper trading state to disk."""
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    with open(PAPER_DIR / "paper_state.json", "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False, default=str)


def load_paper_positions():
    """Load paper positions JSON, return list of dicts."""
    pos_path = PAPER_DIR / "paper_positions.json"
    if not pos_path.exists():
        return []
    with open(pos_path) as f:
        return json.load(f)


def save_paper_positions(broker):
    """Save broker positions to paper_positions.json."""
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    with open(PAPER_DIR / "paper_positions.json", "w") as f:
        json.dump(broker.get_positions_as_dicts(), f, indent=2, ensure_ascii=False, default=str)


def append_paper_trades(broker, new_fills):
    """Append new fills to paper_trades.csv."""
    if not new_fills:
        return
    csv_path = PAPER_DIR / "paper_trades.csv"
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    fieldnames = ["date", "symbol", "side", "quantity", "price", "commission", "stamp_tax", "reason"]
    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        for fill in new_fills:
            row = {
                "date": str(fill.get("date", ""))[:10],
                "symbol": fill.get("symbol", ""),
                "side": fill.get("side", ""),
                "quantity": fill.get("quantity", 0),
                "price": fill.get("price", 0),
                "commission": fill.get("commission", 0),
                "stamp_tax": fill.get("stamp_tax", 0),
                "reason": fill.get("reason", ""),
            }
            writer.writerow(row)


def append_paper_nav(date_str, broker, price_map, stale_info=None):
    """Append NAV snapshot to paper_nav.csv with stale price tracking."""
    csv_path = PAPER_DIR / "paper_nav.csv"
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    total_value = broker.get_nav(price_map) if price_map else broker.cash
    pv = broker.get_position_value(price_map) if price_map else 0
    if stale_info is None:
        stale_info = {}
    stale_syms = [s for s, si in stale_info.items() if si.get("is_stale")]
    stale_count = len(stale_syms)
    stale_pv = sum(
        broker.positions.get(s, {}).get("quantity", 0) * stale_info[s].get("close", 0)
        for s in stale_syms
    )
    price_status = "OK" if stale_count == 0 else ("STALE" if stale_count < len(broker.positions) else "ALL_STALE")
    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "date", "total_value", "cash", "position_value", "n_positions",
                "stale_position_count", "stale_symbols", "stale_position_value", "price_status",
            ])
        writer.writerow([
            date_str, round(total_value, 2), round(broker.cash, 2),
            round(pv, 2), len(broker.positions),
            stale_count, ",".join(stale_syms), round(stale_pv, 2), price_status,
        ])


def run_paper_mode(target_date, force=False):
    """Execute a single day of paper trading.

    Flow:
      1. Load paper state and positions
      2. Safety checks (data freshness, duplicate date, OHLCV)
      3. Build DataContext
      4. Restore PaperBroker from saved state
      5. Run exit check → generate signals → rebalance
      6. Save state, positions, trades, NAV
      7. Write daily report

    Args:
        target_date: Date string YYYY-MM-DD.
        force: If True, allow re-running an already-processed date.
    """
    # ── Load state ──
    state = load_paper_state()
    positions_list = load_paper_positions()

    # ── Safety: check data freshness ──
    bar_path = ROOT / "data/raw/HS300_daily.parquet"
    if not bar_path.exists():
        logger.error("Market data not found: data/raw/HS300_daily.parquet")
        return None
    df_dates = pd.read_parquet(bar_path, columns=["trade_date"])
    max_data_date = str(df_dates["trade_date"].max())[:10]
    if target_date > max_data_date:
        logger.error(f"Target date {target_date} is after last market data {max_data_date}")
        return None

    # ── Safety: check calendar ──
    calendar = pd.read_parquet(ROOT / "data/raw/calendar.parquet")
    cal_dates = set(calendar[calendar["is_trading_day"] == True]["trade_date"].astype(str).str[:10])
    if target_date not in cal_dates:
        logger.warning(f"{target_date} is NOT a trading day. Proceeding anyway (paper-only).")

    # ── Safety: prevent duplicate execution ──
    if state and not force:
        last_date = state.get("last_date", "")
        if last_date >= target_date:
            logger.error(
                f"Date {target_date} already processed (last: {last_date}). "
                f"Use --force to re-run."
            )
            return None

    # ── Safety: data hash check ──
    import hashlib
    with open(bar_path, "rb") as f:
        data_hash = hashlib.md5(f.read()).hexdigest()
    if state and state.get("data_hash") and state["data_hash"] != data_hash:
        logger.warning(f"Data hash changed: {state['data_hash'][:8]}... → {data_hash[:8]}...")

    # ── Build DataContext ──
    calendar_path = str(ROOT / "data/raw/calendar.parquet")
    ctx = build_strategy_context(
        bar_path=str(bar_path),
        calendar_path=calendar_path,
        start_date=target_date,
        end_date=target_date,
        use_constituent_filter=True,
    )

    # ── Restore PaperBroker ──
    broker = PaperBroker(
        initial_cash=1_000_000,
        commission_rate=0.00025,
        stamp_tax_rate=0.0005,
        min_commission=5.0,
        slippage_bps=10.0,
        lot_size=100,
    )
    if state:
        broker.cash = state.get("cash", broker.initial_cash)
    for p in positions_list:
        sym = p["symbol"]
        qty = p.get("quantity", 0)
        if qty > 0:
            broker.positions[sym] = {
                "quantity": qty,
                "locked_quantity": p.get("locked_quantity", 0),
                "avg_cost": p.get("avg_cost", 0.0),
                "entry_price": p.get("entry_price", 0.0),
                "entry_date": p.get("entry_date", ""),
                "entry_peak": p.get("entry_peak", p.get("entry_price", 0.0)),
            }

    logger.info(f"Paper mode: {target_date}  positions={len(broker.positions)} cash={broker.cash:,.0f}")

    # ── Execute daily cycle ──
    out_dir = ROOT / "reports" / "daily_signal"
    result = generate(
        date_str=target_date,
        output_dir=out_dir,
        ctx=ctx,
        broker=broker,
    )

    # ── Get today's price map + stale tracking ──
    # Per-position: current_close, is_stale, stale_days, price_source
    price_map = {}
    stale_info = {}  # sym -> {price_date, stale_days, is_stale, price_source, close}
    today_bars = ctx.bars_by_date.get(target_date, pd.DataFrame())
    if not today_bars.empty:
        price_map = dict(zip(today_bars["symbol"], today_bars["close"]))

    for sym, pos in broker.positions.items():
        has_today = sym in price_map and price_map.get(sym, 0) > 0
        if has_today:
            stale_info[sym] = {
                "price_date": target_date, "stale_days": 0,
                "is_stale": False, "price_source": "current_close",
                "close": price_map[sym],
            }
        else:
            # Look back for last available close
            sym_bars = ctx.bars_by_symbol.get(sym, pd.DataFrame())
            if not sym_bars.empty:
                sym_bars_sorted = sym_bars.sort_values("trade_date")
                hist = sym_bars_sorted[sym_bars_sorted["trade_date"].astype(str).str[:10] <= target_date]
                if not hist.empty:
                    last_close = float(hist["close"].iloc[-1])
                    last_date = str(hist["trade_date"].iloc[-1])[:10]
                    price_map[sym] = last_close
                    s_days = (pd.Timestamp(target_date) - pd.Timestamp(last_date)).days
                    stale_info[sym] = {
                        "price_date": last_date, "stale_days": s_days,
                        "is_stale": True, "price_source": "last_close",
                        "close": last_close,
                    }
                    level = "ERROR" if s_days >= 3 else "WARNING"
                    logger.warning(
                        f"{sym}: STALE price (last={last_date}, {s_days}d ago, "
                        f"close={last_close}). {'DATA GAP — need re-pull.' if s_days >= 3 else ''}"
                    )
                    continue
            # Completely missing
            stale_info[sym] = {
                "price_date": None, "stale_days": -1,
                "is_stale": True, "price_source": "missing",
                "close": 0,
            }
            logger.error(f"{sym}: NO price history available. NAV incomplete.")

    # ── Collect new fills (broker rebuilt each day, trades are this session only) ──
    prev_trade_count = state.get("trade_count", 0) if state else 0
    new_fills = list(broker.trades)  # all fills from this session

    # ── Save state ──
    cumulative_trades = prev_trade_count + len(new_fills)
    new_state = {
        "last_date": target_date,
        "cash": broker.cash,
        "trade_count": cumulative_trades,
        "data_hash": data_hash,
        "max_data_date": max_data_date,
        "generated_at": datetime.now().isoformat(),
        "baseline": "Candidate B (score_high=0.80, atr_bear=0.89, breakout_bear=40)",
    }
    save_paper_state(new_state)
    save_paper_positions(broker)
    append_paper_trades(broker, new_fills)
    append_paper_nav(target_date, broker, price_map, stale_info)

    logger.info(f"Paper state saved: {len(new_fills)} new fills, {len(broker.positions)} positions")

    # ── Print summary ──
    print(f"\n{'='*60}")
    print(f"Paper Trading Report — {target_date}")
    print(f"{'='*60}")
    print(f"  Regime score:      {result['daily_summary']['regime_score']}")
    print(f"  Alloc %:           {result['daily_summary']['alloc_pct']}%")
    print(f"  Candidates:        {result['daily_summary']['candidate_count']}")
    print(f"  Targets:           {result['daily_summary']['target_count']}")
    print(f"  BUYs:              {result['daily_summary']['buy_count']}")
    print(f"  SELLs:             {result['daily_summary']['sell_count']}")
    print(f"  Exits:             {result['daily_summary']['exit_count']}")
    print(f"  New fills:         {len(new_fills)}")
    print(f"  Positions:         {len(broker.positions)}")
    print(f"  Cash:              {broker.cash:,.0f}")
    if price_map:
        print(f"  NAV:               {broker.get_nav(price_map):,.0f}")
    print(f"  Warnings:          {result['daily_summary']['warnings'] or 'none'}")
    # ── Stale price summary ──
    stale_count = sum(1 for si in stale_info.values() if si.get("is_stale"))
    if stale_count > 0:
        print(f"  Stale positions:   {stale_count}")
        for sym, si in stale_info.items():
            if si.get("is_stale"):
                marker = " ⚠ DATA GAP" if si.get("stale_days", 0) >= 3 else " (stale)"
                print(f"    {sym}: last={si.get('price_date')}, {si.get('stale_days')}d ago, close={si.get('close')}{marker}")
    print(f"  Data last:         {max_data_date}")
    print(f"  Time context:      EOD close signal, not real-time. No auto orders.")
    print(f"  State saved:       {PAPER_DIR}")
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="Target date YYYY-MM-DD")
    parser.add_argument("--positions", default=None, help="Path to positions.json")
    parser.add_argument("--replay-last-n", type=int, default=None,
                        help="Replay last N trading days with continuous position tracking")
    parser.add_argument("--output", default=None, help="Output directory for replay mode")
    parser.add_argument("--paper-mode", action="store_true",
                        help="Daily paper trading mode with state persistence")
    parser.add_argument("--force", action="store_true",
                        help="Force re-execution even if date already processed")
    args = parser.parse_args()

    if args.paper_mode:
        if not args.date:
            parser.error("--paper-mode requires --date YYYY-MM-DD")
        run_paper_mode(args.date, force=args.force)
        return

    if args.replay_last_n:
        calendar = pd.read_parquet(ROOT / "data/raw/calendar.parquet")
        cal_dates = sorted(calendar[calendar["is_trading_day"] == True]["trade_date"]
                          .astype(str).str[:10])

        if args.date:
            end_date = args.date
        else:
            df_dates = pd.read_parquet(ROOT / "data/raw/HS300_daily.parquet", columns=["trade_date"])
            max_data_date = df_dates["trade_date"].max()
            end_date = max_data_date[:10]
            logger.info(f"Auto end_date (from market data): {end_date}")

        cal_dates = [d for d in cal_dates if d <= end_date]
        dates = cal_dates[-args.replay_last_n:]

        if len(dates) < args.replay_last_n:
            logger.warning(f"Only {len(dates)} trading days available (requested {args.replay_last_n})")

        output_dir = Path(args.output) if args.output else None
        result = run_replay(dates, output_dir=output_dir)

        agg = _compute_replay_aggregates(result["summary_list"])
        print(f"\n{'='*60}")
        print(f"Replay Complete: {result['config']['start_date']} → {result['config']['end_date']}")
        print(f"{'='*60}")
        print(f"  Days:               {agg['n_days']}")
        print(f"  Days with positions:{agg['days_with_positions']}")
        print(f"  Days with warnings: {agg['days_with_warnings']}")
        print(f"  Avg alloc %:        {agg['avg_alloc_pct']}%")
        print(f"  Max alloc %:        {agg['max_alloc_pct']}%")
        print(f"  Avg regime score:   {agg['avg_regime_score']}")
        print(f"  Total BUY events:   {agg['total_buys']}")
        print(f"  Total SELL events:  {agg['total_sells']}")
        print(f"  Total EXIT events:  {agg['total_exits']}")
        print(f"  Final positions:    {agg['final_position_count']}")
        print(f"  Output:             {result['output_dir']}")
        print(f"  Breadth ref date:   {result['config'].get('breadth_ref_date', 'N/A')}")
        return

    # ── Single-date mode ──
    if not args.date:
        parser.error("Either --date or --replay-last-n is required.")

    output_dir = ROOT / "reports" / "daily_signal"
    result = generate(args.date, args.positions, output_dir=output_dir)
    return result


if __name__ == "__main__":
    main()

"""Paper-mode multi-day replay diagnosis.

Usage:
    python scripts/diagnose_paper_replay.py --days 30
    python scripts/diagnose_paper_replay.py --days 60
    python scripts/diagnose_paper_replay.py --days 120
"""
import sys, json
from pathlib import Path
from collections import defaultdict
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from datetime import datetime

from qts.backtest.data_context import build_strategy_context
from qts.backtest.paper_broker import PaperBroker
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.utils.logger import logger
from qts.utils.config import get_project_root

ROOT = get_project_root()

# Candidate B baseline parameters (same as generate_daily_signal.py)
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


def load_bars():
    df = pd.read_parquet(ROOT / "data/raw/HS300_daily.parquet")
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.strftime("%Y-%m-%d")
    return df


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, required=True, help="Number of trading days to replay")
    args = parser.parse_args()

    bars = load_bars()
    all_dates = sorted(bars["trade_date"].unique())

    # Start from latest available date, go back --days trading days
    end_date = all_dates[-1]
    end_idx = all_dates.index(end_date)
    start_idx = max(0, end_idx - args.days + 1)
    replay_dates = all_dates[start_idx:end_idx + 1]

    logger.info(f"Replay: {len(replay_dates)} trading days ({replay_dates[0]} → {replay_dates[-1]})")

    # Build context once (expensive, ~65s)
    logger.info("Building DataContext (one-time)...")
    ctx = build_strategy_context(
        bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
        calendar_path=str(ROOT / "data/raw/calendar.parquet"),
        start_date=replay_dates[0],
        end_date=replay_dates[-1],
        use_constituent_filter=True,
        constituent_json_path=str(ROOT / "data/historical_constituents.json"),
    )

    genes = CANDIDATE_B_GENES
    regime = RegimeEngine(
        w_breadth=genes["w_breadth"], w_trend=genes["w_trend"],
        w_stability=genes["w_stability"], w_volume=genes["w_volume"],
        score_low=genes["score_low"], score_high=genes["score_high"],
        breakout_bull=int(genes["breakout_bull"]), breakout_bear=int(genes["breakout_bear"]),
        atr_bull=genes["atr_bull"], atr_bear=genes["atr_bear"],
        vol_ratio_bull=genes["vol_ratio_bull"], vol_ratio_bear=genes["vol_ratio_bear"],
        top_n_bull=int(genes["top_n_bull"]), top_n_bear=int(genes["top_n_bear"]),
        support_bull=int(genes["support_bull"]), support_bear=int(genes["support_bear"]),
        ma_days_bull=int(genes["ma_bull"]), ma_days_bear=int(genes["ma_bear"]),
    )
    strategy = TrendBreakoutStrategy(
        breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
        max_loss_pct=genes["max_loss_pct"],
        min_breadth=0.50, breadth_half=0.30,
        atr_multiple=2.0, atr_period=int(genes["atr_period"]),
        profit_lock_pct=genes["profit_lock_pct"],
        top_n=10, max_weight_per_stock=genes["max_weight_per_stock"],
    )
    strategy.regime_engine = regime
    strategy.use_dow_filter = False
    strategy.breadth_ma_days = int(genes["breadth_ma_days"])
    strategy.strategy_max_dd = genes["strategy_max_dd"]
    strategy.enable_rank_buffer = False
    strategy.enable_pullback_entry = False
    strategy.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}
    ctx.apply_to_strategy(strategy)
    broker = PaperBroker(initial_cash=1_000_000)

    # ── Pre-compute expected universe counts per date (from constituent quarters) ──
    quarterly = ctx.constituent_quarterly
    quarters_sorted = sorted(quarterly.keys())
    expected_by_date = {}
    for d in replay_dates:
        past = [q for q in quarters_sorted if q <= d]
        qtr = past[-1] if past else quarters_sorted[0]
        expected_by_date[d] = len(set(quarterly[qtr]))

    # Stats
    daily_records = []
    all_fills = []
    holding_durations = defaultdict(list)
    skipped_dates = []
    low_coverage_dates = []

    for date in replay_dates:
        # ── Market data: MUST use filtered ctx.daily_market_data (same as production paper-mode).
        #     ctx.bars is unfiltered (all 2619 stocks) — using it would allow non-constituent
        #     stocks like 300488/301028 that the real paper-mode never sees.
        market_data_today = ctx.daily_market_data.get(date)
        if market_data_today is None or market_data_today.empty:
            logger.warning(f"No filtered market data for {date} — skipping")
            skipped_dates.append(date)
            continue

        price_map = dict(zip(market_data_today["symbol"], market_data_today["close"]))

        # ── Update peaks ──
        for sym in list(broker.positions.keys()):
            pos = broker.positions[sym]
            if sym in price_map and price_map[sym] > pos.get("entry_peak", 0):
                broker.positions[sym]["entry_peak"] = price_map[sym]

        # ── Exit check: ctx.bars (full history) needed for ATR calculation ──
        exit_fills = broker.check_and_execute_exits(strategy, date, ctx.bars, price_map)

        # ── Generate signals: filtered market_data matches production paper-mode ──
        current_positions_df = broker.get_all_positions()
        signals = strategy.generate_signals(
            current_date=date,
            market_data=market_data_today,
            factor_data=pd.DataFrame(),
            current_positions=current_positions_df,
        )

        # Build target, execute rebalance
        target_list = []
        if not signals.empty:
            for _, row in signals.iterrows():
                tw = round(float(row.get("target_weight", 0)), 4)
                if tw > 0:
                    target_list.append({
                        "symbol": row["symbol"],
                        "target_weight": tw,
                        "reason": str(row.get("reason", "")),
                    })
            rebalance_fills = broker.execute_weight_rebalance(target_list, price_map, date)
        else:
            rebalance_fills = []

        broker.end_of_day()

        # Record fills
        day_fills = exit_fills + rebalance_fills
        all_fills.extend(day_fills)

        # Daily stats
        nav = broker.get_nav(price_map)
        pos_count = len(broker.positions)
        pos_value = broker.get_position_value(price_map)

        # Stale check: position symbols NOT in today's filtered price data
        stale_syms = [sym for sym in broker.positions if sym not in price_map]
        stale_count = len(stale_syms)

        # Coverage check: actual market_data stocks vs expected constituents
        actual_count = len(market_data_today)
        expected_count = expected_by_date.get(date, actual_count)
        coverage_pct = actual_count / expected_count * 100 if expected_count > 0 else 100
        is_low_coverage = coverage_pct < 80
        if is_low_coverage:
            low_coverage_dates.append((date, actual_count, expected_count, coverage_pct))

        daily_records.append({
            "date": date,
            "nav": nav,
            "positions": pos_count,
            "position_value": pos_value,
            "cash": broker.cash,
            "stale_count": stale_count,
            "exit_count": len(exit_fills),
            "buy_count": sum(1 for f in day_fills if f["side"] == "BUY"),
            "sell_count": sum(1 for f in day_fills if f["side"] == "SELL"),
            "signal_count": len(target_list),
            "actual_count": actual_count,
            "expected_count": expected_count,
            "coverage_pct": coverage_pct,
        })

    # Compute holding durations
    entry_dates = {}
    for f in all_fills:
        if f["side"] == "BUY":
            entry_dates.setdefault(f["symbol"], []).append(f["date"])
        elif f["side"] == "SELL":
            sym = f["symbol"]
            if sym in entry_dates and entry_dates[sym]:
                buy_date = entry_dates[sym].pop(0)
                buy_idx = replay_dates.index(buy_date)
                sell_idx = replay_dates.index(f["date"])
                holding_days = sell_idx - buy_idx + 1
                holding_durations["all"].append(holding_days)
                if f.get("reason", "").startswith("atr_stop"):
                    holding_durations["atr_exit"].append(holding_days)
                elif f.get("reason", "") == "removed from target — rotation":
                    holding_durations["rotation"].append(holding_days)

    # ── Output ──
    df_daily = pd.DataFrame(daily_records)
    print(f"\n{'='*60}")
    print(f"PAPER-MODE REPLAY DIAGNOSIS — {args.days} trading days")
    print(f"  Range: {replay_dates[0]} → {replay_dates[-1]}")
    print(f"{'='*60}")

    total_days = len(replay_dates)
    processed_days = len(df_daily)
    skipped_days = len(skipped_dates)
    skipped_pct = skipped_days / total_days * 100 if total_days > 0 else 0

    print(f"\n--- Data Quality ---")
    print(f"  Total days:      {total_days}")
    print(f"  Processed:       {processed_days}")
    print(f"  Skipped:         {skipped_days} ({skipped_pct:.1f}%)  (no market_data at all)")
    if skipped_days > 0:
        print(f"  Skipped dates:   {skipped_dates}")

    low_cov_days = len(low_coverage_dates)
    low_cov_pct = low_cov_days / processed_days * 100 if processed_days > 0 else 0
    print(f"  Low coverage:    {low_cov_days} ({low_cov_pct:.1f}%)  (coverage < 80% of constituents)")
    if low_coverage_dates:
        print(f"  Low coverage dates (date | actual | expected | pct):")
        for d, actual, expected, pct in low_coverage_dates[:10]:
            print(f"    {d}: {actual}/{expected} ({pct:.0f}%)")
        if len(low_coverage_dates) > 10:
            print(f"    ... and {len(low_coverage_dates) - 10} more")

    if "coverage_pct" in df_daily.columns:
        min_cov = df_daily["coverage_pct"].min()
        avg_cov = df_daily["coverage_pct"].mean()
        print(f"  Min coverage:    {min_cov:.0f}%")
        print(f"  Avg coverage:    {avg_cov:.0f}%")
        if min_cov < 80:
            print(f"  ⚠ INSUFFICIENT COVERAGE — some days have < 80% of expected constituents.")
            print(f"    Missing stocks reduce candidate pool and may skew breadth computation.")
            print(f"    Replay results should NOT be used for strategy evaluation.")

    if skipped_pct > 10:
        print(f"  ⚠ INSUFFICIENT DATA — {skipped_pct:.0f}% of trading days have no filtered market data.")

    print(f"  Stale days:      {(df_daily['stale_count'] > 0).sum()} / {len(df_daily)}  (position-level price gaps)")
    print(f"  Max stale:       {df_daily['stale_count'].max()}")
    stale_rows = df_daily[df_daily["stale_count"] > 0]
    if len(stale_rows) > 0:
        print(f"  Stale dates:     {stale_rows['date'].tolist()}")
    print(f"  ALL_STALE free:  {'YES' if df_daily['stale_count'].max() == 0 else 'NO'}")

    print(f"\n--- Trading Activity ---")
    print(f"  Total BUYs:      {sum(1 for f in all_fills if f['side'] == 'BUY')}")
    print(f"  Total SELLs:     {sum(1 for f in all_fills if f['side'] == 'SELL')}")
    print(f"  Total exits:     {df_daily['exit_count'].sum()}")

    atr_exits = sum(1 for f in all_fills if f["side"] == "SELL" and f.get("reason", "").startswith("atr_"))
    profit_exits = sum(1 for f in all_fills if f["side"] == "SELL" and "profit_lock" in f.get("reason", ""))
    rotation_exits = sum(1 for f in all_fills if f["side"] == "SELL" and "rotation" in f.get("reason", ""))
    print(f"    ATR stop:      {atr_exits}")
    print(f"    Profit lock:   {profit_exits}")
    print(f"    Rotation:      {rotation_exits}")

    print(f"\n--- Holding Duration ---")
    all_holds = holding_durations.get("all", [])
    if all_holds:
        print(f"  Total trades:    {len(all_holds)}")
        print(f"  Avg holding:     {np.mean(all_holds):.1f} days")
        print(f"  Median holding:  {np.median(all_holds):.1f} days")
        print(f"  Min/Max:         {min(all_holds)}/{max(all_holds)} days")
        one_day = sum(1 for d in all_holds if d == 1)
        print(f"  1-day trades:    {one_day} ({one_day/len(all_holds)*100:.1f}%)")
        short_trades = sum(1 for d in all_holds if d <= 3)
        print(f"  ≤3-day trades:   {short_trades} ({short_trades/len(all_holds)*100:.1f}%)")
    else:
        print("  (no completed round-trips)")

    print(f"\n--- NAV ---")
    print(f"  Start NAV:       {df_daily['nav'].iloc[0]:,.0f}")
    print(f"  End NAV:         {df_daily['nav'].iloc[-1]:,.0f}")
    print(f"  Δ NAV:           {df_daily['nav'].iloc[-1] - df_daily['nav'].iloc[0]:,.0f}")
    peak = df_daily["nav"].max()
    dd = (df_daily["nav"] - peak) / peak
    print(f"  Max DD:          {dd.min()*100:.2f}%")
    avg_exp = (df_daily["position_value"] / df_daily["nav"]).mean() * 100
    print(f"  Avg exposure:    {avg_exp:.1f}%")

    print(f"\n--- Final State ---")
    print(f"  Positions:       {len(broker.positions)}")
    for sym, pos in broker.positions.items():
        print(f"    {sym}: qty={pos['quantity']}, entry={pos.get('entry_price',0):.2f}")
    print(f"  Cash:            {broker.cash:,.0f}")

    # Reliability — 3 tiers
    print(f"\n--- Reliability ---")
    if skipped_days > 0 or skipped_pct > 10:
        tier = "NOT RELIABLE"
        reason = f"{skipped_days}/{total_days} days skipped — insufficient data for strategy evaluation."
    elif low_cov_days > 0:
        tier = "PARTIALLY RELIABLE"
        reason = (f"{low_cov_days}/{processed_days} days have <80% constituent coverage. "
                  f"Min coverage: {df_daily['coverage_pct'].min():.0f}%. "
                  f"Results may be skewed by reduced candidate pool.")
    else:
        tier = "FULLY RELIABLE"
        reason = f"All {total_days} days processed with full constituent coverage."
    print(f"  Tier:            {tier}")
    print(f"  {reason}")

    # Flag: excessive short holding
    if all_holds and len(all_holds) >= 5:
        one_day_pct = sum(1 for d in all_holds if d == 1) / len(all_holds) * 100
        if one_day_pct > 40:
            print(f"\n  ⚠ HIGH 1-day holding ratio ({one_day_pct:.0f}%) — may indicate excessive churn")


if __name__ == "__main__":
    main()

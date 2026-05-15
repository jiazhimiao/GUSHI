"""Unified data preparation context shared by BacktestEngine and paper trading replay.

Ensures identical pivot/cache/breadth computation regardless of caller.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
import pandas as pd
import numpy as np
from qts.utils.logger import logger


class DataContext:
    """Pre-computed data caches for strategy signal generation.

    All pivots, breadth, and pre-indexed caches are computed once at construction
    and shared across all consumers. This guarantees identical regime scores,
    breakout detection, and signal generation between BacktestEngine and replay.
    """

    def __init__(
        self,
        bars: pd.DataFrame,
        calendar: pd.DataFrame,
        prices: pd.DataFrame,
        volumes: pd.DataFrame,
        highs: pd.DataFrame,
        opens: pd.DataFrame,
        lows: pd.DataFrame,
        breadth_series: pd.Series,
        bars_by_date: dict,
        bars_by_symbol: dict,
        regime_raw_cache: dict | None,
        daily_market_data: dict,
        daily_allowed_symbols: dict,
        constituent_quarterly: dict,
        start_date: str,
        end_date: str,
        use_constituent_filter: bool,
        breadth_ref_date: str,
    ):
        self.bars = bars
        self.calendar = calendar
        self.prices = prices
        self.volumes = volumes
        self.highs = highs
        self.opens = opens
        self.lows = lows
        self.breadth_series = breadth_series
        self.bars_by_date = bars_by_date
        self.bars_by_symbol = bars_by_symbol
        self.regime_raw_cache = regime_raw_cache
        self.daily_market_data = daily_market_data
        self.daily_allowed_symbols = daily_allowed_symbols
        self.constituent_quarterly = constituent_quarterly
        self.start_date = start_date
        self.end_date = end_date
        self.use_constituent_filter = use_constituent_filter
        self.breadth_ref_date = breadth_ref_date

    def apply_to_strategy(self, strategy):
        """Set all strategy-level caches from this context (matching engine _prepare_data)."""
        if hasattr(strategy, '_breadth_cache'):
            strategy._breadth_cache = self.breadth_series
            strategy._prices_pivot = self.prices
            strategy._volumes_pivot = self.volumes
            strategy._highs_pivot = self.highs
            strategy._opens_pivot = self.opens
            strategy._lows_pivot = self.lows
            strategy._bars_by_symbol = self.bars_by_symbol
        if hasattr(strategy, '_regime_raw_cache'):
            strategy._regime_raw_cache = self.regime_raw_cache


def build_strategy_context(
    bar_path: str,
    calendar_path: str,
    start_date: str,
    end_date: str,
    use_constituent_filter: bool = True,
    constituent_json_path: Optional[str] = None,
) -> DataContext:
    """Build unified DataContext from raw data files.

    Args:
        bar_path: Path to Parquet daily bars file.
        calendar_path: Path to Parquet calendar file.
        start_date: Backtest/replay start date (YYYY-MM-DD).
        end_date: Backtest/replay end date (YYYY-MM-DD).
        use_constituent_filter: If True, filter by historical index constituents.
        constituent_json_path: Override path to historical_constituents.json.

    Returns:
        DataContext with all pre-computed caches.
    """
    from qts.backtest.engine import load_bars

    # ── Load bars ──
    bars = load_bars(bar_path, "2018-01-01", end_date)
    calendar = pd.read_parquet(calendar_path)

    # ── Load constituents ──
    constituent_quarterly: dict = {}
    if use_constituent_filter:
        if constituent_json_path is None:
            const_path = Path(bar_path).parent.parent / "historical_constituents.json"
        else:
            const_path = Path(constituent_json_path)
        if const_path.exists():
            with open(const_path) as f:
                const_data = json.load(f)
            index_name = Path(bar_path).stem.replace("_daily", "")
            index_entry = const_data.get("indices", {}).get(index_name)
            if index_entry:
                constituent_quarterly = index_entry.get("quarterly", {})
                sorted_dates = sorted(constituent_quarterly.keys())
                logger.info(
                    f"DataContext: loaded constituents {index_name} "
                    f"({len(sorted_dates)} quarters, {sorted_dates[0]} ~ {sorted_dates[-1]})"
                )
            else:
                logger.warning(f"DataContext: no constituent data for {index_name}")
    breadth_ref_date = start_date

    # ── Pivot matrices ──
    prices = bars.pivot(index="trade_date", columns="symbol", values="close")
    volumes = bars.pivot(index="trade_date", columns="symbol", values="volume")
    highs = bars.pivot(index="trade_date", columns="symbol", values="high")
    opens = bars.pivot(index="trade_date", columns="symbol", values="open")
    lows = bars.pivot(index="trade_date", columns="symbol", values="low")
    logger.info(f"DataContext: price matrix {prices.shape}")

    # ── Breadth computation (matching engine logic exactly) ──
    breadth_symbols = None
    if use_constituent_filter and constituent_quarterly:
        sorted_cd = sorted(constituent_quarterly.keys())
        for q_date in reversed(sorted_cd):
            if q_date <= breadth_ref_date:
                breadth_symbols = constituent_quarterly[q_date]
                break
    if breadth_symbols:
        b_cols = [c for c in breadth_symbols if c in prices.columns]
        prices_b = prices[b_cols]
        volumes_b = volumes[b_cols]
    else:
        prices_b = prices
        volumes_b = volumes

    bma = 35  # Candidate B: breadth_ma_days=35
    ma_breadth = prices_b.rolling(bma).mean()
    breadth_series = (prices_b > ma_breadth).mean(axis=1)

    # ── Regime raw cache ──
    regime_raw_cache = None
    try:
        rets_20 = prices_b.pct_change(20, fill_method=None)
        trend_series = (rets_20.median(axis=1) / 0.05).clip(0, 1)

        rets_daily = prices_b.pct_change(fill_method=None)
        vol_20 = rets_daily.rolling(20).std().median(axis=1)
        vol_60 = rets_daily.rolling(60).std().median(axis=1)
        stability_series = (1.0 - ((vol_20 / vol_60.replace(0, np.nan)) - 0.5).clip(0, 1)).fillna(0.5)

        vol_mean_20 = volumes_b.rolling(20).mean().median(axis=1)
        vol_mean_60 = volumes_b.rolling(60).mean().median(axis=1)
        volume_series = (((vol_mean_20 / vol_mean_60.replace(0, np.nan)) - 0.7) / 0.6).clip(0, 1).fillna(0.5)

        regime_raw_cache = {
            "trend": trend_series,
            "stability": stability_series,
            "volume": volume_series,
        }
    except Exception:
        pass

    # ── Bars by date (P0 optimization) ──
    bars_by_date = {}
    for td, grp in bars.groupby("trade_date", sort=False):
        bars_by_date[str(td)[:10]] = grp

    # ── Bars by symbol ──
    bars_by_symbol = {
        sym: group.sort_values("trade_date")
        for sym, group in bars.groupby("symbol")
    }

    # ── Pre-compute daily market data (constituent-filtered) ──
    daily_market_data = {}
    daily_allowed_symbols = {}

    if constituent_quarterly:
        sorted_cd = sorted(constituent_quarterly.keys())

    for date_str in bars_by_date:
        td_bars = bars_by_date[date_str]
        if use_constituent_filter and constituent_quarterly:
            # Find nearest prior quarterly snapshot
            allowed = None
            for q_date in reversed(sorted_cd):
                if q_date <= date_str:
                    allowed = constituent_quarterly[q_date]
                    break
            if allowed is None:
                allowed = constituent_quarterly[sorted_cd[0]]
            allowed = [s for s in allowed if s in td_bars["symbol"].unique()]
            daily_allowed_symbols[date_str] = allowed
            daily_market_data[date_str] = td_bars[td_bars["symbol"].isin(allowed)]
        else:
            daily_market_data[date_str] = td_bars

    logger.info(f"DataContext: {len(bars_by_date)} dates indexed, breadth ref={breadth_ref_date}")
    logger.info(f"DataContext: breadth={len(b_cols)} symbols, regime cache={'yes' if regime_raw_cache else 'no'}")

    return DataContext(
        bars=bars,
        calendar=calendar,
        prices=prices,
        volumes=volumes,
        highs=highs,
        opens=opens,
        lows=lows,
        breadth_series=breadth_series,
        bars_by_date=bars_by_date,
        bars_by_symbol=bars_by_symbol,
        regime_raw_cache=regime_raw_cache,
        daily_market_data=daily_market_data,
        daily_allowed_symbols=daily_allowed_symbols,
        constituent_quarterly=constituent_quarterly,
        start_date=start_date,
        end_date=end_date,
        use_constituent_filter=use_constituent_filter,
        breadth_ref_date=breadth_ref_date,
    )

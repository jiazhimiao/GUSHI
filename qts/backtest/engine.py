"""Backtest engine: the main event loop.

Orchestrates:
1. Load data & calendar
2. On each rebalance date: generate signals -> target portfolio -> orders -> execute
3. Daily mark-to-market
4. Track NAV, positions, trades
"""
import json
from pathlib import Path

import pandas as pd
import numpy as np

from qts.utils.logger import logger
from qts.utils.time import generate_rebalance_dates
from qts.factors.factor_engine import FactorEngine
from qts.factors.momentum import momentum_factor, turnover_factor
from qts.factors.volatility import volatility_factor
from qts.strategies.base import Strategy
from qts.strategies.portfolio import PortfolioConstructor
from qts.backtest.broker_sim import BrokerSimulator
from qts.data.storage import load_bars, load_bars_pivot


class BacktestEngine:
    """Main backtest engine."""

    def __init__(
        self,
        bar_path: str,
        calendar_path: str,
        start_date: str,
        end_date: str,
        initial_cash: float = 1_000_000,
        commission_rate: float = 0.00025,
        stamp_tax_rate: float = 0.0005,
        min_commission: float = 5.0,
        slippage_bps: float = 10.0,
        lot_size: int = 100,
        execution_price: str = "intraday_close",  # "close", "next_open", "intraday_close"
        intraday_spread_bps: float = 15.0,  # extra spread for intraday_close mode
    ):
        self.bar_path = bar_path
        self.calendar_path = calendar_path
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash
        self.execution_price = execution_price
        self.intraday_spread_bps = intraday_spread_bps

        # intraday_close: add extra spread to simulate 2:30→close price drift
        total_slippage = slippage_bps
        if execution_price == "intraday_close":
            total_slippage += intraday_spread_bps

        self.broker = BrokerSimulator(
            initial_cash=initial_cash,
            commission_rate=commission_rate,
            stamp_tax_rate=stamp_tax_rate,
            min_commission=min_commission,
            slippage_bps=total_slippage,
            lot_size=lot_size,
        )

        # Load data
        self.bars = load_bars(bar_path, start_date, end_date)
        self.calendar = pd.read_parquet(calendar_path)

        # Factor engine
        self.factor_engine = FactorEngine()

        # Results containers
        self.nav_history: list[dict] = []
        self.trades: list[dict] = []
        self.position_history: list[dict] = []

    def run(
        self,
        strategy: Strategy,
        rebalance_freq: str = "weekly",
        min_turnover: float = 0.0,
        factor_names: list[str] | None = None,
    ):
        """Run the backtest.

        Args:
            strategy: Strategy instance (any Strategy subclass).
            rebalance_freq: 'daily', 'weekly', or 'monthly'.
            min_turnover: Minimum portfolio turnover (0-1) to trigger rebalance.
            factor_names: List of factor names used by the strategy (for MomentumValueStrategy).
        """
        logger.info(f"Running backtest [{strategy.name}]: {self.start_date} to {self.end_date}")
        logger.info(f"Initial cash: {self.initial_cash:,.0f}, execution: {self.execution_price}")
        self._strategy_ref = strategy  # for _update_entry_peaks
        strategy_peak = self.initial_cash  # track strategy-level peak for circuit breaker

        # Pre-compute factors (always done; unused strategies just ignore factor_data)
        prices = load_bars_pivot(self.bar_path, "close", self.start_date, self.end_date)
        volumes = load_bars_pivot(self.bar_path, "volume", self.start_date, self.end_date)
        logger.info(f"Price matrix: {prices.shape}")

        self.factor_engine.register("momentum_20d", momentum_factor, {"period": 20})
        self.factor_engine.register("volatility_60d", volatility_factor, {"period": 60})
        self.factor_engine.register("turnover_ratio", turnover_factor, {"period": 20}, depends_on="volume")
        factor_long = self.factor_engine.compute_as_long(prices, volumes)
        logger.info(f"Factor data: {factor_long.shape}")

        # Pre-compute market breadth (vectorized, for TrendBreakoutStrategy)
        bma = getattr(strategy, 'breadth_ma_days', 30)
        ma_breadth = prices.rolling(bma).mean()
        breadth_series = (prices > ma_breadth).mean(axis=1)  # % of stocks above N-day MA per date
        if hasattr(strategy, '_breadth_cache'):
            strategy._breadth_cache = breadth_series
            # Pre-index bars by symbol for fast lookup
            strategy._bars_by_symbol = {
                sym: group.sort_values("trade_date")
                for sym, group in self.bars.groupby("symbol")
            }
            logger.info(f"Breadth + bars cache ready")

        # Generate rebalance dates
        rebalance_dates = generate_rebalance_dates(
            self.start_date, self.end_date, self.calendar, rebalance_freq
        )
        rebalance_set = set(rebalance_dates)
        logger.info(f"Rebalance dates: {len(rebalance_dates)}")

        # Get all trading days in range
        cal_dates = self.calendar[
            (self.calendar["trade_date"] >= self.start_date)
            & (self.calendar["trade_date"] <= self.end_date)
        ]["trade_date"].tolist()

        # Track entry peaks for trailing stop (per strategy instance)
        entry_peaks: dict[str, float] = {}

        # For next_open execution: store pending target from previous day
        pending_target: pd.DataFrame | None = None
        pending_date: str = ""

        # Main loop
        for i, date in enumerate(cal_dates):
            # ── next_open mode: execute yesterday's orders at today's open ──
            if self.execution_price == "next_open" and pending_target is not None:
                logger.info(f"--- Execute {pending_date} orders at {date} open ---")
                self._execute_rebalance(pending_target, date, use_open=True)
                self._update_entry_peaks(date, entry_peaks)
                pending_target = None
                pending_date = ""

            # Daily mark-to-market (at close)
            self._mark_to_market(date)

            # Update strategy-level rolling DD (from 60-day peak, for circuit breaker)
            if hasattr(strategy, '_strategy_peak') and len(self.nav_history) > 0:
                current_nav = self.nav_history[-1]["total_value"]
                # Rolling peak: look back 60 trading days
                lookback = min(60, len(self.nav_history))
                rolling_peak = max(h["total_value"] for h in self.nav_history[-lookback:])
                if rolling_peak > 0:
                    strategy._strategy_dd = (current_nav - rolling_peak) / rolling_peak
                strategy._strategy_peak = rolling_peak

            # ── Daily: check exits (uses close price → realistic) ──
            self._check_and_execute_exits(strategy, date, entry_peaks)

            # Check if rebalance day
            if date not in rebalance_set:
                self.broker.end_of_day()
                continue

            # Generate signals (using today's close data, as you would after market close)
            signals = strategy.generate_signals(
                current_date=date,
                market_data=self.bars,
                factor_data=factor_long,
                current_positions=self.broker.get_all_positions(),
            )

            if signals.empty:
                self.broker.end_of_day()
                continue

            # Build target portfolio
            if strategy.skip_portfolio_construction:
                target = signals
            else:
                pc = PortfolioConstructor(**strategy.portfolio_config)
                target = pc.build_target_portfolio(signals)

            if target.empty:
                self.broker.end_of_day()
                continue

            # Check turnover threshold
            if min_turnover > 0:
                required_turnover = self._compute_turnover(target, date)
                if required_turnover < min_turnover:
                    self.broker.end_of_day()
                    continue

            if self.execution_price == "next_open":
                # Store target, execute at next trading day's open
                pending_target = target
                pending_date = date
                logger.info(
                    f"--- Signal {date} (turnover {self._compute_turnover(target, date):.1%}%) → 明早开盘执行 ---"
                )
            else:
                # close / intraday_close: execute at today's close (≈14:30判断→尾盘成交)
                logger.info(f"--- Rebalance {date} ---")
                self._execute_rebalance(target, date)
                self._update_entry_peaks(date, entry_peaks)

            # End of day processing
            self.broker.end_of_day()

        # Final mark-to-market
        final_date = cal_dates[-1] if cal_dates else self.end_date
        self._mark_to_market(final_date)

        logger.info("Backtest complete")
        return self.get_results()

    def _check_and_execute_exits(
        self, strategy: Strategy, date: str, entry_peaks: dict[str, float]
    ):
        """Check existing positions for exit signals and liquidate."""
        positions = self.broker.get_all_positions()
        if positions.empty:
            return

        latest_bars = self.bars[self.bars["trade_date"] == date]
        if latest_bars.empty:
            return
        price_map = dict(zip(latest_bars["symbol"], latest_bars["close"]))
        limit_down_map = dict(zip(latest_bars["symbol"], latest_bars["limit_down"]))

        for _, pos in positions.iterrows():
            sym = pos["symbol"]
            peak = entry_peaks.get(sym, 0.0)

            # Update peak
            if sym in price_map and price_map[sym] > peak:
                entry_peaks[sym] = price_map[sym]

            # Get entry price from strategy cache or position avg_cost
            entry_price = 0.0
            if hasattr(strategy, '_entry_prices'):
                entry_price = strategy._entry_prices.get(sym, 0.0)
            if entry_price <= 0:
                entry_price = pos.get("avg_cost", 0.0)

            should_exit, reason = strategy.check_exit(
                sym, date, self.bars, peak or price_map.get(sym, 0), entry_price
            )
            if should_exit:
                qty = pos["quantity"]
                if sym in price_map:
                    fill = self.broker.place_sell_order(
                        sym, qty, price_map[sym], limit_down_map.get(sym, 0.01), date
                    )
                    if fill:
                        fill["reason"] = reason
                        self.trades.append(fill)
                        logger.info(f"[{date}] 卖出 {sym} ({reason})")
                        entry_peaks.pop(sym, None)
                        if hasattr(strategy, '_entry_prices'):
                            strategy._entry_prices.pop(sym, None)

    def _update_entry_peaks(self, date: str, entry_peaks: dict[str, float]):
        """Update entry_peaks and strategy._entry_prices for new positions."""
        latest_bars = self.bars[self.bars["trade_date"] == date]
        if latest_bars.empty:
            return
        positions = self.broker.get_all_positions()
        for _, pos in positions.iterrows():
            sym = pos["symbol"]
            if sym not in entry_peaks:
                bar = latest_bars[latest_bars["symbol"] == sym]
                if not bar.empty:
                    # Use open or close depending on execution mode
                    price = bar.iloc[0]["open"] if self.execution_price == "next_open" else bar.iloc[0]["close"]
                    entry_peaks[sym] = price
                    if hasattr(self, '_strategy_ref'):
                        self._strategy_ref._entry_prices[sym] = price

    def _compute_turnover(self, target: pd.DataFrame, date: str) -> float:
        """Compute one-sided turnover needed to go from current to target portfolio.

        Returns a value in [0, 1] where 0.30 means 30% of portfolio needs to change.
        """
        latest_bars = self.bars[self.bars["trade_date"] == date]
        if latest_bars.empty:
            return 1.0

        price_map = dict(zip(latest_bars["symbol"], latest_bars["close"]))
        total_value = self.broker.get_total_value(price_map)
        if total_value <= 0:
            return 1.0

        current_positions = self.broker.get_all_positions()
        current_weights: dict[str, float] = {}
        for _, pos in current_positions.iterrows():
            sym = pos["symbol"]
            if sym in price_map:
                current_weights[sym] = pos["quantity"] * price_map[sym] / total_value

        target_weights = dict(zip(target["symbol"], target["target_weight"]))

        # One-sided turnover: sum of weight reductions (or increases) / 2
        all_symbols = set(current_weights.keys()) | set(target_weights.keys())
        turnover = 0.0
        for sym in all_symbols:
            cw = current_weights.get(sym, 0.0)
            tw = target_weights.get(sym, 0.0)
            turnover += abs(tw - cw)

        return turnover / 2.0

    def _execute_rebalance(self, target: pd.DataFrame, date: str, use_open: bool = False):
        """Generate orders from target portfolio and execute via broker.

        Args:
            use_open: If True, use today's open price (next_open mode).
                      If False, use today's close price (close mode).
        """
        latest_bars = self.bars[self.bars["trade_date"] == date]

        # Get execution prices
        price_map = {}
        limit_up_map = {}
        limit_down_map = {}
        price_col = "open" if use_open else "close"
        for _, bar in latest_bars.iterrows():
            sym = bar["symbol"]
            price_map[sym] = bar[price_col]
            limit_up_map[sym] = bar["limit_up"]
            limit_down_map[sym] = bar["limit_down"]

        current_positions = self.broker.get_all_positions()
        current_symbols = set(current_positions["symbol"].tolist()) if len(current_positions) > 0 else set()
        target_symbols = set(target["symbol"].tolist())
        target_weight_map = dict(zip(target["symbol"], target["target_weight"]))

        total_value = self.broker.get_total_value(price_map)

        # Sell: stocks in current but not in target
        for sym in current_symbols - target_symbols:
            pos = current_positions[current_positions["symbol"] == sym]
            if len(pos) == 0:
                continue
            qty = pos.iloc[0]["quantity"]
            if sym in price_map:
                fill = self.broker.place_sell_order(
                    sym, qty, price_map[sym], limit_down_map.get(sym, 0.01), date
                )
                if fill:
                    self.trades.append(fill)

        # Adjust: stocks in both
        for sym in current_symbols & target_symbols:
            if sym not in price_map:
                continue
            pos = current_positions[current_positions["symbol"] == sym].iloc[0]
            current_qty = pos["quantity"]
            current_value = current_qty * price_map[sym]
            target_value = total_value * target_weight_map.get(sym, 0)
            diff = target_value - current_value

            if diff < -1000:  # sell excess (threshold to avoid tiny trades)
                sell_qty = min(int(abs(diff) / price_map[sym]), current_qty)
                fill = self.broker.place_sell_order(
                    sym, sell_qty, price_map[sym], limit_down_map.get(sym, 0.01), date
                )
                if fill:
                    self.trades.append(fill)
            elif diff > 1000:  # buy more
                fill = self.broker.place_buy_order(
                    sym, min(diff, self.broker.cash * 0.5),
                    price_map[sym], limit_up_map.get(sym, 9999), date,
                )
                if fill:
                    self.trades.append(fill)

        # Buy: stocks in target but not in current
        for sym in target_symbols - current_symbols:
            if sym not in price_map:
                continue
            target_value = total_value * target_weight_map.get(sym, 0)
            fill = self.broker.place_buy_order(
                sym, target_value, price_map[sym], limit_up_map.get(sym, 9999), date
            )
            if fill:
                self.trades.append(fill)

    def _mark_to_market(self, date: str):
        """Record NAV and positions at current date."""
        latest_bars = self.bars[self.bars["trade_date"] == date]
        if latest_bars.empty:
            return

        price_map = dict(zip(latest_bars["symbol"], latest_bars["close"]))
        total_value = self.broker.get_total_value(price_map)
        positions = self.broker.get_all_positions()

        n_stocks = len(positions)
        position_value = total_value - self.broker.cash

        self.nav_history.append({
            "date": date,
            "total_value": total_value,
            "cash": self.broker.cash,
            "position_value": position_value,
            "n_positions": n_stocks,
        })

        for _, pos in positions.iterrows():
            sym = pos["symbol"]
            if sym in price_map:
                self.position_history.append({
                    "date": date,
                    "symbol": sym,
                    "quantity": pos["quantity"],
                    "price": price_map[sym],
                    "market_value": pos["quantity"] * price_map[sym],
                    "weight": pos["quantity"] * price_map[sym] / total_value if total_value > 0 else 0,
                })

    def get_results(self) -> dict:
        """Return backtest results as a dict of DataFrames."""
        return {
            "nav": pd.DataFrame(self.nav_history),
            "trades": pd.DataFrame(self.trades),
            "positions": pd.DataFrame(self.position_history),
        }

"""Paper trading broker — mirrors BrokerSimulator behavior for paper trading replay.

Supports:
- Quantity/lot_size simulation
- T+1 locked shares
- Commission/stamp tax (paper — no real order)
- Entry price / peak tracking for exit simulation
- Weight-based target portfolio execution

Differs from BrokerSimulator in that slippage and price limits are paper-only
(no real execution). All fills use close price for simplicity.
"""
from __future__ import annotations
import pandas as pd
import numpy as np


class PaperBroker:
    """Paper trading broker — simulates fills without real orders."""

    def __init__(
        self,
        initial_cash: float = 1_000_000,
        commission_rate: float = 0.00025,
        stamp_tax_rate: float = 0.0005,
        min_commission: float = 5.0,
        slippage_bps: float = 10.0,
        lot_size: int = 100,
    ):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.commission_rate = commission_rate
        self.stamp_tax_rate = stamp_tax_rate
        self.min_commission = min_commission
        self.slippage_bps = slippage_bps
        self.lot_size = lot_size

        # Position tracking: symbol -> {quantity, locked_quantity, avg_cost,
        #                                entry_price, entry_date, entry_peak}
        self.positions: dict[str, dict] = {}
        self._today_buys: dict[str, int] = {}

        # Trade log
        self.trades: list[dict] = []

    # ── Value ──────────────────────────────────────────────────────────

    def get_total_value(self, price_map: dict[str, float]) -> float:
        """Total account value (cash + position market value)."""
        pv = 0.0
        for sym, pos in self.positions.items():
            px = price_map.get(sym, 0)
            pv += pos["quantity"] * px
        return self.cash + pv

    def get_position_value(self, price_map: dict[str, float]) -> float:
        """Total position market value only."""
        pv = 0.0
        for sym, pos in self.positions.items():
            px = price_map.get(sym, 0)
            pv += pos["quantity"] * px
        return pv

    # ── Interface matching BrokerSimulator ─────────────────────────────

    def get_available_quantity(self, symbol: str) -> int:
        """Sellable quantity (excludes T+1 locked shares)."""
        pos = self.positions.get(symbol, {"quantity": 0, "locked_quantity": 0})
        return pos.get("quantity", 0) - pos.get("locked_quantity", 0)

    def get_all_positions(self) -> pd.DataFrame:
        """Return positions in same format as BrokerSimulator.get_all_positions()."""
        if not self.positions:
            return pd.DataFrame(columns=["symbol", "quantity", "locked_quantity", "avg_cost"])
        rows = []
        for sym, pos in self.positions.items():
            rows.append({
                "symbol": sym,
                "quantity": pos["quantity"],
                "locked_quantity": pos.get("locked_quantity", 0),
                "avg_cost": pos["avg_cost"],
            })
        return pd.DataFrame(rows)

    def end_of_day(self):
        """Clear T+1 lock. Called at end of each trading day."""
        for sym in list(self.positions.keys()):
            if sym in self.positions:
                self.positions[sym]["locked_quantity"] = 0
        self._today_buys = {}

    # ── Order placement (paper fills at close price) ───────────────────

    def place_buy_order(
        self, symbol: str, target_value: float,
        price: float, date: str, reason: str = "",
    ) -> dict | None:
        """Buy with lot rounding. Issues paper fill at close price.

        Slippage is applied for cost realism but does NOT affect
        the entry_price stored (close price is used for exit checks).
        """
        if target_value <= 0 or price <= 0:
            return None

        exec_price = price * (1 + self.slippage_bps / 10000)
        max_quantity = int(self.cash / exec_price)
        target_quantity = int(target_value / exec_price)
        quantity = min(target_quantity, max_quantity)
        quantity = (quantity // self.lot_size) * self.lot_size
        if quantity <= 0:
            return None

        cost = quantity * exec_price
        commission = max(cost * self.commission_rate, self.min_commission)
        total_cost = cost + commission
        if total_cost > self.cash:
            quantity = int((self.cash - commission) / exec_price)
            quantity = (quantity // self.lot_size) * self.lot_size
            if quantity <= 0:
                return None
            cost = quantity * exec_price
            commission = max(cost * self.commission_rate, self.min_commission)
            total_cost = cost + commission
        if total_cost > self.cash:
            return None

        self.cash -= total_cost
        pos = self.positions.setdefault(symbol, {
            "quantity": 0, "locked_quantity": 0, "avg_cost": 0.0,
            "entry_price": 0.0, "entry_date": date, "entry_peak": 0.0,
        })
        old_qty = pos["quantity"]
        old_cost = pos["avg_cost"]
        new_qty = old_qty + quantity
        pos["quantity"] = new_qty
        pos["avg_cost"] = (old_cost * old_qty + cost) / new_qty if new_qty > 0 else 0
        # Entry price: use close price for exit simulation accuracy
        if old_qty == 0:
            pos["entry_price"] = price
            pos["entry_peak"] = price
            pos["entry_date"] = date
        else:
            # Average up/down: update entry price to weighted average
            # For exit checks use the weighted entry
            pos["entry_price"] = (pos["entry_price"] * old_qty + price * quantity) / new_qty

        self._today_buys[symbol] = self._today_buys.get(symbol, 0) + quantity
        pos["locked_quantity"] = pos.get("locked_quantity", 0) + quantity

        fill = {
            "symbol": symbol, "side": "BUY", "quantity": quantity,
            "price": exec_price, "cost": cost,
            "commission": commission, "stamp_tax": 0.0, "date": date,
            "reason": reason or "new target",
        }
        self.trades.append(fill)
        return fill

    def place_sell_order(
        self, symbol: str, quantity: int,
        price: float, date: str, reason: str = "",
    ) -> dict | None:
        """Sell with T+1 lock check. Issues paper fill at close price."""
        available = self.get_available_quantity(symbol)
        quantity = min(quantity, available)
        if quantity <= 0 or price <= 0:
            return None

        exec_price = price * (1 - self.slippage_bps / 10000)
        proceeds = quantity * exec_price
        commission = max(proceeds * self.commission_rate, self.min_commission)
        stamp_tax = proceeds * self.stamp_tax_rate
        net_proceeds = proceeds - commission - stamp_tax

        self.cash += net_proceeds
        pos = self.positions[symbol]
        pos["quantity"] -= quantity
        if pos["quantity"] <= 0:
            del self.positions[symbol]

        fill = {
            "symbol": symbol, "side": "SELL", "quantity": quantity,
            "price": exec_price, "proceeds": proceeds,
            "commission": commission, "stamp_tax": stamp_tax, "date": date,
            "reason": reason or "unknown",
        }
        self.trades.append(fill)
        return fill

    # ── Exit simulation ────────────────────────────────────────────────

    def check_and_execute_exits(
        self, strategy, date: str, bars: pd.DataFrame,
        price_map: dict[str, float],
    ) -> list[dict]:
        """Run exit checks on all positions. Returns list of fill dicts.

        Mirrors BacktestEngine._check_and_execute_exits().
        """
        exit_fills = []
        positions_snapshot = list(self.positions.items())
        for sym, pos in positions_snapshot:
            ep = pos.get("entry_price", pos["avg_cost"])
            peak = pos.get("entry_peak", ep)
            # Update peak if current price is higher
            if sym in price_map and price_map[sym] > peak:
                self.positions[sym]["entry_peak"] = price_map[sym]
                peak = price_map[sym]

            should_exit, reason = strategy.check_exit(
                sym, date, bars, peak, ep
            )
            if should_exit:
                qty = pos["quantity"]
                avail = self.get_available_quantity(sym)
                sell_qty = min(qty, avail) if avail > 0 else qty
                fill = self.place_sell_order(sym, sell_qty, price_map.get(sym, 0), date, reason=reason)
                if fill:
                    exit_fills.append(fill)
        return exit_fills

    # ── Weight-based rebalance ─────────────────────────────────────────

    def execute_weight_rebalance(
        self, target_portfolio: list[dict],
        price_map: dict[str, float], date: str,
    ) -> list[dict]:
        """Execute trades to match target_portfolio weights.

        target_portfolio: list of {"symbol": str, "target_weight": float, ...}
        price_map: {symbol: close_price}
        """
        fills = []
        total_nav = self.get_total_value(price_map)
        if total_nav <= 0:
            return fills

        target_map = {t["symbol"]: t["target_weight"] for t in target_portfolio}
        target_syms = set(target_map.keys())
        current_syms = set(self.positions.keys())

        # SELL: positions not in target
        for sym in current_syms - target_syms:
            pos = self.positions.get(sym)
            if pos and pos["quantity"] > 0:
                avail = self.get_available_quantity(sym)
                if avail > 0:
                    fill = self.place_sell_order(sym, avail, price_map.get(sym, 0), date,
                                                  reason="removed from target — rotation")
                    if fill:
                        fills.append(fill)

        # BUY/ADJUST: target stocks
        for sym in target_syms:
            tw = target_map[sym]
            target_value = tw * total_nav
            current_value = 0.0
            if sym in self.positions:
                current_value = self.positions[sym]["quantity"] * price_map.get(sym, 0)
            diff_value = target_value - current_value

            if diff_value > 50:  # Minimum trade threshold (~0.005% of 1M)
                reason = next((t.get("reason", "") for t in target_portfolio if t["symbol"] == sym), "")
                fill = self.place_buy_order(sym, diff_value, price_map.get(sym, 0), date,
                                             reason=reason)
                if fill:
                    fills.append(fill)
            elif diff_value < -50 and sym in self.positions:
                # Reduce position
                sell_qty = min(int(abs(diff_value) / price_map.get(sym, 1)), self.get_available_quantity(sym))
                sell_qty = (sell_qty // self.lot_size) * self.lot_size
                if sell_qty > 0:
                    fill = self.place_sell_order(sym, sell_qty, price_map.get(sym, 0), date,
                                                  reason="weight reduction")
                    if fill:
                        fills.append(fill)

        return fills

    # ── State export ───────────────────────────────────────────────────

    def get_positions_as_dicts(self) -> list[dict]:
        """Export positions as list of dicts for replay persistence."""
        result = []
        for sym, pos in self.positions.items():
            result.append({
                "symbol": sym,
                "quantity": pos["quantity"],
                "locked_quantity": pos.get("locked_quantity", 0),
                "avg_cost": pos["avg_cost"],
                "entry_price": pos.get("entry_price", 0.0),
                "entry_date": pos.get("entry_date", ""),
                "entry_peak": pos.get("entry_peak", 0.0),
                "current_weight": 0.0,  # filled by caller
            })
        return result

    def get_nav(self, price_map: dict[str, float]) -> float:
        return self.get_total_value(price_map)

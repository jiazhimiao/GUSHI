"""Simulated broker with A-share trading rules.

Rules implemented:
- T+1: shares bought today cannot be sold today
- Lot size: buy orders rounded to 100-share multiples
- Stamp tax: 0.05% on sells only
- Commission: 0.025% both sides, min 5 CNY
- Price limits: cannot execute beyond ±limit
- Suspension: cannot trade suspended stocks
- Slippage: configurable bps
"""
import pandas as pd
import numpy as np


class BrokerSimulator:
    """Simulated broker for backtesting with A-share rules."""

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

        # Position tracking: symbol -> {quantity, locked_quantity, avg_cost}
        self.positions: dict[str, dict] = {}

        # Daily tracking of T+1 locked shares
        self._today_buys: dict[str, int] = {}

    def get_total_value(self, prices: dict[str, float]) -> float:
        """Compute total account value (cash + position market value)."""
        position_value = 0.0
        for sym, pos in self.positions.items():
            if sym in prices:
                position_value += pos["quantity"] * prices[sym]
        return self.cash + position_value

    def get_available_quantity(self, symbol: str) -> int:
        """Get sellable quantity for a symbol (excludes T+1 locked shares)."""
        pos = self.positions.get(symbol, {"quantity": 0, "locked_quantity": 0})
        return pos.get("quantity", 0) - pos.get("locked_quantity", 0)

    def can_trade(self, symbol: str, market_data: pd.DataFrame, date: str) -> tuple[bool, str]:
        """Check if a stock can be traded on a given date.

        Returns (can_trade, reason).
        """
        bar = market_data[
            (market_data["symbol"] == symbol) & (market_data["trade_date"] == date)
        ]
        if bar.empty:
            return False, "no_data"
        bar = bar.iloc[0]

        if bar.get("is_suspended", False):
            return False, "suspended"
        if bar.get("is_st", False):
            return False, "st"
        return True, "ok"

    def place_buy_order(
        self,
        symbol: str,
        target_value: float,
        price: float,
        limit_up: float,
        date: str,
    ) -> dict | None:
        """Place a buy order.

        Args:
            symbol: Stock code.
            target_value: Desired buy value (CNY).
            price: Reference price.
            limit_up: Upper price limit.
            date: Trade date.

        Returns:
            Order fill dict or None if unfillable.
        """
        if target_value <= 0:
            return None

        # Apply slippage
        exec_price = price * (1 + self.slippage_bps / 10000)
        exec_price = min(exec_price, limit_up)

        if exec_price <= 0:
            return None

        # Compute quantity, round to lot size
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

        # Execute
        self.cash -= total_cost

        pos = self.positions.setdefault(
            symbol,
            {"quantity": 0, "locked_quantity": 0, "avg_cost": 0.0},
        )
        old_qty = pos["quantity"]
        old_cost = pos["avg_cost"]
        new_qty = old_qty + quantity
        pos["quantity"] = new_qty
        pos["avg_cost"] = (old_cost * old_qty + cost) / new_qty if new_qty > 0 else 0

        # Lock for T+1
        self._today_buys[symbol] = self._today_buys.get(symbol, 0) + quantity
        pos["locked_quantity"] = pos.get("locked_quantity", 0) + quantity

        return {
            "symbol": symbol,
            "side": "BUY",
            "quantity": quantity,
            "price": exec_price,
            "cost": cost,
            "commission": commission,
            "stamp_tax": 0.0,
            "date": date,
        }

    def place_sell_order(
        self,
        symbol: str,
        quantity: int,
        price: float,
        limit_down: float,
        date: str,
    ) -> dict | None:
        """Place a sell order.

        Args:
            symbol: Stock code.
            quantity: Quantity to sell.
            price: Reference price.
            limit_down: Lower price limit.
            date: Trade date.

        Returns:
            Order fill dict or None if unfillable.
        """
        available = self.get_available_quantity(symbol)
        quantity = min(quantity, available)

        if quantity <= 0:
            return None

        # Apply slippage
        exec_price = price * (1 - self.slippage_bps / 10000)
        exec_price = max(exec_price, limit_down)

        if exec_price <= 0:
            return None

        proceeds = quantity * exec_price
        commission = max(proceeds * self.commission_rate, self.min_commission)
        stamp_tax = proceeds * self.stamp_tax_rate
        net_proceeds = proceeds - commission - stamp_tax

        # Execute
        self.cash += net_proceeds

        pos = self.positions[symbol]
        pos["quantity"] -= quantity
        if pos["quantity"] <= 0:
            del self.positions[symbol]

        return {
            "symbol": symbol,
            "side": "SELL",
            "quantity": quantity,
            "price": exec_price,
            "proceeds": proceeds,
            "commission": commission,
            "stamp_tax": stamp_tax,
            "date": date,
        }

    def end_of_day(self):
        """Run end-of-day processing: clear T+1 lock for next day."""
        # Previously locked shares become available
        for sym in list(self.positions.keys()):
            if sym in self.positions:
                self.positions[sym]["locked_quantity"] = 0
        self._today_buys = {}

    def get_state(self) -> dict:
        """Get current account state."""
        return {
            "cash": self.cash,
            "positions": {
                sym: pos.copy() for sym, pos in self.positions.items()
            },
        }

    def get_all_positions(self) -> pd.DataFrame:
        """Get positions as a DataFrame."""
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

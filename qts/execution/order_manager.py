"""Order lifecycle management.

Converts target portfolio to orders, manages order state machine.
"""
import pandas as pd

from qts.execution.base_gateway import BrokerGateway
from qts.risk.pre_trade import PreTradeRiskManager
from qts.utils.logger import logger


class OrderManager:
    """Manages the full order lifecycle: generate -> validate -> execute -> track."""

    def __init__(
        self,
        gateway: BrokerGateway,
        risk_manager: PreTradeRiskManager | None = None,
    ):
        self.gateway = gateway
        self.risk_manager = risk_manager
        self.order_history: list[dict] = []

    def generate_and_place(
        self,
        target_portfolio: pd.DataFrame,
        current_positions: pd.DataFrame,
        latest_prices: pd.DataFrame,
    ) -> list[dict]:
        """Convert target portfolio to orders, validate, and place.

        Args:
            target_portfolio: DataFrame with symbol, target_weight, score
            current_positions: DataFrame with symbol, quantity, avg_cost
            latest_prices: DataFrame with symbol, close

        Returns:
            List of placed order dicts.
        """
        account = self.gateway.get_account()
        placed = []

        target_map = dict(zip(
            target_portfolio["symbol"], target_portfolio["target_weight"]
        ))
        price_map = dict(zip(latest_prices["symbol"], latest_prices["close"]))

        target_symbols = set(target_map.keys())
        current_symbols = set(current_positions["symbol"].tolist()) if not current_positions.empty else set()
        total_value = account["total_value"]

        # Sell: positions not in target
        for sym in current_symbols - target_symbols:
            orders = self._generate_sell_orders(sym, current_positions, price_map, total_value)
            for o in orders:
                if self._validate_and_send(o, account):
                    placed.append(o)

        # Adjust: positions in both
        for sym in current_symbols & target_symbols:
            current_val = self._position_value(sym, current_positions, price_map)
            target_val = total_value * target_map[sym]
            diff = target_val - current_val
            if diff > 1000:
                orders = self._generate_buy_orders(sym, diff, price_map, account)
                for o in orders:
                    if self._validate_and_send(o, account):
                        placed.append(o)
            elif diff < -1000:
                orders = self._generate_sell_orders(
                    sym, current_positions, price_map, min(abs(diff), current_val)
                )
                for o in orders:
                    if self._validate_and_send(o, account):
                        placed.append(o)

        # Buy: positions not yet held
        for sym in target_symbols - current_symbols:
            target_val = total_value * target_map[sym]
            orders = self._generate_buy_orders(sym, target_val, price_map, account)
            for o in orders:
                if self._validate_and_send(o, account):
                    placed.append(o)

        return placed

    def _generate_buy_orders(self, symbol, target_value, price_map, account) -> list[dict]:
        price = price_map.get(symbol, 0)
        if price <= 0:
            return []
        qty = int(min(target_value, account["cash"]) / price)
        qty = (qty // 100) * 100
        if qty <= 0:
            return []
        return [{
            "symbol": symbol, "side": "BUY", "quantity": qty,
            "price": price, "order_value": qty * price, "order_type": "LIMIT",
        }]

    def _generate_sell_orders(self, symbol, positions, price_map, target_value=None) -> list[dict]:
        pos = positions[positions["symbol"] == symbol]
        if len(pos) == 0:
            return []
        qty = pos.iloc[0]["quantity"]
        if target_value and target_value < qty * price_map.get(symbol, 0):
            qty = int(target_value / price_map.get(symbol, 1))
        if qty <= 0:
            return []
        return [{
            "symbol": symbol, "side": "SELL", "quantity": qty,
            "price": price_map.get(symbol, 0), "order_value": qty * price_map.get(symbol, 0),
            "order_type": "LIMIT",
        }]

    def _validate_and_send(self, order: dict, account: dict) -> bool:
        if self.risk_manager:
            ok, reason = self.risk_manager.validate_order(
                order, account, pd.DataFrame()
            )
            if not ok:
                logger.warning(f"Order rejected: {order['symbol']} - {reason}")
                self.risk_manager.record_failure()
                return False
            self.risk_manager.record_success()

        order_id = self.gateway.place_order(
            symbol=order["symbol"],
            side=order["side"],
            quantity=order["quantity"],
            price=order["price"],
            order_type=order.get("order_type", "LIMIT"),
        )
        order["order_id"] = order_id
        order["status"] = "PLACED"
        self.order_history.append(order)
        return True

    @staticmethod
    def _position_value(symbol, positions, price_map) -> float:
        pos = positions[positions["symbol"] == symbol]
        if len(pos) == 0:
            return 0
        return pos.iloc[0]["quantity"] * price_map.get(symbol, 0)

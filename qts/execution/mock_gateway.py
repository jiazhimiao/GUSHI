"""Mock broker gateway for simulation/testing."""
import uuid

from qts.execution.base_gateway import BrokerGateway
from qts.utils.logger import logger


class MockGateway(BrokerGateway):
    """In-memory mock broker for simulation and testing.

    Maintains a simulated account with cash, positions, and orders.
    """

    def __init__(self, initial_cash: float = 1_000_000):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, dict] = {}
        self.orders: list[dict] = []
        self.trades: list[dict] = []
        self._connected = False

    def connect(self) -> None:
        self._connected = True
        logger.info("MockGateway connected")

    def disconnect(self) -> None:
        self._connected = False
        logger.info("MockGateway disconnected")

    def get_account(self) -> dict:
        position_value = sum(
            p.get("quantity", 0) * p.get("current_price", 0)
            for p in self.positions.values()
        )
        return {
            "cash": self.cash,
            "position_value": position_value,
            "total_value": self.cash + position_value,
            "available": self.cash,
        }

    def get_positions(self) -> list[dict]:
        return [
            {
                "symbol": sym,
                "quantity": pos["quantity"],
                "avg_cost": pos.get("avg_cost", 0),
                "current_price": pos.get("current_price", 0),
            }
            for sym, pos in self.positions.items()
        ]

    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float | None = None,
        order_type: str = "LIMIT",
    ) -> str:
        order_id = str(uuid.uuid4())[:8]
        order = {
            "order_id": order_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "price": price or 0,
            "order_type": order_type,
            "status": "FILLED",  # mock always fills
        }
        self.orders.append(order)
        self.trades.append(order)

        # Update positions
        if side == "BUY":
            pos = self.positions.setdefault(symbol, {"quantity": 0, "avg_cost": 0, "current_price": 0})
            cost = quantity * (price or 0)
            old_qty = pos["quantity"]
            old_cost = pos["avg_cost"]
            new_qty = old_qty + quantity
            pos["quantity"] = new_qty
            pos["avg_cost"] = (old_cost * old_qty + cost) / new_qty if new_qty > 0 else 0
            pos["current_price"] = price or 0
            self.cash -= cost
        else:
            pos = self.positions.get(symbol, {"quantity": 0, "avg_cost": 0, "current_price": 0})
            pos["quantity"] = max(0, pos["quantity"] - quantity)
            self.cash += quantity * (price or 0)

        return order_id

    def cancel_order(self, order_id: str) -> bool:
        for o in self.orders:
            if o["order_id"] == order_id and o["status"] == "OPEN":
                o["status"] = "CANCELLED"
                return True
        return False

    def get_orders(self) -> list[dict]:
        return self.orders.copy()

    def get_trades(self) -> list[dict]:
        return self.trades.copy()

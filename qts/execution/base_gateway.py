"""Unified broker gateway interface."""
from abc import ABC, abstractmethod


class BrokerGateway(ABC):
    """Abstract gateway for broker connectivity.

    All broker-specific implementations (QMT, PTrade, XTP, etc.)
    must implement this interface.
    """

    @abstractmethod
    def connect(self) -> None:
        """Establish connection to broker."""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Close connection."""
        pass

    @abstractmethod
    def get_account(self) -> dict:
        """Get account summary: cash, total_value, available."""
        pass

    @abstractmethod
    def get_positions(self) -> list[dict]:
        """Get current positions."""
        pass

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: str,
        quantity: int,
        price: float | None = None,
        order_type: str = "LIMIT",
    ) -> str:
        """Place an order, return order_id."""
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order."""
        pass

    @abstractmethod
    def get_orders(self) -> list[dict]:
        """Get all orders (open and filled)."""
        pass

    @abstractmethod
    def get_trades(self) -> list[dict]:
        """Get filled trades."""
        pass

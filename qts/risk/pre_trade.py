"""Pre-trade risk management.

Every order must pass through risk checks before being sent to the broker.
"""
import pandas as pd


class PreTradeRiskManager:
    """Validates orders before execution."""

    def __init__(
        self,
        max_order_value: float = 500_000,
        max_position_weight: float = 0.08,
        max_daily_turnover: float = 0.50,
        max_positions: int = 30,
        blacklist: set[str] | None = None,
        ban_st: bool = True,
        ban_suspended: bool = True,
        ban_limit_up: bool = True,
        ban_limit_down: bool = True,
        max_consecutive_failures: int = 3,
    ):
        self.max_order_value = max_order_value
        self.max_position_weight = max_position_weight
        self.max_daily_turnover = max_daily_turnover
        self.max_positions = max_positions
        self.blacklist = blacklist or set()
        self.ban_st = ban_st
        self.ban_suspended = ban_suspended
        self.ban_limit_up = ban_limit_up
        self.ban_limit_down = ban_limit_down
        self.max_consecutive_failures = max_consecutive_failures

        self._consecutive_failures = 0

    def validate_order(
        self,
        order: dict,
        account: dict,
        positions: pd.DataFrame,
        market_data: pd.DataFrame | None = None,
    ) -> tuple[bool, str]:
        """Validate a single order.

        Args:
            order: Dict with symbol, side, quantity, price, order_value
            account: Dict with cash, total_value
            positions: DataFrame of current positions
            market_data: Optional market data for ST/suspension checks

        Returns:
            (approved, reason)
        """
        symbol = order.get("symbol", "")
        side = order.get("side", "BUY")
        order_value = order.get("order_value", 0)

        # Blacklist check
        if symbol in self.blacklist:
            return False, "blacklist"

        # Order value cap
        if order_value > self.max_order_value:
            return False, f"order_value_exceed: {order_value} > {self.max_order_value}"

        # Cash check for buys
        if side == "BUY" and order_value > account.get("cash", 0):
            return False, "cash_not_enough"

        # Position weight cap
        if side == "BUY":
            total_value = account.get("total_value", 0)
            if total_value > 0:
                new_weight = order_value / total_value
                existing_weight = 0.0
                if not positions.empty and symbol in positions["symbol"].values:
                    pos_row = positions[positions["symbol"] == symbol]
                    if len(pos_row) > 0 and "market_value" in pos_row.columns:
                        existing_weight = pos_row.iloc[0]["market_value"] / total_value
                if new_weight + existing_weight > self.max_position_weight:
                    return False, f"position_weight_exceed: {new_weight + existing_weight:.4f}"

        # Max positions
        if side == "BUY":
            current_count = len(positions)
            if current_count >= self.max_positions and symbol not in positions["symbol"].values:
                return False, f"max_positions: {current_count} >= {self.max_positions}"

        # Kill switch
        if self._consecutive_failures >= self.max_consecutive_failures:
            return False, f"kill_switch: {self._consecutive_failures} consecutive failures"

        return True, "ok"

    def record_failure(self):
        self._consecutive_failures += 1

    def record_success(self):
        self._consecutive_failures = 0

    def is_killed(self) -> bool:
        return self._consecutive_failures >= self.max_consecutive_failures

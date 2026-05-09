"""Base strategy interface."""
from abc import ABC, abstractmethod

import pandas as pd


class Strategy(ABC):
    """Abstract base class for all strategies.

    A strategy generates target portfolio weights from market data and factors.
    It does NOT execute trades — that's the execution layer's job.
    """

    name: str
    # Set True if generate_signals returns target weights directly (skip PortfolioConstructor)
    skip_portfolio_construction: bool = False

    @abstractmethod
    def generate_signals(
        self,
        current_date: str,
        market_data: pd.DataFrame,
        factor_data: pd.DataFrame,
        current_positions: pd.DataFrame,
    ) -> pd.DataFrame:
        """Generate target portfolio for the given date.

        Args:
            current_date: Current trading date (YYYY-MM-DD).
            market_data: DataFrame with at minimum columns:
                symbol, trade_date, close, volume, is_suspended, limit_up, limit_down, is_st
            factor_data: DataFrame with columns:
                trade_date, symbol, factor_name, factor_value
            current_positions: DataFrame with columns:
                symbol, quantity, avg_cost

        Returns:
            DataFrame with columns:
                symbol, score, target_weight, reason
            Empty DataFrame if no signals.
        """
        pass

    def check_exit(
        self, sym: str, date: str, market_data: pd.DataFrame, entry_peak: float
    ) -> tuple[bool, str]:
        """Optional: check if a position should be exited. Override in subclass."""
        return False, ""

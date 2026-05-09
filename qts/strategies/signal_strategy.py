"""Concrete signal-based strategy: momentum + volatility + turnover filter."""
import pandas as pd
import numpy as np

from qts.strategies.base import Strategy
from qts.utils.logger import logger


class MomentumValueStrategy(Strategy):
    """Multi-factor strategy combining momentum, volatility, and turnover.

    Stock universe is filtered to remove ST, suspended, and illiquid stocks.
    A composite score is computed from registered factors with configurable weights.
    """

    name = "momentum_value"

    def __init__(
        self,
        factor_weights: dict[str, float] | None = None,
        filters: dict | None = None,
        portfolio_config: dict | None = None,
    ):
        """
        Args:
            factor_weights: {factor_name: weight} for composite score.
                Positive weight = prefer higher factor values.
            filters: Dict of filter parameters:
                - exclude_st: bool
                - exclude_suspended: bool
                - min_list_days: int
                - min_turnover_amount: float (min daily turnover in CNY)
            portfolio_config: Dict passed to PortfolioConstructor.
        """
        self.factor_weights = factor_weights or {
            "momentum_20d": 0.4,
            "volatility_60d": -0.3,
            "turnover_ratio": 0.3,
        }
        self.filters = filters or {
            "exclude_st": True,
            "exclude_suspended": True,
            "min_list_days": 120,
            "min_turnover_amount": 50_000_000,  # 5000万
        }
        self.portfolio_config = portfolio_config or {
            "top_n": 20,
            "max_weight_per_stock": 0.08,
            "cash_buffer": 0.02,
            "weighting": "equal",
        }

    def generate_signals(
        self,
        current_date: str,
        market_data: pd.DataFrame,
        factor_data: pd.DataFrame,
        current_positions: pd.DataFrame,
    ) -> pd.DataFrame:
        """Generate composite-score signals for the given date.

        Filters, then z-scores each factor, combines with weights, ranks.
        """
        # Get latest bar per symbol on current_date
        latest = market_data[market_data["trade_date"] == current_date].copy()
        if latest.empty:
            logger.warning(f"No market data for {current_date}")
            return pd.DataFrame()

        # --- Filters ---
        symbols = latest["symbol"].unique()
        mask = pd.Series(True, index=symbols)

        if self.filters.get("exclude_st"):
            st_symbols = latest.loc[latest["is_st"], "symbol"].unique()
            mask[st_symbols] = False

        if self.filters.get("exclude_suspended"):
            susp_symbols = latest.loc[latest["is_suspended"], "symbol"].unique()
            mask[susp_symbols] = False

        # Exclude stocks with insufficient listing (approximate: data history)
        if self.filters.get("min_list_days"):
            min_days = self.filters["min_list_days"]
            history = market_data.groupby("symbol")["trade_date"].nunique()
            short_history = history[history < min_days].index
            short_in_mask = short_history.intersection(mask.index)
            mask[short_in_mask] = False

        # Exclude low turnover stocks
        if self.filters.get("min_turnover_amount"):
            min_amount = self.filters["min_turnover_amount"]
            recent_turnover = (
                market_data[market_data["trade_date"] == current_date]
                .groupby("symbol")["amount"]
                .sum()
            )
            low_turnover = recent_turnover[recent_turnover < min_amount].index
            mask[low_turnover] = False

        eligible = mask[mask].index.tolist()
        if len(eligible) < self.portfolio_config.get("top_n", 20):
            logger.warning(f"Only {len(eligible)} eligible stocks for {current_date}")

        # --- Factor Scoring ---
        # Get factor values for current_date for eligible symbols
        factor_latest = factor_data[
            (factor_data["trade_date"] == current_date)
            & (factor_data["symbol"].isin(eligible))
        ]

        if factor_latest.empty:
            logger.warning(f"No factor data for {current_date}")
            return pd.DataFrame()

        # Pivot to (symbol x factor_name)
        factor_matrix = factor_latest.pivot(
            index="symbol", columns="factor_name", values="factor_value"
        )

        # Z-score each factor cross-sectionally
        composite = pd.Series(0.0, index=factor_matrix.index)
        for factor_name, weight in self.factor_weights.items():
            if factor_name not in factor_matrix.columns:
                logger.debug(f"Factor {factor_name} missing, skipping")
                continue
            vals = factor_matrix[factor_name].astype(float)
            # Cross-sectional z-score
            z = (vals - vals.mean()) / (vals.std() + 1e-10)
            composite += z * weight

        # Rank and score
        result = pd.DataFrame({
            "symbol": composite.index,
            "score": composite.values,
        }).sort_values("score", ascending=False)

        logger.info(f"[{current_date}] Generated signals for {len(result)} stocks")
        return result

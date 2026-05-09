"""Factor computation engine.

Computes all registered factors on bar data and stores results.
"""
from dataclasses import dataclass, field

import pandas as pd

from qts.utils.logger import logger
from qts.factors.momentum import momentum_factor, turnover_factor
from qts.factors.volatility import volatility_factor


@dataclass
class FactorDefinition:
    """Definition of a computable factor."""
    name: str
    func: callable
    params: dict = field(default_factory=dict)
    depends_on: str = "close"  # "close", "volume", or "ohlc"


class FactorEngine:
    """Registry and compute engine for factors.

    Usage:
        engine = FactorEngine()
        engine.register("momentum_20d", momentum_factor, {"period": 20})
        results = engine.compute(prices, volumes)
    """

    def __init__(self):
        self._registry: list[FactorDefinition] = []

    def register(self, name: str, func: callable, params: dict | None = None, depends_on: str = "close"):
        """Register a factor for computation."""
        self._registry.append(FactorDefinition(
            name=name, func=func, params=params or {}, depends_on=depends_on
        ))
        logger.info(f"Registered factor: {name}")

    def compute(
        self,
        prices: pd.DataFrame,
        volumes: pd.DataFrame | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Compute all registered factors.

        Args:
            prices: (trade_date x symbol) close price matrix.
            volumes: (trade_date x symbol) volume matrix.

        Returns:
            Dict mapping factor_name -> DataFrame of factor values.
        """
        results = {}
        for fdef in self._registry:
            logger.debug(f"Computing {fdef.name}...")
            data = volumes if fdef.depends_on == "volume" else prices
            factor_df = fdef.func(data, **fdef.params)
            factor_df = factor_df.dropna(how="all")
            results[fdef.name] = factor_df
            logger.debug(f"  {fdef.name}: {factor_df.shape}")
        return results

    def compute_as_long(
        self,
        prices: pd.DataFrame,
        volumes: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        """Compute all factors and return as a long-format DataFrame.

        Returns:
            DataFrame with columns: trade_date, symbol, factor_name, factor_value
        """
        results = self.compute(prices, volumes)
        frames = []
        for name, df in results.items():
            long = df.stack().reset_index()
            long.columns = ["trade_date", "symbol", "factor_value"]
            long["factor_name"] = name
            frames.append(long)
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

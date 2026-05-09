"""Portfolio construction from strategy signals."""
import pandas as pd


class PortfolioConstructor:
    """Convert ranked signals into target portfolio weights.

    Handles:
    - Top-N selection
    - Max weight per stock
    - Cash buffer
    - Equal-weight or score-weighted
    """

    def __init__(
        self,
        top_n: int = 20,
        max_weight_per_stock: float = 0.08,
        cash_buffer: float = 0.02,
        weighting: str = "equal",  # "equal" or "score"
    ):
        self.top_n = top_n
        self.max_weight_per_stock = max_weight_per_stock
        self.cash_buffer = cash_buffer
        self.weighting = weighting

    def build_target_portfolio(self, signals: pd.DataFrame) -> pd.DataFrame:
        """Build target portfolio from scored signals.

        Args:
            signals: DataFrame with columns: symbol, score

        Returns:
            DataFrame with columns: symbol, score, target_weight, reason
        """
        if signals.empty:
            return pd.DataFrame()

        df = signals.sort_values("score", ascending=False).copy()

        # Top-N selection
        selected = df.head(self.top_n)

        if self.weighting == "equal":
            n = len(selected)
            raw_weight = min(
                (1.0 - self.cash_buffer) / n if n > 0 else 0,
                self.max_weight_per_stock,
            )
            selected["target_weight"] = raw_weight
        elif self.weighting == "score":
            total_score = selected["score"].abs().sum()
            if total_score > 0:
                selected["target_weight"] = (
                    selected["score"].abs() / total_score * (1.0 - self.cash_buffer)
                )
            else:
                selected["target_weight"] = (1.0 - self.cash_buffer) / len(selected)
            selected["target_weight"] = selected["target_weight"].clip(
                upper=self.max_weight_per_stock
            )

        selected["reason"] = f"top_{self.top_n}_{self.weighting}"
        return selected[["symbol", "score", "target_weight", "reason"]]

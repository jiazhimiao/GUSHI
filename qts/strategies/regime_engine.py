"""Market regime scoring engine: continuous 0-1 score → adaptive strategy params.

Regime score = w1*breadth + w2*trend_strength + w3*stability + w4*volume_energy

Then linear interpolation maps score to strategy parameters.
"""
import numpy as np
import pandas as pd

from qts.utils.logger import logger


class RegimeEngine:
    """Continuous market regime scorer with adaptive parameter mapping.

    Computes a 0-1 regime score from four dimensions, then linearly interpolates
    strategy parameters between bear (score_low) and bull (score_high) extremes.
    """

    def __init__(
        self,
        # Regime weights
        w_breadth: float = 0.40,
        w_trend: float = 0.30,
        w_stability: float = 0.15,
        w_volume: float = 0.15,
        # Score thresholds
        score_low: float = 0.30,   # below this = full bear params
        score_high: float = 0.70,  # above this = full bull params
        # Bull extremes (score >= score_high)
        breakout_bull: int = 15,
        breakout_bear: int = 30,
        atr_bull: float = 3.0,
        atr_bear: float = 1.5,
        vol_ratio_bull: float = 1.2,
        vol_ratio_bear: float = 2.0,
        top_n_bull: int = 15,
        top_n_bear: int = 0,
        alloc_bull: float = 1.0,
        alloc_bear: float = 0.0,
        ma_days_bull: int = 20,
        ma_days_bear: int = 40,
        breadth_ma: int = 30,
        support_bull: int = 5,
        support_bear: int = 15,
    ):
        self.w_breadth = w_breadth
        self.w_trend = w_trend
        self.w_stability = w_stability
        self.w_volume = w_volume
        self.score_low = score_low
        self.score_high = score_high
        self.breakout_bull = breakout_bull
        self.breakout_bear = breakout_bear
        self.atr_bull = atr_bull
        self.atr_bear = atr_bear
        self.vol_ratio_bull = vol_ratio_bull
        self.vol_ratio_bear = vol_ratio_bear
        self.top_n_bull = top_n_bull
        self.top_n_bear = top_n_bear
        self.alloc_bull = alloc_bull
        self.alloc_bear = alloc_bear
        self.ma_days_bull = ma_days_bull
        self.ma_days_bear = ma_days_bear
        self.breadth_ma = breadth_ma
        self.support_bull = support_bull
        self.support_bear = support_bear

    def compute_score(
        self,
        date: str = "",
        breadth: float = 0.0,
        prices: pd.DataFrame | None = None,
        volumes: pd.DataFrame | None = None,
        trend_raw: float | None = None,
        stability_raw: float | None = None,
        volume_raw: float | None = None,
    ) -> float:
        """Compute regime score from four dimensions.

        Fast path: pass pre-computed trend_raw/stability_raw/volume_raw
        (computed once by engine). Slow path (fallback): pass raw
        prices/volumes DataFrames.

        Returns float between 0 and 1.
        """
        score = self.w_breadth * breadth

        if trend_raw is not None:
            score += self.w_trend * trend_raw
        elif prices is not None and not prices.empty:
            score += self.w_trend * self._trend_strength(prices)

        if stability_raw is not None:
            score += self.w_stability * stability_raw
        elif prices is not None and not prices.empty:
            score += self.w_stability * self._stability(prices)

        if volume_raw is not None:
            score += self.w_volume * volume_raw
        elif volumes is not None and not volumes.empty:
            score += self.w_volume * self._volume_energy(volumes)

        return min(1.0, max(0.0, score))

    def _trend_strength(self, prices: pd.DataFrame) -> float:
        """Estimate trend strength from median stock performance.

        Uses ratio of 20-day change to 60-day volatility as a simple trend proxy.
        Returns 0-1 where 1 = strong trend.
        """
        if len(prices) < 60:
            return 0.5
        # Median stock: 20-day price change
        pct_20 = prices.iloc[-1] / prices.iloc[-20] - 1
        median_ret = pct_20.median()
        # Normalize: 2% monthly = slight trend, 5% = strong
        strength = min(1.0, max(0.0, (median_ret - 0.0) / 0.05))
        return strength

    def _stability(self, prices: pd.DataFrame) -> float:
        """Estimate stability: 1 - (current vol / historical vol).

        High vol relative to history → low stability.
        """
        if len(prices) < 60:
            return 0.5
        # 20-day vol vs 60-day vol for median stock
        rets = prices.pct_change(fill_method=None)
        vol_20 = rets.iloc[-20:].std()
        vol_60 = rets.iloc[-60:].std()
        median_vol_20 = vol_20.median()
        median_vol_60 = vol_60.median()
        if median_vol_60 <= 0:
            return 0.5
        ratio = median_vol_20 / median_vol_60
        stability = 1.0 - min(1.0, max(0.0, ratio - 0.5))
        return stability

    def _volume_energy(self, volumes: pd.DataFrame) -> float:
        """Estimate volume energy: recent avg / long-term avg."""
        if len(volumes) < 60:
            return 0.5
        vol_20 = volumes.iloc[-20:].mean().median()
        vol_60 = volumes.iloc[-60:].mean().median()
        if vol_60 <= 0:
            return 0.5
        ratio = vol_20 / vol_60
        energy = min(1.0, max(0.0, (ratio - 0.7) / 0.6))
        return energy

    def map_params(self, score: float) -> dict:
        """Map regime score to strategy parameters via linear interpolation.

        Returns dict of adapted strategy parameters.
        """
        t = (score - self.score_low) / (self.score_high - self.score_low + 1e-10)
        t = min(1.0, max(0.0, t))

        def lerp(bear_val, bull_val):
            return bear_val + (bull_val - bear_val) * t

        return {
            "breakout_days": int(round(lerp(self.breakout_bear, self.breakout_bull))),
            "support_days": int(round(lerp(self.support_bear, self.support_bull))),
            "ma_days": int(round(lerp(self.ma_days_bear, self.ma_days_bull))),
            "atr_multiple": round(lerp(self.atr_bear, self.atr_bull), 1),
            "volume_ratio": round(lerp(self.vol_ratio_bear, self.vol_ratio_bull), 1),
            "top_n": int(round(lerp(self.top_n_bear, self.top_n_bull))),
            "alloc_pct": round(lerp(self.alloc_bear, self.alloc_bull), 2),
        }

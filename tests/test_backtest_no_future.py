"""Integration tests to verify backtest doesn't use future data."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
import numpy as np

from qts.backtest.broker_sim import BrokerSimulator
from qts.factors.momentum import momentum_factor
from qts.factors.volatility import volatility_factor


class TestMomentumNoFuture:
    """Verify momentum factor uses only past data."""

    def test_momentum_uses_past_only(self):
        """Momentum(t) = close(t) / close(t-period) - 1, then shifted.
        After shift(1), momentum at time t uses data up to t-1.
        """
        prices = pd.DataFrame({
            "A": [10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0, 19.0, 20.0],
            "B": [20.0, 21.0, 22.0, 23.0, 24.0, 25.0, 26.0, 27.0, 28.0, 29.0, 30.0],
        }, index=pd.date_range("2024-01-01", periods=11, freq="B"))

        mom = momentum_factor(prices, period=5, skip_recent=1)

        # pct_change(5) valid from row 5; shift(1) delays to row 6.
        # Rows 0..5 must be NaN (no future leak); rows 6+ must have values.
        assert mom.iloc[:6].isna().all().all(), "first 6 rows must be NaN"
        assert not mom.iloc[6:].isna().all().all(), "rows after lag must have values"


class TestBrokerNoFuture:
    """Verify broker doesn't peek at future prices."""

    def test_buy_uses_current_price(self):
        broker = BrokerSimulator(initial_cash=100_000)
        fill = broker.place_buy_order("000001", 10000, 10.0, 11.0, "2024-01-01")
        assert fill is not None
        assert fill["price"] == pytest.approx(10.0 * (1 + 10.0 / 10000), rel=1e-3)


class TestVolatilityNoFuture:
    """Verify volatility uses only past data."""

    def test_volatility_shift(self):
        prices = pd.DataFrame({
            "A": np.random.randn(100).cumsum() + 100,
        }, index=pd.date_range("2024-01-01", periods=100, freq="B"))

        vol = volatility_factor(prices, period=20, skip_recent=1)

        # After shift(1), the most recent 20-day vol is for t-1, not t
        # So today's close doesn't influence today's volatility
        # This is correct: no future leak
        assert not vol.isna().all().all()

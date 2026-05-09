"""Test A-share broker simulation rules."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd

from qts.backtest.broker_sim import BrokerSimulator


@pytest.fixture
def broker():
    return BrokerSimulator(
        initial_cash=1_000_000,
        commission_rate=0.00025,
        stamp_tax_rate=0.0005,
        min_commission=5.0,
        slippage_bps=10.0,
        lot_size=100,
    )


class TestLotRounding:
    def test_buy_rounds_to_100(self, broker):
        fill = broker.place_buy_order("000001", 10000, 10.0, 11.0, "2024-01-01")
        assert fill is not None
        assert fill["quantity"] % 100 == 0

    def test_small_buy_rejected(self, broker):
        fill = broker.place_buy_order("000001", 500, 10.0, 11.0, "2024-01-01")
        assert fill is None  # Can't even buy 100 shares

    def test_cash_constrained(self, broker):
        broker.cash = 2000  # Only 2000 CNY
        fill = broker.place_buy_order("000001", 5000, 10.0, 11.0, "2024-01-01")
        assert fill is None or fill["quantity"] <= 100  # Can buy at most 100 shares


class TestTPlusOne:
    def test_buy_locks_shares(self, broker):
        broker.place_buy_order("000001", 10000, 10.0, 11.0, "2024-01-01")
        avail = broker.get_available_quantity("000001")
        assert avail == 0  # Locked due to T+1

    def test_end_of_day_unlocks(self, broker):
        broker.place_buy_order("000001", 10000, 10.0, 11.0, "2024-01-01")
        broker.end_of_day()
        avail = broker.get_available_quantity("000001")
        assert avail > 0

    def test_cannot_sell_same_day_buy(self, broker):
        broker.place_buy_order("000001", 10000, 10.0, 11.0, "2024-01-01")
        fill = broker.place_sell_order("000001", 100, 10.5, 9.5, "2024-01-01")
        assert fill is None  # Should be rejected: T+1


class TestCommission:
    def test_buy_commission(self, broker):
        fill = broker.place_buy_order("000001", 50000, 10.0, 11.0, "2024-01-01")
        assert fill is not None
        expected_commission = max(fill["cost"] * 0.00025, 5.0)
        assert abs(fill["commission"] - expected_commission) < 0.01

    def test_sell_stamp_tax(self, broker):
        broker.place_buy_order("000001", 10000, 10.0, 11.0, "2024-01-01")
        broker.end_of_day()

        fill = broker.place_sell_order("000001", 100, 10.5, 9.5, "2024-01-02")
        assert fill is not None
        assert fill["stamp_tax"] > 0
        expected_stamp = fill["proceeds"] * 0.0005
        assert abs(fill["stamp_tax"] - expected_stamp) < 0.01


class TestPriceLimits:
    def test_buy_respects_limit_up(self, broker):
        fill = broker.place_buy_order("000001", 10000, 10.0, 10.5, "2024-01-01")
        assert fill is not None
        assert fill["price"] <= 10.5

    def test_sell_respects_limit_down(self, broker):
        broker.place_buy_order("000001", 10000, 10.0, 11.0, "2024-01-01")
        broker.end_of_day()

        fill = broker.place_sell_order("000001", 100, 10.0, 9.5, "2024-01-02")
        assert fill is not None
        assert fill["price"] >= 9.5


class TestAccountValue:
    def test_cash_decreases_after_buy(self, broker):
        initial_cash = broker.cash
        fill = broker.place_buy_order("000001", 10000, 10.0, 11.0, "2024-01-01")
        assert fill is not None
        assert broker.cash < initial_cash

    def test_cash_increases_after_sell(self, broker):
        broker.place_buy_order("000001", 10000, 10.0, 11.0, "2024-01-01")
        broker.end_of_day()
        cash_before = broker.cash

        fill = broker.place_sell_order("000001", 100, 10.5, 9.5, "2024-01-02")
        assert fill is not None
        assert broker.cash > cash_before

    def test_get_total_value(self, broker):
        fill = broker.place_buy_order("000001", 10000, 10.0, 11.0, "2024-01-01")
        assert fill is not None
        tv = broker.get_total_value({"000001": 10.0})
        # Total value = cash + position market value
        positions = broker.get_all_positions()
        pos_val = positions.iloc[0]["quantity"] * 10.0
        assert abs(tv - broker.cash - pos_val) < 0.01

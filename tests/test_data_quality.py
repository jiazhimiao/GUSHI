"""Test data quality checks."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.data.quality import check_bar_quality, check_no_future_leak


class TestBarQuality:
    def test_empty_data(self):
        df = pd.DataFrame()
        results = check_bar_quality(df)
        assert "empty_data" in results

    def test_good_data_passes(self):
        symbols = ["000001", "000002"]
        dates = pd.date_range("2024-01-01", "2024-01-31", freq="B")
        rows = []
        for sym in symbols:
            for d in dates:
                base = 10.0 + hash(sym) % 20
                rows.append({
                    "symbol": sym,
                    "trade_date": d.strftime("%Y-%m-%d"),
                    "open": base,
                    "high": base * 1.05,
                    "low": base * 0.95,
                    "close": base * 1.02,
                    "volume": 1_000_000.0,
                    "amount": base * 1_000_000,
                    "adj_factor": 1.0,
                    "is_suspended": False,
                    "limit_up": base * 1.10,
                    "limit_down": base * 0.90,
                    "is_st": False,
                })
        df = pd.DataFrame(rows)
        results = check_bar_quality(df)
        assert "ohlc_valid" in results
        assert "PASS" in str(results["ohlc_valid"])

    def test_bad_ohlc_detected(self):
        df = pd.DataFrame([{
            "symbol": "000001",
            "trade_date": "2024-01-01",
            "open": 10.0,
            "high": 9.0,  # high < open -- bad!
            "low": 11.0,  # low > close -- bad!
            "close": 10.5,
            "volume": 1_000_000.0,
            "amount": 10_000_000.0,
            "adj_factor": 1.0,
            "is_suspended": False,
            "limit_up": 11.0,
            "limit_down": 9.0,
            "is_st": False,
        }])
        results = check_bar_quality(df)
        assert "FAIL" in str(results["ohlc_valid"])

    def test_negative_prices_detected(self):
        df = pd.DataFrame([{
            "symbol": "000001",
            "trade_date": "2024-01-01",
            "open": -10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.0,
            "volume": 1_000_000.0,
            "amount": 10_000_000.0,
            "adj_factor": 1.0,
            "is_suspended": False,
            "limit_up": 11.0,
            "limit_down": 9.0,
            "is_st": False,
        }])
        results = check_bar_quality(df)
        assert "FAIL" in str(results["negative_prices"])


class TestFutureLeakCheck:
    def test_no_leak_when_dates_align(self):
        factor_df = pd.DataFrame({
            "symbol": ["000001", "000002"],
            "trade_date": ["2024-01-02", "2024-01-02"],
            "factor_value": [0.05, -0.03],
        })
        bar_df = pd.DataFrame({
            "symbol": ["000001", "000002", "000001", "000002"],
            "trade_date": ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-02"],
            "close": [10.0, 20.0, 10.5, 20.5],
        })
        ok = check_no_future_leak(factor_df, bar_df)
        assert ok  # Factor dates <= bar dates

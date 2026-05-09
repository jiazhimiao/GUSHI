"""Build historical constituent lists for backtesting.

Usage:
    python scripts/build_historical_universe.py --universe HS300

Fetches constituent lists at regular intervals and stores them with effective dates.
Backtest engines should use the constituent list that was active at each rebalance date,
NOT the current constituent list projected backwards.
"""
import sys
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd

from qts.utils.logger import logger, setup_file_log
from qts.utils.config import get_project_root


def fetch_hs300_history():
    """Fetch HS300 constituent history.

    Since AKShare's CSIndex endpoint may fail (proxy issues), we use the existing
    data file to identify when each stock first appeared and last appeared.
    This is a proxy for actual historical constituents.
    """
    root = get_project_root()
    bar_path = root / "data/raw/HS300_daily.parquet"

    if not bar_path.exists():
        logger.error("No HS300 data file. Run update_daily_data.py first.")
        return

    bars = pd.read_parquet(bar_path)
    bars["trade_date"] = pd.to_datetime(bars["trade_date"])

    # For each symbol, find first and last trade date in our data
    symbol_range = bars.groupby("symbol")["trade_date"].agg(["min", "max", "count"])
    symbol_range = symbol_range.sort_values("min")

    # Determine which symbols were active in each year
    constituents = {}
    for year in range(2022, 2027):
        year_start = pd.Timestamp(f"{year}-01-01")
        year_end = pd.Timestamp(f"{year}-12-31")

        active = symbol_range[
            (symbol_range["min"] <= year_end)
            & (symbol_range["max"] >= year_start)
        ]
        constituents[str(year)] = sorted(active.index.tolist())
        logger.info(f"  {year}: {len(active)} stocks active")

    # Save
    out_path = root / "data" / "historical_constituents.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({
            "description": "HS300 constituents by year (from available data)",
            "note": "Based on first/last appearance in data. Approximate.",
            "constituents": constituents,
        }, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved to {out_path}")

    return constituents


def main():
    setup_file_log()
    logger.info("Building historical constituent lists...")
    fetch_hs300_history()


if __name__ == "__main__":
    main()

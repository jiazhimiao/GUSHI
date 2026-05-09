"""Daily data update script.

Usage:
    python scripts/update_daily_data.py
    python scripts/update_daily_data.py --start 2020-01-01 --end 2024-12-31 --universe HS300
"""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from qts.data.calendar import load_or_fetch_calendar
from qts.data.akshare_client import AKShareClient
from qts.data.storage import save_bars
from qts.data.quality import check_bar_quality
from qts.utils.logger import logger, setup_file_log
from qts.utils.config import load_yaml


def get_hs300_symbols() -> list[str]:
    """Get HS300 constituent stock codes."""
    import akshare as ak
    df = ak.index_stock_cons_csindex(symbol="000300")
    return df["成分券代码"].astype(str).str.zfill(6).tolist()


def get_csi500_symbols() -> list[str]:
    """Get CSI500 constituent stock codes."""
    import akshare as ak
    df = ak.index_stock_cons_csindex(symbol="000905")
    return df["成分券代码"].astype(str).str.zfill(6).tolist()


UNIVERSE_FETCHERS = {
    "HS300": get_hs300_symbols,
    "CSI500": get_csi500_symbols,
}


def main():
    parser = argparse.ArgumentParser(description="Update daily A-share data")
    parser.add_argument("--start", default="2022-01-01", help="Start date")
    parser.add_argument("--end", default="2025-12-31", help="End date")
    parser.add_argument("--universe", default="HS300", help="Stock universe")
    parser.add_argument("--symbols", nargs="*", help="Specific stock codes")
    args = parser.parse_args()

    setup_file_log()
    root = Path(__file__).resolve().parent.parent

    # 1. Fetch calendar
    logger.info("=== Step 1: Trading Calendar ===")
    cal = load_or_fetch_calendar(args.start, args.end, str(root / "data/raw/calendar.parquet"))
    logger.info(f"Trading days: {len(cal)}")

    # 2. Get symbols
    if args.symbols:
        symbols = args.symbols
    else:
        fetcher = UNIVERSE_FETCHERS.get(args.universe)
        if fetcher is None:
            logger.error(f"Unknown universe: {args.universe}")
            sys.exit(1)
        try:
            symbols = fetcher()
        except Exception as e:
            bar_file = root / f"data/raw/{args.universe}_daily.parquet"
            if bar_file.exists():
                import pandas as pd
                symbols = pd.read_parquet(bar_file)["symbol"].unique().tolist()
                logger.warning(f"Failed to fetch constituent list ({e}), using {len(symbols)} existing symbols")
            else:
                logger.error(f"Cannot get symbols and no existing data file: {e}")
                sys.exit(1)
        logger.info(f"=== Step 2: {args.universe} Universe ({len(symbols)} stocks) ===")

    # 3. Fetch bars
    logger.info("=== Step 3: Fetching Daily Bars ===")
    client = AKShareClient()
    bars = client.get_bars(symbols, args.start, args.end, freq="1d", adjusted="qfq")

    if bars.empty:
        logger.error("No data fetched! Check network or AKShare availability.")
        sys.exit(1)

    # 4. Save bars
    logger.info("=== Step 4: Saving to Parquet ===")
    bar_path = root / f"data/raw/{args.universe}_daily.parquet"
    save_bars(bars, bar_path)

    # 5. Quality check
    logger.info("=== Step 5: Quality Check ===")
    results = check_bar_quality(bars)

    logger.info("=== Done ===")
    logger.info(f"Saved {len(bars)} rows to {bar_path}")


if __name__ == "__main__":
    main()

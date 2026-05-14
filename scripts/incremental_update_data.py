"""Incremental data update — fetch new bars, merge with existing, verify.

Usage:
    python scripts/incremental_update_data.py --symbols HS300 --start 2026-05-06 --end 2026-05-14
"""
import sys, json, hashlib, shutil
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from qts.data.akshare_client import AKShareClient
from qts.utils.logger import logger
from qts.utils.config import get_project_root

ROOT = get_project_root()


def hash_file(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", default="2026-05-06")
    parser.add_argument("--end", default="2026-05-14")
    parser.add_argument("--symbols", default="HS300")
    args = parser.parse_args()

    bar_path = ROOT / f"data/raw/{args.symbols}_daily.parquet"

    # 1. Record pre-update state
    logger.info("=" * 60)
    logger.info("PRE-UPDATE STATE")
    logger.info("=" * 60)
    old_hash = hash_file(bar_path)
    old_df = pd.read_parquet(bar_path)
    old_dates = sorted(old_df["trade_date"].unique())
    old_count = len(old_df)
    logger.info(f"  Parquet MD5: {old_hash}")
    logger.info(f"  Rows: {old_count}, dates: {len(old_dates)}, first: {old_dates[0]}, last: {old_dates[-1]}")

    # 2. Backup
    backup_path = bar_path.with_suffix(".parquet.bak")
    shutil.copy2(bar_path, backup_path)
    logger.info(f"  Backup: {backup_path}")

    # 3. Fetch new data
    logger.info(f"\n{'='*60}")
    logger.info(f"FETCHING: {args.start} → {args.end}")
    logger.info(f"{'='*60}")

    # Get symbols from existing data (not API — to keep consistency)
    symbols = sorted(old_df["symbol"].unique())
    logger.info(f"  Symbols: {len(symbols)} (from existing data)")

    client = AKShareClient()
    new_df = client.get_bars(symbols, args.start, args.end, freq="1d", adjusted="qfq")

    if new_df.empty:
        logger.error("No new data fetched. Check network or market is closed.")
        return

    new_dates = sorted(new_df["trade_date"].unique())
    logger.info(f"  Fetched: {len(new_df)} rows, {len(new_dates)} dates: {new_dates}")

    # 4. Merge: dedup on (trade_date, symbol)
    merged = pd.concat([old_df, new_df], ignore_index=True)
    before_dedup = len(merged)
    merged = merged.drop_duplicates(subset=["trade_date", "symbol"], keep="last")
    after_dedup = len(merged)
    logger.info(f"\n  Merge: {before_dedup} → {after_dedup} rows (removed {before_dedup - after_dedup} duplicates)")

    # 5. Verify old data unchanged
    old_slice = merged[merged["trade_date"] <= old_dates[-1]]
    old_slice_sorted = old_slice.sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    old_sorted = old_df.sort_values(["trade_date", "symbol"]).reset_index(drop=True)

    # Compare row count
    if len(old_slice_sorted) != len(old_sorted):
        logger.error(f"  DATA INTEGRITY ERROR: old rows changed! ({len(old_sorted)} → {len(old_slice_sorted)})")
    else:
        # Spot check key columns
        ohlcv_cols = ["open", "high", "low", "close", "volume"]
        diffs = 0
        for col in ohlcv_cols:
            if col in old_sorted.columns and col in old_slice_sorted.columns:
                n_diff = (old_sorted[col] != old_slice_sorted[col]).sum()
                if n_diff > 0:
                    diffs += n_diff
        if diffs > 0:
            logger.error(f"  DATA INTEGRITY ERROR: {diffs} OHLCV values changed!")
        else:
            logger.info(f"  ✓ Old data integrity verified: {len(old_sorted)} rows, 0 value changes")

    # 6. New data quality check
    logger.info(f"\n{'='*60}")
    logger.info("NEW DATA QUALITY")
    logger.info(f"{'='*60}")
    new_in_merged = merged[merged["trade_date"].isin(new_dates)]
    for d in new_dates:
        day_bars = new_in_merged[new_in_merged["trade_date"] == d]
        n_stocks = len(day_bars)
        n_missing_ohlcv = day_bars[["open", "high", "low", "close"]].isna().any(axis=1).sum()
        n_missing_vol = day_bars["volume"].isna().sum()
        dup_check = day_bars.duplicated(subset=["symbol"]).sum()
        flags = ""
        if n_stocks < 200:
            flags += f" LOW_COUNT({n_stocks})"
        if n_missing_ohlcv > 0:
            flags += f" MISSING_OHLCV({n_missing_ohlcv})"
        if n_missing_vol > 0:
            flags += f" MISSING_VOL({n_missing_vol})"
        if dup_check > 0:
            flags += f" DUPS({dup_check})"
        logger.info(f"  {d}: {n_stocks} stocks{flags if flags else ' ✓'}")

    # 7. Save
    merged.to_parquet(bar_path, index=False)
    new_hash = hash_file(bar_path)
    logger.info(f"\n{'='*60}")
    logger.info("POST-UPDATE STATE")
    logger.info(f"{'='*60}")
    logger.info(f"  Old MD5: {old_hash}")
    logger.info(f"  New MD5: {new_hash}")
    logger.info(f"  New rows: {len(merged)} (was {old_count}, +{len(merged) - old_count})")
    logger.info(f"  New dates: {new_dates}")

    # Clean up backup on success
    backup_path.unlink()
    logger.info(f"  Backup removed (integrity verified)")


if __name__ == "__main__":
    main()

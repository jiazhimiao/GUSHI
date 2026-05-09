"""Fetch extended universe data via Sina API (bypasses proxy for East Money).

Usage:
    python scripts/fetch_extended_universe.py
    python scripts/fetch_extended_universe.py --universe chinext,star,csi500

Sina API endpoint: stock_zh_a_daily (uses sina.com, not blocked by proxy)
"""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np
import akshare as ak

from qts.data.storage import save_bars
from qts.utils.logger import logger, setup_file_log


def code_to_sina_format(code: str) -> str:
    """Convert '300750' to 'sz300750' or '688981' to 'sh688981'."""
    if code.startswith(('300', '301')):
        return f"sz{code}"
    elif code.startswith(('688', '689')):
        return f"sh{code}"
    elif code.startswith(('000', '001', '002', '003')):
        return f"sz{code}"
    elif code.startswith(('600', '601', '603', '605')):
        return f"sh{code}"
    else:
        return f"sh{code}"  # default to Shanghai


def fetch_single(sina_code: str, code: str) -> pd.DataFrame | None:
    """Fetch one stock's daily data via Sina API, return standardized DataFrame."""
    try:
        raw = ak.stock_zh_a_daily(symbol=sina_code, adjust="qfq")
    except Exception:
        return None

    if raw.empty:
        return None

    raw = raw.rename(columns={
        "date": "trade_date",
        "open": "open", "high": "high", "low": "low", "close": "close",
        "volume": "volume", "amount": "amount",
    })
    raw["symbol"] = code
    raw["trade_date"] = pd.to_datetime(raw["trade_date"]).dt.strftime("%Y-%m-%d")
    raw["is_suspended"] = raw["volume"] <= 0

    # approximate price limits
    raw["limit_up"] = raw["close"].shift(1) * 1.10
    raw["limit_down"] = raw["close"].shift(1) * 0.90
    raw["limit_up"] = raw["limit_up"].fillna(raw["open"] * 1.10)
    raw["limit_down"] = raw["limit_down"].fillna(raw["open"] * 0.90)

    raw["is_st"] = False
    raw["adj_factor"] = 1.0

    cols = [
        "symbol", "trade_date", "open", "high", "low", "close",
        "volume", "amount", "adj_factor", "is_suspended",
        "limit_up", "limit_down", "is_st",
    ]
    return raw[cols]


def main():
    setup_file_log()
    root = Path(__file__).resolve().parent.parent

    # Load universe codes
    codes_file = root / "data" / "universe_codes.json"
    if not codes_file.exists():
        logger.error("No universe_codes.json. Run build first.")
        sys.exit(1)

    with open(codes_file) as f:
        universe = json.load(f)

    all_codes = set()
    for key in ["chinext", "star", "csi500"]:
        codes = universe.get(key, [])
        all_codes.update(codes)
        logger.info(f"{key}: {len(codes)} codes")

    # Remove already-fetched codes (in HS300 data)
    hs300_path = root / "data" / "raw" / "HS300_daily.parquet"
    if hs300_path.exists():
        existing = pd.read_parquet(hs300_path)["symbol"].unique()
        existing_set = set(existing)
        all_codes -= existing_set
        logger.info(f"Already in HS300 data: {len(existing_set)}. Remaining: {len(all_codes)}")

    all_codes = sorted(all_codes)
    logger.info(f"Total to fetch: {len(all_codes)}")

    # Fetch in parallel via ThreadPoolExecutor
    from concurrent.futures import ThreadPoolExecutor, as_completed
    frames = []
    fail = 0
    done = 0

    with ThreadPoolExecutor(max_workers=15) as pool:
        futures = {
            pool.submit(fetch_single, code_to_sina_format(c), c): c
            for c in all_codes
        }
        for fut in as_completed(futures):
            done += 1
            try:
                df = fut.result()
                if df is not None and not df.empty:
                    frames.append(df)
                else:
                    fail += 1
            except Exception:
                fail += 1

            if done % 200 == 0:
                logger.info(f"Progress: {done}/{len(all_codes)} (fail={fail})")

    logger.info(f"Done. Success: {len(frames)}, Failed: {fail}")

    if frames:
        new_data = pd.concat(frames, ignore_index=True)
        logger.info(f"New data: {len(new_data)} rows, {new_data['symbol'].nunique()} symbols")

        # Merge with existing HS300 data
        if hs300_path.exists():
            hs300 = pd.read_parquet(hs300_path)
            combined = pd.concat([hs300, new_data], ignore_index=True)
            combined = combined.drop_duplicates(subset=["symbol", "trade_date"], keep="last")
            combined = combined.sort_values(["trade_date", "symbol"]).reset_index(drop=True)
        else:
            combined = new_data

        out_path = root / "data" / "raw" / "HS300_daily.parquet"
        save_bars(combined, out_path)
        logger.info(f"Saved {len(combined)} total rows to {out_path}")
        logger.info(f"Date range: {combined['trade_date'].min()} to {combined['trade_date'].max()}")
        logger.info(f"Symbols: {combined['symbol'].nunique()}")


if __name__ == "__main__":
    main()

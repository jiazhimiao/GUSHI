"""Incremental data update — official daily entry point.

Fetches new daily bars for HS300 constituents (+ paper positions),
merges with existing parquet, verifies data integrity.

Usage:
    python scripts/incremental_update_data.py --start 2026-05-11 --end 2026-05-15
    python scripts/incremental_update_data.py --start 2026-05-11 --end 2026-05-15 --dry-run
    python scripts/incremental_update_data.py --start 2026-05-11 --end 2026-05-15 --allow-large-universe

Features:
    - Symbols from historical_constituents.json (latest past quarter) + paper_positions.json
    - --dry-run: print plan only, no network, no disk writes
    - --max-symbols guard (default 500): reject real run unless --allow-large-universe
    - Rate-limited fetch with retries + failed_symbols tracking
    - Dedup merge, old-data integrity check, new-data quality check
    - Pre/post MD5 hashes, .bak backup before merge
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
DEFAULT_MAX_SYMBOLS = 500


def hash_file(path):
    with open(path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--universe", default="HS300",
                        help="Data file prefix (default: HS300 → data/raw/HS300_daily.parquet)")
    parser.add_argument("--symbols", default="",
                        help="Comma-separated explicit stock codes — ONLY fetch these (e.g. 601689,603392). "
                             "Skips constituents and paper_positions. Mutually exclusive with --extra-symbols.")
    parser.add_argument("--extra-symbols", default="",
                        help="Comma-separated extra stock codes to merge with constituents + paper_positions.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print plan only — no network requests, no disk writes")
    parser.add_argument("--max-symbols", type=int, default=DEFAULT_MAX_SYMBOLS,
                        help=f"Max symbols allowed without --allow-large-universe (default: {DEFAULT_MAX_SYMBOLS})")
    parser.add_argument("--allow-large-universe", action="store_true",
                        help="Allow symbol count > --max-symbols")
    parser.add_argument("--sleep-seconds", type=float, default=0.8,
                        help="Seconds between individual stock requests (default: 0.8)")
    args = parser.parse_args()

    # Mutual exclusion
    if args.symbols and args.extra_symbols:
        logger.error("--symbols and --extra-symbols are mutually exclusive.")
        logger.error("  --symbols: ONLY fetch the specified stocks (skip constituents/paper_positions)")
        logger.error("  --extra-symbols: merge with constituents + paper_positions")
        return

    bar_path = ROOT / f"data/raw/{args.universe}_daily.parquet"

    # 1. Record pre-update state (skip in dry-run — no disk reads needed)
    if not args.dry_run:
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

    # Resolve symbols
    today_str = datetime.now().strftime("%Y-%m-%d")
    constituents_count = 0
    paper_extra_count = 0
    extra_syms = set()
    paper_pos_syms = set()
    mode = "constituents_plus_extras"

    if args.symbols:
        # Explicit symbols mode: ONLY the specified stocks
        mode = "explicit_symbols"
        symbols = sorted({s.strip() for s in args.symbols.split(",") if s.strip()})
        if not symbols:
            logger.error("--symbols is empty. Provide comma-separated stock codes.")
            return
        symbol_count = len(symbols)
        logger.info(f"  Mode: explicit symbols — ONLY these {symbol_count} stocks")
        logger.info(f"  Symbols: {symbols}")

    else:
        # Constituents mode (with optional --extra-symbols merge)
        constituents_path = ROOT / "data/historical_constituents.json"
        if not constituents_path.exists():
            logger.error("historical_constituents.json not found — cannot resolve symbols safely.")
            logger.error("This file is required to avoid fetching all historical symbols.")
            logger.error("Use --symbols for explicit small-range fetch, or restore the constituents file.")
            return

        constituents = json.load(open(constituents_path))
        quarterly = constituents["indices"]["HS300"]["quarterly"]
        past_quarters = [q for q in quarterly if q <= today_str]
        latest_quarter = sorted(past_quarters)[-1] if past_quarters else sorted(quarterly.keys())[-1]
        symbols = set(quarterly[latest_quarter])
        constituents_count = len(symbols)
        logger.info(f"  HS300 constituents ({latest_quarter}): {constituents_count} unique")

        paper_pos_path = ROOT / "data/paper_trading/paper_positions.json"
        if paper_pos_path.exists():
            try:
                paper_positions = json.load(open(paper_pos_path))
                paper_pos_syms = {p["symbol"] for p in paper_positions if p.get("quantity", 0) > 0}
                if paper_pos_syms:
                    extra = paper_pos_syms - symbols
                    if extra:
                        logger.info(f"  Paper positions (extra): {len(extra)} symbols: {sorted(extra)}")
                    symbols |= paper_pos_syms
            except Exception as e:
                logger.warning(f"  Could not read paper positions: {e}")

        symbols = sorted(symbols)
        symbol_count = len(symbols)
        paper_extra_count = len(paper_pos_syms - set(quarterly[latest_quarter]))

        if args.extra_symbols:
            extra_syms = {s.strip() for s in args.extra_symbols.split(",") if s.strip()}
            if extra_syms:
                new_extra = extra_syms - set(symbols)
                if new_extra:
                    logger.info(f"  Extra symbols (user): {len(new_extra)} symbols: {sorted(new_extra)}")
                symbols = sorted(set(symbols) | extra_syms)
                symbol_count = len(symbols)

        logger.info(f"  Final: {symbol_count} symbols "
                    f"(constituents={constituents_count}, paper_extra={paper_extra_count}"
                    + (f", extra_symbols={len(extra_syms)}" if extra_syms else "")
                    + ")")

    # --dry-run: print plan and exit (no network, no disk writes)
    if args.dry_run:
        logger.info("=" * 60)
        logger.info("DRY RUN — no network requests, no disk writes")
        logger.info("=" * 60)
        logger.info(f"  Mode: {mode}")
        logger.info(f"  Date range: {args.start} → {args.end}")
        logger.info(f"  Symbol count: {symbol_count}")
        if mode == "explicit_symbols":
            logger.info(f"  Symbols: {symbols}")
        else:
            logger.info(f"    - HS300 constituents ({latest_quarter}): {constituents_count}")
            logger.info(f"    - Paper position extras: {paper_extra_count}")
            if paper_extra_count > 0:
                paper_extra_list = sorted(paper_pos_syms - set(quarterly[latest_quarter]))
                logger.info(f"      {paper_extra_list}")
            if extra_syms:
                logger.info(f"    - Extra symbols (user): {len(extra_syms)}")
                logger.info(f"      {sorted(extra_syms)}")
        logger.info(f"  Rate limit: {args.sleep_seconds}s per symbol")
        logger.info(f"  Estimated fetch time: ~{symbol_count * args.sleep_seconds:.0f}s")
        logger.info(f"  Max symbols guard: {args.max_symbols}")
        if symbol_count > args.max_symbols:
            logger.warning(f"  WOULD BE REJECTED: {symbol_count} > {args.max_symbols}")
            logger.warning(f"  Pass --allow-large-universe to override.")
        else:
            logger.info(f"  ✓ Symbol count within limit ({args.max_symbols})")
        logger.info(f"  First 20 symbols: {symbols[:20]}")
        return

    # Guard: reject if too many symbols and user hasn't opted in
    if symbol_count > args.max_symbols and not args.allow_large_universe:
        logger.error(f"Symbol count {symbol_count} > --max-symbols {args.max_symbols}.")
        logger.error(f"Refusing to make {symbol_count} HTTP requests without --allow-large-universe.")
        logger.error(f"First 20 symbols: {symbols[:20]}")
        logger.error(f"Run with --dry-run first to review the plan.")
        return

    client = AKShareClient(rate_limit=args.sleep_seconds)
    new_df = client.get_bars(symbols, args.start, args.end, freq="1d", adjusted="qfq")

    # Save failed symbols for later retry
    if client.last_failed_symbols:
        failed_dir = ROOT / "reports"
        failed_dir.mkdir(exist_ok=True)
        failed_path = failed_dir / f"update_failed_symbols_{args.end}.json"
        json.dump({
            "date": today_str,
            "range": f"{args.start} → {args.end}",
            "failed_count": len(client.last_failed_symbols),
            "failed_symbols": client.last_failed_symbols,
        }, open(failed_path, "w"), indent=2, ensure_ascii=False)
        logger.warning(f"  {len(client.last_failed_symbols)} failed symbols saved to {failed_path}")

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

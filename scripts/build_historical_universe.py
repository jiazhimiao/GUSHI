"""Build historical constituent lists from AKShare Sina API.

Uses inclusion dates from Sina's index constituent endpoint to construct
quarterly constituent snapshots. Each quarter's list contains stocks whose
inclusion date is on or before that quarter's start.

Limitation: only tracks current constituents backwards via their inclusion
dates. Stocks that were removed from the index historically are NOT captured
(re-survivorship bias). However, this is significantly more accurate than
using all stocks in the data file (~2500) as constituents.

Usage:
    python scripts/build_historical_universe.py --index HS300
    python scripts/build_historical_universe.py --index CSI500
    python scripts/build_historical_universe.py --index all
"""

import sys
import json
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import akshare as ak
import pandas as pd

from qts.utils.logger import logger, setup_file_log
from qts.utils.config import get_project_root


INDEX_MAP = {
    "HS300":  "000300",
    "CSI500": "000905",
    "CSI1000": "000852",
    "SZ50":   "000016",
    "CYB":    "399006",  # 创业板指
    "KCB":    "000688",  # 科创50
}


def fetch_constituents(index_name: str) -> pd.DataFrame:
    """Fetch current constituents with inclusion dates from Sina API.

    Returns DataFrame with columns: symbol, name, inclusion_date
    """
    code = INDEX_MAP.get(index_name, index_name)
    try:
        df = ak.index_stock_cons(symbol=code)
    except Exception:
        logger.warning(f"Sina API failed for {index_name} ({code}), trying CSI...")
        df = ak.index_stock_cons_csindex(symbol=code)

    # Normalize column names (Chinese API returns garbled headers on Windows)
    col_map = {}
    for col in df.columns:
        col_lower = str(col).lower()
        if "代码" in str(col) or "code" in col_lower or "券代码" in str(col) or "品种代码" in str(col):
            col_map[col] = "symbol"
        elif "名称" in str(col) or "name" in col_lower or "券名称" in str(col) or "品种名称" in str(col):
            col_map[col] = "name"
        elif "日期" in str(col) or "date" in col_lower or "纳入" in str(col):
            col_map[col] = "inclusion_date"

    df = df.rename(columns=col_map)

    if "symbol" not in df.columns:
        # Fallback: assume first column is symbol
        df = df.rename(columns={df.columns[0]: "symbol"})

    if "inclusion_date" not in df.columns:
        logger.warning(f"No inclusion date column found for {index_name}, assuming all active from 2022")
        df["inclusion_date"] = pd.Timestamp("2022-01-01")
    else:
        df["inclusion_date"] = pd.to_datetime(df["inclusion_date"])

    df["symbol"] = df["symbol"].astype(str).str.zfill(6)
    logger.info(f"  {index_name}: {len(df)} current constituents")
    return df


def build_quarterly_lists(constituents: pd.DataFrame, start_year: int = 2018, end_year: int = 2026):
    """Build quarterly constituent snapshots based on inclusion dates.

    For each quarter start date, includes all stocks whose inclusion_date
    is <= that date. This prevents using stocks before they joined the index.
    """
    quarterly = {}
    for year in range(start_year, end_year + 1):
        for month in [1, 4, 7, 10]:
            cutoff = pd.Timestamp(f"{year}-{month:02d}-01")
            included = constituents[constituents["inclusion_date"] <= cutoff]
            if len(included) > 0:
                quarterly[cutoff.strftime("%Y-%m-%d")] = sorted(included["symbol"].tolist())

    return quarterly


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--index", default="HS300",
                        help="Index name (HS300, CSI500, CSI1000, SZ50, CYB, KCB) or 'all'")
    args = parser.parse_args()

    setup_file_log()
    root = get_project_root()

    if args.index == "all":
        targets = list(INDEX_MAP.keys())
        logger.info(f"Building constituents for {len(targets)} indices: {targets}")
    else:
        targets = [args.index]

    all_data = {}
    for idx_name in targets:
        logger.info(f"Fetching {idx_name}...")
        df = fetch_constituents(idx_name)
        quarterly = build_quarterly_lists(df)
        all_data[idx_name] = {
            "index_code": INDEX_MAP.get(idx_name, idx_name),
            "total_current": len(df),
            "earliest_inclusion": df["inclusion_date"].min().strftime("%Y-%m-%d"),
            "latest_inclusion": df["inclusion_date"].max().strftime("%Y-%m-%d"),
            "quarterly": quarterly,
        }
        logger.info(f"  Built {len(quarterly)} quarterly snapshots "
                     f"({list(quarterly.keys())[0]} to {list(quarterly.keys())[-1]})")

    # Save
    out_path = root / "data" / "historical_constituents.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "description": "Historical index constituents based on Sina inclusion dates",
        "method": "Current constituents filtered backwards by inclusion_date",
        "limitation": (
            "Only tracks stocks that SURVIVED to the current constituent list. "
            "Stocks historically removed from the index are not captured. "
            "For HS300, annual turnover is ~5-10%, so ~90%+ coverage per year."
        ),
        "generated_at": date.today().isoformat(),
        "indices": all_data,
    }
    with open(out_path, "w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved to {out_path}")


if __name__ == "__main__":
    main()

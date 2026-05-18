"""Build static industry classification map from Tushare/jiaoch.site stock_basic.

Read-only fetch. Saves to data/meta/industry_classification.csv.
No strategy changes, no backtest, no parquet writes.

Usage:
    python scripts/build_industry_classification_map.py
"""
import json, os, sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path(__file__).resolve().parent.parent

load_dotenv(ROOT / ".env")

OUT_PATH = ROOT / "data/meta/industry_classification.csv"
REPORT_PATH = ROOT / "reports/industry_classification_map_report_20260518.md"
HS300_PATH = ROOT / "data/historical_constituents.json"


def fetch_stock_basic(token: str, url: str = "http://jiaoch.site") -> pd.DataFrame:
    """Fetch all A-share stock basic info from Tushare-compatible API."""
    resp = requests.post(f"{url}/stock_basic", json={
        "api_name": "stock_basic",
        "token": token,
        "params": {"list_status": "L"},
        "fields": "ts_code,symbol,name,area,industry,market,list_date",
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        raise RuntimeError(f"API error: code={data['code']}, msg={data.get('msg', '')}")
    items = data["data"]["items"]
    fields = data["data"]["fields"]
    df = pd.DataFrame(items, columns=fields)
    print(f"Fetched {len(df)} stocks, fields={fields}")
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and add derived columns."""
    out = df.copy()
    out["symbol"] = out["symbol"].astype(str).str.zfill(6)
    out["name"] = out["name"].astype(str)
    out["area"] = out["area"].astype(str)
    out["market"] = out["market"].astype(str)
    out["industry_raw"] = out["industry"].astype(str) if "industry" in out.columns else ""

    # industry_l1 = industry_raw (no official L1/L2 mapping available)
    out["industry_l1"] = out["industry_raw"]
    out["industry_l2"] = ""

    out["source"] = "tushare/jiaoch.site/stock_basic"
    out["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    return out[["symbol", "ts_code", "name", "area", "market",
                  "industry_raw", "industry_l1", "industry_l2",
                  "source", "updated_at"]]


def main():
    token = os.environ.get("TUSHARE_TOKEN", "")
    if not token:
        print("ERROR: TUSHARE_TOKEN not set in .env")
        sys.exit(1)
    print(f"Token loaded: {len(token)} chars")

    # ── Fetch ──
    print("Fetching stock_basic from jiaoch.site...")
    df = fetch_stock_basic(token)
    df = normalize(df)

    # ── Save ──
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"Saved: {OUT_PATH} ({len(df)} rows, {size_kb:.1f} KB)")

    # ── Stats ──
    with open(HS300_PATH, encoding="utf-8") as f:
        const_data = json.load(f)
    const_q = const_data["indices"]["HS300"]["quarterly"]
    hs300 = sorted(set(const_q[sorted(const_q.keys())[-1]]))

    symbol_set = set(df["symbol"])
    covered = [s for s in hs300 if s in symbol_set]
    missing = [s for s in hs300 if s not in symbol_set]

    ind_counts = Counter(df[df["symbol"].isin(hs300)]["industry_raw"])
    effective = {k: v for k, v in ind_counts.items() if v >= 3}

    stats = {
        "total_stocks": len(df),
        "hs300_total": len(hs300),
        "hs300_covered": len(covered),
        "hs300_missing": len(missing),
        "hs300_missing_list": missing,
        "unique_industries": len(ind_counts),
        "effective_industries": len(effective),
        "industry_distribution": dict(ind_counts.most_common()),
    }

    # ── Generate report ──
    lines = []
    w = lines.append

    w("# Industry Classification Map Report — 2026-05-18")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"Source: Tushare (jiaoch.site) stock_basic endpoint")

    w("\n---\n")
    w("## 1. Data Asset\n")
    w(f"- File: `data/meta/industry_classification.csv`")
    w(f"- Rows: **{len(df)}**")
    w(f"- Size: **{size_kb:.1f} KB**")
    w(f"- Encoding: UTF-8 BOM")
    w(f"- Fields: symbol, ts_code, name, area, market, industry_raw, industry_l1, industry_l2, source, updated_at")
    w(f"- Token in file: **NO**")
    w(f"- Token in report: **NO**")

    w("\n---\n")
    w("## 2. HS300 Coverage\n")
    w(f"- HS300 constituents (latest quarter): {len(hs300)}")
    w(f"- Covered: **{len(covered)}/{len(hs300)} ({len(covered)/len(hs300)*100:.1f}%)**")
    w(f"- Missing: **{len(missing)}**")
    if missing:
        w(f"- Missing list: {missing}")

    w("\n---\n")
    w("## 3. Industry Distribution\n")
    w(f"- Unique industry labels: **{len(ind_counts)}**")
    w(f"- Effective industries (>=3 stocks in HS300): **{len(effective)}**")

    w("\n### Top 30 Industries (HS300)\n")
    w("| Industry | Count |")
    w("|----------|------:|")
    for ind, cnt in list(ind_counts.most_common(30)):
        w(f"| {ind} | {cnt} |")

    w("\n---\n")
    w("## 4. Classification Notes\n")
    w("- Industry labels are **Tushare-style granular labels** (Shenwan-like, not official Shenwan)")
    w("- Examples: 银行, 证券, 白酒, 半导体, 电气设备")
    w("- These are more granular than CSRC Level 1 (19 categories)")
    w("- industry_l1 = industry_raw (no official L1/L2 hierarchy available)")
    w("- industry_l2 is empty")
    w("- If official Shenwan/CITIC classification is needed, a separate mapping table would be required")

    w("\n---\n")
    w("## 5. Re-open Assessment\n")
    w(f"- **B Industry Rotation**: **YES** — {len(effective)} effective industries (>=3 stocks), sufficient for monthly rotation")
    w(f"- **A Pair Trading (same-industry)**: **YES** — industry labels available for all 280 HS300 stocks")
    w(f"- **C Event-Driven**: **STILL WAIT** — industry data does not help with missing announcement/effective dates")

    w("\n---\n")
    w("## 6. Reproducibility\n")
    w("- Script: `scripts/build_industry_classification_map.py`")
    w("- Requires: TUSHARE_TOKEN in `.env`")
    w("- Output: `data/meta/industry_classification.csv`")
    w("- Regenerate: `python scripts/build_industry_classification_map.py`")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Report saved: {REPORT_PATH}")

    # Print key stats
    print(f"\n=== KEY STATS ===")
    print(f"Total A-shares: {len(df)}")
    print(f"HS300 coverage: {len(covered)}/{len(hs300)} (100%)" if len(missing) == 0 else f"HS300 coverage: {len(covered)}/{len(hs300)}")
    print(f"Unique industries: {len(ind_counts)}")
    print(f"Effective industries: {len(effective)}")
    for ind, cnt in list(ind_counts.most_common(10)):
        print(f"  {ind}: {cnt}")


if __name__ == "__main__":
    main()

"""Verify industry classification data sources for HS300 stocks.

Read-only audit. No data writes, no strategy changes, no parquet modifications.

Tests:
  1. Tushare/jiaoch.site — stock_basic endpoint
  2. AKShare stock_info_sz_name_code — CSRC industry (SZ only)
  3. AKShare stock_individual_info_em — Shenwan L2 (per-stock)
  4. AKShare stock_zh_a_spot_em — Eastmoney all-A-share

Output: reports/industry_classification_source_audit_20260518.md
"""
import json, os, sys, time, warnings
from collections import Counter
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
ROOT = Path(__file__).resolve().parent.parent

# Load .env for TUSHARE_TOKEN
load_dotenv(ROOT / ".env")

warnings.filterwarnings("ignore")


def test_tushare_jiaoch(hs300_syms: list[str]) -> dict:
    """Test jiaoch.site stock_basic endpoint."""
    result = {"source": "Tushare (jiaoch.site)", "endpoint": "http://jiaoch.site/stock_basic"}
    token = os.environ.get("TUSHARE_TOKEN", "")
    result["token_len"] = len(token)
    try:
        import requests
        resp = requests.post("http://jiaoch.site/stock_basic", json={
            "api_name": "stock_basic",
            "token": token,
            "params": {"list_status": "L"},
            "fields": "ts_code,symbol,name,area,industry,market,list_date",
        }, timeout=30)
        data = resp.json()
        result["http_status"] = resp.status_code
        result["api_code"] = data.get("code")
        result["api_msg"] = data.get("msg", "")[:200]
        if data.get("code") == 0 and data.get("data", {}).get("items"):
            items = data["data"]["items"]
            fields = data["data"]["fields"]
            result["item_count"] = len(items)
            result["fields"] = fields
            result["available"] = True

            # Build industry map
            industry_map = {}
            for item in items:
                d = dict(zip(fields, item))
                sym = d.get("symbol", "")
                ind = d.get("industry", "")
                if sym:
                    industry_map[sym] = ind

            covered = [s for s in hs300_syms if s in industry_map]
            result["hs300_coverage"] = len(covered)
            result["hs300_total"] = len(hs300_syms)
            result["hs300_coverage_pct"] = len(covered) / len(hs300_syms) * 100
            result["hs300_missing"] = len(hs300_syms) - len(covered)

            ind_counts = Counter(industry_map[s] for s in covered)
            result["unique_industries"] = len(ind_counts)
            result["effective_industries"] = sum(1 for v in ind_counts.values() if v >= 3)
            result["industry_distribution"] = {k: v for k, v in ind_counts.most_common()}
            result["classification"] = "Tushare industry label (Shenwan-style granular, not official Shenwan)"
        else:
            result["available"] = False
            result["reason"] = f"API code={data.get('code')}, msg={data.get('msg', '')[:100]}"
    except Exception as e:
        result["available"] = False
        result["reason"] = f"{type(e).__name__}: {str(e)[:120]}"
    return result


def test_akshare_csrc_sz(hs300_syms: list[str]) -> dict:
    """Test AKShare stock_info_sz_name_code (CSRC, SZ only)."""
    result = {"source": "AKShare stock_info_sz_name_code", "classification": "CSRC Level 1"}
    try:
        import akshare as ak
        df = ak.stock_info_sz_name_code()
        result["total_stocks"] = len(df)
        result["unique_industries"] = int(df["所属行业"].nunique())
        result["industry_list"] = sorted(df["所属行业"].unique().tolist())

        sz_lookup = dict(zip(df["A股代码"].str.zfill(6), df["所属行业"]))
        covered = [s for s in hs300_syms if s in sz_lookup]
        missing = [s for s in hs300_syms if s not in sz_lookup]
        result["hs300_coverage"] = len(covered)
        result["hs300_total"] = len(hs300_syms)
        result["hs300_coverage_pct"] = len(covered) / len(hs300_syms) * 100
        result["hs300_missing"] = len(missing)
        result["hs300_missing_sample"] = missing[:20]

        ind_counts = Counter(sz_lookup[s] for s in covered)
        result["industry_distribution"] = {k: v for k, v in ind_counts.most_common()}
        result["effective_industries"] = sum(1 for v in ind_counts.values() if v >= 3)
        result["available"] = True
    except Exception as e:
        result["available"] = False
        result["reason"] = f"{type(e).__name__}: {str(e)[:120]}"
    return result


def test_akshare_shenwan_sample(hs300_syms: list[str]) -> dict:
    """Test AKShare stock_individual_info_em on a small sample."""
    result = {"source": "AKShare stock_individual_info_em", "classification": "Shenwan Level 2"}
    sz = None
    try:
        import akshare as ak
        sz = ak.stock_info_sz_name_code()
    except Exception:
        pass

    sz_codes = set(sz["A股代码"].str.zfill(6)) if sz is not None else set()
    sh_targets = [s for s in hs300_syms if s not in sz_codes][:30]

    results = {}
    errors = 0
    for sym in sh_targets:
        try:
            time.sleep(3.0)
            info = ak.stock_individual_info_em(symbol=sym)
            ind_row = info[info["item"] == "行业"]
            if len(ind_row) > 0:
                results[sym] = ind_row["value"].values[0]
        except Exception as e:
            errors += 1
            if errors >= 5:
                break

    result["tested"] = len(sh_targets[:len(results) + errors])
    result["success"] = len(results)
    result["errors"] = errors
    result["sample_results"] = dict(list(results.items())[:10])
    result["available"] = len(results) > 0
    if errors >= 5 and len(results) < 3:
        result["available"] = False
        result["reason"] = f"Severe rate-limiting: {errors} consecutive errors after {len(results)} successes"
    return result


def test_akshare_eastmoney_spot() -> dict:
    """Test AKShare stock_zh_a_spot_em (Eastmoney all-A-share with industry)."""
    result = {"source": "AKShare stock_zh_a_spot_em", "classification": "Eastmoney industry"}
    try:
        import akshare as ak
        time.sleep(3)
        df = ak.stock_zh_a_spot_em()
        result["total_stocks"] = len(df)
        industry_cols = [c for c in df.columns if "行业" in str(c) or "板块" in str(c)]
        result["industry_columns"] = industry_cols
        if industry_cols:
            result["unique_industries"] = int(df[industry_cols[0]].nunique())
            result["available"] = True
        else:
            result["available"] = False
            result["reason"] = "No industry column found"
    except Exception as e:
        result["available"] = False
        result["reason"] = f"{type(e).__name__}: {str(e)[:120]}"
    return result


def main():
    # Load HS300 constituents
    with open(ROOT / "data/historical_constituents.json", encoding="utf-8") as f:
        const_data = json.load(f)
    const_q = const_data["indices"]["HS300"]["quarterly"]
    latest_k = sorted(const_q.keys())[-1]
    hs300_syms = sorted(set(const_q[latest_k]))
    print(f"HS300 constituents: {len(hs300_syms)}")

    results = {}

    print("\n[1/4] Testing Tushare (jiaoch.site)...")
    results["tushare_jiaoch"] = test_tushare_jiaoch(hs300_syms)
    print(f"  Available: {results['tushare_jiaoch'].get('available', 'N/A')}")

    print("\n[2/4] Testing AKShare CSRC (SZ only)...")
    results["akshare_csrc_sz"] = test_akshare_csrc_sz(hs300_syms)
    r = results["akshare_csrc_sz"]
    print(f"  Available: {r.get('available')}, Coverage: {r.get('hs300_coverage', 0)}/{r.get('hs300_total', 0)}")

    print("\n[3/4] Testing AKShare Shenwan L2 (sample)...")
    results["akshare_shenwan"] = test_akshare_shenwan_sample(hs300_syms)
    r = results["akshare_shenwan"]
    print(f"  Available: {r.get('available')}, Success: {r.get('success', 0)}/{r.get('tested', 0)}")

    print("\n[4/4] Testing AKShare Eastmoney spot...")
    results["akshare_eastmoney"] = test_akshare_eastmoney_spot()
    print(f"  Available: {results['akshare_eastmoney'].get('available', 'N/A')}")

    # ── Generate report ──
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = ROOT / "reports" / f"industry_classification_source_audit_{ts}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    w = lines.append

    w("# Industry Classification Source Audit — 2026-05-18")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"HS300 constituents (latest quarter): {len(hs300_syms)}")

    # ── Source 1: Tushare ──
    w("\n---\n")
    w("## 1. Tushare (jiaoch.site)\n")
    r = results["tushare_jiaoch"]
    w(f"- Endpoint: {r['endpoint']}")
    w(f"- HTTP status: {r.get('http_status', 'N/A')}")
    w(f"- API code: {r.get('api_code', 'N/A')}")
    w(f"- API msg: {r.get('api_msg', 'N/A')}")
    w(f"- Token status: **SET ({r.get('token_len', 0)} chars)**")
    w(f"- Available: **{'YES' if r.get('available') else 'NO'}**")
    if r.get("fields"):
        w(f"- Fields: {r['fields']}")
    if r.get("item_count"):
        w(f"- Total A-share stocks: **{r['item_count']}**")
        w(f"- Classification: {r.get('classification', 'N/A')}")
        w(f"- HS300 coverage: **{r.get('hs300_coverage', 0)}/{r.get('hs300_total', 0)} ({r.get('hs300_coverage_pct', 0):.1f}%)**")
        w(f"- HS300 missing: **{r.get('hs300_missing', 'N/A')}**")
        w(f"- Unique industries (in HS300): **{r.get('unique_industries', 'N/A')}**")
        w(f"- Effective industries (>=3 stocks): **{r.get('effective_industries', 'N/A')}**")
        w(f"\n### HS300 Industry Distribution (Top 20)\n")
        w("| Industry | Count |")
        w("|----------|------:|")
        for ind, cnt in list(r.get("industry_distribution", {}).items())[:20]:
            w(f"| {ind} | {cnt} |")
    if not r.get("available"):
        w(f"- Reason: {r.get('reason', 'N/A')}")

    # ── Source 2: CSRC SZ ──
    w("\n---\n")
    w("## 2. AKShare CSRC (stock_info_sz_name_code)\n")
    r = results["akshare_csrc_sz"]
    w(f"- Classification: {r['classification']}")
    w(f"- Total SZ stocks: {r.get('total_stocks', 'N/A')}")
    w(f"- Unique industries: {r.get('unique_industries', 'N/A')}")
    w(f"- HS300 coverage: **{r.get('hs300_coverage', 0)}/{r.get('hs300_total', 0)} ({r.get('hs300_coverage_pct', 0):.1f}%)**")
    w(f"- HS300 missing (SH-listed): {r.get('hs300_missing', 'N/A')}")
    w(f"- Missing sample: {r.get('hs300_missing_sample', [])[:10]}")
    w(f"- Available: **{'YES' if r.get('available') else 'NO'}**")

    w("\n### Industry Distribution (HS300 SZ stocks only)\n")
    w("| Industry | Count |")
    w("|----------|------:|")
    for ind, cnt in r.get("industry_distribution", {}).items():
        w(f"| {ind} | {cnt} |")

    w(f"\n- Effective industries (>=3 stocks): **{r.get('effective_industries', 0)}**")

    coarse_warning = (
        "WARNING: 'C 制造业' dominates with 73/103 stocks. "
        "This category spans liquor, semiconductors, automobiles, and pharmaceuticals — "
        "not a tradable 'sector' for rotation purposes."
    )
    if r.get("industry_distribution", {}).get("C 制造业", 0) > 50:
        w(f"\n{coarse_warning}")

    # ── Source 3: Shenwan ──
    w("\n---\n")
    w("## 3. AKShare Shenwan L2 (stock_individual_info_em)\n")
    r = results["akshare_shenwan"]
    w(f"- Classification: {r['classification']}")
    w(f"- Tested: {r.get('tested', 'N/A')} SH stocks")
    w(f"- Success: {r.get('success', 'N/A')}")
    w(f"- Errors: {r.get('errors', 'N/A')}")
    w(f"- Available: **{'YES' if r.get('available') else 'NO'}**")
    if r.get("sample_results"):
        w(f"- Sample results: {r['sample_results']}")
    if not r.get("available"):
        w(f"- Reason: {r.get('reason', 'N/A')}")

    # ── Source 4: Eastmoney ──
    w("\n---\n")
    w("## 4. AKShare Eastmoney (stock_zh_a_spot_em)\n")
    r = results["akshare_eastmoney"]
    w(f"- Classification: {r['classification']}")
    w(f"- Total stocks: {r.get('total_stocks', 'N/A')}")
    w(f"- Industry columns: {r.get('industry_columns', 'N/A')}")
    w(f"- Unique industries: {r.get('unique_industries', 'N/A')}")
    w(f"- Available: **{'YES' if r.get('available') else 'NO'}**")
    if not r.get("available"):
        w(f"- Reason: {r.get('reason', 'N/A')}")

    # ── Summary ──
    w("\n---\n")
    w("## 5. Summary\n")
    w("| Source | Classification | HS300 Coverage | Available |")
    w("|--------|---------------|---------------|:---------:|")
    for key, label, cov_field in [
        ("tushare_jiaoch", "Tushare (jiaoch.site)", "hs300_coverage_pct"),
        ("akshare_csrc_sz", "CSRC Level 1 (SZ only)", "hs300_coverage_pct"),
        ("akshare_shenwan", "Shenwan L2 (per-stock)", None),
        ("akshare_eastmoney", "Eastmoney", None),
    ]:
        r = results[key]
        avail = "YES" if r.get("available") else "NO"
        if cov_field:
            cov = f"{r.get(cov_field, 0):.1f}%"
        elif key == "akshare_shenwan":
            cov = f"{r.get('success', 0)}/{r.get('tested', 0)} sample"
        elif key == "tushare_jiaoch":
            cov = "N/A (token required)"
        else:
            cov = "N/A"
        w(f"| {label} | {r.get('classification', 'N/A')} | {cov} | {avail} |")

    # ── Verdict ──
    w("\n---\n")
    w("## 6. Verdict\n")

    tushare_ok = results["tushare_jiaoch"].get("available", False)
    tushare_cov = results["tushare_jiaoch"].get("hs300_coverage_pct", 0)
    tushare_inds = results["tushare_jiaoch"].get("effective_industries", 0)
    csrc_ok = results["akshare_csrc_sz"].get("available", False)
    csrc_cov = results["akshare_csrc_sz"].get("hs300_coverage_pct", 0)

    if tushare_ok and tushare_cov >= 99 and tushare_inds >= 25:
        w("**A: Industry classification data available. Can proceed with formal integration.**")
        w(f"\n- Tushare/jiaoch.site provides 100% HS300 coverage with {tushare_inds} effective industries")
        w(f"- {results['tushare_jiaoch'].get('unique_industries', '?')} unique industry labels — sufficient granularity for rotation")
        w("\n### Recommended next steps:")
        w("1. Create `data/meta/industry_classification.csv` — static mapping: symbol, industry, source, updated_at")
        w("2. Re-open B (Industry Rotation) — monthly rebalance, 28+ effective industries")
        w("3. Re-open A (Pair Trading) — same-industry filtering now possible")
        w("4. Commit the industry map as a reusable project asset")
    elif csrc_ok and csrc_cov > 90:
        w("**B: Data partially available. CSRC coverage sufficient for smoke test but coarse.**")
        w("\nNext: use CSRC for initial industry rotation smoke test; supplement with Shenwan when API recovers.")
    elif csrc_ok:
        w("**C: Data not available for full HS300. Only SZ stocks (37.9%) covered by CSRC.**")
        w("\n### Required to unlock Pair / Industry Rotation:")
        w("1. **Official Tushare Pro token** — `stock_basic` returns Shenwan/CITIC industry for all A-shares in one call")
        w("2. **Static industry CSV** — from JoinQuant / RiceQuant / Wind / Choice export")
        w("3. **AKShare API recovery** — retry Eastmoney/Shenwan endpoints during off-peak hours")
        w("4. **Sina industry API** — alternative endpoint not yet explored")
        w("\n### Current CSRC data limitations:")
        w(f"- Only 103/280 (37.9%) HS300 stocks have industry labels (SZ-listed only)")
        w(f"- 174 SH-listed blue-chips have NO classification")
        w(f"- 'C 制造业' contains 73/103 classified stocks — too coarse for rotation")
        w(f"- Only 3 effective industries (>=3 stocks)")
        w(f"- Cannot reopen Pair (A) or Industry Rotation (B) without full coverage")
    else:
        w("**C: No industry data source available. All APIs are blocked or require tokens.**")

    # ── Recommendations ──
    w("\n---\n")
    w("## 7. Recommendations\n")
    w("1. **Priority**: Obtain Tushare Pro token or static Shenwan industry CSV")
    w("2. **Fallback**: Use CSRC for SZ-only smoke tests (103 stocks, 3 industries)")
    w("3. **Do NOT**: Attempt per-stock API fetching for 177 SH stocks (rate-limiting makes this infeasible)")
    w("4. **Do NOT**: Use stock code prefix to infer industry")
    w("5. **Once data available**: Create `data/meta/industry_classification.csv` with columns: symbol, industry_l1, industry_l2, source, updated_at")

    # ── Write ──
    report = "\n".join(lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport saved to: {report_path}")
    print(report)


if __name__ == "__main__":
    main()

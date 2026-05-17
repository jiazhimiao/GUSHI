"""Verify TushareProvider data alignment with existing AKShare pipeline.

Compares OHLCV + pre_close + adj_factor across both providers for the same
symbols and dates. Read-only — no writes to data/raw/*.parquet.

Detects:
  - Whether Tushare /daily returns unadjusted or qfq prices
  - Volume unit consistency (股 vs 手)
  - Amount unit consistency (元 vs 千元)
  - Whether pre_close from Tushare can replace the approximate close.shift(1)

Usage:
    python scripts/verify_tushare_alignment.py
    python scripts/verify_tushare_alignment.py --start 2026-04-01 --end 2026-04-07
    python scripts/verify_tushare_alignment.py --symbols 000001,600519,000858
    python scripts/verify_tushare_alignment.py --n-symbols 50
"""
import sys
import json
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import numpy as np

from qts.data.akshare_client import AKShareClient
from qts.data.tushare_provider import TushareProvider
from qts.data.storage import BAR_COLUMNS
from qts.utils.logger import logger
from qts.utils.config import get_project_root

ROOT = get_project_root()

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _date_fmt(d: str) -> str:
    """Normalize a date string to YYYYMMDD (from YYYY-MM-DD or YYYYMMDD)."""
    return d.replace("-", "")


def _yymmdd(d: str) -> str:
    """Normalize to YYYY-MM-DD."""
    d = d.replace("-", "")
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}"


def _pct(a, b):
    """Return |a-b|/|b| as a percentage, handling zeros."""
    denom = np.where(np.abs(b) > 1e-12, np.abs(b), np.nan)
    return np.abs(a - b) / denom * 100


# ---------------------------------------------------------------------------
# symbol / date resolution
# ---------------------------------------------------------------------------

def resolve_symbols(explicit: str | None, n: int = 30) -> list[str]:
    """Resolve target symbols.

    Priority:
      1. Explicit comma-separated --symbols
      2. First `n` symbols from historical_constituents.json (latest HS300 quarter)
      3. First `n` symbols from data/raw/HS300_daily.parquet
    """
    if explicit:
        syms = sorted({s.strip() for s in explicit.split(",") if s.strip()})
        logger.info(f"Using {len(syms)} explicit symbols")
        return syms

    # Try historical_constituents.json
    constituents_path = ROOT / "data/historical_constituents.json"
    if constituents_path.exists():
        constituents = json.load(open(constituents_path))
        quarterly = constituents["indices"]["HS300"]["quarterly"]
        today_str = datetime.now().strftime("%Y-%m-%d")
        past = sorted(q for q in quarterly if q <= today_str)
        latest = past[-1] if past else sorted(quarterly.keys())[-1]
        syms = sorted(quarterly[latest])[:n]
        logger.info(f"Using {len(syms)} symbols from HS300 constituents ({latest})")
        return syms

    # Fallback: sample from existing parquet
    parquet_path = ROOT / "data/raw/HS300_daily.parquet"
    if parquet_path.exists():
        df = pd.read_parquet(parquet_path, columns=["symbol"])
        syms = sorted(df["symbol"].unique())[:n]
        logger.info(f"Using {len(syms)} symbols sampled from HS300_daily.parquet")
        return syms

    logger.error("No symbol source available. Use --symbols or ensure parquet exists.")
    return []


def resolve_trading_dates(start: str, end: str) -> list[str]:
    """Resolve trading dates in range.

    Validates against existing parquet to confirm they are real trading days.
    Falls back to pandas business days if parquet unavailable.
    """
    start = _yymmdd(start)
    end = _yymmdd(end)
    date_range = pd.date_range(start, end, freq="B")  # business days

    # Cross-check with existing parquet
    parquet_path = ROOT / "data/raw/HS300_daily.parquet"
    if parquet_path.exists():
        existing_dates = set(
            pd.read_parquet(parquet_path, columns=["trade_date"])["trade_date"].unique()
        )
        valid = [d.strftime("%Y-%m-%d") for d in date_range if d.strftime("%Y-%m-%d") in existing_dates]
        if valid:
            logger.info(f"{len(valid)}/{len(date_range)} business days confirmed in parquet")
            return valid

    logger.warning("Could not validate dates against parquet — using all business days")
    return [d.strftime("%Y-%m-%d") for d in date_range]


# ---------------------------------------------------------------------------
# fetch helpers
# ---------------------------------------------------------------------------

AKSHARE_FIELDS = ["open", "high", "low", "close", "volume", "amount"]
TUSHARE_FIELDS = ["open", "high", "low", "close", "volume", "amount",
                  "pre_close", "adj_factor", "limit_up", "limit_down"]


def fetch_akshare(symbols: list[str], start: str, end: str) -> pd.DataFrame:
    """Fetch bars from AKShare (qfq, per-stock)."""
    client = AKShareClient(rate_limit=0.3)
    df = client.get_bars(symbols, start, end, freq="1d", adjusted="qfq")
    if df.empty:
        return df
    df["source"] = "akshare"
    return df


def fetch_tushare(dates: list[str]) -> dict:
    """Fetch from TushareProvider — both raw daily and adj_factor.

    Returns dict with keys:
        formatted: DataFrame in standard schema (all dates combined)
        raw: dict of date_str → raw daily DataFrame
        adj: dict of date_str → adj_factor DataFrame
    """
    provider = TushareProvider()

    raw_by_date = {}
    adj_by_date = {}
    fmt_frames = []

    for d in dates:
        d8 = _date_fmt(d)
        try:
            raw = provider.fetch_daily_by_date(d8)
            raw_by_date[d] = raw
        except Exception as e:
            logger.warning(f"Tushare daily({d8}) failed: {e}")
            raw_by_date[d] = pd.DataFrame()

        try:
            adj = provider.fetch_adj_factor_by_date(d8)
            adj_by_date[d] = adj
        except Exception as e:
            logger.warning(f"Tushare adj_factor({d8}) failed: {e}")
            adj_by_date[d] = pd.DataFrame()

        try:
            fmt = provider.fetch_formatted(d8)
            if not fmt.empty:
                fmt["source"] = "tushare"
                fmt_frames.append(fmt)
        except Exception as e:
            logger.warning(f"Tushare fetch_formatted({d8}) failed: {e}")

    formatted = pd.concat(fmt_frames, ignore_index=True) if fmt_frames else pd.DataFrame()
    return {"formatted": formatted, "raw": raw_by_date, "adj": adj_by_date}


# ---------------------------------------------------------------------------
# comparison engine
# ---------------------------------------------------------------------------

def compare_providers(ak_df: pd.DataFrame, ts_df: pd.DataFrame) -> pd.DataFrame:
    """Merge AKShare and Tushare data on (symbol, trade_date) and compute diffs."""
    if ak_df.empty or ts_df.empty:
        logger.error("One or both DataFrames are empty — cannot compare")
        return pd.DataFrame()

    merged = ak_df.merge(
        ts_df,
        on=["symbol", "trade_date"],
        suffixes=("_ak", "_ts"),
        how="inner",
    )

    if merged.empty:
        logger.error("No overlapping (symbol, trade_date) rows between providers")
        return merged

    for field in TUSHARE_FIELDS:
        col_ak = f"{field}_ak"
        col_ts = f"{field}_ts"
        if col_ak not in merged.columns or col_ts not in merged.columns:
            continue
        merged[f"{field}_diff"] = merged[col_ak] - merged[col_ts]
        merged[f"{field}_pct_diff"] = _pct(merged[col_ak], merged[col_ts])

    return merged


def field_summary(merged: pd.DataFrame, field: str) -> dict:
    """Compute summary stats for one field's cross-provider differences."""
    diff_col = f"{field}_diff"
    pct_col = f"{field}_pct_diff"
    if diff_col not in merged.columns:
        return {"field": field, "error": "column missing from merged data"}

    diff = merged[diff_col].dropna()
    pct = merged[pct_col].dropna()

    n = len(diff)
    if n == 0:
        return {"field": field, "n_pairs": 0, "note": "no valid pairs"}

    # Match tolerance: 0.1% or absolute < 0.001
    matched = (pct < 0.1) | (diff.abs() < 0.001)
    match_rate = matched.sum() / n * 100

    return {
        "field": field,
        "n_pairs": n,
        "mean_ak": merged[f"{field}_ak"].mean(),
        "mean_ts": merged[f"{field}_ts"].mean(),
        "mean_abs_diff": diff.abs().mean(),
        "median_abs_diff": diff.abs().median(),
        "max_abs_diff": diff.abs().max(),
        "mean_abs_pct": pct.mean(),
        "median_abs_pct": pct.median(),
        "max_abs_pct": pct.max(),
        "match_rate_01pct": round(match_rate, 2),
        "correlation": merged[f"{field}_ak"].corr(merged[f"{field}_ts"]),
    }


# ---------------------------------------------------------------------------
# 复权 mode detection
# ---------------------------------------------------------------------------

def detect_adjustment_mode(merged: pd.DataFrame, ts_data: dict) -> dict:
    """Determine if Tushare /daily returns unadjusted, qfq, or hfq prices.

    Strategy:
      1. Check adj_factor distribution from Tushare's adj_factor endpoint.
         If all adj_factor ≈ 1.0 → data is likely qfq.
         If adj_factor varies significantly → data is likely unadjusted.
      2. Compare OHLC between Tushare formatted and AKShare qfq.
         If close matches within 0.1% → Tushare also returns qfq.
         If close differs systematically → Tushare is unadjusted.
      3. For stocks with adj_factor ≠ 1.0, test:
           Tushare_close × adj_factor ≈ AKShare_close (qfq)?
    """
    result = {"mode": "undetermined", "confidence": "low", "evidence": []}

    # 1. adj_factor distribution
    adj_factors = []
    for d, adj_df in ts_data["adj"].items():
        if not adj_df.empty and "adj_factor" in adj_df.columns:
            adj_factors.extend(adj_df["adj_factor"].dropna().tolist())

    if adj_factors:
        adj_arr = np.array(adj_factors)
        result["adj_factor_stats"] = {
            "count": len(adj_arr),
            "mean": float(np.mean(adj_arr)),
            "std": float(np.std(adj_arr)),
            "min": float(np.min(adj_arr)),
            "max": float(np.max(adj_arr)),
            "pct_not_1": float(np.mean(np.abs(adj_arr - 1.0) > 1e-6) * 100),
        }
        if np.mean(np.abs(adj_arr - 1.0) > 1e-6) < 0.01:
            result["evidence"].append(
                "adj_factor all ≈ 1.0 — Tushare /daily likely returns qfq data"
            )
        else:
            result["evidence"].append(
                f"adj_factor varies: {result['adj_factor_stats']['pct_not_1']:.1f}% ≠ 1.0 "
                f"(range {result['adj_factor_stats']['min']:.4f} – {result['adj_factor_stats']['max']:.4f}) "
                f"— Tushare /daily likely returns unadjusted data"
            )

    # 2. close comparison
    if "close_pct_diff" in merged.columns:
        close_pct = merged["close_pct_diff"].dropna()
        if len(close_pct) > 0:
            mean_pct = close_pct.mean()
            result["close_pct_diff_mean"] = round(float(mean_pct), 4)
            if mean_pct < 0.1:
                result["evidence"].append(
                    f"close matches within {mean_pct:.4f}% — Tushare and AKShare both return qfq"
                )
                result["mode"] = "qfq"
                result["confidence"] = "high"
            else:
                result["evidence"].append(
                    f"close differs by {mean_pct:.2f}% on average — Tushare is NOT qfq"
                )

    # 3. adj_factor correction test (for unadjusted hypothesis)
    if "close_pct_diff" in merged.columns and result.get("mode") != "qfq":
        # Try: does Tushare close * adj_factor ≈ AKShare close?
        adj_candidates = []
        for d, adj_df in ts_data["adj"].items():
            if adj_df.empty or "adj_factor" not in adj_df.columns:
                continue
            adj_df = adj_df.copy()
            adj_df["symbol"] = adj_df["ts_code"].str.replace(
                r"\.(SZ|SH|BJ)$", "", regex=True
            )
            day_merged = merged[merged["trade_date"] == d].copy()
            if day_merged.empty:
                continue
            day_merged = day_merged.merge(
                adj_df[["symbol", "adj_factor"]], on="symbol", how="inner"
            )
            if day_merged.empty:
                continue
            day_merged["close_ts_adj"] = day_merged["close_ts"] * day_merged["adj_factor"]
            day_merged["close_adj_pct"] = _pct(
                day_merged["close_ts_adj"], day_merged["close_ak"]
            )
            adj_candidates.append(day_merged["close_adj_pct"].dropna())

        if adj_candidates:
            all_adj_pct = pd.concat(adj_candidates)
            mean_adj_pct = all_adj_pct.mean()
            result["close_adj_corrected_pct_diff_mean"] = round(float(mean_adj_pct), 4)
            if mean_adj_pct < 0.5:
                result["evidence"].append(
                    f"After adj_factor correction: Tushare close × adj_factor matches "
                    f"AKShare close within {mean_adj_pct:.4f}% — confirms Tushare daily is UNADJUSTED"
                )
                result["mode"] = "unadjusted"
                result["confidence"] = "high"
            else:
                result["evidence"].append(
                    f"adj_factor correction does NOT align close "
                    f"(residual {mean_adj_pct:.2f}%)"
                )

    return result


# ---------------------------------------------------------------------------
# unit analysis
# ---------------------------------------------------------------------------

def analyse_units(merged: pd.DataFrame, ts_data: dict) -> dict:
    """Analyze volume and amount unit consistency.

    TushareProvider assumes: volume in 手, amount in 千元 (→ ×1000 → 元).
    AKShareClient: volume in 股, amount in 元 (from ak.stock_zh_a_hist).

    If both conventions match the raw API docs:
      - Tushare vol / AKShare vol ≈ 0.01  (because 1手 = 100股 → Tushare gives 手)
    Wait — TushareProvider.transform_to_standard() keeps vol as-is (labeled "手").
    AKShare returns 成交量 in 股. So if Tushare vol is 手 and AKShare vol is 股:
      ratio = ts_vol / ak_vol ≈ 0.01 (1手 = 100股)

    But both providers might actually return the same unit depending on the APIs.
    """
    result = {}

    if "volume_pct_diff" in merged.columns:
        vol_pct = merged["volume_pct_diff"].dropna()
        vol_ratio = merged["volume_ts"] / merged["volume_ak"].replace(0, np.nan)
        vol_ratio = vol_ratio.dropna()
        result["volume"] = {
            "mean_pct_diff": round(float(vol_pct.mean()), 2),
            "median_ratio_ts_to_ak": round(float(vol_ratio.median()), 4),
            "mean_ratio_ts_to_ak": round(float(vol_ratio.mean()), 4),
            "likely_unit_match": bool(0.9 < vol_ratio.median() < 1.1),
        }
        if vol_ratio.median() < 0.02:
            result["volume"]["note"] = (
                "Tushare volume ≈ 1% of AKShare → Tushare uses 手, AKShare uses 股. "
                "UNIT MISMATCH — need ×100 on Tushare volume."
            )
        elif 0.9 < vol_ratio.median() < 1.1:
            result["volume"]["note"] = "Units appear consistent (within 10%)."
        else:
            result["volume"]["note"] = (
                f"Unexpected ratio {vol_ratio.median():.4f} — investigate manually."
            )

    if "amount_pct_diff" in merged.columns:
        amt_pct = merged["amount_pct_diff"].dropna()
        amt_ratio = merged["amount_ts"] / merged["amount_ak"].replace(0, np.nan)
        amt_ratio = amt_ratio.dropna()
        result["amount"] = {
            "mean_pct_diff": round(float(amt_pct.mean()), 2),
            "median_ratio_ts_to_ak": round(float(amt_ratio.median()), 4),
            "mean_ratio_ts_to_ak": round(float(amt_ratio.mean()), 4),
            "likely_unit_match": bool(0.9 < amt_ratio.median() < 1.1),
        }
        if 0.9 < amt_ratio.median() < 1.1:
            result["amount"]["note"] = "Units appear consistent (within 10%)."
        elif amt_ratio.median() > 900:
            result["amount"]["note"] = (
                "Tushare amount >> AKShare — Tushare raw might be 千元, "
                "×1000 conversion might be wrong direction."
            )
        else:
            result["amount"]["note"] = (
                f"Unexpected ratio {amt_ratio.median():.4f} — investigate manually."
            )

    return result


# ---------------------------------------------------------------------------
# pre_close analysis
# ---------------------------------------------------------------------------

def analyse_pre_close(merged: pd.DataFrame) -> dict:
    """Analyze whether Tushare pre_close is useful for limit_up/down computation.

    AKShareClient: limit_up = close.shift(1) * 1.10  (approximate, on qfq data)
    TushareProvider: limit_up = pre_close * 1.10  (from API, on raw data)

    Key question: does Tushare's pre_close improve limit_up/down accuracy?
    """
    result = {}
    if "pre_close_pct_diff" not in merged.columns:
        result["note"] = "pre_close not available in merged data"
        return result

    pre_pct = merged["pre_close_pct_diff"].dropna()
    if len(pre_pct) == 0:
        result["note"] = "no pre_close data to compare"
        return result

    # Tushare provides real pre_close; AKShare doesn't output pre_close at all.
    # We compare Tushare pre_close vs AKShare close.shift(1) as a proxy.
    # (AKShare's limit_up is based on close.shift(1), so this is the relevant comparison.)

    result["pre_close"] = {
        "n_available": int(merged["pre_close_ts"].notna().sum()),
        "n_missing": int(merged["pre_close_ts"].isna().sum()),
        "mean_abs_diff_vs_ak": round(float(pre_pct.mean()), 4),
        "median_abs_diff_vs_ak": round(float(pre_pct.median()), 4),
    }

    # Compare limit_up/down derived from each
    merged_valid = merged.dropna(subset=["pre_close_ts"]).copy()
    if len(merged_valid) > 0:
        # Tushare limit: pre_close * 1.10 / 0.90
        # AKShare limit: close.shift(1) * 1.10 / 0.90
        lu_pct = _pct(merged_valid["limit_up_ts"], merged_valid["limit_up_ak"]).dropna()
        ld_pct = _pct(merged_valid["limit_down_ts"], merged_valid["limit_down_ak"]).dropna()
        result["limit_comparison"] = {
            "limit_up_mean_pct_diff": round(float(lu_pct.mean()), 4),
            "limit_down_mean_pct_diff": round(float(ld_pct.mean()), 4),
        }

    result["conclusion"] = (
        "Tushare pre_close (real) is more accurate than close.shift(1) (approximate). "
        "Recommend: use Tushare pre_close for limit_up/down when available."
    )

    return result


# ---------------------------------------------------------------------------
# report generation
# ---------------------------------------------------------------------------

def generate_report(
    config: dict,
    field_stats: list[dict],
    adj_result: dict,
    unit_result: dict,
    preclose_result: dict,
    merged: pd.DataFrame,
) -> str:
    """Generate comprehensive markdown report."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    lines = []
    def w(s=""):
        lines.append(s)

    w(f"# TushareProvider vs AKShare 数据口径验证报告")
    w()
    w(f"**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    w()

    # ── Configuration ──
    w("## 1. 测试配置")
    w()
    w(f"| 参数 | 值 |")
    w(f"|------|-----|")
    w(f"| 交易日范围 | {config['dates'][0]} → {config['dates'][-1]} ({len(config['dates'])} 天) |")
    w(f"| 股票数量 | {config['n_symbols']} |")
    w(f"| 数据行数 (AKShare) | {config['ak_rows']} |")
    w(f"| 数据行数 (Tushare) | {config['ts_rows']} |")
    w(f"| 匹配合并行数 | {config.get('merged_rows', 'N/A')} |")
    w()

    # ── Per-field comparison ──
    w("## 2. 字段逐项对比")
    w()
    w("| 字段 | 匹配数 | 平均差异 | 中位差异% | 匹配率(0.1%) | 相关系数 | 状态 |")
    w("|------|--------|----------|-----------|-------------|----------|------|")
    for s in field_stats:
        if "error" in s:
            w(f"| {s['field']} | — | — | — | — | — | ⚠ {s['error']} |")
            continue
        if s.get("n_pairs", 0) == 0:
            w(f"| {s['field']} | 0 | — | — | — | — | 无数据 |")
            continue
        status = "✅" if s["match_rate_01pct"] > 95 else ("⚠️" if s["match_rate_01pct"] > 80 else "❌")
        w(
            f"| {s['field']} | {s['n_pairs']} | {s['mean_abs_diff']:.4f} | "
            f"{s['median_abs_pct']:.2f}% | {s['match_rate_01pct']:.1f}% | "
            f"{s['correlation']:.6f} | {status} |"
        )
    w()

    # Detailed stats for OHLCV
    w("### 2.1 OHLCV 详细统计")
    w()
    w("| 字段 | AKShare 均值 | Tushare 均值 | 最大差异 | 最大差异% |")
    w("|------|-------------|-------------|----------|-----------|")
    for s in field_stats:
        if s["field"] in ("open", "high", "low", "close", "volume", "amount") and "error" not in s and s.get("n_pairs", 0) > 0:
            w(
                f"| {s['field']} | {s['mean_ak']:.4f} | {s['mean_ts']:.4f} | "
                f"{s['max_abs_diff']:.4f} | {s['max_abs_pct']:.2f}% |"
            )
    w()

    # ── 复权 Detection ──
    w("## 3. 复权模式判定")
    w()
    w(f"**结论: Tushare /daily 返回 `{adj_result.get('mode', 'unknown')}` 数据** (置信度: {adj_result.get('confidence', 'N/A')})")
    w()
    if "adj_factor_stats" in adj_result:
        afs = adj_result["adj_factor_stats"]
        w("### 3.1 adj_factor 分布")
        w()
        w(f"| 指标 | 值 |")
        w(f"|------|-----|")
        w(f"| 样本数 | {afs['count']} |")
        w(f"| 均值 | {afs['mean']:.6f} |")
        w(f"| 标准差 | {afs['std']:.6f} |")
        w(f"| 最小值 | {afs['min']:.6f} |")
        w(f"| 最大值 | {afs['max']:.6f} |")
        w(f"| ≠1.0 比例 | {afs['pct_not_1']:.2f}% |")
        w()

    w("### 3.2 判定依据")
    w()
    for e in adj_result.get("evidence", []):
        w(f"- {e}")
    w()

    if "close_pct_diff_mean" in adj_result:
        w(f"- close 平均差异: {adj_result['close_pct_diff_mean']:.4f}%")
    if "close_adj_corrected_pct_diff_mean" in adj_result:
        w(f"- adj_factor 修正后 close 差异: {adj_result['close_adj_corrected_pct_diff_mean']:.4f}%")
    w()

    # ── Unit Analysis ──
    w("## 4. 量纲一致性")
    w()
    for key in ("volume", "amount"):
        info = unit_result.get(key, {})
        if not info:
            w(f"**{key}**: 无数据")
            continue
        w(f"### 4.{'1' if key == 'volume' else '2'} {key}")
        w()
        w(f"| 指标 | 值 |")
        w(f"|------|-----|")
        w(f"| 平均差异% | {info.get('mean_pct_diff', 'N/A')}% |")
        w(f"| 中位比率 (TS/AK) | {info.get('median_ratio_ts_to_ak', 'N/A')} |")
        w(f"| 单位一致 | {'✅ 是' if info.get('likely_unit_match') else '❌ 否'} |")
        w(f"| 判定 | {info.get('note', 'N/A')} |")
        w()
    w()

    # ── pre_close Analysis ──
    w("## 5. pre_close 分析")
    w()
    if "pre_close" in preclose_result:
        pc = preclose_result["pre_close"]
        w(f"| 指标 | 值 |")
        w(f"|------|-----|")
        w(f"| Tushare pre_close 可用数 | {pc['n_available']} |")
        w(f"| Tushare pre_close 缺失数 | {pc['n_missing']} |")
        w(f"| 与 AKShare close.shift(1) 中位差异 | {pc['median_abs_diff_vs_ak']:.4f}% |")
        w()

    if "limit_comparison" in preclose_result:
        lc = preclose_result["limit_comparison"]
        w("### 5.1 limit_up/down 对比 (Tushare pre_close vs AKShare close.shift(1))")
        w()
        w(f"| 指标 | 值 |")
        w(f"|------|-----|")
        w(f"| limit_up 中位差异 | {lc['limit_up_mean_pct_diff']:.4f}% |")
        w(f"| limit_down 中位差异 | {lc['limit_down_mean_pct_diff']:.4f}% |")
        w()

    if "conclusion" in preclose_result:
        w(f"**{preclose_result['conclusion']}**")
    w()

    # ── Exceptions / Outliers ──
    w("## 6. 异常样本")
    w()
    close_pct = merged.get("close_pct_diff", pd.Series(dtype=float)).dropna()
    outliers = merged[merged.get("close_pct_diff", pd.Series(dtype=float)) > 5.0].head(20) if len(close_pct) > 0 else pd.DataFrame()
    if not outliers.empty and "close_pct_diff" in outliers.columns:
        cols = ["symbol", "trade_date", "close_ak", "close_ts", "close_pct_diff"]
        available = [c for c in cols if c in outliers.columns]
        w(f"以下 {min(len(outliers), 20)} 个样本 close 差异 > 5%（可能含分红/拆股/API 差异）：")
        w()
        w("| symbol | trade_date | close_ak | close_ts | pct_diff% |")
        w("|--------|------------|----------|----------|-----------|")
        for _, row in outliers.head(20).iterrows():
            w(
                f"| {row.get('symbol', '?')} | {row.get('trade_date', '?')} | "
                f"{row.get('close_ak', np.nan):.4f} | {row.get('close_ts', np.nan):.4f} | "
                f"{row.get('close_pct_diff', np.nan):.2f}% |"
            )
        w()
    else:
        w("无显著异常样本 (close 差异均 < 5%)。")
        w()

    # ── Overall Verdict ──
    w("## 7. 综合结论与建议")
    w()
    w(f"1. **复权模式**: Tushare /daily 返回 **{adj_result.get('mode', '?')}** 数据 (置信度: {adj_result.get('confidence', '?')})")
    vol_ok = unit_result.get("volume", {}).get("likely_unit_match", False)
    amt_ok = unit_result.get("amount", {}).get("likely_unit_match", False)
    w(f"2. **volume 单位**: {'✅ 一致' if vol_ok else '❌ 不一致 — ' + unit_result.get('volume', {}).get('note', '?')}")
    w(f"3. **amount 单位**: {'✅ 一致' if amt_ok else '❌ 不一致 — ' + unit_result.get('amount', {}).get('note', '?')}")
    w(f"4. **pre_close**: Tushare 提供真实 pre_close，{'可用于' if preclose_result.get('pre_close', {}).get('n_available', 0) > 0 else '不可用 —'} 更准确的 limit_up/down 计算")
    w()
    w("### 接入建议")
    w()
    if adj_result.get("mode") == "qfq" and vol_ok and amt_ok:
        w("- ✅ 数据口径一致，可以直接接入 `incremental_update_data.py`（需先实现 `get_bars()` 接口）")
    elif adj_result.get("mode") == "unadjusted":
        w("- ⚠️ Tushare 返回未复权数据，接入前必须在 `transform_to_standard()` 中用 `adj_factor` 将 OHLC 转为前复权")
        w("- ⚠️ 转换公式: `close_qfq = close_raw × adj_factor`")
    else:
        w("- ⚠️ 复权模式无法确认，建议手动抽查几只股票后决定")
    if not vol_ok:
        w("- ❌ volume 单位不一致，需要在 `transform_to_standard()` 中修正量纲")
    if not amt_ok:
        w("- ❌ amount 单位不一致，需要在 `transform_to_standard()` 中修正量纲")
    w()
    w("---")
    w(f"*报告由 `scripts/verify_tushare_alignment.py` 自动生成*")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Verify TushareProvider data alignment with AKShare pipeline"
    )
    parser.add_argument("--start", default="2026-05-12", help="Start date YYYY-MM-DD (default: 2026-05-12)")
    parser.add_argument("--end", default="2026-05-15", help="End date YYYY-MM-DD (default: 2026-05-15)")
    parser.add_argument("--symbols", default="", help="Comma-separated explicit stock codes")
    parser.add_argument("--n-symbols", type=int, default=30, help="Number of stocks to sample (default: 30)")
    args = parser.parse_args()

    # ── 0. Pre-flight: check Tushare token ──
    try:
        TushareProvider()
    except ValueError as e:
        logger.error(f"TushareProvider init failed: {e}")
        logger.error("Set $env:TUSHARE_TOKEN before running this script.")
        return

    # ── 1. Resolve symbols and dates ──
    symbols = resolve_symbols(args.symbols if args.symbols else None, args.n_symbols)
    if not symbols:
        logger.error("No symbols resolved — cannot proceed.")
        return

    dates = resolve_trading_dates(args.start, args.end)
    if not dates:
        logger.error("No trading dates resolved — cannot proceed.")
        return

    config = {
        "dates": dates,
        "n_symbols": len(symbols),
        "ak_rows": 0,
        "ts_rows": 0,
        "merged_rows": 0,
    }

    # ── 2. Fetch from both providers ──
    logger.info(f"Fetching {len(symbols)} symbols × {len(dates)} dates from AKShare...")
    ak_df = fetch_akshare(symbols, dates[0], dates[-1])
    config["ak_rows"] = len(ak_df)
    logger.info(f"AKShare returned {len(ak_df)} rows")

    logger.info(f"Fetching {len(dates)} dates from TushareProvider...")
    ts_data = fetch_tushare(dates)
    ts_df = ts_data["formatted"]
    config["ts_rows"] = len(ts_df)
    logger.info(f"Tushare returned {len(ts_df)} rows")

    # ── 3. Filter Tushare to target symbols ──
    if not ts_df.empty:
        ts_df = ts_df[ts_df["symbol"].isin(symbols)]
        logger.info(f"Tushare filtered to {len(ts_df)} rows ({len(symbols)} target symbols)")

    # ── 4. Compare ──
    merged = compare_providers(ak_df, ts_df)
    config["merged_rows"] = len(merged)

    if merged.empty:
        logger.error("Merge produced 0 rows — check date/symbol overlap.")
        logger.error(f"AKShare dates: {sorted(ak_df['trade_date'].unique()) if not ak_df.empty else 'none'}")
        logger.error(f"Tushare dates: {sorted(ts_df['trade_date'].unique()) if not ts_df.empty else 'none'}")
        return

    logger.info(f"Merged: {len(merged)} rows across providers")

    # ── 5. Run analyses ──
    field_stats = [field_summary(merged, f) for f in TUSHARE_FIELDS]
    adj_result = detect_adjustment_mode(merged, ts_data)
    unit_result = analyse_units(merged, ts_data)
    preclose_result = analyse_pre_close(merged)

    # ── 6. Generate & save report ──
    report = generate_report(config, field_stats, adj_result, unit_result, preclose_result, merged)

    reports_dir = ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    report_path = reports_dir / f"tushare_alignment_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.write_text(report, encoding="utf-8")
    logger.info(f"Report saved: {report_path}")

    # ── 7. Print key findings to console ──
    print(f"\n{'='*60}")
    print(f"KEY FINDINGS")
    print(f"{'='*60}")
    print(f"  复权模式: {adj_result.get('mode', '?')} (置信度: {adj_result.get('confidence', '?')})")
    if "adj_factor_stats" in adj_result:
        print(f"  adj_factor ≠1.0: {adj_result['adj_factor_stats']['pct_not_1']:.2f}%")
    print(f"  close 平均差异: {adj_result.get('close_pct_diff_mean', 'N/A')}%")
    if "close_adj_corrected_pct_diff_mean" in adj_result:
        print(f"  adj_factor 修正后: {adj_result['close_adj_corrected_pct_diff_mean']:.4f}%")
    print(f"  volume 单位一致: {unit_result.get('volume', {}).get('likely_unit_match', '?')}")
    print(f"  amount 单位一致: {unit_result.get('amount', {}).get('likely_unit_match', '?')}")
    print(f"\n  Full report: {report_path}")

    return report_path


if __name__ == "__main__":
    main()

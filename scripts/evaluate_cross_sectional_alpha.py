"""Phase 1: Single-factor cross-sectional alpha IC scan.

Evaluates features for daily cross-sectional ranking power on HS300 universe.
Outputs feature-by-feature IC, quantile bucket, and pass/stop verdict.

Usage:
    # Smoke test (1 month, 3 features)
    python scripts/evaluate_cross_sectional_alpha.py --smoke

    # Full run: momentum/trend features (Phase 1 original)
    python scripts/evaluate_cross_sectional_alpha.py

    # Full run: reversal/defensive factor audit
    python scripts/evaluate_cross_sectional_alpha.py --mode reversal

    # Custom date range
    python scripts/evaluate_cross_sectional_alpha.py --start 2022-01-01 --end 2024-12-31
"""
from __future__ import annotations

import json
import sys
import warnings
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
BAR_PATH = ROOT / "data/raw/HS300_daily.parquet"
CAL_PATH = ROOT / "data/raw/calendar.parquet"
IDX_PATH = ROOT / "data/raw/index/sh000300_daily.parquet"
CONST_PATH = ROOT / "data/historical_constituents.json"

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Feature definitions ──
# Each: (name, direction_hint)
# direction_hint: 1 = higher better, -1 = lower better, 0 = unknown (bidirectional)
FEATURE_SPECS = [
    # Momentum
    ("ret_5d", 1),
    ("ret_20d", 1),
    ("ret_60d", 1),
    # Volatility (bidirectional)
    ("vol_20d", 0),
    ("hl_range_20d", 0),
    # Volume / amount
    ("volume_ratio_5_20", 1),
    ("amount_rank_pct", 1),       # cross-sectional, computed per day
    ("amount_ratio_5_20", 1),
    # Relative strength
    ("rs_20d", 1),
    ("rs_60d", 1),
    # Trend quality
    ("close_div_ma20", 1),
    ("close_div_ma60", 1),
    ("ma20_div_ma60", 1),
]

# Feature names only
ALL_FEATURES = [f[0] for f in FEATURE_SPECS]
SMOKE_FEATURES = ["ret_20d", "rs_20d", "amount_rank_pct"]

# ── Reversal / Defensive features (negate base features) ──
# Map: reversal_feature_name -> (base_feature_name, direction_hint)
REVERSAL_FEATURE_SPECS = [
    # Reversal (negate momentum)
    ("low_ret_5d", "ret_5d", 1),
    ("low_ret_20d", "ret_20d", 1),
    ("low_ret_60d", "ret_60d", 1),
    # Defensive / low risk (negate volatility/amount)
    ("low_vol_20d", "vol_20d", 1),
    ("low_hl_range_20d", "hl_range_20d", 1),
    ("low_amount_rank_pct", "amount_rank_pct", 1),
    # Anti-trend (negate trend quality)
    ("low_close_div_ma20", "close_div_ma20", 1),
    ("low_close_div_ma60", "close_div_ma60", 1),
    ("low_ma20_div_ma60", "ma20_div_ma60", 1),
    # RS reversal (redundant with ret reversal but included for completeness)
    ("low_rs_20d", "rs_20d", 1),
    ("low_rs_60d", "rs_60d", 1),
]
# Reference features kept in original direction
REVERSAL_REF_FEATURES = [
    ("volume_ratio_5_20", 1),
    ("amount_ratio_5_20", 1),
]

REVERSAL_ALL_FEATURES = [f[0] for f in REVERSAL_FEATURE_SPECS] + [f[0] for f in REVERSAL_REF_FEATURES]
# Base feature -> negate flag
REVERSAL_NEGATE_MAP = {f[0]: f[1] for f in REVERSAL_FEATURE_SPECS}

# ── Labels ──
LABEL_SPECS = [
    ("fwd_ret_5d", "close(T+5)/open(T+1)-1"),
    ("fwd_ret_10d", "close(T+10)/open(T+1)-1"),
    ("fwd_ret_20d", "close(T+20)/open(T+1)-1"),
    ("mae_10d", "max(1-low(T+i)/open(T+1)), i=1..10"),
    ("hit_rate_10d", "fwd_ret_10d > 0"),
]


def load_constituent_map() -> dict:
    """Load quarterly HS300 constituent snapshots.

    Returns: {date_str: [symbols]} with duplicates removed.
    """
    with open(CONST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    raw = data["indices"]["HS300"]["quarterly"]
    return {k: sorted(set(v)) for k, v in raw.items()}


def get_constituents_for_date(date_str: str, const_map: dict) -> list[str]:
    """Get HS300 constituents for a given date (nearest prior quarter)."""
    sorted_dates = sorted(const_map.keys())
    for q_date in reversed(sorted_dates):
        if q_date <= date_str:
            return const_map[q_date]
    return const_map[sorted_dates[0]] if sorted_dates else []


def build_feature_matrices(
    bars: pd.DataFrame, idx_bars: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """Pre-compute all vectorized feature time series.

    Returns dict of feature_name -> (trade_date x symbol) DataFrame.
    """
    print("  Pivoting OHLCV matrices...")
    close = bars.pivot(index="trade_date", columns="symbol", values="close")
    open_ = bars.pivot(index="trade_date", columns="symbol", values="open")
    high = bars.pivot(index="trade_date", columns="symbol", values="high")
    low = bars.pivot(index="trade_date", columns="symbol", values="low")
    volume = bars.pivot(index="trade_date", columns="symbol", values="volume")
    amount = bars.pivot(index="trade_date", columns="symbol", values="amount")

    features = {}

    print("  Computing momentum features...")
    features["ret_5d"] = close / close.shift(5) - 1
    features["ret_20d"] = close / close.shift(20) - 1
    features["ret_60d"] = close / close.shift(60) - 1

    print("  Computing volatility features...")
    daily_ret = close.pct_change()
    features["vol_20d"] = daily_ret.rolling(20).std() * np.sqrt(242)
    hl_ratio = high / low - 1
    features["hl_range_20d"] = hl_ratio.rolling(20).mean()

    print("  Computing volume/amount features...")
    vol_ma_5 = volume.rolling(5).mean()
    vol_ma_20 = volume.rolling(20).mean()
    features["volume_ratio_5_20"] = vol_ma_5 / vol_ma_20
    # amount_rank_pct computed daily in processing loop
    features["amount_rank_pct"] = amount  # raw, ranked daily
    amt_ma_5 = amount.rolling(5).mean()
    amt_ma_20 = amount.rolling(20).mean()
    features["amount_ratio_5_20"] = amt_ma_5 / amt_ma_20

    print("  Computing relative strength features...")
    idx_close = idx_bars.set_index("trade_date")["close"]
    idx_close = idx_close.reindex(close.index).ffill()
    idx_ret_20 = idx_close / idx_close.shift(20) - 1
    idx_ret_60 = idx_close / idx_close.shift(60) - 1
    features["rs_20d"] = features["ret_20d"].sub(idx_ret_20, axis=0)
    features["rs_60d"] = features["ret_60d"].sub(idx_ret_60, axis=0)

    print("  Computing trend quality features...")
    ma20 = close.rolling(20).mean()
    ma60 = close.rolling(60).mean()
    features["close_div_ma20"] = close / ma20
    features["close_div_ma60"] = close / ma60
    features["ma20_div_ma60"] = ma20 / ma60

    # Build daily filter matrices
    print("  Building filter matrices...")
    features["_is_st"] = bars.pivot(index="trade_date", columns="symbol", values="is_st")
    features["_is_suspended"] = bars.pivot(index="trade_date", columns="symbol", values="is_suspended")
    features["_limit_up"] = bars.pivot(index="trade_date", columns="symbol", values="limit_up")
    features["_limit_down"] = bars.pivot(index="trade_date", columns="symbol", values="limit_down")
    features["_open"] = open_
    features["_close"] = close
    features["_low"] = low
    features["_high"] = high

    # Store refs for label computation
    features["__close"] = close
    features["__open"] = open_
    features["__low"] = low
    features["__high"] = high

    return features


def build_label_data(
    bars: pd.DataFrame, close: pd.DataFrame, open_: pd.DataFrame, low: pd.DataFrame
) -> dict:
    """Pre-compute forward-looking label data.

    Returns:
        open_t1: open(T+1) matrix
        close_t5, close_t10, close_t20: forward close matrices
        low_fwd_min_10d: min low from T+1 to T+10
        suspended_t1: is_suspended at T+1
        limit_up_t1: limit_up at T+1
        is_st_t1: is_st at T+1
    """
    print("  Computing forward label data...")
    open_t1 = open_.shift(-1)
    close_t5 = close.shift(-5)
    close_t10 = close.shift(-10)
    close_t20 = close.shift(-20)

    # Min low from T+1 to T+10: stack shifted arrays, take min
    stacked = []
    for i in range(1, 11):
        stacked.append(low.shift(-i).values)
    low_fwd_min_10d_arr = np.nanmin(np.stack(stacked, axis=-1), axis=-1)
    low_fwd_min_10d = pd.DataFrame(
        low_fwd_min_10d_arr, index=low.index, columns=low.columns
    )

    suspended_mat = bars.pivot(index="trade_date", columns="symbol", values="is_suspended")
    limit_up_mat = bars.pivot(index="trade_date", columns="symbol", values="limit_up")
    is_st_mat = bars.pivot(index="trade_date", columns="symbol", values="is_st")

    suspended_t1 = suspended_mat.shift(-1)
    limit_up_t1 = limit_up_mat.shift(-1)
    is_st_t1 = is_st_mat.shift(-1)

    return {
        "open_t1": open_t1,
        "close_t5": close_t5,
        "close_t10": close_t10,
        "close_t20": close_t20,
        "low_fwd_min_10d": low_fwd_min_10d,
        "suspended_t1": suspended_t1,
        "limit_up_t1": limit_up_t1,
        "is_st_t1": is_st_t1,
    }


def compute_labels_for_date(
    date_str: str,
    symbols: list[str],
    label_data: dict,
) -> dict[str, pd.Series]:
    """Compute forward labels for eligible symbols at a given date."""
    result = {}
    o1 = label_data["open_t1"]
    c5 = label_data["close_t5"]
    c10 = label_data["close_t10"]
    c20 = label_data["close_t20"]
    lmin = label_data["low_fwd_min_10d"]

    if date_str not in o1.index:
        return {name: pd.Series(dtype=float) for name, _ in LABEL_SPECS}

    open_t1_vals = o1.loc[date_str]
    valid_syms = [s for s in symbols if s in open_t1_vals.index]

    if not valid_syms:
        return {name: pd.Series(dtype=float) for name, _ in LABEL_SPECS}

    o1_s = open_t1_vals[valid_syms]
    o1_s = o1_s.replace(0, np.nan)  # open=0 is bad data

    result["fwd_ret_5d"] = c5.loc[date_str, valid_syms] / o1_s - 1 if date_str in c5.index else pd.Series(index=valid_syms, dtype=float)
    result["fwd_ret_10d"] = c10.loc[date_str, valid_syms] / o1_s - 1 if date_str in c10.index else pd.Series(index=valid_syms, dtype=float)
    result["fwd_ret_20d"] = c20.loc[date_str, valid_syms] / o1_s - 1 if date_str in c20.index else pd.Series(index=valid_syms, dtype=float)
    result["mae_10d"] = 1.0 - lmin.loc[date_str, valid_syms] / o1_s if date_str in lmin.index else pd.Series(index=valid_syms, dtype=float)

    hr = result.get("fwd_ret_10d", pd.Series(dtype=float))
    result["hit_rate_10d"] = (hr > 0).astype(float) if len(hr) > 0 else pd.Series(dtype=float)

    return result


@dataclass
class DailyRecord:
    date: str
    n_constituent: int
    n_after_filters: int
    n_tradable: int
    excluded_reasons: dict[str, int] = field(default_factory=dict)
    feature_ranks: dict[str, dict] = field(default_factory=dict)  # feature -> {sym: rank}
    labels: dict[str, float] = field(default_factory=dict)  # sym -> {label: value}


def process_daily(
    date_str: str,
    const_map: dict,
    feat_matrices: dict[str, pd.DataFrame],
    label_data: dict,
    features_to_run: list[str],
    negate_map: dict[str, str] | None = None,
    min_history_days: int = 60,
    eps: float = 1e-8,
) -> DailyRecord:
    """Process one trading day: filter universe, rank features, compute labels."""
    rec = DailyRecord(date=date_str, n_constituent=0, n_after_filters=0, n_tradable=0)
    rec.excluded_reasons = defaultdict(int)

    # ── 1. HS300 constituents ──
    const_syms = get_constituents_for_date(date_str, const_map)
    rec.n_constituent = len(const_syms)

    if not const_syms:
        return rec

    # Get available symbols in the data matrices
    ref_mat = feat_matrices["_close"]
    if date_str not in ref_mat.index:
        return rec
    available = [s for s in const_syms if s in ref_mat.columns]
    if not available:
        return rec

    # ── 2. Daily filters ──
    is_st_s = feat_matrices["_is_st"].loc[date_str, available]
    is_susp_s = feat_matrices["_is_suspended"].loc[date_str, available]
    limit_up_s = feat_matrices["_limit_up"].loc[date_str, available]
    limit_down_s = feat_matrices["_limit_down"].loc[date_str, available]
    close_s = feat_matrices["_close"].loc[date_str, available]

    mask = pd.Series(True, index=available)

    # ST filter
    st_fail = (is_st_s == True) | (is_st_s.astype(float) > 0)
    mask[st_fail] = False
    rec.excluded_reasons["is_st"] = int(st_fail.sum())

    # Suspended filter
    susp_fail = (is_susp_s == True) | (is_susp_s.astype(float) > 0)
    mask[susp_fail] = False
    rec.excluded_reasons["suspended"] = int(susp_fail.sum())

    # Close < 2 filter
    low_price = (close_s < 2.0) & close_s.notna()
    mask[low_price] = False
    rec.excluded_reasons["close_lt_2"] = int(low_price.sum())

    # Limit up at T (close >= limit_up - eps)
    limit_up_fail = (close_s >= limit_up_s - eps) & close_s.notna() & limit_up_s.notna() & (limit_up_s > 0)
    mask[limit_up_fail] = False
    rec.excluded_reasons["limit_up_T"] = int(limit_up_fail.sum())

    # Limit down at T (close <= limit_down + eps)
    limit_down_fail = (close_s <= limit_down_s + eps) & close_s.notna() & limit_down_s.notna() & (limit_down_s > 0)
    mask[limit_down_fail] = False
    rec.excluded_reasons["limit_down_T"] = int(limit_down_fail.sum())

    # Insufficient history (< 120 trading days of data)
    for sym in available:
        if not mask[sym]:
            continue
        sym_close = feat_matrices["__close"][sym].dropna()
        if len(sym_close) == 0:
            mask[sym] = False
            rec.excluded_reasons["no_history"] += 1
            continue
        first_date = sym_close.index[0]
        n_days = (ref_mat.index >= first_date) & (ref_mat.index <= date_str)
        if n_days.sum() < min_history_days:
            mask[sym] = False
            rec.excluded_reasons["insufficient_history"] += 1

    eligible = [s for s in available if mask[s]]
    rec.n_after_filters = len(eligible)

    if not eligible:
        return rec

    # ── 3. T+1 tradability check ──
    o1 = label_data["open_t1"]
    susp_t1 = label_data["suspended_t1"]
    lu_t1 = label_data["limit_up_t1"]

    if date_str in o1.index:
        o1_vals = o1.loc[date_str, eligible]
        susp_t1_vals = susp_t1.loc[date_str, eligible] if date_str in susp_t1.index else pd.Series(0, index=eligible)
        lu_t1_vals = lu_t1.loc[date_str, eligible] if date_str in lu_t1.index else pd.Series(np.nan, index=eligible)

        tradable_mask = pd.Series(True, index=eligible)
        # open(T+1) NaN or 0
        o1_invalid = o1_vals.isna() | (o1_vals == 0)
        tradable_mask[o1_invalid] = False
        rec.excluded_reasons["open_T1_missing"] = int(o1_invalid.sum())

        # Suspended at T+1
        susp_t1_fail = (susp_t1_vals == True) | (susp_t1_vals.astype(float) > 0)
        tradable_mask[susp_t1_fail] = False
        rec.excluded_reasons["suspended_T1"] = int(susp_t1_fail.sum())

        # Limit-up at T+1 (open >= limit_up - eps, can't buy)
        lu_t1_fail = (o1_vals >= lu_t1_vals - eps) & o1_vals.notna() & lu_t1_vals.notna() & (lu_t1_vals > 0)
        tradable_mask[lu_t1_fail] = False
        rec.excluded_reasons["limit_up_T1"] = int(lu_t1_fail.sum())

        tradable = [s for s in eligible if tradable_mask[s]]
    else:
        tradable = []
        rec.excluded_reasons["open_T1_missing"] = len(eligible)

    rec.n_tradable = len(tradable)

    if not tradable:
        return rec

    # ── 4. Compute features and cross-sectional ranks ──
    cs_amount = feat_matrices["amount_rank_pct"].loc[date_str, tradable] if date_str in feat_matrices["amount_rank_pct"].index else pd.Series(dtype=float)

    for fname in features_to_run:
        # Determine base feature and whether to negate
        if negate_map and fname in negate_map:
            base_name = negate_map[fname]
            do_negate = True
        else:
            base_name = fname
            do_negate = False

        if base_name == "amount_rank_pct":
            raw = cs_amount
        else:
            mat = feat_matrices.get(base_name)
            if mat is None or date_str not in mat.index:
                continue
            raw = mat.loc[date_str, tradable]

        if do_negate:
            raw = -raw

        raw = raw.replace([np.inf, -np.inf], np.nan).dropna()
        if len(raw) < 2:
            continue

        # Cross-sectional percentile rank (0 to 1)
        ranks = raw.rank(pct=True, na_option="bottom")
        rec.feature_ranks[fname] = ranks.to_dict()

    # ── 5. Compute labels ──
    labels = compute_labels_for_date(date_str, tradable, label_data)
    # Build sym->label_dict
    label_dict: dict[str, dict] = defaultdict(dict)
    for lbl_name, lbl_series in labels.items():
        for sym, val in lbl_series.items():
            if pd.notna(val) and np.isfinite(val):
                label_dict[sym][lbl_name] = val
    rec.labels = dict(label_dict)

    return rec


def run_analysis(
    start: str,
    end: str,
    features_to_run: list[str],
    smoke: bool = False,
    negate_map: dict[str, str] | None = None,
    mode: str = "momentum",
) -> str:
    """Run Phase 1 cross-sectional alpha evaluation.

    Returns path to output report file.
    """
    lookback_start = "2018-01-01"  # enough history for 60d features + 120d listing check

    print("=" * 60)
    title_str = "Reversal/Defensive Factor Audit" if mode == "reversal" else "Cross-Sectional Alpha Phase 1: Single-Factor IC Scan"
    print(f"{title_str}")
    print(f"Period: {start} ~ {end}")
    print(f"Features: {len(features_to_run)}")
    if smoke:
        print("MODE: SMOKE TEST")
    print("=" * 60)

    # ── Load data ──
    print("\n[1/6] Loading data...")
    bars = pd.read_parquet(BAR_PATH)
    bars["trade_date"] = pd.to_datetime(bars["trade_date"])
    bars = bars[(bars["trade_date"] >= lookback_start) & (bars["trade_date"] <= end)]
    bars = bars.sort_values(["trade_date", "symbol"]).reset_index(drop=True)
    print(f"  Bars loaded: {len(bars)} rows, {bars['symbol'].nunique()} symbols")

    calendar = pd.read_parquet(CAL_PATH)
    calendar["trade_date"] = pd.to_datetime(calendar["trade_date"])
    trading_days = set(
        calendar[calendar["is_trading_day"]]["trade_date"].dt.strftime("%Y-%m-%d")
    )

    idx_bars = pd.read_parquet(IDX_PATH)
    idx_bars["trade_date"] = pd.to_datetime(idx_bars["trade_date"])
    idx_bars = idx_bars[(idx_bars["trade_date"] >= lookback_start) & (idx_bars["trade_date"] <= end)]

    const_map = load_constituent_map()
    print(f"  Constituents: {len(const_map)} quarterly snapshots loaded")

    # ── Pre-compute features ──
    print("\n[2/6] Computing feature matrices...")
    feat_matrices = build_feature_matrices(bars, idx_bars)

    # ── Pre-compute labels ──
    print("\n[3/6] Computing forward label data...")
    label_data = build_label_data(
        bars, feat_matrices["__close"], feat_matrices["__open"], feat_matrices["__low"]
    )

    # ── Generate trading dates ──
    print("\n[4/6] Generating daily records...")
    ref_close = feat_matrices["__close"]
    all_dates = sorted(ref_close.index)
    analysis_dates = [
        d for d in all_dates
        if start <= d.strftime("%Y-%m-%d") <= end
        and d.strftime("%Y-%m-%d") in trading_days
    ]
    print(f"  Trading days in range: {len(analysis_dates)}")

    # ── Process each day ──
    records: list[DailyRecord] = []
    date_strs = [d.strftime("%Y-%m-%d") for d in analysis_dates]

    total_excluded: dict[str, int] = defaultdict(int)

    for i, (dt, date_str) in enumerate(zip(analysis_dates, date_strs)):
        if i % 100 == 0:
            print(f"  Processing {date_str} ({i+1}/{len(analysis_dates)})")
        rec = process_daily(date_str, const_map, feat_matrices, label_data,
                              features_to_run, negate_map)
        records.append(rec)
        for k, v in rec.excluded_reasons.items():
            total_excluded[k] += v

    print(f"  Total records: {len(records)}")

    # ── Aggregate results ──
    print("\n[5/6] Aggregating IC and quantile statistics...")

    # Build per-feature data: list of (date, symbol, feature_rank, labels...)
    # We'll compute per-feature IC independently
    ic_results = {}
    quantile_results = {}

    for fname in features_to_run:
        print(f"  Analyzing {fname}...")

        # Gather data across all dates
        all_rows = []
        for rec in records:
            if fname not in rec.feature_ranks:
                continue
            ranks = rec.feature_ranks[fname]
            for sym, rank_val in ranks.items():
                if sym in rec.labels:
                    row = {"date": rec.date, "symbol": sym, "feature_rank": rank_val}
                    row.update(rec.labels[sym])
                    all_rows.append(row)

        if len(all_rows) < 30:
            ic_results[fname] = {"error": f"Only {len(all_rows)} valid observations"}
            continue

        df_f = pd.DataFrame(all_rows)

        # ── Per-label IC ──
        label_ics = {}
        for lbl_name, _ in LABEL_SPECS:
            if lbl_name not in df_f.columns:
                continue
            valid = df_f.dropna(subset=[lbl_name, "feature_rank"])
            if len(valid) < 30:
                label_ics[lbl_name] = {"error": f"Only {len(valid)} valid obs"}
                continue

            # Daily rank IC (Spearman)
            daily_ics = []
            for date, grp in valid.groupby("date"):
                if len(grp) < 5:
                    continue
                ic = grp["feature_rank"].corr(grp[lbl_name], method="spearman")
                if pd.notna(ic):
                    daily_ics.append({"date": date, "ic": ic, "n": len(grp)})

            if not daily_ics:
                label_ics[lbl_name] = {"error": "No valid daily IC"}
                continue

            ic_df = pd.DataFrame(daily_ics)
            ic_df["year"] = pd.to_datetime(ic_df["date"]).dt.year

            mean_ic = ic_df["ic"].mean()
            ic_std = ic_df["ic"].std()
            ic_ir = mean_ic / ic_std if ic_std > 0 else 0
            ic_pos_ratio = (ic_df["ic"] > 0).mean()

            yearly = {}
            for yr, grp in ic_df.groupby("year"):
                yearly[int(yr)] = {
                    "mean_ic": float(grp["ic"].mean()),
                    "ic_ir": float(grp["ic"].mean() / grp["ic"].std()) if grp["ic"].std() > 0 else 0,
                    "n_days": len(grp),
                }

            # Train/val/test split
            train_ic = ic_df[ic_df["date"] <= "2023-12-31"]["ic"].mean()
            val_ic = ic_df[(ic_df["date"] >= "2024-01-01") & (ic_df["date"] <= "2024-12-31")]["ic"].mean()
            test_ic = ic_df[ic_df["date"] >= "2025-01-01"]["ic"].mean()

            label_ics[lbl_name] = {
                "mean_ic": float(mean_ic),
                "ic_std": float(ic_std),
                "ic_ir": float(ic_ir),
                "ic_pos_ratio": float(ic_pos_ratio),
                "n_daily_obs": len(ic_df),
                "yearly": yearly,
                "train_ic": float(train_ic) if pd.notna(train_ic) else None,
                "val_ic": float(val_ic) if pd.notna(val_ic) else None,
                "test_ic": float(test_ic) if pd.notna(test_ic) else None,
                "ic_df": ic_df,  # keep for quantile analysis
                "full_df": valid,
            }

        ic_results[fname] = label_ics

        # ── Quantile bucket analysis (using fwd_ret_10d as primary label) ──
        primary_label = "fwd_ret_10d"
        if primary_label in df_f.columns and primary_label in label_ics:
            valid = label_ics[primary_label].get("full_df")
            if valid is None or "error" in label_ics[primary_label]:
                quantile_results[fname] = {"error": "No valid IC data"}
                continue

            valid = valid.copy()
            # Add quantile bucket
            valid["q_bucket"] = pd.cut(
                valid["feature_rank"],
                bins=[0, 0.2, 0.4, 0.6, 0.8, 1.0],
                labels=["Q5_bottom", "Q4", "Q3_mid", "Q2", "Q1_top"],
                include_lowest=True,
            )

            q_stats = {}
            for q_name, q_grp in valid.groupby("q_bucket", observed=False):
                if len(q_grp) < 10:
                    continue
                rets = q_grp[primary_label].dropna()
                if len(rets) < 10:
                    continue
                mae_vals = q_grp.get("mae_10d", pd.Series())
                mae_vals = mae_vals.dropna() if isinstance(mae_vals, pd.Series) else pd.Series(dtype=float)
                hit_vals = q_grp.get("hit_rate_10d", pd.Series())
                hit_vals = hit_vals.dropna() if isinstance(hit_vals, pd.Series) else pd.Series(dtype=float)

                q_stats[str(q_name)] = {
                    "n": len(rets),
                    "mean_fwd_ret_10d": float(rets.mean()),
                    "median_fwd_ret_10d": float(rets.median()),
                    "std_fwd_ret_10d": float(rets.std()),
                    "hit_rate": float(hit_vals.mean()) if len(hit_vals) > 0 else None,
                    "mean_mae_10d": float(mae_vals.mean()) if len(mae_vals) > 0 else None,
                }

            # Q1-Q5 spread
            if "Q1_top" in q_stats and "Q5_bottom" in q_stats:
                spread = q_stats["Q1_top"]["mean_fwd_ret_10d"] - q_stats["Q5_bottom"]["mean_fwd_ret_10d"]
                # t-test
                q1_data = valid[valid["q_bucket"] == "Q1_top"][primary_label].dropna()
                q5_data = valid[valid["q_bucket"] == "Q5_bottom"][primary_label].dropna()
                if len(q1_data) >= 5 and len(q5_data) >= 5:
                    t_stat = (q1_data.mean() - q5_data.mean()) / np.sqrt(
                        q1_data.var() / len(q1_data) + q5_data.var() / len(q5_data)
                    )
                else:
                    t_stat = None
            else:
                spread = None
                t_stat = None

            quantile_results[fname] = {
                "q_stats": q_stats,
                "q1_q5_spread": spread,
                "t_stat": float(t_stat) if t_stat is not None and pd.notna(t_stat) else None,
            }
        else:
            quantile_results[fname] = {"error": "fwd_ret_10d not available"}

        ic_results[fname]["quantile"] = quantile_results.get(fname, {})

    # ── Coverage stats ──
    valid_records = [r for r in records if r.n_tradable > 0]
    daily_n_tradable = [r.n_tradable for r in valid_records]
    daily_n_tradable_s = pd.Series(daily_n_tradable) if daily_n_tradable else pd.Series([0])

    # ── Rank distribution analysis ──
    # For each date with features, check within-day score discrimination
    # How many dates have meaningful spread in cross-sectional ranks?
    # Since we use percentile ranks, the distribution is uniform by construction.
    # What matters is whether the rank translates to fwd_ret differences.

    # Rank autocorrelation: for top20% stocks, what fraction stay in top20% next day?
    rank_autocorr_data = []
    for i in range(1, len(records)):
        prev_rec = records[i - 1]
        curr_rec = records[i]
        for fname in features_to_run:
            if fname not in prev_rec.feature_ranks or fname not in curr_rec.feature_ranks:
                continue
            prev_ranks = prev_rec.feature_ranks[fname]
            curr_ranks = curr_rec.feature_ranks[fname]
            prev_top20 = {s for s, r in prev_ranks.items() if r >= 0.8}
            curr_top20 = {s for s, r in curr_ranks.items() if r >= 0.8}
            common = prev_top20 & curr_top20
            if prev_top20:
                rank_autocorr_data.append({
                    "date": curr_rec.date,
                    "feature": fname,
                    "prev_top20_n": len(prev_top20),
                    "stay_top20_n": len(common),
                    "overlap_pct": len(common) / len(prev_top20),
                })

    rac_df = pd.DataFrame(rank_autocorr_data) if rank_autocorr_data else pd.DataFrame()

    # ── Build report ──
    print("\n[6/6] Generating report...")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    if mode == "reversal":
        report_path = ROOT / "reports" / f"reversal_defensive_factor_audit_{ts}.md"
    else:
        report_path = ROOT / "reports" / f"cross_sectional_alpha_report_{ts}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    w = lines.append

    if mode == "reversal":
        w(f"# Reversal / Defensive Factor Audit")
    else:
        w(f"# Cross-Sectional Alpha Phase 1 — Single-Factor IC Scan")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"Period: {start} ~ {end}")
    w(f"Mode: {'SMOKE TEST' if smoke else 'FULL'}")
    w(f"Features evaluated: {len(features_to_run)}")

    # ── Section 1: Data Coverage ──
    w("\n---\n")
    w("## 1. Data Coverage\n")
    w(f"- All trading days in range: {len(analysis_dates)}")
    w(f"- Days with valid records: {len(valid_records)}")
    w(f"- Avg universe size (constituent): {np.mean([r.n_constituent for r in records if r.n_constituent > 0]):.1f}")
    w(f"- Avg eligible after filters: {np.mean([r.n_after_filters for r in records if r.n_after_filters > 0]):.1f}")
    w(f"- Daily tradable count (median): {daily_n_tradable_s.median():.0f}")
    w(f"- Daily tradable count (P25/P75): {daily_n_tradable_s.quantile(0.25):.0f} / {daily_n_tradable_s.quantile(0.75):.0f}")
    w(f"- Daily tradable count (min/max): {daily_n_tradable_s.min():.0f} / {daily_n_tradable_s.max():.0f}")

    w("\n### Exclusion Reason Counts (cumulative)\n")
    w(f"| Reason | Total Excluded |")
    w(f"|--------|---------------:|")
    for reason, count in sorted(total_excluded.items(), key=lambda x: -x[1]):
        w(f"| {reason} | {count} |")

    # ── Section 2: Per-Feature IC ──
    w("\n---\n")
    w("## 2. Single-Factor IC Summary\n")

    # Primary label for ranking: fwd_ret_10d
    primary_label = "fwd_ret_10d"

    # Sort features by IC_IR on primary label
    feature_ic_ranking = []
    for fname in features_to_run:
        if fname not in ic_results or "error" in ic_results.get(fname, {}):
            continue
        lbl_data = ic_results[fname].get(primary_label, {})
        if "error" in lbl_data:
            feature_ic_ranking.append((fname, 0, None))
        else:
            feature_ic_ranking.append((fname, lbl_data.get("mean_ic", 0), lbl_data))

    feature_ic_ranking.sort(key=lambda x: abs(x[1]), reverse=True)

    w(f"\n### IC on {primary_label} (primary label)\n")
    w(f"| Feature | Mean IC | IC IR | IC>0 Ratio | N Days | Train IC | Val IC | Test IC |")
    w(f"|---------|---------|-------|------------|--------|----------|--------|---------|")
    for fname, _, lbl_data in feature_ic_ranking:
        if lbl_data is None:
            w(f"| {fname} | N/A | N/A | N/A | N/A | N/A | N/A | N/A |")
            continue
        w(f"| {fname} | {lbl_data['mean_ic']:.4f} | {lbl_data['ic_ir']:.3f} | "
          f"{lbl_data['ic_pos_ratio']:.1%} | {lbl_data['n_daily_obs']} | "
          f"{lbl_data.get('train_ic') or 0:.4f} | {lbl_data.get('val_ic') or 0:.4f} | "
          f"{lbl_data.get('test_ic') or 0:.4f} |")

    # ── Year-by-year IC ──
    w("\n### Year-by-Year IC (fwd_ret_10d)\n")
    all_years = sorted(set().union(*[
        ic_results[f].get(primary_label, {}).get("yearly", {}).keys()
        for f in features_to_run if f in ic_results
    ]))
    if all_years:
        w(f"| Feature | " + " | ".join(f"{y}" for y in all_years) + " |")
        w(f"|---------|" + "|".join("------" for _ in all_years) + "|")
        for fname, _, lbl_data in feature_ic_ranking:
            if lbl_data is None:
                continue
            yearly = lbl_data.get("yearly", {})
            cells = []
            for y in all_years:
                yd = yearly.get(y, {})
                cells.append(f"{yd.get('mean_ic', 0):.4f}" if yd else "N/A")
            w(f"| {fname} | " + " | ".join(cells) + " |")

    # ── All labels IC matrix ──
    w("\n### Mean IC Across All Labels\n")
    w(f"| Feature | " + " | ".join(f"{l[0]}" for l in LABEL_SPECS) + " |")
    w(f"|---------|" + "|".join("------" for _ in LABEL_SPECS) + "|")
    for fname, _, _ in feature_ic_ranking:
        cells = []
        for lbl_name, _ in LABEL_SPECS:
            lbl_data = ic_results.get(fname, {}).get(lbl_name, {})
            if "error" in lbl_data:
                cells.append("N/A")
            else:
                cells.append(f"{lbl_data.get('mean_ic', 0):.4f}")
        w(f"| {fname} | " + " | ".join(cells) + " |")

    # ── Section 3: Quantile Bucket ──
    w("\n---\n")
    w("## 3. Quantile Bucket Analysis (fwd_ret_10d)\n")
    w("Q1 = top 20% rank, Q5 = bottom 20% rank\n")

    for fname, _, _ in feature_ic_ranking:
        qres = quantile_results.get(fname, {})
        if "error" in qres:
            w(f"\n### {fname}: {qres['error']}\n")
            continue

        q_stats = qres.get("q_stats", {})
        if not q_stats:
            w(f"\n### {fname}: No quantile data\n")
            continue

        w(f"\n### {fname}\n")
        w(f"| Bucket | N | Mean Ret | Median Ret | Std | Hit Rate | MAE |")
        w(f"|--------|---|----------|------------|-----|----------|-----|")
        for bucket in ["Q1_top", "Q2", "Q3_mid", "Q4", "Q5_bottom"]:
            if bucket not in q_stats:
                continue
            qs = q_stats[bucket]
            w(f"| {bucket} | {qs['n']} | {qs['mean_fwd_ret_10d']:.4%} | "
              f"{qs['median_fwd_ret_10d']:.4%} | {qs['std_fwd_ret_10d']:.4%} | "
              f"{qs.get('hit_rate', 0) or 0:.1%} | {qs.get('mean_mae_10d', 0) or 0:.4%} |")

        spread = qres.get("q1_q5_spread")
        t_stat = qres.get("t_stat")
        if spread is not None:
            w(f"\n  **Q1-Q5 spread**: {spread:.4%}  (t={t_stat:.2f})" if t_stat else f"\n  **Q1-Q5 spread**: {spread:.4%}")
        # MAE comparison
        if "Q1_top" in q_stats and "Q5_bottom" in q_stats:
            mae1 = q_stats["Q1_top"].get("mean_mae_10d", 0) or 0
            mae5 = q_stats["Q5_bottom"].get("mean_mae_10d", 0) or 0
            mae_ratio = mae1 / mae5 if mae5 > 0 else float("inf")
            w(f"  **MAE ratio Q1/Q5**: {mae_ratio:.2f}")

    # ── Section 4: Volatility Features — Bidirectional ──
    w("\n---\n")
    w("## 4. Volatility Features — Bidirectional Assessment\n")
    vol_features = ["vol_20d", "hl_range_20d"]
    for fname in vol_features:
        if fname not in ic_results:
            continue
        lbl_data = ic_results[fname].get(primary_label, {})
        if "error" in lbl_data:
            w(f"\n### {fname}: {lbl_data.get('error', 'N/A')}\n")
            continue
        mean_ic = lbl_data.get("mean_ic", 0)
        direction = "high-vol preferred (positive IC)" if mean_ic > 0 else "low-vol preferred (negative IC)"
        w(f"\n### {fname}")
        w(f"- Mean IC: {mean_ic:.4f} → **{direction}**")
        w(f"- IC IR: {lbl_data.get('ic_ir', 0):.3f}")
        w(f"- IC>0 ratio: {lbl_data.get('ic_pos_ratio', 0):.1%}")

    # ── Section 5: Rank Distribution & Discrimination ──
    w("\n---\n")
    w("## 5. Cross-Sectional Rank Discrimination\n")

    # Per-feature, what fraction of days have meaningful spread in fwd_ret across quantiles?
    for fname, _, lbl_data in feature_ic_ranking[:5]:
        if lbl_data is None:
            continue
        qres = quantile_results.get(fname, {})
        q_stats = qres.get("q_stats", {})
        if "Q1_top" in q_stats and "Q5_bottom" in q_stats:
            spread = qres.get("q1_q5_spread", 0) or 0
        else:
            spread = 0
        # Check daily IC std vs mean: if CV(IC) is high, discrimination is noisy
        ic_std = lbl_data.get("ic_std", 0)
        ic_mean = abs(lbl_data.get("mean_ic", 0))
        ic_cv = ic_std / ic_mean if ic_mean > 0 else float("inf")
        w(f"- **{fname}**: Q1-Q5 spread={spread:.4%}, IC CV={ic_cv:.2f}, "
          f"IC>0={lbl_data.get('ic_pos_ratio', 0):.1%}")

    # ── Rank autocorrelation ──
    w("\n### Rank Autocorrelation (Top20% Stay Rate)\n")
    if len(rac_df) > 0:
        w(f"| Feature | Avg Top20% Overlap | Median | P25 |")
        w(f"|---------|-------------------|--------|-----|")
        for fname in features_to_run:
            f_rac = rac_df[rac_df["feature"] == fname]
            if len(f_rac) == 0:
                continue
            w(f"| {fname} | {f_rac['overlap_pct'].mean():.1%} | "
              f"{f_rac['overlap_pct'].median():.1%} | {f_rac['overlap_pct'].quantile(0.25):.1%} |")
    else:
        w("No rank autocorrelation data available.")

    # ── Section 6: vs trend_breakout v2 ──
    w("\n---\n")
    w("## 6. Comparison with trend_breakout v2\n")

    w("\n### 6.1 Within-day Discrimination")
    w("trend_breakout v2: 94.2% days N vs N+1 score gap ≈ 0")
    w("cross-sectional: Percentile rank guarantees uniform distribution per day.")
    w("Key question: Does rank translate to fwd_ret difference?")
    for fname, _, lbl_data in feature_ic_ranking[:3]:
        if lbl_data is None:
            continue
        ic = lbl_data.get("mean_ic", 0)
        ic_pos = lbl_data.get("ic_pos_ratio", 0)
        w(f"- {fname}: IC={ic:.4f}, IC>0={ic_pos:.1%} → "
          f"{'BETTER' if ic_pos > 0.55 else 'MARGINAL' if ic_pos > 0.50 else 'NO BETTER'}")

    w("\n### 6.2 Next-day Stability (vs 80.7% dropout)")
    w("trend_breakout v2: 80.7% new entries gone next day, avg stay=0.2d")
    if len(rac_df) > 0:
        for fname in features_to_run[:3]:
            f_rac = rac_df[rac_df["feature"] == fname]
            if len(f_rac) == 0:
                continue
            w(f"- {fname}: Top20% avg overlap={f_rac['overlap_pct'].mean():.1%} → "
              f"{'MUCH BETTER' if f_rac['overlap_pct'].mean() > 0.5 else 'BETTER' if f_rac['overlap_pct'].mean() > 0.3 else 'SIMILARLY UNSTABLE'}")

    w("\n### 6.3 Year Stability")
    w("trend_breakout v2: B weak in 2023 (score_high=0.80 cost)")
    w("cross-sectional: checking if IC consistent across years...")
    for fname, _, lbl_data in feature_ic_ranking[:3]:
        if lbl_data is None:
            continue
        yearly = lbl_data.get("yearly", {})
        yrs_pos = sum(1 for y, yd in yearly.items() if yd.get("mean_ic", 0) > 0)
        yrs_total = len(yearly)
        w(f"- {fname}: {yrs_pos}/{yrs_total} years IC>0 → "
          f"{'STABLE' if yrs_pos >= yrs_total * 0.75 else 'UNSTABLE' if yrs_pos <= yrs_total * 0.5 else 'MIXED'}")

    # ── Section 7: Pass/Stop Verdict ──
    w("\n---\n")
    w("## 7. Pass / Stop Verdict\n")

    passing_features = []
    failing_features = []
    marginal_features = []

    # ── Criteria differ by mode ──
    if mode == "reversal":
        ic_min = 0.02
        ic_ir_min = 0.15
    else:
        ic_min = 0.0
        ic_ir_min = 0.0

    for fname, _, lbl_data in feature_ic_ranking:
        if lbl_data is None:
            failing_features.append((fname, "No IC data"))
            continue

        qres = quantile_results.get(fname, {})
        reasons = []
        mean_ic = lbl_data.get("mean_ic", 0)

        if mode == "reversal":
            # C1: mean IC >= 0.02
            if abs(mean_ic) < ic_min:
                reasons.append(f"C1: |IC|={abs(mean_ic):.4f} < {ic_min}")

            # C2: IC IR >= 0.15
            ic_ir_val = abs(lbl_data.get("ic_ir", 0))
            if ic_ir_val < ic_ir_min:
                reasons.append(f"C2: |IC IR|={ic_ir_val:.3f} < {ic_ir_min}")

            # C3: validation and test both positive
            val_ic = lbl_data.get("val_ic") or 0
            test_ic = lbl_data.get("test_ic") or 0
            if val_ic <= 0:
                reasons.append(f"C3: val IC={val_ic:.4f} <= 0")
            if test_ic <= 0:
                reasons.append(f"C3: test IC={test_ic:.4f} <= 0")

            # C4: at least 3/5 years IC > 0
            yearly = lbl_data.get("yearly", {})
            yrs_pos = sum(1 for yd in yearly.values() if yd.get("mean_ic", 0) > 0)
            yrs_total = len(yearly)
            if yrs_total >= 3 and yrs_pos < 3:
                reasons.append(f"C4: Only {yrs_pos}/{yrs_total} years IC>0")

            # C5: Q1-Q5 spread > 0 and t > 1.5
            spread = qres.get("q1_q5_spread")
            t_stat = qres.get("t_stat")
            if spread is None:
                reasons.append("C5: No Q1-Q5 spread data")
            elif spread <= 0:
                reasons.append(f"C5: spread={spread:.4%} <= 0")
            elif t_stat is not None and t_stat < 1.5:
                reasons.append(f"C5: t-stat={t_stat:.2f} < 1.5")

            # C6: top bucket MAE not worse
            q_stats = qres.get("q_stats", {})
            if "Q1_top" in q_stats and "Q5_bottom" in q_stats:
                mae1 = q_stats["Q1_top"].get("mean_mae_10d", 0) or 0
                mae5 = q_stats["Q5_bottom"].get("mean_mae_10d", 0) or 0
                if mae5 > 0 and mae1 > mae5 * 1.5:
                    reasons.append(f"C6: Q1 MAE ({mae1:.4f}) >> Q5 MAE ({mae5:.4f})")
        else:
            # Original Phase 1 criteria
            spread = qres.get("q1_q5_spread")
            t_stat = qres.get("t_stat")
            if spread is None or spread == 0:
                reasons.append("P1: No Q1-Q5 spread")
            elif t_stat is not None and t_stat < 1.5:
                reasons.append(f"P1: t-stat={t_stat:.2f} < 1.5")

            ic_pos = lbl_data.get("ic_pos_ratio", 0)
            if ic_pos < 0.50:
                reasons.append(f"P2: IC>0 ratio={ic_pos:.1%}")

            yearly = lbl_data.get("yearly", {})
            yrs_pos = sum(1 for yd in yearly.values() if yd.get("mean_ic", 0) > 0)
            yrs_total = len(yearly)
            if yrs_total >= 3 and yrs_pos < 3:
                reasons.append(f"P3: Only {yrs_pos}/{yrs_total} years IC>0")

            q_stats = qres.get("q_stats", {})
            if "Q1_top" in q_stats and "Q5_bottom" in q_stats:
                mae1 = q_stats["Q1_top"].get("mean_mae_10d", 0) or 0
                mae5 = q_stats["Q5_bottom"].get("mean_mae_10d", 0) or 0
                if mae5 > 0 and mae1 > mae5 * 1.5:
                    reasons.append(f"P4: Q1 MAE ({mae1:.4f}) >> Q5 MAE ({mae5:.4f})")

            n_days = lbl_data.get("n_daily_obs", 0)
            if n_days < 30:
                reasons.append(f"P5: Only {n_days} days with valid IC")

            train_ic = lbl_data.get("train_ic") or 0
            val_ic = lbl_data.get("val_ic") or 0
            test_ic = lbl_data.get("test_ic") or 0
            if val_ic != 0 and abs(val_ic) > 2 * max(abs(train_ic), abs(test_ic)):
                reasons.append(f"P6: 2024-dominant (val IC={val_ic:.4f})")

        if not reasons:
            passing_features.append((fname, lbl_data, qres))
        elif len(reasons) <= 1:
            marginal_features.append((fname, reasons, lbl_data))
        else:
            failing_features.append((fname, "; ".join(reasons)))

    w("\n### Passing Features\n")
    if passing_features:
        for fname, lbl_data, _ in passing_features:
            w(f"- **{fname}**: IC={lbl_data.get('mean_ic', 0):.4f}, "
              f"IC IR={lbl_data.get('ic_ir', 0):.3f}")
    else:
        w("None.")

    w("\n### Marginal Features\n")
    if marginal_features:
        for fname, reasons, lbl_data in marginal_features:
            w(f"- **{fname}**: IC={lbl_data.get('mean_ic', 0):.4f} — {reasons[0]}")
    else:
        w("None.")

    w("\n### Failing Features\n")
    if failing_features:
        for fname, reason in failing_features:
            w(f"- **{fname}**: {reason}")
    else:
        w("None.")

    # ── Overall verdict ──
    w("\n### Overall Verdict\n")
    if mode == "reversal":
        n_pass = len(passing_features)
        best_ic_ir = max([abs(lbl_data.get("ic_ir", 0)) for _, lbl_data, _ in passing_features]) if passing_features else 0
        if n_pass >= 3 and best_ic_ir >= 0.2:
            w(f"**A: Valid** — {n_pass} reversal/defensive factors pass all criteria "
              f"(max IC IR={best_ic_ir:.3f}). Recommend Phase 2 composite research.")
        elif n_pass >= 1:
            w(f"**B: Weak Signal** — {n_pass} factor(s) pass minimum criteria but signal strength "
              f"insufficient (max IC IR={best_ic_ir:.3f}). Continue searching for stronger alpha sources.")
        else:
            w("**C: Stop** — No reversal/defensive factor passes all criteria. "
              "Cross-sectional alpha on HS300 insufficient. "
              "Consider pivoting to alternative strategy structures "
              "(e.g., event-driven, pair-trading, multi-universe).")
    else:
        if len(passing_features) >= 3:
            w(f"**PASS** — {len(passing_features)} features pass. Recommend Phase 2 composite evaluation.")
        elif len(passing_features) >= 1:
            w(f"**MARGINAL** — Only {len(passing_features)} features pass. "
              f"Phase 2 may have limited upside but still worth exploring composite with passing features.")
        else:
            w("**STOP** — No single feature passes all conditions. "
              "Cross-sectional alpha on HS300 universe insufficient for further investment. "
              "Consider alternative alpha sources or universe expansion.")

    if passing_features:
        w(f"\nRecommended Phase 2 features: {', '.join(f[0] for f in passing_features)}")

    # ── Extra checks (reversal mode only) ──
    if mode == "reversal":
        w("\n---\n")
        w("## 7b. Extra Robustness Checks\n")

        # 2024 exclusion
        w("\n### 7b.1 Excluding 2024 (924 market shock)\n")
        w("| Feature | Full IC | IC excl 2024 | Stable? |")
        w("|---------|---------|-------------|---------|")
        for fname, _, lbl_data in feature_ic_ranking:
            if lbl_data is None:
                continue
            yearly = lbl_data.get("yearly", {})
            yrs_excl_2024 = {y: d for y, d in yearly.items() if y != 2024}
            if len(yrs_excl_2024) >= 2:
                excl_ic = np.mean([d["mean_ic"] for d in yrs_excl_2024.values()])
                full_ic = lbl_data.get("mean_ic", 0)
                yrs_pos_excl = sum(1 for d in yrs_excl_2024.values() if d["mean_ic"] > 0)
                stable = "YES" if yrs_pos_excl >= len(yrs_excl_2024) * 0.6 else "WEAK"
                w(f"| {fname} | {full_ic:.4f} | {excl_ic:.4f} | {stable} |")

        # 2022 bear vs 2025-2026
        w("\n### 7b.2 Regime Separation: 2022 Bear vs 2025-2026\n")
        w("| Feature | 2022 IC | 2025 IC | 2026 IC | Bear→Bull Consistent? |")
        w("|---------|---------|---------|---------|----------------------|")
        for fname, _, lbl_data in feature_ic_ranking:
            if lbl_data is None:
                continue
            yearly = lbl_data.get("yearly", {})
            ic22 = yearly.get(2022, {}).get("mean_ic", 0) or 0
            ic25 = yearly.get(2025, {}).get("mean_ic", 0) or 0
            ic26 = yearly.get(2026, {}).get("mean_ic", 0) or 0
            # Consistent if all same sign and > 0
            signs = [1 if x > 0.005 else -1 if x < -0.005 else 0 for x in [ic22, ic25, ic26]]
            consistent = "YES" if len(set(signs)) == 1 and signs[0] == 1 else "FLIPS" if len(set(signs)) > 1 else "NO"
            w(f"| {fname} | {ic22:.4f} | {ic25:.4f} | {ic26:.4f} | {consistent} |")

        # Low vol: alpha or just low risk?
        w("\n### 7b.3 Low-Volatility: Alpha or Just Low Risk?\n")
        for fname in ["low_vol_20d", "low_hl_range_20d"]:
            if fname not in quantile_results:
                continue
            qres = quantile_results[fname]
            q_stats = qres.get("q_stats", {})
            if "Q1_top" in q_stats and "Q5_bottom" in q_stats:
                q1_ret = q_stats["Q1_top"]["mean_fwd_ret_10d"]
                q5_ret = q_stats["Q5_bottom"]["mean_fwd_ret_10d"]
                q1_mae = q_stats["Q1_top"].get("mean_mae_10d", 0) or 0
                q5_mae = q_stats["Q5_bottom"].get("mean_mae_10d", 0) or 0
                q1_hit = q_stats["Q1_top"].get("hit_rate", 0) or 0
                q5_hit = q_stats["Q5_bottom"].get("hit_rate", 0) or 0
                return_per_mae_q1 = q1_ret / q1_mae if q1_mae > 0 else 0
                return_per_mae_q5 = q5_ret / q5_mae if q5_mae > 0 else 0
                w(f"\n**{fname}**:")
                w(f"- Q1 (low vol): ret={q1_ret:.4%}, MAE={q1_mae:.4%}, "
                  f"ret/MAE={return_per_mae_q1:.4f}, hit={q1_hit:.1%}")
                w(f"- Q5 (high vol): ret={q5_ret:.4%}, MAE={q5_mae:.4%}, "
                  f"ret/MAE={return_per_mae_q5:.4f}, hit={q5_hit:.1%}")
                if return_per_mae_q1 > return_per_mae_q5 * 1.1:
                    w(f"- **Alpha**: low-vol has better risk-adjusted return")
                elif abs(return_per_mae_q1 - return_per_mae_q5) < 0.01:
                    w(f"- **Just low risk**: risk-adjusted return similar to high-vol")
                else:
                    w(f"- **High-vol better**: risk-adjusted return favors high-vol")

    # ── Section 8: Key Diagnostic Metrics ──
    w("\n---\n")
    w("## 8. Key Diagnostic Metrics (vs trend_breakout v2)\n")

    total_obs = sum(len(ic_results.get(f, {}).get(primary_label, {}).get("full_df", pd.DataFrame()))
                     for f in features_to_run if f in ic_results)
    avg_n_tradable = daily_n_tradable_s.median() if len(daily_n_tradable_s) > 0 else 0

    w(f"| Metric | trend_breakout v2 | cross-sectional | Verdict |")
    w(f"|--------|-------------------|-----------------|---------|")
    w(f"| Avg daily candidates | ~4 | {avg_n_tradable:.0f} | {'BETTER' if avg_n_tradable > 20 else 'SIMILAR'} |")
    w(f"| Within-day discrimination | 94% gap≈0 | Uniform rank | GUARANTEED BETTER |")
    w(f"| Next-day turnover | 78% | See autocorr above | — |")
    w(f"| False signal rate | 48.4% FB | N/A (no breakout) | DIFFERENT PARADIGM |")

    # ── Write report ──
    report = "\n".join(lines)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    # Also write IC summary CSV
    csv_path = report_path.with_suffix(".csv")
    csv_rows = []
    for fname, _, lbl_data in feature_ic_ranking:
        if lbl_data is None:
            continue
        csv_rows.append({
            "feature": fname,
            "mean_ic": lbl_data.get("mean_ic"),
            "ic_ir": lbl_data.get("ic_ir"),
            "ic_pos_ratio": lbl_data.get("ic_pos_ratio"),
            "n_days": lbl_data.get("n_daily_obs"),
            "train_ic": lbl_data.get("train_ic"),
            "val_ic": lbl_data.get("val_ic"),
            "test_ic": lbl_data.get("test_ic"),
        })
    if csv_rows:
        pd.DataFrame(csv_rows).to_csv(csv_path, index=False)
        print(f"  IC summary CSV: {csv_path}")

    print(f"\nReport saved to: {report_path}")

    # Print report to stdout
    print("\n" + report)

    return str(report_path)


def main():
    import argparse
    p = argparse.ArgumentParser(description="Cross-sectional alpha Phase 1 IC scan")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2026-05-15")
    p.add_argument("--smoke", action="store_true", help="Smoke test: 1 month, 3 features")
    p.add_argument("--mode", default="momentum", choices=["momentum", "reversal"],
                   help="Analysis mode: momentum (default) or reversal/defensive")
    args = p.parse_args()

    if args.smoke:
        start = "2022-04-01"
        end = "2022-04-30"
        features = SMOKE_FEATURES
        smoke = True
        negate_map = None
        mode = "momentum"
    elif args.mode == "reversal":
        start = args.start
        end = args.end
        features = REVERSAL_ALL_FEATURES
        smoke = False
        negate_map = REVERSAL_NEGATE_MAP
        mode = "reversal"
    else:
        start = args.start
        end = args.end
        features = ALL_FEATURES
        smoke = False
        negate_map = None
        mode = "momentum"

    run_analysis(start, end, features, smoke=smoke,
                 negate_map=negate_map, mode=mode)


if __name__ == "__main__":
    main()

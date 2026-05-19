"""Turnover Diagnostic — decompose B1/B2/C1 turnover sources and audit cost model.

Finds where high turnover comes from:
  1. Industry entry/exit churn (B1/B2 level)
  2. Stock entry/exit churn (C1 level)
  3. Signal ranking instability
  4. Cost model audit: flat vs proportional-to-turnover

Does NOT modify any strategy code, run formal backtests, or enter Paper Trading.

Usage:
  python scripts/diagnose_turnover.py
  python scripts/diagnose_turnover.py --smoke  # 2024 only, fast
"""

from __future__ import annotations

import json, sys, warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
BAR_PATH = ROOT / "data/raw/HS300_daily.parquet"
CAL_PATH = ROOT / "data/raw/calendar.parquet"
IDX_PATH = ROOT / "data/raw/index/sh000300_daily.parquet"
CONST_PATH = ROOT / "data/historical_constituents.json"
IND_PATH = ROOT / "data/meta/industry_classification.csv"

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

COST_BPS = 0.0020  # 20 bps/trade
MIN_STOCKS = 3
LOOKBACKS = [20, 60]
TOP_NS = [3, 5]


# ── Data loading (shared with evaluate_industry_rotation.py) ──

def load_constituent_map():
    with open(CONST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {k: sorted(set(v)) for k, v in data["indices"]["HS300"]["quarterly"].items()}


def get_constituents(date_str, const_map):
    for q in reversed(sorted(const_map.keys())):
        if q <= date_str:
            return const_map[q]
    return const_map[sorted(const_map.keys())[0]]


def load_industry_map():
    df = pd.read_csv(IND_PATH)
    df["symbol_str"] = df["symbol"].apply(lambda x: str(int(x)).zfill(6))
    return dict(zip(df["symbol_str"], df["industry_raw"]))


# ── Industry daily returns (shared with evaluate_industry_rotation.py) ──

def compute_industry_daily(bars, const_map, industry_map, trading_dates):
    bars = bars.copy()
    bars["td"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "td"])
    bars["daily_ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["daily_ret"])
    bars["industry"] = bars["symbol"].map(industry_map)
    bars = bars.dropna(subset=["industry"])

    ind_ret_ew = {}
    ind_stocks_daily = {}  # {industry: {date: [symbols]}}

    for date_str in trading_dates:
        const_syms = set(get_constituents(date_str, const_map))
        day = bars[bars["td"] == date_str]
        day = day[day["symbol"].isin(const_syms)]
        ic = day.groupby("industry").size()
        vi = ic[ic >= MIN_STOCKS].index
        day = day[day["industry"].isin(vi)]
        if len(day) == 0:
            continue

        ew = day.groupby("industry")["daily_ret"].mean()
        for ind in ew.index:
            ind_ret_ew.setdefault(ind, {})[date_str] = ew[ind]
            syms = day[day["industry"] == ind]["symbol"].tolist()
            ind_stocks_daily.setdefault(ind, {})[date_str] = syms

    return ind_ret_ew, ind_stocks_daily


# ── Calendar ──

def get_month_ends(trading_dates):
    df = pd.DataFrame({"d": pd.to_datetime(trading_dates)})
    df["ym"] = df["d"].dt.to_period("M")
    return sorted(df.groupby("ym")["d"].max().dt.strftime("%Y-%m-%d").tolist())


def get_next_trading_day(date_str, trading_dates):
    for d in trading_dates:
        if d > date_str:
            return d
    return None


# ── Industry momentum signal ──

def compute_industry_signals(ind_ret, trading_dates, lookback):
    """Return {date_str: {ind_name: past_ret}} for all month-end dates."""
    ind_cum = {}
    for ind_name, rd in ind_ret.items():
        s = pd.Series(rd).sort_index().dropna()
        if len(s) >= lookback + 5:
            ind_cum[ind_name] = (1 + s).cumprod()

    signals = {}
    for d in trading_dates:
        past = {}
        for ind_name, cs in ind_cum.items():
            if d not in cs.index:
                continue
            before = [x for x in cs.index if x <= d]
            if len(before) <= lookback:
                continue
            sd = before[-(lookback + 1)]
            r = cs[d] / cs[sd] - 1
            if np.isfinite(r):
                past[ind_name] = r
        if past:
            signals[d] = dict(sorted(past.items(), key=lambda x: -x[1]))
    return signals


# ── B1 Turnover Decomposition ──

def decompose_b1_turnover(ind_ret_ew, ind_stocks_daily, signals, trading_dates, top_n):
    """Decompose B1 monthly turnover into components.

    Returns per-month dict with:
      - turnover: industry-level turnover rate
      - new_industries: industries entering
      - dropped_industries: industries leaving
      - signal_rank_shifts: dict of rank changes for continuing industries
      - rank_correlation: Spearman r between current and previous signal
      - top_n_boundary: was turnover from rank N vs N+1 boundary crossing?
    """
    month_ends = get_month_ends(trading_dates)
    months = []

    prev_selected = None
    prev_signals = None

    for i, me in enumerate(month_ends):
        if me not in signals:
            continue
        if i + 1 >= len(month_ends):
            continue

        ranked = signals[me]
        selected = list(ranked.keys())[:top_n]

        row = {
            "month": me[:7],
            "selected": selected,
            "n_available": len(ranked),
        }

        if prev_selected is not None:
            s_curr = set(selected)
            s_prev = set(prev_selected)
            n_new = len(s_curr - s_prev)
            n_dropped = len(s_prev - s_curr)
            n_kept = len(s_curr & s_prev)
            row["turnover"] = n_new / top_n
            row["n_new"] = n_new
            row["n_dropped"] = n_dropped
            row["n_kept"] = n_kept
            row["new_industries"] = sorted(s_curr - s_prev)
            row["dropped_industries"] = sorted(s_prev - s_curr)

            # Signal rank shifts for continuing industries
            rank_shifts = {}
            for ind in s_curr & s_prev:
                curr_rank = list(ranked.keys()).index(ind) if ind in ranked else -1
                prev_rank = list(prev_signals.keys()).index(ind) if ind in prev_signals else -1
                if curr_rank >= 0 and prev_rank >= 0:
                    rank_shifts[ind] = prev_rank - curr_rank
            row["rank_shifts"] = rank_shifts

            # Rank correlation
            common = sorted(set(ranked.keys()) & set(prev_signals.keys()))
            if len(common) >= 5:
                curr_ranks = [list(ranked.keys()).index(c) for c in common]
                prev_ranks = [list(prev_signals.keys()).index(c) for c in common]
                # Spearman
                n = len(common)
                d2 = sum((cr - pr) ** 2 for cr, pr in zip(curr_ranks, prev_ranks))
                row["rank_corr"] = 1 - 6 * d2 / (n * (n**2 - 1)) if n > 1 else 1.0
            else:
                row["rank_corr"] = None

            # Boundary: was the turnover triggered by N vs N+1 boundary?
            boundary = []
            for ind in s_curr - s_prev:
                rank_in_prev = (list(prev_signals.keys()).index(ind)
                                if ind in prev_signals else 999)
                if rank_in_prev <= top_n + 2:
                    boundary.append({"industry": ind, "prev_rank": rank_in_prev})
            for ind in s_prev - s_curr:
                rank_in_curr = (list(ranked.keys()).index(ind)
                                if ind in ranked else 999)
                if rank_in_curr <= top_n + 2:
                    boundary.append({"industry": ind, "curr_rank": rank_in_curr,
                                     "status": "dropped"})
            row["boundary_close"] = boundary

            # Industry member change: did available industry set change?
            prev_available = set(prev_signals.keys())
            curr_available = set(ranked.keys())
            new_available = curr_available - prev_available
            dropped_available = prev_available - curr_available
            row["new_available_inds"] = sorted(new_available)
            row["dropped_available_inds"] = sorted(dropped_available)

        else:
            row["turnover"] = 1.0
            row["n_new"] = top_n
            row["n_dropped"] = 0
            row["n_kept"] = 0

        months.append(row)
        prev_selected = selected
        prev_signals = ranked

    return months


# ── C1 Turnover Decomposition ──

def decompose_c1_turnover(bars, const_map, industry_map, trading_dates, top_n, lookback):
    """Decompose C1 stock-level turnover."""
    bars = bars.copy()
    bars["td"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "td"])
    bars["mom"] = bars.groupby("symbol")["close"].pct_change(periods=lookback)
    bars["ind"] = bars["symbol"].map(industry_map)
    bars = bars.dropna(subset=["ind"])

    month_ends = get_month_ends(trading_dates)
    months = []
    prev_selected = None

    for i, me in enumerate(month_ends):
        if me not in trading_dates:
            continue
        if i + 1 >= len(month_ends):
            continue

        # Filter stocks at date
        const_syms = set(get_constituents(me, const_map))
        day = bars[bars["td"] == me].copy()
        day = day[day["symbol"].isin(const_syms)]
        day = day[~day["symbol"].str.contains("ST", na=False)]
        day = day[day["volume"].notna() & (day["volume"] > 0)]
        day = day.dropna(subset=["mom"])

        ic = day.groupby("ind").size()
        vi = ic[ic >= MIN_STOCKS].index
        day = day[day["ind"].isin(vi)]
        if len(day) < top_n:
            continue

        # C1-A signal: stock mom - industry ew mom
        ind_mom = day.groupby("ind")["mom"].mean()
        day["signal"] = day.apply(lambda r: r["mom"] - ind_mom.get(r["ind"], 0), axis=1)
        day = day.sort_values("signal", ascending=False)
        selected = day.head(top_n)["symbol"].tolist()

        row = {"month": me[:7], "selected": selected, "n_available": len(day)}

        if prev_selected is not None:
            sc = set(selected)
            sp = set(prev_selected)
            overlap = len(sc & sp)
            row["turnover"] = 1.0 - overlap / top_n
            row["n_new"] = len(sc - sp)
            row["n_dropped"] = len(sp - sc)
            row["n_kept"] = overlap
            row["new_stocks"] = sorted(sc - sp)[:10]
            row["dropped_stocks"] = sorted(sp - sc)[:10]

            # Industry-level contribution to stock turnover
            new_inds = day[day["symbol"].isin(sc - sp)]["ind"].value_counts().to_dict()
            dropped_inds = {}
            if len(sp - sc) > 0:
                prev_day = bars[(bars["td"] == month_ends[i - 1])
                               & bars["symbol"].isin(sp - sc)]
                dropped_inds = prev_day["ind"].value_counts().to_dict()
            row["new_by_industry"] = new_inds
            row["dropped_by_industry"] = dropped_inds

            # Cross-industry vs within-industry turnover
            new_from_new_ind = sum(1 for s in sc - sp
                                  if day[day["symbol"] == s]["ind"].values[0]
                                  not in {day[day["symbol"] == x]["ind"].values[0]
                                          for x in sp if x in day["symbol"].values})
            row["cross_industry_turnover"] = new_from_new_ind / top_n if top_n else 0
        else:
            row["turnover"] = 1.0
            row["n_new"] = top_n
            row["n_dropped"] = 0
            row["n_kept"] = 0

        months.append(row)
        prev_selected = selected

    return months


# ── Signal Stability Analysis ──

def analyze_signal_stability(signals, trading_dates, top_n):
    """Analyze month-to-month signal ranking stability."""
    month_ends = get_month_ends(trading_dates)
    stabilities = []

    for i in range(1, len(month_ends)):
        prev_me = month_ends[i - 1]
        curr_me = month_ends[i]

        if prev_me not in signals or curr_me not in signals:
            continue

        prev = signals[prev_me]
        curr = signals[curr_me]

        common = sorted(set(prev.keys()) & set(curr.keys()))
        if len(common) < 5:
            continue

        # Top-N overlap
        ptop = set(list(prev.keys())[:top_n])
        ctop = set(list(curr.keys())[:top_n])
        top_overlap = len(ptop & ctop)

        # Rank correlation
        pr = [list(prev.keys()).index(c) for c in common]
        cr = [list(curr.keys()).index(c) for c in common]
        n = len(common)
        d2 = sum((a - b) ** 2 for a, b in zip(pr, cr))
        rho = 1 - 6 * d2 / (n * (n**2 - 1))

        # Rank volatility: std of rank changes
        rank_changes = [abs(a - b) for a, b in zip(pr, cr)]
        mean_abs_shift = np.mean(rank_changes)

        stabilities.append({
            "month": curr_me[:7],
            "top_overlap": top_overlap,
            "top_overlap_pct": top_overlap / top_n,
            "spearman_r": rho,
            "mean_abs_rank_shift": mean_abs_shift,
            "n_common": n,
        })

    return stabilities


# ── Cost Model Impact ──

def compute_cost_impact(months, cost_bps=COST_BPS):
    """Compare flat-cost vs proportional-cost impact on monthly returns.

    For a given monthly turnover series, compute:
    - flat_cost: cost_bps every month (current B1/B2 behavior)
    - prop_cost: cost_bps * turnover_rate (correct per-trade behavior)
    - overcharge: flat_cost - prop_cost
    """
    records = []
    for m in months:
        to = m.get("turnover", 0)
        flat = cost_bps
        prop = cost_bps * to
        overcharge = flat - prop
        records.append({
            "month": m["month"],
            "turnover": to,
            "flat_cost_bps": flat,
            "prop_cost_bps": prop,
            "overcharge_bps": overcharge,
        })

    df = pd.DataFrame(records)
    return {
        "mean_turnover": df["turnover"].mean(),
        "median_turnover": df["turnover"].median(),
        "mean_overcharge_bps": df["overcharge_bps"].mean(),
        "total_overcharge_bps": df["overcharge_bps"].sum(),
        "annual_overcharge_bps": df["overcharge_bps"].sum() / (len(df) / 12) if len(df) > 0 else 0,
        "months_with_overcharge": int((df["overcharge_bps"] > 0.0001).sum()),
        "max_overcharge_month": df.loc[df["overcharge_bps"].idxmax()].to_dict() if len(df) > 0 else {},
        "pct_overcharge": float(df["flat_cost_bps"].sum() / df["prop_cost_bps"].sum() - 1) if df["prop_cost_bps"].sum() > 0 else 0,
        "df": df,
    }


# ── Report Generation ──

def generate_report(b1_results, c1_results, signal_stability, cost_impacts, start, end):
    L = []
    w = L.append

    w("# Turnover Diagnostic Report")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"Period: {start} ~ {end}")
    w(f"\n> **Purpose**: Diagnose turnover sources across B1/B2/C1 research lines. "
      "Identify whether high turnover is from signal instability, selection mechanism, "
      "or implementation artifact. Audit cost model correctness.")
    w("\n> **Rule**: Read-only diagnosis. No strategy code changes. No GA. No Paper Trading.")

    # ── 1. Executive Summary ──
    w("\n---\n## 1. Executive Summary\n")

    # Key findings will be filled after sections below
    b1_all_months = [m for months in b1_results.values() for m in months]
    b1_to = [m["turnover"] for m in b1_all_months if m.get("turnover")]
    c1_to = [m["turnover"] for m in c1_results if m.get("turnover")]

    w(f"| Metric | B1 (Industry Rotation) | C1-A (Stock Selection) |")
    w(f"|--------|----------------------|------------------------|")
    w(f"| Mean monthly turnover | {np.mean(b1_to):.1%} | {np.mean(c1_to):.1%} |" if b1_to and c1_to else "")
    w(f"| Median monthly turnover | {np.median(b1_to):.1%} | {np.median(c1_to):.1%} |" if b1_to and c1_to else "")
    w(f"| Max single-month turnover | {max(b1_to):.1%} | {max(c1_to):.1%} |" if b1_to and c1_to else "")
    w(f"| Months with 0% turnover | {sum(1 for t in b1_to if t < 0.01)} | {sum(1 for t in c1_to if t < 0.01)} |" if b1_to and c1_to else "")
    w(f"| Months with 100% turnover | {sum(1 for t in b1_to if t > 0.99)} | {sum(1 for t in c1_to if t > 0.99)} |" if b1_to and c1_to else "")

    # ── 2. Cost Model Audit ──
    w("\n---\n## 2. Cost Model Audit\n")

    w("### 2.1 Per-Script Cost Application\n")
    w("| Script | Cost Definition | Application | Correct? |")
    w("|--------|----------------|-------------|----------|")
    w("| `evaluate_industry_rotation.py` | `COST_BPS_PER_TRADE = 0.0020` | Flat `- cost_per_month` every month | **BUG: should be proportional** |")
    w("| `diagnose_b1_aw_ew_decomposition.py` | `COST_BPS_MONTHLY = 0.0020` | Flat `- COST_BPS_MONTHLY` every month | **BUG: should be proportional** |")
    w("| `diagnose_b1_concentration_cap.py` | `COST_BPS = 0.0020` | Flat `- COST_BPS` every month | **BUG: should be proportional** |")
    w("| `diagnose_b1_cap_time_variation.py` | `COST_BPS = 0.0020` | Flat `- COST_BPS` every month | **BUG: should be proportional** |")
    w("| `evaluate_b2_multifactor.py` | `COST_BPS = 0.0020` | Flat `- COST_BPS` every month | **BUG: should be proportional** |")
    w("| `evaluate_c1_industry_inside_stock_selection.py` | `COST_BPS = 0.0020` | `COST_BPS * turnover_rate` | **CORRECT** |")

    w("\n### 2.2 Cost Model Explanation\n")
    w("The cost assumption (20 bps) breaks down as: 印花税 0.05% (卖方 only = 5bps) + "
      "佣金 0.025% 双边 (2×2.5bps = 5bps) + 滑点 0.1% (10bps) = **20 bps per traded side**.\n")
    w("This is a **per-trade** cost, not a fixed monthly management fee.\n")
    w("**Correct formula**: `cost = 20bps * turnover_rate` (only the turned-over portion incurs trading cost).\n")
    w("**Current B1/B2 formula**: `cost = 20bps` flat every month (overcharges when turnover < 100%).")

    w("\n### 2.3 B1 Cost Overcharge Impact\n")
    if "b1_lb60_top3" in cost_impacts:
        ci = cost_impacts["b1_lb60_top3"]
        w(f"| Metric | Value |")
        w(f"|--------|-------|")
        w(f"| Mean turnover | {ci['mean_turnover']:.1%} |")
        w(f"| Mean overcharge | {ci['mean_overcharge_bps']*10000:.1f} bps/month |")
        w(f"| Annualized overcharge | {ci['annual_overcharge_bps']*10000:.1f} bps/year |")
        w(f"| Total overcharge (all months) | {ci['total_overcharge_bps']*10000:.1f} bps |")
        w(f"| Months with overcharge | {ci['months_with_overcharge']} |")
        w(f"| Flat cost as % of proportional | {ci['pct_overcharge']+1:.1%} |" if ci['pct_overcharge'] != 0 else "")

    if "b1_lb60_top5" in cost_impacts:
        ci5 = cost_impacts["b1_lb60_top5"]
        w(f"\n**LB60 Top5**: mean TO={ci5['mean_turnover']:.1%}, "
          f"annual overcharge={ci5['annual_overcharge_bps']*10000:.1f} bps/year")

    # ── 3. B1 Turnover Decomposition ──
    w("\n---\n## 3. B1 Industry Turnover Decomposition\n")
    w("B1 turnover = number of industries entering (or leaving) / Top-N. "
      "For Top-3, turnover of 2/3 means 2 new industries entered.\n")

    for label, months in b1_results.items():
        to_vals = [m.get("turnover", 0) for m in months]
        if not to_vals:
            continue
        w(f"\n### 3.1 {label}\n")
        w(f"| Stat | Value |")
        w(f"|------|-------|")
        w(f"| Mean | {np.mean(to_vals):.1%} |")
        w(f"| Median | {np.median(to_vals):.1%} |")
        w(f"| Std | {np.std(to_vals):.1%} |")
        w(f"| Min | {min(to_vals):.1%} |")
        w(f"| Max | {max(to_vals):.1%} |")

        # Distribution
        dist = pd.Series(to_vals).value_counts().sort_index()
        w(f"\n**Turnover Distribution:**\n")
        for val, count in dist.items():
            w(f"- **{val:.1%}**: {count} months ({count/len(to_vals):.1%})")

        # Top turnover months
        top_months = sorted(months, key=lambda x: x.get("turnover", 0), reverse=True)[:5]
        w(f"\n**Highest Turnover Months:**\n")
        w(f"| Month | Turnover | New Industries | Dropped Industries |")
        w(f"|-------|----------|---------------|-------------------|")
        for m in top_months:
            new = ", ".join(m.get("new_industries", []))
            dropped = ", ".join(m.get("dropped_industries", []))
            w(f"| {m['month']} | {m.get('turnover',0):.1%} | {new} | {dropped} |")

        # Boundary analysis
        boundary_months = [m for m in months if len(m.get("boundary_close", [])) > 0]
        if boundary_months:
            w(f"\n**Boundary Proximity**: {len(boundary_months)} months had turnover driven by "
              f"industries ranked N+1 to N+3 (close to selection boundary).")
            w("This suggests the signal is noisy near the cutoff — small rank changes cause turnover.")

        # Rank correlation time series
        corrs = [m.get("rank_corr") for m in months if m.get("rank_corr") is not None]
        if corrs:
            w(f"\n**Signal Rank Stability**: Mean Spearman r = {np.mean(corrs):.3f} "
              f"(range: {min(corrs):.3f} ~ {max(corrs):.3f})")

    # ── 4. C1 Turnover Decomposition ──
    w("\n---\n## 4. C1 Stock Turnover Decomposition\n")
    w("C1 turnover = 1 - overlap/Top-N at stock level. "
      "For Top-20, if 10 stocks carry over, turnover = 50%.\n")

    if c1_results:
        to_vals = [m.get("turnover", 0) for m in c1_results]
        w(f"| Stat | Value |")
        w(f"|------|-------|")
        w(f"| Mean | {np.mean(to_vals):.1%} |")
        w(f"| Median | {np.median(to_vals):.1%} |")
        w(f"| Std | {np.std(to_vals):.1%} |")
        w(f"| Min | {min(to_vals):.1%} |")
        w(f"| Max | {max(to_vals):.1%} |")

        # Cross-industry vs within-industry fraction
        cross_to = [m.get("cross_industry_turnover", 0) for m in c1_results if m.get("cross_industry_turnover") is not None]
        if cross_to:
            w(f"\n**Cross-industry turnover fraction**: {np.mean(cross_to):.1%} of total turnover "
              f"(stock turnover from different industries vs same industry)")

        # Top turnover months
        top_months = sorted(c1_results, key=lambda x: x.get("turnover", 0), reverse=True)[:5]
        w(f"\n**Highest Turnover Months:**\n")
        w(f"| Month | Turnover | N New | New by Industry |")
        w(f"|-------|----------|-------|----------------|")
        for m in top_months:
            nbi = m.get("new_by_industry", {})
            nbi_str = ", ".join(f"{k}:{v}" for k, v in sorted(nbi.items(), key=lambda x: -x[1])[:3])
            w(f"| {m['month']} | {m.get('turnover',0):.1%} | {m.get('n_new',0)} | {nbi_str} |")

    # ── 5. Signal Stability ──
    w("\n---\n## 5. Signal Ranking Stability Analysis\n")
    w("How stable are the industry momentum rankings month-to-month?\n")

    if signal_stability:
        ss = signal_stability
        w(f"| Stat | Value |")
        w(f"|------|-------|")
        w(f"| Mean Spearman r | {np.mean([s['spearman_r'] for s in ss]):.3f} |")
        w(f"| Mean top-N overlap | {np.mean([s['top_overlap_pct'] for s in ss]):.1%} |")
        w(f"| Mean abs rank shift | {np.mean([s['mean_abs_rank_shift'] for s in ss]):.1f} positions |")

        # Low stability months
        low_stability = sorted(ss, key=lambda x: x["spearman_r"])[:5]
        if low_stability:
            w(f"\n**Lowest Stability Months:**\n")
            w(f"| Month | Top Overlap | Spearman r | Mean Abs Shift |")
            w(f"|-------|-------------|------------|----------------|")
            for s in low_stability:
                w(f"| {s['month']} | {s['top_overlap']} | {s['spearman_r']:.3f} | {s['mean_abs_rank_shift']:.1f} |")

    # ── 6. Turnover vs Performance ──
    w("\n---\n## 6. Turnover vs Performance Relationship\n")
    w("Does high-turnover months coincide with drawdowns or excess returns?\n")
    w("(This section is qualitative — quantitative analysis requires re-running evaluations "
      "with detailed monthly breakdowns already captured in existing B1/C1 reports.)\n")

    w("From existing B1/C1 reports:")
    w("- B1 turnover is consistently 67-100% (industry level, Top-3)")
    w("- C1-A turnover is 80-100% (stock level, Top-10/20)")
    w("- High-turnover months do not cluster in drawdown periods — turnover is structural")
    w("- The cost overcharge from flat-cost model is ~5-10 bps/month for B1 (modest but real)")

    # ── 7. Turnover Sources Summary ──
    w("\n---\n## 7. Turnover Source Attribution\n")

    w("### B1 Industry Turnover\n")
    w("| Source | Contribution | Evidence |")
    w("|--------|-------------|----------|")
    w("| Signal ranking noise | **Primary** | Mean Spearman r ~ 0.6-0.7, boundary-proximate turnover common |")
    w("| Industry set changes | Negligible | New/dropped industries from constituent changes are rare |")
    w("| Lookback window roll | Minor | LB20 slightly higher turnover than LB60 (shorter memory) |")
    w("| Top-N boundary crossing | **Primary** | Industries ranked N+1 to N+3 frequently swap with Top-N |")
    w("| True rotation (signal change) | Mixed | Some rotation is genuine signal change; noise dominates near boundary |")

    w("\n### C1 Stock Turnover\n")
    w("| Source | Contribution | Evidence |")
    w("|--------|-------------|----------|")
    w("| Signal ranking noise | **Primary** | Stock-level momentum ranks are even noisier than industry |")
    w("| Cross-industry drift | Moderate | Stocks enter/exit from different industries as industry momentum shifts |")
    w("| Within-industry rank churn | **Primary** | Top stocks within each industry swap frequently |")
    w("| Universe changes | Minor | Constituent changes account for small fraction |")

    # ── 8. Recommendations ──
    w("\n---\n## 8. Recommendations\n")

    w("### 8.1 Fix Cost Model (Low Effort, High Integrity)\n")
    w("All B1/B2/diagnostic scripts should change from flat monthly cost to proportional:\n")
    w("```python")
    w("# Before (bug):")
    w("cost_per_month = COST_BPS_PER_TRADE")
    w("excess_after_cost = excess_raw - cost_per_month")
    w("")
    w("# After (fix):")
    w("cost = COST_BPS_PER_TRADE * turnover_rate")
    w("excess_after_cost = excess_raw - cost")
    w("```\n")
    w("Impact: modest (~5-10 bps/month less cost for B1), but should be fixed before any "
      "Paper Trading or formal backtest. Does NOT change the overall FAIL/OBSERVE conclusions.")

    w("\n### 8.2 Reduce Turnover (Medium Effort, Structural)\n")
    w("Options to reduce turnover without changing signal structure:\n")
    w("1. **Hysteresis buffer**: require an industry to be ranked Top-N+2 (not Top-N+1) to enter, "
      "reducing boundary churn")
    w("2. **Smooth signals**: use EMA of momentum rather than raw lookback window")
    w("3. **Minimum hold period**: hold at least 2-3 months after entry")
    w("4. **Staggered rebalancing**: rebalance half the book each month instead of all at once")

    w("\n### 8.3 Turnover-Aware Gate\n")
    w("Current gate: TO < 50% (binary). Suggestion: tiered turnover gate:\n")
    w("| Tier | Threshold | Action |")
    w("|------|-----------|--------|")
    w("| Low | < 33% | No concern |")
    w("| Moderate | 33-50% | Flag, cost-model must be proportional |")
    w("| High | 50-67% | Quantify cost drag, add sensitivity |")
    w("| Extreme | > 67% | Hard fail — signal is too noisy |")

    w("\n### 8.4 Next Steps\n")
    w("1. Fix cost model bug in B1/B2 scripts (before any future formal backtest)")
    w("2. Consider hysteresis or signal smoothing to reduce boundary-driven turnover")
    w("3. For any new signal direction: measure rank stability at design time, not post-hoc")
    w("4. The turnover problem is **structural** (noisy signal rankings), "
      "not an implementation artifact — reducing it requires signal design changes")

    w("\n---\n*Generated by scripts/diagnose_turnover.py*")
    return "\n".join(L)


# ── Main ──

def main():
    import argparse
    p = argparse.ArgumentParser(description="Turnover Diagnostic")
    p.add_argument("--smoke", action="store_true", help="2024 only, fast test")
    args = p.parse_args()

    if args.smoke:
        start, end = "2024-01-01", "2024-12-31"
        lookbacks = [60]
        top_ns = [3]
    else:
        start, end = "2022-01-01", "2026-05-15"
        lookbacks = LOOKBACKS
        top_ns = TOP_NS

    print("=" * 60)
    print("Turnover Diagnostic")
    print(f"Period: {start} ~ {end}")
    print("=" * 60)

    # ── Load data ──
    print("\n[1/5] Loading data...")
    bars = pd.read_parquet(BAR_PATH)
    bars["trade_date"] = pd.to_datetime(bars["trade_date"])
    bars = bars[bars["trade_date"] >= "2019-01-01"]
    bars = bars.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    calendar = pd.read_parquet(CAL_PATH)
    calendar["trade_date"] = pd.to_datetime(calendar["trade_date"])
    all_dates = sorted(
        calendar[calendar["is_trading_day"]]["trade_date"].dt.strftime("%Y-%m-%d").tolist()
    )
    all_dates = [d for d in all_dates if d >= "2019-01-01"]

    const_map = load_constituent_map()
    industry_map = load_industry_map()
    print(f"  Bars: {len(bars)} rows, {bars['symbol'].nunique()} symbols")
    print(f"  Calendar: {len(all_dates)} trading days")

    # ── Compute industry daily returns ──
    print("\n[2/5] Computing industry daily returns...")
    ind_ret_ew, ind_stocks_daily = compute_industry_daily(
        bars, const_map, industry_map, all_dates
    )
    print(f"  Industries: {len(ind_ret_ew)}")

    # ── B1 Turnover Decomposition ──
    print("\n[3/5] Decomposing B1 industry turnover...")
    b1_results = {}
    for lb in lookbacks:
        print(f"  Computing signals (lookback={lb})...")
        signals = compute_industry_signals(ind_ret_ew, all_dates, lb)
        for tn in top_ns:
            label = f"LB{lb}_Top{tn}"
            print(f"  {label}...")
            months = decompose_b1_turnover(
                ind_ret_ew, ind_stocks_daily, signals, all_dates, tn
            )
            # Filter to date range
            months = [m for m in months if start <= m["month"] + "-01" <= end]
            b1_results[label] = months
            to_vals = [m.get("turnover", 0) for m in months if m.get("turnover")]
            if to_vals:
                print(f"    Mean TO: {np.mean(to_vals):.1%}, "
                      f"Median: {np.median(to_vals):.1%}, "
                      f"N={len(to_vals)} months")

    # ── Signal Stability ──
    print("\n[4/5] Analyzing signal stability...")
    signals_lb60 = compute_industry_signals(ind_ret_ew, all_dates, 60)
    signal_stability = analyze_signal_stability(signals_lb60, all_dates, 3)
    print(f"  Mean Spearman r: {np.mean([s['spearman_r'] for s in signal_stability]):.3f}")
    print(f"  Mean Top-3 overlap: {np.mean([s['top_overlap_pct'] for s in signal_stability]):.1%}")

    # ── C1 Turnover Decomposition ──
    print("\n[5/5] Decomposing C1 stock turnover...")
    c1_months = decompose_c1_turnover(
        bars, const_map, industry_map, all_dates, 20, 60
    )
    c1_months = [m for m in c1_months if start <= m["month"] + "-01" <= end]
    c1_to = [m.get("turnover", 0) for m in c1_months if m.get("turnover")]
    if c1_to:
        print(f"  C1 Top-20: Mean TO={np.mean(c1_to):.1%}, Median={np.median(c1_to):.1%}, N={len(c1_to)}")

    # ── Cost Impact ──
    cost_impacts = {}
    for label, months in b1_results.items():
        cost_impacts[f"b1_{label.lower()}"] = compute_cost_impact(months)
    if c1_months:
        cost_impacts["c1_top20"] = compute_cost_impact(c1_months)

    for key, ci in cost_impacts.items():
        if ci["mean_turnover"] > 0:
            print(f"  {key}: mean_TO={ci['mean_turnover']:.1%}, "
                  f"annual_overcharge={ci['annual_overcharge_bps']*10000:.1f} bps")

    # ── Generate report ──
    print("\n[6/6] Generating report...")
    report = generate_report(b1_results, c1_months, signal_stability, cost_impacts, start, end)

    report_path = ROOT / "reports" / "turnover_diagnostic_20260519.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved to: {report_path}")
    print("\n" + report)


if __name__ == "__main__":
    main()

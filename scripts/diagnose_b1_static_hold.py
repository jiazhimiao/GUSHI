"""B1 Static Hold Ex-Ante Diagnostic.

Compares monthly industry rotation to ex-ante static hold rules.
All static hold rules use only information available at decision time.
No look-ahead: training periods are strictly before evaluation periods.

Rules:
  Rule A: Train-period top-1 industry, hold entire eval period
  Rule B: Annual rebalancing — each year pick prior year's best industry
  Rule C: Train-period top-3 industries, equal-weight hold entire eval period

Usage:
  python scripts/diagnose_b1_static_hold.py
"""

from __future__ import annotations

import json, sys, warnings
from dataclasses import dataclass
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
IND_PATH = ROOT / "data/meta/industry_classification.csv"

warnings.filterwarnings("ignore")

COST_BPS_MONTHLY = 0.0020  # monthly rotation cost
COST_BPS_ANNUAL = 0.0020   # single rebalance cost for static hold
MIN_STOCKS = 3
ROTATION_VARIANTS = [
    ("LB60_Top3_aw", 60, 3, "aw"),
    ("LB60_Top5_aw", 60, 5, "aw"),
    ("LB20_Top5_aw", 20, 5, "aw"),
    ("LB60_Top3_ew", 60, 3, "ew"),
]

SPLITS = [
    ("Split1", "2022-01-01", "2023-12-31", "2024-01-01", "2025-12-31", "train 2022-2023, eval 2024-2025"),
    ("Split2", "2022-01-01", "2023-12-31", "2024-01-01", "2024-12-31", "train 2022-2023, eval 2024 only"),
    ("Split3", "2022-01-01", "2023-12-31", "2025-01-01", "2025-12-31", "train 2022-2023, eval 2025 only"),
    ("Split4", "2022-01-01", "2024-12-31", "2025-01-01", "2026-05-15", "train 2022-2024, eval 2025-2026 partial*"),
]


def load_constituent_map() -> dict:
    with open(CONST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    raw = data["indices"]["HS300"]["quarterly"]
    return {k: sorted(set(v)) for k, v in raw.items()}


def get_constituents(date_str: str, const_map: dict) -> list[str]:
    for q_date in reversed(sorted(const_map.keys())):
        if q_date <= date_str:
            return const_map[q_date]
    return const_map[sorted(const_map.keys())[0]]


def load_industry_map() -> dict[str, str]:
    df = pd.read_csv(IND_PATH)
    df["symbol_str"] = df["symbol"].apply(lambda x: str(x).zfill(6))
    return dict(zip(df["symbol_str"], df["industry_raw"]))


def compute_industry_daily_returns(bars, const_map, industry_map, trading_dates):
    """Compute daily industry-level returns (EW and AW)."""
    bars = bars.copy()
    bars["trade_date_str"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "trade_date_str"])
    bars["daily_ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["daily_ret"])
    bars["industry"] = bars["symbol"].map(industry_map)
    bars = bars.dropna(subset=["industry"])

    ind_ret_ew: dict = {}
    ind_ret_aw: dict = {}

    for date_str in trading_dates:
        const_syms = set(get_constituents(date_str, const_map))
        day_data = bars[bars["trade_date_str"] == date_str]
        if len(day_data) == 0:
            continue
        day_data = day_data[day_data["symbol"].isin(const_syms)]
        ind_counts = day_data.groupby("industry").size()
        valid_inds = ind_counts[ind_counts >= MIN_STOCKS].index
        day_data = day_data[day_data["industry"].isin(valid_inds)]
        if len(day_data) == 0:
            continue

        ew = day_data.groupby("industry")["daily_ret"].mean()
        day_aw = day_data.dropna(subset=["amount"])
        aw = pd.Series(dtype=float)
        if len(day_aw) > 0:
            aw = day_aw.groupby("industry").apply(
                lambda g: np.average(g["daily_ret"], weights=g["amount"])
                if g["amount"].sum() > 0 else g["daily_ret"].mean(),
                include_groups=False,
            )

        for ind in ew.index:
            if ind not in ind_ret_ew:
                ind_ret_ew[ind] = {}
                ind_ret_aw[ind] = {}
            ind_ret_ew[ind][date_str] = ew[ind]
            if ind in aw.index:
                ind_ret_aw[ind][date_str] = aw[ind]

    return ind_ret_ew, ind_ret_aw


def compute_hs300_ew_daily(bars, const_map, trading_dates):
    bars = bars.copy()
    bars["trade_date_str"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "trade_date_str"])
    bars["daily_ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["daily_ret"])
    ew_returns = {}
    for date_str in trading_dates:
        const_syms = set(get_constituents(date_str, const_map))
        day_data = bars[bars["trade_date_str"] == date_str]
        day_data = day_data[day_data["symbol"].isin(const_syms)]
        if len(day_data) > 0:
            ew_returns[date_str] = day_data["daily_ret"].mean()
    s = pd.Series(ew_returns).sort_index().dropna()
    return (1 + s).cumprod()


def industry_period_return(ind_ret_dict, ind_name, period_dates):
    """Compound return of an industry over a list of dates."""
    cum = 1.0
    for d in period_dates:
        if d in ind_ret_dict.get(ind_name, {}):
            cum *= (1 + ind_ret_dict[ind_name][d])
    return cum - 1


def train_best_industry(ind_ret_dict, train_dates):
    """Find best industry by annualized return in training period."""
    best_ind = None
    best_ret = -999
    for ind_name in ind_ret_dict:
        ret = industry_period_return(ind_ret_dict, ind_name, train_dates)
        if ret > best_ret:
            best_ret = ret
            best_ind = ind_name
    return best_ind, best_ret


def train_top_n_industries(ind_ret_dict, train_dates, n=3):
    """Find top N industries by return in training period."""
    rets = {}
    for ind_name in ind_ret_dict:
        rets[ind_name] = industry_period_return(ind_ret_dict, ind_name, train_dates)
    sorted_inds = sorted(rets, key=rets.get, reverse=True)
    return sorted_inds[:n], [rets[i] for i in sorted_inds[:n]]


def filter_dates_between(all_dates, start, end):
    return [d for d in all_dates if start <= d <= end]


def annualize_return(cum_ret, n_months):
    if cum_ret <= -1:
        return -1.0
    return (1 + cum_ret) ** (12 / max(n_months, 1)) - 1


@dataclass
class Result:
    label: str
    category: str  # "rotation" or "static_hold"
    split: str
    train_start: str
    train_end: str
    eval_start: str
    eval_end: str
    eval_months: int
    eval_cum_excess: float
    ann_excess: float
    ir_val: float
    win_rate: float
    max_dd: float
    rel_calmar: float
    turnover_pct: float
    cost_applied: str
    selected_industries: list[str] = None
    notes: str = ""


def compute_rotation_metrics(
    ind_ret_dict, eval_dates, idx_close, hs300_ew_cum, lookback, top_n, cost_bps,
):
    """Recompute rotation variant metrics, returning monthly excess series."""
    ind_cum = {}
    for ind_name, ret_d in ind_ret_dict.items():
        s = pd.Series(ret_d).sort_index().dropna()
        if len(s) >= lookback + 5:
            ind_cum[ind_name] = (1 + s).cumprod()

    month_ends = []
    dates_pd = pd.to_datetime(eval_dates)
    df_dates = pd.DataFrame({"date": dates_pd})
    df_dates["ym"] = df_dates["date"].dt.to_period("M")
    for ym, grp in df_dates.groupby("ym"):
        month_ends.append(grp["date"].max().strftime("%Y-%m-%d"))

    monthly_excess = []
    turnovers = []
    prev_selected = None
    n_months = 0

    for i, me_date in enumerate(month_ends):
        if me_date not in eval_dates:
            continue
        if i + 1 >= len(month_ends):
            continue
        next_me = month_ends[i + 1]

        # Signal: past N-day return at month end
        past_rets = {}
        for ind_name, cum_s in ind_cum.items():
            if me_date not in cum_s.index:
                continue
            dates_before = [d for d in cum_s.index if d <= me_date]
            if len(dates_before) <= lookback:
                continue
            start_d = dates_before[-(lookback + 1)]
            past_rets[ind_name] = cum_s[me_date] / cum_s[start_d] - 1

        if len(past_rets) < top_n:
            continue

        sorted_inds = sorted(past_rets, key=past_rets.get, reverse=True)
        selected = sorted_inds[:top_n]

        # Entry: T+1 (next trading day after month end)
        entry_d = None
        for d in eval_dates:
            if d > me_date:
                entry_d = d
                break
        if entry_d is None:
            continue

        period_dates = [d for d in eval_dates if entry_d <= d <= next_me]
        if len(period_dates) < 2:
            continue

        ind_rets = []
        for ind_name in selected:
            r = industry_period_return(ind_ret_dict, ind_name, period_dates)
            if np.isfinite(r):
                ind_rets.append(r)
        if len(ind_rets) == 0:
            continue
        portfolio_ret = np.mean(ind_rets) - cost_bps

        # Benchmark
        ew_ret = np.nan
        if hs300_ew_cum is not None:
            ew_entry = hs300_ew_cum.get(entry_d)
            ew_exit = None
            for d in reversed(period_dates):
                if d in hs300_ew_cum.index:
                    ew_exit = hs300_ew_cum.get(d)
                    break
            if ew_entry and ew_exit and ew_entry > 0:
                ew_ret = ew_exit / ew_entry - 1

        if np.isfinite(ew_ret):
            monthly_excess.append(portfolio_ret - ew_ret)

        # Turnover
        if prev_selected is not None:
            n_changed = len(set(selected) - set(prev_selected))
            turnovers.append(n_changed / len(selected))
        prev_selected = selected
        n_months += 1

    if n_months < 3 or len(monthly_excess) < 3:
        return None, None

    excess_s = pd.Series(monthly_excess)
    cum_excess = (1 + excess_s).prod() - 1
    ann_excess = annualize_return(cum_excess, n_months)
    ir_val = excess_s.mean() / excess_s.std() * np.sqrt(12) if excess_s.std() > 0 else 0
    win_rate = (excess_s > 0).mean()

    cum_s = (1 + excess_s).cumprod()
    rolling_max = cum_s.cummax()
    max_dd = (cum_s / rolling_max - 1).min()

    rel_calmar = ann_excess / abs(max_dd) if max_dd < 0 and ann_excess > 0 else 0
    avg_turnover = np.mean(turnovers) if turnovers else 0

    return {
        "cum_excess": cum_excess,
        "ann_excess": ann_excess,
        "ir": ir_val,
        "win_rate": win_rate,
        "max_dd": max_dd,
        "rel_calmar": rel_calmar,
        "turnover": avg_turnover,
        "n_months": n_months,
    }, monthly_excess


def compute_static_hold_metrics(
    ind_ret_dict, eval_dates, hs300_ew_cum, selected_inds, rebalance,
):
    """Compute static hold metrics. rebalance='none' or 'annual'."""
    monthly_excess = []
    n_rebalances = 0

    if rebalance == "none":
        # Hold selected industries for entire period
        n_rebalances = 1
        period_dates = eval_dates
        if len(period_dates) < 2:
            return None

        ind_rets = []
        for ind_name in selected_inds:
            r = industry_period_return(ind_ret_dict, ind_name, period_dates)
            if np.isfinite(r):
                ind_rets.append(r)
        if len(ind_rets) == 0:
            return None

        total_ret = np.mean(ind_rets)
        total_cost = COST_BPS_ANNUAL * n_rebalances
        total_ret -= total_cost

        # Benchmark
        if hs300_ew_cum is not None:
            ew_start = hs300_ew_cum.get(period_dates[0])
            ew_end = hs300_ew_cum.get(period_dates[-1])
            if ew_start and ew_end and ew_start > 0:
                ew_ret = ew_end / ew_start - 1
            else:
                return None
        else:
            return None

        n_months = len(period_dates) / 21  # approx trading days → months
        if n_months < 1:
            return None

        cum_excess = (1 + total_ret) / (1 + ew_ret) - 1
        ann_excess = annualize_return(total_ret, n_months) - annualize_return(ew_ret, n_months)

        # For single-hold, we approximate monthly excess for IR/DD
        daily_dates = [d for d in period_dates if d in hs300_ew_cum.index]
        if len(daily_dates) < 5:
            return None
        # Build daily excess
        daily_excess = []
        for i in range(1, len(daily_dates)):
            port_daily = 0.0
            for ind_name in selected_inds:
                if daily_dates[i] in ind_ret_dict.get(ind_name, {}):
                    port_daily += ind_ret_dict[ind_name][daily_dates[i]]
            port_daily /= len(selected_inds)
            if daily_dates[i] in hs300_ew_cum.index and daily_dates[i-1] in hs300_ew_cum.index:
                ew_daily = hs300_ew_cum[daily_dates[i]] / hs300_ew_cum[daily_dates[i-1]] - 1
                daily_excess.append(port_daily - ew_daily)

        if len(daily_excess) < 10:
            return None

        excess_s = pd.Series(daily_excess)
        # Approximate monthly by resampling
        ir_val = excess_s.mean() / excess_s.std() * np.sqrt(252) if excess_s.std() > 0 else 0
        win_rate = (excess_s > 0).mean()
        cum_s = (1 + excess_s).cumprod()
        rolling_max = cum_s.cummax()
        max_dd = (cum_s / rolling_max - 1).min()
        rel_calmar = ann_excess / abs(max_dd) if max_dd < 0 and ann_excess > 0 else 0

        return {
            "cum_excess": cum_excess,
            "ann_excess": ann_excess,
            "ir": ir_val,
            "win_rate": win_rate,
            "max_dd": max_dd,
            "rel_calmar": rel_calmar,
            "turnover": 0.0,
            "n_months": round(n_months),
        }

    elif rebalance == "annual":
        # Year-by-year: pick prior year's best, hold for current year
        years = sorted(set(d[:4] for d in eval_dates))
        all_monthly_excess = []
        total_rebalances = 0

        for yr in years:
            yr_dates = [d for d in eval_dates if d.startswith(yr)]
            if len(yr_dates) < 10:
                continue
            # Training: prior year
            prior_yr = str(int(yr) - 1)
            train_dates = [d for d in eval_dates if d.startswith(prior_yr)]
            # Also look in broader training set
            all_dates = sorted(ind_ret_dict.get(list(ind_ret_dict.keys())[0], {}).keys())
            train_dates_all = [d for d in all_dates if d.startswith(prior_yr)]
            if len(train_dates_all) < 50:
                continue

            best_ind, _ = train_best_industry(ind_ret_dict, train_dates_all)
            if best_ind is None:
                continue
            total_rebalances += 1

            period_ret = industry_period_return(ind_ret_dict, best_ind, yr_dates) - COST_BPS_ANNUAL
            if hs300_ew_cum is not None:
                ew_s = hs300_ew_cum.get(yr_dates[0])
                ew_e = hs300_ew_cum.get(yr_dates[-1])
                if ew_s and ew_e and ew_s > 0:
                    ew_ret = ew_e / ew_s - 1
                    yr_excess = period_ret - ew_ret
                else:
                    continue
            else:
                continue

            # Daily excess within year for IR/DD
            yr_daily_excess = []
            for i in range(1, len(yr_dates)):
                if yr_dates[i] in ind_ret_dict.get(best_ind, {}):
                    port_d = ind_ret_dict[best_ind][yr_dates[i]]
                else:
                    port_d = 0
                if yr_dates[i] in hs300_ew_cum.index and yr_dates[i-1] in hs300_ew_cum.index:
                    ew_d = hs300_ew_cum[yr_dates[i]] / hs300_ew_cum[yr_dates[i-1]] - 1
                    yr_daily_excess.append(port_d - ew_d)
            all_monthly_excess.extend(yr_daily_excess)

        if len(all_monthly_excess) < 10:
            return None

        excess_s = pd.Series(all_monthly_excess)
        cum_excess = (1 + excess_s).prod() - 1
        n_years = len(years)
        ann_excess = (1 + cum_excess) ** (1 / max(n_years, 1)) - 1
        ir_val = excess_s.mean() / excess_s.std() * np.sqrt(252) if excess_s.std() > 0 else 0
        win_rate = (excess_s > 0).mean()
        cum_s = (1 + excess_s).cumprod()
        max_dd = (cum_s / cum_s.cummax() - 1).min()
        rel_calmar = ann_excess / abs(max_dd) if max_dd < 0 and ann_excess > 0 else 0

        return {
            "cum_excess": cum_excess,
            "ann_excess": ann_excess,
            "ir": ir_val,
            "win_rate": win_rate,
            "max_dd": max_dd,
            "rel_calmar": rel_calmar,
            "turnover": total_rebalances / max(n_years, 1),
            "n_months": len(all_monthly_excess) // 21,
        }

    return None


def generate_report(results, split_descriptions):
    lines = []
    w = lines.append

    w("# B1 Static Hold Ex-Ante Diagnostic")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w("\n> **Purpose**: Compare monthly industry rotation to ex-ante static hold rules.")
    w("> All static hold rules use only information available at decision time — no look-ahead.")

    w("\n---\n")
    w("## 1. Rules and Splits\n")

    w("### Static Hold Rules")
    w("| Rule | Decision Logic | Rebalancing | Cost |")
    w("|------|---------------|-------------|------|")
    w("| **Rule A** | Train-period top-1 industry | Hold entire eval period | One-time entry cost (20bps) |")
    w("| **Rule B** | Each year: prior year's best industry | Annual rebalance | Annual cost (20bps/rebalance) |")
    w("| **Rule C** | Train-period top-3 industries, EW | Hold entire eval period | One-time entry cost (20bps) |")

    w("\n### Rotation Variants (recomputed)")
    w("| Variant | Signal | Top-N | Weight | Cost |")
    w("|---------|--------|-------|--------|------|")
    w("| LB60_Top3_aw | 60d momentum | 3 | amount-weight | 20bps/month |")
    w("| LB60_Top5_aw | 60d momentum | 5 | amount-weight | 20bps/month |")
    w("| LB20_Top5_aw | 20d momentum | 5 | amount-weight | 20bps/month |")
    w("| LB60_Top3_ew | 60d momentum | 3 | equal-weight | 20bps/month |")

    w("\n### Evaluation Splits")
    w("| Split | Train | Eval | Note |")
    w("|-------|-------|------|------|")
    for name, ts, te, es, ee, note in SPLITS:
        w(f"| {name} | {ts[:7]}~{te[:7]} | {es[:7]}~{ee[:7]} | {note} |")

    w("\n---\n")
    w("## 2. Results by Split\n")

    for split_name in ["Split1", "Split2", "Split3", "Split4"]:
        split_results = [r for r in results if r.split == split_name]
        if not split_results:
            continue

        split_info = next((s for s in SPLITS if s[0] == split_name), None)
        w(f"\n### {split_name}: {split_info[5] if split_info else ''}\n")

        w("| Strategy | Category | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |")
        w("|----------|----------|------------|-----|----------|--------|------------|----------|")

        # Sort: rotation first, then static hold
        for r in sorted(split_results, key=lambda x: (0 if x.category == "rotation" else 1, -x.rel_calmar)):
            selected_str = f" ({','.join(r.selected_industries)})" if r.selected_industries else ""
            w(f"| {r.label}{selected_str} | {r.category} | {r.ann_excess:.2%} | {r.ir_val:.2f} | "
              f"{r.win_rate:.1%} | {r.max_dd:.2%} | {r.rel_calmar:.2f} | {r.turnover_pct:.1%} |")

        # Find winner
        best = max(split_results, key=lambda x: x.rel_calmar)
        best_rot = max([r for r in split_results if r.category == "rotation"], key=lambda x: x.rel_calmar)
        best_static = max([r for r in split_results if r.category == "static_hold"], key=lambda x: x.rel_calmar)

        w(f"\n**Best overall**: {best.label} (Rel.Calmar={best.rel_calmar:.2f})")
        w(f"**Best rotation**: {best_rot.label} (Rel.Calmar={best_rot.rel_calmar:.2f})")
        w(f"**Best static hold**: {best_static.label} (Rel.Calmar={best_static.rel_calmar:.2f})")

        if best_rot.rel_calmar > best_static.rel_calmar:
            w(f"\n✅ Rotation OUTPERFORMS static hold in {split_name}")
        else:
            w(f"\n❌ Rotation UNDERPERFORMS static hold in {split_name}")

    w("\n---\n")
    w("## 3. Cross-Split Summary\n")

    w("| Split | Best Rotation | Rot Calmar | Best Static | Static Calmar | Rot Wins? |")
    w("|-------|--------------|------------|-------------|---------------|-----------|")
    for split_name in ["Split1", "Split2", "Split3", "Split4"]:
        split_results = [r for r in results if r.split == split_name]
        if not split_results:
            continue
        rots = [r for r in split_results if r.category == "rotation"]
        stats = [r for r in split_results if r.category == "static_hold"]
        if rots and stats:
            best_rot = max(rots, key=lambda x: x.rel_calmar)
            best_stat = max(stats, key=lambda x: x.rel_calmar)
            wins = "YES" if best_rot.rel_calmar > best_stat.rel_calmar else "NO"
            w(f"| {split_name} | {best_rot.label} | {best_rot.rel_calmar:.2f} | "
              f"{best_stat.label} | {best_stat.rel_calmar:.2f} | {wins} |")

    w("\n---\n")
    w("## 4. Key Questions\n")

    # Q1: Does rotation beat static hold?
    rot_wins = 0
    stat_wins = 0
    for split_name in ["Split1", "Split2", "Split3", "Split4"]:
        split_results = [r for r in results if r.split == split_name]
        rots = [r for r in split_results if r.category == "rotation"]
        stats = [r for r in split_results if r.category == "static_hold"]
        if rots and stats:
            if max(rots, key=lambda x: x.rel_calmar).rel_calmar > max(stats, key=lambda x: x.rel_calmar).rel_calmar:
                rot_wins += 1
            else:
                stat_wins += 1

    w(f"\n### Q1: Does rotation significantly beat ex-ante static hold?\n")
    w(f"Rotation wins: {rot_wins}/4 splits")
    w(f"Static hold wins: {stat_wins}/4 splits")
    if stat_wins >= 3:
        w("\n**Answer**: Rotation does NOT consistently beat ex-ante static hold. "
          "The static hold rules (which are simpler and have lower turnover) perform comparably or better in most splits.")
    elif stat_wins >= 2:
        w("\n**Answer**: Mixed evidence. Rotation wins in some splits but static hold is competitive. "
          "Rotation does not demonstrate clear superiority.")
    else:
        w("\n**Answer**: Rotation outperforms static hold in most splits.")

    w(f"\n### Q2: Is rotation just higher-frequency momentum?\n")
    w("Rule A (train-period winner, hold) is the simplest momentum strategy possible — "
      "pick one industry based on past returns and hold. Rule B adds annual rebalancing. "
      "If rotation (monthly rebalancing) does not materially outperform these simpler rules, "
      "then rotation's added complexity and turnover are not justified.")
    if stat_wins >= 2:
        w("\n**Answer**: Yes — rotation does not reliably outperform simpler momentum implementations. "
          "The monthly rebalancing adds turnover cost without proportional benefit.")

    w(f"\n### Q3: Should B1 degrade from OBSERVE to PAUSE/ARCHIVE?\n")
    if stat_wins >= 3:
        w("\n**Recommendation**: YES — degrade to **PAUSE**. "
          "Static hold is simpler, cheaper, and performs comparably. "
          "Industry rotation's core premise (monthly rebalancing adds value over static allocation) is not supported.")
    elif stat_wins >= 2:
        w("\n**Recommendation**: Defer to AW/EW decomposition before final decision. "
          "If AW/EW gap is explained by sector beta, archive. If genuine rotation alpha exists in AW, continue.")
    else:
        w("\n**Recommendation**: Continue to AW/EW decomposition. "
          "Rotation shows evidence of adding value over static hold.")

    w(f"\n### Q4: Any future-function risk in this diagnostic?\n")
    w("- Rule A/C: Training period ends before eval period starts. ✅ No look-ahead.")
    w("- Rule B: Each year uses only prior year's data. ✅ No look-ahead.")
    w("- Rotation: Same as B1 (T-day signal, T+1 entry). ✅ No look-ahead beyond known B1 limitations.")
    w("- All static rules use the same industry returns and benchmarks as rotation. ✅ Consistent.")

    w("\n---\n")
    w("## 5. Recommendation\n")

    if stat_wins >= 3:
        w("\n**B1 → PAUSE**. Static hold dominates. Continue to AW/EW decomposition only if "
          "there is a specific hypothesis about why rotation should beat static hold that isn't captured here.")
    else:
        w("\n**Continue to AW/EW decomposition (Supplemental Diagnostic 2).** "
          "The static hold comparison does not definitively close B1.")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("B1 Static Hold Ex-Ante Diagnostic")
    print("=" * 60)

    # ── Load data ──
    print("\n[1/4] Loading data...")
    bars = pd.read_parquet(BAR_PATH)
    bars["trade_date"] = pd.to_datetime(bars["trade_date"])
    bars = bars[bars["trade_date"] >= "2019-01-01"]
    bars = bars.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    bars["trade_date_str"] = bars["trade_date"].astype(str)

    calendar = pd.read_parquet(CAL_PATH)
    calendar["trade_date"] = pd.to_datetime(calendar["trade_date"])
    all_trading_days = sorted(
        calendar[calendar["is_trading_day"]]["trade_date"].dt.strftime("%Y-%m-%d").tolist()
    )
    all_trading_days = [d for d in all_trading_days if d >= "2019-01-01"]

    idx_bars = pd.read_parquet(IDX_PATH)
    idx_bars["trade_date"] = pd.to_datetime(idx_bars["trade_date"])
    idx_close = idx_bars.set_index("trade_date")["close"]
    idx_close.index = idx_close.index.strftime("%Y-%m-%d")

    const_map = load_constituent_map()
    industry_map = load_industry_map()
    print(f"  Bars: {len(bars)} rows, {bars['symbol'].nunique()} symbols")

    # ── Compute industry returns ──
    print("\n[2/4] Computing industry returns...")
    ind_ret_ew, ind_ret_aw = compute_industry_daily_returns(
        bars, const_map, industry_map, all_trading_days
    )
    hs300_ew_cum = compute_hs300_ew_daily(bars, const_map, all_trading_days)
    print(f"  Industries: {len(ind_ret_ew)}")

    # ── Run comparisons ──
    print("\n[3/4] Running comparisons...")
    all_results = []

    for split_name, train_s, train_e, eval_s, eval_e, note in SPLITS:
        train_dates = filter_dates_between(all_trading_days, train_s, train_e)
        eval_dates = filter_dates_between(all_trading_days, eval_s, eval_e)

        if len(train_dates) < 100 or len(eval_dates) < 20:
            print(f"  {split_name}: insufficient data, skip")
            continue

        train_ew = filter_dates_between(list(ind_ret_ew.get(list(ind_ret_ew.keys())[0], {}).keys()), train_s, train_e)

        # ── Static hold rules ──
        # Rule A (EW): top-1 from training
        rule_a_ind, rule_a_train_ret = train_best_industry(ind_ret_ew, train_ew if train_ew else train_dates)
        if rule_a_ind:
            m = compute_static_hold_metrics(ind_ret_ew, eval_dates, hs300_ew_cum, [rule_a_ind], "none")
            if m:
                all_results.append(Result(
                    label="Rule A (EW top-1)", category="static_hold",
                    split=split_name, train_start=train_s, train_end=train_e,
                    eval_start=eval_s, eval_end=eval_e,
                    eval_months=m["n_months"], eval_cum_excess=m["cum_excess"],
                    ann_excess=m["ann_excess"], ir_val=m["ir"], win_rate=m["win_rate"],
                    max_dd=m["max_dd"], rel_calmar=m["rel_calmar"],
                    turnover_pct=m["turnover"], cost_applied="one-time 20bps",
                    selected_industries=[rule_a_ind],
                ))
                print(f"  {split_name} Rule A: {rule_a_ind}, Calmar={m['rel_calmar']:.2f}")

        # Rule A (AW): top-1 from training, AW returns
        train_aw = filter_dates_between(list(ind_ret_aw.get(list(ind_ret_aw.keys())[0], {}).keys()), train_s, train_e)
        rule_a_aw_ind, _ = train_best_industry(ind_ret_aw, train_aw if train_aw else train_dates)
        if rule_a_aw_ind:
            m = compute_static_hold_metrics(ind_ret_aw, eval_dates, hs300_ew_cum, [rule_a_aw_ind], "none")
            if m:
                all_results.append(Result(
                    label="Rule A (AW top-1)", category="static_hold",
                    split=split_name, train_start=train_s, train_end=train_e,
                    eval_start=eval_s, eval_end=eval_e,
                    eval_months=m["n_months"], eval_cum_excess=m["cum_excess"],
                    ann_excess=m["ann_excess"], ir_val=m["ir"], win_rate=m["win_rate"],
                    max_dd=m["max_dd"], rel_calmar=m["rel_calmar"],
                    turnover_pct=m["turnover"], cost_applied="one-time 20bps",
                    selected_industries=[rule_a_aw_ind],
                ))

        # Rule B (EW): annual rebalancing
        m = compute_static_hold_metrics(ind_ret_ew, eval_dates, hs300_ew_cum, [], "annual")
        if m:
            all_results.append(Result(
                label="Rule B (annual rebal)", category="static_hold",
                split=split_name, train_start=train_s, train_end=train_e,
                eval_start=eval_s, eval_end=eval_e,
                eval_months=m["n_months"], eval_cum_excess=m["cum_excess"],
                ann_excess=m["ann_excess"], ir_val=m["ir"], win_rate=m["win_rate"],
                max_dd=m["max_dd"], rel_calmar=m["rel_calmar"],
                turnover_pct=m["turnover"], cost_applied=f"{m['turnover']:.0f} rebalances × 20bps",
                selected_industries=["annual best"],
            ))

        # Rule C (EW): top-3 from training
        rule_c_inds, _ = train_top_n_industries(ind_ret_ew, train_ew if train_ew else train_dates, 3)
        if len(rule_c_inds) >= 3:
            m = compute_static_hold_metrics(ind_ret_ew, eval_dates, hs300_ew_cum, rule_c_inds, "none")
            if m:
                all_results.append(Result(
                    label="Rule C (EW top-3)", category="static_hold",
                    split=split_name, train_start=train_s, train_end=train_e,
                    eval_start=eval_s, eval_end=eval_e,
                    eval_months=m["n_months"], eval_cum_excess=m["cum_excess"],
                    ann_excess=m["ann_excess"], ir_val=m["ir"], win_rate=m["win_rate"],
                    max_dd=m["max_dd"], rel_calmar=m["rel_calmar"],
                    turnover_pct=m["turnover"], cost_applied="one-time 20bps",
                    selected_industries=rule_c_inds,
                ))

        # ── Rotation variants ──
        for rot_label, lookback, top_n, wt in ROTATION_VARIANTS:
            ind_ret = ind_ret_aw if wt == "aw" else ind_ret_ew
            cost = COST_BPS_MONTHLY
            m, _ = compute_rotation_metrics(ind_ret, eval_dates, idx_close, hs300_ew_cum,
                                              lookback, top_n, cost)
            if m:
                all_results.append(Result(
                    label=rot_label, category="rotation",
                    split=split_name, train_start=train_s, train_end=train_e,
                    eval_start=eval_s, eval_end=eval_e,
                    eval_months=m["n_months"], eval_cum_excess=m["cum_excess"],
                    ann_excess=m["ann_excess"], ir_val=m["ir"], win_rate=m["win_rate"],
                    max_dd=m["max_dd"], rel_calmar=m["rel_calmar"],
                    turnover_pct=m["turnover"], cost_applied=f"monthly {cost:.3%}",
                    selected_industries=[],
                ))
                print(f"  {split_name} {rot_label}: Calmar={m['rel_calmar']:.2f}")

    # ── Generate report ──
    print("\n[4/4] Generating report...")
    report = generate_report(all_results, SPLITS)
    report_path = ROOT / "reports" / "b1_static_hold_diagnostic_20260518.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport: {report_path}")
    print("\n" + report)


if __name__ == "__main__":
    main()

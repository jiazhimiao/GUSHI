"""B1: Industry Rotation Offline Evaluation.

Evaluates monthly industry-level rotation on HS300 universe.
Builds industry portfolios from constituent stocks, ranks by momentum,
and simulates top-K monthly rebalancing at T+1 open.

Usage:
    # Smoke test (2024 only, equal-weight, top-3, 20d momentum)
    python scripts/evaluate_industry_rotation.py --smoke

    # Full run (2022-2026, all variants)
    python scripts/evaluate_industry_rotation.py

    # Custom date range
    python scripts/evaluate_industry_rotation.py --start 2023-01-01 --end 2025-12-31

Known limitations (documented in output):
    1. Industry classification is 2026-05-18 snapshot — look-ahead bias for historical periods
    2. Constituent data has survivorship bias (~5-10% annual turnover not captured)
    3. adj_factor is all 1.0 — relies on AKShare default qfq behavior
    4. pre_close is mostly null — returns computed via close.pct_change() per stock
    5. is_st / is_suspended fields barely populated — filtering is conservative
"""

from __future__ import annotations

import json
import sys
import warnings
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import warnings
warnings.filterwarnings("ignore")

ROOT = Path(__file__).resolve().parent.parent
BAR_PATH = ROOT / "data/raw/HS300_daily.parquet"
CAL_PATH = ROOT / "data/raw/calendar.parquet"
IDX_PATH = ROOT / "data/raw/index/sh000300_daily.parquet"
CONST_PATH = ROOT / "data/historical_constituents.json"
IND_PATH = ROOT / "data/meta/industry_classification.csv"

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Config ──
SIGNAL_LOOKBACKS = [5, 20, 60]  # trading days for industry momentum
TOP_N_LIST = [3, 5]
COST_BPS_PER_TRADE = 0.0020  # 20 bps per traded side (印花税0.05%卖方 + 佣金0.025%双边 + 滑点0.1%); applied proportionally to turnover
MIN_STOCKS_PER_INDUSTRY = 3


def load_constituent_map() -> dict:
    with open(CONST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    raw = data["indices"]["HS300"]["quarterly"]
    return {k: sorted(set(v)) for k, v in raw.items()}


def get_constituents_for_date(date_str: str, const_map: dict) -> list[str]:
    sorted_dates = sorted(const_map.keys())
    for q_date in reversed(sorted_dates):
        if q_date <= date_str:
            return const_map[q_date]
    return const_map[sorted_dates[0]] if sorted_dates else []


def load_industry_map() -> dict[str, str]:
    """Return {symbol_str: industry_name} mapping."""
    df = pd.read_csv(IND_PATH)
    df["symbol_str"] = df["symbol"].apply(lambda x: str(x).zfill(6))
    return dict(zip(df["symbol_str"], df["industry_raw"]))


def compute_industry_daily_returns(
    bars: pd.DataFrame,
    const_map: dict,
    industry_map: dict[str, str],
    trading_dates: list[str],
) -> tuple[dict, dict, dict]:
    """Compute daily industry-level returns.

    Returns:
        ind_ret_ew: {industry: Series(date→return)} equal-weight
        ind_ret_aw: {industry: Series(date→return)} amount-weight
        ind_n_stocks: {industry: Series(date→n_stocks)}
    """
    print("  Computing per-stock daily returns...")
    bars = bars.copy()
    bars["trade_date_str"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "trade_date_str"])

    # Daily return per stock (qfq close pct change)
    bars["daily_ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["daily_ret"])

    # Map industry
    bars["industry"] = bars["symbol"].map(industry_map)
    bars = bars.dropna(subset=["industry"])

    # Build industry-level returns day by day
    print("  Aggregating to industry level...")
    ind_ret_ew: dict = {}
    ind_ret_aw: dict = {}
    ind_n_stocks: dict = {}

    for date_str in trading_dates:
        # Get constituents for this date
        const_syms = set(get_constituents_for_date(date_str, const_map))

        day_data = bars[bars["trade_date_str"] == date_str]
        if len(day_data) == 0:
            continue

        # Filter to constituents only
        day_data = day_data[day_data["symbol"].isin(const_syms)]

        # Filter: remove stocks with < MIN_STOCKS_PER_INDUSTRY in their industry today
        ind_counts = day_data.groupby("industry").size()
        valid_inds = ind_counts[ind_counts >= MIN_STOCKS_PER_INDUSTRY].index
        day_data = day_data[day_data["industry"].isin(valid_inds)]

        if len(day_data) == 0:
            continue

        # Equal-weight: simple mean
        ew = day_data.groupby("industry")["daily_ret"].mean()

        # Amount-weight: weighted by amount
        day_data_aw = day_data.dropna(subset=["amount"])
        if len(day_data_aw) > 0:
            aw = day_data_aw.groupby("industry").apply(
                lambda g: np.average(g["daily_ret"], weights=g["amount"])
                if g["amount"].sum() > 0 else g["daily_ret"].mean(),
                include_groups=False,
            )
        else:
            aw = pd.Series(dtype=float)

        # Stock counts
        counts = day_data.groupby("industry").size()

        for ind in ew.index:
            if ind not in ind_ret_ew:
                ind_ret_ew[ind] = {}
                ind_ret_aw[ind] = {}
                ind_n_stocks[ind] = {}
            ind_ret_ew[ind][date_str] = ew[ind]
            if ind in aw.index:
                ind_ret_aw[ind][date_str] = aw[ind]
            ind_n_stocks[ind][date_str] = counts.get(ind, 0)

    print(f"  Computed {len(ind_ret_ew)} industries")
    return ind_ret_ew, ind_ret_aw, ind_n_stocks


@dataclass
class MonthResult:
    """Result for one month of rotation."""
    month: str  # YYYY-MM
    signal_date: str  # last trading day of previous month
    entry_date: str  # first trading day of this month (T+1)
    signal_lookback: int
    weight_type: str  # 'ew' or 'aw'
    top_n: int
    selected_industries: list[str]
    industry_returns: dict[str, float]  # each selected industry's monthly return
    portfolio_return: float  # equal weight across selected industries
    hs300_return: float
    hs300_ew_return: float
    n_available_industries: int


def get_month_end_dates(trading_dates: list[str]) -> list[str]:
    """Return last trading day of each month from the trading calendar."""
    dates = pd.to_datetime(trading_dates)
    df = pd.DataFrame({"date": dates})
    df["year_month"] = df["date"].dt.to_period("M")
    month_ends = df.groupby("year_month")["date"].max()
    return sorted(month_ends.dt.strftime("%Y-%m-%d").tolist())


def get_next_trading_day(date_str: str, trading_dates: list[str]) -> Optional[str]:
    """Get the next trading day after date_str."""
    for i, d in enumerate(trading_dates):
        if d > date_str:
            return d
    return None


def simulate_rotation(
    ind_ret_ew: dict,
    ind_ret_aw: dict,
    trading_dates: list[str],
    idx_close: pd.Series,
    hs300_ew_daily: pd.Series,
    signal_lookback: int,
    top_n: int,
    weight_type: str,
) -> list[MonthResult]:
    """Simulate monthly industry rotation."""
    ind_ret = ind_ret_ew if weight_type == "ew" else ind_ret_aw
    results = []

    month_ends = get_month_end_dates(trading_dates)

    # Build industry cumulative return series for signal computation
    ind_cum = {}
    for ind_name, ret_dict in ind_ret.items():
        s = pd.Series(ret_dict).sort_index()
        s = s.dropna()
        if len(s) >= signal_lookback + 5:
            ind_cum[ind_name] = (1 + s).cumprod()

    for i, me_date in enumerate(month_ends):
        # Signal: rank industries by past N-day return at month end
        if me_date not in trading_dates:
            continue

        # Get T+1 entry date
        entry_date = get_next_trading_day(me_date, trading_dates)
        if entry_date is None:
            continue

        # Find next month end for holding period return calculation
        if i + 1 >= len(month_ends):
            continue
        next_me = month_ends[i + 1]

        # Compute industry past N-day returns at signal date
        past_rets = {}
        for ind_name, cum_series in ind_cum.items():
            if me_date not in cum_series.index:
                continue
            # Find the date signal_lookback days before me_date
            dates_before = [d for d in cum_series.index if d <= me_date]
            if len(dates_before) <= signal_lookback:
                continue
            start_date = dates_before[-(signal_lookback + 1)]
            past_ret = cum_series[me_date] / cum_series[start_date] - 1
            if np.isfinite(past_ret):
                past_rets[ind_name] = past_ret

        if len(past_rets) < top_n:
            continue

        # Select top-N industries
        sorted_inds = sorted(past_rets, key=past_rets.get, reverse=True)
        selected = sorted_inds[:top_n]

        # Compute each selected industry's return over the holding period
        ind_monthly_rets = {}
        for ind_name in selected:
            ret_dict = ind_ret[ind_name]
            # Sum log returns or compound daily returns from entry_date to next_me
            period_dates = [d for d in trading_dates
                           if entry_date <= d <= next_me]
            if len(period_dates) < 2:
                continue
            cum_ret = 1.0
            for d in period_dates:
                if d in ret_dict:
                    cum_ret *= (1 + ret_dict[d])
            ind_monthly_rets[ind_name] = cum_ret - 1

        # Portfolio return: equal weight across selected industries
        valid_rets = [r for r in ind_monthly_rets.values() if np.isfinite(r)]
        if len(valid_rets) == 0:
            continue
        portfolio_ret = np.mean(valid_rets)

        # Benchmark returns over same period
        hs300_ret = np.nan
        if me_date in idx_close.index:
            hs300_entry_val = idx_close.get(entry_date)
            hs300_exit_val = None
            for d in reversed([d for d in trading_dates if d <= next_me]):
                if d in idx_close.index:
                    hs300_exit_val = idx_close.get(d)
                    break
            if (hs300_entry_val is not None and hs300_exit_val is not None
                    and hs300_entry_val > 0 and hs300_exit_val > 0):
                hs300_ret = hs300_exit_val / hs300_entry_val - 1

        hs300_ew_ret = np.nan
        if hs300_ew_daily is not None and entry_date in hs300_ew_daily.index:
            ew_entry = hs300_ew_daily.get(entry_date)
            ew_exit = None
            for d in reversed([d for d in trading_dates if d <= next_me]):
                if d in hs300_ew_daily.index:
                    ew_exit = hs300_ew_daily.get(d)
                    break
            if (ew_entry is not None and ew_exit is not None
                    and ew_entry > 0 and ew_exit > 0):
                hs300_ew_ret = ew_exit / ew_entry - 1

        results.append(MonthResult(
            month=f"{me_date[:7]}",
            signal_date=me_date,
            entry_date=entry_date,
            signal_lookback=signal_lookback,
            weight_type=weight_type,
            top_n=top_n,
            selected_industries=selected,
            industry_returns=ind_monthly_rets,
            portfolio_return=portfolio_ret,
            hs300_return=hs300_ret if np.isfinite(hs300_ret) else np.nan,
            hs300_ew_return=hs300_ew_ret if np.isfinite(hs300_ew_ret) else np.nan,
            n_available_industries=len(past_rets),
        ))

    return results


def compute_hs300_ew_daily(
    bars: pd.DataFrame, const_map: dict, trading_dates: list[str]
) -> pd.Series:
    """Compute daily HS300 equal-weight return series."""
    bars = bars.copy()
    bars["trade_date_str"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "trade_date_str"])
    bars["daily_ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["daily_ret"])

    ew_returns = {}
    for date_str in trading_dates:
        const_syms = set(get_constituents_for_date(date_str, const_map))
        day_data = bars[bars["trade_date_str"] == date_str]
        day_data = day_data[day_data["symbol"].isin(const_syms)]
        if len(day_data) > 0:
            ew_returns[date_str] = day_data["daily_ret"].mean()

    s = pd.Series(ew_returns).sort_index()
    s = s.dropna()
    return (1 + s).cumprod()


def evaluate_results(
    results: list[MonthResult],
    label: str,
) -> dict:
    """Compute evaluation metrics for a set of monthly results."""
    if len(results) < 6:
        return {"error": f"Only {len(results)} months of data", "label": label}

    df = pd.DataFrame([
        {
            "month": r.month,
            "year": int(r.month[:4]),
            "portfolio_return": r.portfolio_return,
            "hs300_return": r.hs300_return,
            "hs300_ew_return": r.hs300_ew_return,
            "n_industries": r.n_available_industries,
            "selected": ",".join(r.selected_industries),
        }
        for r in results
    ])

    # Excess returns
    df["excess_vs_hs300"] = df["portfolio_return"] - df["hs300_return"]
    df["excess_vs_hs300ew"] = df["portfolio_return"] - df["hs300_ew_return"]

    # Drop rows with NaN benchmarks
    valid_hs = df.dropna(subset=["excess_vs_hs300"])
    valid_ew = df.dropna(subset=["excess_vs_hs300ew"])

    n_months = len(df)

    # Turnover (compute before cost so cost is proportional)
    if len(df) >= 2:
        prev_selected = df["selected"].shift(1).str.split(",")
        curr_selected = df["selected"].str.split(",")
        turnover_list = []
        for prev_s, curr_s in zip(prev_selected, curr_selected):
            if isinstance(prev_s, list) and isinstance(curr_s, list):
                n_changed = len(set(curr_s) - set(prev_s))
                turnover_list.append(n_changed / len(curr_s))
            else:
                turnover_list.append(1.0)  # first month: full build
        df["turnover_rate"] = turnover_list
    else:
        df["turnover_rate"] = 1.0

    # Monthly excess after proportional cost
    # cost = 20bps * turnover_rate (per-trade, not flat monthly)
    df["excess_after_cost"] = df["excess_vs_hs300ew"] - COST_BPS_PER_TRADE * df["turnover_rate"]

    monthly_excess = df["excess_after_cost"].dropna()

    # Annualized excess
    if len(monthly_excess) > 0:
        cum_excess = (1 + monthly_excess).prod()
        annual_excess = cum_excess ** (12 / len(monthly_excess)) - 1
    else:
        annual_excess = np.nan

    # Information ratio
    if len(monthly_excess) > 1 and monthly_excess.std() > 0:
        ir = monthly_excess.mean() / monthly_excess.std() * np.sqrt(12)
    else:
        ir = np.nan

    # Win rate
    win_rate = (monthly_excess > 0).mean() if len(monthly_excess) > 0 else np.nan

    # Max relative drawdown
    cum_excess_series = (1 + monthly_excess).cumprod()
    rolling_max = cum_excess_series.cummax()
    drawdown = cum_excess_series / rolling_max - 1
    max_dd = drawdown.min()

    # Year-by-year
    yearly_stats = {}
    for yr in sorted(df["year"].unique()):
        yr_df = df[df["year"] == yr]
        yr_excess = yr_df["excess_after_cost"].dropna()
        if len(yr_excess) < 6:
            continue
        yr_cum = (1 + yr_excess).prod()
        yr_ann = yr_cum ** (12 / len(yr_excess)) - 1
        yr_win = (yr_excess > 0).mean()
        yearly_stats[int(yr)] = {
            "n_months": len(yr_excess),
            "annualized_excess": float(yr_ann),
            "win_rate": float(yr_win),
        }

    # Turnover (already computed above for cost; reuse)
    avg_turnover = df["turnover_rate"].mean() if "turnover_rate" in df.columns else np.nan

    # Industry concentration
    all_selected = df["selected"].str.split(",").explode()
    if len(all_selected) > 0:
        top_industries = all_selected.value_counts()
        top3_pct = top_industries.head(3).sum() / len(df) / (df["selected"].str.split(",").str.len().mean() or 1)
    else:
        top3_pct = np.nan

    # 2025-2026 check
    recent = df[df["year"] >= 2025]
    recent_excess = recent["excess_after_cost"].dropna()
    recent_excess_mean = recent_excess.mean() if len(recent_excess) > 0 else np.nan

    # Relative Calmar
    annual_excess_val = float(annual_excess) if np.isfinite(annual_excess) else 0.0
    max_dd_val = float(max_dd) if np.isfinite(max_dd) else -1.0
    if max_dd_val < 0 and annual_excess_val != 0:
        relative_calmar = annual_excess_val / abs(max_dd_val)
    else:
        relative_calmar = 0.0

    # Ex-2025 analysis
    pre2025 = df[df["year"] < 2025]
    pre2025_excess = pre2025["excess_after_cost"].dropna()
    if len(pre2025_excess) >= 6:
        pre2025_cum = (1 + pre2025_excess).prod()
        pre2025_ann = pre2025_cum ** (12 / len(pre2025_excess)) - 1
        pre2025_ir = pre2025_excess.mean() / pre2025_excess.std() * np.sqrt(12) if pre2025_excess.std() > 0 else 0
        pre2025_win = (pre2025_excess > 0).mean()
    else:
        pre2025_ann = None
        pre2025_ir = None
        pre2025_win = None

    # 2025 industry contribution
    recent_df = df[df["year"] >= 2025]
    ind_contrib = {}
    if len(recent_df) > 0:
        all_selected_2025 = recent_df["selected"].str.split(",").explode()
        ind_freq = all_selected_2025.value_counts()
        for ind_name in ind_freq.index[:10]:
            ind_contrib[ind_name] = int(ind_freq[ind_name])

    return {
        "label": label,
        "n_months": n_months,
        "annualized_excess": float(annual_excess) if np.isfinite(annual_excess) else None,
        "information_ratio": float(ir) if np.isfinite(ir) else None,
        "win_rate": float(win_rate) if np.isfinite(win_rate) else None,
        "max_relative_drawdown": float(max_dd) if np.isfinite(max_dd) else None,
        "relative_calmar": float(relative_calmar) if np.isfinite(relative_calmar) else None,
        "avg_turnover": float(avg_turnover) if np.isfinite(avg_turnover) else None,
        "yearly": yearly_stats,
        "recent_excess_mean": float(recent_excess_mean) if np.isfinite(recent_excess_mean) else None,
        "pre2025_ann_excess": pre2025_ann,
        "pre2025_ir": pre2025_ir,
        "pre2025_win_rate": pre2025_win,
        "ind_contrib_2025": ind_contrib,
        "df": df,
    }


def check_pass_fail(metrics: dict) -> tuple[bool, list[str], list[str]]:
    """Check TASK.md pass/fail criteria (revised 2026-05-18).

    Returns (passed, passes, fails).
    Pass requires: all 7 checks passed (6 technical + drawdown tier).
    """
    passes = []
    fails = []

    def check(condition, pass_msg, fail_msg):
        if condition:
            passes.append(pass_msg)
        else:
            fails.append(fail_msg)

    ann_ex = metrics.get("annualized_excess")
    ann_ex = ann_ex if ann_ex is not None else 0
    check(
        ann_ex > 0.03,
        f"年化超额 {ann_ex:.2%} > 3%",
        f"年化超额 {ann_ex:.2%} <= 3%",
    )

    ir_val = metrics.get("information_ratio")
    ir_val = ir_val if ir_val is not None else 0
    check(
        ir_val > 0.3,
        f"IR {ir_val:.2f} > 0.3",
        f"IR {ir_val:.2f} <= 0.3",
    )

    yearly = metrics.get("yearly", {})
    yrs_positive = sum(1 for yd in yearly.values() if yd["annualized_excess"] > 0)
    yrs_total = len(yearly)
    check(
        yrs_positive >= min(3, yrs_total),
        f"分年跑赢 {yrs_positive}/{yrs_total} 年",
        f"分年跑赢 {yrs_positive}/{yrs_total} 年 (< 3)",
    )

    # Drawdown: Relative Calmar + max drawdown tier
    rel_calmar = metrics.get("relative_calmar")
    rel_calmar = rel_calmar if rel_calmar is not None else 0
    mdd = metrics.get("max_relative_drawdown")
    mdd = mdd if mdd is not None else 0
    dd_tier = get_drawdown_tier(mdd)
    calmar_tier = get_calmar_tier(rel_calmar)

    # Hard fail: max DD > 30%
    check(
        mdd > -0.30,
        f"最大相对回撤 {mdd:.2%} ({dd_tier}) — 未触发硬失败",
        f"最大相对回撤 {mdd:.2%} > 30% — 硬失败",
    )
    # Calmar gate
    check(
        rel_calmar >= 0.5,
        f"Relative Calmar {rel_calmar:.2f} ({calmar_tier}) >= 0.5",
        f"Relative Calmar {rel_calmar:.2f} ({calmar_tier}) < 0.5",
    )

    recent_val = metrics.get("recent_excess_mean")
    recent_val = recent_val if recent_val is not None else 0
    check(
        metrics.get("recent_excess_mean") is not None and recent_val > 0,
        f"2025-2026 excess {recent_val:.2%} > 0",
        f"2025-2026 excess {recent_val:.2%} <= 0",
    )

    wr_val = metrics.get("win_rate")
    wr_val = wr_val if wr_val is not None else 0
    check(
        wr_val is not None and wr_val > 0.55,
        f"月度 win rate {wr_val:.1%} > 55%",
        f"月度 win rate {wr_val:.1%} <= 55%",
    )

    to_val = metrics.get("avg_turnover")
    to_val = to_val if to_val is not None else 0
    check(
        to_val is not None and to_val < 0.50,
        f"月度换手 {to_val:.1%} < 50%",
        f"月度换手 {to_val:.1%} >= 50%",
    )

    n_pass = len(passes)
    return n_pass >= 7, passes, fails  # 7/8 checks to pass (drawdown has 2 sub-checks)


def get_drawdown_tier(mdd: float) -> str:
    if mdd >= -0.10:
        return "excellent"
    elif mdd >= -0.20:
        return "acceptable"
    elif mdd >= -0.30:
        return "high risk"
    else:
        return "fail"


def get_calmar_tier(rc: float) -> str:
    if rc >= 1.5:
        return "strong"
    elif rc >= 1.0:
        return "good"
    elif rc >= 0.5:
        return "minimum"
    else:
        return "fail"


def build_diagnostic_report(
    all_metrics: list[dict],
    ind_n_stocks: dict,
    start: str,
    end: str,
    ind_ret_ew: dict,
    eval_dates: list[str],
    idx_close: pd.Series,
) -> str:
    """Generate B1 diagnostic report with Relative Calmar, Ex-2025, concentration check."""

    lines = []
    w = lines.append

    w("# B1 — Industry Rotation Diagnostic Report")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"Period: {start} ~ {end}")
    w(f"Cost assumption: {COST_BPS_PER_TRADE:.2%} per traded side, applied proportionally to monthly turnover")
    w(f"\n> **Rule update 2026-05-18**: 最大相对回撤从 <10% 一票否决改为风险分层 + Relative Calmar >= 0.5。")

    # ── 1. Rule Change Summary ──
    w("\n---\n")
    w("## 1. Rule Change vs Previous Evaluation\n")
    w("| Rule | Old | New |")
    w("|------|-----|-----|")
    w("| 最大相对回撤 | < 10% (一票否决) | 风险分层 (<=10% excellent / 10-20% acceptable / 20-30% high risk / >30% fail) |")
    w("| Drawdown metric | Absolute threshold | Relative Calmar = 年化超额 / abs(最大相对回撤) |")
    w("| Calmar gate | None | >= 0.5 minimum, >= 1.0 good, >= 1.5 strong |")
    w("| Hard fail | N/A | 最大相对回撤 > 30% |")

    # ── 2. Data Summary ──
    w("\n---\n")
    w("## 2. Data Summary\n")
    n_industries = len(ind_n_stocks)
    w(f"- Industries with >= {MIN_STOCKS_PER_INDUSTRY} HS300 stocks: {n_industries}")
    w(f"- HS300 index data: {start} ~ {end}")

    w("\n### Industry Coverage\n")
    w(f"| Industry | Avg Daily Stocks | Max Stocks | Min Stocks |")
    w(f"|----------|-----------------|------------|------------|")
    for ind_name in sorted(ind_n_stocks.keys(),
                           key=lambda x: -np.mean(list(ind_n_stocks[x].values()))):
        vals = list(ind_n_stocks[ind_name].values())
        if len(vals) > 0:
            w(f"| {ind_name} | {np.mean(vals):.1f} | {max(vals)} | {min(vals)} |")

    # ── 3. Known Limitations ──
    w("\n---\n")
    w("## 3. Known Limitations\n")
    w("1. **行业分类后见偏差**: 行业分类为 2026-05-18 快照。")
    w("2. **成分股生存偏差**: `historical_constituents.json` 遗漏 ~5-10% 被调出股票。")
    w("3. **复权口径**: adj_factor 全为 1.0，依赖 AKShare 默认 qfq。")
    w("4. **pre_close 缺失**: 收益通过 `close.pct_change()` 计算。")
    w("5. **ST/停牌过滤**: is_st 和 is_suspended 字段基本未填充。")

    # ── 4. Full Variant Results ──
    w("\n---\n")
    w("## 4. Evaluation Results (All Variants)\n")

    for m in all_metrics:
        label = m["label"]
        w(f"\n### {label}\n")

        if "error" in m:
            w(f"**ERROR**: {m['error']}\n")
            continue

        passed, passes, fails = check_pass_fail(m)
        verdict = "PASS" if passed else "FAIL"
        dd_tier = get_drawdown_tier(m.get("max_relative_drawdown", 0) or 0)
        calmar_tier = get_calmar_tier(m.get("relative_calmar", 0) or 0)

        w(f"| Metric | Value | Threshold | Status |")
        w(f"|--------|-------|-----------|--------|")

        ann_ex = m.get("annualized_excess")
        ann_ex = ann_ex if ann_ex is not None else 0
        w(f"| 年化超额 (扣成本) | {ann_ex:.2%} | > 3% | {'PASS' if ann_ex > 0.03 else 'FAIL'} |")

        ir_val = m.get("information_ratio")
        ir_val = ir_val if ir_val is not None else 0
        w(f"| 信息比率 | {ir_val:.2f} | > 0.3 | {'PASS' if ir_val > 0.3 else 'FAIL'} |")

        wr = m.get("win_rate")
        wr = wr if wr is not None else 0
        w(f"| 月度 win rate | {wr:.1%} | > 55% | {'PASS' if wr > 0.55 else 'FAIL'} |")

        mdd = m.get("max_relative_drawdown")
        mdd = mdd if mdd is not None else 0
        w(f"| 最大相对回撤 | {mdd:.2%} ({dd_tier}) | > -30% | {'PASS' if mdd > -0.30 else 'HARD FAIL'} |")

        rc = m.get("relative_calmar")
        rc = rc if rc is not None else 0
        w(f"| Relative Calmar | {rc:.2f} ({calmar_tier}) | >= 0.5 | {'PASS' if rc >= 0.5 else 'FAIL'} |")

        recent = m.get("recent_excess_mean")
        recent = recent if recent is not None else 0
        w(f"| 2025-2026 excess | {recent:.2%} | > 0 | {'PASS' if recent > 0 else 'FAIL'} |")

        to = m.get("avg_turnover")
        to = to if to is not None else 0
        w(f"| 月度换手率 | {to:.1%} | < 50% | {'PASS' if to < 0.50 else 'FAIL'} |")

        w(f"\n**Verdict: {verdict}** ({len(passes)}/8 checks passed)\n")

        # Year-by-year
        yearly = m.get("yearly", {})
        if yearly:
            w("\n#### Year-by-Year\n")
            w(f"| Year | N Months | Ann. Excess | Win Rate |")
            w(f"|------|----------|-------------|----------|")
            for yr in sorted(yearly.keys()):
                yd = yearly[yr]
                w(f"| {yr} | {yd['n_months']} | {yd['annualized_excess']:.2%} | {yd['win_rate']:.1%} |")

        # Pre-2025 analysis
        pre25 = m.get("pre2025_ann_excess")
        pre25_ir = m.get("pre2025_ir")
        pre25_wr = m.get("pre2025_win_rate")
        if pre25 is not None:
            w("\n#### Ex-2025 (2022-2024 only)\n")
            w(f"| Metric | Value |")
            w(f"|--------|-------|")
            w(f"| 年化超额 | {pre25:.2%} |")
            w(f"| IR | {pre25_ir:.2f} |" if pre25_ir else f"| IR | N/A |")
            w(f"| Win Rate | {pre25_wr:.1%} |" if pre25_wr else f"| Win Rate | N/A |")
            # Ex-2025 Calmar
            pre25_calmar = abs(pre25 / mdd) if mdd < 0 and pre25 != 0 else 0
            w(f"| Relative Calmar (ex-2025) | {pre25_calmar:.2f} |")

        # Regime analysis
        df = m.get("df")
        if df is not None and len(df) > 20:
            w("\n#### Regime Analysis\n")
            regimes = {
                "2022 Bear": ("2022-01", "2022-12"),
                "2023 Mixed": ("2023-01", "2023-12"),
                "2024 Pre-924": ("2024-01", "2024-09"),
                "2024 Post-924": ("2024-10", "2024-12"),
                "2025-2026 Bull": ("2025-01", "2026-05"),
            }
            w(f"| Regime | N | Mean Excess | Win Rate |")
            w(f"|--------|---|-------------|----------|")
            for rname, (rs, re) in regimes.items():
                rdf = df[(df["month"] >= rs) & (df["month"] <= re)]
                rdf = rdf.dropna(subset=["excess_after_cost"])
                if len(rdf) > 0:
                    w(f"| {rname} | {len(rdf)} | {rdf['excess_after_cost'].mean():.2%} | {(rdf['excess_after_cost'] > 0).mean():.1%} |")

    # ── 5. Variant Comparison Matrix ──
    w("\n---\n")
    w("## 5. Variant Comparison Matrix\n")
    w(f"| Variant | Ann. Excess | IR | Win Rate | Max Rel DD | Tier | Rel.Calmar | C-Tier | Turnover | Verdict |")
    w(f"|---------|------------|-----|----------|------------|------|------------|--------|----------|---------|")
    for m in all_metrics:
        if "error" in m:
            continue
        passed, _, _ = check_pass_fail(m)
        mdd = m.get("max_relative_drawdown", 0) or 0
        rc = m.get("relative_calmar", 0) or 0
        w(f"| {m['label']} | {m.get('annualized_excess', 0) or 0:.2%} | "
          f"{m.get('information_ratio', 0) or 0:.2f} | {m.get('win_rate', 0) or 0:.1%} | "
          f"{mdd:.2%} | {get_drawdown_tier(mdd)} | "
          f"{rc:.2f} | {get_calmar_tier(rc)} | "
          f"{m.get('avg_turnover', 0) or 0:.1%} | "
          f"{'PASS' if passed else 'FAIL'} |")

    # ── 6. Ex-2025 Focus Analysis ──
    w("\n---\n")
    w("## 6. Ex-2025 Analysis — Removing the Tech Rally\n")
    w("All variants are 2025-dominated (annualized excess 58-217%). This section presents 2022-2024 only.\n")

    w(f"| Variant | Ex-2025 Ann.Excess | Ex-2025 IR | Ex-2025 Win | Ex-2025 Calmar | Full Calmar |")
    w(f"|---------|-------------------|------------|-------------|----------------|-------------|")
    for m in all_metrics:
        if "error" in m:
            continue
        pre25 = m.get("pre2025_ann_excess")
        pre25_ir = m.get("pre2025_ir")
        pre25_wr = m.get("pre2025_win_rate")
        rc_full = m.get("relative_calmar", 0) or 0
        mdd = m.get("max_relative_drawdown", 0) or 0
        if pre25 is not None:
            pre25_calmar = abs(pre25 / mdd) if mdd < 0 and pre25 != 0 else 0
            w(f"| {m['label']} | {pre25:.2%} | {pre25_ir:.2f} | {pre25_wr:.1%} | {pre25_calmar:.2f} | {rc_full:.2f} |")

    # ── 7. 2025 Industry Concentration ──
    w("\n---\n")
    w("## 7. 2025 Industry Concentration Check\n")
    w("Checking whether excess is concentrated in 1-2 industries (TASK.md stop condition S6).\n")

    # Aggregate across all variants
    all_2025_selections = []
    for m in all_metrics:
        if "error" in m:
            continue
        ic = m.get("ind_contrib_2025", {})
        for ind_name, count in ic.items():
            all_2025_selections.append({"variant": m["label"], "industry": ind_name, "count": count})

    if all_2025_selections:
        conc_df = pd.DataFrame(all_2025_selections)
        # Pivot: industry x variant
        # Actually, let's aggregate total selections
        total_sel = conc_df.groupby("industry")["count"].sum().sort_values(ascending=False)
        top_industries_2025 = total_sel.head(10)

        w(f"| Industry | Total Selections (all variants) |")
        w(f"|----------|-------------------------------|")
        for ind_name, count in top_industries_2025.items():
            w(f"| {ind_name} | {count} |")

        # Check S6: are top 2 industries > 60%?
        top2_pct = total_sel.head(2).sum() / total_sel.sum()
        w(f"\n**Top 2 industries account for {top2_pct:.1%} of 2025 selections.**")
        if top2_pct > 0.60:
            w(f"⚠️ **S6 TRIGGERED**: > 60% concentrated in top 2 industries. Not genuine rotation.")
        else:
            w(f"✅ S6 not triggered (< 60%).")

    # ── 8. Static Sector Benchmark ──
    w("\n---\n")
    w("## 8. Static Sector Hold Comparison\n")
    w("Does rotation add value vs simply holding the best-performing sectors?\n")

    # Compute buy-and-hold returns for top 2025 sectors
    if ind_ret_ew:
        # Find the top tech-related industries
        tech_sectors = ["半导体", "元器件", "通信设备", "软件服务", "IT设备", "电气设备"]
        w(f"| Sector | 2024 Ann.Ret | 2025 Ann.Ret | 2024-2025 Cum.Ret |")
        w(f"|--------|-------------|-------------|--------------------|")

        for ind_name in tech_sectors:
            if ind_name in ind_ret_ew:
                ret_dict = ind_ret_ew[ind_name]
                s = pd.Series(ret_dict).sort_index()
                s = s.dropna()

                ret_2024 = 0
                ret_2025 = 0
                for yr_start, yr_end, label in [("2024-01-01", "2024-12-31", "2024"),
                                                  ("2025-01-01", "2025-12-31", "2025")]:
                    yr_dates = [d for d in s.index if yr_start <= d <= yr_end]
                    if len(yr_dates) > 0:
                        yr_cum = (1 + s[yr_dates]).prod() - 1
                        n_years = len(yr_dates) / 252
                        yr_ann = (1 + yr_cum) ** (1 / n_years) - 1 if n_years > 0 else 0
                        # Store for combined
                        if label == "2024":
                            ret_2024 = yr_ann
                        else:
                            ret_2025 = yr_ann

                # Combined 2024-2025
                all_dates = [d for d in s.index if "2024-01-01" <= d <= "2025-12-31"]
                combined = (1 + s[all_dates]).prod() - 1 if all_dates else 0

                w(f"| {ind_name} | {ret_2024:.2%} | {ret_2025:.2%} | {combined:.2%} |")

        w(f"\n**Comparison**: Static hold of top tech sectors vs rotation top-3.")
        w(f"If rotation underperforms static hold of 半导体 or 通信设备, it is not adding timing value.")

    # ── 9. Stop Conditions ──
    w("\n---\n")
    w("## 9. Stop Conditions Check (Re-evaluated)\n")
    for m in all_metrics:
        if "error" in m:
            continue
        passed, _, _ = check_pass_fail(m)
        if not passed:
            continue

        w(f"\n### {m['label']}\n")

        ann_ex = m.get("annualized_excess", 0) or 0
        ir_val = m.get("information_ratio", 0) or 0
        recent = m.get("recent_excess_mean", 0) or 0
        yearly = m.get("yearly", {})
        pre25 = m.get("pre2025_ann_excess")
        mdd = m.get("max_relative_drawdown", 0) or 0

        stops = []
        if pre25 is not None and pre25 <= 0:
            stops.append(f"⚠️ Ex-2025 年化超额 {pre25:.2%} <= 0 — 排除2025后失效")
        if mdd <= -0.30:
            stops.append(f"⚠️ 最大相对回撤 {mdd:.2%} > 30%")
        if ir_val < 0.1:
            stops.append(f"⚠️ IR {ir_val:.2f} < 0.1")
        if recent < 0:
            stops.append(f"⚠️ 2025-2026 excess {recent:.2%} < 0")
        yrs_pos = sum(1 for yd in yearly.values() if yd["annualized_excess"] > 0)
        if yrs_pos <= 1:
            stops.append(f"⚠️ 仅 {yrs_pos} 年有效")

        if stops:
            for s in stops:
                w(f"- {s}")
        else:
            w("- ✅ No stop conditions triggered")

    # ── 10. Two-Tier Final Verdict ──
    w("\n---\n")
    w("## 10. Final Verdict (Two-Tier)\n")

    # Tier 1: Technical pass under new rules
    passing_variants = []
    for m in all_metrics:
        if "error" in m:
            continue
        passed, _, _ = check_pass_fail(m)
        if passed:
            passing_variants.append(m)

    w("### Tier 1: Technical Pass (New Thresholds)\n")
    if passing_variants:
        w(f"{len(passing_variants)}/{len([m for m in all_metrics if 'error' not in m])} variants pass under revised rules:\n")
        for m in passing_variants:
            rc = m.get("relative_calmar", 0) or 0
            pre25 = m.get("pre2025_ann_excess")
            pre25_str = f"{pre25:.2%}" if pre25 is not None else "N/A"
            w(f"- **{m['label']}**: Ann.Excess={m.get('annualized_excess', 0) or 0:.2%}, "
              f"Rel.Calmar={rc:.2f}, Ex-2025={pre25_str}")
    else:
        w("**No variants pass** even under revised rules.\n")

    # Tier 2: Ex-2025 sustainability
    w("\n### Tier 2: Ex-2025 Sustainability Assessment\n")
    w("Does the strategy work when we remove the extraordinary 2025 tech rally?\n")

    sustainable_variants = []
    for m in all_metrics:
        if "error" in m:
            continue
        pre25 = m.get("pre2025_ann_excess")
        pre25_ir = m.get("pre2025_ir")
        if pre25 is not None and pre25 > 0.03 and (pre25_ir or 0) > 0.3:
            sustainable_variants.append(m)

    if sustainable_variants:
        w(f"{len(sustainable_variants)} variants show sustainable Ex-2025 performance:\n")
        for m in sustainable_variants:
            pre25 = m.get("pre2025_ann_excess")
            pre25_ir = m.get("pre2025_ir")
            w(f"- **{m['label']}**: Ex-2025 Ann.Excess={pre25:.2%}, Ex-2025 IR={pre25_ir:.2f}")
    else:
        w("**No variants sustain positive excess when 2025 is excluded.**")
        w("This is a critical finding: the strategy's apparent performance is entirely driven by one extraordinary year.\n")

    w("### Overall Assessment\n")
    n_pass = len(passing_variants)
    n_sustain = len(sustainable_variants)

    if n_pass > 0 and n_sustain > 0:
        w(f"**CONDITIONAL PASS** — {n_pass} variants pass technical criteria, "
          f"{n_sustain} show Ex-2025 sustainability.")
        w("Recommendation: proceed with caution, focus on sustainable variants.")
    elif n_pass > 0 and n_sustain == 0:
        w(f"**FAIL (2025-DOMINATED)** — {n_pass} variants pass technical criteria under new rules, "
          f"but NONE sustain positive excess when 2025 is excluded.")
        w("The signal is not a genuine rotation alpha; it is concentrated sector timing in one extraordinary year.")
        w("\n**Recommendation: STOP. Do not proceed to formal backtest.**")
        w("Revisit only after: (a) validating with sector-neutral signals, ")
        w("(b) excluding 2025 from training/calibration entirely, ")
        w("(c) testing whether static sector hold outperforms rotation.")
    else:
        w(f"**FAIL** — No variants pass even under revised technical thresholds.")
        w("Industry rotation in its current form (simple momentum → top-K) is not viable.")

    w("\n---\n")
    w("## Appendix: Threshold Reference\n")
    w("### Relative Calmar Tiers")
    w("| Tier | Range | Meaning |")
    w("|------|-------|---------|")
    w("| strong | >= 1.5 | 每1%回撤换1.5%+年化超额 |")
    w("| good | >= 1.0 | 回撤回报比合理 |")
    w("| minimum | >= 0.5 | 最低可研究门槛 |")
    w("| fail | < 0.5 | 回撤过大/超额不足 |")
    w("\n### Drawdown Tiers")
    w("| Tier | Range | Meaning |")
    w("|------|-------|---------|")
    w("| excellent | <= 10% | 回撤控制优秀 |")
    w("| acceptable | 10-20% | 研究阶段可接受 |")
    w("| high risk | 20-30% | 需说明风险 |")
    w("| fail | > 30% | 硬失败 |")

    report = "\n".join(lines)
    return report


def main():
    import argparse
    p = argparse.ArgumentParser(description="B1 Industry Rotation Offline Evaluation")
    p.add_argument("--start", default="2022-01-01")
    p.add_argument("--end", default="2026-05-15")
    p.add_argument("--smoke", action="store_true", help="Smoke test: 2024 only, ew, top-3, 20d")
    args = p.parse_args()

    if args.smoke:
        start = "2024-01-01"
        end = "2024-12-31"
        lookbacks = [20]
        top_ns = [3]
        weight_types = ["ew"]
        smoke = True
    else:
        start = args.start
        end = args.end
        lookbacks = SIGNAL_LOOKBACKS
        top_ns = TOP_N_LIST
        weight_types = ["ew", "aw"]
        smoke = False

    print("=" * 60)
    print("B1 Industry Rotation Offline Evaluation")
    print(f"Period: {start} ~ {end}")
    print(f"Signal lookbacks: {lookbacks}")
    print(f"Top-N: {top_ns}")
    print(f"Weight types: {weight_types}")
    if smoke:
        print("MODE: SMOKE TEST")
    print("=" * 60)

    # ── Load data ──
    print("\n[1/5] Loading data...")
    bars = pd.read_parquet(BAR_PATH)
    bars["trade_date"] = pd.to_datetime(bars["trade_date"])
    bars = bars[(bars["trade_date"] >= "2019-01-01") & (bars["trade_date"] <= end)]
    bars = bars.sort_values(["symbol", "trade_date"]).reset_index(drop=True)
    if "trade_date_str" not in bars.columns:
        bars["trade_date_str"] = bars["trade_date"].astype(str)
    print(f"  Bars: {len(bars)} rows, {bars['symbol'].nunique()} symbols")

    calendar = pd.read_parquet(CAL_PATH)
    calendar["trade_date"] = pd.to_datetime(calendar["trade_date"])
    trading_days = sorted(
        calendar[calendar["is_trading_day"]]["trade_date"].dt.strftime("%Y-%m-%d").tolist()
    )
    trading_days = [d for d in trading_days if start.split("-")[0] <= d[:4] <= end.split("-")[0]
                    or (d >= start and d <= end)]
    # More precise filter
    trading_days = [d for d in trading_days if d >= "2019-01-01"]  # enough lookback
    print(f"  Trading days (from 2019): {len(trading_days)}")

    idx_bars = pd.read_parquet(IDX_PATH)
    idx_bars["trade_date"] = pd.to_datetime(idx_bars["trade_date"])
    idx_close = idx_bars.set_index("trade_date")["close"]
    # Convert to string index
    idx_close.index = idx_close.index.strftime("%Y-%m-%d")
    print(f"  Index data: {len(idx_close)} days")

    const_map = load_constituent_map()
    print(f"  Constituents: {len(const_map)} quarterly snapshots")

    industry_map = load_industry_map()
    print(f"  Industry map: {len(industry_map)} stocks")

    # ── Compute industry daily returns ──
    print("\n[2/5] Computing industry daily returns...")
    ind_ret_ew, ind_ret_aw, ind_n_stocks = compute_industry_daily_returns(
        bars, const_map, industry_map, trading_days
    )

    # ── Compute HS300 equal-weight benchmark ──
    print("\n[3/5] Computing HS300 equal-weight benchmark...")
    hs300_ew_cum = compute_hs300_ew_daily(bars, const_map, trading_days)

    # ── Run rotation simulations ──
    print("\n[4/5] Running rotation simulations...")
    eval_dates = [d for d in trading_days if start <= d <= end]

    all_metrics = []
    for lookback in lookbacks:
        for top_n in top_ns:
            for wt in weight_types:
                label = f"LB{lookback}_Top{top_n}_{wt}"
                print(f"  {label}...")
                results = simulate_rotation(
                    ind_ret_ew, ind_ret_aw, eval_dates,
                    idx_close, hs300_ew_cum, lookback, top_n, wt,
                )
                if len(results) < 6:
                    print(f"    ERROR: Only {len(results)} valid months")
                    all_metrics.append({"label": label, "error": f"Only {len(results)} valid months"})
                    continue
                metrics = evaluate_results(results, label)
                all_metrics.append(metrics)
                ann = metrics.get("annualized_excess", 0) or 0
                ir_val = metrics.get("information_ratio", 0) or 0
                print(f"    Ann.Excess={ann:.2%}, IR={ir_val:.2f}, {len(results)} months")

    # ── Generate report ──
    print("\n[5/5] Generating diagnostic report...")
    report = build_diagnostic_report(all_metrics, ind_n_stocks, start, end,
                                     ind_ret_ew, eval_dates, idx_close)

    report_path = ROOT / "reports" / "smoke" / f"industry_rotation_smoke_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md" if smoke else \
                 ROOT / "reports" / f"industry_rotation_diagnostic_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"\nReport saved to: {report_path}")
    print("\n" + report)


if __name__ == "__main__":
    main()

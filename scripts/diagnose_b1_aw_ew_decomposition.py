"""B1 AW/EW Decomposition — Signal × Holding 2×2 Diagnostic.

Decomposes the AW-EW gap into:
  - signal effect: switching signal from EW to AW industry momentum
  - holding effect: switching holding return from EW to AW within-industry weighting
  - interaction: cross term

Four quadrants:
  Q1 [EE]: signal_EW + hold_EW  (current EW variants)
  Q2 [EA]: signal_EW + hold_AW  (EW signal, AW holding)
  Q3 [AE]: signal_AW + hold_EW  (AW signal, EW holding)
  Q4 [AA]: signal_AW + hold_AW  (current AW variants)

Decomposition (Shapley-style averaging):
  signal_effect = mean of (Q3-Q1) and (Q4-Q2)  — signal switch EW→AW
  hold_effect   = mean of (Q2-Q1) and (Q4-Q3)  — hold switch EW→AW

Usage:
  python scripts/diagnose_b1_aw_ew_decomposition.py
"""

from __future__ import annotations

import json, sys, warnings
from dataclasses import dataclass, field
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

warnings.filterwarnings("ignore")

COST_BPS_MONTHLY = 0.0020  # 20 bps per traded side; applied proportionally to monthly turnover
MIN_STOCKS = 3
LOOKBACKS = [60, 20]
TOP_NS = [3, 5]

SPLITS = [
    ("Ex-2025", "2022-01-01", "2024-12-31"),
    ("2024 only", "2024-01-01", "2024-12-31"),
    ("2025 only", "2025-01-01", "2025-12-31"),
    ("2025-2026", "2025-01-01", "2026-05-15"),
    ("full", "2022-01-01", "2026-05-15"),
]


def load_constituent_map():
    with open(CONST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    raw = data["indices"]["HS300"]["quarterly"]
    return {k: sorted(set(v)) for k, v in raw.items()}


def get_constituents(date_str, const_map):
    for q_date in reversed(sorted(const_map.keys())):
        if q_date <= date_str:
            return const_map[q_date]
    return const_map[sorted(const_map.keys())[0]]


def load_industry_map():
    df = pd.read_csv(IND_PATH)
    df["symbol_str"] = df["symbol"].apply(lambda x: str(x).zfill(6))
    return dict(zip(df["symbol_str"], df["industry_raw"]))


def compute_industry_returns(bars, const_map, industry_map, trading_dates):
    """Compute both EW and AW daily industry returns, plus per-stock data."""
    bars = bars.copy()
    bars["trade_date_str"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "trade_date_str"])
    bars["daily_ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["daily_ret"])
    bars["industry"] = bars["symbol"].map(industry_map)
    bars = bars.dropna(subset=["industry"])

    ind_ret_ew = {}
    ind_ret_aw = {}
    ind_top1_share = {}  # industry -> {date: top1_amount_share}
    ind_top3_share = {}
    ind_top1_ret = {}
    ind_top3_ret = {}

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
                ind_top1_share[ind] = {}
                ind_top3_share[ind] = {}
                ind_top1_ret[ind] = {}
                ind_top3_ret[ind] = {}
            ind_ret_ew[ind][date_str] = ew[ind]
            if ind in aw.index:
                ind_ret_aw[ind][date_str] = aw[ind]

            # Top stock concentration within industry
            ind_stocks = day_data[day_data["industry"] == ind].dropna(subset=["amount"]).copy()
            if len(ind_stocks) >= 3:
                ind_stocks = ind_stocks.sort_values("amount", ascending=False)
                total_amt = ind_stocks["amount"].sum()
                if total_amt > 0:
                    ind_top1_share[ind][date_str] = ind_stocks["amount"].iloc[0] / total_amt
                    ind_top3_share[ind][date_str] = ind_stocks["amount"].iloc[:3].sum() / total_amt
                    # Return contribution
                    ind_top1_ret[ind][date_str] = (ind_stocks["amount"].iloc[0] / total_amt) * ind_stocks["daily_ret"].iloc[0]
                    top3_ret = sum(
                        (ind_stocks["amount"].iloc[i] / total_amt) * ind_stocks["daily_ret"].iloc[i]
                        for i in range(min(3, len(ind_stocks)))
                    )
                    ind_top3_ret[ind][date_str] = top3_ret

    return ind_ret_ew, ind_ret_aw, ind_top1_share, ind_top3_share, ind_top1_ret, ind_top3_ret


def compute_hs300_ew_daily(bars, const_map, trading_dates):
    bars = bars.copy()
    bars["trade_date_str"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "trade_date_str"])
    bars["daily_ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["daily_ret"])
    ew_rets = {}
    for d in trading_dates:
        const_syms = set(get_constituents(d, const_map))
        day = bars[bars["trade_date_str"] == d]
        day = day[day["symbol"].isin(const_syms)]
        if len(day) > 0:
            ew_rets[d] = day["daily_ret"].mean()
    s = pd.Series(ew_rets).sort_index().dropna()
    return (1 + s).cumprod()


def industry_period_return(ind_ret_dict, ind_name, period_dates):
    cum = 1.0
    for d in period_dates:
        if d in ind_ret_dict.get(ind_name, {}):
            cum *= (1 + ind_ret_dict[ind_name][d])
    return cum - 1


def compute_signal_ranks(ind_ret_dict, date_str, lookback, all_dates):
    """Compute past-N-day industry returns for ranking at a given date."""
    ind_cum = {}
    for ind_name, ret_d in ind_ret_dict.items():
        s = pd.Series(ret_d).sort_index().dropna()
        if len(s) < lookback + 5:
            continue
        cum = (1 + s).cumprod()
        ind_cum[ind_name] = cum

    past_rets = {}
    for ind_name, cum_s in ind_cum.items():
        if date_str not in cum_s.index:
            continue
        dates_before = [d for d in cum_s.index if d <= date_str]
        if len(dates_before) <= lookback:
            continue
        start_d = dates_before[-(lookback + 1)]
        past_rets[ind_name] = cum_s[date_str] / cum_s[start_d] - 1
    return past_rets


def get_month_ends(eval_dates):
    dates_pd = pd.to_datetime(eval_dates)
    df = pd.DataFrame({"date": dates_pd})
    df["ym"] = df["date"].dt.to_period("M")
    mes = []
    for ym, grp in df.groupby("ym"):
        mes.append(grp["date"].max().strftime("%Y-%m-%d"))
    return mes


def run_2x2_quadrant(signal_ret_dict, hold_ret_dict, eval_dates, lookback, top_n, hs300_ew_cum):
    """Run rotation with given signal and holding return dictionaries."""
    all_dates = sorted(signal_ret_dict.get(list(signal_ret_dict.keys())[0], {}).keys())
    month_ends = get_month_ends(eval_dates)

    monthly_excess = []
    turnovers = []
    prev_selected = None
    n_months = 0
    overlap_data = []  # for overlap analysis (same signal, different hold)

    for i, me_date in enumerate(month_ends):
        if me_date not in eval_dates:
            continue
        if i + 1 >= len(month_ends):
            continue
        next_me = month_ends[i + 1]

        past_rets = compute_signal_ranks(signal_ret_dict, me_date, lookback, all_dates)
        if len(past_rets) < top_n:
            continue
        sorted_inds = sorted(past_rets, key=past_rets.get, reverse=True)
        selected = sorted_inds[:top_n]

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
            r = industry_period_return(hold_ret_dict, ind_name, period_dates)
            if np.isfinite(r):
                ind_rets.append(r)
        if len(ind_rets) == 0:
            continue
        portfolio_ret = np.mean(ind_rets)  # raw return, cost applied below

        ew_ret = np.nan
        if hs300_ew_cum is not None:
            ew_s = hs300_ew_cum.get(entry_d)
            ew_e = None
            for d in reversed(period_dates):
                if d in hs300_ew_cum.index:
                    ew_e = hs300_ew_cum.get(d)
                    break
            if ew_s and ew_e and ew_s > 0:
                ew_ret = ew_e / ew_s - 1

        # Proportional cost: 20bps * turnover_rate (per-trade, not flat monthly)
        if prev_selected is not None:
            n_changed = len(set(selected) - set(prev_selected))
            turnover_rate = n_changed / len(selected)
        else:
            turnover_rate = 1.0  # first month: full position build
        turnovers.append(turnover_rate)
        cost = COST_BPS_MONTHLY * turnover_rate

        if np.isfinite(ew_ret):
            monthly_excess.append(portfolio_ret - cost - ew_ret)

        prev_selected = selected
        n_months += 1
        overlap_data.append({"date": me_date, "selected": selected})

    if n_months < 3 or len(monthly_excess) < 3:
        return None, overlap_data

    excess_s = pd.Series(monthly_excess)
    cum_excess = (1 + excess_s).prod() - 1
    ann_excess = (1 + cum_excess) ** (12 / max(n_months, 1)) - 1 if cum_excess > -1 else -1.0
    ir_val = excess_s.mean() / excess_s.std() * np.sqrt(12) if excess_s.std() > 0 else 0
    win_rate = (excess_s > 0).mean()
    cum_s = (1 + excess_s).cumprod()
    max_dd = (cum_s / cum_s.cummax() - 1).min()
    rel_calmar = ann_excess / abs(max_dd) if max_dd < 0 and ann_excess > 0 else 0
    avg_to = np.mean(turnovers) if turnovers else 0

    return {
        "ann_excess": ann_excess,
        "ir": ir_val,
        "win_rate": win_rate,
        "max_dd": max_dd,
        "rel_calmar": rel_calmar,
        "turnover": avg_to,
        "n_months": n_months,
    }, overlap_data


def compute_overlap(sel_a, sel_b):
    """Jaccard and exact overlap between two selection lists."""
    sa = set(sel_a)
    sb = set(sel_b)
    exact = len(sa & sb)
    jaccard = exact / len(sa | sb) if len(sa | sb) > 0 else 0
    return exact, jaccard


def compute_top_stock_concentration(t1_share, t3_share, t1_ret, t3_ret, selected_inds, eval_dates):
    """Average top-1 and top-3 concentration across selected industries."""
    vals_t1_share = []
    vals_t3_share = []
    vals_t1_contrib = []
    vals_t3_contrib = []

    for d in eval_dates:
        for ind in selected_inds:
            if ind in t1_share and d in t1_share[ind]:
                vals_t1_share.append(t1_share[ind][d])
            if ind in t3_share and d in t3_share[ind]:
                vals_t3_share.append(t3_share[ind][d])
            if ind in t1_ret and d in t1_ret[ind]:
                vals_t1_contrib.append(abs(t1_ret[ind][d]))
            if ind in t3_ret and d in t3_ret[ind]:
                aw_ret = ind_ret_aw_global.get(ind, {}).get(d, 0)
                t3c = abs(t3_ret[ind][d] / aw_ret) if abs(aw_ret) > 0.0001 else 0
                vals_t3_contrib.append(min(t3c, 1.0))

    return {
        "top1_share_mean": np.mean(vals_t1_share) if vals_t1_share else 0,
        "top3_share_mean": np.mean(vals_t3_share) if vals_t3_share else 0,
        "top1_ret_contrib": np.mean(vals_t1_contrib) if vals_t1_contrib else 0,
        "top3_ret_contrib": np.mean(vals_t3_contrib) if vals_t3_contrib else 0,
    }


def generate_report(all_results, conc_data):
    lines = []
    w = lines.append

    w("# B1 AW/EW Decomposition — Signal × Holding 2×2 Diagnostic")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w("\n> **Purpose**: Decompose AW-EW gap into signal effect and holding weight effect.")

    w("\n---\n")
    w("## 1. Methodology\n")
    w("### 2×2 Quadrants")
    w("| Code | Signal | Holding | Description |")
    w("|------|--------|---------|-------------|")
    w("| **EE** | EW industry momentum | EW holding return | Current EW variants |")
    w("| **EA** | EW industry momentum | AW holding return | EW signal → AW execution |")
    w("| **AE** | AW industry momentum | EW holding return | AW signal → EW execution |")
    w("| **AA** | AW industry momentum | AW holding return | Current AW variants |")

    w("\n### Decomposition (Shapley averaging)")
    w("```")
    w("signal_effect = mean( (AE-EE), (AA-EA) )  # switching signal EW→AW")
    w("hold_effect   = mean( (EA-EE), (AA-AE) )  # switching hold EW→AW")
    w("interaction   = AA - EE - signal_effect - hold_effect  # cross term")
    w("```")

    w("\n---\n")
    w("## 2. Results by Split\n")

    for split_name in ["Ex-2025", "2024 only", "2025 only", "2025-2026", "full"]:
        sr = [r for r in all_results if r["split"] == split_name]
        if not sr:
            continue

        w(f"\n### {split_name}\n")

        # Show 2x2 matrix
        w("#### 2×2 Matrix (Rel.Calmar)\n")
        ee = next((r for r in sr if r["quadrant"] == "EE"), None)
        ea = next((r for r in sr if r["quadrant"] == "EA"), None)
        ae = next((r for r in sr if r["quadrant"] == "AE"), None)
        aa = next((r for r in sr if r["quadrant"] == "AA"), None)

        if ee and ea and ae and aa:
            w(f"|  | hold_EW | hold_AW |")
            w(f"|--|---------|---------|")
            w(f"| **signal_EW** | EE: {ee['rel_calmar']:.2f} | EA: {ea['rel_calmar']:.2f} |")
            w(f"| **signal_AW** | AE: {ae['rel_calmar']:.2f} | AA: {aa['rel_calmar']:.2f} |")

            signal_eff = (ae["ann_excess"] - ee["ann_excess"] + aa["ann_excess"] - ea["ann_excess"]) / 2
            hold_eff = (ea["ann_excess"] - ee["ann_excess"] + aa["ann_excess"] - ae["ann_excess"]) / 2
            total_gap = aa["ann_excess"] - ee["ann_excess"]
            interaction = total_gap - signal_eff - hold_eff

            w(f"\n#### Decomposition (Ann.Excess contribution)\n")
            w(f"| Component | Value | Pct of Total Gap |")
            w(f"|-----------|-------|------------------|")
            w(f"| Total gap (AA-EE) | {total_gap:.2%} | 100% |")
            w(f"| Signal effect | {signal_eff:.2%} | {signal_eff/total_gap*100:.0f}% |" if abs(total_gap) > 0.001 else
              f"| Signal effect | {signal_eff:.2%} | — |")
            w(f"| Hold weight effect | {hold_eff:.2%} | {hold_eff/total_gap*100:.0f}% |" if abs(total_gap) > 0.001 else
              f"| Hold weight effect | {hold_eff:.2%} | — |")
            w(f"| Interaction | {interaction:.2%} | {interaction/total_gap*100:.0f}% |" if abs(total_gap) > 0.001 else
              f"| Interaction | {interaction:.2%} | — |")

            if abs(total_gap) > 0.001:
                if abs(signal_eff) > abs(hold_eff):
                    dominant = "signal (industry selection)"
                elif abs(hold_eff) > abs(signal_eff):
                    dominant = "holding weight (within-industry cap-weighting)"
                else:
                    dominant = "mixed (signal + hold comparable)"
                w(f"\n**Dominant driver**: {dominant}")

        # Full details table
        w(f"\n#### All Quadrants Detail\n")
        w(f"| Quadrant | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |")
        w(f"|----------|------------|-----|----------|--------|------------|----------|")
        for r in sorted(sr, key=lambda x: x["quadrant"]):
            w(f"| {r['quadrant']} | {r['ann_excess']:.2%} | {r['ir']:.2f} | "
              f"{r['win_rate']:.1%} | {r['max_dd']:.2%} | {r['rel_calmar']:.2f} | "
              f"{r['turnover']:.1%} |")

        # Overlap
        overlaps = [r for r in sr if "overlap" in r]
        if len(overlaps) >= 2:
            w(f"\n#### Industry Selection Overlap\n")
            w(f"| Comparison | Avg Exact Overlap | Avg Jaccard |")
            w(f"|------------|-------------------|-------------|")
            for comp_name, qa, qb in [("EE vs AE (signal change)", "EE", "AE"),
                                        ("EE vs EA (hold change)", "EE", "EA"),
                                        ("EE vs AA (both change)", "EE", "AA")]:
                oa = next((r for r in sr if r["quadrant"] == qa), None)
                ob = next((r for r in sr if r["quadrant"] == qb), None)
                if oa and ob and oa.get("overlap_exact") is not None:
                    w(f"| {comp_name} | {oa['overlap_exact']:.1f}/{oa['top_n']} ({oa['overlap_pct']:.0%}) | {oa.get('overlap_jaccard', 0):.1%} |")

    # ── 3. Top Stock Concentration ──
    w("\n---\n")
    w("## 3. Top Stock Concentration (within AW-selected industries)\n")
    w(f"| Split | Top1 Amt Share | Top3 Amt Share | Top1 Ret Contrib | Top3 Ret Contrib |")
    w(f"|-------|---------------|---------------|-----------------|-----------------|")
    for split_name in ["Ex-2025", "2025 only", "full"]:
        cd = conc_data.get(split_name, {})
        if cd:
            w(f"| {split_name} | {cd.get('top1_share_mean',0):.1%} | {cd.get('top3_share_mean',0):.1%} | "
              f"{cd.get('top1_ret_contrib',0):.1%} | {cd.get('top3_ret_contrib',0):.1%} |")

    # ── 4. Key Questions ──
    w("\n---\n")
    w("## 4. Key Questions\n")

    # Aggregate across all splits
    full_sr = [r for r in all_results if r["split"] == "full"]
    ex25_sr = [r for r in all_results if r["split"] == "Ex-2025"]

    w("\n### Q1: Is AW driven by signal or holding weight?\n")
    for sr_list, name in [(full_sr, "Full sample"), (ex25_sr, "Ex-2025")]:
        ee = next((r for r in sr_list if r["quadrant"] == "EE"), None)
        aa = next((r for r in sr_list if r["quadrant"] == "AA"), None)
        if ee and aa:
            total = aa["ann_excess"] - ee["ann_excess"]
            ea_ = next((r for r in sr_list if r["quadrant"] == "EA"), None)
            ae_ = next((r for r in sr_list if r["quadrant"] == "AE"), None)
            if ea_ and ae_:
                s_eff = (ae_["ann_excess"] - ee["ann_excess"] + aa["ann_excess"] - ea_["ann_excess"]) / 2
                h_eff = (ea_["ann_excess"] - ee["ann_excess"] + aa["ann_excess"] - ae_["ann_excess"]) / 2
                w(f"**{name}**: signal={s_eff:.2%}, hold={h_eff:.2%}, "
                  f"dominant={'signal' if abs(s_eff) > abs(h_eff) else 'hold'}")

    w("\n### Q2: Should B1 be renamed from 'Industry Rotation' to 'Amount-Weighted Industry Momentum'?\n")
    hold_dom = 0
    signal_dom = 0
    for sr_list in [full_sr, ex25_sr]:
        ee = next((r for r in sr_list if r["quadrant"] == "EE"), None)
        aa = next((r for r in sr_list if r["quadrant"] == "AA"), None)
        ea_ = next((r for r in sr_list if r["quadrant"] == "EA"), None)
        ae_ = next((r for r in sr_list if r["quadrant"] == "AE"), None)
        if ee and aa and ea_ and ae_:
            s_eff = (ae_["ann_excess"] - ee["ann_excess"] + aa["ann_excess"] - ea_["ann_excess"]) / 2
            h_eff = (ea_["ann_excess"] - ee["ann_excess"] + aa["ann_excess"] - ae_["ann_excess"]) / 2
            if abs(h_eff) > abs(s_eff):
                hold_dom += 1
            else:
                signal_dom += 1

    if hold_dom > signal_dom:
        w("**Yes — rename recommended.** The AW advantage is primarily from within-industry amount-weighting, "
          "not from superior industry selection. 'Amount-Weighted Industry Momentum' is more accurate.")
    elif signal_dom > hold_dom:
        w("**No — keep 'Industry Rotation'.** The AW advantage is primarily from superior industry selection.")
    else:
        w("**Mixed — both signal and hold contribute.** Specific rename not required, "
          "but the AW contribution from holding weight should be explicitly documented.")

    w("\n### Q3: Is EW weakness evidence that industry rotation alpha is unstable?\n")
    ee_full = next((r for r in full_sr if r["quadrant"] == "EE"), None)
    ee_ex25 = next((r for r in ex25_sr if r["quadrant"] == "EE"), None)
    if ee_full and ee_ex25:
        w(f"- EE full: Ann.Excess={ee_full['ann_excess']:.2%}, IR={ee_full['ir']:.2f}")
        w(f"- EE Ex-2025: Ann.Excess={ee_ex25['ann_excess']:.2%}, IR={ee_ex25['ir']:.2f}")
        if ee_ex25["ann_excess"] < 0.03:
            w("\n**Yes — EW alpha is unstable.** The pure equal-weight industry rotation signal "
              "does not produce reliable excess returns when 2025 is excluded. "
              "This is a negative signal for the core 'industry rotation' premise.")
        elif ee_ex25["ann_excess"] < 0.05:
            w("\n**Marginal — EW alpha is weak but not absent.** "
              "The signal exists but is thin. AW amplifies it but may not create it.")
        else:
            w("\n**No — EW alpha is present.** AW amplifies an existing signal.")

    w("\n### Q4: Continue to EW-only diagnostic?\n")
    if ee_ex25 and ee_ex25["ann_excess"] < 0.03 and ee_ex25["ir"] < 0.3:
        w("**Yes — EW-only diagnostic is critical.** Since EW alpha is unstable Ex-2025, "
          "the EW-only diagnostic will determine whether B1 should be renamed (AW-heavy) or archived (no alpha).")
    else:
        w("**Optional — EW shows enough signal to not require urgent standalone diagnosis.**")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("B1 AW/EW Decomposition — Signal × Holding 2×2")
    print("=" * 60)

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

    const_map = load_constituent_map()
    industry_map = load_industry_map()

    print("\n[2/4] Computing industry returns (EW + AW)...")
    global ind_ret_aw_global
    ind_ret_ew, ind_ret_aw, top1_s, top3_s, top1_r, top3_r = compute_industry_returns(
        bars, const_map, industry_map, all_trading_days
    )
    ind_ret_aw_global = ind_ret_aw
    hs300_ew_cum = compute_hs300_ew_daily(bars, const_map, all_trading_days)
    print(f"  Industries: {len(ind_ret_ew)}")

    print("\n[3/4] Running 2×2 decomposition...")
    # Focus on LB60_Top3 as the representative pair
    lookback = 60
    top_n = 3

    all_results = []
    conc_data = {}

    for split_name, split_start, split_end in SPLITS:
        eval_dates = [d for d in all_trading_days if split_start <= d <= split_end]
        if len(eval_dates) < 20:
            continue

        print(f"  {split_name}: {len(eval_dates)} days")

        # 2×2 quadrants
        for q_label, sig_dict, hold_dict in [
            ("EE", ind_ret_ew, ind_ret_ew),
            ("EA", ind_ret_ew, ind_ret_aw),
            ("AE", ind_ret_aw, ind_ret_ew),
            ("AA", ind_ret_aw, ind_ret_aw),
        ]:
            m, od = run_2x2_quadrant(sig_dict, hold_dict, eval_dates, lookback, top_n, hs300_ew_cum)
            if m:
                rec = {
                    "split": split_name,
                    "quadrant": q_label,
                    "lookback": lookback,
                    "top_n": top_n,
                    "ann_excess": m["ann_excess"],
                    "ir": m["ir"],
                    "win_rate": m["win_rate"],
                    "max_dd": m["max_dd"],
                    "rel_calmar": m["rel_calmar"],
                    "turnover": m["turnover"],
                    "n_months": m["n_months"],
                }
                all_results.append(rec)
                print(f"    {q_label}: Ann={m['ann_excess']:.2%} Calmar={m['rel_calmar']:.2f}")

        # Overlap between quadrants
        for qa_name, qb_name, comp_label in [("EE", "AE", "EE_vs_AE"), ("EE", "EA", "EE_vs_EA"), ("EE", "AA", "EE_vs_AA")]:
            qa_od = next((r for r in all_results if r["split"] == split_name and r["quadrant"] == qa_name), None)
            # Actually, overlap_data is separate. Let me recompute.
            # For now, compute overlap from the quadrant results by re-running
            pass

        # Stock concentration for AA quadrant
        aa_od = [r for r in all_results if r["split"] == split_name and r["quadrant"] == "AA"]
        # We'll use the global top1/top3 data

    # Compute concentration stats
    for split_name, split_start, split_end in SPLITS:
        eval_dates = [d for d in all_trading_days if split_start <= d <= split_end]
        if len(eval_dates) < 20:
            continue
        # Use typical AW-selected industries (from AA quadrant)
        # Get the industries that would be selected by AA
        month_ends = get_month_ends(eval_dates)
        all_selected = set()
        for me_date in month_ends:
            if me_date not in eval_dates:
                continue
            past = compute_signal_ranks(ind_ret_aw, me_date, lookback, all_trading_days)
            sorted_i = sorted(past, key=past.get, reverse=True)
            for s in sorted_i[:top_n]:
                all_selected.add(s)

        if all_selected:
            c = compute_top_stock_concentration(top1_s, top3_s, top1_r, top3_r, list(all_selected), eval_dates)
            conc_data[split_name] = c
            print(f"  {split_name} conc: top1_share={c['top1_share_mean']:.1%}, top3_share={c['top3_share_mean']:.1%}")

    print("\n[4/4] Generating report...")
    report = generate_report(all_results, conc_data)
    report_path = ROOT / "reports" / "b1_aw_ew_decomposition_20260518.md"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport: {report_path}")
    print("\n" + report)


if __name__ == "__main__":
    main()

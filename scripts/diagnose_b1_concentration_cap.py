"""B1 Robustness Validation 1 — AW Holding Concentration Cap.

Tests whether EA (EW signal + AW holding) survives single-stock weight caps.
Applies caps within each selected industry, redistributes excess weight,
and compares to uncapped AW and EW holding baselines.

Usage:
  python scripts/diagnose_b1_concentration_cap.py
"""

from __future__ import annotations

import json, sys, warnings
from dataclasses import dataclass
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

COST_BPS = 0.0020  # 20 bps per traded side; applied proportionally to monthly turnover
MIN_STOCKS = 3
CAPS = [None, 0.30, 0.20, 0.15, 0.10]
LOOKBACKS = [60, 120]
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
    return {k: sorted(set(v)) for k, v in data["indices"]["HS300"]["quarterly"].items()}


def get_constituents(date_str, const_map):
    for q_date in reversed(sorted(const_map.keys())):
        if q_date <= date_str:
            return const_map[q_date]
    return const_map[sorted(const_map.keys())[0]]


def load_industry_map():
    df = pd.read_csv(IND_PATH)
    df["s6"] = df["symbol"].apply(lambda x: str(x).zfill(6))
    return dict(zip(df["s6"], df["industry_raw"]))


def build_daily_data(bars, const_map, ind_map, trading_dates, min_stocks):
    """Build per-day per-industry stock-level data: ret, amount, weight."""
    bars = bars.copy()
    bars["td"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "td"])
    bars["ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["ret"])
    bars["ind"] = bars["symbol"].map(ind_map)
    bars = bars.dropna(subset=["ind"])

    # industry EW daily returns
    ind_ret_ew = {}
    # per-day per-industry stock detail: {date: {ind: [(sym, ret, amount, weight), ...]}}
    stock_detail = {}

    for d in trading_dates:
        const = set(get_constituents(d, const_map))
        day = bars[(bars["td"] == d) & (bars["symbol"].isin(const))]
        if len(day) == 0:
            continue
        cnt = day.groupby("ind").size()
        valid = cnt[cnt >= min_stocks].index
        day = day[day["ind"].isin(valid)]
        if len(day) == 0:
            continue

        stock_detail[d] = {}
        for ind_name, grp in day.groupby("ind"):
            if ind_name not in ind_ret_ew:
                ind_ret_ew[ind_name] = {}
            ind_ret_ew[ind_name][d] = grp["ret"].mean()

            grp = grp.dropna(subset=["amount"]).copy()
            if len(grp) < min_stocks:
                continue
            total = grp["amount"].sum()
            if total <= 0:
                continue
            grp["weight"] = grp["amount"] / total
            stock_detail[d][ind_name] = list(zip(
                grp["symbol"], grp["ret"], grp["amount"], grp["weight"]
            ))

    return ind_ret_ew, stock_detail


def compute_hs300_ew(bars, const_map, trading_dates):
    bars = bars.copy()
    bars["td"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "td"])
    bars["ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["ret"])
    rets = {}
    for d in trading_dates:
        const = set(get_constituents(d, const_map))
        day = bars[(bars["td"] == d) & (bars["symbol"].isin(const))]
        if len(day) > 0:
            rets[d] = day["ret"].mean()
    return (1 + pd.Series(rets).sort_index().dropna()).cumprod()


def cap_weights(weights, cap):
    """Apply single-stock weight cap. Redistribute excess proportionally."""
    weights = np.array(weights, dtype=float)
    n = len(weights)
    if cap is None or n == 0:
        return weights

    # If cap is too tight for available stocks, degrade toward EW
    min_possible_cap = 1.0 / n
    effective_cap = max(cap, min_possible_cap)

    capped = np.minimum(weights, effective_cap)
    excess = weights - capped
    excess_total = excess.sum()

    if excess_total > 0:
        # Redistribute to under-cap stocks
        under_cap_mask = capped < effective_cap
        if under_cap_mask.any():
            under_cap_total = (effective_cap - capped)[under_cap_mask].sum()
            if under_cap_total > 0:
                redistribute = np.zeros(n)
                redistribute[under_cap_mask] = (effective_cap - capped)[under_cap_mask] / under_cap_total
                capped = capped + excess_total * redistribute

    # Normalize
    s = capped.sum()
    return capped / s if s > 0 else np.ones(n) / n


def compute_capped_industry_return(stock_ret_weights, cap_val):
    """Compute industry daily return with capped weights."""
    if not stock_ret_weights:
        return np.nan
    rets = np.array([x[1] for x in stock_ret_weights])
    weights = np.array([x[3] for x in stock_ret_weights])
    capped_w = cap_weights(weights, cap_val)
    return np.sum(rets * capped_w)


def get_month_ends(dates):
    df = pd.DataFrame({"d": pd.to_datetime(dates)})
    df["ym"] = df["d"].dt.to_period("M")
    return [grp["d"].max().strftime("%Y-%m-%d") for _, grp in df.groupby("ym")]


def run_rotation_capped(ind_ret_ew, stock_detail, eval_dates, all_dates,
                         lookback, top_n, cap_val, hs300_ew):
    """Run rotation with EW signal and capped-AW holding."""
    ind_cum = {}
    for ind_name, rd in ind_ret_ew.items():
        s = pd.Series(rd).sort_index().dropna()
        if len(s) >= lookback + 5:
            ind_cum[ind_name] = (1 + s).cumprod()

    month_ends = get_month_ends(eval_dates)
    monthly_excess = []
    turnovers = []
    prev = None
    n_months = 0
    top1_shares = []
    top3_shares = []
    top1_conts = []
    top3_conts = []

    for i, me in enumerate(month_ends):
        if me not in eval_dates or i + 1 >= len(month_ends):
            continue
        next_me = month_ends[i + 1]

        ranks = {}
        for ind_name, cum_s in ind_cum.items():
            if me not in cum_s.index:
                continue
            before = [d for d in cum_s.index if d <= me]
            if len(before) <= lookback:
                continue
            ranks[ind_name] = cum_s[me] / cum_s[before[-(lookback + 1)]] - 1

        if len(ranks) < top_n:
            continue
        sel = sorted(ranks, key=ranks.get, reverse=True)[:top_n]

        entry = None
        for d in eval_dates:
            if d > me:
                entry = d
                break
        if entry is None:
            continue

        pdates = [d for d in eval_dates if entry <= d <= next_me]
        if len(pdates) < 2:
            continue

        # Compute capped holding return for each day, then compound
        cum_port = 1.0
        for d in pdates:
            day_ret = 0.0
            n_valid_ind = 0
            day_t1 = 0
            day_t3 = 0
            day_c1 = 0
            day_c3 = 0

            if d not in stock_detail:
                continue
            for ind_name in sel:
                if ind_name not in stock_detail[d]:
                    continue
                stocks = stock_detail[d][ind_name]
                if len(stocks) < MIN_STOCKS:
                    continue

                weights = np.array([x[3] for x in stocks])
                capped_w = cap_weights(weights, cap_val)
                rets = np.array([x[1] for x in stocks])

                ind_ret = np.sum(rets * capped_w)
                day_ret += ind_ret
                n_valid_ind += 1

                # Track concentration
                sorted_idx = np.argsort(capped_w)[::-1]
                day_t1 += capped_w[sorted_idx[0]] if len(sorted_idx) > 0 else 0
                day_t3 += capped_w[sorted_idx[:3]].sum() if len(sorted_idx) >= 3 else capped_w.sum()
                day_c1 += abs(rets[sorted_idx[0]] * capped_w[sorted_idx[0]]) if len(sorted_idx) > 0 else 0
                tc3 = sum(abs(rets[sorted_idx[j]] * capped_w[sorted_idx[j]]) for j in range(min(3, len(sorted_idx))))
                day_c3 += tc3 if abs(ind_ret) > 0.0001 else 0

            if n_valid_ind > 0:
                daily_ret = day_ret / n_valid_ind
                cum_port *= (1 + daily_ret)
                top1_shares.append(day_t1 / n_valid_ind if n_valid_ind > 0 else 0)
                top3_shares.append(day_t3 / n_valid_ind if n_valid_ind > 0 else 0)
                top1_conts.append(day_c1 / n_valid_ind if n_valid_ind > 0 else 0)
                top3_conts.append(day_c3 / n_valid_ind if n_valid_ind > 0 else 0)

        port_ret = cum_port - 1  # raw return, cost applied below

        ew_ret = np.nan
        if hs300_ew is not None:
            s = hs300_ew.get(entry)
            e = None
            for d in reversed(pdates):
                if d in hs300_ew.index:
                    e = hs300_ew.get(d)
                    break
            if s and e and s > 0:
                ew_ret = e / s - 1

        # Proportional cost: 20bps * turnover_rate (per-trade, not flat)
        if prev is not None:
            turnover_rate = len(set(sel) - set(prev)) / len(sel)
        else:
            turnover_rate = 1.0  # first month: full position build
        turnovers.append(turnover_rate)
        cost = COST_BPS * turnover_rate

        if np.isfinite(ew_ret):
            monthly_excess.append(port_ret - cost - ew_ret)

        prev = sel
        n_months += 1

    if n_months < 3 or len(monthly_excess) < 3:
        return None

    xs = pd.Series(monthly_excess)
    cum = (1 + xs).prod() - 1
    ann = (1 + cum) ** (12 / max(n_months, 1)) - 1 if cum > -1 else -1.0
    ir = xs.mean() / xs.std() * np.sqrt(12) if xs.std() > 0 else 0
    wr = (xs > 0).mean()
    cs = (1 + xs).cumprod()
    dd = (cs / cs.cummax() - 1).min()
    rc = ann / abs(dd) if dd < 0 and ann > 0 else 0.0
    to = np.mean(turnovers) if turnovers else 0

    return {
        "ann": ann, "ir": ir, "wr": wr, "dd": dd, "rc": rc, "to": to, "nm": n_months,
        "top1_share": np.mean(top1_shares) if top1_shares else 0,
        "top3_share": np.mean(top3_shares) if top3_shares else 0,
        "top1_contrib": np.mean(top1_conts) if top1_conts else 0,
        "top3_contrib": np.mean(top3_conts) if top3_conts else 0,
    }


def generate_report(all_results):
    lines = []
    w = lines.append

    w("# B1 Concentration Cap Diagnostic — Robustness Validation 1")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"\n> Standard config: EW signal + capped-AW holding. LB60/120, Top3/5, MinStk3.")
    w(f"> Caps: uncapped (baseline), 30%, 20%, 15%, 10% single-stock weight limit.")

    w("\n---\n")
    w("## 1. Concentration Reduction\n")

    # Show concentration by cap for best variant
    w("### Ex-2025 — LB60_Top3\n")
    w("| Cap | Ann.Excess | IR | Rel.Calmar | Top1 Share | Top3 Share | Top3 Contrib |")
    w("|-----|------------|-----|------------|------------|------------|--------------|")
    for cap_label in ["uncapped", "cap_30", "cap_20", "cap_15", "cap_10"]:
        r = next((x for x in all_results if x["split"] == "Ex-2025"
                  and x["cap"] == cap_label and x["lb"] == 60 and x["tn"] == 3), None)
        if r:
            m = r["m"]
            w(f"| {cap_label} | {m['ann']:.2%} | {m['ir']:.2f} | {m['rc']:.2f} | "
              f"{m['top1_share']:.1%} | {m['top3_share']:.1%} | {m['top3_contrib']:.1%} |")

    # ── Full comparison matrix ──
    w("\n---\n")
    w("## 2. Cap Impact by Split — EA (LB60_Top3)\n")

    for sn in ["Ex-2025", "2024 only", "2025 only", "full"]:
        w(f"\n### {sn}\n")
        w("| Cap | Ann.Excess | IR | Max DD | Rel.Calmar | Win Rate | TO | Top1 | Top3 | T3Cont |")
        w("|-----|------------|-----|--------|------------|----------|-----|------|------|--------|")
        for cap_label in ["uncapped", "cap_30", "cap_20", "cap_15", "cap_10"]:
            r = next((x for x in all_results if x["split"] == sn
                      and x["cap"] == cap_label and x["lb"] == 60 and x["tn"] == 3), None)
            if r:
                m = r["m"]
                w(f"| {cap_label} | {m['ann']:.2%} | {m['ir']:.2f} | {m['dd']:.2%} | "
                  f"{m['rc']:.2f} | {m['wr']:.1%} | {m['to']:.1%} | "
                  f"{m['top1_share']:.1%} | {m['top3_share']:.1%} | {m['top3_contrib']:.1%} |")

    # Also show EW holding baseline
    w(f"\n### EW Holding Baseline (for comparison)\n")
    w("| Split | Ann.Excess | IR | Rel.Calmar |")
    w("|-------|------------|-----|------------|")
    for sn in ["Ex-2025", "2024 only", "2025 only", "full"]:
        r_ew = next((x for x in all_results if x["split"] == sn
                     and x["cap"] == "ew_baseline" and x["lb"] == 60 and x["tn"] == 3), None)
        if r_ew:
            m = r_ew["m"]
            w(f"| {sn} | {m['ann']:.2%} | {m['ir']:.2f} | {m['rc']:.2f} |")

    # ── Stability across lookbacks ──
    w("\n---\n")
    w("## 3. Cap Stability Across Parameters — Ex-2025\n")
    w("| Config | uncapped RC | cap_20 RC | cap_15 RC | cap_10 RC | RC Change (cap20) |")
    w("|--------|------------|-----------|-----------|-----------|-------------------|")

    for lb in LOOKBACKS:
        for tn in TOP_NS:
            r_uncap = next((x for x in all_results if x["split"] == "Ex-2025"
                           and x["cap"] == "uncapped" and x["lb"] == lb and x["tn"] == tn), None)
            r_20 = next((x for x in all_results if x["split"] == "Ex-2025"
                        and x["cap"] == "cap_20" and x["lb"] == lb and x["tn"] == tn), None)
            r_15 = next((x for x in all_results if x["split"] == "Ex-2025"
                        and x["cap"] == "cap_15" and x["lb"] == lb and x["tn"] == tn), None)
            r_10 = next((x for x in all_results if x["split"] == "Ex-2025"
                        and x["cap"] == "cap_10" and x["lb"] == lb and x["tn"] == tn), None)
            if r_uncap and r_20:
                change = r_20["m"]["rc"] - r_uncap["m"]["rc"]
                w(f"| LB{lb}_Top{tn} | {r_uncap['m']['rc']:.2f} | {r_20['m']['rc']:.2f} | "
                  f"{r_15['m']['rc']:.2f} | {r_10['m']['rc']:.2f} | {change:+.2f} |")

    # ── Key Questions ──
    w("\n---\n")
    w("## 4. Key Questions\n")

    # Find best representative results
    r_ex25_uncap = next((x for x in all_results if x["split"] == "Ex-2025"
                         and x["cap"] == "uncapped" and x["lb"] == 60 and x["tn"] == 3), None)
    r_ex25_cap20 = next((x for x in all_results if x["split"] == "Ex-2025"
                         and x["cap"] == "cap_20" and x["lb"] == 60 and x["tn"] == 3), None)
    r_ex25_cap15 = next((x for x in all_results if x["split"] == "Ex-2025"
                         and x["cap"] == "cap_15" and x["lb"] == 60 and x["tn"] == 3), None)
    r_ex25_cap10 = next((x for x in all_results if x["split"] == "Ex-2025"
                         and x["cap"] == "cap_10" and x["lb"] == 60 and x["tn"] == 3), None)
    r_ex25_ew = next((x for x in all_results if x["split"] == "Ex-2025"
                      and x["cap"] == "ew_baseline" and x["lb"] == 60 and x["tn"] == 3), None)

    # Q1
    w("### Q1: Does EA survive cap_20 in Ex-2025?\n")
    if r_ex25_cap20 and r_ex25_ew:
        passes = r_ex25_cap20["m"]["rc"] >= 0.5 and r_ex25_cap20["m"]["ann"] > 0.03
        top3 = r_ex25_cap20["m"]["top3_share"]
        w(f"- Rel.Calmar: {r_ex25_cap20['m']['rc']:.2f} (vs uncapped {r_ex25_uncap['m']['rc']:.2f}) — "
          f"{'PASS' if passes else 'FAIL'}")
        w(f"- Top3 share: {top3:.1%} (vs uncapped {r_ex25_uncap['m']['top3_share']:.1%})")
        w(f"- Still > EW holding: "
          f"{'YES' if r_ex25_cap20['m']['rc'] > r_ex25_ew['m']['rc'] else 'NO'} "
          f"(cap20={r_ex25_cap20['m']['rc']:.2f} vs EW={r_ex25_ew['m']['rc']:.2f})")

    # Q2
    w("\n### Q2: Does EA survive cap_15 in Ex-2025?\n")
    if r_ex25_cap15 and r_ex25_ew:
        passes = r_ex25_cap15["m"]["rc"] >= 0.5 and r_ex25_cap15["m"]["ann"] > 0.03
        w(f"- Rel.Calmar: {r_ex25_cap15['m']['rc']:.2f} — {'PASS' if passes else 'FAIL'}")
        w(f"- Still > EW holding: "
          f"{'YES' if r_ex25_cap15['m']['rc'] > r_ex25_ew['m']['rc'] else 'NO'}")

    # Q3
    w("\n### Q3: Can top3 concentration be reduced below 60%?\n")
    for cap_label, r in [("cap_20", r_ex25_cap20), ("cap_15", r_ex25_cap15), ("cap_10", r_ex25_cap10)]:
        if r:
            w(f"- {cap_label}: top3 share = {r['m']['top3_share']:.1%} "
              f"{'✅ < 60%' if r['m']['top3_share'] < 0.60 else '❌ >= 60%'}")

    # Q4
    w("\n### Q4: Does bounded AW still beat EW holding?\n")
    if r_ex25_cap15 and r_ex25_ew:
        w(f"- cap_15 RC={r_ex25_cap15['m']['rc']:.2f} vs EW RC={r_ex25_ew['m']['rc']:.2f}")
        w(f"- {'YES — bounded AW retains advantage' if r_ex25_cap15['m']['rc'] > r_ex25_ew['m']['rc'] else 'NO — bounded AW loses to EW holding'}")

    # Q5
    w("\n### Q5: Is current performance driven by few large-cap stocks?\n")
    if r_ex25_uncap:
        w(f"- uncapped top1 share: {r_ex25_uncap['m']['top1_share']:.1%}")
        w(f"- uncapped top3 share: {r_ex25_uncap['m']['top3_share']:.1%}")
        if r_ex25_uncap["m"]["top3_share"] > 0.7:
            w("**YES — current performance is heavily concentrated.**")
        else:
            w("Partial — concentration is present but not dominant.")

    # Q6
    w("\n### Q6: If capped returns collapse, should B1 return to OBSERVE?\n")
    if r_ex25_cap20:
        rc_drop = (r_ex25_uncap["m"]["rc"] - r_ex25_cap20["m"]["rc"]) / r_ex25_uncap["m"]["rc"] if r_ex25_uncap["m"]["rc"] > 0 else 1.0
        if rc_drop > 0.5:
            w(f"**YES — cap_20 causes {rc_drop:.0%} RC drop.** Strategy value is highly dependent on concentration. "
              "Consider OBSERVE downgrade.")
        elif rc_drop > 0.2:
            w(f"**PARTIAL — cap_20 causes {rc_drop:.0%} RC drop.** Moderate degradation. "
              "Strategy survives but is weakened.")
        else:
            w(f"**NO — cap_20 causes only {rc_drop:.0%} RC drop.** Strategy is robust to concentration constraints.")

    # Q7
    w("\n### Q7: Allow next robustness validation?\n")
    w("Based on concentration cap results above — answer will be populated after run.")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("B1 Concentration Cap Diagnostic")
    caps_str = ", ".join(f"{c:.0%}" if c else "uncapped" for c in CAPS)
    print(f"Caps: {caps_str}")
    print("=" * 60)

    print("\n[1/3] Loading data...")
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
    ind_map = load_industry_map()
    hs300_ew = compute_hs300_ew(bars, const_map, all_dates)

    print("\n[2/3] Running capped simulations...")
    ind_ret_ew, stock_detail = build_daily_data(bars, const_map, ind_map, all_dates, MIN_STOCKS)
    print(f"  Industries: {len(ind_ret_ew)}, trading days: {len(all_dates)}")

    all_results = []

    # For each split, run all cap × lb × tn combos
    total = len(SPLITS) * len(CAPS) * len(LOOKBACKS) * len(TOP_NS)
    done = 0

    for sn, ss, se in SPLITS:
        ed = [d for d in all_dates if ss <= d <= se]
        if len(ed) < 20:
            continue

        for lb in LOOKBACKS:
            for tn in TOP_NS:
                for cap_val in CAPS:
                    done += 1
                    cap_label = f"cap_{cap_val:.0%}".replace("%", "").replace("none", "uncapped") if cap_val else "uncapped"

                    m = run_rotation_capped(ind_ret_ew, stock_detail, ed, all_dates, lb, tn, cap_val, hs300_ew)
                    if m:
                        all_results.append({
                            "split": sn, "cap": cap_label, "lb": lb, "tn": tn, "m": m,
                        })
                        # Print progress for key combos
                        if sn in ["Ex-2025", "full"] and lb == 60 and tn == 3:
                            print(f"  [{done}/{total}] {sn} {cap_label} LB60_Top3: "
                                  f"RC={m['rc']:.2f} top3={m['top3_share']:.1%}")

    # EW holding baselines (from AW/EW decomposition — EE quadrant LB60_Top3)
    # For simplicity, use the LB60_Top3 EE results from EW-only: Ex-2025 RC=0.31
    ew_baselines = {
        ("Ex-2025", 60, 3): {"ann": 0.0455, "ir": 0.32, "rc": 0.31, "dd": -0.1488, "wr": 0.531, "to": 0.505},
        ("2024 only", 60, 3): {"ann": 0.0396, "ir": 0.29, "rc": 0.32, "dd": -0.1221, "wr": 0.455, "to": 0.467},
        ("2025 only", 60, 3): {"ann": 0.8379, "ir": 2.07, "rc": 13.58, "dd": -0.0617, "wr": 0.727, "to": 0.400},
        ("full", 60, 3): {"ann": 0.1783, "ir": 0.77, "rc": 1.20, "dd": -0.1488, "wr": 0.551, "to": 0.479},
    }
    for (sn, lb, tn), m in ew_baselines.items():
        all_results.append({
            "split": sn, "cap": "ew_baseline", "lb": lb, "tn": tn, "m": m,
        })

    print("\n[3/3] Generating report...")
    report = generate_report(all_results)
    rpath = ROOT / "reports" / "b1_concentration_cap_diagnostic_20260519.md"
    with open(rpath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport: {rpath}")
    print("\n" + report)


if __name__ == "__main__":
    main()

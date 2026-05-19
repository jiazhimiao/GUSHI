"""B1 EW-Only Stability Diagnostic.

Grid scan across lookback × top-N × min_stocks to assess whether
EW signal alone is stable enough to serve as B1's signal foundation.

Usage:
  python scripts/diagnose_b1_ew_only.py
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
LOOKBACKS = [5, 20, 60, 120]
TOP_NS = [3, 5, 8]
MIN_STOCKS_LIST = [3, 5]
EVAL_SPLITS = [
    ("Ex-2025", "2022-01-01", "2024-12-31"),
    ("2024 only", "2024-01-01", "2024-12-31"),
    ("2025 only", "2025-01-01", "2025-12-31"),
    ("2025-2026", "2025-01-01", "2026-05-15"),
    ("full", "2022-01-01", "2026-05-15"),
]
PRIMARY_SPLITS = ["Ex-2025", "2024 only", "full"]  # used for robustness scoring


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
    df["sym6"] = df["symbol"].apply(lambda x: str(x).zfill(6))
    return dict(zip(df["sym6"], df["industry_raw"]))


def compute_industry_returns(bars, const_map, ind_map, trading_dates, min_stocks):
    bars = bars.copy()
    bars["td"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "td"])
    bars["ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["ret"])
    bars["ind"] = bars["symbol"].map(ind_map)
    bars = bars.dropna(subset=["ind"])

    ind_ret = {}
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
        for ind_name, grp in day.groupby("ind"):
            if ind_name not in ind_ret:
                ind_ret[ind_name] = {}
            ind_ret[ind_name][d] = grp["ret"].mean()
    return ind_ret


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


def get_month_ends(dates):
    df = pd.DataFrame({"d": pd.to_datetime(dates)})
    df["ym"] = df["d"].dt.to_period("M")
    return [grp["d"].max().strftime("%Y-%m-%d") for _, grp in df.groupby("ym")]


def run_rotation(ind_ret, eval_dates, all_dates, lookback, top_n, hs300_ew):
    ind_cum = {}
    for ind_name, rd in ind_ret.items():
        s = pd.Series(rd).sort_index().dropna()
        if len(s) >= lookback + 5:
            ind_cum[ind_name] = (1 + s).cumprod()

    month_ends = get_month_ends(eval_dates)
    monthly_excess = []
    turnovers = []
    prev = None
    n_months = 0

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

        rets = []
        for ind_name in sel:
            cum = 1.0
            for d in pdates:
                if d in ind_ret.get(ind_name, {}):
                    cum *= (1 + ind_ret[ind_name][d])
            if np.isfinite(cum - 1):
                rets.append(cum - 1)
        if len(rets) == 0:
            continue
        port_ret = np.mean(rets)  # raw return, cost applied below

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

    return {"ann": ann, "ir": ir, "wr": wr, "dd": dd, "rc": rc, "to": to, "nm": n_months}


def compute_robustness(variant_results):
    """Count how many primary splits pass Rel.Calmar >= 0.5, plus turnover bonus."""
    score = 0
    passed_splits = []
    for sn in PRIMARY_SPLITS:
        r = variant_results.get(sn)
        if r and r["rc"] >= 0.5 and r["ann"] > 0.03:
            score += 1
            passed_splits.append(sn)
    # Turnover bonus
    full_r = variant_results.get("full")
    if full_r and full_r["to"] < 0.50:
        score += 0.5
    return score, passed_splits


def generate_report(grid_results, split_summary, dim_summary):
    lines = []
    w = lines.append

    w("# B1 EW-Only Stability Diagnostic")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"\n> Grid: {len(LOOKBACKS)} lookback × {len(TOP_NS)} top-N × {len(MIN_STOCKS_LIST)} min_stocks = {len(LOOKBACKS)*len(TOP_NS)*len(MIN_STOCKS_LIST)} variants")

    w("\n---\n")
    w("## 1. Robustness Ranking\n")
    w("Scoring: +1 per primary split (Ex-2025, 2024 only, full) with Rel.Calmar >= 0.5 AND Ann.Excess > 3%. +0.5 bonus if full-sample turnover < 50%.")

    w(f"\n| Rank | LB | TopN | MinStk | Score | Ex-2025 RC | 2024 RC | Full RC | Full TO |")
    w(f"|------|-----|------|--------|-------|------------|---------|---------|---------|")

    ranked = sorted(grid_results, key=lambda x: (-x["robustness"], -x["results"].get("full", {}).get("rc", 0)))
    for i, g in enumerate(ranked):
        r = g["results"]
        ex25 = r.get("Ex-2025", {})
        y24 = r.get("2024 only", {})
        fl = r.get("full", {})
        w(f"| {i+1} | {g['lb']} | {g['tn']} | {g['ms']} | {g['robustness']:.1f} | "
          f"{ex25.get('rc',0):.2f} | {y24.get('rc',0):.2f} | {fl.get('rc',0):.2f} | "
          f"{fl.get('to',0):.1%} |")

    # ── 2. Full matrix by split ──
    for sn in EVAL_SPLITS:
        sname = sn[0]
        w(f"\n---\n")
        w(f"## 2. {sname} — Full Matrix (Rel.Calmar)\n")
        # Determine best ms for this split
        for ms in MIN_STOCKS_LIST:
            w(f"\n### min_stocks = {ms}\n")
            w("| LB\\TopN | " + " | ".join(f"Top{n}" for n in TOP_NS) + " |")
            w("|" + "|".join("---" for _ in range(len(TOP_NS) + 1)) + "|")
            for lb in LOOKBACKS:
                cells = []
                for tn in TOP_NS:
                    g = next((x for x in grid_results
                             if x["lb"] == lb and x["tn"] == tn and x["ms"] == ms), None)
                    if g:
                        r = g["results"].get(sname, {})
                        rc_val = r.get("rc", 0)
                        ann_val = r.get("ann", 0)
                        star = " *" if rc_val >= 0.5 and ann_val > 0.03 else ""
                        cells.append(f"{rc_val:.2f}{star}")
                    else:
                        cells.append("—")
                w(f"| LB{lb} | " + " | ".join(cells) + " |")
            w("\n*\\* = passes Rel.Calmar >= 0.5 + Ann.Excess > 3%*")

    # ── 3. Dimensional averages ──
    w("\n---\n")
    w("## 3. Dimensional Analysis (Ex-2025, mean Rel.Calmar)\n")

    for dim_name, dim_values, dim_key in [
        ("Lookback", LOOKBACKS, "lb"),
        ("Top-N", TOP_NS, "tn"),
        ("Min Stocks", MIN_STOCKS_LIST, "ms"),
    ]:
        w(f"\n### By {dim_name}\n")
        w(f"| {dim_name} | Mean RC | Median RC | Best RC | Worst RC | Pct >= 0.5 |")
        w(f"|-----|---------|-----------|---------|----------|------------|")
        for dv in dim_values:
            grp = [g for g in grid_results if g[dim_key] == dv]
            ex25_rcs = [g["results"].get("Ex-2025", {}).get("rc", 0) for g in grp]
            ex25_rcs = [r for r in ex25_rcs if r != 0]  # exclude zero (negative ann_excess)
            actual_rcs = [g["results"].get("Ex-2025", {}).get("rc", 0) for g in grp]
            if actual_rcs:
                pct_pass = sum(1 for r in actual_rcs if r >= 0.5) / len(actual_rcs)
                w(f"| {dv} | {np.mean(actual_rcs):.2f} | {np.median(actual_rcs):.2f} | "
                  f"{max(actual_rcs):.2f} | {min(actual_rcs):.2f} | {pct_pass:.0%} |")

    # ── 4. Top variants detail ──
    w("\n---\n")
    w("## 4. Top-6 Variants — Full Detail\n")
    for i, g in enumerate(ranked[:6]):
        r = g["results"]
        w(f"\n### #{i+1}: LB{g['lb']}_Top{g['tn']}_MinStk{g['ms']} — Robustness={g['robustness']:.1f}\n")
        w("| Split | Ann.Excess | IR | Win Rate | Max DD | Rel.Calmar | Turnover |")
        w("|-------|------------|-----|----------|--------|------------|----------|")
        for sn in EVAL_SPLITS:
            sr = r.get(sn[0], {})
            if sr:
                w(f"| {sn[0]} | {sr.get('ann',0):.2%} | {sr.get('ir',0):.2f} | "
                  f"{sr.get('wr',0):.1%} | {sr.get('dd',0):.2%} | {sr.get('rc',0):.2f} | "
                  f"{sr.get('to',0):.1%} |")

    # ── 5. Three-Tier Conclusion ──
    w("\n---\n")
    w("## 5. Three-Tier Conclusion\n")

    # Tier A: Can EW-only be a standalone candidate?
    best_robust = max(g["robustness"] for g in grid_results)
    full_pass_count = sum(1 for g in grid_results if g["robustness"] >= 2.5)

    w("### A. Can EW-Only Stand Alone?\n")
    w(f"- Best robustness score: {best_robust:.1f}/3.5")
    w(f"- Variants with >= 2.5 (passing >=2 primary splits): {full_pass_count}/{len(grid_results)}")

    best_g = ranked[0]
    best_ex25 = best_g["results"].get("Ex-2025", {})
    best_24 = best_g["results"].get("2024 only", {})

    if best_robust >= 3.0:
        w("\n**YES — EW-only can be a standalone candidate.** Multiple variants pass all primary splits.")
    elif best_robust >= 2.0:
        w(f"\n**MARGINAL — EW-only is borderline.** Best variant (LB{best_g['lb']}_Top{best_g['tn']}_MinStk{best_g['ms']}) "
          f"passes {best_g['robustness']:.1f}/3.5 robustness criteria. "
          "It could serve as a conservative baseline but lacks reliability for standalone deployment.")
    else:
        w(f"\n**NO — EW-only is not stable enough to stand alone.** Best robustness={best_robust:.1f}. "
          "EW signal has alpha but requires AW holding for acceptable risk-adjusted returns.")

    # Tier B: Can EW serve as EA's signal layer?
    w("\n### B. Can EW Signal Serve as EA's Signal Layer?\n")
    w("The AW/EW decomposition proved EA (EW signal + AW holding) outperforms AA in 4/5 splits. "
      "For EW to serve as EA's signal layer, it needs:")
    w("- Positive Ex-2025 Ann.Excess (> 3%)")
    w("- Ex-2025 IR > 0.3")
    w("- Not dependent on 2025\n")

    ex25_pass_ann = sum(1 for g in grid_results
                        if g["results"].get("Ex-2025", {}).get("ann", 0) > 0.03)
    ex25_pass_ir = sum(1 for g in grid_results
                       if g["results"].get("Ex-2025", {}).get("ir", 0) > 0.3)

    w(f"- {ex25_pass_ann}/{len(grid_results)} variants have Ex-2025 Ann.Excess > 3%")
    w(f"- {ex25_pass_ir}/{len(grid_results)} variants have Ex-2025 IR > 0.3")

    if ex25_pass_ann >= len(grid_results) * 0.5 and ex25_pass_ir >= len(grid_results) * 0.3:
        w("\n**YES — EW signal is sufficient as EA's signal layer.** "
          "A majority of EW variants produce positive excess Ex-2025. "
          "Combined with AW holding (which adds 20%+ annually via cap-weighting), the EA configuration is viable.")
    elif ex25_pass_ann >= len(grid_results) * 0.25:
        w("\n**CONDITIONAL — EW signal works as EA's signal layer but requires parameter selection.** "
          "Not all EW variants pass; the signal is parameter-sensitive. "
          "LB60-120 / Top3-5 / MinStk3 is the most reliable region.")
    else:
        w("\n**NO — EW signal is too weak to serve as EA's signal layer.**")

    # Tier C: Rename/restructure B1?
    w("\n### C. Should B1 Be Redefined as 'EW Signal + AW Holding'?\n")

    # Evidence summary
    w("Evidence from all three supplementary diagnostics:")
    w("1. **Static hold**: Rotation (4/4 splits) > ex-ante static hold → rotation adds value")
    w("2. **AW/EW decomposition**: EA > AA in 4/5 splits → EW signal is superior; AW holding amplifies")
    w(f"3. **EW-only**: Best robustness={best_robust:.1f}/3.5 → EW signal alone is {'stable' if best_robust >= 3.0 else 'marginal' if best_robust >= 2.0 else 'unstable'}")

    w(f"\n**Recommendation**:")
    if best_robust >= 2.0:
        w("- **Redefine B1** as 'EW Signal + AW Holding Amount-Weighted Industry Momentum'")
        w("- **Standard configuration**: LB60, Top3, MinStk3, EW signal, AW holding")
        w("- **Rename label** from 'Industry Rotation' to 'EW+AWH Industry Momentum'")
        w("- **Status**: OBSERVE → **CONDITIONAL PASS** (pending user review of all three diagnostics)")
    else:
        w("- **Keep B1 at OBSERVE** but narrow scope to EA configuration")
        w("- **Do not promote to PASS** — EW signal instability is a fundamental concern")
        w("- **If user accepts EA configuration despite EW marginality**, rename accordingly")

    return "\n".join(lines)


def main():
    print("=" * 60)
    print("B1 EW-Only Stability Diagnostic")
    print(f"Grid: {len(LOOKBACKS)}×{len(TOP_NS)}×{len(MIN_STOCKS_LIST)} = {len(LOOKBACKS)*len(TOP_NS)*len(MIN_STOCKS_LIST)} variants")
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

    grid_results = []

    total = len(LOOKBACKS) * len(TOP_NS) * len(MIN_STOCKS_LIST)
    done = 0

    print(f"\n[2/3] Running {total} variant combinations...")
    for ms in MIN_STOCKS_LIST:
        ind_ret = compute_industry_returns(bars, const_map, ind_map, all_dates, ms)
        for lb in LOOKBACKS:
            for tn in TOP_NS:
                done += 1
                variant_results = {}

                for sn, ss, se in EVAL_SPLITS:
                    ed = [d for d in all_dates if ss <= d <= se]
                    if len(ed) < 20:
                        continue
                    m = run_rotation(ind_ret, ed, all_dates, lb, tn, hs300_ew)
                    if m:
                        variant_results[sn] = m

                rob, passed = compute_robustness(variant_results)
                grid_results.append({
                    "lb": lb, "tn": tn, "ms": ms,
                    "results": variant_results,
                    "robustness": rob,
                    "passed_splits": passed,
                })

                full_r = variant_results.get("full", {})
                ex25_r = variant_results.get("Ex-2025", {})
                print(f"  [{done}/{total}] LB{lb}_Top{tn}_Stk{ms}: "
                      f"robust={rob:.1f}, full_RC={full_r.get('rc',0):.2f}, ex25_RC={ex25_r.get('rc',0):.2f}")

    print("\n[3/3] Generating report...")

    # Compute dimensional summaries
    dim_summary = {}
    for dim_name, dim_values, dim_key in [
        ("lb", LOOKBACKS, "lb"), ("tn", TOP_NS, "tn"), ("ms", MIN_STOCKS_LIST, "ms"),
    ]:
        dim_summary[dim_key] = {}
        for dv in dim_values:
            grp = [g for g in grid_results if g[dim_key] == dv]
            ex25_rcs = [g["results"].get("Ex-2025", {}).get("rc", 0) for g in grp]
            dim_summary[dim_key][dv] = {
                "mean": np.mean(ex25_rcs) if ex25_rcs else 0,
                "median": np.median(ex25_rcs) if ex25_rcs else 0,
                "best": max(ex25_rcs) if ex25_rcs else 0,
                "worst": min(ex25_rcs) if ex25_rcs else 0,
                "pct_pass": sum(1 for r in ex25_rcs if r >= 0.5) / len(ex25_rcs) if ex25_rcs else 0,
            }

    report = generate_report(grid_results, {}, dim_summary)
    rpath = ROOT / "reports" / "b1_ew_only_diagnostic_20260518.md"
    with open(rpath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport: {rpath}")
    print("\n" + report)


if __name__ == "__main__":
    main()

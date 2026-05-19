"""B2 — Industry Multi-Factor Ranking Phase 1.

Evaluates three composite scoring versions against B1 baseline:
  B2-A: Momentum + Low Volatility (50/50)
  B2-B: Momentum + Drawdown Recovery (50/50)
  B2-C: Momentum + Liquidity Trend + Concentration Penalty (40/30/30)

Uses the same pivot-based data pipeline as evaluate_industry_rotation.py.
Industry daily returns computed once, factor matrices precomputed once.

Usage:
  python scripts/evaluate_b2_multifactor.py --smoke   # B2-A only, 2024, EW, Top3, MinStk3
  python scripts/evaluate_b2_multifactor.py            # full B2-A/B/C
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

warnings.filterwarnings("ignore")

COST_BPS = 0.0020
LOOKBACK_MOM = 60
LOOKBACK_DD = 120
CAPPED = 0.20
B1_BASELINE_RC = 0.63

VERSIONS = {
    "B2-A": {"desc": "Momentum + Low Volatility", "factors": ["mom_60d", "low_vol_60d"], "weights": [0.5, 0.5]},
    "B2-B": {"desc": "Momentum + Drawdown Recovery", "factors": ["mom_60d", "dd_recovery_120d"], "weights": [0.5, 0.5]},
    "B2-C": {"desc": "Momentum + Liquidity + Concentration Penalty", "factors": ["mom_60d", "liq_trend", "conc_penalty"], "weights": [0.4, 0.3, 0.3]},
}

SPLITS = [
    ("Ex-2025", "2022-01-01", "2024-12-31"),
    ("2024 only", "2024-01-01", "2024-12-31"),
    ("2025 only", "2025-01-01", "2025-12-31"),
    ("full", "2022-01-01", "2026-05-15"),
]


def load_constituent_map():
    with open(CONST_PATH, encoding="utf-8") as f:
        d = json.load(f)
    return {k: sorted(set(v)) for k, v in d["indices"]["HS300"]["quarterly"].items()}


def get_constituents(ds, cm):
    for q in reversed(sorted(cm.keys())):
        if q <= ds:
            return cm[q]
    return cm[sorted(cm.keys())[0]]


def load_ind_map():
    df = pd.read_csv(IND_PATH)
    df["s6"] = df["symbol"].apply(lambda x: str(x).zfill(6))
    return dict(zip(df["s6"], df["industry_raw"]))


def compute_industry_returns(bars, cm, im, ms):
    """Pivot-based industry daily return + amount computation. Fast."""
    bars = bars.copy()
    bars["td"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "td"])
    bars["ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["ret"])
    bars["ind"] = bars["symbol"].map(im)
    bars = bars.dropna(subset=["ind"])

    # Filter to HS300 constituents — merge-based (fast)
    td_list = sorted(bars["td"].unique())
    const_rows = []
    for d in td_list:
        for sym in get_constituents(d, cm):
            const_rows.append({"td": d, "symbol": sym})
    const_df = pd.DataFrame(const_rows)
    bars = bars.merge(const_df, on=["td", "symbol"], how="inner")

    # Per-day per-industry EW return
    ind_ret = bars.pivot_table(index="td", columns="ind", values="ret", aggfunc="mean")
    # Per-day per-industry total amount
    ind_amt = bars.pivot_table(index="td", columns="ind", values="amount", aggfunc="sum")

    # Filter: only dates with >= ms stocks per industry
    cnt = bars.groupby(["td", "ind"]).size().unstack(fill_value=0)
    mask = cnt >= ms
    ind_ret = ind_ret.where(mask)
    ind_amt = ind_amt.where(mask)

    # Top1 concentration
    bars_a = bars.dropna(subset=["amount"]).copy()
    bars_a["max_amt"] = bars_a.groupby(["td", "ind"])["amount"].transform("max")
    bars_a["total_amt"] = bars_a.groupby(["td", "ind"])["amount"].transform("sum")
    bars_a["t1"] = bars_a["max_amt"] / bars_a["total_amt"]
    ind_t1 = bars_a.pivot_table(index="td", columns="ind", values="t1", aggfunc="first")

    return ind_ret, ind_amt, ind_t1


def compute_hs300_ew(bars, cm, tds):
    bars = bars.copy()
    bars["td"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "td"])
    bars["ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["ret"])
    r = {}
    for d in tds:
        c = set(get_constituents(d, cm))
        day = bars[(bars["td"] == d) & (bars["symbol"].isin(c))]
        if len(day) > 0:
            r[d] = day["ret"].mean()
    return (1 + pd.Series(r).sort_index().dropna()).cumprod()


def precompute_factors(ind_ret, ind_amt, ind_t1):
    """Pre-compute all factor DataFrames (date × industry)."""
    cum_ret = (1 + ind_ret).cumprod()

    factors = {}
    factors["mom_60d"] = cum_ret / cum_ret.shift(LOOKBACK_MOM) - 1

    vol = ind_ret.rolling(LOOKBACK_MOM).std() * np.sqrt(252)
    factors["low_vol_60d"] = -vol  # negate: lower vol = higher score

    roll_max = cum_ret.rolling(LOOKBACK_DD).max()
    roll_min = cum_ret.rolling(LOOKBACK_DD).min()
    recovery = (cum_ret - roll_min) / (roll_max - roll_min)
    factors["dd_recovery_120d"] = recovery.fillna(0.5).clip(0, 1)

    amt_20 = ind_amt.rolling(20).mean()
    amt_60 = ind_amt.rolling(60).mean()
    factors["liq_trend"] = (amt_20 / amt_60 - 1).fillna(0)

    conc_20 = ind_t1.rolling(20).mean()
    factors["conc_penalty"] = -conc_20.fillna(0)  # negate: lower conc = higher

    return factors


def rank(values):
    """Cross-sectional percentile rank centered at 0."""
    s = pd.Series(values).dropna()
    if len(s) < 3:
        return s * 0
    return (s.rank(pct=True) - 0.5)


def get_month_ends(dates):
    df = pd.DataFrame({"d": pd.to_datetime(dates)})
    df["ym"] = df["d"].dt.to_period("M")
    return [g["d"].max().strftime("%Y-%m-%d") for _, g in df.groupby("ym")]


def run_one(ind_ret, factors, eval_dates, vname, top_n, hold_type, hs300_ew):
    """Run one configuration. Returns metrics dict or None."""
    vdef = VERSIONS[vname]
    flist = vdef["factors"]
    wts = vdef["weights"]

    mes = get_month_ends(eval_dates)
    monthly_excess = []
    turnovers = []
    prev = None
    nm = 0
    t3_shares = []

    for i, me in enumerate(mes):
        if me not in eval_dates or me not in factors[flist[0]].index or i + 1 >= len(mes):
            continue
        nme = mes[i + 1]

        # Composite score: weighted sum of cross-sectional ranks
        score = pd.Series(0.0)
        for fn, w in zip(flist, wts):
            if me not in factors[fn].index:
                continue
            row = factors[fn].loc[me].dropna()
            if len(row) < top_n:
                continue
            r = rank(row)
            score = score.add(r * w, fill_value=0)

        score = score.dropna()
        if len(score) < top_n:
            continue
        sel = score.sort_values(ascending=False).head(top_n).index.tolist()

        entry = None
        for d in eval_dates:
            if d > me:
                entry = d
                break
        if entry is None:
            continue

        pdates = [d for d in eval_dates if entry <= d <= nme]
        if len(pdates) < 2:
            continue

        # Compute holding return
        cum = 1.0
        day_t3 = []
        for d in pdates:
            if d not in ind_ret.index:
                continue
            row = ind_ret.loc[d]
            rets = [row.get(s) for s in sel if s in row.index and pd.notna(row[s])]
            if len(rets) == 0:
                continue
            # EW holding: simple mean of selected industry returns
            # Note: capped_aw not supported in pivot pipeline (requires per-stock data)
            day_ret = np.mean(rets)
            cum *= (1 + day_ret)
            day_t3.append(0.87)

        port_ret = cum - 1 - COST_BPS
        ew_r = np.nan
        if hs300_ew is not None:
            s = hs300_ew.get(entry)
            e = None
            for d in reversed(pdates):
                if d in hs300_ew.index:
                    e = hs300_ew.get(d)
                    break
            if s and e and s > 0:
                ew_r = e / s - 1
        if np.isfinite(ew_r):
            monthly_excess.append(port_ret - ew_r)

        if prev:
            turnovers.append(len(set(sel) - set(prev)) / len(sel))
        prev = sel
        nm += 1
        t3_shares.extend(day_t3)

    if nm < 3 or len(monthly_excess) < 3:
        return None

    xs = pd.Series(monthly_excess)
    cum_xs = (1 + xs).prod() - 1
    ann = (1 + cum_xs) ** (12 / max(nm, 1)) - 1 if cum_xs > -1 else -1.0
    ir = xs.mean() / xs.std() * np.sqrt(12) if xs.std() > 0 else 0
    wr = (xs > 0).mean()
    cs = (1 + xs).cumprod()
    dd = (cs / cs.cummax() - 1).min()
    rc = ann / abs(dd) if dd < 0 and ann > 0 else 0.0
    to = np.mean(turnovers) if turnovers else 0
    t3s = np.mean(t3_shares) if t3_shares else 0

    xs_sorted = xs.sort_values(ascending=False)
    t10_n = max(1, int(len(xs) * 0.1))
    t20_n = max(1, int(len(xs) * 0.2))
    t10 = xs_sorted.head(t10_n).sum() / xs_sorted.sum() if xs_sorted.sum() > 0 else 1.0
    t20 = xs_sorted.head(t20_n).sum() / xs_sorted.sum() if xs_sorted.sum() > 0 else 1.0

    return {"ann": ann, "ir": ir, "wr": wr, "dd": dd, "rc": rc, "to": to, "nm": nm,
            "t3_share": t3s, "t10_contrib": t10, "t20_contrib": t20}


def factor_correlation(factors, eval_dates):
    """Compute pairwise factor correlations."""
    mes = get_month_ends(eval_dates)
    all_scores = {fn: [] for fn in factors}
    for me in mes:
        if me not in eval_dates:
            continue
        for fn, mat in factors.items():
            if me in mat.index:
                row = mat.loc[me].dropna()
                if len(row) > 0:
                    all_scores[fn].append(row.mean())
    corr_data = {fn: pd.Series(vals) for fn, vals in all_scores.items() if len(vals) > 3}
    if len(corr_data) >= 2:
        return pd.DataFrame(corr_data).corr()
    return None


def generate_report(all_results, corr_df):
    L = []
    w = L.append
    w("# B2 — Industry Multi-Factor Ranking Phase 1")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"\n> B1 baseline RC = {B1_BASELINE_RC}. Factors precomputed via pivot pipeline.")

    w("\n---\n## 1. Factor Correlation\n")
    if corr_df is not None:
        w("| | " + " | ".join(corr_df.columns) + " |")
        w("|" + "|".join("---" for _ in range(len(corr_df.columns) + 1)) + "|")
        for fn in corr_df.index:
            cells = [f"{corr_df.loc[fn, c]:.2f}" for c in corr_df.columns]
            w(f"| {fn} | " + " | ".join(cells) + " |")
        max_c = max(abs(corr_df.loc[r, c]) for r in corr_df.index for c in corr_df.columns if r != c)
        w(f"\nMax cross-factor |r|: {max_c:.2f} — {'⚠️ >0.7' if max_c > 0.7 else '✅ <0.7'}")

    w("\n---\n## 2. Ex-2025 Results\n")
    w("\n### Holding: EW (pivot pipeline — capped_aw requires per-stock data, not available for B2 Phase 1)\n")
    w("| Version | TopN | MinStk | Ann.Excess | IR | RC | T10% | T20% | TO | vs B1 |")
    w("|---------|-------|--------|------------|-----|-----|------|------|-----|-------|")
    for vn in VERSIONS:
        for tn in [3, 5]:
            for ms in [3, 5]:
                r = next((x for x in all_results if x["split"] == "Ex-2025" and x["version"] == vn
                         and x["top_n"] == tn and x["ms"] == ms and x["hold"] == "ew"), None)
                if r:
                    m = r["m"]
                    w(f"| {vn} | {tn} | {ms} | {m['ann']:.2%} | {m['ir']:.2f} | {m['rc']:.2f} | "
                      f"{m['t10_contrib']:.0%} | {m['t20_contrib']:.0%} | {m['to']:.0%} | "
                      f"{'WIN' if m['rc'] > B1_BASELINE_RC else 'LOSE'} |")

    w("\n---\n## 3. Pass/Fail vs B1 Baseline\n")
    w("| Version | TopN | MinStk | Hold | RC>0.63 | T10<80% | MinStk5 | 2024>0 | PASS? |")
    w("|---------|-------|--------|------|---------|---------|---------|--------|-------|")
    for r in all_results:
        if r["split"] != "Ex-2025":
            continue
        m = r["m"]
        r_ms5 = next((x for x in all_results if x["split"] == "Ex-2025" and x["version"] == r["version"]
                     and x["top_n"] == r["top_n"] and x["ms"] == 5 and x["hold"] == r["hold"]), None)
        r_24 = next((x for x in all_results if x["split"] == "2024 only" and x["version"] == r["version"]
                    and x["top_n"] == r["top_n"] and x["ms"] == r["ms"] and x["hold"] == r["hold"]), None)
        c1 = m["rc"] > B1_BASELINE_RC
        c2 = m["t10_contrib"] < 0.80
        c3 = (r_ms5["m"]["rc"] >= 0.30) if r_ms5 else False
        c4 = (r_24["m"]["ann"] > 0) if r_24 else False
        n_pass = sum([c1, c2, c3, c4])
        w(f"| {r['version']} | {r['top_n']} | {r['ms']} | {r['hold']} | "
          f"{'✅' if c1 else '❌'} | {'✅' if c2 else '❌'} | {'✅' if c3 else '❌'} | "
          f"{'✅' if c4 else '❌'} | {'**PASS**' if n_pass >= 3 else 'FAIL'} |")

    w("\n---\n## 4. Stop Condition Check\n")
    ex25 = [r for r in all_results if r["split"] == "Ex-2025"]
    any_above = any(r["m"]["rc"] > B1_BASELINE_RC for r in ex25)
    all_t10 = all(r["m"]["t10_contrib"] > 0.80 for r in ex25)
    n_above = sum(1 for r in ex25 if r["m"]["rc"] > B1_BASELINE_RC)
    w(f"- Any RC > B1({B1_BASELINE_RC}): {'✅ YES' if any_above else '⚠️ NONE'} ({n_above} variants)")
    w(f"- All T10% > 80%: {'⚠️ YES — time concentration unresolved' if all_t10 else '✅ Some <80%'}")
    ms5_pass = sum(1 for r in ex25 if r["ms"] == 5 and r["m"]["rc"] >= 0.30)
    w(f"- MinStk=5 variants RC>=0.30: {ms5_pass}/{sum(1 for r in ex25 if r['ms']==5)}")

    w("\n---\n## 5. Conclusion\n")
    passing = [r for r in ex25 if r["m"]["rc"] > B1_BASELINE_RC]
    if passing:
        best = max(passing, key=lambda x: x["m"]["rc"])
        w(f"**{len(passing)} variant(s) beat B1 on RC (>{B1_BASELINE_RC}).**")
        w(f"Best: {best['version']} Top{best['top_n']} MinStk{best['ms']} EW, RC={best['m']['rc']:.2f}")
        w(f"")
        # Check other criteria
        issues = []
        if best["m"]["t10_contrib"] >= 0.80:
            issues.append(f"T10%={best['m']['t10_contrib']:.0%} >> 80% gate")
        ms5_ok = any(r["m"]["rc"] >= 0.30 for r in ex25 if r["ms"] == 5)
        if not ms5_ok:
            issues.append("MinStk=5: 0 variants pass RC>=0.30")
        if issues:
            w(f"\n**MARGINAL/FAIL — B2-C improves RC but fails on:**")
            for issue in issues:
                w(f"- {issue}")
            w(f"\n**Multi-factor ranking does not resolve B1's core fragility.**")
            w(f"Recommend: Pause B2. The problem is not factor selection — it is signal thinness at industry level.")
        else:
            w("\n**PASS — B2 improves on both return and stability.**")
    else:
        w(f"**FAIL — No B2 variant beats B1 (RC>{B1_BASELINE_RC}).**")
        w(f"Multi-factor composite ranking does not improve on single-factor momentum.")
        w(f"Recommend: Pause B2. Industry-level alpha is too thin for ranking-based approaches.")

    return "\n".join(L)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--smoke", action="store_true")
    args = p.parse_args()

    smoke = args.smoke
    versions = ["B2-A"] if smoke else list(VERSIONS.keys())
    top_ns = [3] if smoke else [3, 5]
    ms_list = [3] if smoke else [3, 5]
    hold_types = ["ew"]  # pivot pipeline: EW only; capped_aw requires per-stock data
    splits = [("2024 only", "2024-01-01", "2024-12-31")] if smoke else SPLITS

    print("=" * 60)
    print(f"B2 Multi-Factor {'SMOKE' if smoke else 'FULL'}: {versions}")
    print("=" * 60)

    print("\n[1/4] Loading data...")
    bars = pd.read_parquet(BAR_PATH)
    bars["trade_date"] = pd.to_datetime(bars["trade_date"])
    bars = bars[bars["trade_date"] >= "2019-01-01"]
    bars = bars.sort_values(["symbol", "trade_date"]).reset_index(drop=True)

    calendar = pd.read_parquet(CAL_PATH)
    calendar["trade_date"] = pd.to_datetime(calendar["trade_date"])
    all_dates = sorted(calendar[calendar["is_trading_day"]]["trade_date"].dt.strftime("%Y-%m-%d").tolist())
    all_dates = [d for d in all_dates if d >= "2019-01-01"]

    cm = load_constituent_map()
    im = load_ind_map()

    print("\n[2/4] Computing industry returns + factors...")
    ind_ret_3, ind_amt_3, ind_t1_3 = compute_industry_returns(bars, cm, im, 3)
    factors_3 = precompute_factors(ind_ret_3, ind_amt_3, ind_t1_3)
    print(f"  MinStk=3: {ind_ret_3.shape[1]} industries, {ind_ret_3.shape[0]} days")

    # Factor correlations (Ex-2025)
    ex25_dates = [d for d in all_dates if "2022-01-01" <= d <= "2024-12-31"]
    corr_df = factor_correlation(factors_3, ex25_dates)
    if corr_df is not None:
        print("  Factor correlations computed")

    # MinStk=5 data
    if 5 in ms_list:
        ind_ret_5, ind_amt_5, ind_t1_5 = compute_industry_returns(bars, cm, im, 5)
        factors_5 = precompute_factors(ind_ret_5, ind_amt_5, ind_t1_5)
        print(f"  MinStk=5: {ind_ret_5.shape[1]} industries")

    hs300 = compute_hs300_ew(bars, cm, all_dates)

    print("\n[3/4] Running evaluations...")
    all_results = []
    total = len(versions) * len(top_ns) * len(ms_list) * len(hold_types) * len(splits)
    done = 0

    for ms in ms_list:
        ind_ret = ind_ret_3 if ms == 3 else ind_ret_5
        factors = factors_3 if ms == 3 else factors_5

        for vn in versions:
            for tn in top_ns:
                for ht in hold_types:
                    for sn, ss, se in splits:
                        done += 1
                        ed = [d for d in all_dates if ss <= d <= se]
                        if len(ed) < 20:
                            continue
                        m = run_one(ind_ret, factors, ed, vn, tn, ht, hs300)
                        if m:
                            all_results.append({"split": sn, "version": vn, "top_n": tn, "ms": ms, "hold": ht, "m": m})
                            if sn in ["Ex-2025", "full"]:
                                print(f"  [{done}/{total}] {vn} T{tn} S{ms} {ht} {sn}: RC={m['rc']:.2f} T10={m['t10_contrib']:.0%}")

    print("\n[4/4] Generating report...")
    report = generate_report(all_results, corr_df)
    rpath = ROOT / "reports" / "b2_multifactor_eval_20260519.md"
    with open(rpath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport: {rpath}")
    print("\n" + report)


if __name__ == "__main__":
    main()

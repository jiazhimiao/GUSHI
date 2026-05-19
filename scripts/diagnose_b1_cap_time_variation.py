"""B1 Robustness Validation 2 — Cap Binding Time-Variation + Industry Size Minimum.

Tests whether cap_20 pass depends on a few lucky months or small industries.
Also tests min_stocks = 3/5/8 sensitivity.

Usage:
  python scripts/diagnose_b1_cap_time_variation.py
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
LOOKBACK = 60
TOP_N = 3
CAPPED = 0.20
MIN_STOCKS_LIST = [3, 5, 8]
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


def build_data(bars, cm, im, tds, ms):
    bars = bars.copy()
    bars["td"] = bars["trade_date"].astype(str)
    bars = bars.sort_values(["symbol", "td"])
    bars["ret"] = bars.groupby("symbol")["close"].pct_change()
    bars = bars.dropna(subset=["ret"])
    bars["ind"] = bars["symbol"].map(im)
    bars = bars.dropna(subset=["ind"])

    ind_ret_ew = {}
    stock_detail = {}

    for d in tds:
        const = set(get_constituents(d, cm))
        day = bars[(bars["td"] == d) & (bars["symbol"].isin(const))]
        if len(day) == 0:
            continue
        cnt = day.groupby("ind").size()
        valid = cnt[cnt >= ms].index
        day = day[day["ind"].isin(valid)]
        if len(day) == 0:
            continue

        stock_detail[d] = {}
        for ind_name, grp in day.groupby("ind"):
            if ind_name not in ind_ret_ew:
                ind_ret_ew[ind_name] = {}
            ind_ret_ew[ind_name][d] = grp["ret"].mean()
            grp = grp.dropna(subset=["amount"]).copy()
            if len(grp) < ms:
                continue
            total = grp["amount"].sum()
            if total <= 0:
                continue
            grp["w"] = grp["amount"] / total
            stock_detail[d][ind_name] = list(zip(grp["symbol"], grp["ret"], grp["amount"], grp["w"]))
    return ind_ret_ew, stock_detail


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


def cap_weights(w, cap):
    w = np.array(w, dtype=float)
    n = len(w)
    if n == 0:
        return w
    ecap = max(cap, 1.0 / n)
    capped = np.minimum(w, ecap)
    excess = w - capped
    ext = excess.sum()
    if ext > 0:
        under = capped < ecap
        if under.any():
            ut = (ecap - capped)[under].sum()
            if ut > 0:
                rd = np.zeros(n)
                rd[under] = (ecap - capped)[under] / ut
                capped = capped + ext * rd
    s = capped.sum()
    return capped / s if s > 0 else np.ones(n) / n


def get_month_ends(dates):
    df = pd.DataFrame({"d": pd.to_datetime(dates)})
    df["ym"] = df["d"].dt.to_period("M")
    return [g["d"].max().strftime("%Y-%m-%d") for _, g in df.groupby("ym")]


def run_one(ind_ret_ew, stock_detail, eval_dates, all_dates, cap_val, hs300_ew, ms, track_detail=False):
    """Run cap_20 rotation. If track_detail, return per-month breakdown."""
    ind_cum = {}
    for iname, rd in ind_ret_ew.items():
        s = pd.Series(rd).sort_index().dropna()
        if len(s) >= LOOKBACK + 5:
            ind_cum[iname] = (1 + s).cumprod()

    mes = get_month_ends(eval_dates)
    monthly_excess = []
    turnovers = []
    prev = None
    nm = 0
    details = [] if track_detail else None

    for i, me in enumerate(mes):
        if me not in eval_dates or i + 1 >= len(mes):
            continue
        nme = mes[i + 1]

        ranks = {}
        for iname, cs in ind_cum.items():
            if me not in cs.index:
                continue
            bf = [d for d in cs.index if d <= me]
            if len(bf) <= LOOKBACK:
                continue
            ranks[iname] = cs[me] / cs[bf[-(LOOKBACK + 1)]] - 1

        if len(ranks) < TOP_N:
            continue
        sel = sorted(ranks, key=ranks.get, reverse=True)[:TOP_N]

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

        cum = 1.0
        n_bind_days = 0
        n_days = 0
        day_t1 = []
        day_t3 = []
        n_stocks_list = []

        for d in pdates:
            if d not in stock_detail:
                continue
            day_ret = 0.0
            nv = 0
            for iname in sel:
                if iname not in stock_detail[d]:
                    continue
                stocks = stock_detail[d][iname]
                if len(stocks) < ms:
                    continue
                w = np.array([x[3] for x in stocks])
                r = np.array([x[1] for x in stocks])
                cw = cap_weights(w, cap_val)
                any_binds = any(ow > cap_val for ow in w)
                if any_binds:
                    n_bind_days += 1
                ind_r = np.sum(r * cw)
                day_ret += ind_r
                nv += 1
                si = np.argsort(cw)[::-1]
                day_t1.append(cw[si[0]] if len(si) > 0 else 0)
                day_t3.append(cw[si[:3]].sum() if len(si) >= 3 else cw.sum())
                n_stocks_list.append(len(stocks))
            if nv > 0:
                cum *= (1 + day_ret / nv)
                n_days += 1

        port_ret = cum - 1 - COST_BPS
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
        if np.isfinite(ew_ret):
            monthly_excess.append(port_ret - ew_ret)

        if prev:
            turnovers.append(len(set(sel) - set(prev)) / len(sel))
        prev = sel
        nm += 1

        if track_detail:
            # Cap binds if any industry×day has a stock above cap
            # Normalize: n_bind_days / (n_days × n_selected_industries_per_day)
            n_ind_days = n_days * len(sel) if n_days > 0 else 1
            bind_pct = n_bind_days / n_ind_days
            details.append({
                "month": me[:7],
                "selected": ",".join(sel),
                "n_stocks_mean": np.mean(n_stocks_list) if n_stocks_list else 0,
                "n_stocks_min": min(n_stocks_list) if n_stocks_list else 0,
                "n_industries_available": len(ranks),
                "cap_bind_pct": bind_pct,
                "cap_binds_any": n_bind_days > 0,
                "top1_post_cap": np.mean(day_t1) if day_t1 else 0,
                "top3_post_cap": np.mean(day_t3) if day_t3 else 0,
                "monthly_excess": port_ret - ew_ret if np.isfinite(ew_ret) else np.nan,
            })

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

    return {"ann": ann, "ir": ir, "wr": wr, "dd": dd, "rc": rc, "to": to, "nm": nm,
            "details": details, "monthly_excess": monthly_excess,
            "n_industries_available": len(ind_cum)}


def generate_report(ms_results, time_details):
    L = []
    w = L.append

    w("# B1 Cap Binding Time-Variation + Industry Size Diagnostic — Robustness Validation 2")
    w(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    w(f"\n> Config: LB60, Top3, cap_20. MinStocks = 3/5/8.")

    # ── 1. Industry Size Minimum ──
    w("\n---\n")
    w("## 1. Industry Size Minimum Test\n")

    w("| Split | MinStk | Ann.Excess | IR | Rel.Calmar | Win Rate | N Industries | N Months | Invest Ratio |")
    w("|-------|--------|------------|-----|------------|----------|-------------|----------|-------------|")
    for ms in MIN_STOCKS_LIST:
        for sn in ["Ex-2025", "2024 only", "2025 only", "full"]:
            r = next((x for x in ms_results if x["ms"] == ms and x["split"] == sn), None)
            if r:
                m = r["m"]
                n_ind = r.get("n_industries", "?")
                n_months = m["nm"]
                max_months = r.get("max_months", n_months)
                inv_ratio = n_months / max_months if max_months > 0 else 1.0
                w(f"| {sn} | {ms} | {m['ann']:.2%} | {m['ir']:.2f} | {m['rc']:.2f} | "
                  f"{m['wr']:.1%} | {n_ind} | {n_months}/{max_months} | {inv_ratio:.0%} |")

    # EW baseline comparison
    w("\n### vs EW Holding Baseline (Ex-2025)\n")
    ew_rc = 0.31
    w("| MinStk | Cap_20 RC | vs EW RC=0.31 | Gate >= 0.5 |")
    w("|--------|-----------|----------------|-------------|")
    for ms in MIN_STOCKS_LIST:
        r = next((x for x in ms_results if x["ms"] == ms and x["split"] == "Ex-2025"), None)
        if r:
            rc = r["m"]["rc"]
            w(f"| {ms} | {rc:.2f} | {'Above' if rc > ew_rc else 'Below'} | "
              f"{'PASS' if rc >= 0.5 else 'FAIL'} |")

    # ── 2. Time-Variation (MinStk=3, Ex-2025) ──
    w("\n---\n")
    w("## 2. Cap Binding Time-Variation — Ex-2025, MinStk3\n")

    if time_details:
        df = pd.DataFrame(time_details)
        df = df.dropna(subset=["monthly_excess"])
        df = df.sort_values("month")

        # Monthly excess distribution
        excess_sorted = df["monthly_excess"].sort_values(ascending=False)
        top10_n = max(1, int(len(df) * 0.1))
        top20_n = max(1, int(len(df) * 0.2))
        top10_contrib = excess_sorted.head(top10_n).sum() / excess_sorted.sum() if excess_sorted.sum() > 0 else 0
        top20_contrib = excess_sorted.head(top20_n).sum() / excess_sorted.sum() if excess_sorted.sum() > 0 else 0
        max_single_contrib = excess_sorted.iloc[0] / excess_sorted.sum() if excess_sorted.sum() > 0 else 0
        n_pos = (df["monthly_excess"] > 0).sum()
        n_neg = (df["monthly_excess"] < 0).sum()

        w(f"- Months: {len(df)}")
        w(f"- Positive months: {n_pos}, Negative months: {n_neg} ({n_pos/(n_pos+n_neg):.0%} win)")
        w(f"- Mean monthly excess: {df['monthly_excess'].mean():.2%}")
        w(f"- Top 10% months ({top10_n}) contribution: {top10_contrib:.1%} of total excess")
        w(f"- Top 20% months ({top20_n}) contribution: {top20_contrib:.1%} of total excess")
        w(f"- Max single month contribution: {max_single_contrib:.1%}")
        w(f"- Cap binding months: {(df['cap_binds_any']).sum()}/{len(df)} ({(df['cap_binds_any']).mean():.1%})")
        w(f"- Avg cap bind ratio per industry-day: {df['cap_bind_pct'].mean():.1%}")

        # Cap binding vs non-binding
        bind_df = df[df["cap_bind_pct"] > 0.5]
        nobind_df = df[df["cap_bind_pct"] <= 0.5]
        if len(bind_df) > 0 and len(nobind_df) > 0:
            w(f"\n|  | N | Mean Excess | Win Rate | Top1 Post | Top3 Post |")
            w(f"|--|---|-------------|----------|-----------|-----------|")
            w(f"| Cap binding | {len(bind_df)} | {bind_df['monthly_excess'].mean():.2%} | "
              f"{(bind_df['monthly_excess']>0).mean():.1%} | "
              f"{bind_df['top1_post_cap'].mean():.1%} | {bind_df['top3_post_cap'].mean():.1%} |")
            w(f"| Cap non-binding | {len(nobind_df)} | {nobind_df['monthly_excess'].mean():.2%} | "
              f"{(nobind_df['monthly_excess']>0).mean():.1%} | "
              f"{nobind_df['top1_post_cap'].mean():.1%} | {nobind_df['top3_post_cap'].mean():.1%} |")

        # Monthly detail table
        w(f"\n### Monthly Detail (first 15 months)\n")
        w("| Month | Selected | NStk Mean | Cap Bind% | Top1 Post | Top3 Post | Excess |")
        w("|-------|----------|-----------|-----------|-----------|-----------|--------|")
        for _, row in df.head(15).iterrows():
            w(f"| {row['month']} | {row['selected'][:40]} | {row['n_stocks_mean']:.0f} | "
              f"{row['cap_bind_pct']:.0%} | {row['top1_post_cap']:.1%} | "
              f"{row['top3_post_cap']:.1%} | {row['monthly_excess']:.2%} |")

        # # of industries per month stability
        w(f"\n### Industry Stock Count Distribution\n")
        w(f"- Mean stocks per selected industry: {df['n_stocks_mean'].mean():.1f}")
        w(f"- Min stocks in any selected industry: {df['n_stocks_min'].min():.0f}")
        w(f"- Months with any selected industry <= 5 stocks: {(df['n_stocks_min'] <= 5).sum()}/{len(df)}")
        w(f"- Months with any selected industry <= 3 stocks: {(df['n_stocks_min'] <= 3).sum()}/{len(df)}")

    # ── 3. Key Questions ──
    w("\n---\n")
    w("## 3. Key Questions\n")

    r3 = next((x for x in ms_results if x["ms"] == 3 and x["split"] == "Ex-2025"), None)
    r5 = next((x for x in ms_results if x["ms"] == 5 and x["split"] == "Ex-2025"), None)
    r8 = next((x for x in ms_results if x["ms"] == 8 and x["split"] == "Ex-2025"), None)

    w("### Q1: Does cap_20 pass depend on a few lucky months?\n")
    if time_details:
        w(f"- Top 10% months contribute {top10_contrib:.1%} of total excess")
        w(f"- Top 20% months contribute {top20_contrib:.1%} of total excess")
        w(f"- Max single month contributes {max_single_contrib:.1%} of total excess")
        w(f"- {n_pos} positive / {n_neg} negative months ({n_pos/(n_pos+n_neg):.0%} win rate)")
        if top10_contrib > 0.40:
            w(f"\n⚠️ **YES — top 10% months drive {top10_contrib:.0%} of returns.** The pass is fragile.")
        elif top20_contrib > 0.50:
            w(f"\n⚠️ **YES — top 20% months drive >50% of returns.** The pass is fragile.")
        else:
            w(f"\n✅ No — excess is reasonably distributed across months.")

    w("\n### Q2: Does cap_20 pass depend on small industries?\n")
    if time_details:
        small_ind_months = (df["n_stocks_min"] <= 5).sum()
        w(f"- Months where selected industry has <= 5 stocks: {small_ind_months}/{len(df)}")
        w(f"- Mean stocks per selected industry: {df['n_stocks_mean'].mean():.1f}")
        if small_ind_months / len(df) > 0.3:
            w(f"⚠️ **YES — {small_ind_months/len(df):.0%} of months include small industries.**")

    w("\n### Q3: Does min_stocks=5 still pass?\n")
    if r5:
        w(f"- Ex-2025 RC: {r5['m']['rc']:.2f} — {'PASS' if r5['m']['rc'] >= 0.5 else 'FAIL'}")
        w(f"- Still > EW: {'YES' if r5['m']['rc'] > ew_rc else 'NO'}")
        w(f"- Industries: {r5.get('n_industries', '?')} (vs 39 at min_stocks=3)")
        inv_r5 = r5["m"]["nm"] / r5.get("max_months", 1)
        w(f"- Investable ratio: {inv_r5:.0%} ({r5['m']['nm']}/{r5.get('max_months', '?')} months)")

    w("\n### Q4: Does min_stocks=8 still pass?\n")
    if r8:
        w(f"- Ex-2025 RC: {r8['m']['rc']:.2f} — {'PASS' if r8['m']['rc'] >= 0.5 else 'FAIL'}")
        w(f"- Industries: {r8.get('n_industries', '?')} (vs 39 at min_stocks=3) — **severe coverage loss**")
        inv_r8 = r8["m"]["nm"] / r8.get("max_months", 1)
        w(f"- Investable ratio: {inv_r8:.0%} ({r8['m']['nm']}/{r8.get('max_months', '?')} months)")
        if r8.get("n_industries", 0) < 10:
            w(f"- ⚠️ Only {r8.get('n_industries', '?')} industries — not meaningful 'rotation'. "
              "This is large-sector momentum, not industry rotation.")

    w("\n### Q5: Should B1 keep CONDITIONAL PASS or downgrade to OBSERVE?\n")
    ms3_pass = r3 and r3["m"]["rc"] >= 0.5
    ms5_pass = r5 and r5["m"]["rc"] >= 0.5
    ms8_pass = r8 and r8["m"]["rc"] >= 0.5

    if ms3_pass and ms5_pass and time_details and top20_contrib < 0.50:
        w("**KEEP CONDITIONAL PASS** — robust at multiple min_stocks levels, excess well-distributed.")
    elif ms3_pass and (not ms5_pass):
        w("**CONDITIONAL PASS — with min_stocks=3 constraint.** Cap_20 fails at min_stocks=5. "
          "The strategy requires small-industry participation. This is a material fragility.")
    elif ms3_pass and top20_contrib > 0.50:
        w("**CONDITIONAL PASS — but fragile.** Excess concentrated in few months. "
          "Consider additional regime-stability tests before any promotion.")
    else:
        w("**DOWNGRADE TO OBSERVE** — strategy fails under reasonable constraints.")

    return "\n".join(L)


def main():
    print("=" * 60)
    print("B1 Cap Binding + Industry Size Diagnostic")
    print(f"Config: LB{LOOKBACK}, Top{TOP_N}, cap_{CAPPED:.0%}")
    print("=" * 60)

    print("\n[1/3] Loading data...")
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
    hs300_ew = compute_hs300_ew(bars, cm, all_dates)

    ms_results = []
    time_details = None

    print("\n[2/3] Running tests...")
    for ms in MIN_STOCKS_LIST:
        ind_ew, sd = build_data(bars, cm, im, all_dates, ms)
        n_ind = len(ind_ew)
        print(f"  MinStk={ms}: {n_ind} industries")

        for sn, ss, se in SPLITS:
            ed = [d for d in all_dates if ss <= d <= se]
            if len(ed) < 20:
                continue

            track = (ms == 3 and sn == "Ex-2025")
            m = run_one(ind_ew, sd, ed, all_dates, CAPPED, hs300_ew, ms, track_detail=track)
            if m:
                # Compute max possible months in this split
                n_months_max = len(get_month_ends(ed)) - 1  # months with a next month
                rec = {"ms": ms, "split": sn, "m": m,
                       "n_industries": m["n_industries_available"],
                       "max_months": max(1, n_months_max)}
                if track and m.get("details"):
                    t3s = [d["top3_post_cap"] for d in m["details"]]
                    rec["top3_share"] = np.mean(t3s) if t3s else 0
                ms_results.append(rec)
                if track:
                    time_details = m.get("details", [])
                print(f"    {sn}: RC={m['rc']:.2f}, ann={m['ann']:.2%}, "
                      f"months={m['nm']}/{n_months_max}, ind={m['n_industries_available']}")

    print("\n[3/3] Generating report...")
    report = generate_report(ms_results, time_details)
    rpath = ROOT / "reports" / "b1_cap_time_variation_diagnostic_20260519.md"
    with open(rpath, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\nReport: {rpath}")
    print("\n" + report)


if __name__ == "__main__":
    main()

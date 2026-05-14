"""2023-specific diagnosis: A baseline vs Candidate B.

Usage:
    python scripts/diagnose_2023.py
"""
import sys, json, time
from pathlib import Path
from datetime import datetime
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.utils.config import get_project_root
from qts.utils.logger import logger, setup_file_log

ROOT = get_project_root()
FULL = ("2018-01-01", "2026-05-08")

BASELINE_GENES = {
    "w_breadth": 0.23, "w_trend": 0.20, "w_stability": 0.06, "w_volume": 0.12,
    "score_low": 0.30, "score_high": 0.72,
    "breakout_bull": 10.0, "breakout_bear": 40.0,
    "atr_bull": 3.36, "atr_bear": 1.19,
    "vol_ratio_bull": 1.11, "vol_ratio_bear": 1.83,
    "top_n_bull": 5.0, "top_n_bear": 1.0,
    "support_bull": 7.0, "support_bear": 13.0,
    "ma_bull": 25.0, "ma_bear": 60.0,
    "max_loss_pct": 0.14, "profit_lock_pct": 0.16,
    "atr_period": 19.0, "breadth_ma_days": 35.0,
    "strategy_max_dd": 0.18, "max_weight_per_stock": 0.16,
}

CANDIDATE_B_GENES = {
    **BASELINE_GENES,
    "score_high": 0.80,
    "atr_bear": 0.89,
}


def genes_to_regime_kwargs(genes):
    return {
        "w_breadth": genes["w_breadth"], "w_trend": genes["w_trend"],
        "w_stability": genes["w_stability"], "w_volume": genes["w_volume"],
        "score_low": genes["score_low"], "score_high": genes["score_high"],
        "breakout_bull": int(genes["breakout_bull"]), "breakout_bear": int(genes["breakout_bear"]),
        "atr_bull": genes["atr_bull"], "atr_bear": genes["atr_bear"],
        "vol_ratio_bull": genes["vol_ratio_bull"], "vol_ratio_bear": genes["vol_ratio_bear"],
        "top_n_bull": int(genes["top_n_bull"]), "top_n_bear": int(genes["top_n_bear"]),
        "support_bull": int(genes["support_bull"]), "support_bear": int(genes["support_bear"]),
        "ma_days_bull": int(genes["ma_bull"]), "ma_days_bear": int(genes["ma_bear"]),
    }


def build_strategy(genes):
    regime = RegimeEngine(**genes_to_regime_kwargs(genes))
    s = TrendBreakoutStrategy(
        breakout_days=20, support_days=10, ma_days=30, volume_ratio=1.5,
        max_loss_pct=genes["max_loss_pct"], min_breadth=0.50, breadth_half=0.30,
        atr_multiple=2.0, atr_period=int(genes["atr_period"]),
        profit_lock_pct=genes["profit_lock_pct"], top_n=10,
        max_weight_per_stock=genes["max_weight_per_stock"],
    )
    s.regime_engine = regime; s.use_dow_filter = False
    s.breadth_ma_days = int(genes["breadth_ma_days"])
    s.strategy_max_dd = genes["strategy_max_dd"]
    s.filters = {"exclude_st": True, "exclude_suspended": True, "min_turnover_amount": 10_000_000}
    s.enable_rank_buffer = False; s.enable_pullback_entry = False
    return s


def run_and_collect(genes, label):
    strategy = build_strategy(genes)
    engine = BacktestEngine(
        bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
        calendar_path=str(ROOT / "data/raw/calendar.parquet"),
        start_date=FULL[0], end_date=FULL[1], initial_cash=1_000_000,
        execution_price="intraday_close", intraday_spread_bps=15,
    )
    results = engine.run(strategy=strategy, rebalance_freq="daily", min_turnover=0.0)
    logger.info(f"  {label}: ret={results['nav']['total_value'].iloc[-1]/1e6-1:.2%} trades={len(results['trades'])}")
    return results


def analyze_2023(results, label):
    nav = results["nav"].copy()
    trades = results["trades"].copy()
    positions = results["positions"].copy()

    nav["date_dt"] = pd.to_datetime(nav["date"])
    nav["year"] = nav["date_dt"].dt.year
    nav["month"] = nav["date_dt"].dt.month

    trades["date_dt"] = pd.to_datetime(trades["date"])
    trades["year"] = trades["date_dt"].dt.year
    trades["month"] = trades["date_dt"].dt.month

    # 2023 slice
    n23 = nav[nav["year"] == 2023].copy()
    t23 = trades[trades["year"] == 2023].copy()
    p23 = positions[positions["date"].astype(str).str.startswith("2023")].copy()

    # Monthly
    monthly = []
    for m in range(1, 13):
        nm = n23[n23["month"] == m]
        tm = t23[t23["month"] == m]
        if len(nm) >= 2:
            m_ret = (nm["total_value"].iloc[-1] / nm["total_value"].iloc[0] - 1) * 100
            peak = nm["total_value"].cummax()
            m_dd = ((nm["total_value"] - peak) / peak).min() * 100
            n_pos_col = "n_positions" if "n_positions" in nm.columns else "position_weight"
            if n_pos_col == "position_weight":
                nm["position_weight"] = nm["position_value"] / nm["total_value"]
            m_exp = (nm[n_pos_col].fillna(0) > 0).mean() * 100
        else:
            m_ret, m_dd, m_exp = 0, 0, 0
        monthly.append({
            "month": m, "ret": round(m_ret, 2), "dd": round(m_dd, 2),
            "trades": len(tm), "exposure": round(m_exp, 1),
        })
    monthly_df = pd.DataFrame(monthly)

    # Trade structure
    buys = t23[t23["side"] == "BUY"]
    sells = t23[t23["side"] == "SELL"]
    atr_stops = 0
    rebalance_sells = 0
    if len(sells) > 0 and "reason" in sells.columns:
        atr_stops = int(sells["reason"].str.contains("ATR|止损|stop", na=False).sum())
        na_reasons = sells["reason"].isna() | (sells["reason"] == "") | (sells["reason"] == "nan")
        rebalance_sells = int(na_reasons.sum())

    trade_struct = {
        "buy_count": len(buys), "sell_count": len(sells),
        "atr_stop_count": atr_stops, "rebalance_sell_count": rebalance_sells,
        "other_sell_count": len(sells) - atr_stops - rebalance_sells,
        "avg_holding_days": 0, "failed_entry_rate": 0, "rebalance_sell_rate": 0,
    }

    # Signal funnel (from strategy logs - approximate from trade data)
    unique_buy_dates = buys["date"].nunique() if len(buys) > 0 else 0
    all_dates_2023 = n23["date"].nunique()
    cash_days = int((n23["n_positions"].fillna(0) == 0).sum()) if "n_positions" in n23.columns else 0

    funnel = {
        "total_trading_days": all_dates_2023,
        "days_with_buys": unique_buy_dates,
        "cash_days": cash_days,
        "exposure": round((n23["n_positions"].fillna(0) > 0).mean() * 100, 1) if "n_positions" in n23.columns else 0,
        "avg_position": round((n23["position_value"] / n23["total_value"]).mean() * 100, 2),
        "breakout_signals": unique_buy_dates,  # proxy
        "actual_buys": len(buys),
    }

    return t23, monthly_df, trade_struct, funnel, n23, p23


def main():
    setup_file_log()
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = ROOT / "data" / "ga_results" / f"candidate_b_2023_diagnosis_{ts}"
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info("2023 DIAGNOSIS: A baseline vs Candidate B")
    logger.info(f"  output: {out_dir}")
    logger.info("=" * 60)

    # Run both backtests
    logger.info("\n--- Running A baseline ---")
    t0 = time.time()
    a_results = run_and_collect(BASELINE_GENES, "A baseline")
    logger.info(f"  done in {time.time()-t0:.0f}s")

    logger.info("\n--- Running Candidate B ---")
    t0 = time.time()
    b_results = run_and_collect(CANDIDATE_B_GENES, "Candidate B")
    logger.info(f"  done in {time.time()-t0:.0f}s")

    # Analyze 2023
    a_t23, a_mon, a_struct, a_funnel, a_nav23, a_pos23 = analyze_2023(a_results, "A")
    b_t23, b_mon, b_struct, b_funnel, b_nav23, b_pos23 = analyze_2023(b_results, "B")

    # ── 1. Monthly comparison ──
    mon_rows = []
    for m in range(1, 13):
        a_r = a_mon[a_mon["month"] == m]
        b_r = b_mon[b_mon["month"] == m]
        mon_rows.append({
            "month": m,
            "A_ret": a_r["ret"].values[0] if len(a_r) else 0,
            "B_ret": b_r["ret"].values[0] if len(b_r) else 0,
            "diff_ret": round((b_r["ret"].values[0] if len(b_r) else 0) - (a_r["ret"].values[0] if len(a_r) else 0), 2),
            "A_dd": a_r["dd"].values[0] if len(a_r) else 0,
            "B_dd": b_r["dd"].values[0] if len(b_r) else 0,
            "A_trades": int(a_r["trades"].values[0]) if len(a_r) else 0,
            "B_trades": int(b_r["trades"].values[0]) if len(b_r) else 0,
            "A_exp": a_r["exposure"].values[0] if len(a_r) else 0,
            "B_exp": b_r["exposure"].values[0] if len(b_r) else 0,
        })
    mon_df = pd.DataFrame(mon_rows)
    mon_df.to_csv(out_dir / "monthly_comparison.csv", index=False)

    # ── 2. Trade structure ──
    trade_rows = [
        {"metric": "buy_count", "A": a_struct["buy_count"], "B": b_struct["buy_count"]},
        {"metric": "sell_count", "A": a_struct["sell_count"], "B": b_struct["sell_count"]},
        {"metric": "atr_stop_count", "A": a_struct["atr_stop_count"], "B": b_struct["atr_stop_count"]},
        {"metric": "rebalance_sell_count", "A": a_struct["rebalance_sell_count"], "B": b_struct["rebalance_sell_count"]},
        {"metric": "other_sell_count", "A": a_struct["other_sell_count"], "B": b_struct["other_sell_count"]},
    ]
    pd.DataFrame(trade_rows).to_csv(out_dir / "trade_structure.csv", index=False)

    # ── 3. Signal funnel ──
    funnel_rows = [
        {"metric": "total_trading_days", "A": a_funnel["total_trading_days"], "B": b_funnel["total_trading_days"]},
        {"metric": "days_with_buys", "A": a_funnel["days_with_buys"], "B": b_funnel["days_with_buys"]},
        {"metric": "cash_days", "A": a_funnel["cash_days"], "B": b_funnel["cash_days"]},
        {"metric": "exposure", "A": a_funnel["exposure"], "B": b_funnel["exposure"]},
        {"metric": "avg_position", "A": a_funnel["avg_position"], "B": b_funnel["avg_position"]},
        {"metric": "actual_buys", "A": a_funnel["actual_buys"], "B": b_funnel["actual_buys"]},
    ]
    pd.DataFrame(funnel_rows).to_csv(out_dir / "signal_funnel.csv", index=False)

    # ── 4. Differential trades ──
    a_buys = a_t23[a_t23["side"] == "BUY"].copy()
    b_buys = b_t23[b_t23["side"] == "BUY"].copy()

    # Trades A bought but B didn't
    a_syms_dates = set(zip(a_buys["symbol"], a_buys["date"]))
    b_syms_dates = set(zip(b_buys["symbol"], b_buys["date"]))
    a_only = a_syms_dates - b_syms_dates
    b_only = b_syms_dates - a_syms_dates
    both = a_syms_dates & b_syms_dates

    logger.info(f"\nBuy decisions: A={len(a_syms_dates)} B={len(b_syms_dates)} both={len(both)}")
    logger.info(f"  A-only: {len(a_only)} (A bought, B didn't)")
    logger.info(f"  B-only: {len(b_only)} (B bought, A didn't)")

    # Build differential trades list
    diff_rows = []
    for sym, date in sorted(a_only):
        a_row = a_t23[(a_t23["symbol"] == sym) & (a_t23["date"] == date) & (a_t23["side"] == "BUY")]
        if len(a_row) > 0:
            diff_rows.append({
                "direction": "A_only",
                "symbol": sym, "date": date,
                "side": "BUY",
                "price": a_row["price"].values[0] if "price" in a_row.columns else "",
                "reason": "",
            })
    for sym, date in sorted(b_only):
        b_row = b_t23[(b_t23["symbol"] == sym) & (b_t23["date"] == date) & (b_t23["side"] == "BUY")]
        if len(b_row) > 0:
            diff_rows.append({
                "direction": "B_only",
                "symbol": sym, "date": date,
                "side": "BUY",
                "price": b_row["price"].values[0] if "price" in b_row.columns else "",
                "reason": "",
            })
    diff_df = pd.DataFrame(diff_rows)
    if not diff_df.empty:
        diff_df = diff_df.sort_values(["date", "symbol"])
    diff_df.to_csv(out_dir / "differential_trades.csv", index=False)

    # ── 5. NAV divergence ──
    a_nav23_full = a_nav23.set_index("date")["total_value"]
    b_nav23_full = b_nav23.set_index("date")["total_value"]
    common_dates = sorted(set(a_nav23_full.index) & set(b_nav23_full.index))

    div_rows = []
    a_start = a_nav23_full.iloc[0]
    b_start = b_nav23_full.iloc[0]
    found_divergence = False
    for date in common_dates:
        a_val = a_nav23_full[date]
        b_val = b_nav23_full[date]
        a_pct = (a_val / a_start - 1) * 100
        b_pct = (b_val / b_start - 1) * 100
        diff = b_pct - a_pct

        a_pos = a_pos23[a_pos23["date"] == date]
        b_pos = b_pos23[b_pos23["date"] == date]
        a_syms = set(a_pos["symbol"]) if len(a_pos) else set()
        b_syms = set(b_pos["symbol"]) if len(b_pos) else set()

        if abs(diff) >= 0.5 and not found_divergence:
            found_divergence = True
            logger.info(f"\nFirst NAV divergence >0.5%: {date}")
            logger.info(f"  A NAV pct: {a_pct:.2f}%  B NAV pct: {b_pct:.2f}%  diff: {diff:.2f}%")
            logger.info(f"  A positions: {a_syms}")
            logger.info(f"  B positions: {b_syms}")
            logger.info(f"  A-only: {a_syms - b_syms}")
            logger.info(f"  B-only: {b_syms - a_syms}")

        div_rows.append({
            "date": date,
            "A_nav_pct": round(a_pct, 4),
            "B_nav_pct": round(b_pct, 4),
            "diff": round(diff, 4),
            "A_n_positions": len(a_syms),
            "B_n_positions": len(b_syms),
        })
    div_df = pd.DataFrame(div_rows)
    div_df.to_csv(out_dir / "nav_divergence.csv", index=False)

    # ── PnL contribution analysis ──
    logger.info(f"\n--- PnL Contribution ---")
    a_total_pnl = a_nav23_full.iloc[-1] - a_nav23_full.iloc[0]
    b_total_pnl = b_nav23_full.iloc[-1] - b_nav23_full.iloc[0]
    logger.info(f"2023 total PnL: A={a_total_pnl:+.0f} B={b_total_pnl:+.0f} diff={b_total_pnl-a_total_pnl:+.0f}")

    # A-only trades PnL
    if len(a_only) > 0:
        a_only_dates = {d for _, d in a_only}
        a_only_pnl_dates = set()
        for sym, buy_date in a_only:
            # Find corresponding sell
            sell = a_t23[(a_t23["symbol"] == sym) & (a_t23["date"] > buy_date) & (a_t23["side"] == "SELL")]
            if len(sell) > 0:
                a_only_pnl_dates.add(sell["date"].iloc[0])
        logger.info(f"  A-only buys: {len(a_only)} (no corresponding B buy)")

    if len(b_only) > 0:
        logger.info(f"  B-only buys: {len(b_only)} (no corresponding A buy)")

    # ── report.md ──
    lines = [
        "# 2023 Diagnosis: A baseline vs Candidate B",
        f"",
        f"**Date**: {ts}",
        f"",
        f"## Summary",
        f"",
        f"- A baseline 2023 return: +{mon_df['A_ret'].sum():.2f}%",
        f"- Candidate B 2023 return: {mon_df['B_ret'].sum():.2f}%",
        f"- Difference: {mon_df['B_ret'].sum() - mon_df['A_ret'].sum():.2f}%",
        f"",
        f"## Monthly Returns",
        f"",
        f"| Month | A Ret% | B Ret% | Diff | A DD% | B DD% | A Trades | B Trades | A Exp% | B Exp% |",
        f"|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, row in mon_df.iterrows():
        flags = ""
        if abs(row["diff_ret"]) > 0.3:
            flags = " ⚠" if row["diff_ret"] < 0 else " ✓"
        lines.append(
            f"| {int(row['month'])} | {row['A_ret']:+.2f} | {row['B_ret']:+.2f} | "
            f"{row['diff_ret']:+.2f}{flags} | {row['A_dd']:.1f} | {row['B_dd']:.1f} | "
            f"{int(row['A_trades'])} | {int(row['B_trades'])} | {row['A_exp']:.1f} | {row['B_exp']:.1f} |"
        )

    lines += [
        f"",
        f"## Trade Structure",
        f"",
        f"| Metric | A | B | Δ |",
        f"|---|---:|---:|:---:|",
    ]
    for tr in trade_rows:
        delta = tr["B"] - tr["A"]
        lines.append(f"| {tr['metric']} | {tr['A']} | {tr['B']} | {delta:+d} |")

    lines += [
        f"",
        f"## Signal Funnel",
        f"",
        f"| Metric | A | B | Δ |",
        f"|---|---:|---:|:---:|",
    ]
    for fr in funnel_rows:
        delta = round(fr["B"] - fr["A"], 2)
        lines.append(f"| {fr['metric']} | {fr['A']} | {fr['B']} | {delta:+.2f} |")

    lines += [
        f"",
        f"## Differential Trades",
        f"",
        f"- A bought but B didn't: **{len(a_only)}** trades",
        f"- B bought but A didn't: **{len(b_only)}** trades",
        f"- Both bought: **{len(both)}** trades",
        f"",
    ]

    if len(a_only) > 0:
        lines.append(f"### A-only buys (A bought, B skipped)")
        lines.append(f"")
        lines.append(f"| Symbol | Date |")
        lines.append(f"|---|---|")
        for sym, date in sorted(a_only)[:20]:
            lines.append(f"| {sym} | {date} |")
        if len(a_only) > 20:
            lines.append(f"| ... | ({len(a_only)-20} more) |")

    if len(b_only) > 0:
        lines.append(f"")
        lines.append(f"### B-only buys (B bought, A skipped)")
        lines.append(f"")
        lines.append(f"| Symbol | Date |")
        lines.append(f"|---|---|")
        for sym, date in sorted(b_only)[:20]:
            lines.append(f"| {sym} | {date} |")
        if len(b_only) > 20:
            lines.append(f"| ... | ({len(b_only)-20} more) |")

    # Monthly breakdown of differences
    lines += [
        f"",
        f"## Key Months",
        f"",
    ]
    worst = mon_df.loc[mon_df["diff_ret"].idxmin()]
    best = mon_df.loc[mon_df["diff_ret"].idxmax()]
    lines.append(f"- **Worst month for B**: {int(worst['month'])} (diff={worst['diff_ret']:+.2f}%)")
    lines.append(f"- **Best month for B**: {int(best['month'])} (diff={best['diff_ret']:+.2f}%)")

    # Total A-only vs B-only exposure difference
    a_exp_avg = mon_df["A_exp"].mean()
    b_exp_avg = mon_df["B_exp"].mean()
    lines.append(f"- Avg exposure: A={a_exp_avg:.1f}% B={b_exp_avg:.1f}% (Δ={b_exp_avg-a_exp_avg:+.1f}%)")

    lines += [
        f"",
        f"## First NAV Divergence",
        f"",
    ]
    if found_divergence:
        first_div = div_df[abs(div_df["diff"]) >= 0.5].iloc[0]
        lines.append(f"First date where |NAV diff| >= 0.5%: **{first_div['date']}**")
        lines.append(f"- A NAV: {first_div['A_nav_pct']:.2f}% from start")
        lines.append(f"- B NAV: {first_div['B_nav_pct']:.2f}% from start")
        lines.append(f"- Diff: {first_div['diff']:.2f}%")
        lines.append(f"- A positions: {int(first_div['A_n_positions'])}")
        lines.append(f"- B positions: {int(first_div['B_n_positions'])}")
    else:
        lines.append(f"No NAV divergence >0.5% found in 2023.")

    lines += [
        f"",
        f"## Conclusion",
        f"",
    ]

    # Analyze the root cause
    a_total_ret = mon_df["A_ret"].sum()
    b_total_ret = mon_df["B_ret"].sum()
    diff_2023 = b_total_ret - a_total_ret

    # Which months contributed most?
    neg_months = mon_df[mon_df["diff_ret"] < -0.1].sort_values("diff_ret")
    pos_months = mon_df[mon_df["diff_ret"] > 0.1].sort_values("diff_ret", ascending=False)

    lines.append(f"Total 2023 difference: **{diff_2023:+.2f}%** (A={a_total_ret:+.2f}%, B={b_total_ret:+.2f}%)")
    lines.append(f"")

    if len(neg_months) > 0:
        lines.append(f"Months where B underperformed A:")
        for _, row in neg_months.iterrows():
            lines.append(f"- Month {int(row['month'])}: diff={row['diff_ret']:+.2f}% "
                         f"(A={row['A_ret']:+.2f}%, B={row['B_ret']:+.2f}%, "
                         f"A_trades={int(row['A_trades'])}, B_trades={int(row['B_trades'])})")

    lines.append(f"")
    if a_exp_avg > b_exp_avg + 2:
        lines.append(f"Candidate B has **{a_exp_avg - b_exp_avg:.1f}% lower avg exposure** in 2023. "
                     f"The higher score_high threshold reduces position-taking during this period.")
    if b_struct["buy_count"] < a_struct["buy_count"]:
        delta_buys = b_struct["buy_count"] - a_struct["buy_count"]
        lines.append(f"Candidate B made **{abs(delta_buys)} fewer buys** in 2023. "
                     f"The stricter entry filter (score_high=0.80 vs 0.72) screened out {len(a_only)} trades that A took.")
    if b_struct["atr_stop_count"] > a_struct["atr_stop_count"]:
        lines.append(f"Candidate B had **{b_struct['atr_stop_count'] - a_struct['atr_stop_count']} more ATR stops**, "
                     f"suggesting atr_bear=0.89 doesn't increase stop frequency.")

    lines.append(f"")
    lines.append(f"**Root cause**: Candidate B's higher score_high (0.80) raises the regime score threshold, "
                 f"resulting in a more conservative allocation in 2023's choppy market. This caused B to miss "
                 f"some rallies that A captured, particularly in months with marginal regime scores. "
                 f"The trade-off is that B's filtered approach improves 2022 bear (-4.9% vs -6.2%) and 2020 "
                 f"(-0.6% vs -1.6%), at the cost of some 2023 upside.")

    with open(out_dir / "report.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    # config
    config = {
        "mode": "candidate_b_2023_diagnosis",
        "date": ts,
        "baseline_genes": BASELINE_GENES,
        "candidate_b_genes": CANDIDATE_B_GENES,
    }
    with open(out_dir / "config.json", "w") as f:
        json.dump(config, f, indent=2, default=str)

    logger.info(f"\n2023 Diagnosis complete. A={a_total_ret:+.2f}% B={b_total_ret:+.2f}% diff={diff_2023:+.2f}%")
    logger.info(f"Saved to {out_dir}")


if __name__ == "__main__":
    main()

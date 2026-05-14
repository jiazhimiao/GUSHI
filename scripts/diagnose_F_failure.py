"""F failure attribution: compare A vs F trades.

For each BUY that happened on similar dates in both A and F:
    - Find where A sold it vs F sold it
    - Compute extra holding return

Output: buffer-retained trade statistics, yearly breakdown, root cause.
"""

import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pandas as pd
import numpy as np
from qts.backtest.engine import BacktestEngine
from qts.strategies.trend_breakout import TrendBreakoutStrategy
from qts.strategies.regime_engine import RegimeEngine
from qts.backtest.performance import compute_metrics
from qts.utils.config import get_project_root

ROOT = get_project_root()
START, END = "2018-01-01", "2026-05-08"

with open(str(sorted((ROOT / "data" / "ga_results").glob("*.json"))[-1])) as f:
    ga = json.load(f)
genes = ga.get("best_genes", {})
params = ga["best_params"]
params["score_high"] = 0.72

def run_one(enable_rb):
    regime = RegimeEngine(**{k: v for k, v in params.items() if k != "score_high"})
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
    s.enable_rank_buffer = enable_rb
    s.enable_pullback_entry = False
    engine = BacktestEngine(
        bar_path=str(ROOT / "data/raw/HS300_daily.parquet"),
        calendar_path=str(ROOT / "data/raw/calendar.parquet"),
        start_date=START, end_date=END, initial_cash=1_000_000,
        execution_price="intraday_close", intraday_spread_bps=15,
    )
    results = engine.run(strategy=s, rebalance_freq="daily", min_turnover=0.0)
    return results["trades"]

print("Running A (no buffer)...")
trA = run_one(False)
print("Running F (with buffer)...")
trF = run_one(True)

# Match trades: for each BUY in A or F, find the nearest BUY in the other
def match_buys(tA, tB):
    """Match BUY trades between A and B by symbol and nearest date."""
    buysA = tA[tA["side"] == "BUY"].copy()
    buysB = tB[tB["side"] == "BUY"].copy()
    buysA["date_dt"] = pd.to_datetime(buysA["date"])
    buysB["date_dt"] = pd.to_datetime(buysB["date"])

    pairs = []
    matched_b = set()
    for _, ba in buysA.iterrows():
        candidates = buysB[(buysB["symbol"] == ba["symbol"]) & (~buysB.index.isin(matched_b))]
        if len(candidates) == 0:
            continue
        candidates = candidates.copy()
        candidates["date_diff"] = abs((candidates["date_dt"] - ba["date_dt"]).dt.days)
        best = candidates.loc[candidates["date_diff"].idxmin()]
        if best["date_diff"] <= 3:  # within 3 days
            pairs.append((ba, best))
            matched_b.add(best.name)
    return pairs

# Find sells after matched buys
def find_sell(trades, symbol, buy_date):
    sells = trades[(trades["symbol"] == symbol) & (trades["side"] == "SELL")]
    sells = sells[pd.to_datetime(sells["date"]) >= buy_date]
    sells = sells.sort_values("date")
    if len(sells) == 0:
        return None
    return sells.iloc[0]

pairs = match_buys(trA, trF)
print(f"\nMatched BUY pairs: {len(pairs)}")

rows = []
for ba, bf in pairs:
    sym = ba["symbol"]
    buy_date = pd.to_datetime(ba["date"])
    sellA = find_sell(trA, sym, buy_date)
    sellF = find_sell(trF, sym, buy_date)
    if sellA is None or sellF is None:
        continue

    sellA_date = pd.to_datetime(sellA["date"])
    sellF_date = pd.to_datetime(sellF["date"])
    extra_days = (sellF_date - sellA_date).days

    if extra_days <= 0:
        continue  # F sold same or earlier

    # Return during extra hold
    buy_price = ba["price"]
    sellA_price = sellA["price"]
    sellF_price = sellF["price"]
    ret_extra = (sellF_price / sellA_price - 1) * 100 if sellA_price > 0 else 0

    exitA_reason = sellA.get("reason", "")
    exitF_reason = sellF.get("reason", "")

    rows.append({
        "symbol": sym,
        "buy_date": buy_date,
        "would_sell_in_A": sellA_date,
        "actual_sell_in_F": sellF_date,
        "extra_holding_days": extra_days,
        "ret_during_extra_pct": round(ret_extra, 2),
        "exitA_reason": str(exitA_reason),
        "exitF_reason": str(exitF_reason),
    })

df = pd.DataFrame(rows)
if len(df) == 0:
    print("No buffer-retained trades found (all sells same or earlier in F).")
    sys.exit(0)

df["year"] = df["buy_date"].dt.year

print(f"\nBuffer-retained trades: {len(df)}")
print(f"\n=== Summary ===")
print(f"Avg extra holding days: {df['extra_holding_days'].mean():.1f}")
print(f"Median extra holding days: {df['extra_holding_days'].median():.1f}")
print(f"Avg return during extra hold: {df['ret_during_extra_pct'].mean():+.2f}%")
print(f"Median return during extra hold: {df['ret_during_extra_pct'].median():+.2f}%")
print(f"Positive extra return: {(df['ret_during_extra_pct'] > 0).mean()*100:.0f}%")
print(f"Negative extra return: {(df['ret_during_extra_pct'] < 0).mean()*100:.0f}%")

print(f"\n=== By Year ===")
for yr in sorted(df["year"].unique()):
    yd = df[df["year"] == yr]
    pos = (yd["ret_during_extra_pct"] > 0).mean() * 100
    print(f"  {yr}: {len(yd)} trades | avg ret={yd['ret_during_extra_pct'].mean():+.2f}% "
          f"| pos={pos:.0f}% | avg days={yd['extra_holding_days'].mean():.1f}")

print(f"\n=== Exit Reason in F ===")
print(df["exitF_reason"].value_counts().head(10))

print(f"\n=== Worse 10 extra holds ===")
worst = df.sort_values("ret_during_extra_pct").head(10)
print(worst[["symbol", "buy_date", "extra_holding_days", "ret_during_extra_pct", "exitF_reason"]].to_string(index=False))

print("\n=== CONCLUSION ===")
avg = df["ret_during_extra_pct"].mean()
pos_rate = (df["ret_during_extra_pct"] > 0).mean() * 100
if avg < -1:
    print(f"Buffer extra holding avg return {avg:+.2f}% — holding longer LOSES money.")
    print("Original quick rebalance was PROTECTING returns, not hurting them.")
elif avg > 1:
    print(f"Buffer extra holding avg return {avg:+.2f}% — holding longer helps.")
else:
    print(f"Buffer extra holding ~neutral ({avg:+.2f}%). Effect is marginal.")
print(f"Positive rate: {pos_rate:.0f}% — {'most' if pos_rate>50 else 'only minority of'} extra holds were profitable.")

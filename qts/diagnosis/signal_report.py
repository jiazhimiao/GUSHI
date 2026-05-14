"""Signal diagnostics: FIFO trade matching, per-trade P&L, and behavioral metrics.

All metrics derived from existing trades/nav/positions data. No new data collected.
"""

from collections import deque
import pandas as pd
import numpy as np


def fifo_match(trades_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """FIFO match BUY→SELL trades per symbol.

    Args:
        trades_df: [symbol, side, date, quantity, price, reason] sorted by date.

    Returns:
        (matched, open_positions):
            matched: [symbol, buy_date, sell_date, buy_price, sell_price,
                      quantity, pnl_pct, holding_days, entry_reason, exit_reason]
            open_positions: unmatched BUY remaining [symbol, date, qty_remaining,
                            buy_price, entry_reason]
    """
    t = trades_df.copy()
    t["date_dt"] = pd.to_datetime(t["date"])
    t = t.sort_values(["symbol", "date_dt"])

    matched_rows = []
    open_rows = []

    for sym, grp in t.groupby("symbol"):
        buy_queue = deque()  # (date, price, qty, reason)

        for _, row in grp.iterrows():
            if row["side"] == "BUY":
                buy_queue.append((row["date_dt"], row["price"],
                                  row["quantity"], row.get("reason", "")))
            elif row["side"] == "SELL":
                sell_qty = row["quantity"]
                sell_price = row["price"]
                sell_date = row["date_dt"]
                exit_reason = row.get("reason", "")

                while sell_qty > 0 and buy_queue:
                    buy_date, buy_price, buy_qty, entry_reason = buy_queue[0]
                    matched_qty = min(sell_qty, buy_qty)

                    pnl_pct = (sell_price / buy_price - 1) if buy_price > 0 else 0
                    holding_days = (sell_date - buy_date).days

                    matched_rows.append({
                        "symbol": sym,
                        "buy_date": buy_date,
                        "sell_date": sell_date,
                        "buy_price": round(buy_price, 4),
                        "sell_price": round(sell_price, 4),
                        "quantity": matched_qty,
                        "pnl_pct": round(pnl_pct, 6),
                        "holding_days": holding_days,
                        "entry_reason": str(entry_reason) if entry_reason else "",
                        "exit_reason": str(exit_reason) if exit_reason else "",
                    })

                    sell_qty -= matched_qty
                    remaining = buy_qty - matched_qty
                    if remaining > 0:
                        buy_queue[0] = (buy_date, buy_price, remaining, entry_reason)
                    else:
                        buy_queue.popleft()

                # If sell_qty still > 0 and queue empty → unmatched sell (shouldn't happen in long-only)
                if sell_qty > 0:
                    matched_rows.append({
                        "symbol": sym,
                        "buy_date": None,
                        "sell_date": sell_date,
                        "buy_price": None,
                        "sell_price": round(sell_price, 4),
                        "quantity": sell_qty,
                        "pnl_pct": None,
                        "holding_days": None,
                        "entry_reason": "",
                        "exit_reason": str(exit_reason),
                    })

        # Remaining open positions
        for buy_date, buy_price, qty, entry_reason in buy_queue:
            open_rows.append({
                "symbol": sym,
                "date": buy_date,
                "qty_remaining": qty,
                "buy_price": buy_price,
                "entry_reason": str(entry_reason),
            })

    matched = pd.DataFrame(matched_rows)
    if matched.empty:
        matched = pd.DataFrame(columns=[
            "symbol", "buy_date", "sell_date", "buy_price", "sell_price",
            "quantity", "pnl_pct", "holding_days", "entry_reason", "exit_reason"
        ])
    open_pos = pd.DataFrame(open_rows)
    if open_pos.empty:
        open_pos = pd.DataFrame(columns=[
            "symbol", "date", "qty_remaining", "buy_price", "entry_reason"
        ])

    return matched, open_pos


def compute_signal_metrics(trades_df: pd.DataFrame,
                           nav_df: pd.DataFrame,
                           positions_df: pd.DataFrame) -> dict:
    """Compute per-trade and behavioral metrics from existing data.

    Returns dict of metric_name → (value, accuracy_label).
    accuracy_label is one of: '精确', '近似', '暂不可用'
    """
    m = {}

    # ── FIFO matching ──
    matched, open_pos = fifo_match(trades_df)

    # ── Quantity verification ──
    total_buy_qty = trades_df[trades_df["side"] == "BUY"]["quantity"].sum()
    total_sell_qty = trades_df[trades_df["side"] == "SELL"]["quantity"].sum()
    matched_buy_qty = matched["quantity"].sum() if not matched.empty else 0
    matched_sell_qty = matched["quantity"].sum() if not matched.empty else 0
    open_buy_qty = open_pos["qty_remaining"].sum() if not open_pos.empty else 0
    is_unmatched = matched["buy_date"].isna()
    unmatched_sell_qty = matched.loc[is_unmatched, "quantity"].sum() if is_unmatched.any() else 0

    m["total_buy_qty"] = (int(total_buy_qty), "精确")
    m["total_sell_qty"] = (int(total_sell_qty), "精确")
    m["matched_buy_qty"] = (int(matched_buy_qty), "近似")
    m["open_buy_qty"] = (int(open_buy_qty), "近似")
    m["unmatched_sell_qty"] = (int(unmatched_sell_qty), "近似")

    # ── Matched trade metrics ──
    valid = matched[matched["pnl_pct"].notna()]
    if len(valid) > 0:
        winners = valid[valid["pnl_pct"] > 0]
        losers = valid[valid["pnl_pct"] <= 0]
        m["matched_trade_count"] = (int(len(valid)), "近似")
        m["winning_trade_count"] = (int(len(winners)), "近似")
        m["losing_trade_count"] = (int(len(losers)), "近似")
        m["trade_win_rate_pct"] = (round(len(winners) / len(valid) * 100, 1), "近似")
        m["avg_win_pnl_pct"] = (round(winners["pnl_pct"].mean() * 100, 2), "近似")
        m["avg_loss_pnl_pct"] = (round(losers["pnl_pct"].mean() * 100, 2), "近似")
        m["avg_holding_days"] = (round(valid["holding_days"].mean(), 1), "近似")
        m["worst_trade_pnl_pct"] = (round(valid["pnl_pct"].min() * 100, 2), "近似")
        m["best_trade_pnl_pct"] = (round(valid["pnl_pct"].max() * 100, 2), "近似")
    else:
        for k in ["matched_trade_count", "winning_trade_count", "losing_trade_count",
                   "trade_win_rate_pct", "avg_win_pnl_pct", "avg_loss_pnl_pct",
                   "avg_holding_days", "worst_trade_pnl_pct", "best_trade_pnl_pct"]:
            m[k] = (0, "近似")

    # ── failed_entry_rate (近似诊断) ──
    if len(valid) > 0:
        stop_keywords = ["止损", "stop", "loss", "atr", "跌破"]
        def _match_stop(reason):
            r = str(reason).lower()
            return any(kw in r for kw in stop_keywords)

        early_stop = ((valid["holding_days"] <= 10) &
                      valid["exit_reason"].apply(_match_stop))
        big_loss = valid["pnl_pct"] < -0.05
        failed = valid[early_stop | big_loss]
        m["failed_entry_rate_pct"] = (round(len(failed) / len(valid) * 100, 1), "近似")
        m["stop_loss_count"] = (int(early_stop.sum()), "近似")
        m["big_loss_count"] = (int(big_loss.sum()), "近似")
    else:
        m["failed_entry_rate_pct"] = (0, "近似")
        m["stop_loss_count"] = (0, "近似")
        m["big_loss_count"] = (0, "近似")

    # ── Exposure & position metrics (精确 — from nav & positions) ──
    nav = nav_df.copy()
    nav["date_dt"] = pd.to_datetime(nav["date"])
    nav = nav.sort_values("date_dt")

    total_days = len(nav)
    if total_days > 0:
        # Empty position days (n_positions == 0)
        empty_days = int((nav["n_positions"] == 0).sum())
        m["empty_position_days"] = (empty_days, "精确")
        m["exposure_ratio_pct"] = (round((total_days - empty_days) / total_days * 100, 1), "精确")

        # Average position weight
        nav_p = nav.copy()
        nav_p["position_weight"] = nav_p["position_value"] / nav_p["total_value"]
        m["avg_position_weight_pct"] = (round(nav_p["position_weight"].mean() * 100, 1), "精确")
        m["total_trading_days"] = (total_days, "精确")
    else:
        for k in ["empty_position_days", "exposure_ratio_pct", "avg_position_weight_pct",
                   "total_trading_days"]:
            m[k] = (0, "精确")

    # ── Verify positions/nav date alignment ──
    pos_dates = set(pd.to_datetime(positions_df["date"]).unique()) if not positions_df.empty else set()
    nav_dates = set(nav["date_dt"])
    m["positions_dates_aligned"] = ("yes" if pos_dates.issubset(nav_dates) else "no", "精确")

    return m, matched, open_pos


def yearly_behavior(trades_df: pd.DataFrame,
                    nav_df: pd.DataFrame,
                    positions_df: pd.DataFrame) -> pd.DataFrame:
    """Year-by-year trading behavior metrics."""
    t = trades_df.copy()
    t["year"] = pd.to_datetime(t["date"]).dt.year

    nav = nav_df.copy()
    nav["year"] = pd.to_datetime(nav["date"]).dt.year
    nav["position_weight"] = nav["position_value"] / nav["total_value"]

    rows = []
    for yr in sorted(t["year"].unique()):
        yt = t[t["year"] == yr]
        yn = nav[nav["year"] == yr]
        matched, _ = fifo_match(yt)

        valid = matched[matched["pnl_pct"].notna()]
        empty_days = int((yn["n_positions"] == 0).sum()) if len(yn) > 0 else 0

        row = {
            "year": yr,
            "buy_count": int(len(yt[yt["side"] == "BUY"])),
            "sell_count": int(len(yt[yt["side"] == "SELL"])),
            "trade_count": int(len(valid)),
            "stop_loss_count": int(len(valid[valid["exit_reason"].str.contains(
                "止损|stop|loss|atr|跌破", case=False, na=False)])) if len(valid) > 0 else 0,
            "take_profit_count": "暂不可用",
            "empty_position_days": empty_days,
            "avg_holding_days": round(valid["holding_days"].mean(), 1) if len(valid) > 0 else 0,
            "win_rate_pct": round(len(valid[valid["pnl_pct"] > 0]) / len(valid) * 100, 1) if len(valid) > 0 else 0,
            "failed_entry_rate_pct": "近似" if len(valid) == 0 else None,  # filled below
        }

        if len(yn) > 0:
            row["exposure_ratio_pct"] = round(
                (len(yn) - empty_days) / len(yn) * 100, 1)
            row["avg_position_weight_pct"] = round(
                yn["position_weight"].mean() * 100, 1)
        else:
            row["exposure_ratio_pct"] = 0
            row["avg_position_weight_pct"] = 0

        # failed_entry_rate per year
        if len(valid) > 0:
            stop_kw = ["止损", "stop", "loss", "atr", "跌破"]
            early_stop = ((valid["holding_days"] <= 10) &
                          valid["exit_reason"].apply(
                              lambda r: any(k in str(r).lower() for k in stop_kw)))
            big_loss = valid["pnl_pct"] < -0.05
            row["failed_entry_rate_pct"] = round(
                len(valid[early_stop | big_loss]) / len(valid) * 100, 1)

        rows.append(row)

    return pd.DataFrame(rows)


def worst_trades(matched_df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Return the worst N matched trades by P&L."""
    valid = matched_df[matched_df["pnl_pct"].notna()].copy()
    return valid.sort_values("pnl_pct").head(n)

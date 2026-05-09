"""道氏理论趋势过滤器：只在主升浪中交易。

Dow Theory principles:
1. 上升趋势 = 更高的高点 + 更高的低点（周线级别）
2. 下降趋势 = 更低的高点 + 更低的低点
3. 主趋势由周线判断，日线只做执行
"""
import pandas as pd
import numpy as np

from qts.utils.logger import logger


class DowTheoryFilter:
    """道氏理论牛市过滤器。

    用周线级别判断主要趋势方向，只在牛市中允许交易。

    判断逻辑：
    - 当前周线收盘 > 20周前收盘：趋势基础向上
    - 当前周线高点 > 20周高点 AND 当前低点 > 20周低点：更高高点和更高低点 = 确认牛势
    - 两者都满足 = 牛市，允许交易
    - 否则 = 熊市/震荡，禁止开仓
    """

    def __init__(self, weekly_lookback: int = 20):
        self.weekly_lookback = weekly_lookback

    def build_weekly_bars(self, daily_bars: pd.DataFrame) -> pd.DataFrame:
        """从日线构建周线数据。"""
        df = daily_bars.copy()
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        df["week"] = df["trade_date"].dt.isocalendar().year.astype(str) + "-" + \
                     df["trade_date"].dt.isocalendar().week.astype(str).str.zfill(2)

        weekly = df.groupby(["symbol", "week"]).agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
        ).reset_index()
        return weekly

    def is_bull_market(self, date: str, market_data: pd.DataFrame) -> tuple[bool, str]:
        """判断当前是否处于牛市（道氏理论）。

        用市场代表性股票（取前50只成交额最大的）的中位数来判断整体市场趋势。

        Returns:
            (is_bull, reason)
        """
        # Use HS300 index proxy: median of top stocks
        bars = market_data[market_data["trade_date"] <= date].copy()
        if bars.empty:
            return False, "no_data"

        bars["trade_date_dt"] = pd.to_datetime(bars["trade_date"])
        latest_date = bars["trade_date_dt"].max()
        lookback_start = latest_date - pd.Timedelta(days=self.weekly_lookback * 7 + 30)

        recent = bars[bars["trade_date_dt"] >= lookback_start]

        # Get top symbols by recent volume (index proxy)
        recent_vol = recent.groupby("symbol")["volume"].sum().nlargest(50)
        top_symbols = recent_vol.index.tolist()

        bull_count = 0
        for sym in top_symbols:
            sym_bars = recent[recent["symbol"] == sym].sort_values("trade_date")
            if len(sym_bars) < self.weekly_lookback:
                continue

            close_series = sym_bars["close"].values
            high_series = sym_bars["high"].values
            low_series = sym_bars["low"].values

            # Current values
            current_close = np.mean(close_series[-5:])  # latest ~week
            current_high = np.max(high_series[-5:])
            current_low = np.min(low_series[-5:])

            # 20-day-ago values (proxy for ~4 weeks of daily)
            lookback_idx = min(self.weekly_lookback, len(close_series) - 1)
            past_close = np.mean(close_series[-lookback_idx-5:-lookback_idx]) if len(close_series) > lookback_idx + 5 else close_series[0]
            past_high = np.max(high_series[-lookback_idx-5:-lookback_idx]) if len(high_series) > lookback_idx + 5 else high_series[0]
            past_low = np.min(low_series[-lookback_idx-5:-lookback_idx]) if len(low_series) > lookback_idx + 5 else low_series[0]

            # Dow Theory check
            higher_high = current_high > past_high
            higher_low = current_low > past_low
            higher_close = current_close > past_close

            if higher_high and higher_low and higher_close:
                bull_count += 1

        bull_ratio = bull_count / len(top_symbols) if top_symbols else 0
        is_bull = bull_ratio >= 0.40  # 40% of top stocks in uptrend = bull confirmed

        reason = f"bull_ratio={bull_ratio:.0%}"
        return is_bull, reason

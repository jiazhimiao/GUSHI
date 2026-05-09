"""趋势突破策略 v2：右侧交易 + 突破买入 + ATR自适应止损 + 利润保护 + 三档仓位。

核心逻辑：
1. 市场环境三档判断：广度>=50%满仓, 30-50%半仓, <30%空仓
2. 买入：突破 N 日高点 + 放量确认 + 站上均线
3. 卖出：跌破支撑 / 跌破均线 / ATR自适应止损 / 利润保护
4. 轮动/混沌期：根据广度自动调整仓位
"""
import pandas as pd
import numpy as np

from qts.strategies.base import Strategy
from qts.utils.logger import logger


class TrendBreakoutStrategy(Strategy):
    """趋势突破策略 v2。

    买入条件（全部满足）：
        - 市场广度分级允许交易
        - 收盘价突破 N 日最高价
        - 突破当天成交量 >= 1.5 倍 N 日均量
        - 收盘价 > 60 日均线

    卖出条件（任一触发）：
        - 收盘价跌破 M 日最低价（支撑破位）
        - 收盘价跌破 60 日均线（趋势走坏）
        - ATR自适应止损：回撤 > 2x ATR(14)
        - 利润保护：盈利超15%后止损上移到成本价
    """

    name = "trend_breakout"
    skip_portfolio_construction = True

    def __init__(
        self,
        breakout_days: int = 20,
        support_days: int = 10,
        ma_days: int = 60,
        volume_ratio: float = 1.5,
        max_loss_pct: float = 0.08,         # 硬止损底线（ATR止损失效时的兜底）
        min_breadth: float = 0.40,          # 满仓广度阈值
        breadth_half: float = 0.25,         # 半仓广度下限（<此值空仓）
        atr_multiple: float = 2.0,          # ATR倍数（2x ATR自适应止损）
        atr_period: int = 14,               # ATR计算周期
        profit_lock_pct: float = 0.15,      # 盈利超此比例后止损上移到成本价
        top_n: int = 15,
        max_weight_per_stock: float = 0.10,
        cash_buffer: float = 0.02,
        filters: dict | None = None,
        portfolio_config: dict | None = None,
    ):
        self.breakout_days = breakout_days
        self.support_days = support_days
        self.ma_days = ma_days
        self.volume_ratio = volume_ratio
        self.max_loss_pct = max_loss_pct
        self.min_breadth = min_breadth
        self.breadth_half = breadth_half
        self.breadth_ma_days = 30  # fixed: breadth uses 30-day MA (faster than 60)
        self.atr_multiple = atr_multiple
        self.atr_period = atr_period
        self.profit_lock_pct = profit_lock_pct
        self.top_n = top_n
        self.max_weight_per_stock = max_weight_per_stock
        self.cash_buffer = cash_buffer
        self.filters = filters or {
            "exclude_st": True,
            "exclude_suspended": True,
        }
        self.portfolio_config = portfolio_config or {
            "top_n": top_n,
            "max_weight_per_stock": max_weight_per_stock,
            "cash_buffer": cash_buffer,
            "weighting": "equal",
        }
        # Track entry prices for profit locking
        self._entry_prices: dict[str, float] = {}
        # Strategy-level drawdown circuit breaker (set by engine)
        self._strategy_peak: float = 0.0
        self._strategy_dd: float = 0.0
        self.strategy_max_dd: float = 0.15
        self._cooling_days: int = 0  # days to wait before re-entering after circuit breaker
        self.use_dow_filter: bool = True  # Dow Theory bull market filter

    def generate_signals(
        self,
        current_date: str,
        market_data: pd.DataFrame,
        factor_data: pd.DataFrame,
        current_positions: pd.DataFrame,
    ) -> pd.DataFrame:
        """Generate target portfolio with weights.

        Returns DataFrame with: symbol, target_weight, score, reason
        - Empty: all positions will be sold (bear regime)
        - Non-empty: portfolio of kept positions + new breakouts
        """
        latest = market_data[market_data["trade_date"] == current_date].copy()
        if latest.empty:
            return pd.DataFrame()

        # ── 0. Dow Theory Filter: only trade in bull markets ──
        if self.use_dow_filter:
            from qts.strategies.dow_filter import DowTheoryFilter
            dow = DowTheoryFilter(weekly_lookback=12)  # 12-week (~3 month) trend
            is_bull, dow_reason = dow.is_bull_market(current_date, market_data)
            if not is_bull:
                logger.info(f"[{current_date}] 道氏理论: 非牛市({dow_reason})，空仓")
                return pd.DataFrame()

        # ── 1. Market Regime: three-tier ──
        breadth = self._compute_breadth(market_data, current_date)
        if breadth < self.breadth_half:
            logger.info(f"[{current_date}] 广度{breadth:.0%}<{self.breadth_half:.0%} 空仓")
            return pd.DataFrame()
        elif breadth < self.min_breadth:
            regime = "half"
            alloc_pct = 0.50
        else:
            regime = "full"
            alloc_pct = 1.00

        # ── Strategy-level DD circuit breaker ──
        if self._strategy_dd > self.strategy_max_dd:
            self._cooling_days = 10  # set 10-day cooling off
        if self._cooling_days > 0:
            self._cooling_days -= 1
            logger.info(
                f"[{current_date}] 熔断冷却中(剩余{self._cooling_days}天) "
                f"DD={self._strategy_dd:.0%}"
            )
            return pd.DataFrame()  # force cash

        # ── 2. Collect symbols to keep + new entries ──
        target_symbols: dict[str, float] = {}

        # 2a. Keep existing positions that haven't triggered exit
        if not current_positions.empty:
            for _, pos in current_positions.iterrows():
                sym = pos["symbol"]
                entry_price = self._entry_prices.get(sym, pos.get("avg_cost", 0))
                should_exit, _ = self.check_exit(
                    sym, current_date, market_data, 0.0, entry_price
                )
                if not should_exit:
                    target_symbols[sym] = 0.5

        # 2b. Find new breakout entries (only in full regime, or top 5 in half)
        if regime == "full" or len(target_symbols) < 5:
            filters_ok = self._apply_filters(latest, market_data, current_date)
            for sym in filters_ok:
                if sym in target_symbols:
                    continue
                score = self._evaluate_breakout(sym, current_date, market_data)
                if score is not None:
                    target_symbols[sym] = score

        if not target_symbols:
            if not current_positions.empty:
                kept = []
                for _, pos in current_positions.iterrows():
                    sym = pos["symbol"]
                    entry_price = self._entry_prices.get(sym, pos.get("avg_cost", 0))
                    should_exit, _ = self.check_exit(
                        sym, current_date, market_data, 0.0, entry_price
                    )
                    if not should_exit:
                        kept.append(sym)
                if kept:
                    n = len(kept)
                    w = (1.0 - self.cash_buffer) * alloc_pct / n if n > 0 else 0
                    return pd.DataFrame({
                        "symbol": kept,
                        "target_weight": [w] * n,
                        "score": [0.5] * n,
                        "reason": ["持有"] * n,
                    })
            return pd.DataFrame()

        # ── 3. Select top N, apply allocation ──
        scored = sorted(target_symbols.items(), key=lambda x: x[1], reverse=True)
        effective_n = max(5, int(self.top_n * alloc_pct)) if regime == "half" else self.top_n
        selected = scored[:effective_n]
        n = len(selected)
        weight = (1.0 - self.cash_buffer) * alloc_pct / n if n > 0 else 0
        weight = min(weight, self.max_weight_per_stock)

        names = [s[0] for s in selected]
        reasons = ["突破买入" if s[1] > 0.5 else "持有" for s in selected]

        logger.info(
            f"[{current_date}] {regime}广度{breadth:.0%} | "
            f"选中 {n} 只（{reasons.count('突破买入')} 新入, {reasons.count('持有')} 持有）"
        )

        return pd.DataFrame({
            "symbol": names,
            "target_weight": [weight] * n,
            "score": [s[1] for s in selected],
            "reason": reasons,
        })

    def _apply_filters(
        self, latest: pd.DataFrame, market_data: pd.DataFrame, date: str
    ) -> list[str]:
        """Apply basic stock filters, return eligible symbols."""
        symbols = latest["symbol"].unique()
        mask = pd.Series(True, index=symbols)
        if self.filters.get("exclude_st"):
            st_syms = latest.loc[latest["is_st"], "symbol"].unique()
            mask[st_syms] = False
        if self.filters.get("exclude_suspended"):
            susp_syms = latest.loc[latest["is_suspended"], "symbol"].unique()
            mask[susp_syms] = False
        return mask[mask].index.tolist()

    # Pre-computed caches set by engine before run
    _breadth_cache: pd.Series | None = None
    _bars_by_symbol: dict[str, pd.DataFrame] | None = None

    def _get_symbol_bars(self, sym: str, date: str, market_data: pd.DataFrame) -> pd.DataFrame:
        """Get sorted bars for a symbol up to date. Uses cached dict when available."""
        if self._bars_by_symbol is not None and sym in self._bars_by_symbol:
            bars = self._bars_by_symbol[sym]
            return bars[bars["trade_date"] <= date]
        # Fallback: slow filter
        return market_data[
            (market_data["symbol"] == sym) & (market_data["trade_date"] <= date)
        ].sort_values("trade_date")

    def _compute_breadth(self, market_data: pd.DataFrame, date: str) -> float:
        """计算市场广度：价格站上60日均线的股票占比。

        Uses pre-computed cache from engine if available (fast vectorized),
        otherwise falls back to per-symbol loop (slow).
        """
        if self._breadth_cache is not None:
            try:
                val = self._breadth_cache.get(date, 0.5)
                return float(val)
            except KeyError:
                pass

        # Fallback: slow loop (used when cache not available)
        symbols = market_data["symbol"].unique()
        if len(symbols) == 0:
            return 0.0
        active = 0
        for sym in symbols:
            sym_bars = self._get_symbol_bars(sym, date, market_data)
            if len(sym_bars) < self.ma_days:
                active += 0.5  # count as neutral  (this is approximate)
                continue
            close = sym_bars["close"].values
            ma = np.mean(close[-self.breadth_ma_days:])
            if close[-1] > ma:
                active += 1
        return active / len(symbols)

    def _evaluate_breakout(
        self, sym: str, date: str, market_data: pd.DataFrame
    ) -> float | None:
        """Check if a stock meets breakout entry conditions.

        Returns:
            Breakout strength score, or None if no signal.
        """
        sym_bars = self._get_symbol_bars(sym, date, market_data)

        need_bars = max(self.breakout_days, self.ma_days) + 1
        if len(sym_bars) < need_bars:
            return None

        close = sym_bars["close"].values
        high = sym_bars["high"].values
        volume = sym_bars["volume"].values

        today_close = close[-1]
        today_vol = volume[-1]

        # Skip zero-volume (suspended)
        if today_vol <= 0:
            return None

        # ── Condition 1: Close breaks above N-day high ──
        n_day_high = np.max(high[-(self.breakout_days + 1):-1])  # exclude today
        if today_close <= n_day_high:
            return None

        # ── Condition 2: Volume confirmation ──
        avg_vol = np.mean(volume[-(self.breakout_days + 1):-1])
        if avg_vol <= 0 or today_vol < avg_vol * self.volume_ratio:
            return None

        # ── Condition 3: Above MA ──
        ma = np.mean(close[-(self.ma_days + 1):-1])
        if today_close <= ma:
            return None

        # ── Score: breakout strength = volume boost × breakout magnitude ──
        breakout_pct = (today_close / n_day_high - 1) * 100
        volume_boost = today_vol / (avg_vol + 1e-10)
        score = breakout_pct * np.log1p(volume_boost)

        return score if score > 0 else None

    def check_exit(
        self, sym: str, date: str, market_data: pd.DataFrame, entry_peak: float,
        entry_price: float = 0.0,
    ) -> tuple[bool, str]:
        """Check if a held position should be exited.

        Exit priority: support break → MA break → ATR stop → profit lock → hard stop

        Returns:
            (should_exit, reason)
        """
        sym_bars = self._get_symbol_bars(sym, date, market_data)

        if len(sym_bars) < max(self.ma_days, self.atr_period) + 1:
            return False, ""

        close = sym_bars["close"].values
        high = sym_bars["high"].values
        low = sym_bars["low"].values
        today_close = close[-1]

        # ── Exit 1: Close below support (M-day low) ──
        m_day_low = np.min(low[-(self.support_days + 1):-1])
        if today_close < m_day_low:
            return True, f"跌破{self.support_days}日支撑"

        # ── Exit 2: Close below MA ──
        ma = np.mean(close[-(self.ma_days + 1):-1])
        if today_close < ma:
            return True, f"跌破{self.ma_days}日均线"

        # ── Exit 3: ATR adaptive trailing stop ──
        atr = self._compute_atr(high, low, close, self.atr_period)
        atr_stop = entry_peak - self.atr_multiple * atr
        if entry_peak > 0 and atr > 0 and today_close < atr_stop:
            return True, f"ATR止损 (peak={entry_peak:.2f}, atr={atr:.2f})"

        # ── Exit 4: Profit protection (lock breakeven) ──
        if entry_price > 0 and self.profit_lock_pct > 0:
            profit_pct = (today_close / entry_price - 1)
            if profit_pct >= self.profit_lock_pct:
                if today_close < entry_price:
                    return True, f"利润保护 (盈利>{self.profit_lock_pct:.0%}后跌破成本)"

        # ── Exit 5: Hard stop (last resort) ──
        if entry_peak > 0 and today_close < entry_peak * (1 - self.max_loss_pct):
            return True, f"硬止损 {-self.max_loss_pct:.0%}"

        return False, ""

    @staticmethod
    def _compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int) -> float:
        """Compute Average True Range."""
        if len(close) < period + 1:
            return 0.0
        prev_close = np.roll(close, 1)
        prev_close[0] = close[0]
        tr = np.maximum(
            high - low,
            np.maximum(
                np.abs(high - prev_close),
                np.abs(low - prev_close),
            ),
        )
        return float(np.mean(tr[-period:]))

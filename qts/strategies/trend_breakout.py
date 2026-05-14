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
        self._cooling_days: int = 0
        self.use_dow_filter: bool = True
        self.regime_engine = None  # set externally for adaptive mode
        # Experiment switches (default off, no behavior change)
        self.enable_pullback_entry: bool = False
        self.pullback_max_alloc_pct: float = 0.4
        self.enable_rank_buffer: bool = False
        self.sell_rank_multiplier: int = 2

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

        # ── 1. Market Regime: adaptive or three-tier ──
        breadth = self._compute_breadth(market_data, current_date)

        if self.regime_engine is not None:
            # Adaptive mode: use pre-computed regime dimensions (fast lookup)
            if self._regime_raw_cache is not None:
                trend_raw = float(self._regime_raw_cache["trend"].get(current_date, 0.5))
                stability_raw = float(self._regime_raw_cache["stability"].get(current_date, 0.5))
                volume_raw = float(self._regime_raw_cache["volume"].get(current_date, 0.5))
                regime_score = self.regime_engine.compute_score(
                    current_date, breadth,
                    trend_raw=trend_raw, stability_raw=stability_raw,
                    volume_raw=volume_raw,
                )
            else:
                # Fallback: compute from raw matrices (slow)
                allowed_cols = list(market_data["symbol"].unique())
                prices_slice = (
                    self._prices_pivot.loc[:current_date,
                    [c for c in allowed_cols if c in self._prices_pivot.columns]]
                    if self._prices_pivot is not None else None
                )
                volumes_slice = (
                    self._volumes_pivot.loc[:current_date,
                    [c for c in allowed_cols if c in self._volumes_pivot.columns]]
                    if self._volumes_pivot is not None else None
                )
                regime_score = self.regime_engine.compute_score(
                    current_date, breadth,
                    prices=prices_slice, volumes=volumes_slice,
                )
            if regime_score <= 0.01:
                logger.info(f"[{current_date}] 评分{regime_score:.2f}≈0 空仓")
                return pd.DataFrame()

            adapted = self.regime_engine.map_params(regime_score)
            # Override instance vars with adaptive params for this call
            self.breakout_days = adapted["breakout_days"]
            self.support_days = adapted["support_days"]
            self.ma_days = adapted["ma_days"]
            self.atr_multiple = adapted["atr_multiple"]
            self.volume_ratio = adapted["volume_ratio"]
            self.top_n = adapted["top_n"]
            alloc_pct = adapted["alloc_pct"]
            regime = "adaptive"
        else:
            # Three-tier mode (original)
            if breadth < self.breadth_half:
                logger.info(f"[{current_date}] 广度{breadth:.0%}<{self.breadth_half:.0%} 空仓")
                return pd.DataFrame()
            elif breadth < self.min_breadth:
                regime = "half"
                alloc_pct = 0.50
            else:
                regime = "full"
                alloc_pct = 1.00
            regime_score = breadth  # use breadth as proxy for logging

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
        filters_ok = self._apply_filters(latest, market_data, current_date)

        if self.enable_rank_buffer:
            # ── Rank buffer mode ──
            sell_top_n = self.top_n * self.sell_rank_multiplier

            # Entry scores (original breakout, for new buys only)
            entry_scores = self._evaluate_breakout_batch(current_date, filters_ok)
            entry_ranked = sorted(entry_scores.items(), key=lambda x: (-x[1], x[0]))

            # Holding scores (trend continuation, for existing positions)
            current_syms = list(current_positions["symbol"]) if not current_positions.empty else []
            current_in_filters = [s for s in current_syms if s in filters_ok]
            holding_scores = self._compute_holding_scores(
                current_date, current_in_filters, market_data
            )
            holding_ranked = sorted(holding_scores.items(), key=lambda x: (-x[1], x[0]))

            # Assign target_reason by rank
            target_syms: list[tuple[str, str, float]] = []  # [(sym, target_reason, score)]
            for i, (sym, score) in enumerate(holding_ranked):
                if i < self.top_n:
                    target_syms.append((sym, "normal_hold", score))
                elif i < sell_top_n:
                    target_syms.append((sym, "hold_buffer", score))
                # rank >= sell_top_n -> dropped

            # New buys: top_n from entry_scores not already held
            held_syms = {s for s, _, _ in target_syms}
            new_count = 0
            for sym, score in entry_ranked:
                if sym in held_syms:
                    continue
                target_syms.append((sym, "new_buy", score))
                new_count += 1
                if new_count >= self.top_n:
                    break

            # Cap at sell_top_n
            target_syms = target_syms[:sell_top_n]

            if not target_syms:
                return pd.DataFrame()

            n = len(target_syms)
            weight = min(alloc_pct / n, self.max_weight_per_stock)

            logger.info(
                f"[{current_date}] rank_buffer | targets={n} "
                f"(new={sum(1 for t in target_syms if t[1]=='new_buy')} "
                f"hold={sum(1 for t in target_syms if t[1]!='new_buy')}) "
                f"alloc={alloc_pct:.0%} w={weight:.2%}"
            )

            return pd.DataFrame({
                "symbol":        [t[0] for t in target_syms],
                "target_weight": [weight] * n,
                "score":         [t[2] for t in target_syms],
                "reason":        ["breakout_entry" if t[1] == "new_buy" else ""
                                  for t in target_syms],
                "target_reason": [t[1] for t in target_syms],
            })

        else:
            # ── Original logic with entry type tagging ──
            target_scores: dict[str, float] = {}
            target_reasons: dict[str, str] = {}

            # 2a. Keep existing positions that haven't triggered exit
            if not current_positions.empty:
                for _, pos in current_positions.iterrows():
                    sym = pos["symbol"]
                    entry_price = self._entry_prices.get(sym, pos.get("avg_cost", 0))
                    should_exit, _ = self.check_exit(
                        sym, current_date, market_data, 0.0, entry_price
                    )
                    if not should_exit:
                        target_scores[sym] = 0.5
                        target_reasons[sym] = "hold"

            # 2b. Find new breakout entries
            if regime == "full" or len(target_scores) < 5:
                new_entries = self._evaluate_breakout_batch(current_date, filters_ok)
                for sym, score in new_entries.items():
                    if sym not in target_scores:
                        target_scores[sym] = score
                        target_reasons[sym] = "breakout_entry"

            # 2c. Pullback entries (with alloc_pct gate)
            pb_candidates = 0
            pb_added = 0
            pb_gated = 0
            if self.enable_pullback_entry and alloc_pct > 0:
                pb_gate_ok = alloc_pct <= self.pullback_max_alloc_pct
                pullback_scores = self._evaluate_pullback_batch(
                    current_date, filters_ok, market_data
                )
                pb_candidates = len(pullback_scores)
                if pb_gate_ok:
                    for sym, score in pullback_scores.items():
                        if sym not in target_scores:
                            target_scores[sym] = score * 0.8
                            target_reasons[sym] = "pullback_entry"
                            pb_added += 1
                else:
                    pb_gated = pb_candidates

            # Track pullback funnel
            if not hasattr(self, '_pb_funnel'):
                self._pb_funnel: list[dict] = []
            self._pb_funnel.append({
                "date": current_date,
                "branch_entered": int(alloc_pct > 0),
                "alloc_pct": alloc_pct,
                "candidates": pb_candidates,
                "added_to_target": pb_added,
                "gated_out": pb_gated,
                "bought": 0,
            })

            if not target_scores:
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
                            "reason": ["hold"] * n,
                        })
                return pd.DataFrame()

            # ── 3. Select top N ──
            scored = sorted(target_scores.items(), key=lambda x: (-x[1], x[0]))
            effective_n = max(5, int(self.top_n * alloc_pct)) if regime == "half" else self.top_n
            selected = scored[:effective_n]
            n = len(selected)
            weight = (1.0 - self.cash_buffer) * alloc_pct / n if n > 0 else 0
            weight = min(weight, self.max_weight_per_stock)

            names = [s[0] for s in selected]
            reasons = [target_reasons.get(s[0], "") for s in selected]

            # Update funnel: count pullback buys in final selection
            if self.enable_pullback_entry and self._pb_funnel:
                pb_bought = sum(1 for r in reasons if r == "pullback_entry")
                self._pb_funnel[-1]["bought"] = pb_bought

            if regime == "adaptive":
                logger.info(
                    f"[{current_date}] 评分{regime_score:.2f} alloc{alloc_pct:.0%} "
                    f"brk{self.breakout_days}d sup{self.support_days}d "
                    f"选中 {n} 只（{reasons.count('breakout_entry')} brk, "
                    f"{reasons.count('pullback_entry')} pb, {reasons.count('hold')} hold）"
                )
            else:
                logger.info(
                    f"[{current_date}] {regime}广度{breadth:.0%} | "
                    f"选中 {n} 只（{reasons.count('breakout_entry')} brk, "
                    f"{reasons.count('pullback_entry')} pb, {reasons.count('hold')} hold）"
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
    _prices_pivot: pd.DataFrame | None = None
    _volumes_pivot: pd.DataFrame | None = None
    _highs_pivot: pd.DataFrame | None = None
    _opens_pivot: pd.DataFrame | None = None
    _lows_pivot: pd.DataFrame | None = None
    _regime_raw_cache: dict[str, pd.Series] | None = None

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

    def _evaluate_breakout_batch(
        self, date: str, eligible: list[str],
    ) -> dict[str, float]:
        """Vectorized breakout detection for all eligible symbols at once.

        Uses pre-computed pivot matrices (set by engine) instead of per-symbol loops.
        Returns {symbol: score} for symbols that pass all three entry conditions.
        """
        if not eligible or self._prices_pivot is None:
            return {}

        prices = self._prices_pivot
        highs = self._highs_pivot
        volumes = self._volumes_pivot

        common = [s for s in eligible if s in prices.columns]
        if not common:
            return {}

        date_mask = prices.index <= date
        close_mat = prices.loc[date_mask, common]
        high_mat = highs.loc[date_mask, common]
        vol_mat = volumes.loc[date_mask, common]

        need_bars = max(self.breakout_days, self.ma_days) + 1
        if len(close_mat) < need_bars:
            return {}

        today_close = close_mat.iloc[-1]
        today_vol = vol_mat.iloc[-1]

        valid = today_vol > 0
        if not valid.any():
            return {}

        # Condition 1: Close breaks above N-day high (exclude today)
        n_day_high = high_mat.iloc[-(self.breakout_days + 1):-1].max()
        cond1 = today_close > n_day_high

        # Condition 2: Volume >= ratio * N-day average volume
        avg_vol = vol_mat.iloc[-(self.breakout_days + 1):-1].mean()
        cond2 = (avg_vol > 0) & (today_vol >= avg_vol * self.volume_ratio)

        # Condition 3: Close above MA
        ma = close_mat.iloc[-(self.ma_days + 1):-1].mean()
        cond3 = today_close > ma

        signal_mask = valid & cond1 & cond2 & cond3
        if not signal_mask.any():
            return {}

        breakout_pct = (today_close[signal_mask] / n_day_high[signal_mask] - 1.0) * 100
        volume_boost = today_vol[signal_mask] / avg_vol[signal_mask].replace(0, np.nan)
        scores = breakout_pct * np.log1p(volume_boost)

        return {sym: float(scores[sym]) for sym in signal_mask[signal_mask].index if scores[sym] > 0}

    def _evaluate_pullback_batch(
        self, date: str, eligible: list[str], market_data: pd.DataFrame,
    ) -> dict[str, float]:
        """V1 pullback entry: trend retracement to MA20, no breakout required.

        Conditions (all must pass):
          1. ret_20d > 0 OR max_high_20d > max_high_before_20d
          2. today_close > MA20
          3. Past 5-day ([-6:-1]) lowest low near MA20 (<=3%)
          4. Pullback volume < 20d avg * 0.8
          5. today_close > today_open (positive candle)
          6. today_volume >= 20d avg * 0.8 (confirmation)

        Score = trend_s*0.25 + ma_dist_s*0.30 + confirm_s*0.25 + vol_s*0.20
        """
        if not eligible:
            return {}
        prices = self._prices_pivot
        opens_p = self._opens_pivot
        lows_p = self._lows_pivot
        volumes = self._volumes_pivot
        highs = self._highs_pivot
        if any(p is None for p in [prices, opens_p, lows_p, volumes, highs]):
            return {}
        common = [s for s in eligible if s in prices.columns]
        if not common:
            return {}
        date_mask = prices.index <= date
        close_mat = prices.loc[date_mask, common]
        open_mat = opens_p.loc[date_mask, common]
        low_mat = lows_p.loc[date_mask, common]
        vol_mat = volumes.loc[date_mask, common]
        high_mat = highs.loc[date_mask, common]
        need = 60 + 1
        if len(close_mat) < need:
            return {}
        today_close = close_mat.iloc[-1]
        today_open = open_mat.iloc[-1]
        today_vol = vol_mat.iloc[-1]
        # MA20 excluding today
        ma20 = close_mat.iloc[-21:-1].mean()
        avg_vol_20 = vol_mat.iloc[-21:-1].mean()
        # ret_20d excluding today
        ret_20d = close_mat.iloc[-2] / close_mat.iloc[-22] - 1  # shift 1 to avoid today
        # Stage high: past 20 days max > past 21-60 days max
        max_high_20 = high_mat.iloc[-21:-1].max()
        max_high_before_20 = high_mat.iloc[-61:-21].max()
        # Pullback window [-6:-1]: completed trading days
        low_pullback = low_mat.iloc[-6:-1].min()
        vol_pullback = vol_mat.iloc[-6:-1].mean()
        valid = today_vol > 0
        cond_trend = (ret_20d > 0) | (max_high_20 > max_high_before_20)
        cond_above_ma = today_close > ma20
        cond_near_ma = abs(low_pullback / ma20 - 1) < 0.05  # D2: 5%
        cond_shrink = vol_pullback.fillna(0) < avg_vol_20 * 1.0     # D2: no expansion
        cond_pos_candle = today_close > today_open
        cond_confirm_vol = today_vol >= avg_vol_20 * 0.8
        signal = (valid & cond_trend & cond_above_ma & cond_near_ma &
                  cond_shrink & cond_pos_candle & cond_confirm_vol)
        if not signal.any():
            return {}
        trend_s = ret_20d.clip(0, 0.5) / 0.5
        ma_dist_s = (1 - abs(today_close / ma20 - 1).fillna(1) / 0.05).clip(0, 1)
        confirm_s = ((today_close / today_open - 1) / 0.03).clip(0, 1)
        vol_s = (today_vol / avg_vol_20.replace(0, float("nan"))).clip(0.8, 2.0) / 2.0
        score = (trend_s * 0.25 + ma_dist_s * 0.30 + confirm_s * 0.25 + vol_s * 0.20)
        result = {}
        for sym in signal[signal].index:
            if score[sym] > 0:
                result[sym] = float(score[sym])
        return result

    def _compute_holding_scores(
        self, date: str, symbols: list[str], market_data: pd.DataFrame,
    ) -> dict[str, float]:
        """V1 holding score: trend continuation, no re-breakout required.

        Returns {sym: score} for symbols still above their adaptive MA.
        Score = clipped distance_to_ma * log(1 + clipped_volume_boost).
        """
        if not symbols:
            return {}
        prices = self._prices_pivot
        volumes = self._volumes_pivot
        common = [s for s in symbols if s in prices.columns]
        if not common:
            return {}
        date_mask = prices.index <= date
        close_mat = prices.loc[date_mask, common]
        vol_mat = volumes.loc[date_mask, common]
        need = self.ma_days + 1
        if len(close_mat) < need:
            return {}
        today_close = close_mat.iloc[-1]
        today_vol = vol_mat.iloc[-1]
        ma = close_mat.iloc[-(self.ma_days + 1):-1].mean()
        valid = (today_close > ma) & (today_vol > 0)
        if not valid.any():
            return {}
        # Distance to MA (clipped 0-20%)
        dist = ((today_close[valid] / ma[valid] - 1) * 100).clip(0, 20)
        # Volume boost (clipped 0.5-3.0x)
        avg_vol = vol_mat.iloc[-(self.ma_days + 1):-1].mean()
        vol_boost = (today_vol[valid] / avg_vol[valid].replace(0, float("nan"))).clip(0.5, 3.0)
        scores = dist * np.log1p(vol_boost)
        return {sym: float(scores[sym]) for sym in valid[valid].index if scores[sym] > 0}

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

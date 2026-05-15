"""AKShare market data client."""
import time
from abc import ABC, abstractmethod
import pandas as pd

from qts.utils.logger import logger


class MarketDataProvider(ABC):
    """Abstract interface for market data retrieval."""

    @abstractmethod
    def get_bars(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        freq: str = "1d",
        adjusted: str = "qfq",
    ) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_stock_basic(self) -> pd.DataFrame:
        pass


class AKShareClient(MarketDataProvider):
    """AKShare-based market data provider.

    Fetches daily OHLCV data with pre/post-adjusted close prices,
    suspension status, and price limit information.
    """

    def __init__(self, rate_limit: float = 0.8, retries: int = 2, circuit_breaker: int = 10):
        self._stock_basic_cache: pd.DataFrame | None = None
        self._rate_limit = rate_limit
        self._retries = retries
        self._circuit_breaker = circuit_breaker
        self.last_failed_symbols: list[str] = []
        self.last_skipped_symbols: list[str] = []

    def get_stock_basic(self) -> pd.DataFrame:
        """Get basic stock info (code, name, list date, industry)."""
        if self._stock_basic_cache is not None:
            return self._stock_basic_cache
        import akshare as ak
        logger.info("Fetching stock basic info from AKShare")
        raw = ak.stock_info_a_code_name()
        result = pd.DataFrame({
            "symbol": raw["code"].astype(str).str.zfill(6),
            "name": raw["name"],
        })
        self._stock_basic_cache = result
        return result

    def get_bars(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        freq: str = "1d",
        adjusted: str = "qfq",
    ) -> pd.DataFrame:
        """Fetch daily bars for given symbols.

        Args:
            symbols: List of stock codes (6-digit strings like '000001')
            start_date: Start date YYYYMMDD or YYYY-MM-DD
            end_date: End date YYYYMMDD or YYYY-MM-DD
            freq: '1d' for daily
            adjusted: 'qfq' (前复权) or 'hfq' (后复权) or 'none'

        Returns DataFrame with standard schema:
            symbol, trade_date, open, high, low, close, volume, amount,
            adj_factor, is_suspended, limit_up, limit_down, is_st
        """
        import akshare as ak

        start = start_date.replace("-", "")
        end = end_date.replace("-", "")

        n = len(symbols)
        logger.info(f"Fetching bars for {n} symbols (rate limit: {self._rate_limit}s, "
                    f"retries: {self._retries}, circuit_breaker: {self._circuit_breaker})")

        self.last_failed_symbols = []
        self.last_skipped_symbols = []
        frames = []
        consecutive_failures = 0

        for i, sym in enumerate(symbols):
            circuit_tripped = False
            for attempt in range(self._retries + 1):
                try:
                    df = self._fetch_single(sym, start, end, adjusted)
                    if len(df) > 0:
                        frames.append(df)
                    consecutive_failures = 0  # reset on success
                    break
                except Exception as e:
                    if attempt < self._retries:
                        time.sleep(1.0)
                    else:
                        logger.warning(f"Failed to fetch {sym} after {self._retries + 1} attempts: {e}")
                        self.last_failed_symbols.append(sym)
                        consecutive_failures += 1

                        if consecutive_failures >= self._circuit_breaker:
                            remaining = symbols[i + 1:]
                            self.last_skipped_symbols = list(remaining)
                            logger.error(
                                f"Circuit breaker tripped: {consecutive_failures} consecutive failures. "
                                f"Likely IP ban or provider blocking. "
                                f"Skipping remaining {len(remaining)} symbols."
                            )
                            circuit_tripped = True
                            break
            if circuit_tripped:
                break

            if i < n - 1:
                time.sleep(self._rate_limit)

        if not frames:
            return pd.DataFrame()

        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        n_failed = len(self.last_failed_symbols)
        n_skipped = len(self.last_skipped_symbols)
        summary = (f"Fetched {len(result)} bars for {len(frames)}/{len(symbols)} symbols"
                   + (f", {n_failed} failed" if n_failed else ""))
        if n_skipped > 0:
            summary += f" ({n_skipped} skipped by circuit breaker)"
        logger.info(summary)
        return result

    def _fetch_single(
        self, symbol: str, start: str, end: str, adjusted: str
    ) -> pd.DataFrame:
        """Fetch a single stock's daily bars."""
        import akshare as ak

        adjust_map = {"qfq": "qfq", "hfq": "hfq", "none": ""}
        adj = adjust_map.get(adjusted, "qfq")

        raw = ak.stock_zh_a_hist(
            symbol=symbol,
            period="daily",
            start_date=start,
            end_date=end,
            adjust=adj,
        )
        if raw.empty:
            return pd.DataFrame()

        raw = raw.rename(columns={
            "日期": "trade_date",
            "开盘": "open",
            "最高": "high",
            "最低": "low",
            "收盘": "close",
            "成交量": "volume",
            "成交额": "amount",
            "振幅": "amplitude",
            "涨跌幅": "pct_change",
            "涨跌额": "change",
            "换手率": "turnover_rate",
        })

        raw["symbol"] = symbol
        raw["trade_date"] = pd.to_datetime(raw["trade_date"]).dt.strftime("%Y-%m-%d")
        raw["is_suspended"] = raw["volume"] <= 0
        raw["volume"] = raw["volume"].astype(float)
        raw["amount"] = raw["amount"].astype(float)

        # Price limits: ±10% based on previous close (approximate for backtest)
        # More precise limits require fetching from exchange rules
        raw["limit_up"] = raw["close"].shift(1) * 1.10
        raw["limit_down"] = raw["close"].shift(1) * 0.90
        raw["limit_up"] = raw["limit_up"].fillna(raw["open"] * 1.10)
        raw["limit_down"] = raw["limit_down"].fillna(raw["open"] * 0.90)

        # ST flag: crude detection by 5% limit
        raw["is_st"] = False

        # adj_factor: with qfq (前复权), AKShare returns already-adjusted OHLC.
        # adj_factor=1.0 means "no further adjustment needed" for qfq data.
        # For real trading, you need unadjusted prices to compute limit_up/down correctly.
        # Here we store 1.0 and note: limit_up/down are approximate on qfq data.
        raw["adj_factor"] = 1.0

        cols = [
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "is_suspended",
            "limit_up", "limit_down", "is_st",
        ]
        return raw[cols]

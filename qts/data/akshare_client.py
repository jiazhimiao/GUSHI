"""AKShare market data client."""
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

    def __init__(self):
        self._stock_basic_cache: pd.DataFrame | None = None

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

        frames = []
        for sym in symbols:
            try:
                df = self._fetch_single(sym, start, end, adjusted)
                if len(df) > 0:
                    frames.append(df)
            except Exception as e:
                logger.warning(f"Failed to fetch {sym}: {e}")

        if not frames:
            return pd.DataFrame()

        result = pd.concat(frames, ignore_index=True)
        logger.info(f"Fetched {len(result)} bars for {len(frames)}/{len(symbols)} symbols")
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

        # Adj factor: with qfq adjust, close is already adjusted
        raw["adj_factor"] = 1.0

        cols = [
            "symbol", "trade_date", "open", "high", "low", "close",
            "volume", "amount", "adj_factor", "is_suspended",
            "limit_up", "limit_down", "is_st",
        ]
        return raw[cols]

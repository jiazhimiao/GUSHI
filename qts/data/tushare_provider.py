"""Tushare-compatible market data provider.

Uses a Tushare Pro compatible API endpoint (jiaoch.site) for bulk daily data.
Unlike AKShareClient (per-stock), this provider fetches all A-share daily bars
in a single request per trade date.

Token and URL are read from environment variables:
    TUSHARE_TOKEN      — required
    TUSHARE_HTTP_URL   — optional, defaults to http://jiaoch.site

Usage:
    provider = TushareProvider()
    df = provider.fetch_daily_by_date("20260511")       # all ~5490 A stocks
    af = provider.fetch_adj_factor_by_date("20260511")   # all ~5520 adj factors
"""
import os
import re
import json
import requests
import pandas as pd

from qts.utils.logger import logger
from qts.data.akshare_client import MarketDataProvider


class TushareProvider(MarketDataProvider):
    """Tushare Pro compatible API provider for bulk daily market data.

    Implements MarketDataProvider for drop-in compatibility with AKShareClient.
    Fetches all A-share daily bars in a single request per trade date (bulk),
    then filters to the requested symbols.
    """

    _DATE_RE = re.compile(r"^\d{8}$")

    def __init__(self, token: str | None = None, http_url: str | None = None):
        self._token = token or os.environ.get("TUSHARE_TOKEN")
        if not self._token:
            raise ValueError(
                "TUSHARE_TOKEN environment variable is required. "
                "Set it in PowerShell: "
                '$env:TUSHARE_TOKEN="your_token"'
            )
        self._http_url = http_url or os.environ.get("TUSHARE_HTTP_URL", "http://jiaoch.site")
        self._session = requests.Session()
        self._timeout = 30
        logger.info(f"TushareProvider initialized (url={self._http_url}, token_len={len(self._token)})")

    def _validate_date(self, date_str: str) -> str:
        if not self._DATE_RE.match(date_str):
            raise ValueError(f"date_str must be YYYYMMDD, got: {date_str}")
        return date_str

    def _post(self, api_name: str, **params) -> pd.DataFrame:
        """Post to the Tushare-compatible API and return a DataFrame."""
        url = f"{self._http_url}/{api_name}"
        payload = {
            "api_name": api_name,
            "token": self._token,
            "params": params,
            "fields": "",
        }
        try:
            resp = self._session.post(url, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            result = json.loads(resp.text)
            if result.get("code") != 0:
                raise RuntimeError(f"API error from {api_name}: {result.get('msg', 'unknown')}")
            data = result["data"]
            if not data or not data.get("items"):
                return pd.DataFrame()
            return pd.DataFrame(data["items"], columns=data["fields"])
        except requests.RequestException as e:
            logger.error(f"HTTP error calling {api_name}: {e}")
            raise

    def fetch_daily_by_date(self, date_str: str) -> pd.DataFrame:
        """Fetch daily OHLCV for all A-share stocks on a single trade date.

        Args:
            date_str: Trade date in YYYYMMDD format, e.g. "20260511".

        Returns DataFrame with columns:
            ts_code, trade_date, open, high, low, close, pre_close,
            change, pct_chg, vol, amount
        """
        self._validate_date(date_str)
        df = self._post("daily", trade_date=date_str)
        if df.empty:
            logger.warning(f"daily({date_str}) returned empty — market closed or API issue")
        return df

    def fetch_adj_factor_by_date(self, date_str: str) -> pd.DataFrame:
        """Fetch adjustment factors for all A-share stocks on a single trade date.

        Args:
            date_str: Trade date in YYYYMMDD format.

        Returns DataFrame with columns:
            ts_code, trade_date, adj_factor
        """
        self._validate_date(date_str)
        df = self._post("adj_factor", trade_date=date_str)
        if df.empty:
            logger.warning(f"adj_factor({date_str}) returned empty")
        return df

    def transform_to_standard(self, daily_df: pd.DataFrame) -> pd.DataFrame:
        """Transform raw Tushare daily output to project standard schema.

        Field mapping:
            ts_code    → symbol (strip .SZ/.SH suffix)
            trade_date → YYYY-MM-DD
            open/high/low/close → direct
            pre_close  → pre_close (not in AKShare schema but available from Tushare)
            vol        → volume (手, unchanged)
            amount     → × 1000 (千元→元)
            adj_factor → 1.0
            is_suspended → volume <= 0

        Returns DataFrame with columns matching project BAR_COLUMNS plus pre_close.
        """
        if daily_df.empty:
            return pd.DataFrame()

        df = daily_df.copy()
        df["symbol"] = df["ts_code"].str.replace(r"\.(SZ|SH|BJ)$", "", regex=True)
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d").dt.strftime("%Y-%m-%d")
        df["volume"] = df["vol"].astype(float)
        df["amount"] = df["amount"].astype(float) * 1000.0
        df["adj_factor"] = 1.0
        df["is_suspended"] = df["volume"] <= 0

        # Approximate price limits (same convention as AKShareClient):
        # ±10% of previous close. This is approximate on qfq/unadjusted data.
        df["limit_up"] = df["pre_close"] * 1.10
        df["limit_down"] = df["pre_close"] * 0.90

        # ST flag: crude detection by 5% price limit
        # (Tushare daily does not include ST status; default to False)
        df["is_st"] = False

        cols = [
            "symbol", "trade_date", "open", "high", "low", "close",
            "pre_close", "volume", "amount", "adj_factor", "is_suspended",
            "limit_up", "limit_down", "is_st",
        ]
        return df[cols]

    def fetch_formatted(self, date_str: str) -> pd.DataFrame:
        """Fetch daily data and transform to standard schema in one call."""
        self._validate_date(date_str)
        raw = self.fetch_daily_by_date(date_str)
        return self.transform_to_standard(raw)

    # ---- MarketDataProvider interface ----

    def get_bars(
        self,
        symbols: list[str],
        start_date: str,
        end_date: str,
        freq: str = "1d",
        adjusted: str = "qfq",
    ) -> pd.DataFrame:
        """Fetch daily bars for given symbols across a date range.

        Args:
            symbols: List of 6-digit stock codes.
            start_date: Start date YYYY-MM-DD or YYYYMMDD.
            end_date: End date YYYY-MM-DD or YYYYMMDD.
            freq: Only '1d' is supported.
            adjusted: Only 'qfq' is supported (/daily endpoint returns qfq).

        Returns DataFrame with BAR_COLUMNS + pre_close.
        """
        if freq != "1d":
            raise ValueError("TushareProvider only supports freq='1d'")
        if adjusted != "qfq":
            raise ValueError("TushareProvider only supports adjusted='qfq'")

        start = start_date.replace("-", "")
        end = end_date.replace("-", "")

        # Generate candidate trading dates (business days)
        start_dt = pd.Timestamp(start[:4] + "-" + start[4:6] + "-" + start[6:8])
        end_dt = pd.Timestamp(end[:4] + "-" + end[4:6] + "-" + end[6:8])
        candidate_dates = pd.date_range(start_dt, end_dt, freq="B")

        # Cross-check with existing parquet for known trading days
        from qts.utils.config import get_project_root
        parquet_path = get_project_root() / "data/raw/HS300_daily.parquet"
        known_dates: set[str] = set()
        if parquet_path.exists():
            existing = pd.read_parquet(parquet_path, columns=["trade_date"])
            known_dates = set(existing["trade_date"].unique())

        dates_to_fetch: list[str] = []
        for d in candidate_dates:
            ds = d.strftime("%Y-%m-%d")
            if known_dates and ds not in known_dates:
                continue
            dates_to_fetch.append(d.strftime("%Y%m%d"))

        if not dates_to_fetch:
            logger.warning("No trading dates to fetch after calendar check")
            return pd.DataFrame()

        symbol_set = set(symbols)
        frames: list[pd.DataFrame] = []
        empty_dates: list[str] = []

        for d8 in dates_to_fetch:
            try:
                fmt = self.fetch_formatted(d8)
                if fmt.empty:
                    empty_dates.append(d8)
                    continue
                filtered = fmt[fmt["symbol"].isin(symbol_set)]
                if not filtered.empty:
                    frames.append(filtered)
            except Exception as e:
                logger.warning(f"Tushare get_bars: skipping {d8}: {e}")
                continue

        if empty_dates:
            logger.info(
                f"Tushare: {len(empty_dates)} dates returned empty "
                f"(market closed or no data): {empty_dates}"
            )

        if not frames:
            logger.error("Tushare get_bars: no data fetched for any date")
            return pd.DataFrame()

        result = pd.concat(frames, ignore_index=True)
        logger.info(
            f"Tushare get_bars: {len(result)} rows, "
            f"{result['trade_date'].nunique()} dates, "
            f"{result['symbol'].nunique()} symbols"
        )
        return result

    def get_stock_basic(self) -> pd.DataFrame:
        """Not supported by Tushare/jiaoch.site.

        Use AKShareClient for stock basic info.
        """
        raise NotImplementedError(
            "TushareProvider does not support get_stock_basic(). "
            "Use AKShareClient for stock basic info."
        )

    # ---- diagnostics ----

    def check_adj_factor_stable(self, dates: list[str]) -> dict:
        """Check if adj_factor is stable across a list of dates.

        Returns dict with:
            stable: True if adj_factor values are identical across all dates
            per_stock_diffs: dict of symbol -> list of (date, adj_factor) for stocks with changes
            common_stocks: set of ts_code present in all dates
        """
        af_by_date = {}
        for d in dates:
            af = self.fetch_adj_factor_by_date(d)
            if af.empty:
                return {"stable": False, "reason": f"adj_factor({d}) returned empty"}
            af_by_date[d] = af.set_index("ts_code")["adj_factor"]

        common = set.intersection(*(set(af.index) for af in af_by_date.values()))
        if not common:
            return {"stable": False, "reason": "no common stocks across dates"}

        ref_date = dates[0]
        ref_af = af_by_date[ref_date]
        diffs = {}
        for d in dates[1:]:
            for code in common:
                if abs(ref_af[code] - af_by_date[d][code]) > 1e-6:
                    diffs.setdefault(code, []).append((ref_date, ref_af[code]))
                    diffs[code].append((d, af_by_date[d][code]))

        return {
            "stable": len(diffs) == 0,
            "per_stock_diffs": diffs,
            "common_stocks": common,
        }

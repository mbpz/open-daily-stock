"""Market data wrapper with auto-polling."""
import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

class MarketData:
    def __init__(self, code: str, name: str, price: float, change: float, volume: str):
        self.code = code
        self.name = name
        self.price = price
        self.change = change
        self.volume = volume

class DataProviderWrapper:
    def __init__(self, poll_interval: int = 30):
        self._poll_interval = poll_interval
        self._stocks: List[str] = []
        self._data: Dict[str, MarketData] = {}
        self._last_update: Optional[str] = None

    def set_stocks(self, stocks: List[str]):
        self._stocks = stocks

    @property
    def poll_interval(self) -> int:
        return self._poll_interval

    async def fetch_all(self):
        """Fetch market data for all configured stocks."""
        self._data = {}
        for code in self._stocks:
            data = await self._fetch_one(code)
            if data:
                self._data[code] = data
        tz_cn = timezone(timedelta(hours=8))
        self._last_update = datetime.now(tz_cn).strftime("%H:%M:%S")

    async def _fetch_one(self, code: str) -> Optional[MarketData]:
        """Route to appropriate provider based on code format."""
        if len(code) == 6 and code.isdigit():
            return await self._fetch_akshare(code)
        elif code.startswith("hk") or code.isalpha():
            return await self._fetch_yfinance(code)
        return None

    async def _fetch_akshare(self, code: str) -> Optional[MarketData]:
        """Fetch A-share data using AkShareStockFetcher."""
        try:
            from data_provider.akshare_fetcher import AkshareFetcher
            fetcher = AkshareFetcher()
            result = await asyncio.to_thread(fetcher.get_realtime_quote, code)
            if not result:
                return None
            return MarketData(
                code=code,
                name=result.name or code,
                price=float(result.price) if result.price else 0.0,
                change=float(result.change_pct) if result.change_pct else 0.0,
                volume=self._format_volume(result.volume),
            )
        except Exception as e:
            logger.warning(f"Failed to fetch {code}: {e}")
            return None

    async def _fetch_yfinance(self, code: str) -> Optional[MarketData]:
        """Fetch HK/US data using YFinanceFetcher."""
        try:
            import pandas as pd  # lazy import - only needed when yfinance data arrives
            from data_provider.yfinance_fetcher import YfinanceFetcher
            fetcher = YfinanceFetcher()
            df = await asyncio.to_thread(fetcher.get_daily_data, code)
            if df is None or df.empty:
                return None
            # Get the last row for latest close and change
            last = df.iloc[-1]
            return MarketData(
                code=code,
                name=code,
                price=float(last.get('close', 0)) if pd.notna(last.get('close')) else 0.0,
                change=float(last.get('pct_chg', 0)) if pd.notna(last.get('pct_chg')) else 0.0,
                volume=self._format_volume(last.get('volume', 0)),
            )
        except Exception as e:
            logger.warning(f"Failed to fetch {code}: {e}")
            return None

    def _format_volume(self, vol) -> str:
        """Format volume to wanyij unit."""
        try:
            v = float(vol)
            if v >= 100000000:
                return f"{v/100000000:.1f}亿"
            elif v >= 10000:
                return f"{v/10000:.1f}万"
            return f"{v:.0f}"
        except (ValueError, TypeError):
            return "---"

    def get_data(self) -> Dict[str, MarketData]:
        return self._data

    def get_last_update(self) -> Optional[str]:
        return self._last_update
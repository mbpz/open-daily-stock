"""Refresh service for full data refresh: market + analysis + notification."""
import asyncio
import logging
from typing import List
from src.config import Config
from src.core.pipeline import StockAnalysisPipeline
from src.notification import NotificationService
from tui.data.wrapper import DataProviderWrapper

logger = logging.getLogger(__name__)

class RefreshService:
    """Orchestrates full data refresh: fetch → analyze → notify."""

    def __init__(self, config: Config):
        self._config = config
        self._dp = DataProviderWrapper()
        self._dp.set_stocks(config.stock_list)
        self._pipeline = StockAnalysisPipeline(config)
        self._notifier = NotificationService()

    async def refresh_all(self) -> List:
        """
        Full refresh: fetch market data → run analysis → send notifications.
        Returns list of analysis results.
        """
        try:
            # Step 1: Fetch all stock data
            logger.info("正在刷新股票行情...")
            await self._dp.fetch_all()

            # Step 2: Run analysis pipeline
            logger.info("正在执行股票分析...")
            results = await asyncio.to_thread(
                self._pipeline.run,
                self._config.stock_list,
                send_notification=True
            )

            logger.info(f"刷新完成: {len(results)} 只股票")
            return results

        except Exception as e:
            logger.error(f"刷新失败: {e}")
            raise
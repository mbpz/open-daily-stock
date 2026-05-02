"""test_data_provider 共享 fixtures"""
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

from tui.data.wrapper import DataProviderWrapper, MarketData


@pytest.fixture
def wrapper():
    """创建 DataProviderWrapper 实例"""
    return DataProviderWrapper(poll_interval=30)


@pytest.fixture
def mock_akshare_fetcher():
    """Mock AkShareStockFetcher"""
    with patch('data_provider.akshare_fetcher.AkshareFetcher') as mock:
        instance = MagicMock()
        # get_realtime_quote is called via asyncio.to_thread, so return regular value
        instance.get_realtime_quote = MagicMock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def mock_yfinance_fetcher():
    """Mock YfinanceFetcher"""
    with patch('data_provider.yfinance_fetcher.YfinanceFetcher') as mock:
        instance = MagicMock()
        # get_daily_data is called via asyncio.to_thread, so return regular value
        instance.get_daily_data = MagicMock()
        mock.return_value = instance
        yield instance


@pytest.fixture
def sample_akshare_result():
    """AkShare 返回的样例数据"""
    result = MagicMock()
    result.name = "贵州茅台"
    result.price = 1680.50
    result.change_pct = 1.25
    result.volume = 3500000
    return result


@pytest.fixture
def sample_yfinance_df():
    """YFinance 返回的样例 DataFrame"""
    import pandas as pd
    return pd.DataFrame({
        'close': [180.0, 182.5, 185.0],
        'pct_chg': [0.5, 1.0, 1.25],
        'volume': [1500000, 1600000, 1700000],
    })


@pytest.fixture
def event_loop():
    """创建事件循环用于 async 测试"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
# -*- coding: utf-8 -*-
"""DataProviderWrapper 测试"""
import pytest
from unittest.mock import patch, MagicMock

from tui.data.wrapper import DataProviderWrapper, MarketData


class TestDataProviderWrapper:
    """DataProviderWrapper 测试类"""

    @pytest.mark.asyncio
    async def test_wrapper_fetch_all(self, wrapper, mock_akshare_fetcher, sample_akshare_result):
        """Wrapper 获取所有股票数据"""
        # 设置股票列表
        wrapper.set_stocks(["000001", "600519"])

        # Mock akshare fetcher 返回值 - using to_thread so return value directly
        mock_akshare_fetcher.get_realtime_quote.return_value = sample_akshare_result

        # 执行 fetch_all
        await wrapper.fetch_all()

        # 验证数据已获取
        data = wrapper.get_data()
        assert len(data) == 2
        assert "000001" in data
        assert "600519" in data

        # 验证 MarketData 对象
        assert isinstance(data["000001"], MarketData)
        assert data["000001"].name == "贵州茅台"
        assert data["000001"].price == 1680.50

        # 验证最后更新时间已设置
        assert wrapper.get_last_update() is not None

    @pytest.mark.asyncio
    async def test_wrapper_fetch_akshare_stock(self, wrapper, mock_akshare_fetcher, sample_akshare_result):
        """测试 A 股股票获取 (6位数字)"""
        wrapper.set_stocks(["600519"])
        mock_akshare_fetcher.get_realtime_quote.return_value = sample_akshare_result

        await wrapper.fetch_all()

        data = wrapper.get_data()
        assert "600519" in data
        assert data["600519"].price == 1680.50

    @pytest.mark.asyncio
    async def test_wrapper_fetch_hk_stock(self, wrapper, mock_yfinance_fetcher, sample_yfinance_df):
        """测试港股股票获取 (hk 前缀)"""
        wrapper.set_stocks(["hk00700"])
        mock_yfinance_fetcher.get_daily_data.return_value = sample_yfinance_df

        await wrapper.fetch_all()

        data = wrapper.get_data()
        assert "hk00700" in data

    @pytest.mark.asyncio
    async def test_wrapper_fetch_us_stock(self, wrapper, mock_yfinance_fetcher, sample_yfinance_df):
        """测试美股股票获取 (字母代码)"""
        wrapper.set_stocks(["AAPL"])
        mock_yfinance_fetcher.get_daily_data.return_value = sample_yfinance_df

        await wrapper.fetch_all()

        data = wrapper.get_data()
        assert "AAPL" in data

    @pytest.mark.asyncio
    async def test_wrapper_empty_stocks(self, wrapper):
        """测试空股票列表"""
        wrapper.set_stocks([])

        await wrapper.fetch_all()

        data = wrapper.get_data()
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_wrapper_fetch_one_returns_none(self, wrapper, mock_akshare_fetcher):
        """测试获取失败时返回 None"""
        wrapper.set_stocks(["000001"])
        mock_akshare_fetcher.get_realtime_quote.return_value = None

        await wrapper.fetch_all()

        data = wrapper.get_data()
        assert "000001" not in data

    def test_wrapper_set_stocks(self, wrapper):
        """测试设置股票列表"""
        stocks = ["000001", "600519", "AAPL"]
        wrapper.set_stocks(stocks)

        assert wrapper._stocks == stocks

    def test_wrapper_poll_interval(self, wrapper):
        """测试轮询间隔属性"""
        assert wrapper.poll_interval == 30

        wrapper._poll_interval = 60
        assert wrapper.poll_interval == 60

    def test_wrapper_format_volume(self, wrapper):
        """测试成交量格式化"""
        # 亿级别
        assert wrapper._format_volume(150000000) == "1.5亿"
        # 万级别
        assert wrapper._format_volume(1500000) == "150.0万"
        # 普通
        assert wrapper._format_volume(1500) == "1500"
        # 无效值
        assert wrapper._format_volume("invalid") == "---"
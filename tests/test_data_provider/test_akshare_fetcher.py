# -*- coding: utf-8 -*-
"""AkshareFetcher 测试"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd


class TestAkshareFetcher:
    """AkshareFetcher 测试组"""

    @pytest.fixture
    def fetcher(self):
        """创建 AkshareFetcher 实例"""
        from data_provider.akshare_fetcher import AkshareFetcher
        return AkshareFetcher()

    def test_is_etf_code(self, fetcher):
        """ETF 代码判断"""
        from data_provider.akshare_fetcher import _is_etf_code

        # 上交所 ETF
        assert _is_etf_code('512000') is True  # 华夏中证证券公司ETF
        assert _is_etf_code('510050') is True  # 上证50ETF

        # 深交所 ETF
        assert _is_etf_code('159001') is True  # 深交所ETF

        # 普通股票
        assert _is_etf_code('600519') is False  # 贵州茅台
        assert _is_etf_code('000001') is False  # 平安银行

    def test_is_hk_code(self, fetcher):
        """港股代码判断"""
        from data_provider.akshare_fetcher import _is_hk_code

        # 带 hk 前缀
        assert _is_hk_code('hk00700') is True
        assert _is_hk_code('hk00001') is True

        # 5位纯数字
        assert _is_hk_code('00700') is True
        assert _is_hk_code('00001') is True

        # A股不是港股
        assert _is_hk_code('600519') is False
        assert _is_hk_code('000001') is False

    def test_is_us_code(self, fetcher):
        """美股代码判断"""
        from data_provider.akshare_fetcher import _is_us_code

        # 正常美股代码
        assert _is_us_code('AAPL') is True
        assert _is_us_code('TSLA') is True
        assert _is_us_code('MSFT') is True

        # 带点的美股
        assert _is_us_code('BRK.B') is True

        # A股不是美股
        assert _is_us_code('600519') is False
        assert _is_us_code('000001') is False

    def test_fetch_stock_data(self, fetcher):
        """获取 A 股历史数据"""
        mock_df = pd.DataFrame({
            '日期': ['2026-04-01', '2026-04-02', '2026-04-03'],
            '开盘': [1680.0, 1690.0, 1700.0],
            '收盘': [1690.0, 1700.0, 1710.0],
            '最高': [1700.0, 1710.0, 1720.0],
            '最低': [1670.0, 1680.0, 1690.0],
            '成交量': [1000000, 1200000, 1100000],
            '成交额': [1680000000, 2040000000, 1880000000],
            '振幅': [1.79, 1.78, 1.77],
            '涨跌幅': [0.60, 0.59, 0.59],
            '涨跌额': [10.0, 10.0, 10.0],
            '换手率': [0.05, 0.06, 0.05],
        })

        with patch.object(fetcher, '_fetch_stock_data', return_value=mock_df):
            df = fetcher._fetch_stock_data('600519', '2026-04-01', '2026-04-03')

            assert df is not None
            assert len(df) == 3

    def test_fetch_hk_data(self, fetcher):
        """获取港股历史数据"""
        mock_df = pd.DataFrame({
            '日期': ['2026-04-01', '2026-04-02'],
            '开盘': [300.0, 305.0],
            '收盘': [305.0, 310.0],
            '最高': [310.0, 315.0],
            '最低': [298.0, 300.0],
            '成交量': [500000, 550000],
            '成交额': [152500000, 167500000],
            '振幅': [4.0, 5.0],
            '涨跌幅': [1.67, 1.64],
            '涨跌额': [5.0, 5.0],
            '换手率': [0.05, 0.06],
        })

        with patch.object(fetcher, '_fetch_hk_data', return_value=mock_df):
            df = fetcher._fetch_hk_data('00700', '2026-04-01', '2026-04-03')

            assert df is not None
            assert len(df) == 2

    def test_fetch_etf_data(self, fetcher):
        """获取 ETF 历史数据"""
        mock_df = pd.DataFrame({
            '日期': ['2026-04-01', '2026-04-02'],
            '开盘': [1.0, 1.01],
            '收盘': [1.01, 1.02],
            '最高': [1.02, 1.03],
            '最低': [0.99, 1.0],
            '成交量': [10000000, 12000000],
            '成交额': [10000000, 12000000],
            '振幅': [3.0, 3.0],
            '涨跌幅': [1.0, 1.0],
            '涨跌额': [0.01, 0.01],
            '换手率': [0.1, 0.12],
        })

        with patch.object(fetcher, '_fetch_etf_data', return_value=mock_df):
            df = fetcher._fetch_etf_data('512000', '2026-04-01', '2026-04-03')

            assert df is not None
            assert len(df) == 2

    def test_normalize_data(self, fetcher):
        """数据标准化"""
        raw_df = pd.DataFrame({
            '日期': ['2026-04-01'],
            '开盘': [1680.0],
            '收盘': [1690.0],
            '最高': [1700.0],
            '最低': [1670.0],
            '成交量': [1000000],
            '成交额': [1680000000],
            '涨跌幅': [0.60],
        })

        df = fetcher._normalize_data(raw_df, '600519')

        # 验证列名已映射
        assert 'date' in df.columns
        assert 'open' in df.columns
        assert 'close' in df.columns
        assert 'code' in df.columns
        assert df['code'].iloc[0] == '600519'

    def test_get_realtime_quote_em(self, fetcher):
        """获取实时行情（东方财富源）"""
        # 构造全市场行情数据
        mock_spot_df = pd.DataFrame({
            '代码': ['600519', '000001'],
            '名称': ['贵州茅台', '平安银行'],
            '最新价': [1690.0, 12.5],
            '涨跌幅': [0.60, 0.85],
            '涨跌额': [10.0, 0.1],
            '成交量': [1000000, 1500000],
            '成交额': [1680000000, 18750000],
            '量比': [1.2, 1.5],
            '换手率': [0.05, 0.08],
            '振幅': [1.79, 2.0],
            '今开': [1680.0, 12.4],
            '最高': [1700.0, 12.8],
            '最低': [1670.0, 11.9],
            '市盈率-动态': [30.5, 8.2],
            '市净率': [10.2, 0.85],
            '总市值': [2120000000000, 230000000000],
            '流通市值': [1060000000000, 180000000000],
            '60日涨跌幅': [5.0, 3.5],
            '52周最高': [1800.0, 15.0],
            '52周最低': [1500.0, 10.0],
        })

        with patch.object(fetcher, '_get_stock_realtime_quote_em', return_value=None) as mock_get:
            # Create a mock quote to return
            from data_provider.realtime_types import UnifiedRealtimeQuote, RealtimeSource
            mock_quote = UnifiedRealtimeQuote(
                code='600519',
                name='贵州茅台',
                source=RealtimeSource.AKSHARE_EM,
                price=1690.0,
            )
            mock_get.return_value = mock_quote

            quote = fetcher._get_stock_realtime_quote_em('600519')

            assert quote is not None
            assert quote.code == '600519'

    def test_rate_limit(self, fetcher):
        """速率限制"""
        import time

        fetcher.sleep_min = 0.1
        fetcher.sleep_max = 0.2

        start = time.time()
        fetcher._enforce_rate_limit()
        fetcher._enforce_rate_limit()
        elapsed = time.time() - start

        # 两次调用应该至少间隔 sleep_min
        assert elapsed >= 0.1


class TestAkshareFetcherEdgeCases:
    """AkshareFetcher 边界情况测试"""

    @pytest.fixture
    def fetcher(self):
        """创建 AkshareFetcher 实例"""
        from data_provider.akshare_fetcher import AkshareFetcher
        return AkshareFetcher()

    def test_fetch_empty_data(self, fetcher):
        """空数据处理"""
        import pandas as pd

        with patch.object(fetcher, '_fetch_stock_data', return_value=pd.DataFrame()):
            df = fetcher._fetch_stock_data('600519', '2026-04-01', '2026-04-03')

            assert df is not None
            assert df.empty

    def test_fetch_api_error(self, fetcher):
        """API 错误处理"""
        with patch.object(fetcher, '_fetch_stock_data', side_effect=Exception("API Error")):
            with pytest.raises(Exception):
                fetcher._fetch_stock_data('600519', '2026-04-01', '2026-04-03')
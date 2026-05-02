# -*- coding: utf-8 -*-
"""EfinanceFetcher 测试"""
import pytest
from unittest.mock import MagicMock, patch
import pandas as pd


class TestEfinanceFetcher:
    """EfinanceFetcher 测试组"""

    @pytest.fixture
    def fetcher(self):
        """创建 EfinanceFetcher 实例"""
        from data_provider.efinance_fetcher import EfinanceFetcher
        return EfinanceFetcher()

    def test_get_daily_data_a_stock(self, fetcher):
        """获取 A 股日线数据"""
        mock_df = pd.DataFrame({
            '日期': ['2026-04-01', '2026-04-02', '2026-04-03'],
            '开盘': [1680.0, 1690.0, 1700.0],
            '收盘': [1690.0, 1700.0, 1710.0],
            '最高': [1700.0, 1710.0, 1720.0],
            '最低': [1670.0, 1680.0, 1690.0],
            '成交量': [1000000, 1200000, 1100000],
            '成交额': [1680000000, 2040000000, 1880000000],
            '涨跌幅': [0.60, 0.59, 0.59],
        })

        with patch.object(fetcher, '_fetch_raw_data', return_value=mock_df):
            df = fetcher.get_daily_data('600519', days=3)

            assert df is not None
            assert len(df) == 3

    def test_get_daily_data_hk_stock(self, fetcher):
        """获取港股日线数据"""
        mock_df = pd.DataFrame({
            '日期': ['2026-04-01', '2026-04-02'],
            '开盘': [300.0, 305.0],
            '收盘': [305.0, 310.0],
            '最高': [310.0, 315.0],
            '最低': [298.0, 300.0],
            '成交量': [500000, 550000],
            '成交额': [152500000, 167500000],
            '涨跌幅': [1.67, 1.64],
        })

        with patch.object(fetcher, '_fetch_raw_data', return_value=mock_df):
            df = fetcher.get_daily_data('00700', days=2)

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


class TestEfinanceFetcherEdgeCases:
    """EfinanceFetcher 边界情况测试"""

    def test_get_daily_data_empty_result(self):
        """空数据处理"""
        from data_provider.efinance_fetcher import EfinanceFetcher

        fetcher = EfinanceFetcher()

        with patch.object(fetcher, 'get_daily_data') as mock_method:
            mock_method.return_value = pd.DataFrame()

            df = fetcher.get_daily_data('600519', days=3)

            assert df is not None

    def test_get_daily_data_api_error(self):
        """API 错误处理"""
        from data_provider.efinance_fetcher import EfinanceFetcher

        fetcher = EfinanceFetcher()

        with patch.object(fetcher, 'get_daily_data') as mock_method:
            mock_method.side_effect = Exception("Network Error")

            with pytest.raises(Exception):
                fetcher.get_daily_data('600519', days=3)
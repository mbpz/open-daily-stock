# -*- coding: utf-8 -*-
"""StockAnalysisPipeline 流水线测试"""
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from datetime import date

from src.core.pipeline import StockAnalysisPipeline
from src.analyzer import AnalysisResult


class TestPipelineFetchData:
    """Pipeline 数据获取测试"""

    def test_fetch_data_success(self, mock_config):
        """测试成功获取并保存数据"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        # Mock 数据库
        pipeline.db = MagicMock()
        pipeline.db.has_today_data.return_value = False

        # Mock 数据获取管理器
        pipeline.fetcher_manager = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = False
        pipeline.fetcher_manager.get_daily_data.return_value = (mock_df, "akshare")

        # 执行
        success, error = pipeline.fetch_and_save_stock_data("000001")

        # 验证
        assert success is True
        assert error is None
        pipeline.db.has_today_data.assert_called_once()
        pipeline.fetcher_manager.get_daily_data.assert_called_once()
        pipeline.db.save_daily_data.assert_called_once()

    def test_fetch_data_already_exists(self, mock_config):
        """测试数据已存在时跳过获取（断点续传）"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        # Mock 数据库 - 已有今日数据
        pipeline.db = MagicMock()
        pipeline.db.has_today_data.return_value = True

        # Mock fetcher_manager 以支持断言
        pipeline.fetcher_manager = MagicMock()

        # 执行
        success, error = pipeline.fetch_and_save_stock_data("000001")

        # 验证 - 跳过获取
        assert success is True
        assert error is None
        pipeline.db.has_today_data.assert_called_once()
        pipeline.fetcher_manager.get_daily_data.assert_not_called()

    def test_fetch_data_force_refresh(self, mock_config):
        """测试强制刷新时重新获取数据"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        # Mock 数据库
        pipeline.db = MagicMock()
        pipeline.db.has_today_data.return_value = True  # 即使已有数据

        # Mock 数据获取管理器
        pipeline.fetcher_manager = MagicMock()
        mock_df = MagicMock()
        mock_df.empty = False
        pipeline.fetcher_manager.get_daily_data.return_value = (mock_df, "akshare")

        # 执行 - 强制刷新
        success, error = pipeline.fetch_and_save_stock_data("000001", force_refresh=True)

        # 验证 - 仍然获取数据
        assert success is True
        assert error is None
        pipeline.fetcher_manager.get_daily_data.assert_called_once()

    def test_fetch_data_empty_result(self, mock_config):
        """测试获取数据为空"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        # Mock 数据库
        pipeline.db = MagicMock()
        pipeline.db.has_today_data.return_value = False

        # Mock 数据获取管理器 - 返回空数据
        pipeline.fetcher_manager = MagicMock()
        pipeline.fetcher_manager.get_daily_data.return_value = (None, "akshare")

        # 执行
        success, error = pipeline.fetch_and_save_stock_data("000001")

        # 验证
        assert success is False
        assert error == "获取数据为空"

    def test_fetch_data_exception(self, mock_config):
        """测试获取数据时发生异常"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        # Mock 数据库
        pipeline.db = MagicMock()
        pipeline.db.has_today_data.return_value = False

        # Mock 数据获取管理器 - 抛出异常
        pipeline.fetcher_manager = MagicMock()
        pipeline.fetcher_manager.get_daily_data.side_effect = Exception("Network error")

        # 执行
        success, error = pipeline.fetch_and_save_stock_data("000001")

        # 验证
        assert success is False
        assert "获取/保存数据失败" in error


class TestPipelineAnalyze:
    """Pipeline 分析功能测试"""

    def test_analyze_stock_success(self, mock_config):
        """测试成功分析股票"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        # Mock 各组件
        pipeline.fetcher_manager = MagicMock()
        pipeline.fetcher_manager.get_realtime_quote.return_value = None
        pipeline.fetcher_manager.get_chip_distribution.return_value = None

        pipeline.db = MagicMock()
        pipeline.db.get_analysis_context.return_value = {
            "code": "000001",
            "stock_name": "平安银行",
            "date": "2024-01-01",
            "raw_data": [
                {"date": "2024-01-01", "close": 12.5, "volume": 1000}
            ],
        }

        pipeline.trend_analyzer = MagicMock()
        pipeline.trend_analyzer.analyze.return_value = MagicMock(
            trend_status=MagicMock(value="多头"),
            buy_signal=MagicMock(value="强烈买入"),
            signal_score=85,
            ma_alignment=True,
            trend_strength=0.75,
            bias_ma5=1.2,
            bias_ma10=0.8,
            volume_status=MagicMock(value="放量"),
            volume_trend="温和放量",
            signal_reasons=["MA多头排列"],
            risk_factors=["注意回调风险"],
        )

        pipeline.analyzer = MagicMock()
        mock_result = AnalysisResult(
            code="000001",
            name="平安银行",
            sentiment_score=75,
            trend_prediction="看多",
            operation_advice="买入",
        )
        pipeline.analyzer.analyze.return_value = mock_result

        pipeline.search_service = MagicMock()
        pipeline.search_service.is_available = False

        # 执行
        result = pipeline.analyze_stock("000001")

        # 验证
        assert result is not None
        assert result.code == "000001"
        assert result.sentiment_score == 75
        pipeline.analyzer.analyze.assert_called_once()

    def test_analyze_stock_no_context(self, mock_config):
        """测试无法获取历史数据时的分析"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        # Mock 各组件
        pipeline.fetcher_manager = MagicMock()
        pipeline.fetcher_manager.get_realtime_quote.return_value = None
        pipeline.fetcher_manager.get_chip_distribution.return_value = None

        pipeline.db = MagicMock()
        pipeline.db.get_analysis_context.return_value = None  # 无历史数据

        pipeline.trend_analyzer = MagicMock()

        pipeline.analyzer = MagicMock()
        mock_result = AnalysisResult(
            code="000001",
            name="股票000001",
            sentiment_score=50,
            trend_prediction="震荡",
            operation_advice="观望",
        )
        pipeline.analyzer.analyze.return_value = mock_result

        pipeline.search_service = MagicMock()
        pipeline.search_service.is_available = False

        # 执行
        result = pipeline.analyze_stock("000001")

        # 验证 - 仍然返回结果
        assert result is not None
        assert result.code == "000001"

    def test_analyze_stock_analyzer_returns_none(self, mock_config):
        """测试分析器返回 None"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        # Mock 各组件
        pipeline.fetcher_manager = MagicMock()
        pipeline.fetcher_manager.get_realtime_quote.return_value = None
        pipeline.fetcher_manager.get_chip_distribution.return_value = None

        pipeline.db = MagicMock()
        pipeline.db.get_analysis_context.return_value = {"code": "000001"}

        pipeline.trend_analyzer = MagicMock()

        pipeline.analyzer = MagicMock()
        pipeline.analyzer.analyze.return_value = None  # 分析失败

        pipeline.search_service = MagicMock()
        pipeline.search_service.is_available = False

        # 执行
        result = pipeline.analyze_stock("000001")

        # 验证
        assert result is None

    def test_analyze_stock_with_search_intelligence(self, mock_config):
        """测试带搜索情报的分析"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        # Mock 各组件
        pipeline.fetcher_manager = MagicMock()
        pipeline.fetcher_manager.get_realtime_quote.return_value = None
        pipeline.fetcher_manager.get_chip_distribution.return_value = None

        pipeline.db = MagicMock()
        pipeline.db.get_analysis_context.return_value = {"code": "000001"}

        pipeline.trend_analyzer = MagicMock()

        pipeline.analyzer = MagicMock()
        mock_result = AnalysisResult(
            code="000001",
            name="平安银行",
            sentiment_score=70,
            trend_prediction="看多",
            operation_advice="加仓",
        )
        pipeline.analyzer.analyze.return_value = mock_result

        pipeline.search_service = MagicMock()
        pipeline.search_service.is_available = True
        pipeline.search_service.search_comprehensive_intel.return_value = {
            "news": MagicMock(success=True, results=["业绩预增"])
        }
        pipeline.search_service.format_intel_report.return_value = "情报报告内容"

        # 执行
        result = pipeline.analyze_stock("000001")

        # 验证
        assert result is not None
        pipeline.search_service.search_comprehensive_intel.assert_called_once()


class TestPipelineNotify:
    """Pipeline 通知功能测试"""

    def test_send_notifications_success(self, mock_config):
        """测试成功发送通知"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        # 创建测试结果
        mock_result = AnalysisResult(
            code="000001",
            name="平安银行",
            sentiment_score=75,
            trend_prediction="看多",
            operation_advice="买入",
        )

        # Mock notifier
        pipeline.notifier = MagicMock()
        pipeline.notifier.is_available.return_value = True
        pipeline.notifier.get_available_channels.return_value = []
        pipeline.notifier.generate_dashboard_report.return_value = "仪表盘报告"
        pipeline.notifier.save_report_to_file.return_value = "/path/to/report.txt"
        pipeline.notifier.send_to_context.return_value = True

        # 执行
        pipeline._send_notifications([mock_result])

        # 验证
        pipeline.notifier.generate_dashboard_report.assert_called_once()
        pipeline.notifier.save_report_to_file.assert_called_once()
        pipeline.notifier.send_to_context.assert_called_once()

    def test_send_notifications_skip_push(self, mock_config):
        """测试跳过推送（单股推送模式）"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        mock_result = AnalysisResult(
            code="000001",
            name="平安银行",
            sentiment_score=75,
            trend_prediction="看多",
            operation_advice="买入",
        )

        # Mock notifier
        pipeline.notifier = MagicMock()
        pipeline.notifier.is_available.return_value = True
        pipeline.notifier.generate_dashboard_report.return_value = "仪表盘报告"
        pipeline.notifier.save_report_to_file.return_value = "/path/to/report.txt"

        # 执行 - 跳过推送
        pipeline._send_notifications([mock_result], skip_push=True)

        # 验证 - 只保存，不推送
        pipeline.notifier.save_report_to_file.assert_called_once()
        pipeline.notifier.send_to_context.assert_not_called()

    def test_send_notifications_not_available(self, mock_config):
        """测试通知渠道不可用"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        mock_result = AnalysisResult(
            code="000001",
            name="平安银行",
            sentiment_score=75,
            trend_prediction="看多",
            operation_advice="买入",
        )

        # Mock notifier - 不可用
        pipeline.notifier = MagicMock()
        pipeline.notifier.is_available.return_value = False
        pipeline.notifier.generate_dashboard_report.return_value = "仪表盘报告"
        pipeline.notifier.save_report_to_file.return_value = "/path/to/report.txt"

        # 执行
        pipeline._send_notifications([mock_result])

        # 验证 - 仍然保存，但不推送
        pipeline.notifier.save_report_to_file.assert_called_once()
        pipeline.notifier.send_to_context.assert_not_called()

    def test_send_notifications_with_wechat(self, mock_config):
        """测试企业微信通知"""
        from src.notification import NotificationChannel

        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        mock_result = AnalysisResult(
            code="000001",
            name="平安银行",
            sentiment_score=75,
            trend_prediction="看多",
            operation_advice="买入",
        )

        # Mock notifier
        pipeline.notifier = MagicMock()
        pipeline.notifier.is_available.return_value = True
        pipeline.notifier.get_available_channels.return_value = [NotificationChannel.WECHAT]
        pipeline.notifier.generate_dashboard_report.return_value = "仪表盘报告"
        pipeline.notifier.generate_wechat_dashboard.return_value = "企业微信内容"
        pipeline.notifier.save_report_to_file.return_value = "/path/to/report.txt"
        pipeline.notifier.send_to_context.return_value = False
        pipeline.notifier.send_to_wechat.return_value = True

        # 执行
        pipeline._send_notifications([mock_result])

        # 验证
        pipeline.notifier.send_to_wechat.assert_called_once()

    def test_send_notifications_empty_results(self, mock_config):
        """测试空结果列表"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        pipeline.notifier = MagicMock()
        pipeline.notifier.is_available.return_value = True
        pipeline.notifier.generate_dashboard_report.return_value = "空报告"
        pipeline.notifier.save_report_to_file.return_value = "/path/to/report.txt"

        # 执行 - 空列表
        pipeline._send_notifications([])

        # 验证 - 生成报告并尝试推送（is_available=True 时会发送）
        pipeline.notifier.generate_dashboard_report.assert_called_once_with([])
        pipeline.notifier.save_report_to_file.assert_called_once()
        pipeline.notifier.send_to_context.assert_called_once()

    def test_send_notifications_exception(self, mock_config):
        """测试发送通知时发生异常"""
        pipeline = StockAnalysisPipeline(config=mock_config, max_workers=2)

        mock_result = AnalysisResult(
            code="000001",
            name="平安银行",
            sentiment_score=75,
            trend_prediction="看多",
            operation_advice="买入",
        )

        # Mock notifier - 抛出异常
        pipeline.notifier = MagicMock()
        pipeline.notifier.is_available.return_value = True
        pipeline.notifier.generate_dashboard_report.side_effect = Exception("Report generation failed")

        # 执行 - 不应抛出异常
        pipeline._send_notifications([mock_result])
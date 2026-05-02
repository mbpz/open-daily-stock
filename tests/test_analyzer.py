# -*- coding: utf-8 -*-
"""AI Analyzer 测试"""
import pytest
from unittest.mock import MagicMock, patch

from src.analyzer import GeminiAnalyzer, AnalysisResult


class TestGeminiAnalyzer:
    """GeminiAnalyzer 测试类"""

    def test_analyzer_no_key(self):
        """无 API Key 时返回可用但失败的分析结果"""
        # 创建一个没有有效 API Key 的 analyzer
        with patch('src.analyzer.get_config') as mock_config:
            config = MagicMock()
            config.gemini_api_key = None
            config.openai_api_key = None
            config.openai_base_url = None
            config.openai_model = "gpt-4o-mini"
            config.gemini_model = "gemini-2.0-flash"
            config.gemini_model_fallback = "gemini-1.5-flash"
            config.gemini_temperature = 0.3
            config.gemini_max_retries = 3
            config.gemini_retry_delay = 2.0
            config.gemini_request_delay = 0.0
            config.openai_temperature = 0.3
            mock_config.return_value = config

            analyzer = GeminiAnalyzer(api_key=None)

            # analyzer.is_available() 应该返回 False
            assert analyzer.is_available() is False

    def test_analyzer_mock_response(self):
        """Mock LLM 响应解析"""
        # 创建一个有 API Key 但会被 mock 的 analyzer
        with patch('src.analyzer.get_config') as mock_config:
            config = MagicMock()
            config.gemini_api_key = "fake_key_for_testing"
            config.openai_api_key = None
            config.openai_base_url = None
            config.openai_model = "gpt-4o-mini"
            config.gemini_model = "gemini-2.0-flash"
            config.gemini_model_fallback = "gemini-1.5-flash"
            config.gemini_temperature = 0.3
            config.gemini_max_retries = 3
            config.gemini_retry_delay = 2.0
            config.gemini_request_delay = 0.0
            config.openai_temperature = 0.3
            mock_config.return_value = config

            # Mock _init_model 让它不真正初始化
            with patch.object(GeminiAnalyzer, '_init_model'):
                analyzer = GeminiAnalyzer(api_key="fake_key")

                # Mock _call_api_with_retry 返回预设的 JSON 响应
                mock_json_response = '''{
                    "sentiment_score": 75,
                    "trend_prediction": "看多",
                    "operation_advice": "买入",
                    "confidence_level": "高",
                    "dashboard": {
                        "core_conclusion": {
                            "one_sentence": "建议买入",
                            "signal_type": "🟢买入信号",
                            "position_advice": {"no_position": "买入", "has_position": "持有"}
                        }
                    },
                    "analysis_summary": "测试分析摘要",
                    "key_points": "测试买点",
                    "risk_warning": "风险提示",
                    "buy_reason": "测试理由"
                }'''

                with patch.object(analyzer, '_call_api_with_retry', return_value=mock_json_response):
                    # Mock is_available 返回 True（模拟 API 可用）
                    analyzer._model = MagicMock()

                    context = {
                        "code": "600519",
                        "stock_name": "贵州茅台",
                        "date": "2026-01-09",
                        "today": {
                            "close": 1680.0,
                            "open": 1670.0,
                            "high": 1690.0,
                            "low": 1660.0,
                            "pct_chg": 1.5,
                            "volume": 3500000,
                            "ma5": 1675.0,
                            "ma10": 1665.0,
                            "ma20": 1650.0,
                        }
                    }

                    result = analyzer.analyze(context)

                    assert isinstance(result, AnalysisResult)
                    assert result.code == "600519"
                    assert result.sentiment_score == 75
                    assert result.trend_prediction == "看多"
                    assert result.operation_advice == "买入"
                    assert result.confidence_level == "高"
                    assert "测试分析摘要" in result.analysis_summary

    def test_analyzer_parse_text_response(self):
        """测试纯文本响应解析"""
        # 创建一个 analyzer 实例
        with patch('src.analyzer.get_config') as mock_config:
            config = MagicMock()
            config.gemini_api_key = None
            config.openai_api_key = None
            config.openai_base_url = None
            config.gemini_model = "gemini-2.0-flash"
            config.gemini_model_fallback = "gemini-1.5-flash"
            config.gemini_temperature = 0.3
            config.gemini_max_retries = 3
            config.gemini_retry_delay = 2.0
            config.gemini_request_delay = 0.0
            config.openai_temperature = 0.3
            mock_config.return_value = config

            analyzer = GeminiAnalyzer(api_key=None)

            # 测试纯文本响应解析
            text_response = "经过分析，这只股票走势良好，建议买入。看多。利好因素包括业绩增长。"

            result = analyzer._parse_text_response(text_response, "600519", "贵州茅台")

            assert result.code == "600519"
            assert result.name == "贵州茅台"
            assert result.trend_prediction in ["看多", "震荡", "看空"]
            assert result.operation_advice in ["买入", "持有", "卖出"]

    def test_analyzer_format_volume(self):
        """测试成交量格式化"""
        with patch('src.analyzer.get_config') as mock_config:
            config = MagicMock()
            config.gemini_api_key = None
            config.openai_api_key = None
            config.openai_base_url = None
            config.gemini_model = "gemini-2.0-flash"
            config.gemini_model_fallback = "gemini-1.5-flash"
            config.gemini_temperature = 0.3
            config.gemini_max_retries = 3
            config.gemini_retry_delay = 2.0
            config.gemini_request_delay = 0.0
            config.openai_temperature = 0.3
            mock_config.return_value = config

            analyzer = GeminiAnalyzer(api_key=None)

            # 亿级别
            assert "亿" in analyzer._format_volume(150000000)
            # 万级别
            assert "万" in analyzer._format_volume(1500000)
            # 普通
            assert "股" in analyzer._format_volume(1500)
            # None
            assert analyzer._format_volume(None) == "N/A"

    def test_analyzer_format_amount(self):
        """测试成交额格式化"""
        with patch('src.analyzer.get_config') as mock_config:
            config = MagicMock()
            config.gemini_api_key = None
            config.openai_api_key = None
            config.openai_base_url = None
            config.gemini_model = "gemini-2.0-flash"
            config.gemini_model_fallback = "gemini-1.5-flash"
            config.gemini_temperature = 0.3
            config.gemini_max_retries = 3
            config.gemini_retry_delay = 2.0
            config.gemini_request_delay = 0.0
            config.openai_temperature = 0.3
            mock_config.return_value = config

            analyzer = GeminiAnalyzer(api_key=None)

            # 亿元级别
            assert "亿" in analyzer._format_amount(1500000000)
            # 万元级别
            assert "万" in analyzer._format_amount(1500000)
            # None
            assert analyzer._format_amount(None) == "N/A"

    def test_analysis_result_to_dict(self):
        """测试 AnalysisResult 转换为字典"""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            sentiment_score=75,
            trend_prediction="看多",
            operation_advice="买入",
            confidence_level="高",
            analysis_summary="测试摘要",
            key_points="买点1,买点2",
            risk_warning="风险提示",
            buy_reason="理由",
        )

        d = result.to_dict()

        assert d["code"] == "600519"
        assert d["name"] == "贵州茅台"
        assert d["sentiment_score"] == 75
        assert d["trend_prediction"] == "看多"
        assert d["operation_advice"] == "买入"
        assert d["success"] is True

    def test_analysis_result_get_emoji(self):
        """测试操作建议 emoji 映射"""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            sentiment_score=75,
            trend_prediction="看多",
            operation_advice="买入",
            confidence_level="高",
        )

        assert result.get_emoji() == "🟢"
        assert result.get_emoji() == "🟢"

        result.operation_advice = "持有"
        assert result.get_emoji() == "🟡"

        result.operation_advice = "卖出"
        assert result.get_emoji() == "🔴"

    def test_analysis_result_get_confidence_stars(self):
        """测试置信度星级"""
        result = AnalysisResult(
            code="600519",
            name="贵州茅台",
            sentiment_score=75,
            trend_prediction="看多",
            operation_advice="买入",
            confidence_level="高",
        )

        assert result.get_confidence_stars() == "⭐⭐⭐"

        result.confidence_level = "中"
        assert result.get_confidence_stars() == "⭐⭐"

        result.confidence_level = "低"
        assert result.get_confidence_stars() == "⭐"
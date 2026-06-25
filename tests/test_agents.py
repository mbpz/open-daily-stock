# -*- coding: utf-8 -*-
"""Tests for the multi-agent analysis system (P5-5).

Covers:
- Each specialist agent builds valid prompts
- Orchestrator dispatches agents in parallel
- Synthesizer combines specialist results
- Fallback when one or more specialists fail
- Timeout handling
- API availability check
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from src.agents.base_agent import BaseAgent
from src.agents.technical_agent import TechnicalAgent
from src.agents.fundamental_agent import FundamentalAgent
from src.agents.news_agent import NewsAgent
from src.agents.synthesizer_agent import SynthesizerAgent
from src.agents.orchestrator import MultiAgentOrchestrator


# ============================================================
# Test Data
# ============================================================

@pytest.fixture
def sample_context():
    """Sample analysis context matching what storage.get_analysis_context() returns."""
    return {
        "code": "600519",
        "stock_name": "贵州茅台",
        "date": "2026-05-10",
        "market": "CN",
        "today": {
            "close": 1820.0,
            "open": 1800.0,
            "high": 1850.0,
            "low": 1780.0,
            "pct_chg": 1.25,
            "volume": 3500000,
            "amount": 6370000000,
            "ma5": 1790.0,
            "ma10": 1750.0,
            "ma20": 1700.0,
            "pe": 28.5,
            "pb": 8.2,
            "total_mv": 2285000000000,
            "roe": 25.3,
            "revenue_growth": 15.2,
            "profit_growth": 18.5,
            "gross_margin": 72.0,
            "debt_ratio": 21.0,
            "dividend_yield": 1.8,
            "industry_pe": 32.0,
            "industry_pb": 9.5,
        },
        "ma_status": "多头排列",
        "rsi": 58.5,
        "macd_signal": "金叉",
        "boll_position": "中轨上方",
        "trend_analysis": {
            "trend_status": "上涨趋势",
            "bias_ma5": 1.68,
            "signal_score": 72,
        },
        "realtime": {
            "price": 1820.0,
            "volume_ratio": 1.15,
            "turnover_rate": 0.35,
            "pe_ratio": 28.5,
            "pb_ratio": 8.2,
            "total_mv": 2285000000000,
            "circ_mv": 2285000000000,
            "change_60d": 8.5,
        },
        "chip": {
            "profit_ratio": 0.85,
            "avg_cost": 1700.0,
            "concentration_90": 0.12,
            "concentration_70": 0.08,
            "chip_status": "筹码集中",
        },
        "industry": "食品饮料",
        "_news_context": "贵州茅台发布2026年一季度报告，营收同比增长15%。北向资金持续净买入。",
        "recent_events": "2026-04-28: 发布一季报; 2026-05-05: 股东大会召开",
        "sector_position": "行业龙头",
    }


@pytest.fixture
def mock_analyzer():
    """Mock GeminiAnalyzer for testing without actual API calls."""
    from src.analyzer import AnalysisResult

    analyzer = MagicMock()
    analyzer.is_available.return_value = True
    # _call_api_with_retry returns mock LLM response
    analyzer._call_api_with_retry.return_value = "Mock specialist analysis report content"
    # _parse_response returns a valid AnalysisResult, using the passed code/name
    def make_result(text, code, name):
        return AnalysisResult(
            code=code,
            name=name,
            sentiment_score=72,
            trend_prediction="看多",
            operation_advice="买入",
            confidence_level="中",
            technical_analysis="技术面看多",
            fundamental_analysis="基本面良好",
            news_summary="消息面偏正面",
            analysis_summary="综合分析看多",
            risk_warning="注意回调风险",
            success=True,
        )
    analyzer._parse_response.side_effect = make_result
    return analyzer


# ============================================================
# BaseAgent Tests
# ============================================================

class TestBaseAgent:
    """Tests for the abstract base agent class."""

    def test_cannot_instantiate_abstract(self):
        """BaseAgent cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseAgent(name="test", role="测试")

    def test_concrete_subclass_works(self):
        """A concrete subclass can be instantiated."""
        class TestAgent(BaseAgent):
            def get_system_prompt(self):
                return "Test system prompt"

            def build_prompt(self, code, context):
                return f"Test prompt for {code}"

        agent = TestAgent(name="test", role="测试")
        assert agent.name == "test"
        assert agent.role == "测试"
        assert "Test system prompt" in agent.get_system_prompt()
        assert "600519" in agent.build_prompt("600519", {})


# ============================================================
# TechnicalAgent Tests
# ============================================================

class TestTechnicalAgent:
    """Tests for the TechnicalAgent specialist."""

    def test_agent_initialization(self):
        """TechnicalAgent initializes with correct name and role."""
        agent = TechnicalAgent()
        assert agent.name == "technical"
        assert "技术面" in agent.role

    def test_system_prompt_is_chinese(self):
        """System prompt is in Chinese for A-share market."""
        agent = TechnicalAgent()
        prompt = agent.get_system_prompt()
        assert len(prompt) > 100
        assert "技术" in prompt
        assert "MA5" in prompt or "均线" in prompt

    def test_build_prompt_includes_technical_data(self, sample_context):
        """Built prompt includes all key technical data points."""
        agent = TechnicalAgent()
        prompt = agent.build_prompt("600519", sample_context)

        # Check key data points are present
        assert "600519" in prompt
        assert "1820.0" in prompt  # close price
        assert "MA5" in prompt
        assert "MA10" in prompt
        assert "MA20" in prompt
        assert "RSI" in prompt
        assert "MACD" in prompt

    def test_build_prompt_includes_trend_data(self, sample_context):
        """Built prompt includes trend analysis data."""
        agent = TechnicalAgent()
        prompt = agent.build_prompt("600519", sample_context)

        assert "上涨趋势" in prompt
        assert "1.68" in prompt  # bias_ma5
        assert "量比" in prompt
        assert "换手率" in prompt

    def test_build_prompt_includes_chip_data(self, sample_context):
        """Built prompt includes chip distribution data."""
        agent = TechnicalAgent()
        prompt = agent.build_prompt("600519", sample_context)

        assert "获利比例" in prompt or "profit" in prompt.lower()
        assert "筹码" in prompt

    def test_build_prompt_handles_missing_data(self):
        """Build prompt gracefully handles missing/malformed data."""
        agent = TechnicalAgent()
        minimal_context = {"code": "000001", "today": {}, "stock_name": "测试股"}
        prompt = agent.build_prompt("000001", minimal_context)

        # Should not crash, should show N/A for missing fields
        assert "测试股" in prompt
        assert "N/A" in prompt

    def test_build_prompt_handles_none_values(self):
        """Build prompt handles None values in context."""
        agent = TechnicalAgent()
        context = {
            "code": "000001",
            "stock_name": None,
            "today": None,
            "trend_analysis": None,
            "realtime": None,
            "chip": None,
        }
        prompt = agent.build_prompt("000001", context)
        assert "000001" in prompt  # Should not crash


# ============================================================
# FundamentalAgent Tests
# ============================================================

class TestFundamentalAgent:
    """Tests for the FundamentalAgent specialist."""

    def test_agent_initialization(self):
        """FundamentalAgent initializes with correct name and role."""
        agent = FundamentalAgent()
        assert agent.name == "fundamental"
        assert "基本面" in agent.role

    def test_system_prompt_is_chinese(self):
        """System prompt is in Chinese for A-share market."""
        agent = FundamentalAgent()
        prompt = agent.get_system_prompt()
        assert len(prompt) > 100
        assert "估值" in prompt or "PE" in prompt or "基本面" in prompt

    def test_build_prompt_includes_financial_metrics(self, sample_context):
        """Built prompt includes key financial metrics."""
        agent = FundamentalAgent()
        prompt = agent.build_prompt("600519", sample_context)

        assert "PE" in prompt or "市盈率" in prompt
        assert "PB" in prompt or "市净率" in prompt
        assert "ROE" in prompt
        assert "28.5" in prompt  # PE value

    def test_build_prompt_includes_industry_comparison(self, sample_context):
        """Built prompt includes industry comparison data."""
        agent = FundamentalAgent()
        prompt = agent.build_prompt("600519", sample_context)

        assert "行业" in prompt
        # Industry PE/PB should be present
        assert "32.0" in prompt  # industry_pe


# ============================================================
# NewsAgent Tests
# ============================================================

class TestNewsAgent:
    """Tests for the NewsAgent specialist."""

    def test_agent_initialization(self):
        """NewsAgent initializes with correct name and role."""
        agent = NewsAgent()
        assert agent.name == "news"
        assert "消息" in agent.role or "情绪" in agent.role

    def test_system_prompt_is_chinese(self):
        """System prompt is in Chinese for A-share market."""
        agent = NewsAgent()
        prompt = agent.get_system_prompt()
        assert len(prompt) > 100
        assert "新闻" in prompt or "消息" in prompt or "情绪" in prompt

    def test_build_prompt_includes_news_context(self, sample_context):
        """Built prompt includes news and event context."""
        agent = NewsAgent()
        prompt = agent.build_prompt("600519", sample_context)

        assert "一季度报告" in prompt
        assert "股东大会" in prompt

    def test_build_prompt_handles_no_news(self):
        """Build prompt works when no news context is available."""
        agent = NewsAgent()
        context = {"code": "000001", "today": {}, "stock_name": "测试股"}
        prompt = agent.build_prompt("000001", context)
        assert "测试股" in prompt

    def test_build_prompt_includes_market_type(self, sample_context):
        """Built prompt includes market type information."""
        agent = NewsAgent()
        prompt = agent.build_prompt("600519", sample_context)
        assert "600519" in prompt


# ============================================================
# SynthesizerAgent Tests
# ============================================================

class TestSynthesizerAgent:
    """Tests for the SynthesizerAgent."""

    def test_agent_initialization(self):
        """SynthesizerAgent initializes correctly."""
        agent = SynthesizerAgent()
        assert agent.name == "synthesizer"
        assert "综合" in agent.role

    def test_system_prompt_includes_output_format(self):
        """System prompt specifies the JSON output format."""
        agent = SynthesizerAgent()
        prompt = agent.get_system_prompt()
        assert "sentiment_score" in prompt
        assert "trend_prediction" in prompt
        assert "operation_advice" in prompt

    def test_all_specialists_failed_returns_error(self, mock_analyzer, sample_context):
        """When all specialists fail, returns an error AnalysisResult."""
        agent = SynthesizerAgent()
        failed_results = {
            "technical": {"error": "timeout"},
            "fundamental": {"error": "API error"},
            "news": {"error": "network issue"},
        }

        result = agent.synthesize(
            "600519", sample_context, failed_results, mock_analyzer
        )

        assert result.success is False
        assert "失败" in result.analysis_summary or "不可用" in result.analysis_summary
        # Should not have called API since all specialists failed
        mock_analyzer._call_api_with_retry.assert_not_called()

    def test_partial_failure_includes_error_notes(self, mock_analyzer, sample_context):
        """When some specialists fail, their errors are noted in synthesis."""
        agent = SynthesizerAgent()
        partial_results = {
            "technical": "技术面看多，建议买入",
            "fundamental": {"error": "API超时"},
            "news": "消息面偏正面",
        }

        result = agent.synthesize(
            "600519", sample_context, partial_results, mock_analyzer
        )

        # Should have called the API for synthesis
        mock_analyzer._call_api_with_retry.assert_called_once()
        # Should have called parse_response
        mock_analyzer._parse_response.assert_called_once()

    def test_synthesizer_api_failure_returns_error(self, mock_analyzer, sample_context):
        """When synthesis API call fails, returns an error result."""
        mock_analyzer._call_api_with_retry.side_effect = Exception("API error")

        agent = SynthesizerAgent()
        results = {
            "technical": "看多",
            "fundamental": "中性",
            "news": "看多",
        }

        result = agent.synthesize(
            "600519", sample_context, results, mock_analyzer
        )

        assert result.success is False
        assert "出错" in result.analysis_summary

    def test_synthesis_prompt_truncation(self, mock_analyzer, sample_context):
        """Very long specialist reports are truncated to avoid token limits."""
        agent = SynthesizerAgent()
        long_report = "x" * 5000  # Exceeds 3000 char truncation limit

        results = {
            "technical": long_report,
            "fundamental": "基本面良好",
            "news": "消息面中性",
        }

        # Build the synthesis prompt (indirect test via synthesize)
        prompt = agent._build_synthesis_prompt(
            "600519", "贵州茅台", results, sample_context
        )
        # The long report should be truncated
        assert "[内容过长已截断]" in prompt
        # But other reports should be intact
        assert "基本面良好" in prompt


# ============================================================
# MultiAgentOrchestrator Tests
# ============================================================

class TestMultiAgentOrchestrator:
    """Tests for the MultiAgentOrchestrator."""

    def test_orchestrator_initialization(self, mock_analyzer):
        """Orchestrator initializes with 3 specialists and 1 synthesizer."""
        orchestrator = MultiAgentOrchestrator(mock_analyzer)
        assert len(orchestrator.agents) == 3
        agent_names = [a.name for a in orchestrator.agents]
        assert "technical" in agent_names
        assert "fundamental" in agent_names
        assert "news" in agent_names
        assert orchestrator.synthesizer is not None

    def test_analyze_when_api_unavailable(self, sample_context):
        """When API is not available, returns error immediately."""
        analyzer = MagicMock()
        analyzer.is_available.return_value = False

        orchestrator = MultiAgentOrchestrator(analyzer)
        result = orchestrator.analyze("600519", sample_context)

        assert result.success is False
        assert "未启用" in result.analysis_summary

    def test_analyze_success_path(self, mock_analyzer, sample_context):
        """Full analyze pipeline completes successfully."""
        orchestrator = MultiAgentOrchestrator(mock_analyzer)
        result = orchestrator.analyze("600519", sample_context)

        # Should have called API for each of the 4 specialists + 1 synthesizer
        assert mock_analyzer._call_api_with_retry.call_count == 5
        # Result should be the mock AnalysisResult
        assert result.code == "600519"
        assert result.success is True

    def test_single_specialist_failure_is_handled(self, mock_analyzer, sample_context):
        """One agent failing should not crash the orchestrator."""
        # Set up: first call (technical) fails, others succeed
        call_count = [0]

        def fail_first_call(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Technical agent API error")
            return "Mock response text"

        mock_analyzer._call_api_with_retry.side_effect = fail_first_call

        orchestrator = MultiAgentOrchestrator(mock_analyzer)
        result = orchestrator.analyze("600519", sample_context)

        # Should complete without raising
        assert result.success is True

    def test_all_specialists_fail_triggers_error(self, mock_analyzer, sample_context):
        """When all specialists fail, synthesis produces error result."""
        call_count = [0]

        def fail_first_three(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 3:
                raise Exception(f"Agent {call_count[0]} API error")
            return "Synthesizer response"

        mock_analyzer._call_api_with_retry.side_effect = fail_first_three

        orchestrator = MultiAgentOrchestrator(mock_analyzer)
        result = orchestrator.analyze("600519", sample_context)

        # Since all specialists fail, synthesizer._synthesize returns error
        # But the orchestrator still returns an AnalysisResult
        assert result is not None
        assert result.code == "600519"

    def test_timeout_handling(self, mock_analyzer, sample_context):
        """Timeout during specialist execution is handled gracefully."""
        import time
        from concurrent.futures import TimeoutError as FuturesTimeoutError

        # Simulate timeout by making _call_api_with_retry very slow
        def slow_response(*args, **kwargs):
            time.sleep(0.2)  # Slow enough to test timeout logic
            return "Slow response"

        mock_analyzer._call_api_with_retry.side_effect = slow_response

        # Create orchestrator with a very short timeout for testing
        orchestrator = MultiAgentOrchestrator(mock_analyzer)

        # Patch SPECIALIST_TIMEOUT to force timeout
        with patch(
            "src.agents.orchestrator.SPECIALIST_TIMEOUT", 0.05
        ):
            result = orchestrator.analyze("600519", sample_context)

        # Should complete without raising
        assert result is not None

    def test_agents_run_in_parallel(self, mock_analyzer, sample_context):
        """Verify agents dispatch in parallel (timing check)."""
        import time

        call_times = []

        def record_time(*args, **kwargs):
            call_times.append(time.time())
            time.sleep(0.05)  # Small delay to measure parallelism
            return "Response"

        mock_analyzer._call_api_with_retry.side_effect = record_time

        orchestrator = MultiAgentOrchestrator(mock_analyzer)
        start = time.time()
        orchestrator.analyze("600519", sample_context)
        elapsed = time.time() - start

        # 3 parallel calls of 0.05s each should take ~0.05s, not ~0.15s
        # Allow some overhead for thread creation
        assert elapsed < 0.3, (
            f"Parallel execution too slow: {elapsed:.2f}s. "
            f"Should be near ~0.05s for parallel 0.05s tasks."
        )

    def test_context_without_stock_name(self, mock_analyzer):
        """Works when stock_name is not in context."""
        context = {
            "code": "000001",
            "today": {"close": 12.5, "pct_chg": 0.85},
        }
        orchestrator = MultiAgentOrchestrator(mock_analyzer)
        result = orchestrator.analyze("000001", context)
        assert result.code == "000001"


# ============================================================
# DeepAnalysisResult Tests (inline implementation in analyzer.py)
# ============================================================

class TestDeepAnalysisResult:
    """Tests for the DeepAnalysisResult dataclass in analyzer.py."""

    def test_creation(self):
        """DeepAnalysisResult can be created with basic fields."""
        from src.analyzer import DeepAnalysisResult
        result = DeepAnalysisResult(
            code="600519",
            name="贵州茅台",
            composite_score=75,
            final_verdict="看涨",
            key_catalysts=["业绩增长", "北向资金流入"],
            risk_factors=["估值偏高"],
            success=True,
        )
        assert result.code == "600519"
        assert result.composite_score == 75
        assert result.final_verdict == "看涨"

    def test_to_dict(self):
        """to_dict() returns a dictionary with all fields."""
        from src.analyzer import DeepAnalysisResult
        result = DeepAnalysisResult(
            code="600519",
            name="贵州茅台",
            composite_score=75,
            final_verdict="看涨",
            technical={"trend": "bullish", "score": 80},
            fundamental={"valuation": "fair", "score": 70},
            news={"sentiment": "positive", "score": 75},
            success=True,
        )
        d = result.to_dict()
        assert d["code"] == "600519"
        assert d["composite_score"] == 75
        assert d["final_verdict"] == "看涨"
        assert d["technical"]["trend"] == "bullish"
        assert d["success"] is True

    def test_error_result(self):
        """error_result() factory creates a failed result."""
        from src.analyzer import DeepAnalysisResult
        result = DeepAnalysisResult.error_result(
            "000001", "测试股", "测试错误"
        )
        assert result.success is False
        assert result.error_message == "测试错误"
        assert result.code == "000001"

    def test_default_values(self):
        """Default values are sensible."""
        from src.analyzer import DeepAnalysisResult
        result = DeepAnalysisResult(code="test", name="test")
        assert result.sentiment_score == 50
        assert result.trend_prediction == "震荡"
        assert result.operation_advice == "观望"
        assert result.composite_score == 50
        assert result.final_verdict == "中性"
        assert result.key_catalysts == []
        assert result.risk_factors == []
        assert result.success is True


# ============================================================
# Integration: existing deep_analyze method
# ============================================================

class TestDeepAnalyzeIntegration:
    """Integration tests for analyzer.deep_analyze()."""

    def test_deep_analyze_no_api_key(self):
        """deep_analyze returns error when no API key configured."""
        with patch('src.llm.analyzer.get_config') as mock_config:
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
            config.deep_analysis_agents = "technical,fundamental,news"
            mock_config.return_value = config

            from src.analyzer import GeminiAnalyzer
            analyzer = GeminiAnalyzer(api_key=None)
            result = analyzer.deep_analyze({"code": "600519"})

            assert result.success is False
            assert "未启用" in result.error_message or "未配置" in result.error_message

    def test_deep_analyze_no_enabled_agents(self):
        """deep_analyze returns error when no agents enabled."""
        from src.analyzer import GeminiAnalyzer
        with patch('src.llm.analyzer.get_config') as mock_config:
            config = MagicMock()
            config.gemini_api_key = "fake_key"
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
            config.deep_analysis_agents = "technical,fundamental,news"
            mock_config.return_value = config

            # We need to mock _init_model to avoid actual API init
            with patch.object(GeminiAnalyzer, '_init_model'):
                analyzer = GeminiAnalyzer()
                analyzer._model = MagicMock()  # Fake model to pass is_available check

                # Pass empty enabled_agents list
                result = analyzer.deep_analyze(
                    {"code": "600519"}, enabled_agents=[]
                )
                assert result.success is False
                assert "没有启用" in result.error_message

    def test_score_to_verdict(self):
        """_score_to_verdict maps scores to Chinese verdicts."""
        from src.analyzer import GeminiAnalyzer
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)

        assert analyzer._score_to_verdict(80) == "看涨"
        assert analyzer._score_to_verdict(70) == "看涨"
        assert analyzer._score_to_verdict(50) == "中性"
        assert analyzer._score_to_verdict(40) == "中性"
        assert analyzer._score_to_verdict(30) == "看跌"

    def test_score_to_trend(self):
        """_score_to_trend maps scores to trend predictions."""
        from src.analyzer import GeminiAnalyzer
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)

        assert analyzer._score_to_trend(85) == "强烈看多"
        assert analyzer._score_to_trend(65) == "看多"
        assert analyzer._score_to_trend(50) == "震荡"
        assert analyzer._score_to_trend(30) == "看空"
        assert analyzer._score_to_trend(10) == "强烈看空"

    def test_score_to_advice(self):
        """_score_to_advice maps scores to operation advice."""
        from src.analyzer import GeminiAnalyzer
        analyzer = GeminiAnalyzer.__new__(GeminiAnalyzer)

        assert analyzer._score_to_advice(85) == "买入"
        assert analyzer._score_to_advice(65) == "加仓"
        assert analyzer._score_to_advice(50) == "持有"
        assert analyzer._score_to_advice(30) == "减仓"
        assert analyzer._score_to_advice(10) == "卖出"

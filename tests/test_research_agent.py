# -*- coding: utf-8 -*-
"""P5-9: Agentic Research Mode tests.

Tests ResearchAgent REPL loop, tool execution, and DataService integration.
"""

import pytest
import json
import time
from unittest.mock import patch, MagicMock

from src.agents.research_agent import (
    ResearchAgent, ResearchAction, ResearchStep, ResearchReport,
    research_stock,
)


class TestResearchAction:
    """Test ResearchAction enum."""

    def test_all_actions_defined(self):
        assert ResearchAction.SEARCH_NEWS.value == "search_news"
        assert ResearchAction.RAG_SEARCH.value == "rag_search"
        assert ResearchAction.GET_KLINE.value == "get_kline"
        assert ResearchAction.GET_FINANCIALS.value == "get_financials"
        assert ResearchAction.GET_INSTITUTIONAL.value == "get_institutional"
        assert ResearchAction.ANALYZE_BASIC.value == "analyze_basic"
        assert ResearchAction.GIVE_REPORT.value == "give_report"


class TestResearchStep:
    """Test ResearchStep dataclass."""

    def test_research_step_creation(self):
        step = ResearchStep(
            iteration=1,
            thinking="First, search for news",
            action="search_news",
            tool_input={"query": "600519"},
            tool_output={"success": True, "results": []},
            observation="No news found",
        )
        assert step.iteration == 1
        assert step.thinking == "First, search for news"
        assert step.action == "search_news"
        assert step.is_final is False

    def test_research_step_is_final_flag(self):
        step = ResearchStep(
            iteration=2,
            thinking="Enough info, generating report",
            action="give_report",
            tool_input={},
            tool_output={},
            observation="Final step",
            is_final=True,
        )
        assert step.is_final is True


class TestResearchReport:
    """Test ResearchReport dataclass."""

    def test_research_report_creation(self):
        steps = [
            ResearchStep(
                iteration=1,
                thinking="Search news",
                action="search_news",
                tool_input={"query": "600519"},
                tool_output={"success": True},
                observation="Found 3 articles",
            ),
        ]
        report = ResearchReport(
            code="600519",
            topic="贵州茅台投资价值分析",
            steps=steps,
            final_report="# 分析报告...",
            tool_calls=1,
            duration_seconds=2.5,
        )
        assert report.code == "600519"
        assert report.topic == "贵州茅台投资价值分析"
        assert len(report.steps) == 1
        assert report.tool_calls == 1
        assert report.duration_seconds == 2.5

    def test_research_report_default_timestamp(self):
        report = ResearchReport(
            code="000001",
            topic="测试",
            steps=[],
            final_report="No data",
            tool_calls=0,
            duration_seconds=0.0,
        )
        assert report.timestamp is not None
        assert len(report.timestamp) > 0


class TestResearchAgentMockDecide:
    """Test ResearchAgent with mock decision (no LLM)."""

    def test_agent_initialization(self):
        agent = ResearchAgent(max_iterations=3)
        assert agent.max_iterations == 3
        assert agent._llm is None

    def test_research_empty_loop(self):
        """Agent with max_iterations=0 does nothing."""
        agent = ResearchAgent(max_iterations=0)
        report = agent.research("600519", "测试")
        assert report.code == "600519"
        assert len(report.steps) == 0

    def test_research_progression(self):
        """Mock decisions progress through all 4 tool calls then give_report."""
        agent = ResearchAgent(max_iterations=5)
        report = agent.research("600519", "测试 topic")

        # Should have: search_news, rag_search, get_kline, get_financials, then give_report
        # But give_report doesn't produce a step (it's the break condition)
        # So we expect at least 4 steps
        assert len(report.steps) >= 4, f"Expected >=4 steps, got {len(report.steps)}"

        # Verify step sequence
        actions = [s.action for s in report.steps]
        assert actions[0] == "search_news"
        assert actions[1] == "rag_search"
        assert actions[2] == "get_kline"
        assert actions[3] == "get_financials"

    def test_research_stops_at_max_iterations(self):
        """Agent stops after max_iterations even if still has tools."""
        agent = ResearchAgent(max_iterations=2)
        report = agent.research("600519", "测试")

        assert report.tool_calls <= 2
        assert len(report.steps) <= 2

    def test_research_accumulates_context(self):
        """Each iteration's observation gets accumulated."""
        agent = ResearchAgent(max_iterations=3)
        report = agent.research("600519", "分析")

        assert len(report.steps) == 3

        # Verify each step has required fields
        for step in report.steps:
            assert step.iteration > 0
            assert step.thinking
            assert step.action
            assert step.observation is not None


class TestMockDecide:
    """Test the mock decision logic directly."""

    def test_mock_first_iteration(self):
        agent = ResearchAgent(max_iterations=3)
        decision = agent._mock_decide(
            "600519", "测试",
            {"code": "600519", "tool_results": []},
            iteration=1,
        )
        assert decision["action"] == "search_news"
        assert "input" in decision

    def test_mock_second_iteration(self):
        agent = ResearchAgent(max_iterations=3)
        decision = agent._mock_decide(
            "600519", "测试",
            {"code": "600519", "tool_results": [{"tool": "search_news"}]},
            iteration=2,
        )
        assert decision["action"] == "rag_search"

    def test_mock_third_iteration(self):
        agent = ResearchAgent(max_iterations=3)
        decision = agent._mock_decide(
            "600519", "测试",
            {"code": "600519", "tool_results": [
                {"tool": "search_news"},
                {"tool": "rag_search"},
            ]},
            iteration=3,
        )
        assert decision["action"] == "get_kline"

    def test_mock_later_iterations_give_report(self):
        agent = ResearchAgent(max_iterations=5)
        decision = agent._mock_decide(
            "600519", "测试",
            {"code": "600519", "tool_results": [
                {"tool": "search_news"},
                {"tool": "rag_search"},
                {"tool": "get_kline"},
                {"tool": "get_financials"},
            ]},
            iteration=5,
        )
        assert decision["action"] == ResearchAction.GIVE_REPORT.value


class TestToolExecution:
    """Test tool execution in ResearchAgent."""

    def test_extract_observation_from_search_news(self):
        agent = ResearchAgent()
        output = {
            "success": True,
            "results": [
                {"title": "茅台业绩增长", "snippet": "...", "source": "东方财富"},
            ]
        }
        obs = agent._extract_observation("search_news", output)
        assert "茅台业绩增长" in obs or "找到" in obs

    def test_extract_observation_no_results(self):
        agent = ResearchAgent()
        output = {"success": True, "results": []}
        obs = agent._extract_observation("search_news", output)
        assert "未找到" in obs or "0" in obs

    def test_extract_observation_error(self):
        agent = ResearchAgent()
        output = {"error": "Network error"}
        obs = agent._extract_observation("search_news", output)
        assert "错误" in obs

    def test_extract_observation_rag_search(self):
        agent = ResearchAgent()
        output = {"success": True, "context": "历史分析...贵州茅台..."}
        obs = agent._extract_observation("rag_search", output)
        assert "历史分析" in obs or "上下文" in obs

    def test_extract_observation_kline(self):
        agent = ResearchAgent()
        output = {"status": "ok", "klines": [{"close": 1800}] * 100}
        obs = agent._extract_observation("get_kline", output)
        assert "K线" in obs

    def test_extract_observation_financials(self):
        agent = ResearchAgent()
        output = {"status": "ok", "message": "财务数据获取成功"}
        obs = agent._extract_observation("get_financials", output)
        assert "财务" in obs

    def test_extract_observation_institutional(self):
        agent = ResearchAgent()
        output = {"status": "ok"}
        obs = agent._extract_observation("get_institutional", output)
        assert "机构" in obs


class TestFinalReport:
    """Test final report generation."""

    def test_generate_final_report_empty_steps(self):
        agent = ResearchAgent()
        report_text = agent._generate_final_report("600519", "测试", [])
        assert "600519" in report_text
        assert "测试" in report_text

    def test_generate_final_report_with_steps(self):
        agent = ResearchAgent()
        steps = [
            ResearchStep(
                iteration=1,
                thinking="搜索新闻",
                action="search_news",
                tool_input={"query": "600519"},
                tool_output={"success": True, "results": []},
                observation="未找到相关新闻",
            ),
            ResearchStep(
                iteration=2,
                thinking="查看历史",
                action="rag_search",
                tool_input={"code": "600519"},
                tool_output={"success": False},
                observation="知识库中无相关记录",
                is_final=True,
            ),
        ]
        report_text = agent._generate_final_report("600519", "贵州茅台分析", steps)
        assert "# 600519 研究报告" in report_text
        assert "贵州茅台分析" in report_text
        assert "第 1 轮" in report_text
        assert "第 2 轮" in report_text
        assert "搜索新闻" in report_text
        assert "查看历史" in report_text


class TestSummarizePriorResults:
    """Test prior results summarization for LLM prompts."""

    def test_empty_prior_results(self):
        agent = ResearchAgent()
        summary = agent._summarize_prior_results([])
        assert "尚未收集" in summary

    def test_single_prior_result(self):
        agent = ResearchAgent()
        summary = agent._summarize_prior_results([
            {"tool": "search_news", "observation": "找到3条新闻"}
        ])
        assert "1. [search_news]" in summary
        assert "找到3条新闻" in summary

    def test_multiple_prior_results(self):
        agent = ResearchAgent()
        summary = agent._summarize_prior_results([
            {"tool": "search_news", "observation": "找到新闻"},
            {"tool": "rag_search", "observation": "有历史记录"},
            {"tool": "get_kline", "observation": "K线数据"},
        ])
        assert "[search_news]" in summary
        assert "[rag_search]" in summary
        assert "[get_kline]" in summary


class TestResearchStockFunction:
    """Test the convenience function."""

    def test_research_stock_convenience(self):
        agent = ResearchAgent(max_iterations=1)
        report = research_stock("600519", "测试")
        assert report.code == "600519"
        assert report.topic == "测试"


class TestDataServiceIntegration:
    """Test DataService research action handler."""

    def test_research_action_registered(self):
        from src.data_service import DataService
        svc = DataService()
        assert "research" in svc._actions
        assert svc._actions["research"] == "_handle_research"

    def test_research_missing_params(self):
        from src.data_service import DataService
        svc = DataService()
        # Missing both code and topic
        result = svc._handle_research({"action": "research"})
        assert result["status"] == "error"
        assert "缺少" in result["message"]

    def test_research_missing_code(self):
        from src.data_service import DataService
        svc = DataService()
        result = svc._handle_research({"action": "research", "topic": "分析"})
        assert result["status"] == "error"
        assert "缺少" in result["message"]

    def test_research_missing_topic(self):
        from src.data_service import DataService
        svc = DataService()
        result = svc._handle_research({"action": "research", "code": "600519"})
        assert result["status"] == "error"
        assert "缺少" in result["message"]

    def test_research_with_valid_params(self):
        from src.data_service import DataService
        from src.agents.research_agent import ResearchAgent

        agent = ResearchAgent(max_iterations=1)
        with patch.object(ResearchAgent, 'research', return_value=MagicMock(
            code="600519",
            topic="测试",
            steps=[],
            tool_calls=0,
            duration_seconds=0.5,
            final_report="# 测试报告",
            timestamp="2026-05-11 12:00:00",
        )) as mock_research:
            svc = DataService()
            result = svc._handle_research({
                "action": "research",
                "code": "600519",
                "topic": "测试",
                "max_iterations": 1,
            })

            assert result["status"] == "ok"
            assert result["code"] == "600519"
            mock_research.assert_called_once()
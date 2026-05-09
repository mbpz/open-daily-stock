# -*- coding: utf-8 -*-
"""Tests for A-share CN prompt templates."""
import pytest

from src.cn_prompts import (
    CNPromptBuilder,
    CN_ANALYST_SYSTEM_PROMPT,
    CN_FACTOR_ANALYSIS_TEMPLATE,
    CN_SECTOR_ROTATION_PROMPT,
    CN_INSTITUTIONAL_PROMPT,
    CN_MACRO_PROMPT,
)


class TestCNPromptBuilder:
    """Tests for CNPromptBuilder."""

    def test_build_analysis_prompt_contains_code(self):
        """CN analysis prompt includes the stock code."""
        context = {
            "code": "600519",
            "stock_name": "贵州茅台",
            "today": {
                "close": 1800.50,
                "pct_chg": 2.35,
                "volume": 12345678,
                "pe": 35.2,
                "pb": 9.8,
                "total_mv": "2.26万亿",
                "ma5": 1780.00,
                "ma10": 1750.00,
                "ma20": 1700.00,
            },
            "ma_status": "多头排列",
            "rsi": 62.5,
            "macd_signal": "金叉",
        }
        prompt = CNPromptBuilder.build_analysis_prompt(context)
        assert "600519" in prompt
        assert "贵州茅台" in prompt
        assert "A股深度分析" in prompt

    def test_build_analysis_prompt_handles_missing_data(self):
        """CN analysis prompt handles context with minimal/missing data gracefully."""
        context = {
            "code": "000001",
            "today": {},
        }
        prompt = CNPromptBuilder.build_analysis_prompt(context)
        assert "000001" in prompt
        assert "N/A" in prompt  # Missing fields use "N/A" placeholder
        assert "A股深度分析" in prompt
        # Should not raise any exception

    def test_build_analysis_prompt_fallback_stock_name(self):
        """When stock_name is missing, falls back to code."""
        context = {
            "code": "002594",
            "today": {},
        }
        prompt = CNPromptBuilder.build_analysis_prompt(context)
        # stock_name falls back to code when missing
        assert "002594" in prompt

    def test_build_analysis_prompt_with_optional_contexts(self):
        """CN prompt includes provided institutional, news, and industry contexts."""
        context = {
            "code": "300750",
            "today": {},
        }
        prompt = CNPromptBuilder.build_analysis_prompt(
            context,
            inst_context="机构增持500万股",
            news_context="发布业绩预告",
            industry_context="新能源汽车行业景气度高",
        )
        assert "机构增持500万股" in prompt
        assert "发布业绩预告" in prompt
        assert "新能源汽车行业景气度高" in prompt

    def test_build_analysis_prompt_default_fallback_contexts(self):
        """When optional contexts are empty, placeholders are used."""
        context = {
            "code": "600036",
            "today": {},
        }
        prompt = CNPromptBuilder.build_analysis_prompt(context)
        assert "无机构动向数据" in prompt
        assert "无行业对比数据" in prompt
        assert "无近期新闻" in prompt


class TestVerdictBadge:
    """Tests for CNPromptBuilder.build_verdict_badge parsing."""

    def test_verdict_badge_bullish_text(self):
        """Bullish Chinese keywords produce bullish verdict."""
        result = CNPromptBuilder.build_verdict_badge(
            {"output": "综合判断：看涨，目标价200元"}
        )
        assert result["verdict"] == "bullish"

    def test_verdict_badge_bearish_text(self):
        """Bearish Chinese keywords produce bearish verdict."""
        result = CNPromptBuilder.build_verdict_badge(
            {"output": "建议卖出，趋势走弱"}
        )
        assert result["verdict"] == "bearish"

    def test_verdict_badge_neutral_default(self):
        """No directional keywords produce neutral verdict."""
        result = CNPromptBuilder.build_verdict_badge(
            {"output": "市场目前横盘整理，方向不明"}
        )
        assert result["verdict"] == "neutral"

    def test_verdict_badge_bullish_english(self):
        """English bullish keywords also work."""
        result = CNPromptBuilder.build_verdict_badge(
            {"output": "Bullish signal on volume breakout"}
        )
        assert result["verdict"] == "bullish"

    def test_verdict_badge_star_score_extraction(self):
        """Star rating is extracted from text like '3星'."""
        result = CNPromptBuilder.build_verdict_badge(
            {"output": "综合评分：4星，建议买入"}
        )
        assert result["score"] == 4

    def test_verdict_badge_star_score_default(self):
        """Missing star rating defaults to 3."""
        result = CNPromptBuilder.build_verdict_badge(
            {"output": "没有星级评分"}
        )
        assert result["score"] == 3

    def test_verdict_badge_confidence_default(self):
        """Confidence defaults to 70."""
        result = CNPromptBuilder.build_verdict_badge({"output": "any text"})
        assert result["confidence"] == 70


class TestSummaryBulletpoints:
    """Tests for CNPromptBuilder.build_summary_bulletpoints."""

    def test_build_summary_bulletpoints(self):
        """Extracts bullet points from text."""
        text = """分析结果：
- 关键技术位获得支撑
- 机构资金持续流入
* 行业景气度上升
• 短期回调不改中期趋势
1. 建议逢低布局
2. 止损位设在50元下方
普通文本内容
"""
        bullets = CNPromptBuilder.build_summary_bulletpoints(text)
        assert len(bullets) == 5  # Max 5
        assert "关键技术位获得支撑" in bullets
        assert "机构资金持续流入" in bullets

    def test_build_summary_bulletpoints_empty(self):
        """Empty input returns empty list."""
        bullets = CNPromptBuilder.build_summary_bulletpoints("")
        assert bullets == []

    def test_build_summary_bulletpoints_no_bullets(self):
        """Text without bullets returns empty list."""
        bullets = CNPromptBuilder.build_summary_bulletpoints("这是一段普通文本没有任何列表项。")
        assert bullets == []


class TestPromptConstants:
    """Verify prompt template constants are well-formed."""

    def test_system_prompt_is_non_empty(self):
        """CN system prompt is a non-empty Chinese string."""
        assert len(CN_ANALYST_SYSTEM_PROMPT) > 50
        assert "A股" in CN_ANALYST_SYSTEM_PROMPT

    def test_factor_analysis_template_has_placeholders(self):
        """Factor analysis template contains expected format placeholders."""
        assert "{stock_name}" in CN_FACTOR_ANALYSIS_TEMPLATE
        assert "{stock_code}" in CN_FACTOR_ANALYSIS_TEMPLATE
        assert "{price}" in CN_FACTOR_ANALYSIS_TEMPLATE
        assert "{institutional_context}" in CN_FACTOR_ANALYSIS_TEMPLATE

    def test_sector_rotation_prompt_has_placeholder(self):
        """Sector rotation prompt has industry_data placeholder."""
        assert "{industry_data}" in CN_SECTOR_ROTATION_PROMPT

    def test_institutional_prompt_has_placeholders(self):
        """Institutional prompt has data and name/code placeholders."""
        assert "{institutional_data}" in CN_INSTITUTIONAL_PROMPT
        assert "{stock_name}" in CN_INSTITUTIONAL_PROMPT
        assert "{stock_code}" in CN_INSTITUTIONAL_PROMPT

    def test_macro_prompt_has_placeholders(self):
        """Macro prompt has economic data placeholders."""
        assert "{gdp}" in CN_MACRO_PROMPT
        assert "{cpi}" in CN_MACRO_PROMPT
        assert "{pmi}" in CN_MACRO_PROMPT
        assert "{m2}" in CN_MACRO_PROMPT
        assert "{policy_keywords}" in CN_MACRO_PROMPT

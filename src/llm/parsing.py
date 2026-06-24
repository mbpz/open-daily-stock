"""LLM 响应解析 — 迁自 src/analyzer.py:GeminiAnalyzer。

包含：
- fix_json_string: 修复常见 JSON 格式问题（注释/尾随逗号/布尔大小写）
- parse_response: 主解析器，返回 AnalysisResult
- parse_text_response: JSON 解析失败时的纯文本 fallback
- parse_specialist_json: P5-5 多 agent 模式下的 specialist JSON 解析

设计：纯函数，无 self 依赖，可独立测试。
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict

from src.llm.types import AnalysisResult

logger = logging.getLogger(__name__)


def fix_json_string(json_str: str) -> str:
    """修复常见的 JSON 格式问题。

    - 移除 // 单行注释 和 /* */ 多行注释
    - 移除尾随逗号 {a: 1,} / [1,]
    - True/False → true/false
    """
    # 移除注释
    json_str = re.sub(r'//.*?\n', '\n', json_str)
    json_str = re.sub(r'/\*.*?\*/', '', json_str, flags=re.DOTALL)

    # 修复尾随逗号
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)

    # 确保布尔值是小写
    json_str = json_str.replace('True', 'true').replace('False', 'false')

    return json_str


def parse_response(response_text: str, code: str, name: str) -> AnalysisResult:
    """解析 Gemini 响应（决策仪表盘版）。

    尝试从响应中提取 JSON 格式的分析结果，包含 dashboard 字段。
    如果解析失败，回退到 parse_text_response。
    """
    try:
        # 清理响应文本：移除 markdown 代码块标记
        cleaned_text = response_text
        if '```json' in cleaned_text:
            cleaned_text = cleaned_text.replace('```json', '').replace('```', '')
        elif '```' in cleaned_text:
            cleaned_text = cleaned_text.replace('```', '')

        # 尝试找到 JSON 内容
        json_start = cleaned_text.find('{')
        json_end = cleaned_text.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_str = cleaned_text[json_start:json_end]
            json_str = fix_json_string(json_str)
            data = json.loads(json_str)

            # 提取 dashboard 数据
            dashboard = data.get('dashboard', None)

            return AnalysisResult(
                code=code,
                name=name,
                # 核心指标
                sentiment_score=int(data.get('sentiment_score', 50)),
                trend_prediction=data.get('trend_prediction', '震荡'),
                operation_advice=data.get('operation_advice', '持有'),
                confidence_level=data.get('confidence_level', '中'),
                # 决策仪表盘
                dashboard=dashboard,
                # 走势分析
                trend_analysis=data.get('trend_analysis', ''),
                short_term_outlook=data.get('short_term_outlook', ''),
                medium_term_outlook=data.get('medium_term_outlook', ''),
                # 技术面
                technical_analysis=data.get('technical_analysis', ''),
                ma_analysis=data.get('ma_analysis', ''),
                volume_analysis=data.get('volume_analysis', ''),
                pattern_analysis=data.get('pattern_analysis', ''),
                # 基本面
                fundamental_analysis=data.get('fundamental_analysis', ''),
                sector_position=data.get('sector_position', ''),
                company_highlights=data.get('company_highlights', ''),
                # 情绪面/消息面
                news_summary=data.get('news_summary', ''),
                market_sentiment=data.get('market_sentiment', ''),
                hot_topics=data.get('hot_topics', ''),
                # 综合
                analysis_summary=data.get('analysis_summary', '分析完成'),
                key_points=data.get('key_points', ''),
                risk_warning=data.get('risk_warning', ''),
                buy_reason=data.get('buy_reason', ''),
                # 元数据
                search_performed=data.get('search_performed', False),
                data_sources=data.get('data_sources', '技术面数据'),
                success=True,
            )
        else:
            logger.warning("无法从响应中提取 JSON，使用原始文本分析")
            return parse_text_response(response_text, code, name)

    except json.JSONDecodeError as e:
        logger.warning(f"JSON 解析失败: {e}，尝试从文本提取")
        return parse_text_response(response_text, code, name)


def parse_text_response(response_text: str, code: str, name: str) -> AnalysisResult:
    """从纯文本响应中尽可能提取分析信息（JSON 解析失败时的 fallback）。"""
    # 尝试识别关键词来判断情绪
    sentiment_score = 50
    trend = '震荡'
    advice = '持有'

    text_lower = response_text.lower()

    # 简单的情绪识别
    positive_keywords = ['看多', '买入', '上涨', '突破', '强势', '利好', '加仓', 'bullish', 'buy']
    negative_keywords = ['看空', '卖出', '下跌', '跌破', '弱势', '利空', '减仓', 'bearish', 'sell']

    positive_count = sum(1 for kw in positive_keywords if kw in text_lower)
    negative_count = sum(1 for kw in negative_keywords if kw in text_lower)

    if positive_count > negative_count + 1:
        sentiment_score = 65
        trend = '看多'
        advice = '买入'
    elif negative_count > positive_count + 1:
        sentiment_score = 35
        trend = '看空'
        advice = '卖出'

    # 截取前 500 字符作为摘要
    summary = response_text[:500] if response_text else '无分析结果'

    return AnalysisResult(
        code=code,
        name=name,
        sentiment_score=sentiment_score,
        trend_prediction=trend,
        operation_advice=advice,
        confidence_level='低',
        analysis_summary=summary,
        key_points='JSON解析失败，仅供参考',
        risk_warning='分析结果可能不准确，建议结合其他信息判断',
        raw_response=response_text,
        success=True,
    )


def parse_specialist_json(response_text: str, agent_name: str) -> Dict[str, Any]:
    """Parse JSON from a P5-5 multi-agent specialist's response.

    Falls back to {"score": 50, "reasoning": ..., "raw": ...} if parsing fails.
    """
    try:
        cleaned = response_text
        if '```json' in cleaned:
            cleaned = cleaned.replace('```json', '').replace('```', '')
        elif '```' in cleaned:
            cleaned = cleaned.replace('```', '')

        json_start = cleaned.find('{')
        json_end = cleaned.rfind('}') + 1

        if json_start >= 0 and json_end > json_start:
            json_str = cleaned[json_start:json_end]
            json_str = fix_json_string(json_str)
            return json.loads(json_str)

    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"[DeepAnalyze:{agent_name}] JSON parse failed: {e}")

    # Fallback: extract score from text
    return {"score": 50, "reasoning": response_text[:200], "raw": response_text}

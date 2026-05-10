# -*- coding: utf-8 -*-
"""
===================================
A股自选股智能分析系统 - RAG 知识库
===================================

P5-6: Retrieval-Augmented Generation for historical analysis context.

When analyzing a stock, this module retrieves relevant past analysis
results from the FTS5 full-text search index and formats them as
structured context for the LLM prompt.
"""

from __future__ import annotations

import json
import logging
from typing import Optional, List, Dict, Any

from src.storage import get_db

logger = logging.getLogger(__name__)


def build_rag_context(
    code: str,
    question: Optional[str] = None,
    top_k_self: int = 3,
    top_k_similar: int = 2,
) -> str:
    """Build RAG context string for injection into the LLM prompt.

    Retrieves relevant past analyses for the target stock and searches
    for similar patterns across other stocks.  Formats the results as a
    structured [历史分析上下文] block.

    Args:
        code: Stock code being analyzed.
        question: Optional natural-language question to guide search.
                  If None, a default broad query is used.
        top_k_self: Number of past analyses to retrieve for this stock.
        top_k_similar: Number of cross-stock pattern matches to retrieve.

    Returns:
        Formatted RAG context string, or empty string when no relevant
        context is found (graceful degradation).
    """
    db = get_db()

    # Determine search query
    if question:
        search_query = f"{question} {code}"
    else:
        search_query = code  # broad search for this stock

    # --- Search for this stock's past analyses ---
    self_results = db.search_analyses(query=code, code=code, limit=top_k_self)

    # --- Search for similar patterns across all stocks ---
    broad_query = _build_broad_query(code, self_results)
    similar_results = db.search_analyses(query=broad_query, limit=top_k_similar)

    # Remove duplicates (entries already in self_results)
    self_ids = {r["id"] for r in self_results}
    similar_results = [r for r in similar_results if r["id"] not in self_ids]

    # --- Format output ---
    if not self_results and not similar_results:
        logger.debug(f"No RAG context found for {code}")
        return ""

    lines = ["\n---\n", "[历史分析上下文]", ""]

    if self_results:
        lines.append(f"### {code} 历史分析（最近 {len(self_results)} 次）")
        lines.append("")
        for i, r in enumerate(self_results, 1):
            lines.append(_format_entry(i, r))
            lines.append("")

    if similar_results:
        lines.append(f"### 相似模式参考（跨股票，共 {len(similar_results)} 条）")
        lines.append("")
        for i, r in enumerate(similar_results, 1):
            lines.append(_format_entry(i, r))
            lines.append("")

    lines.append("---")
    context = "\n".join(lines)
    logger.debug(f"Built RAG context for {code}: {len(context)} chars")

    return context


def _build_broad_query(code: str, self_results: List[Dict]) -> str:
    """Build a broad search query based on past analysis signals."""
    keywords = []
    for r in self_results:
        text = r.get("result_text", "")
        if not text:
            continue
        # Extract key signals from result JSON
        try:
            data = json.loads(text) if isinstance(text, str) else text
            trend = data.get("trend_prediction", "")
            if trend and trend not in ("震荡",):
                keywords.append(trend)
            # Extract MA-related signals from technical analysis
            ta = data.get("technical_analysis", "")
            ma = data.get("ma_analysis", "")
            combined = f"{ta} {ma}"
            if "金叉" in combined:
                keywords.append("金叉")
            if "死叉" in combined:
                keywords.append("死叉")
            if "放量" in combined:
                keywords.append("放量")
        except (json.JSONDecodeError, TypeError):
            # Try simple keyword extraction from raw text
            for kw in ["金叉", "死叉", "放量", "缩量", "突破", "支撑"]:
                if kw in str(text):
                    keywords.append(kw)

    if not keywords:
        return code  # fallback to just the stock code

    # Deduplicate and build query
    unique_kw = list(dict.fromkeys(keywords))[:3]
    return f"{code} {' '.join(unique_kw)}"


def _format_entry(index: int, result: Dict[str, Any]) -> str:
    """Format a single analysis history entry for RAG context."""
    text = result.get("result_text", "")
    ts = result.get("timestamp", "未知")
    code = result.get("code", "?")
    name = result.get("stock_name", "")

    # Try to extract structured info from JSON
    try:
        if isinstance(text, str) and text.strip().startswith("{"):
            data = json.loads(text)
        else:
            data = {}
    except (json.JSONDecodeError, TypeError):
        data = {}

    # Build a concise summary line
    trend = data.get("trend_prediction", "")
    score = data.get("sentiment_score", "")
    advice = data.get("operation_advice", "")
    summary = data.get("analysis_summary", "")

    # Extract key signals from technical analysis
    signals = []
    ma = data.get("ma_analysis", "")
    if ma:
        signals.append(ma[:80])
    elif data.get("technical_analysis"):
        signals.append(data["technical_analysis"][:80])

    # Format date for readability
    date_str = ts[:10] if ts and len(str(ts)) >= 10 else str(ts)

    parts = [f"{index}. {date_str} | {name or code}"]
    if trend:
        parts.append(f"趋势:{trend}")
    if score:
        parts.append(f"评分:{score}")
    if advice:
        parts.append(f"建议:{advice}")
    if signals:
        parts.append(f"信号:{signals[0]}")

    line = " | ".join(parts)

    # Add summary if available
    if summary and len(summary) > 5:
        line += f"\n   摘要: {summary[:120]}"

    return line

# -*- coding: utf-8 -*-
"""DEPRECATED — 全部实现已迁至 ``src.llm`` 包。

本文件保留作向后兼容 shim。所有 import 均从 src.llm 重新导出。
新代码请直接 from src.llm import ...。

迁移历程：P0-5（8 phases）完成。原 3112 行 → 现 17 行。

主要模块：
- src.llm.types: AnalysisResult + DeepAnalysisResult + OrchestratorCancelled
- src.llm.prompts: STOCK_NAME_MAP + system prompts + formatters + build_analysis_prompt
- src.llm.client: LLMClient 类（init + call_openai + call_with_retry + streaming）
- src.llm.parsing: response JSON 解析
- src.llm.analyzer: GeminiAnalyzer 高层业务逻辑（analyze / analyze_stream / deep_analyze / batch_analyze）
"""
# Re-export 公共 API（保持存量 from src.analyzer import ... 的兼容性）
from src.llm.types import (  # noqa: F401
    AnalysisResult,
    DeepAnalysisResult,
    OrchestratorCancelled,
)
from src.llm.prompts import (  # noqa: F401
    STOCK_NAME_MAP,
    get_stock_name_multi_source,
    format_volume,
    format_amount,
    build_analysis_prompt,
    TECHNICAL_SYSTEM_PROMPT,
    FUNDAMENTAL_SYSTEM_PROMPT,
    NEWS_SYSTEM_PROMPT,
    SYNTHESIZER_PROMPT,
    DEEP_AGENTS,
    DEEP_PROMPTS,
)
from src.llm.client import LLMClient  # noqa: F401
from src.llm.analyzer import GeminiAnalyzer, get_analyzer  # noqa: F401

# 兼容旧 src.llm.X import（之前 P0-5 中间态）
from src.llm.client import (  # noqa: F401
    init_gemini_model,
    init_openai_client,
    switch_to_fallback_model,
)
from src.llm.parsing import (  # noqa: F401
    fix_json_string,
    parse_response,
    parse_text_response,
    parse_specialist_json,
)

__all__ = [
    "AnalysisResult",
    "DeepAnalysisResult",
    "OrchestratorCancelled",
    "GeminiAnalyzer",
    "get_analyzer",
    "LLMClient",
    "STOCK_NAME_MAP",
    "get_stock_name_multi_source",
    "format_volume",
    "format_amount",
    "build_analysis_prompt",
    "TECHNICAL_SYSTEM_PROMPT",
    "FUNDAMENTAL_SYSTEM_PROMPT",
    "NEWS_SYSTEM_PROMPT",
    "SYNTHESIZER_PROMPT",
    "DEEP_AGENTS",
    "DEEP_PROMPTS",
    "init_gemini_model",
    "init_openai_client",
    "switch_to_fallback_model",
    "fix_json_string",
    "parse_response",
    "parse_text_response",
    "parse_specialist_json",
]

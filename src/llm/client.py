"""LLM 客户端初始化 + fallback 逻辑 — 迁自 src/analyzer.py:GeminiAnalyzer。

包含：
- init_gemini_model：初始化 Gemini 模型（带 fallback）
- init_openai_client：初始化 OpenAI 兼容 API 客户端
- switch_to_fallback_model：运行时切换到 fallback 模型
- is_available：检查客户端是否可用（any model + OpenAI）

设计目标：让这些函数独立可测，不依赖 GeminiAnalyzer 实例。
"""
from __future__ import annotations

import logging
from typing import Any, Optional, Tuple

logger = logging.getLogger(__name__)


# Init result type: (model/client_instance, model_name_str, is_fallback_bool)
# 或 (None, None, False) 表示初始化失败
GeminiInitResult = Tuple[Any, str, bool]  # Model | None, str, bool
OpenAIInitResult = Tuple[Any, str, bool]  # OpenAI | None, str, bool


def init_gemini_model(
    api_key: Optional[str],
    model_name: str,
    fallback_model: str,
    system_prompt: str,
) -> GeminiInitResult:
    """初始化 Gemini 模型（主 + 备选）。

    Returns:
        (model_instance, model_name, using_fallback)
        或 (None, "", False) 表示初始化失败
    """
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)

        try:
            model = genai.GenerativeModel(
                model_name=model_name,
                system_instruction=system_prompt,
            )
            logger.info(f"Gemini 模型初始化成功 (模型: {model_name})")
            return (model, model_name, False)
        except Exception as model_error:
            logger.warning(f"主模型 {model_name} 初始化失败: {model_error}，尝试备选模型 {fallback_model}")
            try:
                model = genai.GenerativeModel(
                    model_name=fallback_model,
                    system_instruction=system_prompt,
                )
                logger.info(f"Gemini 备选模型初始化成功 (模型: {fallback_model})")
                return (model, fallback_model, True)
            except Exception as fallback_error:
                logger.error(f"备选模型 {fallback_model} 也初始化失败: {fallback_error}")
                return (None, "", False)

    except Exception as e:
        logger.error(f"Gemini 模型初始化失败: {e}")
        return (None, "", False)


def init_openai_client(
    api_key: Optional[str],
    base_url: Optional[str],
    model: str,
) -> OpenAIInitResult:
    """初始化 OpenAI 兼容 API 客户端。

    支持：
    - OpenAI 官方
    - DeepSeek
    - 通义千问
    - Moonshot 等

    Returns:
        (client_instance, model_name, use_openai)
        或 (None, "", False) 表示未配置或初始化失败
    """
    if not api_key or api_key.startswith("your_") or len(api_key) <= 10:
        logger.debug("OpenAI 兼容 API 未配置或配置无效")
        return (None, "", False)

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("未安装 openai 库，请运行: pip install openai")
        return (None, "", False)

    try:
        client_kwargs: dict = {"api_key": api_key}
        if base_url and base_url.startswith("http"):
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)
        logger.info(f"OpenAI 兼容 API 初始化成功 (base_url: {base_url}, model: {model})")
        return (client, model, True)
    except ImportError as e:
        # 依赖缺失（如 socksio）
        if 'socksio' in str(e).lower() or 'socks' in str(e).lower():
            logger.error(
                f"OpenAI 客户端需要 SOCKS 代理支持，请运行: pip install httpx[socks] 或 pip install socksio"
            )
        else:
            logger.error(f"OpenAI 依赖缺失: {e}")
        return (None, "", False)
    except Exception as e:
        error_msg = str(e).lower()
        if 'socks' in error_msg or 'socksio' in error_msg or 'proxy' in error_msg:
            logger.error(f"OpenAI 代理配置错误: {e}，如使用 SOCKS 代理请运行: pip install httpx[socks]")
        else:
            logger.error(f"OpenAI 兼容 API 初始化失败: {e}")
        return (None, "", False)


def switch_to_fallback_model(
    api_key: Optional[str],
    fallback_model: str,
    system_prompt: str,
) -> GeminiInitResult:
    """运行时切换到备选 Gemini 模型。

    Returns:
        (model_instance, model_name, True)
        或 (None, "", False) 表示切换失败
    """
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        logger.warning(f"[LLM] 切换到备选模型: {fallback_model}")
        model = genai.GenerativeModel(
            model_name=fallback_model,
            system_instruction=system_prompt,
        )
        logger.info(f"[LLM] 备选模型 {fallback_model} 初始化成功")
        return (model, fallback_model, True)
    except Exception as e:
        logger.error(f"[LLM] 切换备选模型失败: {e}")
        return (None, "", False)


def is_available(model: Any = None, openai_client: Any = None) -> bool:
    """检查 LLM 客户端是否可用（任一 provider 即可）。"""
    return model is not None or openai_client is not None

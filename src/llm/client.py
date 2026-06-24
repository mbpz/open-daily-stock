"""LLM 客户端 — 封装 Gemini + OpenAI 双 provider 的初始化、状态管理、fallback。

迁自 src/analyzer.py:GeminiAnalyzer 的 7 个状态字段 + 3 个 init 方法。

设计目标:
- LLMClient 拥有所有 provider 状态（model / openai_client / current_model_name 等）
- 提供 ensure_initialized / switch_to_fallback / is_available 等 lifecycle API
- 保留 init_gemini_model / init_openai_client / switch_to_fallback_model /
  is_available 模块函数作为底层 helper（Phase 3 引入，pure functional）

GeminiAnalyzer 持有 self._client = LLMClient(...) 并把状态访问转为委托。
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


# ============================================================
# LLMClient: stateful wrapper combining Gemini + OpenAI
# ============================================================


class LLMClient:
    """封装 LLM 双 provider 状态：Gemini + OpenAI 兼容 API。

    GeminiAnalyzer 持有 self._client = LLMClient(...) 并把状态访问转为委托。

    字段（迁自 GeminiAnalyzer）:
        api_key: Gemini API Key
        model: google.generativeai.GenerativeModel 实例（可 None）
        current_model_name: 当前激活的模型名（Gemini 或 OpenAI）
        using_fallback: 当前是否在用 Gemini 备选模型
        use_openai: 是否在用 OpenAI 兼容 API
        openai_client: openai.OpenAI 实例（可 None）
        system_prompt: 系统提示词（可动态变更：例如中国市场切到 CN_ANALYST_SYSTEM_PROMPT）
    """

    def __init__(
        self,
        api_key: Optional[str],
        gemini_model: str,
        gemini_fallback_model: str,
        openai_api_key: Optional[str],
        openai_base_url: Optional[str],
        openai_model: str,
        system_prompt: str,
    ):
        self.api_key = api_key
        self.gemini_model_name_cfg = gemini_model
        self.gemini_fallback_cfg = gemini_fallback_model
        self.openai_api_key = openai_api_key
        self.openai_base_url = openai_base_url
        self.openai_model_cfg = openai_model

        self.system_prompt = system_prompt

        # runtime state
        self.model = None
        self.current_model_name: Optional[str] = None
        self.using_fallback = False
        self.use_openai = False
        self.openai_client = None

        self._init_providers()

    def _init_providers(self) -> None:
        """初始化 Gemini → 若 Gemini 失败再尝试 OpenAI（与旧 __init__ 行为一致）。"""
        gemini_key_valid = (
            self.api_key
            and not self.api_key.startswith("your_")
            and len(self.api_key) > 10
        )

        if gemini_key_valid:
            try:
                model, name, fallback = init_gemini_model(
                    self.api_key,
                    self.gemini_model_name_cfg,
                    self.gemini_fallback_cfg,
                    self.system_prompt,
                )
                if model is not None:
                    self.model = model
                    self.current_model_name = name
                    self.using_fallback = fallback
                else:
                    logger.warning("Gemini 初始化失败，尝试 OpenAI 兼容 API")
                    self.init_openai()
            except Exception as e:
                logger.warning(f"Gemini 初始化异常: {e}，尝试 OpenAI 兼容 API")
                self.init_openai()
        else:
            logger.info("Gemini API Key 未配置，尝试使用 OpenAI 兼容 API")
            self.init_openai()

        if not self.model and not self.openai_client:
            logger.warning("未配置任何 AI API Key，AI 分析功能将不可用")

    def init_openai(self) -> None:
        """初始化 OpenAI 兼容 API（mutate self）。"""
        client, model_name, use_openai = init_openai_client(
            self.openai_api_key,
            self.openai_base_url,
            self.openai_model_cfg,
        )
        if client is not None:
            self.openai_client = client
            self.current_model_name = model_name
            self.use_openai = use_openai

    def switch_to_fallback(self) -> bool:
        """运行时切换 Gemini 备选模型（mutate self）。

        Returns:
            是否切换成功
        """
        model, name, _ = switch_to_fallback_model(
            self.api_key,
            self.gemini_fallback_cfg,
            self.system_prompt,
        )
        if model is None:
            return False
        self.model = model
        self.current_model_name = name
        self.using_fallback = True
        return True

    def is_available(self) -> bool:
        """任一 provider 可用即返回 True。"""
        return is_available(self.model, self.openai_client)

    def set_system_prompt(self, prompt: str) -> None:
        """运行时变更系统提示词（例如切换 CN 模式时使用）。

        注意：变更后已实例化的 model 不会自动重建——下次切换 fallback 时新提示词生效。
        与旧 GeminiAnalyzer.analyze() 行为一致。
        """
        self.system_prompt = prompt

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
import time
from typing import Any, Optional, Tuple

from src.config import get_config

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

    # ============================================================
    # API call methods — migrated from GeminiAnalyzer in Phase 7
    # ============================================================

    def call_openai(self, prompt: str, generation_config: dict) -> str:
        """调用 OpenAI 兼容 API（带重试）。

        迁自 src/analyzer.py:GeminiAnalyzer._call_openai_api。
        """
        config = get_config()
        max_retries = config.gemini_max_retries
        base_delay = config.gemini_retry_delay

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))
                    delay = min(delay, 60)
                    logger.info(f"[OpenAI] 第 {attempt + 1} 次重试，等待 {delay:.1f} 秒...")
                    time.sleep(delay)

                config = get_config()
                response = self.openai_client.chat.completions.create(
                    model=self.current_model_name,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=generation_config.get("temperature", config.openai_temperature),
                    max_tokens=generation_config.get("max_output_tokens", 8192),
                )

                if response and response.choices and response.choices[0].message.content:
                    return response.choices[0].message.content
                else:
                    raise ValueError("OpenAI API 返回空响应")

            except Exception as e:
                error_str = str(e)
                is_rate_limit = (
                    '429' in error_str
                    or 'rate' in error_str.lower()
                    or 'quota' in error_str.lower()
                )

                if is_rate_limit:
                    logger.warning(f"[OpenAI] API 限流，第 {attempt + 1}/{max_retries} 次尝试: {error_str[:100]}")
                else:
                    logger.warning(f"[OpenAI] API 调用失败，第 {attempt + 1}/{max_retries} 次尝试: {error_str[:100]}")

                if attempt == max_retries - 1:
                    raise

        raise Exception("OpenAI API 调用失败，已达最大重试次数")

    def call_with_retry(
        self,
        prompt: str,
        generation_config: dict,
        cancellation_event: Optional[Any] = None,
    ) -> str:
        """调用 AI API，带有重试和模型切换机制。

        迁自 src/analyzer.py:GeminiAnalyzer._call_api_with_retry。

        优先级：Gemini → Gemini 备选模型 → OpenAI 兼容 API

        处理 429 限流错误：
        1. 先指数退避重试
        2. 多次失败后切换到备选模型
        3. Gemini 完全失败后尝试 OpenAI

        Args:
            prompt: 提示词
            generation_config: 生成配置
            cancellation_event: 可选信号；如被 set()，立即抛 OrchestratorCancelled

        Returns:
            响应文本
        """
        from src.llm.types import OrchestratorCancelled

        # 如果已经在使用 OpenAI 模式，直接调用 OpenAI
        if self.use_openai:
            return self.call_openai(prompt, generation_config)

        config = get_config()
        max_retries = config.gemini_max_retries
        base_delay = config.gemini_retry_delay

        last_error = None
        tried_fallback = self.using_fallback

        # Co-operative cancellation: callers can pass an Event that the
        # caller sets to abort the retry loop (e.g. user closed the GUI).
        # We check before each attempt and after each sleep.
        def _check_cancel() -> None:
            if cancellation_event is not None and cancellation_event.is_set():
                raise OrchestratorCancelled("cancelled before Gemini attempt")

        for attempt in range(max_retries):
            _check_cancel()
            try:
                # 请求前增加延时（防止请求过快触发限流）
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))  # 指数退避: 5, 10, 20, 40...
                    delay = min(delay, 60)  # 最大60秒
                    logger.info(f"[Gemini] 第 {attempt + 1} 次重试，等待 {delay:.1f} 秒...")
                    # Sleep in 0.5s slices so cancellation is responsive
                    # (default backoff can be 5–60s).
                    slept = 0.0
                    while slept < delay:
                        _check_cancel()
                        step = min(0.5, delay - slept)
                        time.sleep(step)
                        slept += step

                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    request_options={"timeout": 120},
                )

                if response and response.text:
                    return response.text
                else:
                    raise ValueError("Gemini 返回空响应")

            except Exception as e:
                # Cancellation must propagate immediately, not be
                # treated as a retryable error.
                if isinstance(e, OrchestratorCancelled):
                    raise
                last_error = e
                error_str = str(e)

                # 检查是否是 429 限流错误
                is_rate_limit = (
                    '429' in error_str
                    or 'quota' in error_str.lower()
                    or 'rate' in error_str.lower()
                )

                if is_rate_limit:
                    logger.warning(f"[Gemini] API 限流 (429)，第 {attempt + 1}/{max_retries} 次尝试: {error_str[:100]}")

                    # 如果已经重试了一半次数且还没切换过备选模型，尝试切换
                    if attempt >= max_retries // 2 and not tried_fallback:
                        if self.switch_to_fallback():
                            tried_fallback = True
                            logger.info("[Gemini] 已切换到备选模型，继续重试")
                        else:
                            logger.warning("[Gemini] 切换备选模型失败，继续使用当前模型重试")
                else:
                    # 非限流错误，记录并继续重试
                    logger.warning(f"[Gemini] API 调用失败，第 {attempt + 1}/{max_retries} 次尝试: {error_str[:100]}")

        # Gemini 所有重试都失败，尝试 OpenAI 兼容 API
        if self.openai_client:
            logger.warning("[Gemini] 所有重试失败，切换到 OpenAI 兼容 API")
            try:
                return self.call_openai(prompt, generation_config)
            except Exception as openai_error:
                logger.error(f"[OpenAI] 备选 API 也失败: {openai_error}")
                raise last_error or openai_error
        elif config.openai_api_key and config.openai_base_url:
            # 尝试懒加载初始化 OpenAI
            logger.warning("[Gemini] 所有重试失败，尝试初始化 OpenAI 兼容 API")
            self.init_openai()
            if self.openai_client:
                try:
                    return self.call_openai(prompt, generation_config)
                except Exception as openai_error:
                    logger.error(f"[OpenAI] 备选 API 也失败: {openai_error}")
                    raise last_error or openai_error

        # 所有方式都失败
        raise last_error or Exception("所有 AI API 调用失败，已达最大重试次数")


# ============================================================


# ============================================================
# Streaming methods — migrated from GeminiAnalyzer in Phase 8
# ============================================================


    def call_gemini_stream(
        self, prompt: str, generation_config: dict,
    ):
        """Call Gemini API with streaming enabled.

        Yields text chunks as they arrive from the API.

        迁自 src/analyzer.py:GeminiAnalyzer._call_gemini_stream。
        """
        if self.use_openai and self.openai_client:
            yield from self.call_openai_stream(prompt, generation_config)
            return

        config = get_config()
        max_retries = config.gemini_max_retries
        base_delay = config.gemini_retry_delay

        last_error = None
        tried_fallback = self.using_fallback

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))
                    delay = min(delay, 60)
                    logger.info(f"[Gemini Stream] 第 {attempt + 1} 次重试，等待 {delay:.1f} 秒...")
                    time.sleep(delay)

                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    stream=True,
                    request_options={"timeout": 120},
                )

                for chunk in response:
                    if chunk.text:
                        yield chunk.text

                return

            except Exception as e:
                last_error = e
                error_str = str(e)
                is_rate_limit = (
                    '429' in error_str
                    or 'quota' in error_str.lower()
                    or 'rate' in error_str.lower()
                )
                if is_rate_limit:
                    logger.warning(f"[Gemini Stream] API 限流 (429)，第 {attempt + 1}/{max_retries} 次尝试")
                    if attempt >= max_retries // 2 and not tried_fallback:
                        if self.switch_to_fallback():
                            tried_fallback = True
                            logger.info("[Gemini Stream] 已切换到备选模型，继续重试")
                else:
                    logger.warning(f"[Gemini Stream] API 调用失败，第 {attempt + 1}/{max_retries} 次尝试: {error_str[:100]}")

        if self.openai_client:
            logger.warning("[Gemini Stream] 所有重试失败，尝试 OpenAI 兼容 API 流式")
            try:
                yield from self.call_openai_stream(prompt, generation_config)
                return
            except Exception as openai_error:
                logger.error(f"[OpenAI Stream] 备选也失败: {openai_error}")
                raise last_error or openai_error

        raise last_error or Exception("所有 AI API 流式调用失败")


    def call_openai_stream(
        self, prompt: str, generation_config: dict,
    ):
        """Call OpenAI-compatible API with streaming enabled.

        Yields text chunks as they arrive from the API.

        迁自 src/analyzer.py:GeminiAnalyzer._call_openai_stream。
        """
        config = get_config()
        max_retries = config.gemini_max_retries
        base_delay = config.gemini_retry_delay

        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    delay = base_delay * (2 ** (attempt - 1))
                    delay = min(delay, 60)
                    logger.info(f"[OpenAI Stream] 第 {attempt + 1} 次重试，等待 {delay:.1f} 秒...")
                    time.sleep(delay)

                stream = self.openai_client.chat.completions.create(
                    model=self.current_model_name,
                    messages=[
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=generation_config.get("temperature", config.openai_temperature),
                    max_tokens=generation_config.get("max_output_tokens", 8192),
                    stream=True,
                )

                for chunk in stream:
                    if chunk.choices and chunk.choices[0].delta.content:
                        yield chunk.choices[0].delta.content

                return

            except Exception as e:
                error_str = str(e)
                is_rate_limit = (
                    '429' in error_str
                    or 'rate' in error_str.lower()
                    or 'quota' in error_str.lower()
                )
                if is_rate_limit:
                    logger.warning(f"[OpenAI Stream] API 限流，第 {attempt + 1}/{max_retries} 次尝试")
                else:
                    logger.warning(f"[OpenAI Stream] API 调用失败，第 {attempt + 1}/{max_retries} 次尝试: {error_str[:100]}")

                if attempt == max_retries - 1:
                    raise

        raise Exception("OpenAI 流式 API 调用失败，已达最大重试次数")

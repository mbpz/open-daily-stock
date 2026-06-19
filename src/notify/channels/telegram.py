"""Telegram Bot 通知渠道。

迁自 src/notification.py:send_to_telegram / _send_telegram_message /
_send_telegram_message_with_retry / _send_telegram_chunked /
_convert_to_telegram_markdown。

核心特性：
- Telegram Bot API 端点 `/bot<token>/sendMessage`
- 字符（不是字节）上限 4096
- **Markdown 转换** _convert_to_telegram_markdown：
  - 移除 #/##/### 标题（Telegram 不支持）
  - **粗体** → *粗体*（Telegram 用单 *）
  - 转义 [ ] ( )
- **解析失败 fallback**：API 返回 parse/markdown 错误时，同请求内改纯文本重试（不消耗 tenacity 重试次数）
- 智能分块按 `\\n---\\n`；都不命中时整段发送（沿用旧行为）
- tenacity retry 3 次指数退避
- 块间 sleep(0.5) 防 Telegram rate limit（30 msg/s）
- disable_web_page_preview=True 禁止链接预览展开
"""
from __future__ import annotations

import logging
import re
import time
from typing import List

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..base import BaseChannel, ChannelPriority, ChannelResult

logger = logging.getLogger(__name__)

# Telegram 单条消息上限（字符，非字节）
_MAX_LENGTH = 4096


# ─── Markdown 转换 ─────────────────────────────────────────────


def _convert_to_telegram_markdown(text: str) -> str:
    """将通用 Markdown 转换为 Telegram 支持的格式。

    迁自 src/notification.py:_convert_to_telegram_markdown。
    """
    result = text

    # 移除 # 标题标记（Telegram 不支持）
    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)

    # 转换 **bold** → *bold*（Telegram 用单星号）
    result = re.sub(r"\*\*(.+?)\*\*", r"*\1*", result)

    # 转义特殊字符（Telegram Markdown 需要）
    for char in ["[", "]", "(", ")"]:
        result = result.replace(char, f"\\{char}")

    return result


# ─── 分块 ──────────────────────────────────────────────────────


def _split_chunks(content: str, max_length: int) -> List[str]:
    """按 `\\n---\\n` 分割并装箱；没有分隔符时整段单元素返回。

    沿用旧 _send_telegram_chunked 行为：单一无分隔符的超长内容会作为一段发出，
    由 Telegram API 拒收（旧实现的局限——本次迁移不引入新行为）。
    """
    sections = content.split("\n---\n")
    sep_chars = len("\n---\n")

    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for section in sections:
        section_len = len(section) + sep_chars
        if current_len + section_len > max_length:
            if current:
                chunks.append("\n---\n".join(current))
            current = [section]
            current_len = section_len
        else:
            current.append(section)
            current_len += section_len

    if current:
        chunks.append("\n---\n".join(current))
    return chunks


class TelegramChannel(BaseChannel):
    """Telegram Bot 通知。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get("telegram_bot_token")
        self.chat_id = config.get("telegram_chat_id")

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.HIGH

    @property
    def api_url(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/sendMessage"

    def send(self, content: str, **kwargs) -> ChannelResult:
        """发送 Telegram 消息（自动 Markdown 转换 + 解析失败回退纯文本）。

        kwargs:
            max_length: 覆盖默认字符上限（用于测试）
        """
        if not self.is_configured():
            return ChannelResult(success=False, channel=self.name, error="Telegram 未配置")

        max_length = kwargs.get("max_length", _MAX_LENGTH)

        if len(content) <= max_length:
            return self._send_one(content)

        chunks = _split_chunks(content, max_length)
        return self._send_chunks(chunks)

    # ─── 单条发送 ──────────────────────────────────────────────

    def _send_one(self, content: str) -> ChannelResult:
        try:
            self._post_with_retry(content)
            return ChannelResult(success=True, channel=self.name, message="Telegram 已发送")
        except requests.RequestException as e:
            logger.error(f"Telegram 发送失败（已重试）: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))
        except Exception as e:
            logger.error(f"Telegram 发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        reraise=True,
    )
    def _post_with_retry(self, content: str) -> None:
        """单次 HTTP POST + 重试装饰；解析失败时同请求内回退纯文本。"""
        # 1) 优先 Markdown
        telegram_text = _convert_to_telegram_markdown(content)
        payload = {
            "chat_id": self.chat_id,
            "text": telegram_text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        response = requests.post(self.api_url, json=payload, timeout=10)

        if response.status_code != 200:
            raise requests.RequestException(f"HTTP {response.status_code}")

        result = response.json()
        if result.get("ok"):
            return

        error_desc = result.get("description", "未知错误")

        # 2) parse_mode 解析失败 → 同请求内回退纯文本（不消耗 tenacity 重试）
        if "parse" in error_desc.lower() or "markdown" in error_desc.lower():
            logger.info("Telegram Markdown 解析失败，回退纯文本重发")
            plain_payload = {
                "chat_id": self.chat_id,
                "text": content,  # 原始未转换文本
                "disable_web_page_preview": True,
            }
            response = requests.post(self.api_url, json=plain_payload, timeout=10)
            if response.status_code == 200 and response.json().get("ok"):
                return
            # 纯文本也失败 → raise 让 retry 重试
            raise requests.RequestException(f"Telegram 纯文本回退也失败: {error_desc}")

        raise requests.RequestException(f"Telegram 返回错误: {error_desc}")

    # ─── 分批发送 ──────────────────────────────────────────────

    def _send_chunks(self, chunks: List[str]) -> ChannelResult:
        total = len(chunks)
        success_count = 0
        last_error = ""

        logger.info(f"Telegram 分批发送：共 {total} 批")

        for i, chunk in enumerate(chunks):
            r = self._send_one(chunk)
            if r.success:
                success_count += 1
                logger.info(f"Telegram 第 {i + 1}/{total} 批发送成功")
            else:
                last_error = r.error or "未知错误"
                logger.error(f"Telegram 第 {i + 1}/{total} 批发送失败: {last_error}")

            if i < total - 1:
                time.sleep(0.5)

        if success_count == total:
            return ChannelResult(
                success=True, channel=self.name, message=f"Telegram 已发送 {total} 批"
            )
        return ChannelResult(
            success=False,
            channel=self.name,
            error=f"分批发送 {success_count}/{total} 成功，最后错误: {last_error}",
        )

"""企业微信 Webhook 通知渠道。

迁自 src/notification.py:send_to_wechat 及其辅助方法
（_send_wechat_chunked / _send_wechat_force_chunked / _truncate_to_bytes /
_send_wechat_message / _send_wechat_message_with_retry）。

核心特性：
- 企业微信 markdown 消息字节上限 4096（默认配置 4000，留余地）
- 智能分块：按 `\\n---\\n` → `\\n### ` → `\\n## ` → `\\n**` 四级 fallback；都不命中
  时按行强制截断
- 多字节字符安全的字节级截断 _truncate_to_bytes
- tenacity 重试（3 次指数退避，仅 RequestException/ConnectionError）
- 分批发送时块间 sleep 防限流
- 分页标记 `📄 *(i/N)*`
"""
from __future__ import annotations

import logging
import time
from typing import List, Optional, Tuple

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..base import BaseChannel, ChannelPriority, ChannelResult

logger = logging.getLogger(__name__)

# 默认字节上限（企业微信 markdown 限 4096 字节，留 96 字节余量）
_DEFAULT_MAX_BYTES = 4000
# 块间间隔（秒）
_SMART_CHUNK_INTERVAL = 2.5
_FORCE_CHUNK_INTERVAL = 1.0
# 强制按行分块时预留给分页标记的字节
_PAGE_MARKER_RESERVE = 100
# 单 section 强制截断时预留的提示字节
_TRUNCATE_RESERVE = 200


def _get_bytes(s: str) -> int:
    """字符串的 UTF-8 字节数。"""
    return len(s.encode("utf-8"))


def _truncate_to_bytes(text: str, max_bytes: int) -> str:
    """按字节数截断字符串，确保不会在多字节字符中间截断。

    迁自旧 _truncate_to_bytes。
    """
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    truncated = encoded[:max_bytes]
    while truncated:
        try:
            return truncated.decode("utf-8")
        except UnicodeDecodeError:
            truncated = truncated[:-1]
    return ""


def _smart_split(content: str) -> Tuple[Optional[List[str]], Optional[str]]:
    """按 4 级 fallback 智能分割。

    Returns:
        (sections, separator) 若命中智能分割；(None, None) 表示需要强制按行截断
    """
    if "\n---\n" in content:
        return content.split("\n---\n"), "\n---\n"
    if "\n### " in content:
        parts = content.split("\n### ")
        return [parts[0]] + [f"### {p}" for p in parts[1:]], "\n"
    if "\n## " in content:
        parts = content.split("\n## ")
        return [parts[0]] + [f"## {p}" for p in parts[1:]], "\n"
    if "\n**" in content:
        parts = content.split("\n**")
        return [parts[0]] + [f"**{p}" for p in parts[1:]], "\n"
    return None, None


def _build_smart_chunks(
    sections: List[str], separator: str, max_bytes: int
) -> List[str]:
    """根据已切好的 sections 装箱成 ≤ max_bytes 的 chunk 列表。

    单 section 超长则强制截断并标注 "(本段内容过长已截断)"。
    """
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_bytes = 0
    sep_bytes = _get_bytes(separator)

    for section in sections:
        section_bytes = _get_bytes(section) + sep_bytes

        # 单 section 就超长 → 截断单独成 chunk
        if section_bytes > max_bytes:
            if current_chunk:
                chunks.append(separator.join(current_chunk))
                current_chunk = []
                current_bytes = 0
            truncated = _truncate_to_bytes(section, max_bytes - _TRUNCATE_RESERVE)
            truncated += "\n\n...(本段内容过长已截断)"
            chunks.append(truncated)
            continue

        # 装箱
        if current_bytes + section_bytes > max_bytes:
            if current_chunk:
                chunks.append(separator.join(current_chunk))
            current_chunk = [section]
            current_bytes = section_bytes
        else:
            current_chunk.append(section)
            current_bytes += section_bytes

    if current_chunk:
        chunks.append(separator.join(current_chunk))
    return chunks


def _build_force_chunks(content: str, max_bytes: int) -> List[str]:
    """按行强制分块（智能分割失败时的 fallback）。"""
    chunks: List[str] = []
    current_chunk = ""
    for line in content.split("\n"):
        test_chunk = current_chunk + ("\n" if current_chunk else "") + line
        if _get_bytes(test_chunk) > max_bytes - _PAGE_MARKER_RESERVE:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk = test_chunk
    if current_chunk:
        chunks.append(current_chunk)
    return chunks


def _add_page_marker(chunk: str, idx: int, total: int) -> str:
    """超过 1 块时附加 `📄 *(i/N)*` 分页标记。"""
    if total <= 1:
        return chunk
    return f"{chunk}\n\n📄 *({idx + 1}/{total})*"


class WechatChannel(BaseChannel):
    """企业微信 Webhook 推送。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config.get("wechat_webhook_url")
        self.max_bytes = config.get("wechat_max_bytes", _DEFAULT_MAX_BYTES)

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.HIGH

    def send(self, content: str, **kwargs) -> ChannelResult:
        """发送企业微信消息。

        kwargs:
            max_bytes: 覆盖默认字节上限（用于测试）
        """
        if not self.is_configured():
            return ChannelResult(
                success=False, channel=self.name, error="企业微信 Webhook 未配置"
            )

        max_bytes = kwargs.get("max_bytes", self.max_bytes)
        content_bytes = _get_bytes(content)

        if content_bytes <= max_bytes:
            return self._send_one(content)

        logger.info(
            f"企业微信消息超长 ({content_bytes}字节/{len(content)}字符)，将分批发送"
        )

        sections, separator = _smart_split(content)
        if sections is None:
            chunks = _build_force_chunks(content, max_bytes)
            interval = _FORCE_CHUNK_INTERVAL
        else:
            chunks = _build_smart_chunks(sections, separator or "\n", max_bytes)
            interval = _SMART_CHUNK_INTERVAL

        return self._send_chunks(chunks, interval)

    # ─── 单条发送 ──────────────────────────────────────────────

    def _send_one(self, content: str) -> ChannelResult:
        try:
            self._post_with_retry(content)
            return ChannelResult(success=True, channel=self.name, message="企业微信已发送")
        except requests.RequestException as e:
            logger.error(f"企业微信发送失败（已重试）: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))
        except Exception as e:
            logger.error(f"企业微信发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        reraise=True,
    )
    def _post_with_retry(self, content: str) -> None:
        """单次 HTTP POST + 重试装饰。

        失败时 raise RequestException 让 tenacity 重试；成功时静默返回。
        """
        payload = {"msgtype": "markdown", "markdown": {"content": content}}
        response = requests.post(self.webhook_url, json=payload, timeout=10)

        if response.status_code != 200:
            raise requests.RequestException(f"HTTP {response.status_code}")

        result = response.json()
        if result.get("errcode") != 0:
            raise requests.RequestException(
                f"errcode={result.get('errcode')} errmsg={result.get('errmsg')}"
            )

    # ─── 分批发送 ──────────────────────────────────────────────

    def _send_chunks(self, chunks: List[str], interval: float) -> ChannelResult:
        total = len(chunks)
        success_count = 0
        last_error = ""

        logger.info(f"企业微信分批发送：共 {total} 批")

        for i, chunk in enumerate(chunks):
            chunk_with_marker = _add_page_marker(chunk, i, total)
            r = self._send_one(chunk_with_marker)
            if r.success:
                success_count += 1
                logger.info(f"企业微信第 {i + 1}/{total} 批发送成功")
            else:
                last_error = r.error or "未知错误"
                logger.error(f"企业微信第 {i + 1}/{total} 批发送失败: {last_error}")

            if i < total - 1:
                time.sleep(interval)

        if success_count == total:
            return ChannelResult(
                success=True, channel=self.name, message=f"企业微信已发送 {total} 批"
            )
        return ChannelResult(
            success=False,
            channel=self.name,
            error=f"分批发送 {success_count}/{total} 成功，最后错误: {last_error}",
        )

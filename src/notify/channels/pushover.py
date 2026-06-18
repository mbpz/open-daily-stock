"""Pushover 推送通知渠道（手机/桌面）"""
import logging
import re
import time
from datetime import datetime
from typing import List

import requests

from ..base import BaseChannel, ChannelPriority, ChannelResult

logger = logging.getLogger(__name__)

# Pushover API 端点
_API_URL = "https://api.pushover.net/1/messages.json"
# Pushover 单条消息字符上限
_MAX_LENGTH = 1024
# 块间发送间隔（秒），避免触发 API 频率限制
_CHUNK_INTERVAL = 1.0


def _markdown_to_plain_text(markdown_text: str) -> str:
    """将 Markdown 转换为纯文本，移除格式标记保留可读性。

    迁自 src/notification.py:_markdown_to_plain_text。
    """
    text = markdown_text

    # 标题 #/##/### → 去除标记
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # 加粗 **text** → text
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    # 斜体 *text* → text
    text = re.sub(r"\*(.+?)\*", r"\1", text)
    # 引用 > text → text
    text = re.sub(r"^>\s+", "", text, flags=re.MULTILINE)
    # 列表标记 - / * → •
    text = re.sub(r"^[-*]\s+", "• ", text, flags=re.MULTILINE)
    # 分隔线 --- → 长破折号
    text = re.sub(r"^---+$", "────────", text, flags=re.MULTILINE)
    # 表格分隔行 |---|---|
    text = re.sub(r"\|[-:]+\|[-:|\s]+\|", "", text)
    # 表格行去掉两侧 |
    text = re.sub(r"^\|(.+)\|$", r"\1", text, flags=re.MULTILINE)
    # 多余空行折叠
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _split_into_chunks(content: str, max_length: int) -> List[str]:
    """按段落分块，确保每块不超过 max_length。

    优先按分隔线 ──────── 切分，否则按双换行；保留旧 chunk 长度计算（首段不
    带分隔符、后续段需加分隔符）的语义，避免回归。
    """
    if "────────" in content:
        sections = content.split("────────")
        separator = "────────"
    else:
        sections = content.split("\n\n")
        separator = "\n\n"

    chunks: List[str] = []
    current_chunk: List[str] = []
    current_length = 0

    for section in sections:
        if current_chunk:
            new_length = current_length + len(separator) + len(section)
        else:
            new_length = len(section)

        if new_length > max_length:
            if current_chunk:
                chunks.append(separator.join(current_chunk))
            current_chunk = [section]
            current_length = len(section)
        else:
            current_chunk.append(section)
            current_length = new_length

    if current_chunk:
        chunks.append(separator.join(current_chunk))

    return chunks


class PushoverChannel(BaseChannel):
    """Pushover 推送（iOS / Android / 桌面）。

    迁自 src/notification.py:send_to_pushover/_send_pushover_message/
    _send_pushover_chunked/_markdown_to_plain_text。

    特点：
    - 单条消息上限 1024 字符（超过自动分块）
    - 默认 priority=0，范围 -2 ~ 2
    - 接受 Markdown 输入，内部自动转换为纯文本
    """

    def __init__(self, config: dict):
        super().__init__(config)
        self.user_key = config.get("pushover_user_key")
        self.api_token = config.get("pushover_api_token")

    def is_configured(self) -> bool:
        return bool(self.user_key and self.api_token)

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.MEDIUM

    def send(self, content: str, **kwargs) -> ChannelResult:
        """发送 Pushover 消息。

        kwargs:
            title: 自定义标题，默认 "📈 股票分析报告 - YYYY-MM-DD"
            priority: -2 ~ 2，默认 0
        """
        if not self.is_configured():
            return ChannelResult(
                success=False, channel=self.name, error="Pushover 未配置（需 user_key 与 api_token）"
            )

        title = kwargs.get("title")
        if title is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            title = f"📈 股票分析报告 - {date_str}"

        msg_priority = kwargs.get("priority", 0)

        plain_content = _markdown_to_plain_text(content)

        if len(plain_content) <= _MAX_LENGTH:
            return self._send_one(plain_content, title, msg_priority)

        chunks = _split_into_chunks(plain_content, _MAX_LENGTH)
        return self._send_chunks(chunks, title, msg_priority)

    # ─── 内部 ───────────────────────────────────────────────

    def _send_one(self, message: str, title: str, msg_priority: int) -> ChannelResult:
        try:
            payload = {
                "token": self.api_token,
                "user": self.user_key,
                "message": message,
                "title": title,
                "priority": msg_priority,
            }
            response = requests.post(_API_URL, data=payload, timeout=30)

            if response.status_code != 200:
                err = f"HTTP {response.status_code}"
                logger.error(f"Pushover 请求失败: {err}")
                return ChannelResult(success=False, channel=self.name, error=err)

            result = response.json()
            if result.get("status") == 1:
                return ChannelResult(success=True, channel=self.name, message="Pushover 已发送")

            errors = result.get("errors", ["未知错误"])
            err_str = "; ".join(str(e) for e in errors)
            logger.error(f"Pushover 返回错误: {err_str}")
            return ChannelResult(success=False, channel=self.name, error=err_str)

        except requests.exceptions.Timeout:
            logger.error("Pushover 发送超时")
            return ChannelResult(success=False, channel=self.name, error="发送超时")
        except Exception as e:
            logger.error(f"Pushover 发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))

    def _send_chunks(self, chunks: List[str], title: str, msg_priority: int) -> ChannelResult:
        total = len(chunks)
        success_count = 0
        last_error: str = ""

        logger.info(f"Pushover 分批发送：共 {total} 批")

        for i, chunk in enumerate(chunks):
            chunk_title = f"{title} ({i + 1}/{total})" if total > 1 else title
            r = self._send_one(chunk, chunk_title, msg_priority)
            if r.success:
                success_count += 1
                logger.info(f"Pushover 第 {i + 1}/{total} 批发送成功")
            else:
                last_error = r.error or "未知错误"
                logger.error(f"Pushover 第 {i + 1}/{total} 批发送失败: {last_error}")

            if i < total - 1:
                time.sleep(_CHUNK_INTERVAL)

        if success_count == total:
            return ChannelResult(
                success=True, channel=self.name, message=f"Pushover 已发送 {total} 批"
            )
        return ChannelResult(
            success=False,
            channel=self.name,
            error=f"分批发送 {success_count}/{total} 成功，最后错误: {last_error}",
        )

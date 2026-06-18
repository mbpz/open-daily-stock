"""飞书 Webhook 通知渠道。

迁自 src/notification.py:send_to_feishu / _send_feishu_chunked /
_send_feishu_force_chunked / _send_feishu_message / _send_feishu_message_with_retry /
_format_feishu_markdown。

核心特性：
- **双 payload 策略**：优先用 interactive 卡片（lark_md 渲染 Markdown），失败回退 text
- **格式预处理** _format_feishu_markdown：飞书 lark_md 不支持完整 Markdown
  - 标题 #/## → 加粗 **text**
  - 引用 > → 💬 前缀
  - --- → ────────
  - 列表 - item → • item
  - 表格 | a | b | → 条目列表 "• 表头：值"
- 智能分块 2 级 fallback：\\n---\\n → \\n###  → 强制按行
- 默认字节上限 20000（可配置）
- tenacity retry 3 次指数退避
- 块间 sleep(1) 防限流
- 分页标记 `📄 (i/N)`（无 wechat 的星号）
- API 响应兼容 `code` 与 `StatusCode` 两种字段（旧/新飞书 API）
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..base import BaseChannel, ChannelPriority, ChannelResult
from .._chunking import get_bytes as _get_bytes, truncate_to_bytes as _truncate_to_bytes

logger = logging.getLogger(__name__)

# 默认字节上限
_DEFAULT_MAX_BYTES = 20000
# 块间间隔（秒）
_CHUNK_INTERVAL = 1.0
# 单 section 强制截断时预留的提示字节
_TRUNCATE_RESERVE = 200
# 强制按行分块时预留给分页标记的字节
_PAGE_MARKER_RESERVE = 100
# 卡片标题
_CARD_HEADER = "A股智能分析报告"


# ─── format Markdown for lark_md ───────────────────────────────


def _format_feishu_markdown(content: str) -> str:
    """将通用 Markdown 转换为飞书 lark_md 更友好的格式。

    迁自 src/notification.py:_format_feishu_markdown。
    """

    def _flush_table_rows(buffer: List[str], output: List[str]) -> None:
        if not buffer:
            return

        def _parse_row(row: str) -> List[str]:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            return [c for c in cells if c]

        rows = []
        for raw in buffer:
            if re.match(r"^\s*\|?\s*[:-]+\s*(\|\s*[:-]+\s*)+\|?\s*$", raw):
                continue
            parsed = _parse_row(raw)
            if parsed:
                rows.append(parsed)

        if not rows:
            return

        header = rows[0]
        data_rows = rows[1:] if len(rows) > 1 else []
        for row in data_rows:
            pairs = []
            for idx, cell in enumerate(row):
                key = header[idx] if idx < len(header) else f"列{idx + 1}"
                pairs.append(f"{key}：{cell}")
            output.append(f"• {' | '.join(pairs)}")

    lines: List[str] = []
    table_buffer: List[str] = []

    for raw_line in content.splitlines():
        line = raw_line.rstrip()

        if line.strip().startswith("|"):
            table_buffer.append(line)
            continue

        if table_buffer:
            _flush_table_rows(table_buffer, lines)
            table_buffer = []

        if re.match(r"^#{1,6}\s+", line):
            title = re.sub(r"^#{1,6}\s+", "", line).strip()
            line = f"**{title}**" if title else ""
        elif line.startswith("> "):
            quote = line[2:].strip()
            line = f"💬 {quote}" if quote else ""
        elif line.strip() == "---":
            line = "────────"
        elif line.startswith("- "):
            line = f"• {line[2:].strip()}"

        lines.append(line)

    if table_buffer:
        _flush_table_rows(table_buffer, lines)

    return "\n".join(lines).strip()


# ─── chunking ──────────────────────────────────────────────────


def _smart_split(content: str) -> Tuple[Optional[List[str]], Optional[str]]:
    """飞书 2 级 smart split：\\n---\\n → \\n### ；都不命中返回 (None, None)。"""
    if "\n---\n" in content:
        return content.split("\n---\n"), "\n---\n"
    if "\n### " in content:
        parts = content.split("\n### ")
        return [parts[0]] + [f"### {p}" for p in parts[1:]], "\n"
    return None, None


def _build_smart_chunks(
    sections: List[str], separator: str, max_bytes: int
) -> List[str]:
    """根据 sections 装箱成 ≤ max_bytes 的 chunk 列表。

    单 section 超长则字节截断 + (本段内容过长已截断) 提示。
    """
    chunks: List[str] = []
    current_chunk: List[str] = []
    current_bytes = 0
    sep_bytes = _get_bytes(separator)

    for section in sections:
        section_bytes = _get_bytes(section) + sep_bytes

        if section_bytes > max_bytes:
            if current_chunk:
                chunks.append(separator.join(current_chunk))
                current_chunk = []
                current_bytes = 0
            truncated = _truncate_to_bytes(section, max_bytes - _TRUNCATE_RESERVE)
            truncated += "\n\n...(本段内容过长已截断)"
            chunks.append(truncated)
            continue

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
    """飞书分页标记 `📄 (i/N)` — 比 wechat 少星号。"""
    if total <= 1:
        return chunk
    return f"{chunk}\n\n📄 ({idx + 1}/{total})"


# ─── Channel ──────────────────────────────────────────────────


class FeishuChannel(BaseChannel):
    """飞书 Webhook 推送（自动选择 interactive 卡片 / text）。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config.get("feishu_webhook_url")
        self.max_bytes = config.get("feishu_max_bytes", _DEFAULT_MAX_BYTES)

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.HIGH

    def send(self, content: str, **kwargs) -> ChannelResult:
        """发送飞书消息（先 interactive 卡片，失败回退 text）。

        kwargs:
            max_bytes: 覆盖默认字节上限（用于测试）
            skip_format: 跳过 _format_feishu_markdown（默认 False）
        """
        if not self.is_configured():
            return ChannelResult(
                success=False, channel=self.name, error="飞书 Webhook 未配置"
            )

        # 1) Markdown → lark_md 友好格式
        if kwargs.get("skip_format", False):
            formatted = content
        else:
            formatted = _format_feishu_markdown(content)

        max_bytes = kwargs.get("max_bytes", self.max_bytes)
        content_bytes = _get_bytes(formatted)

        if content_bytes <= max_bytes:
            return self._send_one(formatted)

        logger.info(
            f"飞书消息超长 ({content_bytes}字节/{len(formatted)}字符)，将分批发送"
        )

        sections, separator = _smart_split(formatted)
        if sections is None:
            chunks = _build_force_chunks(formatted, max_bytes)
        else:
            chunks = _build_smart_chunks(sections, separator or "\n", max_bytes)

        return self._send_chunks(chunks)

    # ─── 单条发送 ──────────────────────────────────────────────

    def _send_one(self, content: str) -> ChannelResult:
        try:
            self._post_with_retry(content)
            return ChannelResult(success=True, channel=self.name, message="飞书已发送")
        except requests.RequestException as e:
            logger.error(f"飞书发送失败（已重试）: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))
        except Exception as e:
            logger.error(f"飞书发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        reraise=True,
    )
    def _post_with_retry(self, content: str) -> None:
        """先 interactive 卡片，失败回退 text；任意一种成功即返回。

        retry 装饰只对**最终**抛出的 RequestException 触发——内部 try/except 让
        卡片失败时静默走 text fallback，不消耗重试次数。
        """
        # 1) 优先交互卡片
        card_payload = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": _CARD_HEADER},
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {"tag": "lark_md", "content": content},
                    }
                ],
            },
        }
        try:
            self._post_payload(card_payload)
            return
        except requests.RequestException as e:
            logger.debug(f"飞书卡片失败，回退 text: {e}")

        # 2) 回退普通文本
        text_payload: Dict[str, Any] = {
            "msg_type": "text",
            "content": {"text": content},
        }
        self._post_payload(text_payload)

    def _post_payload(self, payload: Dict[str, Any]) -> None:
        """单次 HTTP POST；失败 raise RequestException。"""
        response = requests.post(self.webhook_url, json=payload, timeout=30)

        if response.status_code != 200:
            raise requests.RequestException(f"HTTP {response.status_code}")

        result = response.json()
        # API 兼容 code / StatusCode
        code = result.get("code") if "code" in result else result.get("StatusCode")
        if code != 0:
            err_msg = result.get("msg") or result.get("StatusMessage", "未知错误")
            err_code = result.get("code") or result.get("StatusCode", "N/A")
            raise requests.RequestException(f"飞书返回错误 [code={err_code}]: {err_msg}")

    # ─── 分批发送 ──────────────────────────────────────────────

    def _send_chunks(self, chunks: List[str]) -> ChannelResult:
        total = len(chunks)
        success_count = 0
        last_error = ""

        logger.info(f"飞书分批发送：共 {total} 批")

        for i, chunk in enumerate(chunks):
            chunk_with_marker = _add_page_marker(chunk, i, total)
            r = self._send_one(chunk_with_marker)
            if r.success:
                success_count += 1
                logger.info(f"飞书第 {i + 1}/{total} 批发送成功")
            else:
                last_error = r.error or "未知错误"
                logger.error(f"飞书第 {i + 1}/{total} 批发送失败: {last_error}")

            if i < total - 1:
                time.sleep(_CHUNK_INTERVAL)

        if success_count == total:
            return ChannelResult(
                success=True, channel=self.name, message=f"飞书已发送 {total} 批"
            )
        return ChannelResult(
            success=False,
            channel=self.name,
            error=f"分批发送 {success_count}/{total} 成功，最后错误: {last_error}",
        )

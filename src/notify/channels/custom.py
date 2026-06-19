"""自定义 Webhook 通知渠道（含 DingTalk 分块、payload 自适应、Bearer Token）。

迁自 src/notification.py:send_to_custom / _is_dingtalk_webhook /
_post_custom_webhook / _post_custom_webhook_with_retry / _chunk_markdown_by_bytes /
_send_dingtalk_chunked / _build_custom_webhook_payload。

核心特性：
- **多 URL 循环**：遍历 `custom_webhook_urls`，至少一个成功视为整体成功
- **payload 自适应**：根据 URL 识别 DingTalk / Discord / Slack / Bark，否则发通用多键
  payload `{text, content, message, body}` 兼容大多数服务
- **DingTalk 分块**：URL 包含 dingtalk → 字节级分块（默认 20000 max_bytes，预留 1500
  字节给 payload 开销）+ 3 级 separator fallback（--- / ### / 按行）+ 兜底字节切分
- **Bearer Token**：`custom_webhook_bearer_token` → `Authorization: Bearer xxx`
- **tenacity retry** 3 次指数退避
- 自定义 Headers：Content-Type / User-Agent
- POST body 用 `json.dumps(ensure_ascii=False)` 手编码避免 ASCII 转义
- 旧实现"成功条件"：success_count > 0（至少一个）— 新版保留
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List

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

# DingTalk 默认字节上限（含 payload 开销）
_DINGTALK_MAX_BYTES = 20000
# DingTalk payload 开销预留
_DINGTALK_PAYLOAD_OVERHEAD = 1500
# DingTalk 块间间隔
_DINGTALK_CHUNK_INTERVAL = 1.0
# 单 section 兜底字节切分时预留
_TRUNCATE_RESERVE = 200
# Discord webhook 字符上限（旧实现 1900 留余量）
_DISCORD_TRUNCATE = 1900
# Bark 字符上限
_BARK_TRUNCATE = 4000
# 默认请求超时
_DEFAULT_TIMEOUT = 30
# 单条请求 Headers
_REQUEST_HEADERS_BASE = {
    "Content-Type": "application/json; charset=utf-8",
    "User-Agent": "StockAnalysis/1.0",
}


# ─── URL 识别 ──────────────────────────────────────────────────


def _is_dingtalk_webhook(url: str) -> bool:
    url_lower = (url or "").lower()
    return "dingtalk" in url_lower or "oapi.dingtalk.com" in url_lower


def _is_discord_webhook(url: str) -> bool:
    url_lower = (url or "").lower()
    return "discord.com/api/webhooks" in url_lower or "discordapp.com/api/webhooks" in url_lower


def _is_slack_webhook(url: str) -> bool:
    return "hooks.slack.com" in (url or "").lower()


def _is_bark_webhook(url: str) -> bool:
    return "api.day.app" in (url or "").lower()


def _build_payload(url: str, content: str) -> Dict[str, Any]:
    """根据 URL 识别 + 构建对应服务的 payload。

    迁自 src/notification.py:_build_custom_webhook_payload。
    """
    if _is_dingtalk_webhook(url):
        return {
            "msgtype": "markdown",
            "markdown": {"title": "股票分析报告", "text": content},
        }
    if _is_discord_webhook(url):
        truncated = content[:_DISCORD_TRUNCATE] + "..." if len(content) > _DISCORD_TRUNCATE else content
        return {"content": truncated}
    if _is_slack_webhook(url):
        return {"text": content, "mrkdwn": True}
    if _is_bark_webhook(url):
        return {"title": "股票分析报告", "body": content[:_BARK_TRUNCATE], "group": "stock"}
    # 通用：多键兼容
    return {"text": content, "content": content, "message": content, "body": content}


# ─── DingTalk 分块 ────────────────────────────────────────────


def _split_by_bytes(text: str, limit: int) -> List[str]:
    """按字节硬切分（多字节字符安全）— 兜底用，避免无 separator 的整段被丢失。"""
    parts: List[str] = []
    remaining = text
    while remaining:
        part = _truncate_to_bytes(remaining, limit)
        if not part:
            break
        parts.append(part)
        remaining = remaining[len(part):]
    return parts


def _chunk_markdown_by_bytes(content: str, max_bytes: int) -> List[str]:
    """DingTalk 专用 3 级 fallback 分块：--- → ### → 按行。

    迁自 src/notification.py:_chunk_markdown_by_bytes。
    """
    if "\n---\n" in content:
        sections = content.split("\n---\n")
        separator = "\n---\n"
    elif "\n### " in content:
        parts = content.split("\n### ")
        sections = [parts[0]] + [f"### {p}" for p in parts[1:]]
        separator = "\n"
    else:
        sections = content.split("\n")
        separator = "\n"

    chunks: List[str] = []
    current: List[str] = []
    current_bytes = 0
    sep_bytes = _get_bytes(separator)

    for section in sections:
        section_bytes = _get_bytes(section)
        extra = sep_bytes if current else 0

        # 单段超长 → flush 当前 + 字节硬切
        if section_bytes + extra > max_bytes:
            if current:
                chunks.append(separator.join(current))
                current = []
                current_bytes = 0
            for part in _split_by_bytes(section, max(_TRUNCATE_RESERVE, max_bytes - _TRUNCATE_RESERVE)):
                chunks.append(part)
            continue

        if current_bytes + section_bytes + extra > max_bytes:
            chunks.append(separator.join(current))
            current = [section]
            current_bytes = section_bytes
        else:
            if current:
                current_bytes += sep_bytes
            current.append(section)
            current_bytes += section_bytes

    if current:
        chunks.append(separator.join(current))

    # 移除空块
    return [c for c in (c.strip() for c in chunks) if c]


# ─── Channel ──────────────────────────────────────────────────


class CustomChannel(BaseChannel):
    """自定义 Webhook 通知。"""

    def __init__(self, config: dict):
        super().__init__(config)
        urls = config.get("custom_webhook_urls", []) or []
        self.webhook_urls: List[str] = list(urls) if isinstance(urls, list) else [str(urls)]
        self.bearer_token = config.get("custom_webhook_bearer_token")

    def is_configured(self) -> bool:
        return bool(self.webhook_urls)

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.LOW

    def send(self, content: str, **kwargs) -> ChannelResult:
        """遍历所有 URL 发送；至少一个成功视为整体成功（保留旧语义）。"""
        if not self.is_configured():
            return ChannelResult(
                success=False, channel=self.name, error="自定义 Webhook 未配置"
            )

        success_count = 0
        last_error = ""
        total = len(self.webhook_urls)

        for i, url in enumerate(self.webhook_urls):
            try:
                if _is_dingtalk_webhook(url):
                    ok, err = self._send_dingtalk_chunked(url, content)
                else:
                    payload = _build_payload(url, content)
                    ok, err = self._post(url, payload)

                if ok:
                    logger.info(f"自定义 Webhook {i + 1}/{total} 推送成功 ({url[:50]})")
                    success_count += 1
                else:
                    last_error = err
                    logger.error(f"自定义 Webhook {i + 1}/{total} 推送失败: {err}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"自定义 Webhook {i + 1}/{total} 推送异常: {e}")

        if success_count > 0:
            return ChannelResult(
                success=True,
                channel=self.name,
                message=f"自定义 Webhook 推送 {success_count}/{total} 成功",
            )
        return ChannelResult(
            success=False,
            channel=self.name,
            error=f"所有 {total} 个 Webhook 推送失败，最后错误: {last_error}",
        )

    # ─── 通用 POST ─────────────────────────────────────────────

    def _post(self, url: str, payload: Dict[str, Any]) -> tuple[bool, str]:
        """单次 POST + retry。返回 (success, error_str)。"""
        try:
            self._post_with_retry(url, payload)
            return True, ""
        except requests.RequestException as e:
            return False, str(e)
        except Exception as e:
            return False, str(e)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((requests.RequestException, ConnectionError)),
        reraise=True,
    )
    def _post_with_retry(self, url: str, payload: Dict[str, Any]) -> None:
        headers = dict(_REQUEST_HEADERS_BASE)
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        # 手编码避免 ensure_ascii=True 把中文字符转义成 \\uXXXX
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        response = requests.post(url, data=body, headers=headers, timeout=_DEFAULT_TIMEOUT)

        if response.status_code != 200:
            raise requests.RequestException(f"HTTP {response.status_code}")

    # ─── DingTalk 分块路径 ──────────────────────────────────────

    def _send_dingtalk_chunked(self, url: str, content: str) -> tuple[bool, str]:
        """分批发送 DingTalk Markdown 消息。返回 (all_success, last_error)。"""
        budget = max(1000, _DINGTALK_MAX_BYTES - _DINGTALK_PAYLOAD_OVERHEAD)
        chunks = _chunk_markdown_by_bytes(content, budget)
        if not chunks:
            return False, "分块后无内容"

        total = len(chunks)
        ok_count = 0
        last_error = ""

        for idx, chunk in enumerate(chunks):
            marker = f"\n\n📄 *({idx + 1}/{total})*" if total > 1 else ""
            payload: Dict[str, Any] = {
                "msgtype": "markdown",
                "markdown": {"title": "股票分析报告", "text": chunk + marker},
            }

            # 极端情况：payload 仍超 _DINGTALK_MAX_BYTES → 二次硬截断
            body_bytes = len(json.dumps(payload, ensure_ascii=False).encode("utf-8"))
            if body_bytes > _DINGTALK_MAX_BYTES:
                hard_budget = max(
                    _TRUNCATE_RESERVE, budget - (body_bytes - _DINGTALK_MAX_BYTES) - _TRUNCATE_RESERVE
                )
                payload["markdown"]["text"] = _truncate_to_bytes(
                    payload["markdown"]["text"], hard_budget
                )

            ok, err = self._post(url, payload)
            if ok:
                ok_count += 1
            else:
                last_error = err
                logger.error(f"钉钉分批 {idx + 1}/{total} 失败: {err}")

            if idx < total - 1:
                time.sleep(_DINGTALK_CHUNK_INTERVAL)

        return ok_count == total, last_error

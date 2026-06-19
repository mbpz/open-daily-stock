"""Discord 通知渠道（Webhook 与 Bot API 双模式）。

迁自 src/notification.py:send_to_discord / _send_discord_webhook /
_send_discord_bot。

核心特性：
- **双模式**：优先 Webhook（配置简单），fallback 到 Bot API（权限高，需 channel_id）
- Webhook payload 含 username + avatar_url 自定义机器人显示
- Bot API 使用 `Authorization: Bot <token>` header 调 v10 API
- 接受 Markdown 内容（Discord 原生支持）
"""
from __future__ import annotations

import logging

import requests

from ..base import BaseChannel, ChannelPriority, ChannelResult

logger = logging.getLogger(__name__)

# Webhook 默认显示
_BOT_USERNAME = "A股分析机器人"
_BOT_AVATAR = "https://picsum.photos/200"


class DiscordChannel(BaseChannel):
    """Discord 通知（Webhook 优先 / Bot API 回退）。"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config.get("discord_webhook_url")
        self.bot_token = config.get("discord_bot_token")
        self.channel_id = config.get("discord_main_channel_id") or config.get(
            "discord_channel_id"
        )

    def is_configured(self) -> bool:
        return self._has_webhook() or self._has_bot()

    def _has_webhook(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    def _has_bot(self) -> bool:
        return bool(self.bot_token and self.channel_id)

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.LOW

    def send(self, content: str, **kwargs) -> ChannelResult:
        """优先 Webhook，fallback 到 Bot API。"""
        if self._has_webhook():
            return self._send_webhook(content)
        if self._has_bot():
            return self._send_bot(content)
        return ChannelResult(
            success=False,
            channel=self.name,
            error="Discord 未配置（需 webhook_url 或 bot_token + channel_id）",
        )

    # ─── Webhook ───────────────────────────────────────────────

    def _send_webhook(self, content: str) -> ChannelResult:
        try:
            payload = {
                "content": content,
                "username": _BOT_USERNAME,
                "avatar_url": _BOT_AVATAR,
            }
            response = requests.post(self.webhook_url, json=payload, timeout=10)

            if response.status_code in (200, 204):
                return ChannelResult(
                    success=True, channel=self.name, message="Discord Webhook 已发送"
                )
            err = f"HTTP {response.status_code}"
            try:
                err += f" {response.text[:200]}"
            except Exception:
                pass
            logger.error(f"Discord Webhook 发送失败: {err}")
            return ChannelResult(success=False, channel=self.name, error=err)

        except requests.exceptions.Timeout:
            logger.error("Discord Webhook 发送超时")
            return ChannelResult(success=False, channel=self.name, error="发送超时")
        except Exception as e:
            logger.error(f"Discord Webhook 发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))

    # ─── Bot API ──────────────────────────────────────────────

    def _send_bot(self, content: str) -> ChannelResult:
        try:
            headers = {
                "Authorization": f"Bot {self.bot_token}",
                "Content-Type": "application/json",
            }
            url = f"https://discord.com/api/v10/channels/{self.channel_id}/messages"
            response = requests.post(url, json={"content": content}, headers=headers, timeout=10)

            if response.status_code == 200:
                return ChannelResult(
                    success=True, channel=self.name, message="Discord Bot 已发送"
                )
            err = f"HTTP {response.status_code}"
            try:
                err += f" {response.text[:200]}"
            except Exception:
                pass
            logger.error(f"Discord Bot 发送失败: {err}")
            return ChannelResult(success=False, channel=self.name, error=err)

        except requests.exceptions.Timeout:
            logger.error("Discord Bot 发送超时")
            return ChannelResult(success=False, channel=self.name, error="发送超时")
        except Exception as e:
            logger.error(f"Discord Bot 发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))

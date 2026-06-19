"""通知分发器。

根据配置初始化所有已知渠道，提供 send / send_to_channel / 状态查询。
迁自 src/notification.py:NotificationService.send() 的逐渠道循环逻辑。
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List

from .base import ChannelResult, BaseChannel
from .channels import (
    CustomChannel,
    DiscordChannel,
    EmailChannel,
    FeishuChannel,
    PushoverChannel,
    PushPlusChannel,
    TelegramChannel,
    WechatChannel,
    WindowsToastChannel,
)

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """根据配置实例化所有 9 个渠道，提供统一分发。"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._channels: Dict[str, BaseChannel] = {}  # key → channel 实例
        self._init_channels()

    def _init_channels(self) -> None:
        # 企业微信
        if self.config.get("wechat_webhook_url"):
            self._channels["wechat"] = WechatChannel(self.config)

        # 飞书
        if self.config.get("feishu_webhook_url"):
            self._channels["feishu"] = FeishuChannel(self.config)

        # Telegram
        if self.config.get("telegram_bot_token") and self.config.get("telegram_chat_id"):
            self._channels["telegram"] = TelegramChannel(self.config)

        # 邮件
        if self.config.get("email_sender") and self.config.get("email_password"):
            self._channels["email"] = EmailChannel(self.config)

        # Discord（webhook 或 bot 任意一者即可）
        if (
            self.config.get("discord_webhook_url")
            or (
                self.config.get("discord_bot_token")
                and (self.config.get("discord_main_channel_id") or self.config.get("discord_channel_id"))
            )
        ):
            self._channels["discord"] = DiscordChannel(self.config)

        # Pushover
        if self.config.get("pushover_user_key") and self.config.get("pushover_api_token"):
            self._channels["pushover"] = PushoverChannel(self.config)

        # PushPlus
        if self.config.get("pushplus_token"):
            self._channels["pushplus"] = PushPlusChannel(self.config)

        # 自定义 Webhook
        custom_urls = self.config.get("custom_webhook_urls", []) or []
        if custom_urls:
            self._channels["custom"] = CustomChannel(self.config)

        # Windows Toast（平台门控在 channel 内部）
        self._channels["windows"] = WindowsToastChannel(self.config)

        logger.info(f"已初始化 {len(self._channels)} 个通知渠道")

    # ─── 状态查询（for NotificationService facade） ────────────

    @property
    def configured_channels(self) -> Dict[str, BaseChannel]:
        """返回已实例化的渠道 dict（key → channel）。"""
        return self._channels

    def configured_channel_names(self) -> List[str]:
        """返回已配置的渠道 key 列表。"""
        return list(self._channels.keys())

    def has_channel(self, name: str) -> bool:
        """指定 key 的渠道是否已配置。"""
        return (name or "").lower() in self._channels

    # ─── 分发 ──────────────────────────────────────────────────

    def send(self, content: str, **kwargs) -> List[ChannelResult]:
        """向所有已配置渠道发送。"""
        results: List[ChannelResult] = []
        for key, channel in self._channels.items():
            if not channel.is_configured():
                logger.debug(f"渠道 {key} 未配置，跳过")
                continue
            result = channel.send(content, **kwargs)
            results.append(result)
            if result.success:
                logger.info(f"[{key}] 发送成功")
            else:
                logger.warning(f"[{key}] 发送失败: {result.error}")
        return results

    def send_to_channel(self, channel_name: str, content: str, **kwargs) -> ChannelResult:
        """向指定渠道发送（按 ALL_CHANNELS key 匹配）。"""
        key = (channel_name or "").lower()
        if key not in self._channels:
            return ChannelResult(success=False, channel=key, error=f"渠道 '{channel_name}' 未配置或不存在")
        channel = self._channels[key]
        if not channel.is_configured():
            return ChannelResult(success=False, channel=key, error=f"渠道 '{channel_name}' 配置不完整")
        return channel.send(content, **kwargs)

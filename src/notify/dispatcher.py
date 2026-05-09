"""通知分发器"""
import logging
from typing import List, Dict, Any
from .base import ChannelResult
from .channels import (
    WechatChannel,
    FeishuChannel,
    TelegramChannel,
    EmailChannel,
    DiscordChannel,
    CustomChannel,
)

logger = logging.getLogger(__name__)


class NotificationDispatcher:
    """
    通知分发器

    根据配置初始化所有渠道，send() 时向所有渠道发送。
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.channels: List = []
        self._init_channels()

    def _init_channels(self):
        """根据配置初始化所有渠道"""
        # 企业微信
        if self.config.get("wechat_webhook_url"):
            self.channels.append(WechatChannel(self.config))

        # 飞书
        if self.config.get("feishu_webhook_url"):
            self.channels.append(FeishuChannel(self.config))

        # Telegram
        if self.config.get("telegram_bot_token") and self.config.get("telegram_chat_id"):
            self.channels.append(TelegramChannel(self.config))

        # 邮件
        if self.config.get("email_sender") and self.config.get("email_password"):
            self.channels.append(EmailChannel(self.config))

        # Discord
        if self.config.get("discord_webhook_url"):
            self.channels.append(DiscordChannel(self.config))

        # 自定义 Webhook
        custom_urls = self.config.get("custom_webhook_urls", [])
        if custom_urls:
            self.channels.append(CustomChannel(self.config))

        logger.info(f"已初始化 {len(self.channels)} 个通知渠道")

    def send(self, content: str, **kwargs) -> List[ChannelResult]:
        """
        向所有已配置渠道发送通知

        Args:
            content: 通知内容（Markdown）
            **kwargs: 额外参数传递给各渠道

        Returns:
            List[ChannelResult]: 各渠道发送结果
        """
        results = []
        for channel in self.channels:
            if not channel.is_configured():
                logger.debug(f"渠道 {channel.name} 未配置，跳过")
                continue

            result = channel.send(content, **kwargs)
            results.append(result)

            if result.success:
                logger.info(f"[{channel.name}] 发送成功")
            else:
                logger.warning(f"[{channel.name}] 发送失败: {result.error}")

        return results

    def send_to_channel(self, channel_name: str, content: str, **kwargs) -> ChannelResult:
        """向指定渠道发送"""
        for channel in self.channels:
            if channel.__class__.__name__.lower() == channel_name.lower():
                return channel.send(content, **kwargs)
        return ChannelResult(success=False, channel=channel_name, error="渠道不存在")
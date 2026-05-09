"""Discord Webhook 通知渠道"""
import logging
import requests
from ..base import BaseChannel, ChannelResult, ChannelPriority

logger = logging.getLogger(__name__)


class DiscordChannel(BaseChannel):
    """Discord Webhook 通知"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config.get("discord_webhook_url")

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.LOW

    def send(self, content: str, **kwargs) -> ChannelResult:
        if not self.is_configured():
            return ChannelResult(success=False, channel=self.name, error="Discord Webhook 未配置")

        try:
            payload = {"content": content}
            response = requests.post(self.webhook_url, json=payload, timeout=10)

            if response.status_code in (200, 204):
                return ChannelResult(success=True, channel=self.name)
            else:
                return ChannelResult(success=False, channel=self.name, error=f"HTTP {response.status_code}")

        except requests.exceptions.Timeout:
            logger.error("Discord 发送超时")
            return ChannelResult(success=False, channel=self.name, error="发送超时")
        except Exception as e:
            logger.error(f"Discord 发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))
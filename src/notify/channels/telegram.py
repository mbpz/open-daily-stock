"""Telegram Bot 通知渠道"""
import logging
import requests
from ..base import BaseChannel, ChannelResult, ChannelPriority

logger = logging.getLogger(__name__)


class TelegramChannel(BaseChannel):
    """Telegram Bot 通知"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.bot_token = config.get("telegram_bot_token")
        self.chat_id = config.get("telegram_chat_id")

    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.HIGH

    def send(self, content: str, **kwargs) -> ChannelResult:
        if not self.is_configured():
            return ChannelResult(success=False, channel=self.name, error="Telegram 未配置")

        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {"chat_id": self.chat_id, "text": content, "parse_mode": "Markdown"}
            response = requests.post(url, json=payload, timeout=10)

            if response.status_code == 200:
                result = response.json()
                if result.get("ok"):
                    return ChannelResult(success=True, channel=self.name)
                else:
                    return ChannelResult(success=False, channel=self.name, error=result.get("description", "发送失败"))
            else:
                return ChannelResult(success=False, channel=self.name, error=f"HTTP {response.status_code}")

        except requests.exceptions.Timeout:
            logger.error("Telegram 发送超时")
            return ChannelResult(success=False, channel=self.name, error="发送超时")
        except Exception as e:
            logger.error(f"Telegram 发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))
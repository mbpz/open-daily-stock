"""飞书 Webhook 通知渠道"""
import logging
import requests
from ..base import BaseChannel, ChannelResult, ChannelPriority

logger = logging.getLogger(__name__)


class FeishuChannel(BaseChannel):
    """飞书 Webhook 通知"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_url = config.get("feishu_webhook_url")

    def is_configured(self) -> bool:
        return bool(self.webhook_url and self.webhook_url.startswith("http"))

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.HIGH

    def send(self, content: str, **kwargs) -> ChannelResult:
        if not self.is_configured():
            return ChannelResult(success=False, channel=self.name, error="飞书 Webhook 未配置")

        try:
            payload = {
                "msg_type": "interactive",
                "card": {
                    "config": {"wide_screen_mode": True},
                    "elements": [{"tag": "markdown", "content": content}]
                }
            }

            response = requests.post(self.webhook_url, json=payload, timeout=10)
            result = response.json()

            if response.status_code == 200 and result.get("code", 0) == 0:
                return ChannelResult(success=True, channel=self.name)
            else:
                return ChannelResult(success=False, channel=self.name, error=result.get("msg", "发送失败"))

        except requests.exceptions.Timeout:
            logger.error("飞书发送超时")
            return ChannelResult(success=False, channel=self.name, error="发送超时")
        except Exception as e:
            logger.error(f"飞书发送异常: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))
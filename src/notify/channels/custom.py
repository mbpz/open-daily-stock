"""自定义 Webhook 通知渠道"""
import logging
import requests
from ..base import BaseChannel, ChannelResult, ChannelPriority

logger = logging.getLogger(__name__)


class CustomChannel(BaseChannel):
    """自定义 Webhook 通知"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.webhook_urls = config.get("custom_webhook_urls", [])
        self.bearer_token = config.get("custom_webhook_bearer_token")

    def is_configured(self) -> bool:
        return bool(self.webhook_urls and len(self.webhook_urls) > 0)

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.LOW

    def send(self, content: str, **kwargs) -> ChannelResult:
        if not self.is_configured():
            return ChannelResult(success=False, channel=self.name, error="自定义 Webhook 未配置")

        results = []
        headers = {}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        for url in self.webhook_urls:
            try:
                response = requests.post(
                    url,
                    json={"text": content},
                    headers=headers,
                    timeout=10,
                )

                if response.status_code in (200, 204):
                    results.append(True)
                else:
                    results.append(False)

            except Exception as e:
                logger.error(f"自定义 Webhook 发送异常 [{url}]: {e}")
                results.append(False)

        success = all(results) if results else False
        if success:
            return ChannelResult(success=True, channel=self.name, message=f"已发送至 {len(self.webhook_urls)} 个 Webhook")
        else:
            return ChannelResult(success=False, channel=self.name, error="部分 Webhook 发送失败")
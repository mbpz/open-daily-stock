"""自定义 Webhook 通知渠道"""
from ..base import BaseChannel, ChannelResult

class CustomChannel(BaseChannel):
    def send(self, content: str, **kwargs) -> ChannelResult:
        return ChannelResult(success=False, channel=self.name, error="not implemented")
"""通知调度器"""
from typing import List
from .base import BaseChannel, ChannelResult, ChannelPriority


class NotificationDispatcher:
    """通知调度器"""

    def __init__(self):
        self.channels: List[BaseChannel] = []

    def add_channel(self, channel: BaseChannel):
        self.channels.append(channel)

    def dispatch(self, content: str) -> List[ChannelResult]:
        results = []
        for channel in self.channels:
            results.append(channel.send(content))
        return results
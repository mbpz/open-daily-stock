"""通知模块 - 重构后版本"""
from .base import BaseChannel, ChannelResult, ChannelPriority
from .dispatcher import NotificationDispatcher

__all__ = [
    "BaseChannel",
    "ChannelResult",
    "ChannelPriority",
    "NotificationDispatcher",
]
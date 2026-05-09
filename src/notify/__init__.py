"""通知模块 - 重构后版本"""
from .base import BaseChannel, ChannelResult, ChannelPriority
from .dispatcher import NotificationDispatcher
from .formatters import MarkdownFormatter, SimpleFormatter, DashboardFormatter

__all__ = [
    "BaseChannel",
    "ChannelResult",
    "ChannelPriority",
    "NotificationDispatcher",
    "MarkdownFormatter",
    "SimpleFormatter",
    "DashboardFormatter",
]
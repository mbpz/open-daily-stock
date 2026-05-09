"""通知模块 - 重构后版本"""
from .base import BaseChannel, ChannelResult, ChannelPriority
from .dispatcher import NotificationDispatcher
from .formatters import MarkdownFormatter, SimpleFormatter, DashboardFormatter

# For backward compatibility, re-export NotificationChannel from original location
try:
    from src.notification import NotificationChannel
except ImportError:
    pass  # Not available in old versions

__all__ = [
    "BaseChannel",
    "ChannelResult",
    "ChannelPriority",
    "NotificationDispatcher",
    "MarkdownFormatter",
    "SimpleFormatter",
    "DashboardFormatter",
]
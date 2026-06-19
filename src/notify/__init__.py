"""通知模块 - 重构后版本

新代码请使用：
    from src.notify import (
        NotificationDispatcher,      # 多渠道统一派发
        BaseChannel, ChannelResult, # 渠道基类
        MarkdownFormatter,          # 报告格式化
        NotificationChannel,        # 渠道类型 enum
        BotMessage,                 # Bot 消息结构
    )

旧 API（src.notification.NotificationService）仍可用但已 deprecated，
会被自动转发到新实现并发出 DeprecationWarning。详见
docs/adr/ADR-006-notification-migration.md。
"""
from .base import BaseChannel, ChannelResult, ChannelPriority
from .dispatcher import NotificationDispatcher
from .formatters import MarkdownFormatter, SimpleFormatter, DashboardFormatter
from ._legacy import NotificationChannel, BotMessage

__all__ = [
    "BaseChannel",
    "ChannelResult",
    "ChannelPriority",
    "NotificationDispatcher",
    "MarkdownFormatter",
    "SimpleFormatter",
    "DashboardFormatter",
    "NotificationChannel",
    "BotMessage",
]

"""通知模块 — P0-2 重构完版。

全部入口由 src/notify/ 提供：
- 生产代码用 NotificationService facade（统一分发 + 状态查询）
- 类型导入用 types 模块（BotMessage / NotificationChannel / ChannelDetector）
- 报告生成用 reports 模块（5 个 generate_* 函数）
- 渠道注册用 channels/__init__.py 的 ALL_CHANNELS

旧 src.notification 文件将在迁移完成后删除。
"""
from .base import BaseChannel, ChannelPriority, ChannelResult
from .builder import NotificationBuilder
from .channels import ALL_CHANNELS
from .dispatcher import NotificationDispatcher
from .formatters import MarkdownFormatter, SimpleFormatter, DashboardFormatter
from .reports import (
    generate_daily_report,
    generate_dashboard_report,
    generate_single_stock_report,
    generate_wechat_dashboard,
    generate_wechat_summary,
)
from .service import NotificationService
from .singletons import get_notification_service, send_daily_report
from .types import BotMessage, ChannelDetector, NotificationChannel

__all__ = [
    # facade
    "NotificationService",
    "NotificationDispatcher",
    # singletons
    "get_notification_service",
    "send_daily_report",
    # types
    "BotMessage",
    "NotificationChannel",
    "ChannelDetector",
    # channels
    "ALL_CHANNELS",
    "BaseChannel",
    "ChannelPriority",
    "ChannelResult",
    # formatters
    "MarkdownFormatter",
    "SimpleFormatter",
    "DashboardFormatter",
    # reports
    "generate_daily_report",
    "generate_dashboard_report",
    "generate_wechat_dashboard",
    "generate_wechat_summary",
    "generate_single_stock_report",
    # builder
    "NotificationBuilder",
]

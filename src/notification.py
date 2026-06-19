# -*- coding: utf-8 -*-
"""DEPRECATED — 全部实现已迁至 ``src.notify``。

本文件保留作向后兼容 shim。所有 import 均从 src.notify 重新导出。
新代码请直接 from src.notify import ...。

将在 v0.7 删除本文件。
"""
from src.notify.builder import NotificationBuilder
from src.notify.channels.email import SMTP_CONFIGS  # noqa: F401
from src.notify.service import NotificationService
from src.notify.singletons import get_notification_service, send_daily_report
from src.notify.types import BotMessage, ChannelDetector, NotificationChannel

# 通知 channel 实现已迁至 src/notify/channels/，不支持从此文件导入各 channel 类。
# 如需枚举所有 channel 实例 from src.notify.channels import ALL_CHANNELS。

__all__ = [
    "NotificationService",
    "BotMessage",
    "NotificationChannel",
    "ChannelDetector",
    "SMTP_CONFIGS",
    "NotificationBuilder",
    "get_notification_service",
    "send_daily_report",
]

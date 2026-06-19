"""向后兼容 shim — 实际定义已迁至 src.notify.types。

本文件保留以便已 import 此路径的调用方不改动。将在 v0.7 删除。
"""
from .types import BotMessage, NotificationChannel  # noqa: F401

__all__ = ["NotificationChannel", "BotMessage"]

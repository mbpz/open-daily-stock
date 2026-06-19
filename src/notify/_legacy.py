"""Lightweight types migrated from the legacy ``src.notification`` monolith.

These are the only two types callers actually import directly:
  - :class:`NotificationChannel` — enum of channel names
  - :class:`BotMessage` — dataclass for bot message payloads

The full :class:`NotificationService` (3000+ LOC) still lives in
``src.notification`` and is deprecated. Migrating it is tracked in
``docs/adr/ADR-006-notification-migration.md`` (P7-5).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class NotificationChannel(Enum):
    """通知渠道类型 — single source of truth."""
    WECHAT = "wechat"
    FEISHU = "feishu"
    TELEGRAM = "telegram"
    EMAIL = "email"
    PUSHOVER = "pushover"
    PUSHPLUS = "pushplus"
    CUSTOM = "custom"
    DISCORD = "discord"
    WINDOWS = "windows"
    UNKNOWN = "unknown"


@dataclass
class BotMessage:
    """通知消息结构"""
    content: str = ""
    html_content: str = ""
    image_paths: List[str] = field(default_factory=list)
    mention_list: List[str] = field(default_factory=list)


__all__ = ["NotificationChannel", "BotMessage"]

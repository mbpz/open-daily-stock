"""通知层共享数据类型与契约。

迁自 src/notification.py：
- `BotMessage` (L56) — 反向回复入参（钉钉/飞书 Bot Stream 模式触发任务时携带）
- `NotificationChannel` Enum (L72) — 渠道身份枚举，pipeline.py 用作 per-channel 比较 key
- `ChannelDetector` (L111) — Enum → 中文名映射

**架构定位**：本模块只放"非分发"职责的纯数据类型 / 契约——任何依赖通知层的代码
（如 `core/pipeline.py` / `core/market_review.py`）都通过此模块拿到稳定的 enum 与
dataclass，不必导入具体 channel 实现。

`SMTP_CONFIGS` 不在这里：它是邮件 channel 的实现细节，留在 `channels/email.py`。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


# ─── BotMessage ────────────────────────────────────────────────


@dataclass
class BotMessage:
    """通知反向回复入参。

    用于从钉钉/飞书 Bot Stream 模式触发的分析任务——把分析结果回送到原会话上下文
    （而不是默认发到管理员配置的目标）。

    迁自 src/notification.py:56-67。
    """

    content: str = ""
    html_content: str = ""
    image_paths: List[str] = field(default_factory=list)
    mention_list: List[str] = field(default_factory=list)


# ─── NotificationChannel Enum ─────────────────────────────────


class NotificationChannel(Enum):
    """通知渠道身份枚举（10 个成员）。

    pipeline.py 用 `NotificationChannel.WECHAT in channels` 之类比较；新代码
    应优先用 channel 类名字符串（与 ALL_CHANNELS key 对应），但此 Enum 保留作
    向后兼容契约。
    """

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


# ─── ChannelDetector ──────────────────────────────────────────


# 渠道中文显示名（迁自 src/notification.py:121-133 的 ChannelDetector.get_channel_name）
_CHANNEL_DISPLAY_NAMES: Dict[NotificationChannel, str] = {
    NotificationChannel.WECHAT: "企业微信",
    NotificationChannel.FEISHU: "飞书",
    NotificationChannel.TELEGRAM: "Telegram",
    NotificationChannel.EMAIL: "邮件",
    NotificationChannel.PUSHOVER: "Pushover",
    NotificationChannel.PUSHPLUS: "PushPlus",
    NotificationChannel.CUSTOM: "自定义Webhook",
    NotificationChannel.DISCORD: "Discord机器人",
    NotificationChannel.WINDOWS: "Windows通知",
    NotificationChannel.UNKNOWN: "未知渠道",
}


class ChannelDetector:
    """渠道工具类（保留旧 staticmethod API 形态便于调用方零改动）。"""

    @staticmethod
    def get_channel_name(channel: NotificationChannel) -> str:
        """获取渠道中文名。"""
        return _CHANNEL_DISPLAY_NAMES.get(channel, "未知渠道")


# ─── 名称 ↔ Enum 映射（新代码用） ───────────────────────────


# channel 类名字符串到 Enum 的映射（与 src/notify/channels/__init__.py:ALL_CHANNELS
# 的 key 对齐）。新代码倾向于用字符串 key（去除对 Enum 的硬依赖），此 dict 提供两者
# 互转的桥梁。
_CHANNEL_KEY_TO_ENUM: Dict[str, NotificationChannel] = {
    "wechat": NotificationChannel.WECHAT,
    "feishu": NotificationChannel.FEISHU,
    "telegram": NotificationChannel.TELEGRAM,
    "email": NotificationChannel.EMAIL,
    "pushover": NotificationChannel.PUSHOVER,
    "pushplus": NotificationChannel.PUSHPLUS,
    "custom": NotificationChannel.CUSTOM,
    "discord": NotificationChannel.DISCORD,
    "windows": NotificationChannel.WINDOWS,
}


def channel_from_key(key: str) -> Optional[NotificationChannel]:
    """字符串 key → NotificationChannel；未知 key 返回 None。"""
    return _CHANNEL_KEY_TO_ENUM.get((key or "").lower())


def channel_to_key(channel: NotificationChannel) -> str:
    """NotificationChannel → 字符串 key（即 Enum.value）。"""
    return channel.value

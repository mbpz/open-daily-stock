"""通知渠道模块"""
from .custom import CustomChannel
from .discord import DiscordChannel
from .email import EmailChannel
from .feishu import FeishuChannel
from .pushover import PushoverChannel
from .pushplus import PushPlusChannel
from .telegram import TelegramChannel
from .wechat import WechatChannel
from .windows import WindowsToastChannel

# 渠道注册表 — plugin_manager 用此枚举所有可用渠道。
# key 是稳定的短名称（用于 config 配置 / plugin 注册），与各 BaseChannel 子类
# 内 `is_configured()` 判定的 config key 前缀对应。
ALL_CHANNELS = {
    "wechat": WechatChannel,
    "feishu": FeishuChannel,
    "telegram": TelegramChannel,
    "email": EmailChannel,
    "discord": DiscordChannel,
    "custom": CustomChannel,
    "pushover": PushoverChannel,
    "pushplus": PushPlusChannel,
    "windows": WindowsToastChannel,
}

__all__ = [
    "WechatChannel",
    "FeishuChannel",
    "TelegramChannel",
    "EmailChannel",
    "DiscordChannel",
    "CustomChannel",
    "PushoverChannel",
    "PushPlusChannel",
    "WindowsToastChannel",
    "ALL_CHANNELS",
]

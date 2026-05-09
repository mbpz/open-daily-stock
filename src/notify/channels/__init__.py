"""通知渠道模块"""
from .wechat import WechatChannel
from .feishu import FeishuChannel
from .telegram import TelegramChannel
from .email import EmailChannel
from .discord import DiscordChannel
from .custom import CustomChannel

__all__ = [
    "WechatChannel",
    "FeishuChannel",
    "TelegramChannel",
    "EmailChannel",
    "DiscordChannel",
    "CustomChannel",
]
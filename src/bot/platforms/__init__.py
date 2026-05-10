# -*- coding: utf-8 -*-
"""Platform registry."""
from __future__ import annotations
from typing import Dict, Type

from ..base import BotPlatform

from .telegram import TelegramPlatform
from .discord import DiscordPlatform

ALL_PLATFORMS: Dict[str, Type[BotPlatform]] = {
    "telegram": TelegramPlatform,
    "discord": DiscordPlatform,
}


def get_platform(name: str) -> BotPlatform:
    return ALL_PLATFORMS[name]()
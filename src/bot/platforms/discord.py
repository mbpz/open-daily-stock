# -*- coding: utf-8 -*-
"""Discord platform adapter."""
from __future__ import annotations
import logging
import os
from typing import Any, Dict, Optional

import requests

from ..base import BotMessage, BotPlatform

logger = logging.getLogger(__name__)


class DiscordPlatform(BotPlatform):
    """Discord Webhook adapter."""

    platform_name = "discord"

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL", "")
        self._session = requests.Session()

    @property
    def available(self) -> bool:
        return bool(self.webhook_url)

    def send_message(self, chat_id: str, text: str, **kwargs) -> bool:
        if not self.available:
            logger.warning("Discord webhook not configured")
            return False
        try:
            # Discord uses Slack-compatible markdown (MT模式下)
            payload = {"content": text}
            resp = self._session.post(self.webhook_url, json=payload, timeout=10)
            return resp.status_code in (200, 204)
        except Exception as e:
            logger.error(f"Discord send error: {e}")
            return False

    def parse_update(self, payload: Dict[str, Any]) -> Optional[BotMessage]:
        # Discord sends messages via interaction webhooks
        # Simple version: messages arrive as webhook POSTs
        try:
            if payload.get("t") != "MESSAGE_CREATE":
                return None
            msg = payload.get("d", {})
            author = msg.get("author", {})
            if author.get("bot"):
                return None  # Ignore bot messages
            content = msg.get("content", "")
            if not content:
                return None
            channel_id = str(msg.get("channel_id", ""))
            return BotMessage(
                platform=self.platform_name,
                user_id=str(author.get("id", "")),
                chat_id=channel_id,
                text=content,
                raw=payload,
            )
        except Exception as e:
            logger.warning(f"Discord parse error: {e}")
            return None

    def build_keyboard(self, buttons: list[list[str]]) -> Any:
        # Discord uses button components in embeds
        # Simplified: return description text
        return None
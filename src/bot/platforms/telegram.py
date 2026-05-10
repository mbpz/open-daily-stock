# -*- coding: utf-8 -*-
"""Telegram platform adapter."""
from __future__ import annotations
import logging
import os
from typing import Any, Dict, Optional

import requests

from ..base import BotMessage, BotPlatform

logger = logging.getLogger(__name__)


class TelegramPlatform(BotPlatform):
    """Telegram Bot API adapter."""

    platform_name = "telegram"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.api_url = f"https://api.telegram.org/bot{self.token}"
        self._session = requests.Session()

    @property
    def available(self) -> bool:
        return bool(self.token)

    def send_message(self, chat_id: str, text: str, **kwargs) -> bool:
        if not self.available:
            logger.warning("Telegram bot not configured (no token)")
            return False
        url = f"{self.api_url}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, **kwargs}
        try:
            resp = self._session.post(url, json=payload, timeout=10)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"Telegram send error: {e}")
            return False

    def parse_update(self, payload: Dict[str, Any]) -> Optional[BotMessage]:
        try:
            msg = payload.get("message", {})
            chat = msg.get("chat", {})
            text = msg.get("text", "") or ""
            if not text:
                return None
            return BotMessage(
                platform=self.platform_name,
                user_id=str(chat.get("id", "")),
                chat_id=str(chat.get("id", "")),
                text=text,
                raw=payload,
            )
        except Exception as e:
            logger.warning(f"Telegram parse error: {e}")
            return None

    def build_keyboard(self, buttons: list[list[str]]) -> dict:
        """Build Telegram inline keyboard."""
        return {
            "inline_keyboard": [
                [{"text": btn, "callback_data": btn} for btn in row]
                for row in buttons
            ]
        }
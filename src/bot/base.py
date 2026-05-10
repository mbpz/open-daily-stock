# -*- coding: utf-8 -*-
"""Base class and models for bot platforms."""
from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


@dataclass
class BotMessage:
    """Incoming message from a bot platform."""
    platform: str            # "telegram" | "wechat" | "discord"
    user_id: str            # Platform user ID
    chat_id: str            # Chat/conversation ID
    text: str               # Message text
    raw: Dict[str, Any] = field(default_factory=dict)  # Raw platform payload


@dataclass
class BotResponse:
    """Outgoing response to a bot platform."""
    text: str
    parse_mode: Optional[str] = None   # "Markdown" | "HTML"
    reply_to: Optional[str] = None     # Message ID to reply to
    keyboard: Optional[List[List[str]]] = None  # Inline keyboard buttons


class BotPlatform(ABC):
    """Abstract base class for IM platform adapters."""

    platform_name: str = "unknown"

    @abstractmethod
    def send_message(self, chat_id: str, text: str, **kwargs) -> bool:
        """Send a text message to a chat.

        Returns True on success.
        """

    @abstractmethod
    def parse_update(self, payload: Dict[str, Any]) -> Optional[BotMessage]:
        """Parse a platform webhook payload into a BotMessage."""

    @abstractmethod
    def build_keyboard(self, buttons: List[List[str]]) -> Any:
        """Build platform-native inline keyboard from button lists."""

    def format_progress(self, text: str, current: int, total: int) -> str:
        """Format a progress bar string (platform-agnostic)."""
        bar_len = 12
        filled = int(bar_len * current / total) if total > 0 else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        return f"{text}\n[{bar}] {current}/{total}"

    def format_table(self, rows: List[List[str]], headers: List[str]) -> str:
        """Format a simple table (platform-agnostic markdown)."""
        col_widths = [len(h) for h in headers]
        for row in rows:
            for i, cell in enumerate(row):
                col_widths[i] = max(col_widths[i], len(str(cell)))

        lines = []
        header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        separator = "-+-".join("-" * w for w in col_widths)
        lines.append(header_line)
        lines.append(separator)
        for row in rows:
            line = " | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row))
            lines.append(line)
        return "\n".join(lines)
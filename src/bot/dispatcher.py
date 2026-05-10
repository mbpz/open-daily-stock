# -*- coding: utf-8 -*-
"""Command dispatcher with rate limiting for bot interactions."""
from __future__ import annotations
import logging
import re
import time
from collections import defaultdict
from typing import Callable, Dict, List, Optional, TYPE_CHECKING

from .base import BotMessage, BotResponse

if TYPE_CHECKING:
    from .base import BotPlatform

logger = logging.getLogger(__name__)

# Handler: async def (BotMessage) -> Optional[BotResponse]
BotHandler = Callable[[BotMessage], Optional[BotResponse]]


class RateLimiter:
    """Sliding-window rate limiter per user."""

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: Dict[str, List[float]] = defaultdict(list)

    def is_allowed(self, user_id: str) -> bool:
        now = time.time()
        window_start = now - self.window_seconds
        self._requests[user_id] = [t for t in self._requests[user_id] if t > window_start]
        if len(self._requests[user_id]) >= self.max_requests:
            return False
        self._requests[user_id].append(now)
        return True

    def remaining(self, user_id: str) -> int:
        now = time.time()
        window_start = now - self.window_seconds
        self._requests[user_id] = [t for t in self._requests[user_id] if t > window_start]
        return max(0, self.max_requests - len(self._requests[user_id]))


class BotDispatcher:
    """Routes incoming bot messages to registered command handlers."""

    def __init__(self):
        self._handlers: Dict[str, BotHandler] = {}
        self._rate_limiter = RateLimiter()
        self._platforms: Dict[str, "BotPlatform"] = {}

    def register_platform(self, platform: "BotPlatform") -> None:
        self._platforms[platform.platform_name] = platform

    def register(self, command: str, handler: BotHandler) -> None:
        self._handlers[command.lower()] = handler

    def dispatch(self, message: BotMessage) -> Optional[BotResponse]:
        """Dispatch a message to the appropriate handler."""
        if not self._rate_limiter.is_allowed(message.user_id):
            return BotResponse(text="请求过于频繁，请稍后再试。⏳")

        text = message.text.strip()

        # Parse command (e.g. "/analyze 600519" or "分析 000001")
        cmd, args = self._parse_command(text)
        if not cmd:
            return None  # Not a command

        # Inject args into a new message-like dict for the handler
        msg_with_args = BotMessage(
            platform=message.platform,
            user_id=message.user_id,
            chat_id=message.chat_id,
            text=args,
            raw={"command": cmd, "original_text": text, **message.raw},
        )

        handler = self._handlers.get(cmd.lower())
        if handler:
            try:
                return handler(msg_with_args)
            except Exception as e:
                logger.error(f"Handler error for command '{cmd}': {e}")
                return BotResponse(text=f"处理命令时出错: {e}")
        else:
            return BotResponse(text=f"未知命令: {cmd}\n发送 /help 查看可用命令。")

    def _parse_command(self, text: str) -> tuple[Optional[str], str]:
        """Parse /command args or Chinese command pattern."""
        # /command args style
        if text.startswith("/"):
            parts = text.split(None, 1)
            return parts[0], parts[1] if len(parts) > 1 else ""
        # Chinese: "分析 600519" or "查行情 000001"
        match = re.match(r"^([\w一-鿿]+)\s+(.+)$", text)
        if match:
            return match.group(1), match.group(2)
        return None, text


# ---------------------------------------------------------------------------
# Built-in handlers (wired to DataService via shared registry)
# ---------------------------------------------------------------------------

def _help_handler(message: BotMessage) -> BotResponse:
    lines = [
        "📊 *open-daily-stock 指令*",
        "",
        "`/analyze <code>`  — 分析股票",
        "`/price <code>`     — 查行情",
        "`/portfolio`        — 我的持仓",
        "`/tasks`           — 任务列表",
        "`/help`            — 显示此消息",
        "",
        "也可直接发送:",
        "`分析 600519` — 分析指定股票",
        "`行情`        — 自选股行情",
    ]
    return BotResponse(text="\n".join(lines), parse_mode="Markdown")


def _build_default_dispatcher() -> BotDispatcher:
    """Build dispatcher with built-in command handlers."""
    dispatcher = BotDispatcher()

    def make_handler(cmd: str) -> BotHandler:
        def handler(msg: BotMessage) -> BotResponse:
            return BotResponse(text=f"命令 {cmd} 已收到: {msg.text}")
        return handler

    dispatcher.register("help", _help_handler)
    dispatcher.register("analyze", make_handler("analyze"))
    dispatcher.register("price", make_handler("price"))
    dispatcher.register("行情", make_handler("行情"))
    dispatcher.register("分析", make_handler("分析"))
    dispatcher.register("portfolio", make_handler("portfolio"))
    dispatcher.register("持仓", make_handler("持仓"))
    return dispatcher


_DISPATCHER: Optional[BotDispatcher] = None


def get_dispatcher() -> BotDispatcher:
    global _DISPATCHER
    if _DISPATCHER is None:
        _DISPATCHER = _build_default_dispatcher()
    return _DISPATCHER
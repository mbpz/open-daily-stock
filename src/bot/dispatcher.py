"""Command dispatcher with rate limiting for bot interactions (P6-4).

Wires bot commands (/quote, /analyze, /alert, /positions, /review)
to the real DataService action handlers.
"""

from __future__ import annotations

import json
import logging
import re
import time
import threading
from collections import defaultdict
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from .base import BotMessage, BotResponse

if TYPE_CHECKING:
    from .base import BotPlatform
    from src.data_service import DataService

logger = logging.getLogger(__name__)

BotHandler = Callable[["BotMessage", "DataService"], Optional["BotResponse"]]


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Bot Dispatcher
# ---------------------------------------------------------------------------

class BotDispatcher:
    """Routes incoming bot messages to registered command handlers.

    Handlers receive (BotMessage, DataService) → Optional[BotResponse].
    """

    def __init__(self, data_service: Optional["DataService"] = None):
        self._handlers: Dict[str, BotHandler] = {}
        self._rate_limiter = RateLimiter()
        self._platforms: Dict[str, "BotPlatform"] = {}
        self._data_service = data_service

    def set_data_service(self, ds: "DataService") -> None:
        self._data_service = ds

    def register_platform(self, platform: "BotPlatform") -> None:
        self._platforms[platform.platform_name] = platform

    def register(self, command: str, handler: BotHandler) -> None:
        self._handlers[command.lower()] = handler

    def dispatch(self, message: BotMessage) -> Optional[BotResponse]:
        """Dispatch a message to the appropriate handler."""
        if not self._rate_limiter.is_allowed(message.user_id):
            return BotResponse(text="⏳ 请求过于频繁，请稍后再试。")

        text = message.text.strip()
        cmd, args = self._parse_command(text)
        if not cmd:
            return None

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
                ds = self._data_service
                if ds is None:
                    return BotResponse(text="⚠️ 后端服务未连接，请稍后再试。")
                return handler(msg_with_args, ds)
            except Exception as e:
                logger.error(f"Handler error for '{cmd}': {e}")
                return BotResponse(text=f"❌ 处理命令时出错: {e}")
        else:
            return BotResponse(text=f"❓ 未知命令: {cmd}\n发送 /help 查看可用命令。")

    def _parse_command(self, text: str) -> tuple[Optional[str], str]:
        """Parse /command args or Chinese pattern."""
        if text.startswith("/"):
            parts = text.split(None, 1)
            return parts[0], parts[1] if len(parts) > 1 else ""
        match = re.match(r"^([\w一-鿿]+)\s+(.+)$", text)
        if match:
            return match.group(1), match.group(2)
        return None, text


# ---------------------------------------------------------------------------
# Built-in Command Handlers (P6-4)
# ---------------------------------------------------------------------------

def _help_handler(msg: BotMessage, ds: "DataService") -> BotResponse:
    lines = [
        "📊 *open-daily-stock 指令*",
        "",
        "`/quote <code>`     — 查实时行情",
        "`/analyze <code>`   — AI 分析股票",
        "`/alert <code> <条件>` — 设置价格告警",
        "`/positions`        — 查看持仓",
        "`/review`           — 市场复盘日报",
        "`/help`             — 显示此消息",
    ]
    return BotResponse(text="\n".join(lines), parse_mode="Markdown")


def _quote_handler(msg: BotMessage, ds: "DataService") -> BotResponse:
    code = msg.text.strip()
    if not code:
        return BotResponse(text="用法: `/quote 600519`")
    try:
        result = ds._handle_get_markets({})
        if result.get("status") != "ok":
            return BotResponse(text="⚠️ 获取行情失败")
        markets = result.get("data", [])
        stock = next((m for m in markets if m.get("code") == code), None)
        if not stock:
            return BotResponse(text=f"❓ 未找到股票: {code}")
        return BotResponse(
            text=(
                f"*{stock.get('name', code)}* ({code})\n"
                f"💰 最新价: {stock.get('price', 0):.2f}\n"
                f"📈 涨跌幅: {stock.get('change', 0):+.2f}%\n"
                f"📊 成交量: {stock.get('volume_display', stock.get('volume', 0))}"
            ),
            parse_mode="Markdown",
        )
    except Exception as e:
        return BotResponse(text=f"❌ 查询失败: {e}")


def _analyze_handler(msg: BotMessage, ds: "DataService") -> BotResponse:
    code = msg.text.strip()
    if not code:
        return BotResponse(text="用法: `/analyze 600519`")
    try:
        result = ds._handle_analyze({"code": code})
        if result.get("status") != "ok":
            return BotResponse(text=f"⚠️ 分析失败: {result.get('message', '未知错误')}")
        task_id = result.get("task_id", "")
        return BotResponse(text=f"🔍 已提交分析任务: {code}\n📋 任务ID: `{task_id}`\n⏳ 请稍后查看结果。", parse_mode="Markdown")
    except Exception as e:
        return BotResponse(text=f"❌ 触发分析失败: {e}")


def _alert_handler(msg: BotMessage, ds: "DataService") -> BotResponse:
    """Set price alert. Format: /alert <code> <condition> <threshold>"""
    parts = msg.text.strip().split()
    if len(parts) < 3:
        return BotResponse(text="用法: `/alert 600519 price_above 1850`\n条件: price_above | price_below | change_pct_above")
    code, condition, threshold = parts[0], parts[1], parts[2]
    try:
        thresh_val = float(threshold)
    except ValueError:
        return BotResponse(text="⚠️ 阈值必须是数字")
    try:
        result = ds._handle_save_alert({
            "stock": code,
            "condition": condition,
            "threshold": thresh_val,
            "channel": "telegram",
        })
        if result.get("status") == "ok":
            return BotResponse(text=f"✅ 告警已设置: {code} {condition} {thresh_val}")
        return BotResponse(text=f"⚠️ 设置失败: {result.get('message', '')}")
    except Exception as e:
        return BotResponse(text=f"❌ 设置告警失败: {e}")


def _positions_handler(msg: BotMessage, ds: "DataService") -> BotResponse:
    try:
        result = ds._handle_get_positions({})
        if result.get("status") != "ok":
            return BotResponse(text="⚠️ 获取持仓失败")
        positions = result.get("positions", [])
        if not positions:
            return BotResponse(text="📭 当前无持仓记录。")
        lines = ["📋 *我的持仓*", ""]
        for p in positions[:10]:
            name = p.get("name", p.get("code", ""))
            code = p.get("code", "")
            shares = p.get("shares", 0)
            cost = p.get("buy_price", 0)
            lines.append(f"• {name}({code}): {shares}股 @ {cost:.2f}")
        return BotResponse(text="\n".join(lines), parse_mode="Markdown")
    except Exception as e:
        return BotResponse(text=f"❌ 查询失败: {e}")


def _review_handler(msg: BotMessage, ds: "DataService") -> BotResponse:
    try:
        result = ds._handle_get_market_review({"force": False})
        if result.get("status") != "ok":
            return BotResponse(text="⚠️ 生成复盘报告失败")
        report = result.get("report", "")
        # Truncate for Telegram (4096 char limit)
        if len(report) > 3800:
            report = report[:3800] + "\n\n...（内容过长已截断，完整报告请在 GUI 查看）"
        return BotResponse(text=report, parse_mode="Markdown")
    except Exception as e:
        return BotResponse(text=f"❌ 复盘失败: {e}")


# ---------------------------------------------------------------------------
# Dispatcher factory
# ---------------------------------------------------------------------------

def build_dispatcher(data_service: Optional["DataService"] = None) -> BotDispatcher:
    """Build a BotDispatcher with all P6-4 command handlers wired to DataService."""
    d = BotDispatcher(data_service)

    d.register("/help", _help_handler)
    d.register("/start", _help_handler)
    d.register("/quote", _quote_handler)
    d.register("/analyze", _analyze_handler)
    d.register("/alert", _alert_handler)
    d.register("/positions", _positions_handler)
    d.register("/review", _review_handler)
    # Chinese aliases
    d.register("行情", _quote_handler)
    d.register("分析", _analyze_handler)
    d.register("持仓", _positions_handler)
    d.register("复盘", _review_handler)
    d.register("帮助", _help_handler)

    return d


# ---------------------------------------------------------------------------
# Bot Runner (Telegram long-polling)
# ---------------------------------------------------------------------------

class BotRunner:
    """Runs bot polling loops in background daemon threads."""

    def __init__(self, dispatcher: BotDispatcher, config: Any):
        self.dispatcher = dispatcher
        self.config = config
        self._running = False
        self._threads: List[threading.Thread] = []

    def start(self) -> None:
        """Start all configured bot platforms."""
        if not self.config.bot_enabled:
            logger.info("Bot disabled in config, skipping")
            return

        self._running = True

        # Telegram long-polling
        if self.config.telegram_bot_token:
            t = threading.Thread(
                target=self._telegram_polling_loop,
                daemon=True,
                name="telegram-bot",
            )
            t.start()
            self._threads.append(t)
            logger.info("Telegram bot polling started")

        # Discord — outgoing webhook only (bidirectional needs gateway API)
        if self.config.discord_webhook_url:
            logger.info("Discord webhook available (outgoing only)")

    def stop(self) -> None:
        self._running = False

    def _telegram_polling_loop(self) -> None:
        """Long-poll getUpdates in a loop, dispatch each message."""
        import requests

        token = self.config.telegram_bot_token
        base_url = f"https://api.telegram.org/bot{token}"
        offset = 0
        session = requests.Session()
        error_count = 0

        while self._running:
            try:
                url = f"{base_url}/getUpdates?offset={offset}&timeout=30"
                resp = session.get(url, timeout=35)
                if resp.status_code != 200:
                    error_count += 1
                    if error_count > 5:
                        logger.error("Telegram polling: too many errors, backing off")
                        time.sleep(60)
                        error_count = 0
                    continue

                error_count = 0
                data = resp.json()
                if not data.get("ok"):
                    continue

                for update in data.get("result", []):
                    offset = max(offset, update["update_id"] + 1)

                    msg_data = update.get("message") or update.get("channel_post")
                    if not msg_data:
                        continue

                    chat = msg_data.get("chat", {})
                    text = msg_data.get("text", "")
                    if not text:
                        continue

                    # Build BotMessage
                    from .platforms.telegram import TelegramPlatform
                    platform = TelegramPlatform(token=token)
                    bot_msg = platform.parse_update({"message": msg_data})
                    if bot_msg is None:
                        continue

                    # Dispatch
                    response = self.dispatcher.dispatch(bot_msg)
                    if response:
                        platform.send_message(
                            bot_msg.chat_id,
                            response.text,
                            parse_mode=response.parse_mode or "Markdown",
                        )

            except requests.RequestException as e:
                logger.warning(f"Telegram polling error: {e}")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Telegram polling unexpected error: {e}")
                time.sleep(5)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_DISPATCHER: Optional[BotDispatcher] = None


def get_dispatcher(data_service: Optional["DataService"] = None) -> BotDispatcher:
    global _DISPATCHER
    if _DISPATCHER is None:
        _DISPATCHER = build_dispatcher(data_service)
    elif data_service is not None and _DISPATCHER._data_service is None:
        _DISPATCHER.set_data_service(data_service)
    return _DISPATCHER

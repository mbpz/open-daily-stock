"""NotificationService facade — 通知层统一入口。

对外契约（v2，新风格）：
    notifier = NotificationService()
    results = notifier.send(content)               # -> List[ChannelResult]
    r = notifier.send_to_channel("wechat", content) # -> ChannelResult
    notifier.has_channel("wechat")                  # -> bool
    notifier.is_available()                         # -> bool
    notifier.get_available_channels()               # -> List[str]（字符串 key）
    notifier.send_to_context(content)               # -> bool（旧 Stream 回复，保留）
    notifier.save_report_to_file(content)           # -> str filepath

迁自 src/notification.py:NotificationService。
"""
from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config import get_config

from .base import ChannelResult
from .context import has_context_channel, send_via_source_context
from .dispatcher import NotificationDispatcher
from .types import BotMessage

logger = logging.getLogger(__name__)


class NotificationService:
    """通知 facade — 基于 NotificationDispatcher + 各 channel 的分发引擎。"""

    def __init__(self, source_message: Optional[BotMessage] = None):
        self._source_message = source_message
        config = get_config()

        # 组装 dispatcher 所需的 config dict（与旧 __init__ 逐字段平铺保持一致）
        self._config: Dict = {
            # 企业微信
            "wechat_webhook_url": config.wechat_webhook_url or "",
            "wechat_max_bytes": getattr(config, "wechat_max_bytes", 4000),
            # 飞书
            "feishu_webhook_url": getattr(config, "feishu_webhook_url", ""),
            "feishu_max_bytes": getattr(config, "feishu_max_bytes", 20000),
            # Telegram
            "telegram_bot_token": getattr(config, "telegram_bot_token", ""),
            "telegram_chat_id": getattr(config, "telegram_chat_id", ""),
            # 邮件
            "email_sender": config.email_sender or "",
            "email_password": config.email_password or "",
            "email_receivers": config.email_receivers or [],
            # Discord
            "discord_webhook_url": getattr(config, "discord_webhook_url", ""),
            "discord_bot_token": getattr(config, "discord_bot_token", ""),
            "discord_main_channel_id": getattr(config, "discord_main_channel_id", ""),
            "discord_channel_id": getattr(config, "discord_channel_id", ""),
            # Pushover
            "pushover_user_key": getattr(config, "pushover_user_key", ""),
            "pushover_api_token": getattr(config, "pushover_api_token", ""),
            # PushPlus
            "pushplus_token": getattr(config, "pushplus_token", ""),
            # Custom
            "custom_webhook_urls": getattr(config, "custom_webhook_urls", []) or [],
            "custom_webhook_bearer_token": getattr(config, "custom_webhook_bearer_token", ""),
            # Windows (无额外配置 — 平台门控在 channel 内)
        }

        self._dispatcher = NotificationDispatcher(self._config)
        self._has_context = has_context_channel(source_message)

        if not self.is_available() and not self._has_context:
            logger.warning("未配置有效的通知渠道，将不发送推送通知")
        else:
            ch_names = self._dispatcher.configured_channel_names()
            if self._has_context:
                ch_names.append("钉钉会话")
            logger.info(f"已配置 {len(ch_names)} 个通知渠道：{', '.join(ch_names)}")

    # ─── 状态查询 ──────────────────────────────────────────────

    def is_available(self) -> bool:
        """是否有至少一个渠道已配置。"""
        return len(self._dispatcher.configured_channels) > 0

    def get_available_channels(self) -> List[str]:
        """返回已配置渠道的字符串 key 列表。"""
        return self._dispatcher.configured_channel_names()

    def has_channel(self, name: str) -> bool:
        """检查指定渠道是否已配置。"""
        return self._dispatcher.has_channel(name)

    # ─── 分发 ──────────────────────────────────────────────────

    def send(self, content: str) -> List[ChannelResult]:
        """向所有已配置渠道发送。

        Returns:
            List[ChannelResult] — 每个渠道一条结果。
        """
        return self._dispatcher.send(content)

    def send_to_channel(self, name: str, content: str, **kwargs) -> ChannelResult:
        """向指定渠道发送。渠道不存在或未配置时返回失败。"""
        return self._dispatcher.send_to_channel(name, content, **kwargs)

    def send_to_context(self, content: str) -> bool:
        """向基于消息上下文的渠道发送（钉钉/飞书 Stream 模式回复）。

        保留旧 bool 返回契约——pipeline.py 直接用。
        """
        # 使用当前 notify 实例的 feishu webhook url（若已配置）
        feishu_url = self._config.get("feishu_webhook_url")
        return send_via_source_context(self._source_message, content, feishu_url)

    # ─── 文件落地 ──────────────────────────────────────────────

    def save_report_to_file(
        self, content: str, filename: Optional[str] = None
    ) -> str:
        """保存日报到项目根 `reports/` 目录。"""
        if filename is None:
            date_str = datetime.now().strftime("%Y%m%d")
            filename = f"report_{date_str}.md"

        reports_dir = Path(__file__).parent.parent.parent / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)

        filepath = reports_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)

        logger.info(f"日报已保存到: {filepath}")
        return str(filepath)

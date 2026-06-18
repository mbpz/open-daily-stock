"""Windows Toast 桌面通知渠道（仅 Windows 平台可用）"""
from __future__ import annotations

import logging
import sys
from datetime import datetime

from ..base import BaseChannel, ChannelPriority, ChannelResult

logger = logging.getLogger(__name__)

# Windows Toast 内容上限（旧实现的经验值；超过截断 + ...）
_MAX_CONTENT_LENGTH = 200
# 通知显示时长（秒）
_DURATION = 5

# 平台门控：仅在 Windows 上 import win10toast，其他平台保持模块可加载但渠道不可用
_win10toast_available = False
_ToastNotifier = None
if sys.platform == "win32":
    try:
        from win10toast import ToastNotifier as _ToastNotifier  # type: ignore
        _win10toast_available = True
    except ImportError:
        _win10toast_available = False


class WindowsToastChannel(BaseChannel):
    """Windows Toast 桌面通知。

    迁自 src/notification.py:send_to_windows。

    平台门控：
    - 非 Windows 平台 → is_configured() 永远 False，send() 返回失败但不抛异常
    - 缺 win10toast 包 → 同上
    """

    def __init__(self, config: dict):
        super().__init__(config)

    def is_configured(self) -> bool:
        return _win10toast_available

    @property
    def priority(self) -> ChannelPriority:
        return ChannelPriority.LOW

    def send(self, content: str, **kwargs) -> ChannelResult:
        """显示一条 Windows Toast 通知。

        kwargs:
            title: 自定义标题，默认 "股票分析报告 - YYYY-MM-DD"
            duration: 显示时长（秒），默认 5
        """
        if not self.is_configured():
            return ChannelResult(
                success=False,
                channel=self.name,
                error="Windows Toast 不可用（非 Windows 平台或 win10toast 未安装）",
            )

        title = kwargs.get("title")
        if title is None:
            date_str = datetime.now().strftime("%Y-%m-%d")
            title = f"股票分析报告 - {date_str}"

        duration = kwargs.get("duration", _DURATION)

        # 内容截断
        if len(content) > _MAX_CONTENT_LENGTH:
            truncated = content[:_MAX_CONTENT_LENGTH] + "..."
        else:
            truncated = content

        try:
            toaster = _ToastNotifier()  # type: ignore[misc]
            toaster.show_toast(
                title=title,
                msg=truncated,
                duration=duration,
                threaded=False,
            )
            return ChannelResult(success=True, channel=self.name, message="Windows Toast 已显示")
        except Exception as e:
            logger.error(f"Windows Toast 通知失败: {e}")
            return ChannelResult(success=False, channel=self.name, error=str(e))

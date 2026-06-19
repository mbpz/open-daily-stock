"""通知消息构建器 — 便捷的通知内容格式化方法。

迁自 src/notification.py:NotificationBuilder (L3033-3078)。
"""
from __future__ import annotations

from typing import List

from src.analyzer import AnalysisResult


class NotificationBuilder:
    """通知消息构建器（全静态方法，不需要实例化）。"""

    @staticmethod
    def build_simple_alert(
        title: str,
        content: str,
        alert_type: str = "info",
    ) -> str:
        """构建简单的提醒消息。

        Args:
            title: 标题
            content: 内容
            alert_type: 类型（info / warning / error / success）
        """
        emoji_map = {
            "info": "ℹ️",      # ℹ️
            "warning": "⚠️",   # ⚠️
            "error": "❌",            # ❌
            "success": "✅",          # ✅
        }
        emoji = emoji_map.get(alert_type, "\U0001f4e2")  # 📢
        return f"{emoji} **{title}**\n\n{content}"

    @staticmethod
    def build_stock_summary(results: List[AnalysisResult]) -> str:
        """构建股票摘要（简短版，适用于快速通知）。

        按 sentiment_score 降序排列。
        """
        lines = ["\U0001f4ca **今日自选股摘要**", ""]  # 📊
        for r in sorted(results, key=lambda x: x.sentiment_score, reverse=True):
            emoji = r.get_emoji()
            lines.append(
                f"{emoji} {r.name}({r.code}): {r.operation_advice} | 评分 {r.sentiment_score}"
            )
        return "\n".join(lines)

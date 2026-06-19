"""通知层便捷函数（单例获取 / 顶层快捷入口）。

迁自 src/notification.py:get_notification_service + send_daily_report。
"""
from __future__ import annotations

import logging
from typing import List

from src.analyzer import AnalysisResult

from .reports import generate_daily_report
from .service import NotificationService

logger = logging.getLogger(__name__)


def get_notification_service() -> NotificationService:
    """获取通知服务实例（每次新建，配置实时读取）。"""
    return NotificationService()


def send_daily_report(results: List[AnalysisResult]) -> bool:
    """每天报告的快捷入口：生成 → 保存 → 推送 → 返回至少一个渠道成功。

    保留旧 bool 返回契约。
    """
    service = get_notification_service()
    report = generate_daily_report(results)
    service.save_report_to_file(report)
    results_list = service.send(report)
    return any(r.success for r in results_list)

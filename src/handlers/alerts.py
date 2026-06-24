"""alerts handlers — 告警配置的 CRUD（get/save/delete/toggle）。"""
from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

from src.storage import get_db

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def get_alerts(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取所有告警配置"""
    try:
        db = get_db()
        alerts = db.get_alerts()
        return {"status": "ok", "alerts": [a.to_dict() for a in alerts]}
    except Exception as e:
        logger.error(f"获取告警失败: {e}")
        return {"status": "error", "message": f"获取告警失败: {str(e)}"}


def save_alert(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """创建新告警"""
    stock = req.get("stock")
    condition = req.get("condition")
    threshold = req.get("threshold")
    channel = req.get("channel", "wechat")

    if not stock:
        return {"status": "error", "message": "缺少 stock 参数"}
    if not condition:
        return {"status": "error", "message": "缺少 condition 参数"}
    if threshold is None:
        return {"status": "error", "message": "缺少 threshold 参数"}

    try:
        db = get_db()
        alert = db.save_alert(
            stock=stock,
            condition=condition,
            threshold=float(threshold),
            channel=channel,
            enabled=True,
        )
        return {"status": "ok", "alert": alert.to_dict()}
    except Exception as e:
        logger.error(f"保存告警失败: {e}")
        return {"status": "error", "message": f"保存告警失败: {str(e)}"}


def delete_alert(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """删除告警"""
    alert_id = req.get("id")
    if alert_id is None:
        return {"status": "error", "message": "缺少 id 参数"}

    try:
        db = get_db()
        success = db.delete_alert(int(alert_id))
        if success:
            return {"status": "ok", "message": "告警已删除"}
        return {"status": "error", "message": f"告警 {alert_id} 不存在"}
    except Exception as e:
        logger.error(f"删除告警失败: {e}")
        return {"status": "error", "message": f"删除告警失败: {str(e)}"}


def toggle_alert(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """切换告警启用状态"""
    alert_id = req.get("id")
    if alert_id is None:
        return {"status": "error", "message": "缺少 id 参数"}

    try:
        db = get_db()
        alert = db.toggle_alert(int(alert_id))
        if alert:
            return {"status": "ok", "alert": alert.to_dict()}
        return {"status": "error", "message": f"告警 {alert_id} 不存在"}
    except Exception as e:
        logger.error(f"切换告警失败: {e}")
        return {"status": "error", "message": f"切换告警失败: {str(e)}"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_get_alerts = partial(get_alerts, service)
    service._actions["get_alerts"] = "_handle_get_alerts"

    service._handle_save_alert = partial(save_alert, service)
    service._actions["save_alert"] = "_handle_save_alert"

    service._handle_delete_alert = partial(delete_alert, service)
    service._actions["delete_alert"] = "_handle_delete_alert"

    service._handle_toggle_alert = partial(toggle_alert, service)
    service._actions["toggle_alert"] = "_handle_toggle_alert"

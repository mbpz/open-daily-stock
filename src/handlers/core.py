"""core handlers — hello / refresh / quit。

每个域模块提供 `register(service)` 把 module-level 函数用 `functools.partial`
绑为 service 实例属性（只接受 req 一个参数，service 已绑定），并把 action
name 注入到 `service._actions` dict。

dispatch 路径（data_service.py:242-256）保持原样：
    handler = getattr(self, self._actions[action])
    handler(req)
→ instance attribute 是 partial(原函数, service)，
  调用时等价于 handler_fn(req) → 原函数(service, req) ✓
"""
from __future__ import annotations

import logging
from functools import partial
from typing import Any, Dict

from src.data_service import DataService

logger = logging.getLogger(__name__)


def hello(service: DataService, req: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "ok", "version": "0.4.0"}


def refresh(service: DataService, req: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if service._is_demo_mode():
            return {"status": "ok", "message": "演示模式 - 数据无需刷新"}
        service._refresh_markets()
        service._check_alerts()
        return {"status": "ok", "message": "刷新完成"}
    except Exception as e:
        logger.error(f"刷新行情失败: {e}")
        return {"status": "error", "message": "刷新失败，请检查网络连接"}


def quit_(service: DataService, req: Dict[str, Any]) -> Dict[str, Any]:
    service._running = False
    return {"status": "ok", "message": "退出"}


def register(service: DataService) -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_hello = partial(hello, service)
    service._actions["hello"] = "_handle_hello"

    service._handle_refresh = partial(refresh, service)
    service._actions["refresh"] = "_handle_refresh"

    service._handle_quit = partial(quit_, service)
    service._actions["quit"] = "_handle_quit"


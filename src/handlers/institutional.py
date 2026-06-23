"""institutional handlers — 机构动向 + 龙虎榜 (P1-6)。"""
from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def get_institutional(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取机构动向追踪数据（大股东增减持 + 机构调研）"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    try:
        from src.institutional import get_institutional_summary
        data = get_institutional_summary(code)
        return {"status": "ok", "data": data}

    except Exception as e:
        logger.error(f"获取机构动向失败 [{code}]: {e}")
        return {"status": "error", "message": f"获取机构动向失败: {str(e)}"}


def get_dragon_board(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取龙虎榜数据"""
    date = req.get("date")  # 可选参数

    try:
        from src.institutional import get_dragon_board
        data = get_dragon_board(date=date)
        return {"status": "ok", "data": data}

    except Exception as e:
        logger.error(f"获取龙虎榜失败: {e}")
        return {"status": "error", "message": f"获取龙虎榜失败: {str(e)}"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_get_institutional = partial(get_institutional, service)
    service._actions["get_institutional"] = "_handle_get_institutional"

    service._handle_get_dragon_board = partial(get_dragon_board, service)
    service._actions["get_dragon_board"] = "_handle_get_dragon_board"

"""portfolio handlers — 持仓 CRUD（add/remove/update/get）。"""
from __future__ import annotations

import logging
from datetime import date
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

from src.storage import get_db

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def add_position(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """添加持仓"""
    code = req.get("code")
    name = req.get("name")
    shares = req.get("shares")
    buy_price = req.get("buy_price")
    buy_date = req.get("buy_date")

    # Validate required fields
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}
    if not name:
        name = code  # Default to code if name not provided
    if shares is None:
        return {"status": "error", "message": "缺少 shares 参数"}
    if buy_price is None:
        return {"status": "error", "message": "缺少 buy_price 参数"}
    if not buy_date:
        return {"status": "error", "message": "缺少 buy_date 参数"}

    try:
        buy_date_parsed = date.fromisoformat(buy_date)
        db = get_db()
        position = db.save_position(
            code=code,
            name=name,
            shares=shares,
            buy_price=buy_price,
            buy_date=buy_date_parsed,
            current_price=buy_price,
        )
        return {"status": "ok", "position": position.to_dict()}
    except Exception as e:
        logger.error(f"添加持仓失败: {e}")
        return {"status": "error", "message": f"添加持仓失败: {str(e)}"}


def remove_position(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """删除持仓"""
    position_id = req.get("id")
    if position_id is None:
        return {"status": "error", "message": "缺少 id 参数"}

    try:
        db = get_db()
        position = db.get_position(position_id)
        if not position:
            return {"status": "error", "message": f"持仓 {position_id} 不存在"}

        db.delete_position(position_id)
        return {"status": "ok", "message": "持仓已删除"}
    except Exception as e:
        logger.error(f"删除持仓失败: {e}")
        return {"status": "error", "message": f"删除持仓失败: {str(e)}"}


def update_position(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """更新持仓（当前价格等）"""
    position_id = req.get("id")
    if position_id is None:
        return {"status": "error", "message": "缺少 id 参数"}

    try:
        db = get_db()
        existing = db.get_position(position_id)
        if not existing:
            return {"status": "error", "message": f"持仓 {position_id} 不存在"}

        # Build update kwargs dynamically
        kwargs: Dict[str, Any] = {}
        if "current_price" in req:
            kwargs["current_price"] = req["current_price"]
        if "shares" in req:
            kwargs["shares"] = req["shares"]
        if "buy_price" in req:
            kwargs["buy_price"] = req["buy_price"]

        if not kwargs:
            return {"status": "error", "message": "没有提供更新字段"}

        updated = db.update_position(position_id, **kwargs)
        return {"status": "ok", "position": updated.to_dict()}
    except Exception as e:
        logger.error(f"更新持仓失败: {e}")
        return {"status": "error", "message": f"更新持仓失败: {str(e)}"}


def get_positions(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取所有持仓"""
    try:
        # Demo mode: return pre-configured demo portfolio
        if service._is_demo_mode():
            from src.demo_data import DEMO_PORTFOLIO, DEMO_PORTFOLIO_SUMMARY
            return {
                "status": "ok",
                "positions": list(DEMO_PORTFOLIO),
                "summary": DEMO_PORTFOLIO_SUMMARY,
            }

        db = get_db()
        positions = db.get_positions()
        return {"status": "ok", "positions": [p.to_dict() for p in positions]}
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        return {"status": "error", "message": f"获取持仓失败: {str(e)}"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_add_position = partial(add_position, service)
    service._actions["add_position"] = "_handle_add_position"

    service._handle_remove_position = partial(remove_position, service)
    service._actions["remove_position"] = "_handle_remove_position"

    service._handle_update_position = partial(update_position, service)
    service._actions["update_position"] = "_handle_update_position"

    service._handle_get_positions = partial(get_positions, service)
    service._actions["get_positions"] = "_handle_get_positions"

"""sim handlers — 模拟交易账户的 buy / sell / summary / history / reset。"""
from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

from src.sim_trading import SimAccount
from src.storage import get_db

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


def _notify_in_app(title: str, message: str, level: str, category: str, action: str) -> None:
    """内部辅助：在 app 内部发通知（容错，不影响主流程）。"""
    try:
        from src.notification_center import get_notification_center
        get_notification_center().notify(
            title=title,
            message=message,
            level=level,
            category=category,
            action=action,
        )
    except Exception:
        pass


# ─── Handlers ──────────────────────────────────────────────────


def sim_buy(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    code = req["code"]
    name = req.get("name", code)
    price = req["price"]
    shares = req.get("shares", 100)
    result = service._sim_account.buy(code, name, price, shares)

    # Persist after each trade
    try:
        get_db().save_sim_account(service._sim_account.to_dict())
    except Exception as e:
        logger.warning(f"持久化模拟账户失败: {e}")

    if result.get("status") == "ok":
        cost = price * shares
        _notify_in_app(
            title=f"买入 {name}({code})",
            message=f"{shares}股 @{price:.2f}  成本 ¥{cost:,.2f}",
            level="success",
            category="trade_executed",
            action="markets",
        )
    return result


def sim_sell(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    code = req["code"]
    price = req["price"]
    shares = req.get("shares")
    result = service._sim_account.sell(code, price, shares)

    try:
        get_db().save_sim_account(service._sim_account.to_dict())
    except Exception as e:
        logger.warning(f"持久化模拟账户失败: {e}")

    if result.get("status") == "ok":
        trade = result.get("trade", {})
        pnl = trade.get("pnl", 0)
        name = trade.get("name", code)
        shares_sold = trade.get("shares", 0)
        level = "success" if pnl >= 0 else "warning"
        _notify_in_app(
            title=f"卖出 {name}({code})",
            message=f"{shares_sold}股 @{price:.2f}  盈亏 ¥{pnl:+,.2f}",
            level=level,
            category="trade_executed",
            action="markets",
        )
    return result


def sim_summary(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Update prices from market data first, then return account summary."""
    markets = service._get_markets()
    prices = {m["code"]: m["price"] for m in markets}
    service._sim_account.update_prices(prices)
    return {"status": "ok", "data": service._sim_account.get_summary()}


def sim_history(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    return {"status": "ok", "data": service._sim_account.trade_history[-50:]}


def sim_reset(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    service._sim_account = SimAccount()
    try:
        get_db().save_sim_account(None)
    except Exception as e:
        logger.warning(f"清除模拟账户持久化失败: {e}")
    return {"status": "ok", "message": "账户已重置"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_sim_buy = partial(sim_buy, service)
    service._actions["sim_buy"] = "_handle_sim_buy"

    service._handle_sim_sell = partial(sim_sell, service)
    service._actions["sim_sell"] = "_handle_sim_sell"

    service._handle_sim_summary = partial(sim_summary, service)
    service._actions["sim_summary"] = "_handle_sim_summary"

    service._handle_sim_history = partial(sim_history, service)
    service._actions["sim_history"] = "_handle_sim_history"

    service._handle_sim_reset = partial(sim_reset, service)
    service._actions["sim_reset"] = "_handle_sim_reset"

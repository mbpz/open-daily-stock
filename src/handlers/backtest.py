"""backtest handlers — 策略回测 (P1-7 + P6-1)。"""
from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def run_backtest(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """运行回测"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    initial_capital = req.get("initial_capital")
    if initial_capital is None:
        return {"status": "error", "message": "缺少 initial_capital 参数"}

    days = req.get("days", 60)  # 默认 60 天
    strategy_name = req.get("strategy", "")  # P6-1: 可选策略名称

    try:
        # 获取历史数据 — 调 markets.get_history 模块函数（不要走 _safe_call 包装）
        from .markets import get_history
        history_result = get_history(service, {"code": code, "days": days})
        if history_result.get("status") != "ok":
            return history_result

        history_data = history_result.get("data", [])
        if not history_data:
            return {"status": "ok", "data": [], "message": "无历史数据"}

        # P6-1: 支持多种策略
        from src.backtester import backtest, ma_crossover_strategy
        from src.strategies import get_python_strategy, get_strategy

        strategy_fn = ma_crossover_strategy  # 默认
        strategy_label = "MA交叉(默认)"

        if strategy_name:
            # 优先查找 Python 内置策略
            py_strat = get_python_strategy(strategy_name)
            if py_strat is not None:
                # 允许请求参数覆盖策略参数
                strat_params = req.get("strategy_params", {})
                if strat_params:
                    py_strat = py_strat.__class__(**strat_params)
                strategy_fn = py_strat
                strategy_label = py_strat.display_name
            else:
                # 尝试 YAML 策略（暂不支持回测，返回提示）
                yaml_strat = get_strategy(strategy_name)
                if yaml_strat is not None and not hasattr(yaml_strat, "generate_trades"):
                    return {
                        "status": "error",
                        "message": f"YAML策略 '{strategy_name}' 暂不支持回测，请使用Python内置策略"
                    }

        result = backtest(
            history_data,
            initial_capital=initial_capital,
            strategy_fn=strategy_fn,
        )

        # In-app notification
        try:
            from src.notification_center import get_notification_center
            get_notification_center().notify(
                title=f"回测完成: {code} [{strategy_label}]",
                message=f"收益率 {result.total_return:+.2f}%  胜率 {result.win_rate:.1f}%  交易 {result.num_trades}次",
                level="info",
                category="backtest_complete",
                action="strategies",
            )
        except Exception:
            pass

        return {
            "status": "ok",
            "data": {
                "strategy": strategy_label,
                "total_return": result.total_return,
                "max_drawdown": result.max_drawdown,
                "sharpe_ratio": result.sharpe_ratio,
                "num_trades": result.num_trades,
                "win_rate": result.win_rate,
            }
        }

    except Exception as e:
        logger.error(f"回测失败 [{code}]: {e}")
        return {"status": "error", "message": f"回测失败: {str(e)}"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_run_backtest = partial(run_backtest, service)
    service._actions["run_backtest"] = "_handle_run_backtest"

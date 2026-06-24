"""strategies handlers — 策略文件 CRUD + 超参优化 (P6-1 + P7-5)。"""
from __future__ import annotations

import json
import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def optimize_strategy(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Optimize strategy hyperparameters (P7-5)."""
    strategy_name = req.get("strategy", "ma_cross")
    code = req.get("code", "600519")
    days = req.get("days", 120)
    n_trials = req.get("trials", 30)

    try:
        from src.strategies.optimizer import HyperOptimizer
        from src.strategies import get_python_strategy

        strategy_cls = type(get_python_strategy(strategy_name))
        if strategy_cls is None:
            return {"status": "error", "message": f"策略 '{strategy_name}' 不存在"}

        # Get history data — markets.get_history 模块函数
        from .markets import get_history
        history_result = get_history(service, {"code": code, "days": days})
        if history_result.get("status") != "ok":
            return history_result

        history_data = history_result.get("data", [])
        if len(history_data) < 30:
            return {"status": "error", "message": "历史数据不足（需要至少30天）"}

        opt = HyperOptimizer()
        result = opt.optimize(strategy_cls, history_data, n_trials=n_trials)

        return {
            "status": "ok",
            "data": result.to_dict(),
        }
    except Exception as e:
        logger.error(f"Strategy optimization failed: {e}")
        return {"status": "error", "message": str(e)}


def export_strategy(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Export current backtest configuration as a strategy JSON file."""
    name = req.get("name", "").strip()
    if not name:
        return {"status": "error", "message": "missing strategy name parameter"}

    strategy = {
        "name": name,
        "version": req.get("version", "1.0"),
        "description": req.get("description", ""),
        "author": req.get("author", ""),
        "params": req.get("params", {
            "fast_ma": 5,
            "slow_ma": 20,
            "initial_capital": 100000,
            "stop_loss_pct": -5.0,
        }),
        "code": req.get("code", "python"),
        "indicators": req.get("indicators", ["ma5", "ma20"]),
        "entry_rule": req.get("entry_rule", ""),
        "exit_rule": req.get("exit_rule", ""),
    }

    file_path = service._get_strategy_path(name)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(strategy, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "data": strategy, "message": f"Strategy '{name}' exported"}
    except OSError as e:
        logger.error(f"Failed to export strategy '{name}': {e}")
        return {"status": "error", "message": f"Export failed: {str(e)}"}


def import_strategy(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Import a strategy from JSON data (string or dict)."""
    data = req.get("data")
    if not data:
        return {"status": "error", "message": "missing strategy data parameter"}

    if isinstance(data, str):
        try:
            strategy = json.loads(data)
        except json.JSONDecodeError as e:
            return {"status": "error", "message": f"JSON parse failed: {str(e)}"}
    elif isinstance(data, dict):
        strategy = data
    else:
        return {"status": "error", "message": "data must be JSON string or dict"}

    name = strategy.get("name", "").strip()
    if not name:
        return {"status": "error", "message": "strategy data missing name field"}

    strategy.setdefault("version", "1.0")
    strategy.setdefault("description", "")
    strategy.setdefault("author", "")
    strategy.setdefault("params", {})
    strategy.setdefault("code", "python")
    strategy.setdefault("indicators", [])
    strategy.setdefault("entry_rule", "")
    strategy.setdefault("exit_rule", "")

    file_path = service._get_strategy_path(name)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(strategy, f, ensure_ascii=False, indent=2)
        return {"status": "ok", "data": strategy, "message": f"Strategy '{name}' imported"}
    except OSError as e:
        logger.error(f"Failed to import strategy '{name}': {e}")
        return {"status": "error", "message": f"Import failed: {str(e)}"}


def list_strategies(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """List all saved strategies."""
    try:
        # 加载 JSON 策略文件
        json_strategies = service._load_all_strategies()

        # P6-1: 合并 Python 内置策略
        from src.strategies.builtin import BUILTIN_STRATEGIES
        builtin_list = []
        for cls in BUILTIN_STRATEGIES:
            instance = cls()
            builtin_list.append({
                "name": instance.name,
                "display_name": instance.display_name,
                "description": instance.description,
                "category": instance.category,
                "params": instance.get_params(),
                "type": "python",
            })

        return {
            "status": "ok",
            "data": builtin_list + json_strategies,
        }
    except Exception as e:
        logger.error(f"Failed to list strategies: {e}")
        return {"status": "error", "message": f"List failed: {str(e)}"}


def delete_strategy(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Delete a saved strategy by name."""
    name = req.get("name", "").strip()
    if not name:
        return {"status": "error", "message": "missing strategy name parameter"}

    file_path = service._get_strategy_path(name)
    if not file_path.exists():
        return {"status": "error", "message": f"Strategy '{name}' not found"}

    try:
        file_path.unlink()
        return {"status": "ok", "message": f"Strategy '{name}' deleted"}
    except OSError as e:
        logger.error(f"Failed to delete strategy '{name}': {e}")
        return {"status": "error", "message": f"Delete failed: {str(e)}"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_optimize_strategy = partial(optimize_strategy, service)
    service._actions["optimize_strategy"] = "_handle_optimize_strategy"

    service._handle_export_strategy = partial(export_strategy, service)
    service._actions["export_strategy"] = "_handle_export_strategy"

    service._handle_import_strategy = partial(import_strategy, service)
    service._actions["import_strategy"] = "_handle_import_strategy"

    service._handle_list_strategies = partial(list_strategies, service)
    service._actions["list_strategies"] = "_handle_list_strategies"

    service._handle_delete_strategy = partial(delete_strategy, service)
    service._actions["delete_strategy"] = "_handle_delete_strategy"

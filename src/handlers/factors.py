"""factors handlers — 因子分析引擎 (P5-10)。"""
from __future__ import annotations

import logging
from datetime import date as date_class
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def get_factor_value(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Get factor value for a single stock.

    Request params:
        code (required): Stock code
        factor_name (required): Factor name (pe_ratio, pb_ratio, momentum_5d,
                                momentum_20d, volume_ratio, ma_golden_cross, rsi_14)
    """
    code = req.get("code")
    factor_name = req.get("factor_name")

    if not code:
        return {"status": "error", "message": "缺少 code 参数"}
    if not factor_name:
        return {"status": "error", "message": "缺少 factor_name 参数"}

    try:
        from src.factor_engine import get_factor_engine
        engine = get_factor_engine()
        value = engine.get_factor_value(code, factor_name)
        return {"status": "ok", "code": code, "factor_name": factor_name, "value": value}
    except Exception as e:
        logger.error(f"get_factor_value failed [{code}/{factor_name}]: {e}")
        return {"status": "error", "message": str(e)}


def analyze_factor_ic(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze factor IC/IR and decay metrics.

    Request params:
        factor_name (required): Factor name to analyze
        start_date (optional): Analysis start date (ISO string)
        end_date (optional): Analysis end date (ISO string)
    """
    factor_name = req.get("factor_name")
    if not factor_name:
        return {"status": "error", "message": "缺少 factor_name 参数"}

    start_date = req.get("start_date")
    end_date = req.get("end_date")

    if start_date:
        try:
            start_date = date_class.fromisoformat(start_date)
        except ValueError:
            return {"status": "error", "message": f"无效的 start_date: {start_date}"}
    if end_date:
        try:
            end_date = date_class.fromisoformat(end_date)
        except ValueError:
            return {"status": "error", "message": f"无效的 end_date: {end_date}"}

    try:
        from src.factor_engine import get_factor_engine
        engine = get_factor_engine()
        result = engine.analyze_factor_ic(factor_name, start_date, end_date)
        return {"status": "ok", "data": result}
    except Exception as e:
        logger.error(f"analyze_factor_ic failed [{factor_name}]: {e}")
        return {"status": "error", "message": str(e)}


def get_factor_rankings(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Get factor rankings across all stocks.

    Request params:
        factor_name (required): Factor name to rank
        date (optional): Ranking date (ISO string), defaults to today
        top_n (optional): Number of top stocks to return (default 50)
    """
    factor_name = req.get("factor_name")
    if not factor_name:
        return {"status": "error", "message": "缺少 factor_name 参数"}

    ranking_date = req.get("date")
    if ranking_date:
        try:
            ranking_date = date_class.fromisoformat(ranking_date)
        except ValueError:
            return {"status": "error", "message": f"无效的 date: {ranking_date}"}

    top_n = req.get("top_n", 50)
    try:
        top_n = int(top_n)
    except (ValueError, TypeError):
        top_n = 50

    try:
        from src.factor_engine import get_factor_engine
        engine = get_factor_engine()
        rankings = engine.get_factor_rankings(factor_name, ranking_date, top_n)
        return {"status": "ok", "factor_name": factor_name, "rankings": rankings}
    except Exception as e:
        logger.error(f"get_factor_rankings failed [{factor_name}]: {e}")
        return {"status": "error", "message": str(e)}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_get_factor_value = partial(get_factor_value, service)
    service._actions["get_factor_value"] = "_handle_get_factor_value"

    service._handle_analyze_factor_ic = partial(analyze_factor_ic, service)
    service._actions["analyze_factor_ic"] = "_handle_analyze_factor_ic"

    service._handle_get_factor_rankings = partial(get_factor_rankings, service)
    service._actions["get_factor_rankings"] = "_handle_get_factor_rankings"

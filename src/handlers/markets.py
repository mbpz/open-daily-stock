"""markets handlers — 行情 / 历史 / K线 / 技术指标 / 画线工具。"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any, Dict, List

from src.storage import get_db

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def get_markets(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if service._is_demo_mode():
            from src.demo_data import DEMO_STOCKS
            return {"status": "ok", "data": list(DEMO_STOCKS)}

        markets = service._get_markets()
        include_sparkline = req.get("include_sparkline", False)
        if include_sparkline:
            for m in markets:
                history = service._get_recent_prices(m.get("code"), days=10)
                m["sparkline_data"] = history
        return {"status": "ok", "data": markets}
    except Exception as e:
        logger.error(f"获取行情失败: {e}")
        return {"status": "error", "message": "获取行情失败，请稍后重试"}


def get_history(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取股票历史数据"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    days = req.get("days", 30)  # 默认 30 天

    # Demo mode: return pre-generated K-line data
    if service._is_demo_mode():
        from src.demo_data import DEMO_KLINES
        if code in DEMO_KLINES:
            klines = DEMO_KLINES[code]
            # Convert from [date, open, high, low, close, volume] to dict list
            data = []
            for row in klines:
                if isinstance(row, list) and len(row) >= 6:
                    data.append({
                        "date": str(row[0]),
                        "open": float(row[1]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                        "close": float(row[4]),
                        "volume": float(row[5]),
                        "pct_chg": 0.0,
                    })
            return {"status": "ok", "data": data[-days:] if days < len(data) else data}
        else:
            return {"status": "ok", "data": [], "message": "演示模式无此股票历史数据"}

    try:
        from data_provider.efinance_fetcher import EfinanceFetcher
        fetcher = EfinanceFetcher()
        df = fetcher.get_daily_data(code, days=days)

        if df is None or len(df) == 0:
            return {"status": "ok", "data": [], "message": "无历史数据"}

        # 转换为 dict 列表
        data = []
        for _, row in df.iterrows():
            data.append({
                "date": str(row.get("date", "")),
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)),
                "pct_chg": float(row.get("pct_chg", 0)),
            })

        return {"status": "ok", "data": data}

    except Exception as e:
        logger.error(f"获取历史数据失败 [{code}]: {e}")
        return {"status": "error", "message": f"获取历史数据失败: {str(e)}"}


def get_kline_data(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取K线图表数据"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    days = req.get("days", 60)
    indicators = req.get("indicators")

    try:
        # 先获取历史数据
        history_result = get_history(service, {"code": code, "days": days})
        if history_result.get("status") != "ok":
            return history_result

        history_data = history_result.get("data", [])
        if not history_data:
            return {"status": "ok", "data": [], "message": "无历史数据"}

        # 保存到 daily_history 表（幂等）
        try:
            saved = get_db().save_daily_history(code, history_data)
            if saved:
                logger.debug(f"Persisted {saved} new rows to daily_history for {code}")
        except Exception as e:
            logger.warning(f"Failed to persist daily_history for {code}: {e}")

        # 生成K线图表
        from src.charts import create_kline_chart
        chart_path = create_kline_chart(history_data, code, days=days, indicators=indicators)

        return {"status": "ok", "image_path": chart_path, "data": history_data}

    except Exception as e:
        logger.error(f"获取K线数据失败 [{code}]: {e}")
        return {"status": "error", "message": f"获取K线数据失败: {str(e)}"}


def get_indicators(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取技术指标数据"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    indicator_names = req.get("indicator_names")
    if not indicator_names:
        return {"status": "error", "message": "缺少 indicator_names 参数"}

    if isinstance(indicator_names, str):
        indicator_names = [indicator_names]

    days = req.get("days", 60)

    try:
        # 获取历史数据
        history_result = get_history(service, {"code": code, "days": days})
        if history_result.get("status") != "ok":
            return history_result

        history_data = history_result.get("data", [])
        if not history_data:
            return {"status": "ok", "data": {}, "message": "无历史数据"}

        # 计算指标
        from src.charts import convert_history_to_df, add_indicators
        df = convert_history_to_df(history_data)
        if df is None:
            return {"status": "ok", "data": {}, "message": "无历史数据"}

        df = add_indicators(df, indicator_names)

        # 构建返回数据
        indicator_data: Dict[str, Any] = {}
        valid_indicators = {"rsi", "macd", "bollinger", "kdj", "wr", "obv"}

        for name in indicator_names:
            name_lower = name.lower()
            if name_lower not in valid_indicators:
                continue

            if name_lower == "rsi":
                indicator_data["rsi"] = df["RSI"].dropna().to_dict()
            elif name_lower == "macd":
                indicator_data["macd"] = {
                    "macd": df["MACD"].dropna().to_dict(),
                    "dif": df["DIF"].dropna().to_dict(),
                    "dea": df["DEA"].dropna().to_dict(),
                }
            elif name_lower == "bollinger":
                indicator_data["bollinger"] = {
                    "upper": df["BB_UPPER"].dropna().to_dict(),
                    "middle": df["BB_MIDDLE"].dropna().to_dict(),
                    "lower": df["BB_LOWER"].dropna().to_dict(),
                }
            elif name_lower == "kdj":
                indicator_data["kdj"] = {
                    "k": df["K"].dropna().to_dict(),
                    "d": df["D"].dropna().to_dict(),
                    "j": df["J"].dropna().to_dict(),
                }
            elif name_lower == "wr":
                indicator_data["wr"] = df["WR"].dropna().to_dict()
            elif name_lower == "obv":
                indicator_data["obv"] = df["OBV"].dropna().to_dict()

        return {"status": "ok", "data": indicator_data}

    except Exception as e:
        logger.error(f"获取技术指标失败 [{code}]: {e}")
        return {"status": "error", "message": f"获取技术指标失败: {str(e)}"}


def get_drawing_data(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取画线工具数据（支撑/阻力位、斐波那契回调线）"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    days = req.get("days", 60)

    try:
        from src.charts import convert_history_to_df
        from src.shared.indicators import find_support_resistance, calculate_fibonacci_levels

        # 获取历史数据
        history_data = get_db().get_data_range(
            code,
            date.today() - timedelta(days=days),
            date.today()
        )
        if not history_data:
            return {"status": "ok", "data": {}, "message": "无历史数据"}

        df = convert_history_to_df(history_data)
        if df is None or len(df) == 0:
            return {"status": "ok", "data": {}, "message": "无历史数据"}

        sr = find_support_resistance(df)
        high = float(df['High'].max())
        low = float(df['Low'].min())
        fib = calculate_fibonacci_levels(high, low)

        return {
            "status": "ok",
            "support_resistance": sr,
            "fibonacci": fib,
            "high": high,
            "low": low,
        }
    except Exception as e:
        logger.error(f"获取画线数据失败 [{code}]: {e}")
        return {"status": "error", "message": f"获取画线数据失败: {str(e)}"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_get_markets = partial(get_markets, service)
    service._actions["get_markets"] = "_handle_get_markets"

    service._handle_get_history = partial(get_history, service)
    service._actions["get_history"] = "_handle_get_history"

    service._handle_get_kline_data = partial(get_kline_data, service)
    service._actions["get_kline_data"] = "_handle_get_kline_data"

    service._handle_get_indicators = partial(get_indicators, service)
    service._actions["get_indicators"] = "_handle_get_indicators"

    service._handle_get_drawing_data = partial(get_drawing_data, service)
    service._actions["get_drawing_data"] = "_handle_get_drawing_data"

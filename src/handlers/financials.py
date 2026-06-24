"""financials handlers — 财务报表 / 关键指标 (P4-3)。"""
from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

from src.financials import FinancialDataFetcher, _safe_float

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def get_financials(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取财务报表数据（利润表/资产负债表/现金流量表）"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    statement_type = req.get("type", "income")
    if statement_type not in ("income", "balance", "cashflow"):
        return {"status": "error", "message": f"不支持的报表类型: {statement_type}，支持: income/balance/cashflow"}

    try:
        from src.analyzer import STOCK_NAME_MAP
        name = STOCK_NAME_MAP.get(code, code)

        fetcher = FinancialDataFetcher()
        df = fetcher.get_financial_report_df(code, statement_type)

        if df is None or len(df) == 0:
            return {"status": "ok", "data": {
                "code": code, "name": name, "type": statement_type,
                "periods": [], "items": [],
            }, "message": "无财务数据"}

        # Find the period/date column
        period_col = None
        for col in ["报告期", "REPORT_DATE", "报告日期"]:
            if col in df.columns:
                period_col = col
                break

        if period_col is None:
            for col in df.columns[:3]:
                period_col = col
                break

        # Get periods (most recent first)
        periods = df[period_col].astype(str).tolist()[-8:]

        # Get key financial items with column name mappings
        if statement_type == "income":
            key_items = [
                ("营业总收入", "TOTALOPERATEREVE", "OPERATEREVE"),
                ("营业收入", "OPERATEREVE", "营业总收入"),
                ("营业成本", "TOTALOPERATEEXP", "OPERATEEXP"),
                ("净利润", "NETPROFIT", "KCFL"),
                ("营业利润", "OPERATEPROFIT", "TOTALPROFIT"),
            ]
        elif statement_type == "balance":
            key_items = [
                ("资产总计", "TOTALASSETS"),
                ("负债合计", "TOTALLIABILITIES"),
                ("股东权益合计", "EQUITYTOTAL", "归属于母公司股东权益合计"),
                ("流动资产合计", "TOTALCURRENTASSETS"),
                ("流动负债合计", "TOTALCURRENTLIABILITIES"),
            ]
        else:
            key_items = [
                ("经营活动现金流量净额", "CASHFLOWOPERATE"),
                ("投资活动现金流量净额", "CASHFLOWINVEST"),
                ("筹资活动现金流量净额", "CASHFLOWFINANCE"),
                ("期末现金余额", "期末现金及现金等价物余额"),
            ]

        # Extract items from dataframe
        items = []
        for item_def in key_items:
            chinese_name = item_def[0]
            candidates = list(item_def)
            col_name = None
            for candidate in candidates:
                if candidate and candidate in df.columns:
                    col_name = candidate
                    break

            if col_name is None:
                for col in df.columns:
                    if isinstance(col, str) and chinese_name[:2] in col:
                        col_name = col
                        break

            if col_name is not None:
                values = df[col_name].tolist()[-8:]
                values = [_safe_float(v) for v in values]
                items.append({"name": chinese_name, "values": values})

        return {"status": "ok", "data": {
            "code": code,
            "name": name,
            "type": statement_type,
            "periods": periods,
            "items": items,
        }}

    except ImportError:
        logger.warning(f"获取财务报表失败 [{code}]: akshare 未安装")
        return {"status": "error", "message": "财务报表功能需要 akshare 库支持，请安装 akshare"}
    except Exception as e:
        logger.error(f"获取财务报表失败 [{code}]: {e}")
        return {"status": "error", "message": f"获取财务报表失败: {str(e)}"}


def get_key_metrics(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取股票关键财务指标（PE/PB/ROE/市值/增长率等）"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    try:
        fetcher = FinancialDataFetcher()
        data = fetcher.get_key_metrics(code)
        if data is None:
            return {"status": "error", "message": f"获取 {code} 关键指标失败: 无数据"}
        return {"status": "ok", "data": data}
    except ImportError:
        logger.warning(f"获取关键指标失败 [{code}]: akshare 未安装")
        return {"status": "error", "message": "关键指标功能需要 akshare 库支持，请安装 akshare"}
    except Exception as e:
        logger.error(f"获取关键指标失败 [{code}]: {e}")
        return {"status": "error", "message": f"获取关键指标失败: {str(e)}"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_get_financials = partial(get_financials, service)
    service._actions["get_financials"] = "_handle_get_financials"

    service._handle_get_key_metrics = partial(get_key_metrics, service)
    service._actions["get_key_metrics"] = "_handle_get_key_metrics"

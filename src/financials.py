"""Financial statement data fetcher using AkShare."""
import logging
from typing import Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)


def _safe_float(value):
    """Safely convert value to float."""
    if value is None:
        return 0.0
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


class FinancialDataFetcher:
    """Fetch financial statements for A-share stocks using AkShare."""

    @staticmethod
    def get_income_statement(code: str) -> Optional[Dict]:
        """Get latest income statement (利润表).

        Returns dict with: report_date, revenue, total_cost, operating_profit,
                          total_profit, net_profit, parent_net_profit
        """
        try:
            import akshare as ak
            df = ak.stock_profit_sheet_by_report_em(symbol=code)
            if df is None or df.empty:
                return None
            latest = df.iloc[-1]
            return {
                "report_date": str(latest.get("报告期", "")),
                "revenue": _safe_float(
                    latest.get("TOTALOPERATEREVE", 0)
                    or latest.get("OPERATEREVE", 0)
                ),
                "total_cost": _safe_float(
                    latest.get("TOTALOPERATEEXP", 0)
                    or latest.get("OPERATEEXP", 0)
                ),
                "operating_profit": _safe_float(latest.get("OPERATEPROFIT", 0)),
                "total_profit": _safe_float(latest.get("TOTALPROFIT", 0)),
                "net_profit": _safe_float(latest.get("NETPROFIT", 0)),
                "parent_net_profit": _safe_float(
                    latest.get("PARENTNETPROFIT", 0)
                ),
            }
        except ImportError:
            logger.warning("akshare 未安装")
            return None
        except Exception as e:
            logger.error(f"获取利润表失败 {code}: {e}")
            return None

    @staticmethod
    def get_balance_sheet(code: str) -> Optional[Dict]:
        """Get latest balance sheet (资产负债表).

        Returns dict with: report_date, total_assets, total_liabilities,
                          shareholder_equity, current_assets, current_liabilities
        """
        try:
            import akshare as ak
            df = ak.stock_balance_sheet_by_report_em(symbol=code)
            if df is None or df.empty:
                return None
            latest = df.iloc[-1]
            return {
                "report_date": str(latest.get("报告期", "")),
                "total_assets": _safe_float(latest.get("TOTALASSETS", 0)),
                "total_liabilities": _safe_float(latest.get("TOTALLIABILITIES", 0)),
                "shareholder_equity": _safe_float(latest.get("EQUITYTOTAL", 0)),
                "current_assets": _safe_float(latest.get("TOTALCURRENTASSETS", 0)),
                "current_liabilities": _safe_float(latest.get("TOTALCURRENTLIABILITIES", 0)),
            }
        except ImportError:
            logger.warning("akshare 未安装")
            return None
        except Exception as e:
            logger.error(f"获取资产负债表失败 {code}: {e}")
            return None

    @staticmethod
    def get_cash_flow(code: str) -> Optional[Dict]:
        """Get latest cash flow statement (现金流量表).

        Returns dict with: report_date, operating_cf, investing_cf,
                          financing_cf, net_cf_increase
        """
        try:
            import akshare as ak
            df = ak.stock_cash_flow_sheet_by_report_em(symbol=code)
            if df is None or df.empty:
                return None
            latest = df.iloc[-1]
            return {
                "report_date": str(latest.get("报告期", "")),
                "operating_cf": _safe_float(latest.get("CASHFLOWOPERATE", 0)),
                "investing_cf": _safe_float(latest.get("CASHFLOWINVEST", 0)),
                "financing_cf": _safe_float(latest.get("CASHFLOWFINANCE", 0)),
                "net_cf_increase": _safe_float(
                    latest.get("期末现金及现金等价物余额", 0)
                ),
            }
        except ImportError:
            logger.warning("akshare 未安装")
            return None
        except Exception as e:
            logger.error(f"获取现金流量表失败 {code}: {e}")
            return None

    @staticmethod
    def get_key_metrics(code: str) -> Optional[Dict]:
        """Get key financial metrics from 东方财富.

        Returns dict keyed by metric name with values like: 总市值, 流通市值,
        市盈率, 市净率, 净资产收益率, 净利润, 净利润增长率, 毛利率, 净利率, etc.
        """
        try:
            import akshare as ak
            df = ak.stock_individual_info_em(symbol=code)
            if df is None or df.empty:
                return None
            info = {}
            for _, row in df.iterrows():
                info[str(row["item"])] = row["value"]
            return info
        except ImportError:
            logger.warning("akshare 未安装")
            return None
        except Exception as e:
            logger.error(f"获取关键指标失败 {code}: {e}")
            return None

    @staticmethod
    def get_financial_report_df(
        code: str, statement_type: str
    ) -> Optional[pd.DataFrame]:
        """Get raw financial report DataFrame for multi-period analysis.

        Args:
            code: Stock code (e.g. "600519")
            statement_type: One of "income", "balance", "cashflow"

        Returns:
            Raw DataFrame from akshare, or None on failure.
        """
        try:
            import akshare as ak
        except ImportError:
            raise  # Let caller handle missing akshare

        try:
            if statement_type == "income":
                return ak.stock_profit_sheet_by_report_em(symbol=code)
            elif statement_type == "balance":
                return ak.stock_balance_sheet_by_report_em(symbol=code)
            elif statement_type == "cashflow":
                return ak.stock_cash_flow_sheet_by_report_em(symbol=code)
            else:
                logger.error(f"不支持的报表类型: {statement_type}")
                return None
        except Exception as e:
            logger.error(f"获取财务报表失败 {code}/{statement_type}: {e}")
            return None

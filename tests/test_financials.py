# -*- coding: utf-8 -*-
"""Tests for financial statement module (P4-3)."""
import sys
import pytest
from unittest.mock import patch, MagicMock
import pandas as pd


# ============================================================
# FinancialDataFetcher Unit Tests
# ============================================================

def _make_mock_akshare(mock_df):
    """Create a mock akshare module with the given DataFrame."""
    mock_ak = MagicMock()
    mock_ak.stock_profit_sheet_by_report_em.return_value = mock_df
    mock_ak.stock_balance_sheet_by_report_em.return_value = mock_df
    mock_ak.stock_cash_flow_sheet_by_report_em.return_value = mock_df
    mock_ak.stock_individual_info_em.return_value = pd.DataFrame({
        "item": ["总市值", "流通市值", "行业", "上市时间", "股票代码", "总股本",
                  "流通股", "市盈率-动态", "市净率"],
        "value": [200000000000, 180000000000, "白酒", "20010827", "600519",
                  1256197800, 1256197800, 25.5, 8.2],
    })
    return mock_ak


class TestFinancialDataFetcher:
    """Unit tests for FinancialDataFetcher in src/financials.py."""

    def test_import(self):
        """FinancialDataFetcher should be importable."""
        from src.financials import FinancialDataFetcher
        assert FinancialDataFetcher is not None

    def test_income_statement_structure(self):
        """get_income_statement should return dict with expected keys."""
        mock_df = pd.DataFrame({
            "报告期": ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"],
            "TOTALOPERATEREVE": [15000000000, 30000000000, 45000000000, 60000000000],
            "TOTALOPERATEEXP": [12000000000, 25000000000, 37000000000, 50000000000],
            "OPERATEPROFIT": [3000000000, 5000000000, 8000000000, 10000000000],
            "TOTALPROFIT": [3000000000, 5000000000, 8000000000, 10000000000],
            "NETPROFIT": [2000000000, 4000000000, 6000000000, 8000000000],
            "PARENTNETPROFIT": [2000000000, 4000000000, 6000000000, 8000000000],
        })
        mock_ak = _make_mock_akshare(mock_df)
        mock_ak.stock_profit_sheet_by_report_em.return_value = mock_df

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.financials import FinancialDataFetcher
            result = FinancialDataFetcher.get_income_statement("600519")

        assert result is not None
        assert "report_date" in result
        assert "revenue" in result
        assert "total_cost" in result
        assert "operating_profit" in result
        assert "total_profit" in result
        assert "net_profit" in result
        assert "parent_net_profit" in result
        # Latest report should be the last row
        assert result["revenue"] == 60000000000
        assert result["net_profit"] == 8000000000

    def test_balance_sheet_structure(self):
        """get_balance_sheet should return dict with expected keys."""
        mock_df = pd.DataFrame({
            "报告期": ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"],
            "TOTALASSETS": [100000000000, 105000000000, 110000000000, 120000000000],
            "TOTALLIABILITIES": [50000000000, 52000000000, 55000000000, 58000000000],
            "EQUITYTOTAL": [50000000000, 53000000000, 55000000000, 62000000000],
            "TOTALCURRENTASSETS": [60000000000, 62000000000, 65000000000, 70000000000],
            "TOTALCURRENTLIABILITIES": [30000000000, 31000000000, 33000000000, 35000000000],
        })
        mock_ak = _make_mock_akshare(mock_df)
        mock_ak.stock_balance_sheet_by_report_em.return_value = mock_df

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.financials import FinancialDataFetcher
            result = FinancialDataFetcher.get_balance_sheet("600519")

        assert result is not None
        assert "report_date" in result
        assert "total_assets" in result
        assert "total_liabilities" in result
        assert "shareholder_equity" in result
        assert "current_assets" in result
        assert "current_liabilities" in result
        assert result["total_assets"] == 120000000000
        assert result["shareholder_equity"] == 62000000000

    def test_cash_flow_structure(self):
        """get_cash_flow should return dict with expected keys."""
        mock_df = pd.DataFrame({
            "报告期": ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"],
            "CASHFLOWOPERATE": [1000000000, 3000000000, 4500000000, 6500000000],
            "CASHFLOWINVEST": [-500000000, -1500000000, -2000000000, -3000000000],
            "CASHFLOWFINANCE": [-200000000, -800000000, -1200000000, -2000000000],
            "期末现金及现金等价物余额": [8000000000, 9500000000, 10200000000, 11700000000],
        })
        mock_ak = _make_mock_akshare(mock_df)
        mock_ak.stock_cash_flow_sheet_by_report_em.return_value = mock_df

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.financials import FinancialDataFetcher
            result = FinancialDataFetcher.get_cash_flow("600519")

        assert result is not None
        assert "report_date" in result
        assert "operating_cf" in result
        assert "investing_cf" in result
        assert "financing_cf" in result
        assert "net_cf_increase" in result
        assert result["operating_cf"] == 6500000000
        assert result["investing_cf"] == -3000000000

    def test_get_key_metrics_structure(self):
        """get_key_metrics should return dict with metric items."""
        mock_ak = _make_mock_akshare(pd.DataFrame())

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.financials import FinancialDataFetcher
            result = FinancialDataFetcher.get_key_metrics("600519")

        assert result is not None
        assert isinstance(result, dict)
        assert "总市值" in result
        assert "市盈率-动态" in result
        assert "市净率" in result

    def test_nonexistent_code_returns_none(self):
        """Akshare exception should result in None return."""
        mock_ak = _make_mock_akshare(pd.DataFrame())
        mock_ak.stock_profit_sheet_by_report_em.side_effect = Exception("API error")

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.financials import FinancialDataFetcher
            result = FinancialDataFetcher.get_income_statement("INVALID")

        assert result is None

    def test_empty_dataframe_returns_none(self):
        """Empty DataFrame should result in None."""
        mock_ak = _make_mock_akshare(pd.DataFrame())
        mock_ak.stock_profit_sheet_by_report_em.return_value = pd.DataFrame()

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.financials import FinancialDataFetcher
            result = FinancialDataFetcher.get_income_statement("600519")

        assert result is None

    def test_get_financial_report_df_income(self):
        """get_financial_report_df with income type returns DataFrame."""
        mock_df = pd.DataFrame({
            "报告期": ["2024-12-31"],
            "TOTALOPERATEREVE": [60000000000],
        })
        mock_ak = _make_mock_akshare(mock_df)
        mock_ak.stock_profit_sheet_by_report_em.return_value = mock_df

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.financials import FinancialDataFetcher
            result = FinancialDataFetcher.get_financial_report_df("600519", "income")

        assert result is not None
        assert len(result) == 1
        assert "TOTALOPERATEREVE" in result.columns

    def test_get_financial_report_df_balance(self):
        """get_financial_report_df with balance type returns DataFrame."""
        mock_df = pd.DataFrame({
            "报告期": ["2024-12-31"],
            "TOTALASSETS": [120000000000],
        })
        mock_ak = _make_mock_akshare(mock_df)
        mock_ak.stock_balance_sheet_by_report_em.return_value = mock_df

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.financials import FinancialDataFetcher
            result = FinancialDataFetcher.get_financial_report_df("600519", "balance")

        assert result is not None
        assert "TOTALASSETS" in result.columns

    def test_get_financial_report_df_cashflow(self):
        """get_financial_report_df with cashflow type returns DataFrame."""
        mock_df = pd.DataFrame({
            "报告期": ["2024-12-31"],
            "CASHFLOWOPERATE": [6500000000],
        })
        mock_ak = _make_mock_akshare(mock_df)
        mock_ak.stock_cash_flow_sheet_by_report_em.return_value = mock_df

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.financials import FinancialDataFetcher
            result = FinancialDataFetcher.get_financial_report_df("600519", "cashflow")

        assert result is not None
        assert "CASHFLOWOPERATE" in result.columns

    def test_get_financial_report_df_invalid_type(self):
        """get_financial_report_df with invalid type should return None."""
        with patch.dict(sys.modules, {"akshare": MagicMock()}):
            from src.financials import FinancialDataFetcher
            result = FinancialDataFetcher.get_financial_report_df("600519", "invalid")
        assert result is None


# ============================================================
# DataService Financial Action Tests
# ============================================================

class TestDataServiceFinancialsAction:
    """Test DataService get_financials and get_key_metrics actions."""

    # ---- get_financials tests ----

    def test_get_financials_action_exists(self):
        """DataService should have get_financials and get_key_metrics actions."""
        from src.data_service import DataService
        service = DataService()
        assert "get_financials" in service._actions
        assert hasattr(service, "_handle_get_financials")
        assert "get_key_metrics" in service._actions
        assert hasattr(service, "_handle_get_key_metrics")

    def test_get_financials_missing_code(self):
        """get_financials without code should return error."""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_financials"})
        assert result.get("status") == "error"
        assert "code" in result.get("message", "").lower()

    def test_get_financials_invalid_type(self):
        """get_financials with invalid type should return error."""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "get_financials",
            "code": "600519",
            "type": "invalid",
        })
        assert result.get("status") == "error"
        assert "income" in result.get("message", "").lower()

    def test_get_financials_income_with_mock(self):
        """get_financials with income type should return structured table data."""
        mock_df = pd.DataFrame({
            "报告期": ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"],
            "TOTALOPERATEREVE": [15000000000, 30000000000, 45000000000, 60000000000],
            "TOTALOPERATEEXP": [12000000000, 25000000000, 37000000000, 50000000000],
            "NETPROFIT": [2000000000, 4000000000, 6000000000, 8000000000],
            "OPERATEPROFIT": [3000000000, 5000000000, 8000000000, 10000000000],
        })
        mock_ak = _make_mock_akshare(mock_df)
        mock_ak.stock_profit_sheet_by_report_em.return_value = mock_df

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            with patch("src.analyzer.STOCK_NAME_MAP", {"600519": "贵州茅台"}):
                from src.data_service import DataService
                service = DataService()
                result = service._handle_request({
                    "action": "get_financials",
                    "code": "600519",
                    "type": "income",
                })

        assert result.get("status") == "ok"
        assert result["data"]["code"] == "600519"
        assert result["data"]["name"] == "贵州茅台"
        assert result["data"]["type"] == "income"
        assert len(result["data"]["periods"]) == 4
        assert len(result["data"]["items"]) >= 1
        assert result["data"]["items"][0]["name"] == "营业总收入"
        assert len(result["data"]["items"][0]["values"]) == 4

    def test_get_financials_balance_with_mock(self):
        """get_financials with balance type should return structured table data."""
        mock_df = pd.DataFrame({
            "报告期": ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"],
            "TOTALASSETS": [100000000000, 105000000000, 110000000000, 120000000000],
            "TOTALLIABILITIES": [50000000000, 52000000000, 55000000000, 58000000000],
            "EQUITYTOTAL": [50000000000, 53000000000, 55000000000, 62000000000],
        })
        mock_ak = _make_mock_akshare(mock_df)
        mock_ak.stock_balance_sheet_by_report_em.return_value = mock_df

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            with patch("src.analyzer.STOCK_NAME_MAP", {"600519": "贵州茅台"}):
                from src.data_service import DataService
                service = DataService()
                result = service._handle_request({
                    "action": "get_financials",
                    "code": "600519",
                    "type": "balance",
                })

        assert result.get("status") == "ok"
        assert result["data"]["type"] == "balance"
        assert len(result["data"]["items"]) >= 1
        assert result["data"]["items"][0]["name"] == "资产总计"

    def test_get_financials_cashflow_with_mock(self):
        """get_financials with cashflow type should return structured table data."""
        mock_df = pd.DataFrame({
            "报告期": ["2024-03-31", "2024-06-30", "2024-09-30", "2024-12-31"],
            "CASHFLOWOPERATE": [1000000000, 3000000000, 4500000000, 6500000000],
            "CASHFLOWINVEST": [-500000000, -1500000000, -2000000000, -3000000000],
            "CASHFLOWFINANCE": [-200000000, -800000000, -1200000000, -2000000000],
            "期末现金及现金等价物余额": [8000000000, 9500000000, 10200000000, 11700000000],
        })
        mock_ak = _make_mock_akshare(mock_df)
        mock_ak.stock_cash_flow_sheet_by_report_em.return_value = mock_df

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            with patch("src.analyzer.STOCK_NAME_MAP", {"600519": "贵州茅台"}):
                from src.data_service import DataService
                service = DataService()
                result = service._handle_request({
                    "action": "get_financials",
                    "code": "600519",
                    "type": "cashflow",
                })

        assert result.get("status") == "ok"
        assert result["data"]["type"] == "cashflow"
        assert len(result["data"]["items"]) >= 1
        assert result["data"]["items"][0]["name"] == "经营活动现金流量净额"

    def test_get_financials_handles_akshare_unavailable(self):
        """get_financials should handle akshare not installed gracefully."""
        with patch.dict(sys.modules, {"akshare": None}):
            from src.data_service import DataService
            service = DataService()
            result = service._handle_request({
                "action": "get_financials",
                "code": "600519",
                "type": "income",
            })

        assert result.get("status") == "error"
        assert "akshare" in result.get("message", "").lower()

    # ---- get_key_metrics tests ----

    def test_get_key_metrics_action_exists(self):
        """DataService should have get_key_metrics action registered."""
        from src.data_service import DataService
        service = DataService()
        assert "get_key_metrics" in service._actions

    def test_get_key_metrics_missing_code(self):
        """get_key_metrics without code should return error."""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_key_metrics"})
        assert result.get("status") == "error"
        assert "code" in result.get("message", "").lower()

    def test_get_key_metrics_with_mock(self):
        """get_key_metrics should return key metrics dict."""
        mock_ak = _make_mock_akshare(pd.DataFrame())

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.data_service import DataService
            service = DataService()
            result = service._handle_request({
                "action": "get_key_metrics",
                "code": "600519",
            })

        assert result.get("status") == "ok"
        assert isinstance(result.get("data"), dict)
        assert "总市值" in result["data"]
        assert "市盈率-动态" in result["data"]

    def test_get_key_metrics_handles_fetch_failure(self):
        """get_key_metrics should handle fetch failure gracefully."""
        mock_ak = _make_mock_akshare(pd.DataFrame())
        mock_ak.stock_individual_info_em.side_effect = Exception("Network error")

        with patch.dict(sys.modules, {"akshare": mock_ak}):
            from src.data_service import DataService
            service = DataService()
            result = service._handle_request({
                "action": "get_key_metrics",
                "code": "600519",
            })

        assert result.get("status") == "error"

    def test_get_key_metrics_handles_akshare_unavailable(self):
        """get_key_metrics should handle akshare not installed gracefully."""
        with patch.dict(sys.modules, {"akshare": None}):
            from src.data_service import DataService
            service = DataService()
            result = service._handle_request({
                "action": "get_key_metrics",
                "code": "600519",
            })

        assert result.get("status") == "error"


# ============================================================
# Utility Tests
# ============================================================

class TestFinancialsSafeFloat:
    """Test _safe_float helper in both financials.py and data_service.py."""

    def test_safe_float_none(self):
        from src.financials import _safe_float
        assert _safe_float(None) == 0.0

    def test_safe_float_number(self):
        from src.financials import _safe_float
        assert _safe_float(123.45) == 123.45

    def test_safe_float_string(self):
        from src.financials import _safe_float
        assert _safe_float("123.45") == 123.45

    def test_safe_float_invalid(self):
        from src.financials import _safe_float
        assert _safe_float("abc") == 0.0

    def test_safe_float_data_service_still_works(self):
        """_safe_float is importable from src.financials (deduplicated from DataService)."""
        from src.financials import _safe_float
        assert _safe_float(None) == 0.0
        assert _safe_float(123.45) == 123.45

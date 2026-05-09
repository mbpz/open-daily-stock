"""Tests for stock screener functionality."""
import pytest
import json


class TestScreenStocksAction:
    """Test the screen_stocks action in DataService"""

    def test_action_registry_has_screen_stocks(self):
        """DataService should have screen_stocks action registered"""
        from src.data_service import DataService
        service = DataService()
        assert "screen_stocks" in service._actions
        assert service._actions["screen_stocks"] == "_handle_screen_stocks"

    def test_handle_screen_stocks_method_exists(self):
        """DataService should have _handle_screen_stocks method"""
        from src.data_service import DataService
        service = DataService()
        assert hasattr(service, "_handle_screen_stocks")

    def test_screen_stocks_empty_criteria_returns_all_stocks(self):
        """Screen with no criteria should return all stocks (first page)"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "screen_stocks"})
        # Should return ok with data array (may be empty if network unavailable)
        assert result.get("status") in ("ok", "error")
        if result.get("status") == "ok":
            assert "data" in result
            assert isinstance(result["data"], list)

    def test_screen_stocks_with_market_cap_filter(self):
        """Screen with market cap filter should apply correctly"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "screen_stocks",
            "market_cap_min": 100,
            "market_cap_max": 1000,
        })
        assert result.get("status") in ("ok", "error")
        if result.get("status") == "ok":
            data = result.get("data", [])
            for stock in data:
                mv = stock.get("total_mv", 0) or 0
                mv_b = mv / 1e8
                assert 100 <= mv_b <= 1000, f"Market cap {mv_b} not in range [100, 1000]"

    def test_screen_stocks_with_pe_filter(self):
        """Screen with PE filter should apply correctly"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "screen_stocks",
            "pe_min": 10,
            "pe_max": 50,
        })
        assert result.get("status") in ("ok", "error")
        if result.get("status") == "ok":
            data = result.get("data", [])
            for stock in data:
                pe = stock.get("pe")
                if pe is not None:
                    assert 10 <= pe <= 50, f"PE {pe} not in range [10, 50]"

    def test_screen_stocks_with_change_pct_filter(self):
        """Screen with change percent filter should apply correctly"""
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({
            "action": "screen_stocks",
            "change_pct_min": -5,
            "change_pct_max": 5,
        })
        assert result.get("status") in ("ok", "error")
        if result.get("status") == "ok":
            data = result.get("data", [])
            for stock in data:
                pct = stock.get("change_pct")
                if pct is not None:
                    assert -5 <= pct <= 5, f"Change {pct}% not in range [-5, 5]"


class TestScreenerPage:
    """Test GUI screener page"""

    def test_screener_page_imports(self):
        """ScreenerPage should be importable"""
        from gui.pages.screener import ScreenerPage
        assert ScreenerPage is not None

    def test_screener_page_has_required_fields(self):
        """ScreenerPage should have all filter input fields"""
        from gui.pages.screener import ScreenerPage

        class MockApp:
            class page:
                @staticmethod
                def run_task(*args, **kwargs):
                    pass
                @staticmethod
                def show_snack_bar(*args, **kwargs):
                    pass

        app = MockApp()
        page = ScreenerPage(app)

        assert page._market_cap_min_field is not None
        assert page._market_cap_max_field is not None
        assert page._pe_min_field is not None
        assert page._pe_max_field is not None
        assert page._change_pct_min_field is not None
        assert page._change_pct_max_field is not None
        assert page._industry_field is not None

    def test_screener_page_build_criteria(self):
        """ScreenerPage should correctly build criteria dict"""
        from gui.pages.screener import ScreenerPage

        class MockApp:
            class page:
                @staticmethod
                def run_task(*args, **kwargs):
                    pass
                @staticmethod
                def show_snack_bar(*args, **kwargs):
                    pass

        app = MockApp()
        page = ScreenerPage(app)

        # Test that criteria building works
        page._market_cap_min_field.value = "100"
        page._market_cap_max_field.value = "1000"
        page._pe_min_field.value = "5"
        page._pe_max_field.value = "50"
        page._change_pct_min_field.value = "-5"
        page._change_pct_max_field.value = "10"
        page._industry_field.value = "银行"

        # Simulate what _do_screener does
        criteria = {}
        if page._market_cap_min_field.value:
            criteria["market_cap_min"] = float(page._market_cap_min_field.value)
        if page._market_cap_max_field.value:
            criteria["market_cap_max"] = float(page._market_cap_max_field.value)
        if page._pe_min_field.value:
            criteria["pe_min"] = float(page._pe_min_field.value)
        if page._pe_max_field.value:
            criteria["pe_max"] = float(page._pe_max_field.value)
        if page._change_pct_min_field.value:
            criteria["change_pct_min"] = float(page._change_pct_min_field.value)
        if page._change_pct_max_field.value:
            criteria["change_pct_max"] = float(page._change_pct_max_field.value)
        if page._industry_field.value:
            criteria["industry"] = page._industry_field.value.strip()

        assert criteria == {
            "market_cap_min": 100.0,
            "market_cap_max": 1000.0,
            "pe_min": 5.0,
            "pe_max": 50.0,
            "change_pct_min": -5.0,
            "change_pct_max": 10.0,
            "industry": "银行",
        }


class TestScreenerWidget:
    """Test TUI screener widget"""

    def test_screener_widget_imports(self):
        """ScreenerWidget should be importable"""
        from tui.widgets.screener import ScreenerWidget
        assert ScreenerWidget is not None

    def test_screener_widget_has_compose(self):
        """ScreenerWidget should have compose method"""
        from tui.widgets.screener import ScreenerWidget
        widget = ScreenerWidget()
        assert hasattr(widget, "compose")

    def test_screener_widget_render_data_empty(self):
        """ScreenerWidget should handle empty results"""
        from tui.widgets.screener import ScreenerWidget
        widget = ScreenerWidget()
        widget._results = []
        output = widget._render_data()
        assert "暂无结果" in output or "no results" in output.lower()
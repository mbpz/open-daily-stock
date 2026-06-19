"""Tests for the AsyncTaskMixin integration in financials.py and screener.py.

These tests verify the migration by importing the actual page classes
(after our refactor) and checking they have the mixin API + correct
runtime behavior. We use ``__new__`` to bypass full Flet __init__ and
avoid metaclass conflicts when ft is stubbed.
"""
import asyncio
import importlib
import sys
import threading
from unittest.mock import AsyncMock, MagicMock


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _build_minimal_instance(cls):
    """Build an instance of a Flet page with the minimum attributes
    AsyncTaskMixin and the page's methods need."""
    p = cls.__new__(cls)
    p._cancel_event = threading.Event()
    p._active_tasks = []
    p.app = MagicMock()
    p.app.page = MagicMock()
    p._status_text = MagicMock()
    p._status_text.value = ""
    p._status_text.visible = False
    return p


def test_financials_page_class_inherits_mixin():
    """Class-level: FinancialsPage must be a subclass of AsyncTaskMixin."""
    import gui.components.async_task  # ensure loaded
    from gui.pages.financials import FinancialsPage
    from gui.components.async_task import AsyncTaskMixin
    assert issubclass(FinancialsPage, AsyncTaskMixin)


def test_screener_page_class_inherits_mixin():
    from gui.pages.screener import ScreenerPage
    from gui.components.async_task import AsyncTaskMixin
    assert issubclass(ScreenerPage, AsyncTaskMixin)


def test_financials_instance_has_mixin_methods():
    from gui.pages.financials import FinancialsPage
    p = _build_minimal_instance(FinancialsPage)
    # The instance should have all the mixin methods
    for method in ("cancel", "check_cancelled", "is_cancelled",
                   "reset_cancellation", "set_busy", "set_idle",
                   "set_status", "show_error", "show_result", "run_async"):
        assert hasattr(p, method), f"FinancialsPage missing {method}"


def test_screener_instance_has_mixin_methods():
    from gui.pages.screener import ScreenerPage
    p = _build_minimal_instance(ScreenerPage)
    for method in ("cancel", "check_cancelled", "set_busy", "set_idle",
                   "set_status", "show_error", "show_result", "run_async"):
        assert hasattr(p, method), f"ScreenerPage missing {method}"


def test_financials_query_validates_input_via_set_status():
    """Empty stock code should call set_status and not launch a task."""
    from gui.pages.financials import FinancialsPage
    p = _build_minimal_instance(FinancialsPage)
    p._stock_input = MagicMock()
    p._stock_input.value = "   "
    p._type_dropdown = MagicMock()
    p._type_dropdown.value = "income"
    p.set_status = MagicMock()
    p.run_async = MagicMock()

    p._query_financials(None)

    p.set_status.assert_called_once()
    p.run_async.assert_not_called()


def test_financials_fetch_cancelled_before_call_returns_early():
    from gui.pages.financials import FinancialsPage
    p = _build_minimal_instance(FinancialsPage)
    p._cancel_event.set()  # pre-cancelled
    p._client = MagicMock()
    p._client._send_request = MagicMock()
    p._display_table = MagicMock()
    p._result_area = MagicMock()

    _run(p._fetch_financials("600519", "income"))

    p._client._send_request.assert_not_called()
    p._display_table.assert_not_called()


def test_screener_cancellation_skips_expensive_call():
    from gui.pages.screener import ScreenerPage
    p = _build_minimal_instance(ScreenerPage)
    p._cancel_event.set()  # pre-cancelled
    p._service_client = MagicMock()
    p._service_client.screen_stocks = AsyncMock(
        return_value={"status": "ok", "data": []}
    )
    p._update_results = MagicMock()

    _run(p._run_screener_async({}))

    p._service_client.screen_stocks.assert_not_called()
    p._update_results.assert_not_called()


def test_screener_builds_criteria_from_fields():
    from gui.pages.screener import ScreenerPage
    p = _build_minimal_instance(ScreenerPage)
    p._service_client = MagicMock()  # not None -> not the early-return path

    p._market_cap_min_field = MagicMock(value="100")
    p._market_cap_max_field = MagicMock(value="1000")
    p._pe_min_field = MagicMock(value="5")
    p._pe_max_field = MagicMock(value="50")
    p._change_pct_min_field = MagicMock(value="-5")
    p._change_pct_max_field = MagicMock(value="10")
    p._industry_field = MagicMock(value=" 银行 ")

    p.set_status = MagicMock()
    p.run_async = MagicMock()

    p._do_screener(None)

    p.set_status.assert_called_once()
    p.run_async.assert_called_once()
    # (coroutine_fn, *args) — second positional arg is the criteria dict
    criteria = p.run_async.call_args.args[1]
    assert criteria["market_cap_min"] == 100.0
    assert criteria["market_cap_max"] == 1000.0
    assert criteria["pe_min"] == 5.0
    assert criteria["pe_max"] == 50.0
    assert criteria["change_pct_min"] == -5.0
    assert criteria["change_pct_max"] == 10.0
    assert criteria["industry"] == "银行"  # stripped


def test_screener_ignores_garbage_in_number_fields():
    from gui.pages.screener import ScreenerPage
    p = _build_minimal_instance(ScreenerPage)
    p._service_client = MagicMock()
    p._market_cap_min_field = MagicMock(value="not-a-number")
    p._market_cap_max_field = MagicMock(value="")
    p._pe_min_field = MagicMock(value="abc")
    p._pe_max_field = MagicMock(value="")
    p._change_pct_min_field = MagicMock(value="")
    p._change_pct_max_field = MagicMock(value="")
    p._industry_field = MagicMock(value="")
    p.set_status = MagicMock()
    p.run_async = MagicMock()

    p._do_screener(None)

    criteria = p.run_async.call_args.args[1]
    assert criteria == {}


def test_financials_fetch_displays_table_on_success():
    """Happy path: status ok, data present, _display_table is called."""
    from gui.pages.financials import FinancialsPage
    p = _build_minimal_instance(FinancialsPage)
    p._client = MagicMock()
    p._client._send_request = MagicMock(return_value={
        "status": "ok", "data": {"items": [], "periods": []}
    })
    p._display_table = MagicMock()
    p.set_status = MagicMock()

    _run(p._fetch_financials("600519", "income"))

    p._display_table.assert_called_once()


def test_screener_completion_shows_count_in_status():
    from gui.pages.screener import ScreenerPage
    p = _build_minimal_instance(ScreenerPage)
    p._service_client = MagicMock()
    p._service_client.screen_stocks = AsyncMock(return_value={
        "status": "ok", "data": [{"code": "x"}] * 5, "count": 5
    })
    p._update_results = MagicMock()
    p.set_status = MagicMock()

    _run(p._run_screener_async({}))

    p._update_results.assert_called_once()
    msg = p.set_status.call_args.args[0]
    assert "5" in msg

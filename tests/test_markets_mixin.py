"""Tests for the AsyncTaskMixin integration in markets.py."""
import asyncio
import threading
import pytest
from unittest.mock import AsyncMock, MagicMock


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def patch_asyncio_sleep():
    """Return a context manager that makes asyncio.sleep a no-op."""
    from contextlib import contextmanager
    from unittest.mock import patch, AsyncMock

    @contextmanager
    def _cm():
        with patch("asyncio.sleep", new=AsyncMock()):
            yield
    return _cm()

def _build_instance():
    from gui.pages.markets import MarketsPage
    p = MarketsPage.__new__(MarketsPage)
    p._cancel_event = threading.Event()
    p._active_tasks = []
    p.app = MagicMock()
    p.app.page = MagicMock()
    p._client = MagicMock()
    p._previous_data = {}
    p._flash_indices = set()
    p._table_container = MagicMock()
    p._table_container.page = MagicMock()
    p.table = MagicMock()
    p.table.rows = []
    return p


def test_markets_page_class_inherits_mixin():
    from gui.pages.markets import MarketsPage
    from gui.components.async_task import AsyncTaskMixin
    assert issubclass(MarketsPage, AsyncTaskMixin)


def test_markets_instance_has_mixin_methods():
    p = _build_instance()
    for method in ("cancel", "check_cancelled", "is_cancelled",
                   "set_busy", "set_idle", "set_status", "run_async"):
        assert hasattr(p, method), f"MarketsPage missing {method}"


def test_markets_fetch_cancelled_before_call_returns_early():
    """If cancelled, we must NOT call the expensive client.get_markets."""
    p = _build_instance()
    p._cancel_event.set()  # pre-cancelled

    _run(p._fetch_and_update())

    p._client.get_markets.assert_not_called()


def test_markets_fetch_runs_normally_when_not_cancelled():
    p = _build_instance()
    p._client.get_markets = MagicMock(return_value=[
        {"code": "600519", "name": "Kweichow Moutai", "price": 1800.0,
         "change": 1.5, "volume": 1000000},
    ])
    p._load_data = MagicMock()
    p.app.update_status = MagicMock()
    p.update = MagicMock()

    _run(p._fetch_and_update())

    p._client.get_markets.assert_called_once()
    p._load_data.assert_called_once()
    p.app.update_status.assert_called_once()


def test_markets_flash_clear_cancelled_returns_early():
    p = _build_instance()
    p._cancel_event.set()
    p._table_container.update = MagicMock()

    _run(p._clear_flash_after_delay())

    # Flash should NOT be cleared (cancellation wins)
    assert p._flash_indices == set()
    p._table_container.update.assert_not_called()


def test_markets_flash_clear_normal_path_clears_indices():
    p = _build_instance()
    p._flash_indices = {1, 2, 3}  # start with some flashing rows

    # Patch asyncio.sleep to be instant
    with patch_asyncio_sleep():
        _run(p._clear_flash_after_delay())

    assert p._flash_indices == set()
    p._table_container.update.assert_called_once()


def test_markets_refresh_uses_mixin():
    """_refresh should call run_async (not raw page.run_task) for cancellation."""
    p = _build_instance()
    p.run_async = MagicMock()
    p._refresh(None)
    p.run_async.assert_called_once()
    # First arg is the coroutine
    assert p.run_async.call_args.args[0] == p._fetch_and_update


def test_markets_on_mount_uses_mixin():
    p = _build_instance()
    p.run_async = MagicMock()
    p.on_mount()
    p.run_async.assert_called_once()
    assert p.run_async.call_args.args[0] == p._fetch_and_update


def patch_asyncio_sleep():
    """Return a context manager that makes asyncio.sleep a no-op."""
    from contextlib import contextmanager
    from unittest.mock import patch, AsyncMock

    @contextmanager
    def _cm():
        with patch("asyncio.sleep", new=AsyncMock()):
            yield
    return _cm()

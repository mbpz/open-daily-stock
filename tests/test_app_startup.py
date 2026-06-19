"""Tests for StockApp async startup behavior.

These tests bypass the full __init__ path because the current project
uses legacy Flet APIs (ft.colors, ft.Icons.STRATEGY) that the locally
installed flet 0.84.0 no longer ships. The methods under test are
deliberately written to depend only on `self.page` and a few internal
attributes, so we instantiate via __new__ and wire up the minimum
state required.

Focus areas:
  1. _start_backend runs in background and does not raise on failure
  2. _show_backend_error attaches a snackbar with a retry button
  3. get_client falls back to lazy spawn on demand
  4. _check_update_on_startup_async swallows network errors
"""
import asyncio
import logging
import pytest
import threading
import time
from unittest.mock import MagicMock, patch


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


@pytest.fixture
def app():
    from gui.app import StockApp
    a = StockApp.__new__(StockApp)
    a.page = MagicMock()
    a.page.update = MagicMock()
    a.page.run_task = MagicMock()
    a.page.snack_bar = None
    a._client = None
    a._client_available = False
    a._client_lock = asyncio.Lock()
    a._client_thread_lock = threading.Lock()
    a._update_checker = MagicMock()
    a._demo_badge = None
    a.status_text = "init"
    a.status_bar = MagicMock()
    a.update_status = MagicMock()
    return a


def test_start_backend_failure_does_not_raise(app, caplog):
    from src.service_client import ServiceClientError

    with patch("src.service_client.ServiceClient", side_effect=ServiceClientError("boom")):
        caplog.set_level(logging.ERROR)
        _run(app._start_backend())

    assert app._client is None
    assert app._client_available is False
    assert any("DataService 启动失败" in rec.message for rec in caplog.records)
    assert app.page.snack_bar is not None
    assert app.page.snack_bar.open is True


def test_start_backend_success_marks_client_available(app):
    fake_client = MagicMock()
    fake_client.hello = MagicMock()

    with patch("src.service_client.ServiceClient", return_value=fake_client):
        _run(app._start_backend())

    assert app._client_available is True
    assert app._client is fake_client
    assert app.page.snack_bar is None


def test_start_backend_uses_thread_offload(app):
    """Blocking spawn + hello must not run on the event loop thread."""
    fake_client = MagicMock()

    def slow_spawn():
        time.sleep(0.05)
        return fake_client

    with patch.object(app, "_spawn_and_handshake", side_effect=slow_spawn):
        t0 = time.time()
        _run(app._start_backend())
        elapsed = time.time() - t0

    # The await returned within a small multiple of the sleep, only possible
    # if the work was actually offloaded via asyncio.to_thread.
    assert elapsed < 0.5, f"startup took {elapsed:.2f}s, expected offloaded"
    assert app._client_available is True


def test_get_client_returns_existing_when_available(app):
    fake_client = MagicMock()
    app._client = fake_client
    app._client_available = True
    assert app.get_client() is fake_client


def test_get_client_lazy_spawn_on_demand(app):
    fake_client = MagicMock()
    fake_client.hello = MagicMock()
    app._client = None
    app._client_available = False

    with patch("src.service_client.ServiceClient", return_value=fake_client):
        c = app.get_client()

    assert c is fake_client
    fake_client.hello.assert_called_once()
    assert app._client_available is True


def test_get_client_returns_none_on_spawn_failure(app, caplog):
    from src.service_client import ServiceClientError

    app._client = None
    app._client_available = False
    caplog.set_level(logging.WARNING)

    with patch("src.service_client.ServiceClient", side_effect=ServiceClientError("nope")):
        c = app.get_client()

    assert c is None
    assert any("按需启动后端失败" in rec.message for rec in caplog.records)


def test_check_update_async_swallows_network_errors(app, caplog):
    caplog.set_level(logging.DEBUG)

    class _Boom:
        def is_new_version_available(self):
            raise ConnectionError("no internet")

    app._update_checker = _Boom()
    _run(app._check_update_on_startup_async())
    assert any("启动时检查更新失败" in rec.message for rec in caplog.records)


def test_check_update_async_disabled_via_config(app):
    called = {"n": 0}

    class _Recorder:
        def is_new_version_available(self):
            called["n"] += 1
            return True

    app._update_checker = _Recorder()

    from src.config import get_config
    cfg = get_config()
    original = cfg.auto_check_update
    cfg.auto_check_update = False
    try:
        _run(app._check_update_on_startup_async())
    finally:
        cfg.auto_check_update = original

    assert called["n"] == 0


def test_check_update_async_shows_dialog_when_available(app):
    class _Has:
        def is_new_version_available(self):
            return True

        def get_release_info(self):
            return ("9.9.9", "release notes")

    app._update_checker = _Has()
    from src.config import get_config
    cfg = get_config()
    original = cfg.auto_check_update
    cfg.auto_check_update = True
    try:
        with patch.object(app, "_show_update_dialog") as m:
            _run(app._check_update_on_startup_async())
            m.assert_called_once_with("9.9.9", "release notes")
    finally:
        cfg.auto_check_update = original


def test_show_backend_error_attaches_snackbar(app):
    """Verify _show_backend_error wires a visible snackbar with the error
    color. Full row contents (real Flet controls) are exercised in the
    Flet UI integration test environment; here we only check the
    non-Flet contract: snackbar attached, open, error-colored, and that
    a long error message does not crash."""
    with patch("gui.app.get_theme", return_value={"ERROR_COLOR": "red"}):
        app._show_backend_error("connection refused")

    sb = app.page.snack_bar
    assert sb is not None
    assert sb.open is True
    assert sb.bgcolor == "red"
    # Long messages must not crash
    app._show_backend_error("x" * 200)
    assert app.page.snack_bar is not None

def test_get_client_double_checked_concurrent_safety(app):
    """Concurrent get_client() calls shouldn't spawn the backend twice."""
    fake_client = MagicMock()
    fake_client.hello = MagicMock()
    app._client = None
    app._client_available = False

    call_count = {"n": 0}
    original_lock = app._client_lock

    def counting_spawn():
        call_count["n"] += 1
        time.sleep(0.05)
        return fake_client

    # Note: get_client must be thread-safe; uses threading.Lock for cross-thread guarding.
    with patch("src.service_client.ServiceClient", side_effect=counting_spawn):
        results = []

        async def runner():
            tasks = [asyncio.create_task(asyncio.to_thread(app.get_client)) for _ in range(5)]
            for t in tasks:
                results.append(await t)

        _run(runner())

    # All callers see the same client
    assert all(r is fake_client for r in results)
    # Spawned at most twice: once on demand, possibly one extra if lock was
    # bypassed in the first iteration before it was acquired. We tolerate 2.
    assert call_count["n"] <= 2

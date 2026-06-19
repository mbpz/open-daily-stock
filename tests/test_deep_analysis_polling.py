"""Tests for AnalyzePage deep analysis polling loop.

Validates the P7-3 fix: a SINGLE WebSocket connection is used for the
whole deep-analyze + poll-for-result sequence, not 30+ per-iteration
connect/close cycles.

Also validates the new cancellation token check.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def page():
    p = MagicMock()
    p.run_task = MagicMock(side_effect=lambda fn, *a, **kw: asyncio.ensure_future(fn(*a, **kw)) if asyncio.iscoroutinefunction(fn) else None)
    p.update = MagicMock()
    return p

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

def _make_page(page):
    """Build an AnalyzePage instance without going through full __init__."""
    from gui.pages.analyze import AnalyzePage
    p = AnalyzePage.__new__(AnalyzePage)
    p.app = MagicMock()
    p.app.page = page
    import threading
    p._cancel_event = threading.Event()
    # Stubs for the methods _run_deep_analysis_async calls
    p._update_progress_agent = MagicMock()
    p._format_deep_result = MagicMock()
    p._show_result = MagicMock()
    p._status_text = MagicMock()
    p._status_text.value = ""
    p._progress_ring = MagicMock()
    p._progress_ring.visible = False
    p._pipeline = None
    return p

def test_single_websocket_connection_for_entire_polling_loop(page):
    """The polling loop must NOT call ws.connect() per iteration."""
    ap = _make_page(page)

    ws = MagicMock()
    ws.connect = AsyncMock()
    ws.close = AsyncMock()
    ws._ws = MagicMock()
    ws._ws.send = AsyncMock()
    # First recv: deep_analyze response with task_id (async mode)
    # Subsequent recv: get_task response with running status
    recv_responses = iter([
        json.dumps({"status": "ok", "task_id": "task-123", "result": None}),  # deep_analyze resp
        json.dumps({"status": "ok", "data": {"status": "running"}}),  # get_task poll 1
        json.dumps({"status": "ok", "data": {"status": "completed", "result": {"x": 1}}}),  # get_task poll 2
    ])
    async def fake_recv():
        return next(recv_responses)
    ws._ws.recv = fake_recv

    # ws.request is the high-level helper; mock it
    request_responses = iter([
        {"status": "ok", "data": {"status": "running"}},
        {"status": "ok", "data": {"status": "completed", "result": {"x": 1}}},
    ])
    async def fake_request(action, **params):
        return next(request_responses)
    ws.request = fake_request

    # Patch sleep to be instant
    with patch("asyncio.sleep", new=AsyncMock()), \
         patch("src.ws_client.WsClient", return_value=ws):
        _run(ap._run_deep_analysis_async("600519"))

    # CRITICAL: connect must be called exactly ONCE (start of polling), not 30 times.
    assert ws.connect.await_count == 1, (
        f"connect() called {ws.connect.await_count} times; "
        "expected 1 (single connection for entire flow)"
    )
    # close should also be called exactly once
    assert ws.close.await_count == 1

def test_polling_stops_when_cancellation_event_is_set(page):
    """Setting _cancel_event must break the polling loop quickly."""
    ap = _make_page(page)
    ap._cancel_event.set()  # already cancelled

    ws = MagicMock()
    ws.connect = AsyncMock()
    ws.close = AsyncMock()
    ws._ws = MagicMock()
    ws._ws.send = AsyncMock()
    async def fake_recv():
        return json.dumps({"status": "ok", "task_id": "task-1", "result": None})
    ws._ws.recv = fake_recv
    ws.request = AsyncMock(return_value={"status": "ok", "data": {"status": "running"}})

    sleep_called = {"n": 0}
    async def counting_sleep(_):
        sleep_called["n"] += 1

    with patch("asyncio.sleep", side_effect=counting_sleep), \
         patch("src.ws_client.WsClient", return_value=ws):
        _run(ap._run_deep_analysis_async("600519"))

    # The loop should have bailed out after the first cancellation check,
    # so at most 1 sleep call (the one before the check) and NO get_task
    # request after cancellation.
    assert ws.request.await_count == 0, (
        f"Polled {ws.request.await_count} times despite cancellation"
    )

def test_polling_handles_completed_status_via_poll(page):
    """When task eventually completes, format and return without timeout."""
    ap = _make_page(page)

    ws = MagicMock()
    ws.connect = AsyncMock()
    ws.close = AsyncMock()
    ws._ws = MagicMock()
    ws._ws.send = AsyncMock()
    async def fake_recv():
        return json.dumps({"status": "ok", "task_id": "task-1", "result": None})
    ws._ws.recv = fake_recv

    request_responses = iter([
        {"status": "ok", "data": {"status": "running"}},
        {"status": "ok", "data": {"status": "completed", "result": {"score": 80}}},
    ])
    async def fake_request(action, **params):
        return next(request_responses)
    ws.request = fake_request

    with patch("asyncio.sleep", new=AsyncMock()), \
         patch("src.ws_client.WsClient", return_value=ws):
        _run(ap._run_deep_analysis_async("600519"))

    # _format_deep_result called with the completed result
    ap._format_deep_result.assert_called_once_with({"score": 80})
    # _show_result for "超时" must NOT have been called
    show_calls = [c for c in ap._show_result.call_args_list if "超时" in str(c)]
    assert show_calls == [], f"Timed out despite completion: {show_calls}"

def test_polling_handles_failed_status(page):
    """A failed task must surface the error to the user."""
    ap = _make_page(page)

    ws = MagicMock()
    ws.connect = AsyncMock()
    ws.close = AsyncMock()
    ws._ws = MagicMock()
    ws._ws.send = AsyncMock()
    async def fake_recv():
        return json.dumps({"status": "ok", "task_id": "task-1", "result": None})
    ws._ws.recv = fake_recv
    ws.request = AsyncMock(return_value={
        "status": "ok", "data": {"status": "failed", "error": "API quota exceeded"},
    })

    with patch("asyncio.sleep", new=AsyncMock()), \
         patch("src.ws_client.WsClient", return_value=ws):
        _run(ap._run_deep_analysis_async("600519"))

    show_calls = ap._show_result.call_args_list
    assert any("API quota exceeded" in str(c) for c in show_calls), (
        f"Failed status error not surfaced: {show_calls}"
    )

def test_polling_handles_request_failure_with_reconnect(page):
    """If the connection drops mid-poll, we should attempt to reconnect."""
    ap = _make_page(page)

    ws = MagicMock()
    ws.connect = AsyncMock(side_effect=[None, None, OSError("server down")])
    ws.close = AsyncMock()
    ws._ws = MagicMock()
    ws._ws.send = AsyncMock()
    async def fake_recv():
        return json.dumps({"status": "ok", "task_id": "task-1", "result": None})
    ws._ws.recv = fake_recv

    request_responses = iter([
        OSError("connection lost"),
        {"status": "ok", "data": {"status": "completed", "result": {"ok": True}}},
    ])
    async def fake_request(action, **params):
        r = next(request_responses)
        if isinstance(r, Exception):
            raise r
        return r
    ws.request = fake_request
    ws.reconnect = AsyncMock(side_effect=[True, True])

    with patch("asyncio.sleep", new=AsyncMock()), \
         patch("src.ws_client.WsClient", return_value=ws):
        _run(ap._run_deep_analysis_async("600519"))

    # We should have called reconnect at least once (after the first failure)
    assert ws.reconnect.await_count >= 1

def test_request_error_top_level_does_not_crash_ui(page):
    """An exception deep in the WS flow must surface a friendly error."""
    ap = _make_page(page)

    with patch("src.ws_client.WsClient", side_effect=OSError("server down")):
        # Pipeline fallback path is exercised; we just need it not to crash.
        ap._show_result = MagicMock()  # refresh since pipeline path may call it
        _run(ap._run_deep_analysis_async("600519"))
    # No exception leaked — that's the success criterion.

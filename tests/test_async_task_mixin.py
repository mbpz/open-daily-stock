"""Tests for AsyncTaskMixin — shared helper for GUI pages."""
import asyncio
import threading
import time
import pytest
from unittest.mock import MagicMock

from gui.components.async_task import AsyncTaskMixin


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


class _Page(AsyncTaskMixin):
    """Minimal subclass for testing."""
    def __init__(self):
        self.app = MagicMock()
        self.app.page = MagicMock()
        self._progress_ring = MagicMock()
        self._progress_ring.visible = False
        self._status_text = MagicMock()
        self._status_text.value = ""
        self._status_text.visible = False
        self._show_result = MagicMock()
        AsyncTaskMixin.__init__(self, self.app)


def test_initial_state_not_cancelled():
    p = _Page()
    assert p.is_cancelled() is False
    assert p.check_cancelled() is False
    assert p._cancel_event.is_set() is False


def test_cancel_signals_event():
    p = _Page()
    p.cancel()
    assert p.is_cancelled() is True
    assert p._cancel_event.is_set() is True


def test_reset_cancellation_allows_reuse():
    p = _Page()
    p.cancel()
    p.reset_cancellation()
    assert p.is_cancelled() is False


def test_set_busy_makes_progress_ring_visible():
    p = _Page()
    p.set_busy()
    assert p._progress_ring.visible is True
    assert p._progress_ring.update.called


def test_set_idle_hides_progress_ring():
    p = _Page()
    p.set_busy()
    p.set_idle()
    assert p._progress_ring.visible is False


def test_set_status_updates_text():
    p = _Page()
    p.set_status("Loading...")
    assert p._status_text.value == "Loading..."
    assert p._status_text.visible is True


def test_set_status_empty_hides_text():
    p = _Page()
    p.set_status("first")
    p.set_status("")
    assert p._status_text.visible is False


def test_show_error_calls_show_result_with_error():
    p = _Page()
    p.show_error("connection refused")
    p._show_result.assert_called_once_with("connection refused", is_error=True)


def test_show_result_calls_show_result_without_error():
    p = _Page()
    p.show_result({"score": 80})
    p._show_result.assert_called_once_with({"score": 80}, is_error=False)


def test_show_error_falls_back_to_logging_when_no_result_area(caplog):
    class _NoResultPage(AsyncTaskMixin):
        def __init__(self):
            self.app = MagicMock()
            self.app.page = MagicMock()
            AsyncTaskMixin.__init__(self, self.app)
            # No _show_result attribute
    import logging
    p = _NoResultPage()
    with caplog.at_level(logging.WARNING):
        p.show_error("test fallback")
    assert any("test fallback" in rec.message for rec in caplog.records)


def test_check_cancelled_breaks_long_loop():
    """Simulates a polling loop that exits on cancel."""
    p = _Page()

    async def poll_loop():
        iterations = 0
        while not p.check_cancelled():
            await asyncio.sleep(0.01)
            iterations += 1
            if iterations >= 3:
                p.cancel()  # cancel after 3 iterations
        return iterations

    n = _run(poll_loop())
    assert n == 3  # exited after exactly 3 iterations, not the full loop


def test_run_async_launches_coroutine():
    """run_async should call page.run_task and (best-effort) track the task."""
    p = _Page()

    async def quick_coro():
        return "done"

    task = p.run_async(quick_coro)
    # The exact behaviour depends on Flet internals; we just need
    # page.run_task to have been invoked.
    assert p.app.page.run_task.called
    # And the cancellation token was re-armed.
    assert p.is_cancelled() is False


def test_run_async_resets_previous_cancellation():
    p = _Page()
    p.cancel()
    assert p.is_cancelled() is True
    async def noop():
        return None
    p.run_async(noop)
    assert p.is_cancelled() is False  # re-armed for the new run


def test_no_progress_ring_tolerated():
    """Pages without _progress_ring should not crash set_busy/set_idle."""
    class _BarePage(AsyncTaskMixin):
        def __init__(self):
            self.app = MagicMock()
            self.app.page = MagicMock()
            AsyncTaskMixin.__init__(self, self.app)
    p = _BarePage()
    p.set_busy()  # must not raise
    p.set_idle()  # must not raise
    p.set_status("ok")  # must not raise


def test_task_done_callback_restores_idle():
    """When a tracked task finishes, set_idle is called automatically."""
    p = _Page()
    p.set_busy()

    async def quick():
        return "x"

    # Manually simulate the bookkeeping that run_async would do
    # when an event loop is available.
    loop = asyncio.new_event_loop()
    try:
        task = loop.create_task(quick())
        p._active_tasks.append(task)
        task.add_done_callback(p._on_task_done)
        loop.run_until_complete(task)
    finally:
        loop.close()

    # The done callback should have flipped the ring back to idle
    assert p._progress_ring.visible is False

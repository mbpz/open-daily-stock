"""AsyncTaskMixin — shared helpers for GUI pages that run background work.

Every Flet page in this app follows the same pattern:
  - show a progress indicator
  - kick off a coroutine via ``app.page.run_task``
  - poll a cancellation event so closing the window stops the work
  - hide the indicator and show an error or result when done

This mixin centralises the boilerplate so individual pages only need to
implement ``_run_*_async`` methods that periodically call
``self.check_cancelled()`` and use ``self.show_error(...)`` /
``self.show_result(...)`` for terminal states.

Usage:
    from gui.components.async_task import AsyncTaskMixin

    class AnalyzePage(AsyncTaskMixin, ft.Container):
        def __init__(self, app, ...):
            AsyncTaskMixin.__init__(self, app)
            # ... page-specific UI setup ...

        def _start(self):
            self.run_async(self._run_deep_analysis_async, code)

        async def _run_deep_analysis_async(self, code):
            while not self.check_cancelled():
                await asyncio.sleep(1)
                try:
                    result = await self.fetch_remote(code)
                except Exception as e:
                    self.show_error(f"fetch failed: {e}")
                    return
                if result.ready:
                    self.show_result(result.payload)
                    return
"""
from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any, Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class AsyncTaskMixin:
    """Provides cancellation, progress, and result helpers for Flet pages.

    Subclasses are expected to have these attributes (set in __init__):
      - self.app            — the StockApp instance
      - self._progress_ring — optional ft.ProgressRing (None = no spinner)
      - self._result_area   — optional ft.Container for showing results
      - self._status_text   — optional ft.Text for status messages

    Missing attributes are tolerated: the helper methods check with
    ``getattr(self, name, None)`` and become no-ops if absent.
    """

    def __init__(self, app: Any) -> None:
        self.app = app
        # Cancellation token shared across all background tasks launched
        # by this page. Pages that do not use this mixin can be subclassed
        # safely because the attribute only exists on subclasses.
        self._cancel_event: threading.Event = threading.Event()
        # Track active tasks so unmount can wait for or cancel them.
        self._active_tasks: list[asyncio.Task] = []

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    def cancel(self) -> None:
        """Signal all background tasks on this page to stop.

        Safe to call multiple times. The page is not re-armed; use
        ``reset_cancellation()`` if you need to launch another task
        after cancelling.
        """
        self._cancel_event.set()
        # Best-effort cancel of in-flight asyncio tasks too.
        for task in list(self._active_tasks):
            if not task.done():
                task.cancel()

    def reset_cancellation(self) -> None:
        """Re-arm the cancellation token for a new task."""
        self._cancel_event = threading.Event()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def check_cancelled(self) -> bool:
        """Return True if cancellation has been requested.

        Use in long-running loops:
            while not self.check_cancelled():
                ...
        """
        return self._cancel_event.is_set()

    # ------------------------------------------------------------------
    # Task launch
    # ------------------------------------------------------------------

    def run_async(
        self,
        coro_fn: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Optional[asyncio.Task]:
        """Launch a coroutine in the Flet event loop, tracked for cleanup.

        Returns the asyncio.Task, or None if no event loop is running yet.
        Re-arms the cancellation token so a re-run after a previous
        cancel works correctly.
        """
        self.reset_cancellation()
        self.set_busy()
        try:
            page = getattr(self.app, "page", None)
            if page is None or not hasattr(page, "run_task"):
                logger.warning("AsyncTaskMixin.run_async called without page")
                return None
            # Flet's run_task takes (coroutine_fn, *args) — wraps it for us.
            page.run_task(coro_fn, *args, **kwargs)
            # We can't easily access the asyncio.Task Flet created, but
            # for explicit cleanup, we ALSO schedule our own task below.
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    task = loop.create_task(coro_fn(*args, **kwargs))
                    self._active_tasks.append(task)
                    task.add_done_callback(self._on_task_done)
                    return task
            except RuntimeError:
                # No event loop in this thread (test harness). Skip.
                pass
            return None
        except Exception as e:
            logger.exception(f"run_async failed: {e}")
            self.set_idle()
            return None

    def _on_task_done(self, task: asyncio.Task) -> None:
        """Called when a tracked task completes (success or cancel)."""
        if task in self._active_tasks:
            self._active_tasks.remove(task)
        # Don't swallow CancelledError — that's the whole point.
        if task.cancelled():
            logger.debug("AsyncTaskMixin: task cancelled")
            return
        exc = task.exception()
        if exc is not None and not isinstance(exc, asyncio.CancelledError):
            logger.exception(f"AsyncTaskMixin: task raised {exc}")
            # Surface to UI if possible
            self.show_error(str(exc))
        # Always restore the idle state in case the task forgot.
        self.set_idle()

    # ------------------------------------------------------------------
    # Progress + result UI helpers
    # ------------------------------------------------------------------

    def set_busy(self) -> None:
        """Show the progress ring + status text, if present."""
        ring = getattr(self, "_progress_ring", None)
        if ring is not None:
            ring.visible = True
            try:
                ring.update()
            except Exception:
                pass

    def set_idle(self) -> None:
        """Hide the progress ring + status text, if present."""
        ring = getattr(self, "_progress_ring", None)
        if ring is not None:
            ring.visible = False
            try:
                ring.update()
            except Exception:
                pass

    def set_status(self, text: str) -> None:
        """Update the status text (if the page has one)."""
        status = getattr(self, "_status_text", None)
        if status is not None:
            status.value = text
            status.visible = bool(text)
            try:
                status.update()
            except Exception:
                pass

    def show_error(self, message: str) -> None:
        """Display an error message in the result area, if present.

        Falls back to logging if the page has no result area.
        """
        if hasattr(self, "_show_result") and callable(getattr(self, "_show_result")):
            try:
                self._show_result(message, is_error=True)
                return
            except Exception:
                pass
        logger.warning(f"[{type(self).__name__}] {message}")

    def show_result(self, content: Any) -> None:
        """Display a successful result in the result area, if present."""
        if hasattr(self, "_show_result") and callable(getattr(self, "_show_result")):
            try:
                self._show_result(content, is_error=False)
                return
            except Exception:
                pass
        logger.info(f"[{type(self).__name__}] result: {content}")


__all__ = ["AsyncTaskMixin"]

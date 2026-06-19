# ADR-007: AsyncTaskMixin for Flet Pages

Status: **Accepted** (P7-3)

## Context

Every Flet page in this app follows the same pattern when running
background work:

1. Show a progress indicator
2. Kick off a coroutine via ``app.page.run_task(coro, *args)``
3. Poll a ``threading.Event`` cancellation token so closing the window
   stops the work
4. Hide the indicator and show an error or result when done
5. Clean up any per-task state (e.g. the `ws` connection in analyze.py)

Before the mixin, this pattern was duplicated in every page that
launches work:

- `gui/pages/analyze.py` — 818 lines with 3 different `_start_*` paths
  and a 30-iteration WebSocket poll loop that needed its own
  cancellation
- `gui/pages/markets.py` — a flash-effect timer launched as a raw
  `page.run_task` without cancellation
- `gui/pages/financials.py` — duplicated 6-line status block per
  query path
- `gui/pages/screener.py` — 9 lines of manual `self._status_text.value = ...; .color = ...; .update()` per status change

The result was 4× duplication of the same boilerplate, plus 4 places
where GUI close did NOT actually cancel in-flight work (most painful
in analyze.py's 90-second LLM round-trip).

## Decision

Introduce `gui.components.async_task.AsyncTaskMixin` with a small,
focussed API:

- **Cancellation**: `self._cancel_event` (a `threading.Event`),
  `cancel()`, `is_cancelled()`, `check_cancelled()`, `reset_cancellation()`
- **Task launch**: `run_async(coro_fn, *args, **kwargs)` wraps
  `page.run_task` and re-arms the cancellation token
- **UI helpers**: `set_busy()` / `set_idle()` for the progress ring,
  `set_status(text)` for the status text, `show_error(msg)` /
  `show_result(content)` for terminal state
- **Task bookkeeping**: `_on_task_done` callback restores idle state
  and surfaces uncaught exceptions to the user

All helpers tolerate missing attributes (no `_progress_ring` or no
`_show_result` is fine — they become no-ops or fall back to logging).
This makes the mixin safe to drop into a partially-built page.

### Usage

```python
from gui.components.async_task import AsyncTaskMixin

class MyPage(AsyncTaskMixin, ft.Container):
    def __init__(self, app, ...):
        # Order matters: Container first, then mixin (mixin needs `app`).
        ft.Container.__init__(self)
        AsyncTaskMixin.__init__(self, app)
        # ... page-specific UI setup ...

    def _start(self):
        # Old: self.app.page.run_task(self._work_async, code)
        # New: cancel-aware, auto-busy-state
        self.run_async(self._work_async, code)

    async def _work_async(self, code):
        while not self.check_cancelled():
            await asyncio.sleep(1)
            result = await self.fetch(code)
            if result.ready:
                self.show_result(result.payload)
                return
```

### Initial adoption

The mixin has been applied to:
- `gui/pages/analyze.py` (P7-3)
- `gui/pages/financials.py`
- `gui/pages/screener.py`
- `gui/pages/markets.py`

Remaining pages (`chart.py`, `kline.py`, `tasks.py`, `notifications.py`,
`config.py`, `strategies.py`, `logs.py`) do not launch background
tasks and so do not need the mixin.

## Consequences

**Positive**
- 4× duplicated cancellation/status code paths removed (~120 LOC)
- GUI close now reliably cancels in-flight work (analyze.py
  WebSocket poll, markets.py flash timer, financials.py query,
  screener.py filter)
- New pages can adopt cancellation for free by inheriting the mixin
- The mixin is testable in isolation (15 unit tests in
  `tests/test_async_task_mixin.py`)

**Negative / Trade-offs**
- MRO requires `class FooPage(AsyncTaskMixin, ft.Container)` and
  explicit `ft.Container.__init__(self); AsyncTaskMixin.__init__(self, app)`
  in the page's `__init__` (Python's `super()` would also work but is
  more fragile to Flet metaclass changes)
- The `run_async` helper does best-effort task tracking (it depends
  on `asyncio.get_event_loop()` which may be unavailable in test
  contexts). Pages that need strict task tracking can call
  `page.run_task` directly
- Cancellation is **co-operative**: a coroutine that doesn't call
  `self.check_cancelled()` or yield to the event loop cannot be
  cancelled. This is documented in the mixin's docstring

## Future work

- If Flet adopts a more idiomatic async API (e.g. native
  `page.run_async` that returns a Task), revisit to drop the manual
  loop detection
- Consider adding `self.on_unmount()` hook in the mixin so pages
  don't need to remember to call `self.cancel()` from the app's
  `_load_page` swap

# ADR-006: Notification Module Migration (P7-5)

Status: **In progress** (P7-4 completed; P7-5 scheduled)

## Context

`src/notification.py` grew to 3128 lines as a single monolith containing:

- A `NotificationChannel` enum (10 values)
- A `BotMessage` dataclass
- A `NotificationService` class with 14+ methods, each implementing
  one channel's send logic (wechat / feishu / telegram / email / pushover /
  pushplus / custom / discord / windows) + report generators +
  dispatching logic

Issues:

- Single class couples 9 channel implementations; one channel's
  breakage (e.g. flaky SMTP) can mask problems in others
- No per-channel unit tests were practical; everything shared state
- ~10 duplicated retry/chunking patterns
- No type hints on most methods
- `try/except: pass` patterns silently swallowed errors

## Decision

Phased migration (this PR = P7-4; P7-5 = future):

1. ✅ Extract lightweight types (`NotificationChannel`, `BotMessage`)
   into `src/notify/_legacy.py`
2. ✅ Extract channel implementations into `src/notify/channels/*.py`
   with byte-safe chunking (`_chunking.py`), tenacity-based retries,
   and per-channel unit tests
3. ✅ Add `NotificationDispatcher` for multi-channel fan-out
4. ✅ Add `MarkdownFormatter` / `SimpleFormatter` / `DashboardFormatter`
5. ✅ `src/notify/__init__.py` re-exports the modern API; importing
   lightweight types from `src.notification` no longer triggers a
   deprecation warning
6. ✅ `src.notification` retains the 3000-line `NotificationService`
   class as a backwards-compat shim, but every access to
   `NotificationService` emits a `DeprecationWarning`
7. ⏳ P7-5: Re-implement `NotificationService` as a thin facade over
   `NotificationDispatcher` + formatters, then delete the monolith
   entirely. Tracked separately because the API surface is large
   (14 methods) and the existing tests in `tests/test_notification.py`
   verify exact byte-level behavior we don't want to break.

## Consequences

**Positive**
- New code uses `from src.notify import NotificationDispatcher` —
  clean module boundary, per-channel testing
- Existing callers (`src/core/pipeline.py`, `src/core/market_review.py`,
  `src/data_service.py`, `tests/test_notification.py`,
  `tests/test_pipeline.py`) continue to work
- Deprecation warnings on `NotificationService` access surface the
  migration debt to any future code reader

**Negative / Risks**
- Until P7-5 lands, `src.notification` still exists; we have not
  actually deleted the dead code yet
- The `__getattr__` proxy adds a tiny runtime cost (one warning
  emit per process per first-access) for legacy users
- The monolith's tests in `tests/test_notification.py` remain
  coupled to the legacy implementation, slowing future migration

## Migration cheat-sheet

```python
# OLD (works, emits DeprecationWarning on first use)
from src.notification import NotificationService
svc = NotificationService()
svc.send_to_wechat(content)

# NEW (preferred, no warning)
from src.notify import NotificationDispatcher, MarkdownFormatter
dispatcher = NotificationDispatcher(config)
formatter = MarkdownFormatter()
results = dispatcher.send(formatter.format_multiple_results(results))
```

See `tests/test_notify/` for examples of the new API.

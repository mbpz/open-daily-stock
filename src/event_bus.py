"""P7-3: Lightweight EventBus for in-process pub/sub communication.

Provides decoupled, priority-ordered, async-safe event routing
between modules. Replaces hardcoded direct handler calls with
subscribe/publish patterns.

Usage:
    bus = EventBus()
    bus.subscribe("analysis.completed", my_handler, priority=30)
    bus.publish("analysis.completed", {"code": "600519", "score": 75})

Standard events are defined as constants in StandardEvents.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

# Handler signature: (event_name: str, data: Any) -> None
EventHandler = Callable[[str, Any], None]

DEFAULT_PRIORITY = 50
MAX_WORKERS = 4  # For async publishing


@dataclass(order=True)
class _Subscription:
    """Internal subscription entry, ordered by priority (lower = higher priority)."""
    priority: int
    handler: EventHandler = field(compare=False)
    subscriber_id: str = field(compare=False)


class StandardEvents:
    """Standard event types used across open-daily-stock."""

    MARKET_REFRESHED = "market.refreshed"
    ANALYSIS_COMPLETED = "analysis.completed"
    ANALYSIS_STREAM_DONE = "analysis.stream_done"
    ALERT_TRIGGERED = "alert.triggered"
    MARKET_REVIEW_READY = "market.review.ready"
    BACKTEST_COMPLETED = "backtest.completed"
    BOT_COMMAND_RECEIVED = "bot.command.received"
    SYSTEM_SHUTDOWN = "system.shutdown"
    CONFIG_CHANGED = "config.changed"


class EventBus:
    """In-process publish/subscribe event bus.

    Features:
    - Priority-based handler execution (lower number = higher priority)
    - Synchronous and asynchronous publish modes
    - Exception isolation: one handler failing doesn't affect others
    - Thread-safe: safe for use across daemon threads
    - Singleton pattern via get_event_bus()

    Thread safety:
    - subscribe/unsubscribe are protected by a reentrant lock
    - publish iterates over a snapshot of subscribers for a given event
    """

    _instance: Optional["EventBus"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Drop the singleton and clear all subscriptions.

        Intended for test isolation between pytest tests. Calling this in
        production code is almost always wrong — it will detach any
        handlers other modules installed at import time.
        """
        if cls._instance is not None:
            try:
                cls._instance.unsubscribe_all()
            except Exception:
                pass
            try:
                # Don't wait forever on stuck executor workers.
                cls._instance._executor.shutdown(wait=False)
            except Exception:
                pass
            cls._instance = None

    def __init__(self):
        if self._initialized:
            return
        self._subscriptions: Dict[str, List[_Subscription]] = defaultdict(list)
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=MAX_WORKERS, thread_name_prefix="eventbus")
        self._subscriber_counter = 0
        self._initialized = True
        logger.info("EventBus initialized")

    # ------------------------------------------------------------------
    # Subscribe / Unsubscribe
    # ------------------------------------------------------------------

    def subscribe(
        self,
        event_type: str,
        handler: EventHandler,
        priority: int = DEFAULT_PRIORITY,
    ) -> str:
        """Subscribe to an event type.

        Args:
            event_type: Event name (use StandardEvents constants).
            handler: Callback function(event_name, data).
            priority: Lower number = higher priority (default 50).

        Returns:
            subscriber_id string for later unsubscribe.
        """
        with self._lock:
            self._subscriber_counter += 1
            sub_id = f"sub_{self._subscriber_counter}"
            sub = _Subscription(priority=priority, handler=handler, subscriber_id=sub_id)
            self._subscriptions[event_type].append(sub)
            self._subscriptions[event_type].sort()  # Keep sorted by priority
            logger.debug(f"Subscribed to '{event_type}' (id={sub_id}, priority={priority})")
            return sub_id

    def unsubscribe(self, subscriber_id: str) -> bool:
        """Remove a subscription by its ID.

        Returns True if found and removed.
        """
        with self._lock:
            for event_type, subs in list(self._subscriptions.items()):
                for sub in list(subs):
                    if sub.subscriber_id == subscriber_id:
                        subs.remove(sub)
                        if not subs:
                            del self._subscriptions[event_type]
                        logger.debug(f"Unsubscribed '{subscriber_id}' from '{event_type}'")
                        return True
        return False

    def unsubscribe_all(self, event_type: Optional[str] = None) -> int:
        """Remove all subscriptions, optionally filtered by event type.

        Returns count of removed subscriptions.
        """
        count = 0
        with self._lock:
            if event_type:
                count = len(self._subscriptions.get(event_type, []))
                self._subscriptions.pop(event_type, None)
            else:
                count = sum(len(subs) for subs in self._subscriptions.values())
                self._subscriptions.clear()
        logger.info(f"Unsubscribed {count} handlers")
        return count

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------

    def publish(self, event_type: str, data: Any = None) -> int:
        """Publish an event synchronously (blocks until all handlers complete).

        Handlers are called in priority order. Exceptions in one handler
        do not prevent other handlers from running.

        Returns:
            Number of handlers that were called.
        """
        with self._lock:
            subs = list(self._subscriptions.get(event_type, []))

        if not subs:
            return 0

        called = 0
        for sub in subs:
            called += 1  # counted as dispatched even if it raises
            try:
                sub.handler(event_type, data)
            except Exception as e:
                logger.error(
                    f"EventBus handler error for '{event_type}' "
                    f"(id={sub.subscriber_id}): {e}",
                    exc_info=True,
                )
        return called

    def publish_async(self, event_type: str, data: Any = None) -> int:
        """Publish an event asynchronously (non-blocking, via thread pool).

        Handlers run in background threads. Does not wait for completion.

        Returns:
            Number of handlers dispatched.
        """
        with self._lock:
            subs = list(self._subscriptions.get(event_type, []))

        if not subs:
            return 0

        for sub in subs:
            self._executor.submit(self._safe_call, sub.handler, event_type, data)

        return len(subs)

    def _safe_call(self, handler: EventHandler, event_type: str, data: Any) -> None:
        """Wrapper to catch exceptions in async handlers."""
        try:
            handler(event_type, data)
        except Exception as e:
            logger.error(
                f"EventBus async handler error for '{event_type}': {e}",
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def list_subscriptions(self) -> Dict[str, int]:
        """Return {event_type: subscriber_count}."""
        with self._lock:
            return {k: len(v) for k, v in self._subscriptions.items()}

    def has_subscribers(self, event_type: str) -> bool:
        with self._lock:
            return event_type in self._subscriptions and len(self._subscriptions[event_type]) > 0

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def shutdown(self) -> None:
        """Shut down the async executor and clear all subscriptions."""
        self.unsubscribe_all()
        self._executor.shutdown(wait=True)
        logger.info("EventBus shut down")


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------

def get_event_bus() -> EventBus:
    """Return the singleton EventBus instance."""
    return EventBus()

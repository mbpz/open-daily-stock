"""Tests for EventBus — focus on singleton reset for test isolation."""
import pytest

from src.event_bus import EventBus, StandardEvents, get_event_bus


@pytest.fixture(autouse=True)
def _isolated_bus():
    """Each test gets a fresh EventBus singleton."""
    EventBus.reset_instance()
    yield
    EventBus.reset_instance()


def test_singleton_returns_same_instance():
    a = get_event_bus()
    b = get_event_bus()
    assert a is b


def test_reset_instance_returns_new_singleton():
    a = get_event_bus()
    a.subscribe("x", lambda *_: None)
    assert a.list_subscriptions() == {"x": 1}

    EventBus.reset_instance()
    b = get_event_bus()
    assert a is not b
    assert b.list_subscriptions() == {}


def test_reset_clears_subscriptions_but_keeps_priority_order():
    bus = get_event_bus()
    order = []

    bus.subscribe(StandardEvents.ANALYSIS_COMPLETED, lambda *_: order.append("a"), priority=10)
    bus.subscribe(StandardEvents.ANALYSIS_COMPLETED, lambda *_: order.append("b"), priority=20)
    bus.subscribe(StandardEvents.ANALYSIS_COMPLETED, lambda *_: order.append("c"), priority=5)

    bus.publish(StandardEvents.ANALYSIS_COMPLETED, {})
    assert order == ["c", "a", "b"]  # priority 5, 10, 20

    # Reset and verify empty
    EventBus.reset_instance()
    bus2 = get_event_bus()
    assert bus2.publish(StandardEvents.ANALYSIS_COMPLETED, {}) == 0


def test_reset_does_not_raise_on_already_clean_state():
    EventBus.reset_instance()
    EventBus.reset_instance()  # second time should be no-op
    bus = get_event_bus()
    assert bus is not None


def test_publish_continues_after_handler_error():
    bus = get_event_bus()
    seen = []

    def boom(*_):
        raise RuntimeError("handler boom")

    bus.subscribe("e", boom)
    bus.subscribe("e", lambda *_: seen.append("ok"))

    called = bus.publish("e", None)
    # Both handlers were called; exception in one doesn't block the other.
    assert called == 2
    assert seen == ["ok"]


def test_publish_async_dispatches_via_executor():
    import threading
    bus = get_event_bus()
    seen = []
    ev = threading.Event()

    def slow_handler(*_):
        ev.set()
        seen.append(threading.current_thread().name)

    bus.subscribe("async_test", slow_handler)
    bus.publish_async("async_test", None)
    assert ev.wait(timeout=2.0), "async handler did not fire"
    assert "eventbus" in seen[0]

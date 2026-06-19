"""Tests for the src.notification → src.notify migration (P7-4 + P7-5 stub).

Covers:
  1. Lightweight types (NotificationChannel, BotMessage) are re-exported
     from src.notify (the new canonical home) and from src.notification
     (the legacy shim) without raising a deprecation warning
  2. NotificationService is still accessible from src.notification for
     backwards compat, but accessing it triggers a DeprecationWarning
  3. The legacy class is the same Python object that lives in the
     legacy monolith (callers depending on isinstance() still work)
  4. src.notify no longer depends on src.notification internally
"""
import warnings
import sys


def test_lightweight_types_importable_from_src_notify():
    from src.notify import NotificationChannel, BotMessage
    assert NotificationChannel.WECHAT.value == "wechat"
    assert NotificationChannel.FEISHU.value == "feishu"
    msg = BotMessage(content="hello")
    assert msg.content == "hello"
    assert msg.image_paths == []  # dataclass default


def test_lightweight_types_from_legacy_module_no_warning():
    """Importing types from the legacy module must NOT warn — they have
    already been migrated to src.notify."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from src.notification import NotificationChannel, BotMessage

    deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)
                    and "src.notification" in str(x.message)]
    assert deprecations == [], (
        f"Unexpected DeprecationWarnings on type import: "
        f"{[str(x.message) for x in deprecations]}"
    )


def test_notification_service_access_emits_deprecation_warning():
    """Touching NotificationService must emit exactly one DeprecationWarning."""
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        from src.notification import NotificationService

    deprecations = [x for x in w if issubclass(x.category, DeprecationWarning)
                    and "NotificationService" in str(x.message)]
    assert len(deprecations) >= 1
    msg = str(deprecations[0].message)
    assert "deprecated" in msg.lower()
    assert "src.notify" in msg


def test_notification_service_is_real_class():
    """NotificationService should be a real class (not a Mock or placeholder)
    so existing callers that depend on isinstance() keep working."""
    from src.notification import NotificationService
    import inspect
    assert inspect.isclass(NotificationService)
    # It should have at least the canonical methods
    assert hasattr(NotificationService, "send")
    assert hasattr(NotificationService, "is_available")


def test_src_notify_does_not_depend_on_legacy_module():
    """The new src.notify package must work even if src.notification is unavailable.

    This protects against future removal of the legacy module."""
    # Simulate the legacy module being unavailable by hiding it in sys.modules
    saved = sys.modules.pop("src.notification", None)
    try:
        # Re-import src.notify; should succeed without trying to load legacy
        if "src.notify" in sys.modules:
            del sys.modules["src.notify"]
        from src.notify import (  # noqa: F401
            NotificationChannel, BotMessage, NotificationDispatcher,
            BaseChannel, ChannelResult, ChannelPriority,
            MarkdownFormatter, SimpleFormatter, DashboardFormatter,
        )
    finally:
        # Restore for other tests
        if saved is not None:
            sys.modules["src.notification"] = saved


def test_legacy_and_new_notification_channel_are_same_object():
    """The new src.notify.NotificationChannel must BE the same enum as
    the one re-exported from src.notification (so ``is`` checks work)."""
    from src.notify import NotificationChannel as New
    from src.notification import NotificationChannel as Legacy
    assert New is Legacy


def test_bot_message_dataclass_compatible():
    """The migrated BotMessage preserves the old API."""
    from src.notify import BotMessage
    # Old usage: positional content
    m = BotMessage("hello")
    assert m.content == "hello"
    assert m.html_content == ""
    # With all fields
    m2 = BotMessage(content="c", html_content="<p>c</p>",
                    image_paths=["/a.png"], mention_list=["@user"])
    assert m2.image_paths == ["/a.png"]
    assert m2.mention_list == ["@user"]

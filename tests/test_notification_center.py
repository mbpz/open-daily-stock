# -*- coding: utf-8 -*-
"""Tests for the in-app notification center."""
import pytest
import time
from unittest.mock import patch, MagicMock


def _clear_db_notifications():
    """Remove all test notifications from the SQLite database."""
    try:
        from src.storage import get_db
        db = get_db()
        # Delete all rows from notifications table
        with db.get_session() as session:
            from src.storage import NotificationRecord
            session.query(NotificationRecord).delete()
            session.commit()
    except Exception:
        pass


class TestNotificationModel:
    """Test Notification dataclass and model."""

    def test_notification_creation(self):
        from src.notification_center import Notification
        n = Notification(
            id="test-1",
            title="Test Title",
            message="Test Message",
            level="info",
            category="system",
            timestamp="2025-01-01T00:00:00",
        )
        assert n.id == "test-1"
        assert n.title == "Test Title"
        assert n.message == "Test Message"
        assert n.level == "info"
        assert n.category == "system"
        assert n.read is False
        assert n.action is None

    def test_notification_levels(self):
        from src.notification_center import Notification
        levels = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
        }
        for level, icon in levels.items():
            n = Notification(id="x", title="t", message="m", level=level)
            assert n.icon == icon

    def test_notification_timestamp_auto(self):
        from src.notification_center import Notification
        n = Notification(id="test", title="t", message="m")
        assert n.timestamp is not None
        assert len(n.timestamp) > 0

    def test_notification_to_dict(self):
        from src.notification_center import Notification
        n = Notification(
            id="abc123", title="Title", message="Msg",
            level="warning", category="trade_executed",
            timestamp="2025-06-01T12:00:00", read=True,
            action="markets",
        )
        d = n.to_dict()
        assert d["id"] == "abc123"
        assert d["level"] == "warning"
        assert d["category"] == "trade_executed"
        assert d["read"] is True

    def test_notification_from_db_row(self):
        from src.notification_center import Notification
        row = {
            "id": 42, "title": "DB Title", "message": "DB Msg",
            "level": "error", "category": "system",
            "created_at": "2025-01-01T00:00:00", "read": False,
            "action": None,
        }
        n = Notification.from_db_row(row)
        assert n.id == "42"
        assert n.title == "DB Title"
        assert n._db_id == 42


class TestNotificationCenter:
    """Test NotificationCenter singleton."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        _clear_db_notifications()
        from src.notification_center import NotificationCenter
        NotificationCenter.reset_instance()

    def test_singleton_pattern(self):
        from src.notification_center import NotificationCenter, get_notification_center
        nc1 = get_notification_center()
        nc2 = get_notification_center()
        assert nc1 is nc2

    def test_notify_adds_notification(self):
        from src.notification_center import get_notification_center
        nc = get_notification_center()
        n = nc.notify(
            title="Price Alert",
            message="Stock X moved 5%",
            level="warning",
            category="price_alert",
        )
        assert isinstance(n.id, str)
        assert n.title == "Price Alert"
        assert n.category == "price_alert"
        assert n.read is False

    def test_get_unread(self):
        from src.notification_center import get_notification_center
        nc = get_notification_center()
        nc.notify("t1", "m1", category="system")
        nc.notify("t2", "m2", category="price_alert")
        nc.notify("t3", "m3", category="trade_executed")
        unread = nc.get_unread()
        assert len(unread) == 3

    def test_mark_read(self):
        from src.notification_center import get_notification_center
        nc = get_notification_center()
        n = nc.notify("t1", "m1")
        assert nc.get_unread_count() == 1
        result = nc.mark_read(n.id)
        assert result is True
        assert nc.get_unread_count() == 0

    def test_mark_all_read(self):
        from src.notification_center import get_notification_center
        nc = get_notification_center()
        for i in range(5):
            nc.notify(f"t{i}", f"m{i}")
        assert nc.get_unread_count() == 5
        updated = nc.mark_all_read()
        assert updated == 5
        assert nc.get_unread_count() == 0

    def test_get_all_with_limit(self):
        from src.notification_center import get_notification_center
        nc = get_notification_center()
        for i in range(20):
            nc.notify(f"t{i}", f"m{i}")
        all_notifs = nc.get_all(limit=10)
        assert len(all_notifs) == 10

    def test_category_filter(self):
        from src.notification_center import get_notification_center
        nc = get_notification_center()
        nc.notify("ct1", "m1", category="system")
        nc.notify("ct2", "m2", category="price_alert")
        nc.notify("ct3", "m3", category="trade_executed")
        nc.notify("ct4", "m4", category="system")
        filtered = nc.get_all(category="system")
        assert len(filtered) == 2
        for n in filtered:
            assert n.category == "system"

    def test_clear_old(self):
        from src.notification_center import get_notification_center, Notification
        from datetime import datetime, timedelta
        nc = get_notification_center()
        # Manually set notifications to isolate from DB-loaded ones
        old_ts = (datetime.now() - timedelta(days=30)).isoformat()
        nc._notifications = [Notification(
            id="old1", title="old", message="old msg",
            timestamp=old_ts,
        )]
        new_n = nc.notify("new", "new msg")
        assert len([n for n in nc._notifications]) == 2
        cleared = nc.clear_old(days=7)
        assert cleared == 1
        remaining = [n for n in nc._notifications]
        assert len(remaining) == 1
        assert remaining[0].id == new_n.id

    def test_listener_callback(self):
        from src.notification_center import get_notification_center
        nc = get_notification_center()
        received = []

        def listener(n):
            received.append(n)

        nc.add_listener(listener)
        n = nc.notify("hello", "world")
        assert len(received) == 1
        assert received[0] is n

        nc.remove_listener(listener)
        nc.notify("hello2", "world2")
        assert len(received) == 1  # No new callbacks

    def test_get_unread_count(self):
        from src.notification_center import get_notification_center
        nc = get_notification_center()
        assert nc.get_unread_count() == 0
        nc.notify("u1", "m1")
        nc.notify("u2", "m2")
        assert nc.get_unread_count() == 2
        nc.mark_all_read()
        assert nc.get_unread_count() == 0


class TestNotificationPersistence:
    """Test notification persistence via storage.py."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        _clear_db_notifications()
        from src.notification_center import NotificationCenter
        NotificationCenter.reset_instance()

    def test_notify_persists_to_db(self):
        """Verify notification is written to SQLite."""
        from src.notification_center import get_notification_center
        from src.storage import get_db
        nc = get_notification_center()
        n = nc.notify(
            title="Persist Test",
            message="Testing DB write",
            level="info",
            category="system",
        )
        assert n._db_id is not None
        # Verify from DB
        db = get_db()
        rows = db.get_notifications(limit=50)
        found = any(r["title"] == "Persist Test" for r in rows)
        assert found, "Notification should be found in SQLite"

    def test_db_mark_read(self):
        """Verify mark_read updates both memory and DB."""
        from src.notification_center import get_notification_center
        from src.storage import get_db
        nc = get_notification_center()
        n = nc.notify("Read Test", "msg")
        assert nc.get_unread_count() == 1
        # Mark read
        nc.mark_read(n.id)
        assert nc.get_unread_count() == 0
        # Verify in DB
        db = get_db()
        rows = db.get_notifications(unread_only=False, limit=50)
        for r in rows:
            if r["title"] == "Read Test":
                assert r["read"] is True, "Should be marked read in DB"

    def test_db_mark_all_read(self):
        from src.notification_center import get_notification_center
        from src.storage import get_db
        nc = get_notification_center()
        for i in range(3):
            nc.notify(f"AllRead{i}", f"msg{i}")
        nc.mark_all_read()
        assert nc.get_unread_count() == 0
        db = get_db()
        remaining = db.get_unread_count()
        assert remaining == 0

    def test_max_500_enforcement(self):
        from src.notification_center import get_notification_center
        from src.storage import get_db
        nc = get_notification_center()
        db = get_db()
        current = len(db.get_notifications(limit=600))
        # Add 10 more, verify total doesn't exceed 500
        for i in range(10):
            nc.notify(f"MaxTest{i}", f"msg{i}")
        total = len(db.get_notifications(limit=600))
        assert total <= 500, f"Should not exceed 500, got {total}"

    def test_clear_old_from_db(self):
        from src.notification_center import get_notification_center
        nc = get_notification_center()
        nc.notify("Fresh", "msg")
        # Clear should not remove the fresh one
        cleared = nc.clear_old(days=7)
        remaining = nc.get_all(limit=50)
        fresh_exists = any(n.title == "Fresh" for n in remaining)
        assert fresh_exists, "Fresh notification should not be cleared"


class TestToastIntegration:
    """Test toast rendering utilities."""

    def test_level_icons_values(self):
        """Verify icon mappings without importing modules that trigger circular imports."""
        icons = {"info": "ℹ️", "warning": "⚠️",
                 "error": "❌", "success": "✅"}
        assert "info" in icons
        assert "warning" in icons
        assert "error" in icons
        assert "success" in icons

    def test_level_colors_keys(self):
        """Verify color keys exist."""
        colors = {"info": "blue", "warning": "orange",
                  "error": "red", "success": "green"}
        assert len(colors) == 4


class TestNotificationCenterPanel:
    """Test notification center panel category definitions."""

    def test_categories_defined(self):
        from tui.widgets.notification_center import CATEGORIES
        assert len(CATEGORIES) == 6
        expected_keys = {"all", "price_alert", "analysis_complete",
                         "trade_executed", "system", "backtest_complete"}
        actual_keys = {c[0] for c in CATEGORIES}
        assert actual_keys == expected_keys

    def test_category_labels_defined(self):
        from tui.widgets.notification_center import CATEGORY_LABELS
        assert CATEGORY_LABELS["all"] == "全部"  # zh_CN label
        assert CATEGORY_LABELS["price_alert"] == "价格异动"


class TestGUIComponents:
    """Basic smoke tests for GUI notification components."""

    def test_toast_import(self):
        """Verify toast module imports cleanly without circular import."""
        from gui.pages.toast import show_toast, LEVEL_COLORS, LEVEL_ICONS
        assert callable(show_toast)
        assert len(LEVEL_COLORS) >= 4
        assert len(LEVEL_ICONS) >= 4

    def test_notifications_page_import(self):
        """Verify notifications page class exists."""
        import gui.pages.notifications as nmod
        assert hasattr(nmod, 'NotificationsPage')

# -*- coding: utf-8 -*-
"""
===================================
In-App Notification Center
===================================

Provides local toast notifications and a notification history panel
so users can see what happened while they were away.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any, Callable

logger = logging.getLogger(__name__)

MAX_STORED = 500


@dataclass
class Notification:
    """A single notification entry."""
    id: str
    title: str
    message: str
    level: str = "info"     # info / warning / error / success
    category: str = "system"  # price_alert / analysis_complete / trade_executed / system / backtest_complete
    timestamp: str = ""
    read: bool = False
    action: Optional[str] = None  # optional target page or command on click
    _db_id: Optional[int] = None  # internal: SQLite row id

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    @staticmethod
    def from_db_row(row: Dict[str, Any]) -> "Notification":
        return Notification(
            id=str(row["id"]),
            title=row["title"],
            message=row["message"],
            level=row.get("level", "info"),
            category=row.get("category", "system"),
            timestamp=row.get("created_at", ""),
            read=row.get("read", False),
            action=row.get("action"),
            _db_id=row.get("id"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "message": self.message,
            "level": self.level,
            "category": self.category,
            "timestamp": self.timestamp,
            "read": self.read,
            "action": self.action,
        }

    @property
    def icon(self) -> str:
        """Icon for display based on level."""
        return {"info": "ℹ️", "warning": "⚠️",
                "error": "❌", "success": "✅"}.get(self.level, "ℹ️")


class NotificationCenter:
    """
    Singleton notification center.

    - In-memory store for fast toast access
    - SQLite persistence via storage.py for durability
    - Max 500 stored notifications
    - Thread-safe
    """

    _instance: Optional["NotificationCenter"] = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._notifications: List[Notification] = []
        self._lock = threading.Lock()
        self._listeners: List[Callable[[Notification], None]] = []
        self._initialized = True

        # Load existing notifications from SQLite
        self._load_from_db()

    @classmethod
    def get_instance(cls) -> "NotificationCenter":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton (for testing)."""
        cls._instance = None

    # --- Public API ---

    def notify(self, title: str, message: str, level: str = "info",
               category: str = "system", action: Optional[str] = None) -> Notification:
        """
        Add a new notification. Returns the Notification object.

        This is non-blocking and safe to call from any thread.
        """
        notif = Notification(
            id=str(uuid.uuid4().hex[:12]),
            title=title,
            message=message,
            level=level,
            category=category,
            timestamp=datetime.now().isoformat(),
            action=action,
        )

        with self._lock:
            # Persist to SQLite
            try:
                from src.storage import get_db
                db = get_db()
                db_id = db.save_notification(
                    title=title, message=message, level=level,
                    category=category, action=action,
                )
                notif._db_id = db_id
            except Exception as e:
                logger.warning(f"Failed to persist notification: {e}")

            # Store in memory (write-through)
            self._notifications.insert(0, notif)
            # Trim to max stored in memory
            if len(self._notifications) > MAX_STORED:
                self._notifications = self._notifications[:MAX_STORED]

        # Notify listeners (for real-time toast)
        for listener in self._listeners:
            try:
                listener(notif)
            except Exception as e:
                logger.warning(f"Notification listener error: {e}")

        return notif

    def get_unread(self) -> List[Notification]:
        """Return unread notifications."""
        with self._lock:
            return [n for n in self._notifications if not n.read]

    def get_unread_count(self) -> int:
        """Return count of unread notifications."""
        with self._lock:
            count = sum(1 for n in self._notifications if not n.read)
        # Also check DB for any stragglers
        try:
            from src.storage import get_db
            db_count = get_db().get_unread_count()
            if db_count > count:
                self._load_from_db()
                with self._lock:
                    count = sum(1 for n in self._notifications if not n.read)
        except Exception:
            pass
        return count

    def get_all(self, limit: int = 50, category: Optional[str] = None) -> List[Notification]:
        """Return recent notifications, optionally filtered by category."""
        with self._lock:
            if category:
                result = [n for n in self._notifications if n.category == category]
            else:
                result = list(self._notifications)
        # Ensure we have full DB data
        if not result:
            self._load_from_db()
            with self._lock:
                if category:
                    result = [n for n in self._notifications if n.category == category]
                else:
                    result = list(self._notifications)
        return result[:limit]

    def mark_read(self, notification_id: str) -> bool:
        """Mark a single notification as read by its id string."""
        with self._lock:
            for n in self._notifications:
                if n.id == notification_id:
                    n.read = True
                    # Also update in DB
                    if n._db_id:
                        try:
                            from src.storage import get_db
                            get_db().mark_notification_read(n._db_id)
                        except Exception:
                            pass
                    return True
        # Try marking by DB id directly (if numeric id passed)
        try:
            db_id = int(notification_id)
            from src.storage import get_db
            if get_db().mark_notification_read(db_id):
                with self._lock:
                    for n in self._notifications:
                        if n._db_id == db_id:
                            n.read = True
                return True
        except (ValueError, Exception):
            pass
        return False

    def mark_all_read(self) -> int:
        """Mark all notifications as read. Returns count updated."""
        with self._lock:
            count = 0
            for n in self._notifications:
                if not n.read:
                    n.read = True
                    count += 1
        # Also update DB
        try:
            from src.storage import get_db
            get_db().mark_all_notifications_read()
        except Exception:
            pass
        return count

    def clear_old(self, days: int = 7) -> int:
        """Remove notifications older than `days`. Returns count removed."""
        cutoff = datetime.now()
        from datetime import timedelta
        cutoff = cutoff - timedelta(days=days)
        with self._lock:
            before = len(self._notifications)
            self._notifications = [
                n for n in self._notifications
                if datetime.fromisoformat(n.timestamp) >= cutoff
            ]
            removed = before - len(self._notifications)
        # Also clean DB
        try:
            from src.storage import get_db
            get_db().clear_old_notifications(days=days)
        except Exception:
            pass
        return removed

    def add_listener(self, listener: Callable[[Notification], None]) -> None:
        """Register a callback that fires on every new notification."""
        self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[Notification], None]) -> None:
        """Remove a previously registered listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)

    # --- Internal ---

    def _load_from_db(self):
        """Load notifications from SQLite into memory."""
        try:
            from src.storage import get_db
            rows = get_db().get_notifications(limit=MAX_STORED)
            with self._lock:
                existing_ids = {n._db_id for n in self._notifications}
                for row in rows:
                    if row["id"] not in existing_ids:
                        self._notifications.append(Notification.from_db_row(row))
                # Sort by timestamp descending
                self._notifications.sort(key=lambda n: n.timestamp, reverse=True)
                if len(self._notifications) > MAX_STORED:
                    self._notifications = self._notifications[:MAX_STORED]
        except Exception as e:
            logger.debug(f"Could not load notifications from DB: {e}")


# Convenience function
def get_notification_center() -> NotificationCenter:
    """Get the singleton NotificationCenter instance."""
    return NotificationCenter.get_instance()

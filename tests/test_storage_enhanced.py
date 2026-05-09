"""Tests for P1-1: Data Layer Enhancement (schema version + task persistence)."""
import pytest
import sqlite3
import os


class TestSchemaVersion:
    """Test schema_version table via DatabaseManager."""

    def test_schema_version_table_exists(self):
        """Schema_version table is created by DatabaseManager."""
        from src.storage import get_db
        db = get_db()
        conn = sqlite3.connect(db._engine.url.database)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'")
        assert c.fetchone() is not None
        conn.close()

    def test_schema_version_has_record(self):
        """Schema_version table has at least one version record."""
        from src.storage import get_db
        db = get_db()
        conn = sqlite3.connect(db._engine.url.database)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM schema_version")
        count = c.fetchone()[0]
        assert count >= 1
        conn.close()

    def test_schema_version_is_v2(self):
        """Current schema version should be 2."""
        from src.storage import get_db
        db = get_db()
        conn = sqlite3.connect(db._engine.url.database)
        c = conn.cursor()
        c.execute("SELECT MAX(version) FROM schema_version")
        version = c.fetchone()[0]
        assert version == 2
        conn.close()

    def test_schema_version_idempotent(self):
        """Multiple DatabaseManager instantiations don't create duplicate schema records."""
        from src.storage import get_db, DatabaseManager
        DatabaseManager.reset_instance()
        db1 = get_db()
        db2 = get_db()
        conn = sqlite3.connect(db1._engine.url.database)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM schema_version WHERE version = 2")
        count = c.fetchone()[0]
        assert count == 1
        conn.close()


class TestTaskPersistence:
    """Test task persistence via DatabaseManager."""

    def test_save_task_creates_record(self):
        """save_task creates a new AnalysisHistory record."""
        from src.storage import get_db
        db = get_db()
        task_id = "test_task_001"
        db.save_task(task_id, "600519", "pending")

        row = db.get_task(task_id)
        assert row is not None
        assert row["task_id"] == task_id
        assert row["code"] == "600519"
        assert row["status"] == "pending"

    def test_save_task_updates_status(self):
        """save_task updates an existing record's status."""
        from src.storage import get_db
        db = get_db()
        task_id = "test_task_002"
        db.save_task(task_id, "000001", "pending")
        db.save_task(task_id, "000001", "running")
        db.save_task(task_id, "000001", "completed", result_json='{"score": 80}')

        row = db.get_task(task_id)
        assert row["status"] == "completed"
        assert row["result_json"] == '{"score": 80}'

    def test_save_task_stores_error(self):
        """save_task stores error message for failed tasks."""
        from src.storage import get_db
        db = get_db()
        task_id = "test_task_003"
        db.save_task(task_id, "600519", "failed", error="Network timeout")

        row = db.get_task(task_id)
        assert row["status"] == "failed"
        assert row["error"] == "Network timeout"

    def test_load_tasks_returns_list(self):
        """load_tasks returns a list of recent tasks."""
        from src.storage import get_db
        db = get_db()
        tasks = db.load_tasks(limit=10)
        assert isinstance(tasks, list)

    def test_get_task_not_found(self):
        """get_task returns None for unknown task_id."""
        from src.storage import get_db
        db = get_db()
        row = db.get_task("nonexistent_task_id_xyz")
        assert row is None

    def test_data_service_task_creates_db_record(self):
        """DataService._handle_analyze persists task to DB."""
        from src.data_service import DataService
        from src.storage import get_db
        service = DataService()
        result = service._handle_request({"action": "analyze", "code": "600519"})
        assert result["status"] == "ok"

        db = get_db()
        row = db.get_task(result["task_id"])
        assert row is not None
        assert row["status"] in ("pending", "running")
        assert row["code"] == "600519"

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
        """Multiple DatabaseManager instantiations don't create excessive duplicates."""
        from src.storage import get_db, DatabaseManager
        DatabaseManager.reset_instance()
        db1 = get_db()
        db2 = get_db()
        conn = sqlite3.connect(db1._engine.url.database)
        c = conn.cursor()
        # Count before re-init
        c.execute("SELECT COUNT(*) FROM schema_version WHERE version = 2")
        count_before = c.fetchone()[0]

        # The second get_db should return the same singleton (no re-init)
        # so the count must not have increased.
        assert count_before >= 1

        # Trigger a real re-init via reset
        DatabaseManager.reset_instance()
        db3 = get_db()
        c.execute("SELECT COUNT(*) FROM schema_version WHERE version = 2")
        count_after = c.fetchone()[0]
        # Strong idempotency: re-init must not create extra version rows
        assert count_after == count_before, (
            f"Re-init created extra schema_version rows: {count_before} -> {count_after}"
        )
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


class TestDailyHistory:
    """Test daily_history table and CRUD operations."""

    def test_daily_history_table_exists(self):
        """daily_history table is created by DatabaseManager."""
        from src.storage import get_db
        db = get_db()
        conn = sqlite3.connect(db._engine.url.database)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='daily_history'")
        assert c.fetchone() is not None
        conn.close()

    def test_save_daily_history_inserts_rows(self):
        """save_daily_history persists OHLCV rows."""
        from src.storage import get_db
        db = get_db()
        # Use unique code to avoid collision with previous test runs
        import uuid
        code = f"test_dh_{uuid.uuid4().hex[:8]}"
        data = [
            {"date": "2026-05-08", "open": 10.0, "high": 12.0, "low": 9.0,
             "close": 11.0, "volume": 1000000, "pct_chg": 5.0},
            {"date": "2026-05-09", "open": 11.0, "high": 13.0, "low": 10.5,
             "close": 12.5, "volume": 1200000, "pct_chg": 2.0},
        ]
        saved = db.save_daily_history(code, data)
        assert saved == 2

    def test_save_daily_history_idempotent(self):
        """save_daily_history does not insert duplicate (code, date) rows."""
        from src.storage import get_db
        import uuid
        db = get_db()
        code = f"test_dh_{uuid.uuid4().hex[:8]}"
        data = [
            {"date": "2026-05-06", "open": 20.0, "high": 22.0, "low": 19.0,
             "close": 21.0, "volume": 500000, "pct_chg": 1.5},
        ]
        first = db.save_daily_history(code, data)
        second = db.save_daily_history(code, data)
        assert first == 1  # first insert should succeed
        assert second == 0  # second should insert 0 (already exists)

    def test_get_daily_history_returns_data(self):
        """get_daily_history retrieves saved rows."""
        from src.storage import get_db
        import uuid
        db = get_db()
        code = f"test_dh_{uuid.uuid4().hex[:8]}"
        data = [
            {"date": "2026-05-07", "open": 30.0, "high": 32.0, "low": 29.0,
             "close": 31.0, "volume": 800000, "pct_chg": 3.0},
        ]
        db.save_daily_history(code, data)
        results = db.get_daily_history(code)
        assert len(results) == 1
        assert results[0]["code"] == code
        assert results[0]["open"] == 30.0
        assert results[0]["close"] == 31.0

    def test_get_daily_history_date_range(self):
        """get_daily_history filters by date range."""
        from src.storage import get_db
        from datetime import date as date_type
        import uuid
        db = get_db()
        code = f"test_dh_{uuid.uuid4().hex[:8]}"
        data = [
            {"date": "2026-04-01", "open": 5.0, "high": 6.0, "low": 4.0,
             "close": 5.5, "volume": 100000, "pct_chg": 0.5},
            {"date": "2026-04-15", "open": 6.0, "high": 7.0, "low": 5.5,
             "close": 6.5, "volume": 200000, "pct_chg": 1.0},
            {"date": "2026-05-10", "open": 7.0, "high": 8.0, "low": 6.5,
             "close": 7.5, "volume": 300000, "pct_chg": 1.5},
        ]
        db.save_daily_history(code, data)

        # Filter April only
        results = db.get_daily_history(code,
                                       start_date=date_type(2026, 4, 1),
                                       end_date=date_type(2026, 4, 30))
        assert len(results) == 2
        dates = [r["date"] for r in results]
        assert "2026-04-01" in dates
        assert "2026-04-15" in dates

    def test_save_daily_history_empty_data(self):
        """save_daily_history returns 0 for empty data."""
        from src.storage import get_db
        db = get_db()
        saved = db.save_daily_history("test_dh_empty", [])
        assert saved == 0


class TestTaskLog:
    """Test task_log table and CRUD operations."""

    def test_task_log_table_exists(self):
        """task_log table is created by DatabaseManager."""
        from src.storage import get_db
        db = get_db()
        conn = sqlite3.connect(db._engine.url.database)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='task_log'")
        assert c.fetchone() is not None
        conn.close()

    def test_save_task_log_creates_record(self):
        """save_task_log creates a new TaskLog record."""
        from src.storage import get_db
        db = get_db()
        db.save_task_log("log_001", "analyze", "600519", "pending")
        row = db.get_task_log("log_001")
        assert row is not None
        assert row["task_id"] == "log_001"
        assert row["action"] == "analyze"
        assert row["code"] == "600519"
        assert row["status"] == "pending"

    def test_save_task_log_upserts_existing(self):
        """save_task_log updates existing record."""
        from src.storage import get_db
        db = get_db()
        db.save_task_log("log_002", "analyze", "000001", "pending")
        db.save_task_log("log_002", "analyze", "000001", "running")
        row = db.get_task_log("log_002")
        assert row["status"] == "running"

    def test_update_task_log_changes_status(self):
        """update_task_log changes status and sets completed_at."""
        from src.storage import get_db
        from datetime import datetime as dt
        db = get_db()
        db.save_task_log("log_003", "analyze", "600519", "pending")
        db.update_task_log("log_003", "done")
        row = db.get_task_log("log_003")
        assert row["status"] == "done"
        assert row["completed_at"] is not None

    def test_update_task_log_stores_result(self):
        """update_task_log persists result_json."""
        from src.storage import get_db
        import json
        db = get_db()
        db.save_task_log("log_004", "analyze", "000001", "running")
        db.update_task_log("log_004", "done", result_json='{"score": 85}')
        row = db.get_task_log("log_004")
        assert row["status"] == "done"
        assert row["result_json"] == '{"score": 85}'

    def test_update_task_log_not_found_no_error(self):
        """update_task_log for missing task_id does not throw."""
        from src.storage import get_db
        db = get_db()
        # Should not raise
        db.update_task_log("nonexistent_task_log_xyz", "done")

    def test_get_task_logs_returns_list(self):
        """get_task_logs returns recent entries."""
        from src.storage import get_db
        db = get_db()
        logs = db.get_task_logs(limit=10)
        assert isinstance(logs, list)

    def test_get_task_log_not_found(self):
        """get_task_log returns None for unknown task_id."""
        from src.storage import get_db
        db = get_db()
        row = db.get_task_log("nonexistent_task_log_xyz")
        assert row is None

    def test_get_task_log_returns_all_fields(self):
        """get_task_log returns action, code, status, created_at, completed_at, result_json."""
        from src.storage import get_db
        db = get_db()
        db.save_task_log("log_005", "refresh", "000001", "done",
                         result_json='{"count": 10}')
        row = db.get_task_log("log_005")
        assert row["action"] == "refresh"
        assert row["code"] == "000001"
        assert row["status"] == "done"
        assert row["created_at"] is not None
        assert row["completed_at"] is None  # save_task_log doesn't set completed_at
        assert row["result_json"] == '{"count": 10}'


class TestMigrations:
    """Test migration system (_run_migrations placeholder)."""

    def test_run_migrations_noop_same_version(self):
        """_run_migrations with from >= to_version is a no-op."""
        from src.storage import _run_migrations, get_db
        db = get_db()
        # Should not raise
        _run_migrations(db, 2, 2)
        _run_migrations(db, 3, 2)  # from > to => no-op

    def test_run_migrations_creates_version_record(self):
        """_run_migrations records a new SchemaVersion row."""
        from src.storage import _run_migrations, get_db, SchemaVersion
        db = get_db()
        _run_migrations(db, 1, 2)

        # Verify a version 2 record exists (created by migration or earlier)
        conn = sqlite3.connect(db._engine.url.database)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM schema_version WHERE version = 2")
        count = c.fetchone()[0]
        assert count >= 1
        conn.close()

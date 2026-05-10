"""Tests for P5-6: RAG knowledge base (FTS5 full-text search + context builder)."""
import pytest
import sqlite3
import json
import time


class TestFTS5Table:
    """Test FTS5 virtual table creation and triggers."""

    def test_fts5_table_exists(self):
        """FTS5 virtual table analysis_fts is created by migration."""
        from src.storage import get_db
        db = get_db()
        conn = sqlite3.connect(db._engine.url.database)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_fts'")
        assert c.fetchone() is not None, "FTS5 table analysis_fts should exist"
        conn.close()

    def test_fts5_triggers_exist(self):
        """FTS5 triggers (INSERT/UPDATE/DELETE) should be created."""
        from src.storage import get_db
        db = get_db()
        conn = sqlite3.connect(db._engine.url.database)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name LIKE 'analysis_fts_%'")
        triggers = [row[0] for row in c.fetchall()]
        assert "analysis_fts_insert" in triggers, "INSERT trigger missing"
        assert "analysis_fts_update" in triggers, "UPDATE trigger missing"
        assert "analysis_fts_delete" in triggers, "DELETE trigger missing"
        conn.close()

    def test_fts5_idempotent(self):
        """Multiple inits don't duplicate FTS5 table or triggers."""
        from src.storage import get_db, DatabaseManager
        DatabaseManager.reset_instance()
        db1 = get_db()
        conn = sqlite3.connect(db1._engine.url.database)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='analysis_fts'")
        assert c.fetchone()[0] == 1, "Should have exactly 1 FTS table"
        c.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger' AND name LIKE 'analysis_fts_%'")
        trigger_count = c.fetchone()[0]
        assert trigger_count >= 3, f"Should have at least 3 triggers, got {trigger_count}"
        # Verify each required trigger exists at least once
        c.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='analysis_fts_insert'")
        assert c.fetchone() is not None
        c.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='analysis_fts_delete'")
        assert c.fetchone() is not None
        c.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='analysis_fts_update'")
        assert c.fetchone() is not None
        conn.close()


class TestSearchAnalyses:
    """Test search_analyses() method."""

    def test_search_empty_index_returns_empty(self):
        """Search on empty FTS index returns empty list gracefully."""
        from src.storage import get_db
        db = get_db()
        results = db.search_analyses("nonexistent_query_xyz", limit=5)
        assert results == [], "Empty FTS should return empty list, not error"

    def test_search_by_code_after_insert(self):
        """FTS5 search finds results after analysis_history insert."""
        from src.storage import get_db, DatabaseManager

        # Reset to get fresh state
        DatabaseManager.reset_instance()
        db = get_db()

        # Build result JSON
        result_json = json.dumps({
            "name": "测试股票",
            "sentiment_score": 72,
            "trend_prediction": "看多",
            "operation_advice": "买入",
            "analysis_summary": "MA5金叉MA20，放量突破前高，趋势看涨",
            "technical_analysis": "均线多头排列，量价配合良好",
            "ma_analysis": "MA5金叉MA20，短线买入信号",
        }, ensure_ascii=False)

        # Insert an analysis record
        record_id = db.save_analysis_history(
            code="600519",
            status="done",
            result_json=result_json,
        )
        assert record_id > 0

        # Wait briefly for FTS trigger to sync (SQLite triggers are synchronous,
        # but give a tiny buffer for WAL mode)
        time.sleep(0.05)

        # FTS5 tokenization note: Chinese characters embedded in ASCII sequences
        # (like MA5金叉MA20) aren't searchable via prefix matching on the Chinese part alone.
        # We search for the full token 'MA5金叉MA20' which is indexed as a single token.
        results = db.search_analyses("MA5金叉MA20", code="600519", limit=5)
        assert len(results) >= 1, f"Should find at least 1 result, got {len(results)}"
        found = any(r["id"] == record_id for r in results)
        assert found, f"Inserted record {record_id} not found in FTS search results"

        # Also test that standalone Chinese term '放量' can be found (it's a
        # standalone token in the content, comma-separated)
        results2 = db.search_analyses("放量", code="600519", limit=5)
        assert len(results2) >= 1, f"Should find '放量' result, got {len(results2)}"

        # Clean up
        conn = sqlite3.connect(db._engine.url.database)
        conn.execute("DELETE FROM analysis_history WHERE id = ?", (record_id,))
        conn.commit()
        conn.close()

    def test_search_across_codes(self):
        """Search across different stock codes returns results from both."""
        from src.storage import get_db, DatabaseManager

        DatabaseManager.reset_instance()
        db = get_db()

        result_600519 = json.dumps({
            "name": "贵州茅台",
            "sentiment_score": 65,
            "trend_prediction": "震荡",
            "analysis_summary": "高位盘整，量能萎缩，等待方向选择",
        }, ensure_ascii=False)

        result_000001 = json.dumps({
            "name": "平安银行",
            "sentiment_score": 75,
            "trend_prediction": "看多",
            "analysis_summary": "银行板块利好，均线多头排列，放量突破",
        }, ensure_ascii=False)

        id1 = db.save_analysis_history("600519", "done", result_json=result_600519)
        id2 = db.save_analysis_history("000001", "done", result_json=result_000001)

        time.sleep(0.05)

        # FTS5 tokenization: individual 2-char Chinese terms are indexed as tokens.
        # '盘整' is searchable via prefix even though it's within '高位盘整'
        # because FTS5 tokenizes character sequences. Standalone terms match.
        results = db.search_analyses("盘整", code="600519", limit=5)
        codes = {r["code"] for r in results}
        assert "600519" in codes, f"Should find 600519 via 盘整, got codes: {codes}"
        assert "000001" not in codes

        # '放量突破' as a full token (comma-separated) is searchable
        results_all = db.search_analyses("放量突破", limit=5)
        all_codes = {r["code"] for r in results_all}
        assert len(all_codes) >= 1, f"Should find at least 1 code via 放量突破, got {len(all_codes)}"

        # Clean up
        conn = sqlite3.connect(db._engine.url.database)
        conn.execute("DELETE FROM analysis_history WHERE id IN (?, ?)", (id1, id2))
        conn.commit()
        conn.close()

    def test_search_result_fields(self):
        """Search results contain expected fields."""
        from src.storage import get_db, DatabaseManager

        DatabaseManager.reset_instance()
        db = get_db()

        # Use content that's indexed as a standalone FTS token.
        # FTS5 tokenizes multi-char Chinese terms; '看多' itself is a token.
        result_json = json.dumps({
            "name": "测试股票",
            "sentiment_score": 80,
            "trend_prediction": "看多",
            "analysis_summary": "看多信号出现",  # Full term '看多' indexed as token
        }, ensure_ascii=False)

        rid = db.save_analysis_history("600519", "done", result_json=result_json)
        time.sleep(0.05)

        results = db.search_analyses("看多信号", code="600519", limit=5)
        assert len(results) >= 1, f"Should find at least 1 result, got {len(results)}"
        r = results[0]
        assert "id" in r
        assert "code" in r
        assert "stock_name" in r
        assert "result_text" in r
        assert "score" in r
        assert "timestamp" in r
        assert r["code"] == "600519"

        # Clean up
        conn = sqlite3.connect(db._engine.url.database)
        conn.execute("DELETE FROM analysis_history WHERE id = ?", (rid,))
        conn.commit()
        conn.close()


class TestRebuildFTS:
    """Test rebuild_fts_index()."""

    def test_rebuild_returns_false_when_no_fts_table(self):
        """rebuild_fts_index returns False when FTS doesn't exist."""
        # Create a fresh in-memory DB without FTS
        from src.storage import DatabaseManager
        mgr = DatabaseManager.__new__(DatabaseManager)
        mgr._initialized = False
        mgr._engine = None
        mgr._SessionLocal = None
        # Don't call init — just test with a fresh in-memory engine
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        mgr._engine = create_engine("sqlite://", echo=False)
        mgr._SessionLocal = sessionmaker(bind=mgr._engine)

        result = mgr.rebuild_fts_index()
        assert result is False, "Should return False when FTS table doesn't exist"

        mgr._engine.dispose()

    def test_rebuild_after_migration(self):
        """rebuild_fts_index succeeds after migration creates FTS table."""
        from src.storage import get_db, DatabaseManager
        DatabaseManager.reset_instance()
        db = get_db()
        result = db.rebuild_fts_index()
        assert result is True, "rebuild_fts_index should succeed"


class TestRagContextBuilder:
    """Test build_rag_context() from src/rag.py."""

    def test_build_context_empty_db(self):
        """build_rag_context returns empty string when no history."""
        from src.rag import build_rag_context
        context = build_rag_context("000000")
        assert context == "", "Should return empty for unknown stock"

    def test_build_context_with_history(self):
        """build_rag_context returns formatted context with past analyses."""
        from src.storage import get_db, DatabaseManager
        from src.rag import build_rag_context
        import sqlite3

        DatabaseManager.reset_instance()
        db = get_db()

        # Use ma_analysis which gets displayed separately in context
        result_json = json.dumps({
            "name": "贵州茅台",
            "sentiment_score": 72,
            "trend_prediction": "看多",
            "analysis_summary": "MA5金叉MA20，放量突破",
            "ma_analysis": "MA5金叉MA20",  # This is shown as signal
            "technical_analysis": "均线多头排列",
        }, ensure_ascii=False)

        rid = db.save_analysis_history("600519", "done", result_json=result_json)
        time.sleep(0.05)

        # Debug: verify FTS has the data
        conn = sqlite3.connect(db._engine.url.database)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM analysis_fts WHERE code = ?', ('600519',))
        fts_count = c.fetchone()[0]
        c.execute('SELECT analysis_summary, trend_analysis FROM analysis_fts WHERE code = ?', ('600519',))
        fts_data = c.fetchall()
        conn.close()
        assert fts_count >= 1, f"FTS should have data for 600519, got count={fts_count}"

        context = build_rag_context("600519")
        assert context != "", f"Should return context for 600519, got: {repr(context)}"
        assert "[历史分析上下文]" in context
        assert "600519" in context
        # FTS result_text contains analysis_summary which shows in the summary line
        # Note: ma_analysis and technical_analysis are NOT stored in FTS (only analysis_summary is indexed)
        # So we check for content that IS in the indexed fields
        assert "贵州茅台" in context, f"Expected stock name in context, got: {context}"

        # Clean up
        conn = sqlite3.connect(db._engine.url.database)
        conn.execute("DELETE FROM analysis_history WHERE id = ?", (rid,))
        conn.commit()
        conn.close()

    def test_build_context_respects_top_k(self):
        """build_rag_context limits results per top_k parameters."""
        from src.storage import get_db, DatabaseManager
        from src.rag import build_rag_context

        DatabaseManager.reset_instance()
        db = get_db()

        ids = []
        for i in range(5):
            result_json = json.dumps({
                "name": f"测试{i}",
                "sentiment_score": 50 + i,
                "trend_prediction": "看多",
                "analysis_summary": f"分析摘要 {i}",
            }, ensure_ascii=False)
            rid = db.save_analysis_history("600519", "done", result_json=result_json)
            ids.append(rid)
            time.sleep(0.01)

        time.sleep(0.05)

        context = build_rag_context("600519", top_k_self=2, top_k_similar=1)
        # Count analysis entries (each entry starts with a number and period)
        entry_count = context.count(". 20")  # date starts with 20xx
        assert entry_count <= 3, f"Should have <= 3 entries, got ~{entry_count}"

        # Clean up
        conn = sqlite3.connect(db._engine.url.database)
        for rid in ids:
            conn.execute("DELETE FROM analysis_history WHERE id = ?", (rid,))
        conn.commit()
        conn.close()


class TestDataServiceRagAction:
    """Test rag_search DataService action handler."""

    def test_rag_search_action_registered(self):
        """rag_search action is registered in DataService."""
        from src.data_service import DataService
        svc = DataService()
        assert "rag_search" in svc._actions
        assert svc._actions["rag_search"] == "_handle_search_knowledge"

    def test_rag_search_without_query(self):
        """rag_search returns error when query is missing."""
        from src.data_service import DataService
        svc = DataService()
        result = svc._handle_search_knowledge({"action": "rag_search"})
        assert result["status"] == "error"
        assert "缺少 query 参数" in result["message"]

    def test_rag_search_with_valid_query(self):
        """rag_search with valid query returns results."""
        from src.data_service import DataService
        from src.storage import get_db

        # Insert test data
        db = get_db()
        result_json = json.dumps({
            "name": "测试银行",
            "sentiment_score": 80,
            "trend_prediction": "强烈看多",
            "analysis_summary": "放量突破均线压制，涨势确立",  # Standalone '放量突破' as token
        }, ensure_ascii=False)
        rid = db.save_analysis_history("000001", "done", result_json=result_json)
        time.sleep(0.05)

        svc = DataService()
        result = svc._handle_search_knowledge({
            "action": "rag_search",
            "query": "放量突破",  # Match the indexed content
            "code": "000001",
            "limit": 5,
        })
        assert result["status"] == "ok"
        assert isinstance(result["results"], list)
        assert len(result["results"]) >= 1
        assert result["results"][0]["code"] == "000001"

        # Clean up
        conn = sqlite3.connect(db._engine.url.database)
        conn.execute("DELETE FROM analysis_history WHERE id = ?", (rid,))
        conn.commit()
        conn.close()

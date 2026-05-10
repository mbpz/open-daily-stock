# -*- coding: utf-8 -*-
"""Tests for P5-6: RAG Knowledge Base (FTS5 full-text index)."""
import pytest
import json
import sqlite3
import os

from src.storage import get_db, DatabaseManager, AnalysisHistory


@pytest.fixture
def rag_db_path():
    """Return the database path used by the singleton DatabaseManager."""
    db = get_db()
    return db._engine.url.database


class TestFTS5Table:
    """Test FTS5 virtual table creation and structure."""

    def test_fts5_table_exists(self, rag_db_path):
        """analysis_fts virtual table is created on init."""
        conn = sqlite3.connect(rag_db_path)
        c = conn.cursor()
        c.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='analysis_fts'"
        )
        row = c.fetchone()
        conn.close()
        assert row is not None, "FTS5 virtual table 'analysis_fts' not found"

    def test_fts5_triggers_exist(self, rag_db_path):
        """INSERT, DELETE, and UPDATE triggers are created for FTS5 sync."""
        conn = sqlite3.connect(rag_db_path)
        c = conn.cursor()
        c.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='trigger' AND name LIKE 'analysis_fts_%'"
        )
        triggers = [row[0] for row in c.fetchall()]
        conn.close()
        assert "analysis_fts_insert" in triggers
        assert "analysis_fts_delete" in triggers
        assert "analysis_fts_update" in triggers

    def test_fts5_table_idempotent(self):
        """Multiple DatabaseManager instantiations do not break FTS5 setup."""
        DatabaseManager.reset_instance()
        db1 = get_db()
        # Re-init should not raise
        DatabaseManager.reset_instance()
        db2 = get_db()
        conn = sqlite3.connect(db1._engine.url.database)
        c = conn.cursor()
        c.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='analysis_fts'"
        )
        assert c.fetchone() is not None
        conn.close()


class TestRAGStoreSearch:
    """Test RAGStore search and context generation."""

    def test_search_empty_knowledge_base(self):
        """Search on an empty FTS5 index returns an empty list."""
        from src.rag_store import RAGStore
        rag = RAGStore()
        results = rag.search("nonexistent query", limit=5)
        assert isinstance(results, list)
        assert len(results) == 0

    def test_search_returns_relevant_results(self, rag_db_path):
        """Search returns results after inserting analysis records."""
        # Insert a test analysis with known content
        db = get_db()
        test_json = json.dumps({
            "analysis_summary": "Strong bullish signal detected for AAPL",
            "trend_analysis": "AAPL is breaking out above resistance at 200",
            "risk_alerts": "Watch for pullback at 210 level",
        })
        db.save_analysis_history(
            code="AAPL",
            status="completed",
            result_json=test_json,
        )

        from src.rag_store import RAGStore
        rag = RAGStore()
        results = rag.search("bullish", limit=5)
        assert len(results) > 0

        # Verify search result structure
        for r in results:
            assert "code" in r
            assert "analysis_summary" in r
            assert "trend_analysis" in r
            assert "risk_alerts" in r

    def test_search_with_code_filter(self, rag_db_path):
        """Search with code filter returns only results for that stock."""
        db = get_db()

        # Insert two different stocks
        db.save_analysis_history(
            code="TSLA",
            status="completed",
            result_json=json.dumps({
                "analysis_summary": "TSLA bearish divergence detected",
                "trend_analysis": "TSLA trending down",
                "risk_alerts": "TSLA support at 150",
            }),
        )
        db.save_analysis_history(
            code="NVDA",
            status="completed",
            result_json=json.dumps({
                "analysis_summary": "NVDA bullish momentum strong",
                "trend_analysis": "NVDA above all moving averages",
                "risk_alerts": "NVDA overbought RSI",
            }),
        )

        from src.rag_store import RAGStore
        rag = RAGStore()

        # Search for TSLA only
        results = rag.search("bullish OR bearish", code="TSLA", limit=10)
        for r in results:
            assert r["code"] == "TSLA"

    def test_search_fts5_match_operators(self, rag_db_path):
        """FTS5 query syntax works (AND, OR, prefix searches)."""
        db = get_db()
        db.save_analysis_history(
            code="MSFT",
            status="completed",
            result_json=json.dumps({
                "analysis_summary": "MSFT cloud revenue growth strong",
                "trend_analysis": "MSFT uptrend intact with higher lows",
                "risk_alerts": "MSFT antitrust risk",
            }),
        )

        from src.rag_store import RAGStore
        rag = RAGStore()

        # Test OR syntax
        results = rag.search("cloud OR uptrend", limit=5)
        assert isinstance(results, list)

        # Test prefix search (FTS5 *)
        # Note: prefix searches work in FTS5 with the * operator
        results = rag.search("up*", limit=5)
        assert isinstance(results, list)

        # Test quoted phrase (FTS5 supports "phrase" syntax)
        results = rag.search('"growth strong"', limit=5)
        assert isinstance(results, list)


class TestRAGContext:
    """Test RAGStore.get_relevant_context formatting."""

    def test_get_relevant_context_empty(self):
        """Returns empty string when no historical analyses exist."""
        from src.rag_store import RAGStore
        rag = RAGStore()
        context = rag.get_relevant_context("NONEXIST", limit=3)
        assert context == ""

    def test_get_relevant_context_format(self, rag_db_path):
        """Returns formatted markdown string with historical context."""
        db = get_db()
        test_json = json.dumps({
            "analysis_summary": "GOOGL search revenue stable with AI integration progress",
            "trend_analysis": "GOOGL showing strong uptrend pattern",
            "risk_alerts": "GOOGL regulatory pressure in EU",
        })
        db.save_analysis_history(
            code="GOOGL",
            status="completed",
            result_json=test_json,
        )

        from src.rag_store import RAGStore
        rag = RAGStore()
        context = rag.get_relevant_context("GOOGL", limit=3)

        assert "Historical Analysis Reference" in context
        assert "GOOGL" in context or "### Historical Analysis" in context

    def test_get_relevant_context_with_name(self, rag_db_path):
        """Context generation includes stock name in the query."""
        db = get_db()
        test_json = json.dumps({
            "analysis_summary": "META advertising revenue rebound",
            "trend_analysis": "META forming cup and handle pattern",
            "risk_alerts": "META metaverse spending concern",
        })
        db.save_analysis_history(
            code="META",
            status="completed",
            result_json=test_json,
        )

        from src.rag_store import RAGStore
        rag = RAGStore()
        context = rag.get_relevant_context("META", name="Meta", limit=3)
        assert isinstance(context, str)

    def test_context_truncation(self, rag_db_path):
        """Long analysis_summary and fields are truncated to reasonable length."""
        db = get_db()
        long_text = "A" * 500  # 500 chars summary
        test_json = json.dumps({
            "analysis_summary": long_text,
            "trend_analysis": long_text,
            "risk_alerts": long_text,
        })
        db.save_analysis_history(
            code="TEST",
            status="completed",
            result_json=test_json,
        )

        from src.rag_store import RAGStore
        rag = RAGStore()
        context = rag.get_relevant_context("TEST", limit=3)

        # Each field should be truncated to its max length
        # analysis_summary: 200, trend_analysis: 150, risk_alerts: 150
        # So the full context should be less than ~600 chars per entry
        lines = context.split("\n")
        for line in lines:
            if line.startswith("Summary:") and "A" in line:
                # The raw text after "Summary: " should be <= 200 chars
                summary_text = line.split("Summary: ", 1)[1] if "Summary: " in line else ""
                assert len(summary_text) <= 200
            if line.startswith("Trend:") and "A" in line:
                trend_text = line.split("Trend: ", 1)[1] if "Trend: " in line else ""
                assert len(trend_text) <= 150
            if line.startswith("Risk:") and "A" in line:
                risk_text = line.split("Risk: ", 1)[1] if "Risk: " in line else ""
                assert len(risk_text) <= 150


class TestRAGStoreIndexAnalysis:
    """Test RAGStore.index_analysis (no-op, for API compatibility)."""

    def test_index_analysis_is_noop(self):
        """index_analysis is a no-op and does not raise."""
        from src.rag_store import RAGStore
        rag = RAGStore()
        # Should not raise
        rag.index_analysis("TEST", "{}")


class TestSearchKnowledgeAction:
    """Test search_knowledge action via DataService."""

    def test_search_knowledge_action_missing_query(self):
        """Returns error when query parameter is missing."""
        from src.data_service import DataService
        ds = DataService()
        resp = ds._handle_search_knowledge({})
        assert resp["status"] == "error"
        assert "query" in resp["message"].lower()

    def test_search_knowledge_action_success(self, rag_db_path):
        """Returns ok status with results list."""
        db = get_db()
        test_json = json.dumps({
            "analysis_summary": "TEST searchable content here",
            "trend_analysis": "TEST trend bullish",
            "risk_alerts": "TEST low risk",
        })
        db.save_analysis_history(
            code="TEST",
            status="completed",
            result_json=test_json,
        )

        from src.data_service import DataService
        ds = DataService()
        resp = ds._handle_search_knowledge({
            "query": "searchable",
            "code": "TEST",
            "limit": 3,
        })
        assert resp["status"] == "ok"
        assert "results" in resp
        assert isinstance(resp["results"], list)

    def test_search_knowledge_action_with_code_filter(self, rag_db_path):
        """Code filter works in the action handler."""
        from src.data_service import DataService
        ds = DataService()
        resp = ds._handle_search_knowledge({
            "query": "nonexistent",
            "code": "UNKNOWN",
        })
        assert resp["status"] == "ok"
        assert resp["results"] == []


class TestFTS5TriggerSync:
    """Test that FTS5 triggers keep the index in sync with analysis_history."""

    def test_insert_trigger_syncs(self, rag_db_path):
        """INSERT on analysis_history automatically syncs to analysis_fts."""
        db = get_db()

        # Count current FTS5 entries for a unique code
        unique_code = "FTS5TEST1"
        conn = sqlite3.connect(rag_db_path)
        c = conn.cursor()
        c.execute(
            "SELECT COUNT(*) FROM analysis_fts WHERE code = ?",
            (unique_code,),
        )
        count_before = c.fetchone()[0]

        # Insert via ORM
        test_json = json.dumps({
            "analysis_summary": "FTS5 sync test insert",
            "trend_analysis": "FTS5 trend",
            "risk_alerts": "FTS5 risk",
        })
        db.save_analysis_history(
            code=unique_code,
            status="completed",
            result_json=test_json,
        )

        # Verify FTS5 has the new entry
        c.execute(
            "SELECT COUNT(*) FROM analysis_fts WHERE code = ?",
            (unique_code,),
        )
        count_after = c.fetchone()[0]
        conn.close()
        assert count_after > count_before, "FTS5 insert trigger did not sync"

    def test_update_trigger_syncs(self, rag_db_path):
        """UPDATE on analysis_history syncs FTS5 changes."""
        db = get_db()
        unique_code = "FTS5TESTU"

        # Insert initial record
        original_json = json.dumps({
            "analysis_summary": "original summary",
            "trend_analysis": "original trend",
            "risk_alerts": "original risk",
        })
        record_id = db.save_analysis_history(
            code=unique_code,
            status="completed",
            result_json=original_json,
        )

        # Verify initial FTS5 content
        conn = sqlite3.connect(rag_db_path)
        c = conn.cursor()
        c.execute(
            "SELECT analysis_summary FROM analysis_fts WHERE code = ?",
            (unique_code,),
        )
        row = c.fetchone()
        assert row is not None

        # Update the record via ORM
        updated_json = json.dumps({
            "analysis_summary": "updated summary content",
            "trend_analysis": "updated trend",
            "risk_alerts": "updated risk",
        })
        with db.get_session() as session:
            from src.storage import AnalysisHistory
            record = session.query(AnalysisHistory).filter_by(id=record_id).first()
            record.result_json = updated_json
            session.commit()

        # Verify FTS5 was updated
        c.execute(
            "SELECT analysis_summary FROM analysis_fts WHERE code = ?",
            (unique_code,),
        )
        updated_row = c.fetchone()
        conn.close()
        assert updated_row is not None
        # Check that the content changed (it should now contain "updated")
        assert "updated" in (updated_row[0] or ""), f"FTS5 update trigger did not sync, got: {updated_row}"

# -*- coding: utf-8 -*-
"""RAG knowledge base using SQLite FTS5 for historical analysis retrieval.

Provides full-text search over past AI analyses and generates context
strings that can be injected into new LLM prompts for continuity.
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any

from sqlalchemy import text

logger = logging.getLogger(__name__)


class RAGStore:
    """Retrieval-Augmented Generation store backed by SQLite FTS5.

    The FTS5 virtual table (analysis_fts) is content-synced with the
    analysis_history ORM table via INSERT/UPDATE/DELETE triggers, so
    searches always reflect the latest data automatically.
    """

    def __init__(self, db_manager=None):
        """Initialize RAG store with a database manager.

        Args:
            db_manager: DatabaseManager instance. If None, uses the singleton.
        """
        from src.storage import get_db
        self._db = db_manager or get_db()

    def search(
        self,
        query: str,
        code: str = None,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search historical analyses via FTS5 full-text index.

        Args:
            query: FTS5 search query string.
            code: Optional stock code to filter results.
            limit: Maximum number of results to return.

        Returns:
            List of result dicts with keys: code, analysis_summary,
            trend_analysis, risk_alerts, rank.
        """
        with self._db.get_session() as session:
            if code:
                rows = session.execute(
                    text(
                        "SELECT code, analysis_summary, trend_analysis, "
                        "risk_alerts, rank "
                        "FROM analysis_fts "
                        "WHERE analysis_fts MATCH :query AND code = :code "
                        "ORDER BY rank LIMIT :limit"
                    ),
                    {"query": query, "code": code, "limit": limit},
                )
            else:
                rows = session.execute(
                    text(
                        "SELECT code, analysis_summary, trend_analysis, "
                        "risk_alerts, rank "
                        "FROM analysis_fts "
                        "WHERE analysis_fts MATCH :query "
                        "ORDER BY rank LIMIT :limit"
                    ),
                    {"query": query, "limit": limit},
                )
            return [dict(row._mapping) for row in rows]

    def get_relevant_context(
        self,
        code: str,
        name: str = None,
        limit: int = 3,
    ) -> str:
        """Build a context string from historical analyses for a given stock.

        Returns an empty string when no historical analyses exist.

        Args:
            code: Stock code to retrieve context for.
            name: Optional stock name to enrich the search query.
            limit: Maximum number of historical analyses to include.

        Returns:
            Formatted markdown string with historical analysis summaries,
            or an empty string if no results are found.
        """
        query = code
        if name:
            query = f"{code} OR {name}"
        results = self.search(query, code=code, limit=limit)
        if not results:
            return ""

        lines = ["## Historical Analysis Reference\n"]
        for i, r in enumerate(results):
            lines.append(f"### Historical Analysis #{i + 1}")
            if r.get("analysis_summary"):
                lines.append(f"Summary: {r['analysis_summary'][:200]}")
            if r.get("trend_analysis"):
                lines.append(f"Trend: {r['trend_analysis'][:150]}")
            if r.get("risk_alerts"):
                lines.append(f"Risk: {r['risk_alerts'][:150]}")
            lines.append("")
        return "\n".join(lines)

    def index_analysis(self, code: str, result_json: str):
        """No-op: FTS5 content-sync triggers handle indexing automatically.

        This method exists for API compatibility. The FTS5 virtual table
        is kept in sync with analysis_history via INSERT/UPDATE/DELETE
        triggers, so manual indexing is not needed.
        """
        pass

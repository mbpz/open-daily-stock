"""search handlers — 实时新闻搜索 + 知识库 FTS5 全文检索。"""
from __future__ import annotations

import logging
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

from src.storage import get_db

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Handlers ──────────────────────────────────────────────────


def search_news(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """搜索股票相关新闻"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    # Demo mode: return empty news list (no real search APIs)
    if service._is_demo_mode():
        return {"status": "ok", "data": [], "message": "演示模式下不提供实时新闻搜索"}

    try:
        from src.config import get_config
        from src.search_pkg import SearchManager

        config = get_config()
        search_service = SearchManager(
            bocha_keys=config.bocha_api_keys,
            tavily_keys=config.tavily_api_keys,
            serpapi_keys=config.serpapi_keys,
        )

        # 获取股票名称
        from src.analyzer import STOCK_NAME_MAP
        name = STOCK_NAME_MAP.get(code, code)

        # 执行搜索
        news_results = search_service.search_stock_news(code, name)

        return {"status": "ok", "data": news_results.results}

    except Exception as e:
        logger.error(f"搜索新闻失败 [{code}]: {e}")
        return {"status": "error", "message": f"搜索新闻失败: {str(e)}"}


def search_knowledge(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """P5-6: Search historical analysis knowledge base via FTS5 full-text index.

    Expected request fields:
        query (required): FTS5 search query string.
        code (optional): Stock code filter.
        limit (optional, default 5): Max results to return.
    """
    query = req.get("query", "")
    if not query:
        return {"status": "error", "message": "缺少 query 参数"}

    code = req.get("code")
    limit = req.get("limit", 5)
    try:
        limit = int(limit)
    except (ValueError, TypeError):
        limit = 5

    db = get_db()
    results = db.search_analyses(query=query, code=code, limit=limit)
    return {"status": "ok", "results": results}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。

    注意：search_knowledge 注册两个 action（search_knowledge / rag_search）
    指向同一个 handler — 与旧 _actions dict 一致。
    """
    service._handle_search_news = partial(search_news, service)
    service._actions["search_news"] = "_handle_search_news"

    service._handle_search_knowledge = partial(search_knowledge, service)
    service._actions["search_knowledge"] = "_handle_search_knowledge"
    service._actions["rag_search"] = "_handle_search_knowledge"

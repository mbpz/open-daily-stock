# -*- coding: utf-8 -*-
"""DEPRECATED — 全部实现已迁至 ``src.search_pkg``。

本文件保留作向后兼容 shim。所有 import 均从 src.search_pkg 重新导出。
新代码请直接 from src.search_pkg import ...。

将在 v0.7 删除本文件。
"""
from src.search_pkg.base import (  # noqa: F401
    BaseSearchProvider,
    SearchResponse,
    SearchResult,
)
from src.search_pkg.manager import SearchManager
from src.search_pkg.singletons import get_search_service, reset_search_service  # noqa: F401


class SearchService(SearchManager):
    """旧 SearchService 名字 — 现以 SearchManager 别名形式提供。

    兼容旧构造签名：SearchService(bocha_keys=..., tavily_keys=..., serpapi_keys=...)
    """


__all__ = [
    "SearchService",
    "SearchManager",
    "SearchResult",
    "SearchResponse",
    "BaseSearchProvider",
    "get_search_service",
    "reset_search_service",
]

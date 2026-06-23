"""
搜索模块 - 重构后版本

新代码使用：
    from src.search_pkg import SearchManager, get_search_service
"""
from .base import BaseSearchProvider, SearchResponse, SearchResult
from .bocha import BochaProvider
from .manager import SearchManager
from .serpapi import SerpapiProvider
from .singletons import get_search_service, reset_search_service
from .tavily import TavilyProvider

__all__ = [
    "SearchResult",
    "SearchResponse",
    "BaseSearchProvider",
    "BochaProvider",
    "TavilyProvider",
    "SerpapiProvider",
    "SearchManager",
    "get_search_service",
    "reset_search_service",
]

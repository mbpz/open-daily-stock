"""
搜索模块 - 重构后版本

支持多源搜索：
- Bocha API
- Tavily API
- SerpAPI

提供 key 轮换和结果合并。
"""
from .base import BaseSearchProvider, SearchResult

__all__ = [
    "SearchManager",
    "SearchResult",
    "BaseSearchProvider",
    "BochaProvider",
    "TavilyProvider",
    "SerpapiProvider",
]

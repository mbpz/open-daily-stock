"""
搜索模块 - 重构后版本

支持多源搜索：
- Bocha API
- Tavily API
- SerpAPI

提供 key 轮换和结果合并。
"""
from .base import BaseSearchProvider, SearchResult
from .bocha import BochaProvider

__all__ = [
    "SearchResult",
    "BaseSearchProvider",
    "BochaProvider",
]

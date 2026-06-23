"""搜索服务全局单例。

迁自 src/search_service.py:get_search_service / reset_search_service。
"""
from __future__ import annotations

import threading
from typing import Optional

from src.config import get_config

from .manager import SearchManager

_instance: Optional[SearchManager] = None
_lock = threading.Lock()


def get_search_service() -> SearchManager:
    """获取全局 SearchManager 单例（线程安全的双重检查）。"""
    global _instance
    if _instance is None:
        with _lock:
            if _instance is None:
                config = get_config()
                _instance = SearchManager(
                    bocha_keys=getattr(config, "bocha_api_keys", []) or [],
                    tavily_keys=getattr(config, "tavily_api_keys", []) or [],
                    serpapi_keys=getattr(config, "serpapi_keys", []) or [],
                )
    return _instance


def reset_search_service() -> None:
    """重置全局单例（配置热更新或测试使用）。"""
    global _instance
    with _lock:
        _instance = None

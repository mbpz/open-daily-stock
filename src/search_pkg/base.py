"""搜索提供者基类"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass
import logging
import threading

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """搜索结果项"""
    title: str
    url: str
    snippet: str
    source: str  # e.g., "bocha", "tavily", "serpapi"
    published_at: Optional[str] = None


class BaseSearchProvider(ABC):
    """
    搜索提供者抽象基类

    所有搜索提供者继承此类，实现 search 方法。
    """

    def __init__(self, api_keys: List[str]):
        self.api_keys = api_keys
        self._current_key_index = 0
        self._key_lock = threading.Lock()
        self.name = self.__class__.__name__

    def get_next_key(self) -> Optional[str]:
        """轮换取下一个 key（线程安全，可在并发 search_all 中使用）"""
        if not self.api_keys:
            return None
        with self._key_lock:
            key = self.api_keys[self._current_key_index]
            self._current_key_index = (self._current_key_index + 1) % len(self.api_keys)
            return key

    @abstractmethod
    def search(self, query: str, **kwargs) -> List[SearchResult]:
        """
        执行搜索

        Args:
            query: 搜索查询
            **kwargs: 提供者特定参数

        Returns:
            List[SearchResult]: 搜索结果列表
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """检查提供者是否可用（至少有一个有效 key）"""
        pass

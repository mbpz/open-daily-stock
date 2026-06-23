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
    published_date: Optional[str] = None

    def to_text(self) -> str:
        """转换为文本格式（迁移兼容：旧 SearchResult 的 to_text 方法）。"""
        date_str = f" ({self.published_date})" if self.published_date else ""
        return f"【{self.source}】{self.title}{date_str}\n{self.snippet}"


@dataclass
class SearchResponse:
    """搜索响应（兼容旧 SearchResponse 契约：.results / .success / .provider）。"""
    query: str
    results: List[SearchResult]
    provider: str
    success: bool = True
    error_message: Optional[str] = None

    def to_context(self, max_results: int = 5) -> str:
        """将搜索结果转换为可用于 AI 分析的上下文。"""
        if not self.success or not self.results:
            return f"搜索 '{self.query}' 未找到相关结果。"

        lines = [f"【{self.query} 搜索结果】（来源：{self.provider}）"]
        for i, result in enumerate(self.results[:max_results], 1):
            lines.append(f"\n{i}. {result.to_text()}")

        return "\n".join(lines)


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

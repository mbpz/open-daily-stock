"""搜索管理器 - 多 key 负载均衡"""
import logging
from typing import List, Dict, Any, Optional
from .base import SearchResult
from .bocha import BochaProvider
from .tavily import TavilyProvider
from .serpapi import SerpapiProvider

logger = logging.getLogger(__name__)


class SearchManager:
    """
    搜索管理器

    整合多个搜索提供者，支持 key 轮换和结果合并。
    提供统一的 search_stock_news 接口给 DataService 使用。
    """

    def __init__(
        self,
        bocha_keys: List[str] = None,
        tavily_keys: List[str] = None,
        serpapi_keys: List[str] = None,
    ):
        self.bocha_keys = bocha_keys or []
        self.tavily_keys = tavily_keys or []
        self.serpapi_keys = serpapi_keys or []

        self.providers: List[Any] = []

        # 初始化所有可用的提供者
        if self.bocha_keys:
            self.providers.append(BochaProvider(self.bocha_keys))
        if self.tavily_keys:
            self.providers.append(TavilyProvider(self.tavily_keys))
        if self.serpapi_keys:
            self.providers.append(SerpapiProvider(self.serpapi_keys))

        logger.info(f"搜索管理器初始化完成，共 {len(self.providers)} 个提供者")

    def is_available(self) -> bool:
        """至少有一个提供者可用"""
        return len(self.providers) > 0

    def search(self, query: str, **kwargs) -> List[SearchResult]:
        """
        搜索（单源）

        按优先级尝试各提供者，直到成功。
        """
        for provider in self.providers:
            if not provider.is_available():
                continue

            try:
                results = provider.search(query, **kwargs)
                if results:
                    return results
            except Exception as e:
                logger.warning(f"{provider.name} 搜索失败: {e}")
                continue

        return []

    def search_all(self, query: str, **kwargs) -> List[SearchResult]:
        """
        搜索（多源合并）

        并发请求所有提供者，合并结果。
        """
        all_results = []
        seen_urls = set()

        for provider in self.providers:
            if not provider.is_available():
                continue

            try:
                results = provider.search(query, **kwargs)
                # 去重
                for r in results:
                    if r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append(r)
            except Exception as e:
                logger.warning(f"{provider.name} 搜索异常: {e}")

        return all_results

    def search_stock_news(
        self,
        stock_name: str,
        stock_code: str,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        搜索股票新闻

        专门为 AI 分析设计的新闻搜索接口。

        Args:
            stock_name: 股票名称（用于搜索）
            stock_code: 股票代码
            days: 搜索最近天数

        Returns:
            List[Dict]: 格式化后的新闻列表，适合作为 AI 分析输入
        """
        # 构建搜索查询
        query = f"{stock_name} {stock_code} 股票"

        # 使用多源合并搜索
        results = self.search_all(query, count=10)

        # 格式化为 AI 分析友好的格式
        news_items = []
        for r in results:
            news_items.append({
                "title": r.title,
                "url": r.url,
                "snippet": r.snippet,
                "source": r.source,
            })

        return news_items
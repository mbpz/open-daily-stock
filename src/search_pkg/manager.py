"""搜索管理器 - 多 key 负载均衡 + 多源并发"""
import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from .base import SearchResult, BaseSearchProvider
from .bocha import BochaProvider
from .tavily import TavilyProvider
from .serpapi import SerpapiProvider

logger = logging.getLogger(__name__)


class SearchManager:
    """
    搜索管理器

    整合多个搜索提供者，支持 key 轮换和结果合并。
    提供统一的 search_stock_news 接口给 DataService 使用。

    并发模型：
    - search()        — 顺序回退（先到先得，最快响应）
    - search_all()    — ThreadPoolExecutor 并发合并（覆盖性更好）
    - 每个 provider 的 key 轮换内部用锁保护，可在并发下安全使用
    """

    DEFAULT_PROVIDER_TIMEOUT = 10.0
    DEFAULT_MAX_WORKERS = 4

    def __init__(
        self,
        bocha_keys: List[str] = None,
        tavily_keys: List[str] = None,
        serpapi_keys: List[str] = None,
    ):
        self.bocha_keys = bocha_keys or []
        self.tavily_keys = tavily_keys or []
        self.serpapi_keys = serpapi_keys or []

        self.providers: List[BaseSearchProvider] = []

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
        搜索（单源，按优先级回退）

        按优先级尝试各提供者，直到拿到非空结果。
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

    def search_all(
        self,
        query: str,
        timeout: Optional[float] = None,
        max_workers: Optional[int] = None,
        **kwargs,
    ) -> List[SearchResult]:
        """
        搜索（多源并发合并）

        并发请求所有可用提供者，按 url 去重后合并结果。
        任何一个 provider 抛异常 / 超时都不会影响其他 provider。

        Args:
            query: 搜索关键词
            timeout: 总超时（秒），None = 不限；默认 10s
            max_workers: 并发线程数，默认 4
            **kwargs: 透传给各 provider

        Returns:
            去重后的 SearchResult 列表
        """
        timeout = timeout if timeout is not None else self.DEFAULT_PROVIDER_TIMEOUT
        max_workers = max_workers or self.DEFAULT_MAX_WORKERS

        available = [p for p in self.providers if p.is_available()]
        if not available:
            return []

        all_results: List[SearchResult] = []
        seen_urls: set = set()
        lock = threading.Lock()

        def _run(p: BaseSearchProvider) -> List[SearchResult]:
            try:
                return p.search(query, **kwargs)
            except Exception as e:
                logger.warning(f"{p.name} 搜索异常: {e}")
                return []

        ex = ThreadPoolExecutor(
            max_workers=max(1, min(max_workers, len(available))),
            thread_name_prefix="search",
        )
        futures = {ex.submit(_run, p): p for p in available}
        try:
            try:
                for fut in as_completed(futures, timeout=timeout):
                    try:
                        results = fut.result()
                    except Exception as e:  # defensive; _run already swallows
                        logger.warning(f"search task 异常: {e}")
                        continue
                    with lock:
                        for r in results:
                            if r.url and r.url not in seen_urls:
                                seen_urls.add(r.url)
                                all_results.append(r)
            except TimeoutError:
                logger.warning(
                    f"search_all 总超时 {timeout}s，返回已收集结果 ({len(all_results)})"
                )
                # Cancel pending futures; do NOT wait for slow providers.
                for fut in futures:
                    if not fut.done():
                        fut.cancel()
        finally:
            # Don't block on stuck providers; they run as daemon-ish threads
            # inside the executor and will be torn down on GC.
            ex.shutdown(wait=False)

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

        # 使用多源并发合并搜索
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

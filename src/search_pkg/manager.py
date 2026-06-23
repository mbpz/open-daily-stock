"""搜索管理器 - 多 key 负载均衡 + 多源并发"""
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Optional

from .base import SearchResponse, SearchResult, BaseSearchProvider
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
        stock_code: str,
        stock_name: str,
        max_results: int = 10,
        focus_keywords: Optional[List[str]] = None,
        days: Optional[int] = None,  # noqa: ARG002 — kept for backwards compat
    ) -> SearchResponse:
        """搜索股票新闻。

        迁自 src/search_service.py:SearchService.search_stock_news。返回 SearchResponse
        以兼容 data_service.py / market_analyzer.py 的调用契约。

        Args:
            stock_code: 股票代码（"market" 表示大盘搜索）
            stock_name: 股票名称
            max_results: 最大结果数（每个 provider 上限）
            focus_keywords: 额外查询词（可选，拼接到查询）
            days: 搜索最近天数（保留参数兼容，目前不参与查询）

        Returns:
            SearchResponse(query=..., results=[SearchResult], provider="multi")
        """
        # 构建查询
        if stock_code == "market":
            query = stock_name
        else:
            query = f"{stock_name} {stock_code} 股票"
        if focus_keywords:
            query = f"{query} {' '.join(focus_keywords)}"

        # 多源并发合并
        results = self.search_all(query, count=max_results)

        return SearchResponse(
            query=query,
            results=results,
            provider="multi",
            success=bool(results),
            error_message=None if results else "未找到结果",
        )

    # ------------------------------------------------------------------
    # 多维度情报搜索 — 迁自 src/search_service.py:SearchService
    # ------------------------------------------------------------------

    # 搜索维度配置（迁自 search_service.py:search_comprehensive_intel）
    _INTEL_DIMENSIONS = [
        {
            "name": "latest_news",
            "query_tmpl": "{name} {code} 最新 新闻 重大 事件",
            "desc": "📰 最新消息",
        },
        {
            "name": "market_analysis",
            "query_tmpl": "{name} 研报 目标价 评级 深度分析",
            "desc": "📈 机构分析",
        },
        {
            "name": "risk_check",
            "query_tmpl": "{name} 减持 处罚 违规 诉讼 利空 风险",
            "desc": "⚠️ 风险排查",
        },
        {
            "name": "earnings",
            "query_tmpl": "{name} 业绩预告 财报 营收 净利润 同比增长",
            "desc": "📊 业绩预期",
        },
        {
            "name": "industry",
            "query_tmpl": "{name} 所在行业 竞争对手 市场份额 行业前景",
            "desc": "🏭 行业分析",
        },
    ]

    def search_comprehensive_intel(
        self,
        stock_code: str,
        stock_name: str,
        max_searches: int = 3,
    ) -> Dict[str, SearchResponse]:
        """多维度情报搜索。

        迁自 src/search_service.py:SearchService.search_comprehensive_intel。
        每个维度轮流挑一个 provider 调用，避免单 provider 配额耗尽。
        """
        results: Dict[str, SearchResponse] = {}
        available = [p for p in self.providers if p.is_available()]
        if not available:
            return results

        provider_index = 0
        search_count = 0

        for dim in self._INTEL_DIMENSIONS:
            if search_count >= max_searches:
                break

            provider = available[provider_index % len(available)]
            provider_index += 1
            query = dim["query_tmpl"].format(name=stock_name, code=stock_code)

            logger.info(f"[情报搜索] {dim['desc']}: 使用 {provider.name}")
            try:
                hits = provider.search(query, count=3)
                resp = SearchResponse(
                    query=query,
                    results=hits,
                    provider=provider.name,
                    success=bool(hits),
                    error_message=None if hits else "未找到结果",
                )
            except Exception as e:
                logger.warning(f"[情报搜索] {dim['desc']}: {provider.name} 异常: {e}")
                resp = SearchResponse(
                    query=query,
                    results=[],
                    provider=provider.name,
                    success=False,
                    error_message=str(e),
                )

            results[dim["name"]] = resp
            search_count += 1
            time.sleep(0.5)  # 防止请求过快

        return results

    def format_intel_report(
        self,
        intel_results: Dict[str, SearchResponse],
        stock_name: str,
    ) -> str:
        """格式化情报搜索结果为报告文本。

        迁自 src/search_service.py:SearchService.format_intel_report。
        """
        lines = [f"【{stock_name} 情报搜索结果】"]
        dim_desc_map = {d["name"]: d["desc"] for d in self._INTEL_DIMENSIONS}

        for dim_name in dim_desc_map:
            if dim_name not in intel_results:
                continue
            resp = intel_results[dim_name]
            lines.append(f"\n{dim_desc_map[dim_name]} (来源: {resp.provider}):")
            if resp.success and resp.results:
                for i, r in enumerate(resp.results[:4], 1):
                    date_str = f" [{r.published_date}]" if r.published_date else ""
                    lines.append(f"  {i}. {r.title}{date_str}")
                    snippet = r.snippet[:150] if len(r.snippet) > 20 else r.snippet
                    lines.append(f"     {snippet}...")
            else:
                lines.append("  未找到相关信息")

        return "\n".join(lines)

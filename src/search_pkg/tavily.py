"""Tavily 搜索提供者"""
import logging
import requests
from typing import List
from .base import BaseSearchProvider, SearchResult

logger = logging.getLogger(__name__)


class TavilyProvider(BaseSearchProvider):
    """Tavily Search API 提供者"""

    BASE_URL = "https://api.tavily.com/search"

    def __init__(self, api_keys: List[str]):
        super().__init__(api_keys)

    def is_available(self) -> bool:
        return len(self.api_keys) > 0

    def search(self, query: str, **kwargs) -> List[SearchResult]:
        if not self.is_available():
            return []

        api_key = self.get_next_key()
        if not api_key:
            return []

        try:
            payload = {
                "api_key": api_key,
                "query": query,
                "search_depth": kwargs.get("search_depth", "basic"),
                "max_results": kwargs.get("count", 10),
            }

            response = requests.post(
                self.BASE_URL,
                json=payload,
                timeout=15,
            )

            if response.status_code != 200:
                return []

            data = response.json()

            results = []
            for item in data.get("results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source="tavily",
                    published_at=item.get("published_date"),
                ))

            return results

        except Exception as e:
            logger.error(f"Tavily API 异常: {e}")
            return []
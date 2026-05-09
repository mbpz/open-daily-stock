"""SerpAPI 搜索提供者"""
import logging
import requests
from typing import List
from .base import BaseSearchProvider, SearchResult

logger = logging.getLogger(__name__)


class SerpapiProvider(BaseSearchProvider):
    """SerpAPI Google 搜索提供者"""

    BASE_URL = "https://serpapi.com/search"

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
            params = {
                "q": query,
                "api_key": api_key,
                "engine": "google_news",
                "num": kwargs.get("count", 10),
            }

            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=15,
            )

            if response.status_code != 200:
                return []

            data = response.json()

            results = []
            for item in data.get("organic_results", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source="serpapi",
                ))

            return results

        except Exception as e:
            logger.error(f"SerpAPI 异常: {e}")
            return []
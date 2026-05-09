"""Bocha 搜索提供者"""
import logging
import requests
from typing import List
from .base import BaseSearchProvider, SearchResult

logger = logging.getLogger(__name__)


class BochaProvider(BaseSearchProvider):
    """Bocha 搜索 API 提供者"""

    BASE_URL = "https://api.bocha.com/v1/search"

    def __init__(self, api_keys: List[str]):
        super().__init__(api_keys)

    def is_available(self) -> bool:
        return len(self.api_keys) > 0

    def search(self, query: str, **kwargs) -> List[SearchResult]:
        if not self.is_available():
            logger.warning("Bocha API key 未配置")
            return []

        api_key = self.get_next_key()
        if not api_key:
            return []

        try:
            params = {
                "query": query,
                "apikey": api_key,
                "count": kwargs.get("count", 10),
            }

            response = requests.get(
                self.BASE_URL,
                params=params,
                timeout=10,
            )

            if response.status_code != 200:
                logger.warning(f"Bocha API 请求失败: {response.status_code}")
                return []

            data = response.json()

            results = []
            for item in data.get("data", []):
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", ""),
                    source="bocha",
                    published_at=item.get("publish_time"),
                ))

            return results

        except requests.exceptions.Timeout:
            logger.error("Bocha API 请求超时")
            return []
        except Exception as e:
            logger.error(f"Bocha API 异常: {e}")
            return []
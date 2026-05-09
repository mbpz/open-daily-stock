# search_service.py Modularization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the 1079-line `src/search_service.py` into: `src/search/bocha.py`, `src/search/tavily.py`, `src/search/serpapi.py`, and a `src/search/manager.py` that handles multi-key load balancing.

**Architecture:** Keep `SearchService` as facade. Each search provider is a separate class. `SearchManager` handles key rotation, rate limiting, and result merging. DataService will call `SearchManager.search_stock_news()`.

**Tech Stack:** Python stdlib (requests), no new dependencies.

---

## File Structure

```
src/search/
    __init__.py           # CREATE: SearchManager, re-exports
    base.py               # CREATE: BaseSearchProvider abstract class
    bocha.py              # CREATE: Bocha search provider
    tavily.py             # CREATE: Tavily search provider
    serpapi.py            # CREATE: SerpAPI search provider
    manager.py            # CREATE: Multi-key load balancer
src/search_service.py     # MODIFY: Keep compatibility shim (import from new location)
tests/test_search/
    test_bocha.py         # CREATE
    test_tavily.py        # CREATE
    test_manager.py       # CREATE
    test_search_service.py # CREATE (backward compat test)
```

---

## Baseline: Current State

The existing `src/search_service.py` (1079 lines) contains:
1. `SearchService` class with all search logic crammed together
2. Bocha API integration (300+ lines)
3. Tavily API integration (200+ lines)
4. SerpAPI integration (200+ lines)
5. Multi-key rotation logic (100+ lines)
6. Result parsing/merging (150+ lines)

**Problem:** Adding a new provider or changing key logic requires modifying the large file. Hard to test individual providers.

---

## Task 1: Create directory structure and base classes

**Files:**
- Create: `src/search/__init__.py`
- Create: `src/search/base.py`
- Modify: `src/search_service.py` (add compatibility import)

- [ ] **Step 1: Create base.py with abstract provider class**

```python
# src/search/base.py
"""搜索提供者基类"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

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
        self.name = self.__class__.__name__

    def get_next_key(self) -> Optional[str]:
        """轮换取下一个 key"""
        if not self.api_keys:
            return None
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
```

- [ ] **Step 2: Create search/__init__.py**

```python
# src/search/__init__.py
"""
搜索模块 - 重构后版本

支持多源搜索：
- Bocha API
- Tavily API
- SerpAPI

提供 key 轮换和结果合并。
"""
from .manager import SearchManager
from .base import SearchResult, BaseSearchProvider
from .bocha import BochaProvider
from .tavily import TavilyProvider
from .serpapi import SerpapiProvider

__all__ = [
    "SearchManager",
    "SearchResult",
    "BaseSearchProvider",
    "BochaProvider",
    "TavilyProvider",
    "SerpapiProvider",
]
```

- [ ] **Step 3: Add compatibility import to search_service.py**

Add at top of `src/search_service.py`:
```python
# 导入新模块（向后兼容）
import warnings
warnings.warn(
    "SearchService 已迁移到 src.search.SearchManager",
    DeprecationWarning,
    stacklevel=2
)
from src.search import SearchManager
```

- [ ] **Step 4: Run test to verify import works**

Run: `python -c "from src.search import SearchManager; print('OK')"`
Expected: OK

- [ ] **Step 5: Commit**

```bash
git add src/search/ src/search_service.py
git commit -m "refactor: create search module directory structure"
```

---

## Task 2: Implement bocha.py

**Files:**
- Create: `src/search/bocha.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_search/test_bocha.py
import pytest
from unittest.mock import Mock, patch
from src.search.bocha import BochaProvider

class TestBochaProvider:
    def test_is_available_with_valid_key(self):
        provider = BochaProvider(["test_key_123"])
        assert provider.is_available() == True

    def test_is_available_without_key(self):
        provider = BochaProvider([])
        assert provider.is_available() == False

    def test_search_returns_results(self):
        provider = BochaProvider(["test_key"])
        mock_response = {
            "data": [
                {"title": "Test Article", "url": "https://example.com", "content": "Test snippet"}
            ]
        }
        with patch('requests.post') as mock_post:
            mock_post.return_value = Mock(status_code=200, json=lambda: mock_response)
            results = provider.search("贵州茅台")
            assert len(results) >= 1
            assert results[0].source == "bocha"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search/test_bocha.py -v`
Expected: FAIL - module not found

- [ ] **Step 3: Implement bocha.py**

```python
# src/search/bocha.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search/test_bocha.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/search/bocha.py tests/test_search/test_bocha.py
git commit -m "refactor: extract bocha provider to separate module"
```

---

## Task 3: Implement tavily.py

**Files:**
- Create: `src/search/tavily.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_search/test_tavily.py
import pytest
from unittest.mock import Mock, patch
from src.search.tavily import TavilyProvider

class TestTavilyProvider:
    def test_is_available_with_valid_key(self):
        provider = TavilyProvider(["test_key_123"])
        assert provider.is_available() == True

    def test_search_returns_results(self):
        provider = TavilyProvider(["test_key"])
        mock_response = {
            "results": [
                {"title": "Test", "url": "https://example.com", "content": "Snippet"}
            ]
        }
        with patch('requests.post') as mock_post:
            mock_post.return_value = Mock(status_code=200, json=lambda: mock_response)
            results = provider.search("股票")
            assert len(results) >= 1
            assert results[0].source == "tavily"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search/test_tavily.py -v`
Expected: FAIL

- [ ] **Step 3: Implement tavily.py**

```python
# src/search/tavily.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search/test_tavily.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/search/tavily.py tests/test_search/test_tavily.py
git commit -m "refactor: extract tavily provider to separate module"
```

---

## Task 4: Implement serpapi.py

**Files:**
- Create: `src/search/serpapi.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_search/test_serpapi.py
import pytest
from unittest.mock import Mock, patch
from src.search.serpapi import SerpapiProvider

class TestSerpapiProvider:
    def test_is_available_with_valid_key(self):
        provider = SerpapiProvider(["test_key"])
        assert provider.is_available() == True

    def test_search_returns_results(self):
        provider = SerpapiProvider(["test_key"])
        mock_response = {
            "organic_results": [
                {"title": "Test", "link": "https://example.com", "snippet": "Snippet"}
            ]
        }
        with patch('requests.get') as mock_get:
            mock_get.return_value = Mock(status_code=200, json=lambda: mock_response)
            results = provider.search("股票")
            assert len(results) >= 1
            assert results[0].source == "serpapi"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search/test_serpapi.py -v`
Expected: FAIL

- [ ] **Step 3: Implement serpapi.py**

```python
# src/search/serpapi.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search/test_serpapi.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/search/serpapi.py tests/test_search/test_serpapi.py
git commit -m "refactor: extract serpapi provider to separate module"
```

---

## Task 5: Implement manager.py (multi-key load balancer)

**Files:**
- Create: `src/search/manager.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_search/test_manager.py
import pytest
from unittest.mock import Mock
from src.search.manager import SearchManager

class TestSearchManager:
    def test_manager_with_multiple_providers(self):
        manager = SearchManager(
            bocha_keys=["key1", "key2"],
            tavily_keys=["key3"],
            serpapi_keys=["key4"],
        )
        assert len(manager.providers) >= 3

    def test_search_stock_news(self):
        manager = SearchManager(bocha_keys=["key1"])
        # Mock the search to return sample data
        with pytest.mock.patch.object(manager.providers[0], 'search') as mock:
            mock.return_value = []
            results = manager.search_stock_news("贵州茅台", "600519")
            assert isinstance(results, list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_search/test_manager.py -v`
Expected: FAIL

- [ ] **Step 3: Implement manager.py**

```python
# src/search/manager.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_search/test_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/search/manager.py tests/test_search/test_manager.py
git commit -m "refactor: add search manager with multi-key load balancing"
```

---

## Task 6: Final integration - Update DataService to use new search module

**Files:**
- Modify: `src/data_service.py` (_handle_search_news handler)

- [ ] **Step 1: Update _handle_search_news to use SearchManager**

```python
# In src/data_service.py, update _handle_search_news:
def _handle_search_news(self, req: Dict[str, Any]) -> Dict[str, Any]:
    """搜索股票相关新闻"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    try:
        # 使用新的 SearchManager
        from src.search import SearchManager
        from src.config import get_config

        config = get_config()
        manager = SearchManager(
            bocha_keys=config.bocha_api_keys,
            tavily_keys=config.tavily_api_keys,
            serpapi_keys=config.serpapi_keys
        )

        # 获取股票名称
        from src.analyzer import STOCK_NAME_MAP
        name = STOCK_NAME_MAP.get(code, code)

        # 执行搜索
        news_results = manager.search_stock_news(name, code)

        return {"status": "ok", "data": news_results}

    except Exception as e:
        logger.error(f"搜索新闻失败 [{code}]: {e}")
        return {"status": "error", "message": f"搜索新闻失败: {str(e)}"}
```

- [ ] **Step 2: Run integration test**

Run: `pytest tests/test_data_service.py::TestSearchNewsAction -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add src/data_service.py
git commit -m "refactor: update DataService to use new SearchManager"
```

---

## Self-Review Checklist

1. **Spec coverage:** 每个搜索源都有独立模块？
   - Bocha provider ✅
   - Tavily provider ✅
   - SerpAPI provider ✅
   - SearchManager ✅

2. **No placeholder code:** 所有方法都有实际实现

3. **Backward compatibility:** 旧 import 路径仍然可用（through search_service.py shim）

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-09-search-modularization.md`**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
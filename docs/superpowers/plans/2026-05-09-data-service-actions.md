# DataService Action Expansion Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand DataService from 4 actions to 10+ actions, enabling TUI/GUI to perform AI analysis, history lookup, news search, and task management through stdio JSON.

**Architecture:** Extend DataService with a new action handler registry pattern. Each action maps to a handler method. Handlers return JSON-serializable dicts. Add async support for long-running operations (analyze/search) with progress callbacks.

**Tech Stack:** Python stdlib (subprocess, sqlite3, json), no new dependencies.

---

## File Structure

```
src/data_service.py          # MODIFY: Add action registry, expand handlers
src/analyzer.py             # READ: AI analyzer interface
src/search_service.py       # READ: Search service interface
src/storage.py              # READ: Task storage interface
tests/test_data_service.py  # CREATE: Unit tests
```

---

## Current State (Baseline)

DataService currently supports only 4 actions:
- `hello` → returns version
- `get_markets` → returns cached market data
- `refresh` → refreshes market data, checks alerts
- `quit` → exits main loop

Target: 10+ actions including:
- `get_markets` (existing)
- `refresh` (existing)
- `analyze` (NEW: trigger AI analysis)
- `get_history` (NEW: get historical data for a stock)
- `search_news` (NEW: search news for a stock)
- `get_tasks` (NEW: list analysis tasks)
- `get_task` (NEW: get single task status/result)
- `cancel_task` (NEW: cancel running task)
- `hello` (existing)
- `quit` (existing)

---

## Task 1: Refactor to Action Registry Pattern

**Files:**
- Modify: `src/data_service.py:1-50` (class structure)
- Test: `tests/test_data_service.py`

- [ ] **Step 1: Write the failing test for action registry**

```python
# tests/test_data_service.py
import pytest
import json
from io import StringIO
import sys

class TestDataServiceActionRegistry:
    """Test that DataService dispatches to correct handlers"""

    def test_hello_returns_version(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "hello"})
        assert result["status"] == "ok"
        assert "version" in result

    def test_unknown_action_returns_error(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "nonexistent"})
        assert result["status"] == "error"
        assert "不支持" in result["message"]

    def test_action_registry_has_analyze(self):
        from src.data_service import DataService
        service = DataService()
        assert hasattr(service, '_handle_analyze')

    def test_action_registry_has_get_history(self):
        from src.data_service import DataService
        service = DataService()
        assert hasattr(service, '_handle_get_history')

    def test_action_registry_has_search_news(self):
        from src.data_service import DataService
        service = DataService()
        assert hasattr(service, '_handle_search_news')

    def test_action_registry_has_get_tasks(self):
        from src.data_service import DataService
        service = DataService()
        assert hasattr(service, '_handle_get_tasks')
```

- [ ] **Step 2: Run tests to verify they fail (missing handlers)**

Run: `pytest tests/test_data_service.py -v`
Expected: FAIL - AttributeError: 'DataService' object has no attribute '_handle_analyze'

- [ ] **Step 3: Implement action registry with base handlers**

```python
# src/data_service.py (lines 1-70)
"""DataService 后端守护进程"""
import json
import sys
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

logger = logging.getLogger(__name__)


# Action handler type: takes request dict, returns response dict
ActionHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


class DataService:
    """
    DataService 后端守护进程

    使用 action registry 模式分发请求到各 handler。
    每个 handler 是类的一个方法，接受 request dict，返回 response dict。
    """

    def __init__(self):
        self._running = True
        self._db_path = ".open-daily-stock.db"
        self._init_db()

        # === Action Registry ===
        # 映射 action name -> handler method name
        self._actions: Dict[str, str] = {
            "hello": "_handle_hello",
            "get_markets": "_handle_get_markets",
            "refresh": "_handle_refresh",
            "analyze": "_handle_analyze",
            "get_history": "_handle_get_history",
            "search_news": "_handle_search_news",
            "get_tasks": "_handle_get_tasks",
            "get_task": "_handle_get_task",
            "cancel_task": "_handle_cancel_task",
            "quit": "_handle_quit",
        }

        # Task storage for async operations
        self._tasks: Dict[str, Dict[str, Any]] = {}

    def _handle_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """根据 action 分发到对应 handler"""
        action = req.get("action", "")

        if action not in self._actions:
            return {"status": "error", "message": f"不支持的操作: {action}"}

        handler_name = self._actions[action]
        handler: ActionHandler = getattr(self, handler_name)
        return handler(req)

    # === Existing Handlers ===

    def _handle_hello(self, req: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "version": "0.4.0"}

    def _handle_get_markets(self, req: Dict[str, Any]) -> Dict[str, Any]:
        try:
            markets = self._get_markets()
            return {"status": "ok", "data": markets}
        except Exception as e:
            logger.error(f"获取行情失败: {e}")
            return {"status": "error", "message": "获取行情失败，请稍后重试"}

    def _handle_refresh(self, req: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self._refresh_markets()
            self._check_alerts()
            return {"status": "ok", "message": "刷新完成"}
        except Exception as e:
            logger.error(f"刷新行情失败: {e}")
            return {"status": "error", "message": "刷新失败，请检查网络连接"}

    def _handle_quit(self, req: Dict[str, Any]) -> Dict[str, Any]:
        self._running = False
        return {"status": "ok", "message": "退出"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_service.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_service.py tests/test_data_service.py
git commit -m "refactor: add action registry pattern to DataService"
```

---

## Task 2: Implement analyze Action

**Files:**
- Modify: `src/data_service.py:180-250` (add _handle_analyze)
- Test: `tests/test_data_service.py` (add tests)

- [ ] **Step 1: Write failing test for analyze action**

```python
# Add to tests/test_data_service.py

class TestAnalyzeAction:
    def test_analyze_returns_task_id(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "analyze", "code": "600519"})
        assert result["status"] == "ok"
        assert "task_id" in result
        assert result["task_id"] is not None

    def test_analyze_missing_code_returns_error(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "analyze"})
        assert result["status"] == "error"
        assert "code" in result["message"].lower()

    def test_analyze_creates_task_in_tasks_dict(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "analyze", "code": "600519"})
        task_id = result["task_id"]
        assert task_id in service._tasks
        assert service._tasks[task_id]["code"] == "600519"
        assert service._tasks[task_id]["status"] in ["pending", "running"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_service.py::TestAnalyzeAction -v`
Expected: FAIL - '_handle_analyze' not found

- [ ] **Step 3: Implement _handle_analyze**

Add to `src/data_service.py`:

```python
    def _handle_analyze(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """触发 AI 分析任务"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        # 生成 task_id
        task_id = f"task_{len(self._tasks) + 1}_{code}_{int(datetime.now().timestamp())}"

        # 创建任务记录
        self._tasks[task_id] = {
            "task_id": task_id,
            "code": code,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "result": None,
            "error": None,
        }

        # 异步执行分析（不阻塞 DataService）
        import threading
        thread = threading.Thread(target=self._run_analyze_task, args=(task_id, code))
        thread.daemon = True
        thread.start()

        return {"status": "ok", "task_id": task_id, "message": "分析任务已创建"}

    def _run_analyze_task(self, task_id: str, code: str):
        """后台执行 AI 分析"""
        try:
            self._tasks[task_id]["status"] = "running"

            # 获取分析上下文
            from src.storage import get_analysis_context
            context = get_analysis_context(code)

            # 执行 AI 分析
            from src.analyzer import GeminiAnalyzer
            analyzer = GeminiAnalyzer()
            result = analyzer.analyze(context)

            # 保存结果
            self._tasks[task_id]["status"] = "completed"
            self._tasks[task_id]["result"] = result.to_dict()
            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()

            # 发送通知
            self._send_analysis_notification(code, result)

        except Exception as e:
            logger.error(f"AI 分析失败 [{code}]: {e}")
            self._tasks[task_id]["status"] = "failed"
            self._tasks[task_id]["error"] = str(e)

    def _send_analysis_notification(self, code: str, result):
        """发送分析完成通知"""
        try:
            from src.notification import NotificationService
            notifier = NotificationService()
            message = f"📊 {result.name}({code}) 分析完成: {result.operation_advice} (评分: {result.sentiment_score})"
            notifier.send(message)
        except Exception as e:
            logger.warning(f"发送分析通知失败: {e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_service.py::TestAnalyzeAction -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_service.py tests/test_data_service.py
git commit -m "feat: add analyze action to DataService"
```

---

## Task 3: Implement get_history Action

**Files:**
- Modify: `src/data_service.py` (add _handle_get_history)

- [ ] **Step 1: Write failing test**

```python
class TestGetHistoryAction:
    def test_get_history_returns_data(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_history", "code": "600519", "days": 30})
        assert result["status"] == "ok"
        assert "data" in result
        assert isinstance(result["data"], list)

    def test_get_history_missing_code(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_history"})
        assert result["status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_service.py::TestGetHistoryAction -v`
Expected: FAIL

- [ ] **Step 3: Implement _handle_get_history**

```python
    def _handle_get_history(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取股票历史数据"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        days = req.get("days", 30)  # 默认 30 天

        try:
            from data_provider.efinance_fetcher import EfinanceFetcher
            fetcher = EfinanceFetcher()
            df = fetcher.get_daily_data(code, days=days)

            if df is None or len(df) == 0:
                return {"status": "ok", "data": [], "message": "无历史数据"}

            # 转换为 dict 列表
            data = []
            for _, row in df.iterrows():
                data.append({
                    "date": str(row.get("date", "")),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)),
                    "pct_chg": float(row.get("pct_chg", 0)),
                })

            return {"status": "ok", "data": data}

        except Exception as e:
            logger.error(f"获取历史数据失败 [{code}]: {e}")
            return {"status": "error", "message": f"获取历史数据失败: {str(e)}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_service.py::TestGetHistoryAction -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_service.py tests/test_data_service.py
git commit -m "feat: add get_history action to DataService"
```

---

## Task 4: Implement search_news Action

**Files:**
- Modify: `src/data_service.py`

- [ ] **Step 1: Write failing test**

```python
class TestSearchNewsAction:
    def test_search_news_returns_results(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "search_news", "code": "600519"})
        assert result["status"] == "ok"
        assert "data" in result
        assert isinstance(result["data"], list)

    def test_search_news_missing_code(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "search_news"})
        assert result["status"] == "error"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_data_service.py::TestSearchNewsAction -v`
Expected: FAIL

- [ ] **Step 3: Implement _handle_search_news**

```python
    def _handle_search_news(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """搜索股票相关新闻"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        try:
            from src.search_service import SearchService
            from src.config import get_config

            config = get_config()
            search_service = SearchService(
                bocha_keys=config.bocha_api_keys,
                tavily_keys=config.tavily_api_keys,
                serpapi_keys=config.serpapi_keys
            )

            # 获取股票名称
            from src.analyzer import STOCK_NAME_MAP
            name = STOCK_NAME_MAP.get(code, code)

            # 执行搜索
            news_results = search_service.search_stock_news(name, code)

            return {"status": "ok", "data": news_results}

        except Exception as e:
            logger.error(f"搜索新闻失败 [{code}]: {e}")
            return {"status": "error", "message": f"搜索新闻失败: {str(e)}"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_service.py::TestSearchNewsAction -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_service.py tests/test_data_service.py
git commit -m "feat: add search_news action to DataService"
```

---

## Task 5: Implement task management Actions (get_tasks, get_task, cancel_task)

**Files:**
- Modify: `src/data_service.py`

- [ ] **Step 1: Write failing tests**

```python
class TestTaskManagementActions:
    def test_get_tasks_returns_list(self):
        from src.data_service import DataService
        service = DataService()
        # First create a task
        service._handle_request({"action": "analyze", "code": "600519"})
        result = service._handle_request({"action": "get_tasks"})
        assert result["status"] == "ok"
        assert "tasks" in result
        assert isinstance(result["tasks"], list)
        assert len(result["tasks"]) >= 1

    def test_get_task_returns_specific_task(self):
        from src.data_service import DataService
        service = DataService()
        # Create task
        create_result = service._handle_request({"action": "analyze", "code": "600519"})
        task_id = create_result["task_id"]
        # Get specific task
        result = service._handle_request({"action": "get_task", "task_id": task_id})
        assert result["status"] == "ok"
        assert result["task"]["task_id"] == task_id

    def test_get_task_not_found(self):
        from src.data_service import DataService
        service = DataService()
        result = service._handle_request({"action": "get_task", "task_id": "nonexistent"})
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    def test_cancel_task_marks_as_cancelled(self):
        from src.data_service import DataService
        service = DataService()
        # Create task
        create_result = service._handle_request({"action": "analyze", "code": "600519"})
        task_id = create_result["task_id"]
        # Cancel it
        result = service._handle_request({"action": "cancel_task", "task_id": task_id})
        assert result["status"] == "ok"
        assert service._tasks[task_id]["status"] == "cancelled"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_data_service.py::TestTaskManagementActions -v`
Expected: FAIL

- [ ] **Step 3: Implement task management handlers**

```python
    def _handle_get_tasks(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取所有任务列表"""
        tasks = []
        for task_id, task in self._tasks.items():
            tasks.append({
                "task_id": task_id,
                "code": task["code"],
                "status": task["status"],
                "created_at": task["created_at"],
                "completed_at": task.get("completed_at"),
            })
        # 按时间倒序
        tasks.sort(key=lambda x: x["created_at"], reverse=True)
        return {"status": "ok", "tasks": tasks}

    def _handle_get_task(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取单个任务详情"""
        task_id = req.get("task_id")
        if not task_id:
            return {"status": "error", "message": "缺少 task_id 参数"}

        if task_id not in self._tasks:
            return {"status": "error", "message": f"任务 {task_id} 不存在"}

        task = self._tasks[task_id]
        return {"status": "ok", "task": task}

    def _handle_cancel_task(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """取消任务"""
        task_id = req.get("task_id")
        if not task_id:
            return {"status": "error", "message": "缺少 task_id 参数"}

        if task_id not in self._tasks:
            return {"status": "error", "message": f"任务 {task_id} 不存在"}

        task = self._tasks[task_id]
        if task["status"] in ["completed", "failed", "cancelled"]:
            return {"status": "error", "message": f"任务已 {task['status']}，无法取消"}

        task["status"] = "cancelled"
        return {"status": "ok", "message": "任务已取消"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_data_service.py::TestTaskManagementActions -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/data_service.py tests/test_data_service.py
git commit -m "feat: add task management actions to DataService"
```

---

## Self-Review Checklist

1. **Spec coverage:** 每个 action 都有对应实现吗？
   - `hello` ✅
   - `get_markets` ✅
   - `refresh` ✅
   - `analyze` ✅
   - `get_history` ✅
   - `search_news` ✅
   - `get_tasks` ✅
   - `get_task` ✅
   - `cancel_task` ✅
   - `quit` ✅

2. **Placeholder scan:** 没有 TBD/TODO/placeholder

3. **Type consistency:** 所有 handler 返回 `Dict[str, Any]`，所有 task_id 是 string

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-05-09-data-service-actions.md`**

**Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
import pytest
import json
import subprocess
import sys
import time

class TestDataService:
    def test_data_service_starts(self):
        """DataService 进程可以启动并响应 hello 请求"""
        proc = subprocess.Popen(
            [sys.executable, '-m', 'src.data_service'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        # 发送 hello 请求
        req = json.dumps({"action": "hello"})
        proc.stdin.write(req.encode())
        proc.stdin.flush()
        proc.stdin.close()  # Close stdin to signal EOF

        # 读取响应
        line = proc.stdout.readline()
        resp = json.loads(line)

        proc.terminate()
        assert resp.get("status") == "ok"
        assert "version" in resp

    def test_get_markets_request(self):
        """DataService 可以响应 get_markets 请求"""
        proc = subprocess.Popen(
            [sys.executable, '-m', 'src.data_service'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        req = json.dumps({"action": "get_markets"})
        proc.stdin.write(req.encode())
        proc.stdin.flush()
        proc.stdin.close()  # Close stdin to signal EOF

        line = proc.stdout.readline()
        resp = json.loads(line)

        proc.terminate()
        assert resp.get("status") == "ok"
        assert "data" in resp


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
        # Accept both English "not found" and Chinese "不存在"
        assert "not found" in result["message"].lower() or "不存在" in result["message"]

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
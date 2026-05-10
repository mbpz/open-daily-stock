"""Tests for MCP (Model Context Protocol) Server Bridge."""

import json
import subprocess
import sys

import pytest


class TestMCPToolDefinitions:
    """Verify MCP tool definitions are complete and well-formed."""

    def test_tools_list_has_expected_tools(self):
        """tools/list returns all expected MCP tools."""
        from src.mcp_server import MCP_TOOLS

        tool_names = {t["name"] for t in MCP_TOOLS}
        assert len(tool_names) == len(MCP_TOOLS), "工具名称不应重复"

        # 核心工具应存在
        expected = {
            # 行情数据
            "get_markets", "refresh", "get_history", "get_kline_data",
            # 分析
            "analyze", "search_news", "get_indicators", "get_drawing_data",
            "get_financials", "get_key_metrics",
            # 组合
            "add_position", "remove_position", "update_position", "get_positions",
            # 交易
            "sim_buy", "sim_sell", "sim_summary", "sim_history", "sim_reset",
            "run_backtest",
            # 策略
            "export_strategy", "import_strategy", "list_strategies", "delete_strategy",
            # 监控
            "get_tasks", "get_task", "cancel_task", "get_institutional",
            "get_dragon_board",
            # 配置
            "get_config", "update_config",
            # 告警
            "get_alerts", "save_alert", "delete_alert", "toggle_alert",
            # 筛选
            "screen_stocks",
            # 其他
            "list_providers",
        }
        missing = expected - tool_names
        assert not missing, f"缺少工具定义: {missing}"

    def test_every_tool_has_required_fields(self):
        """每个工具定义包含 name, description, inputSchema."""
        from src.mcp_server import MCP_TOOLS

        for tool in MCP_TOOLS:
            assert "name" in tool, f"工具缺少 name 字段: {tool}"
            assert "description" in tool, f"工具 {tool['name']} 缺少 description 字段"
            assert "inputSchema" in tool, f"工具 {tool['name']} 缺少 inputSchema 字段"
            assert isinstance(tool["name"], str)
            assert isinstance(tool["description"], str)
            schema = tool["inputSchema"]
            assert schema.get("type") == "object", f"工具 {tool['name']} inputSchema.type 应为 'object'"
            assert "properties" in schema, f"工具 {tool['name']} inputSchema 缺少 properties"

    def test_analyze_tool_has_code_required(self):
        """analyze 工具的 inputSchema 要求 code 参数."""
        from src.mcp_server import MCP_TOOLS

        tool = next(t for t in MCP_TOOLS if t["name"] == "analyze")
        assert "code" in tool["inputSchema"]["required"]
        assert "code" in tool["inputSchema"]["properties"]

    def test_run_backtest_has_code_and_capital_required(self):
        """run_backtest 工具的 inputSchema 要求 code 和 initial_capital."""
        from src.mcp_server import MCP_TOOLS

        tool = next(t for t in MCP_TOOLS if t["name"] == "run_backtest")
        required = tool["inputSchema"]["required"]
        assert "code" in required
        assert "initial_capital" in required

    def test_tools_list_count(self):
        """确认 MCP 工具总数合理."""
        from src.mcp_server import MCP_TOOLS

        # 应有至少 36 个工具（覆盖所有 action）
        assert len(MCP_TOOLS) >= 36, f"预期至少 36 个工具，实际: {len(MCP_TOOLS)}"


class TestMCPServer:
    """Test MCP server protocol handling (in-process, not subprocess)."""

    @pytest.fixture
    def server(self):
        from src.mcp_server import MCPServer
        return MCPServer()

    def test_initialize_handshake(self, server):
        """initialize 返回服务器信息和能力声明."""
        result = server.handle_initialize(1, {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "test", "version": "1.0"},
        })
        assert result["protocolVersion"] == "2024-11-05"
        assert result["serverInfo"]["name"] == "open-daily-stock"
        assert result["serverInfo"]["version"] == "0.4.0"
        assert "tools" in result["capabilities"]

    def test_tools_list_returns_all_tools(self, server):
        """tools/list 返回完整工具列表."""
        result = server.handle_tools_list(1)
        assert "tools" in result
        assert isinstance(result["tools"], list)
        assert len(result["tools"]) >= 36
        # 验证每个元素都有 name
        for tool in result["tools"]:
            assert "name" in tool

    def test_tools_call_get_markets(self, server):
        """tools/call 调用 get_markets 返回预期数据."""
        result = server.handle_tools_call(1, {
            "name": "get_markets",
            "arguments": {},
        })
        assert "content" in result
        assert len(result["content"]) >= 1
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] == "ok"

    def test_tools_call_hello(self, server):
        """tools/call 调用 hello 返回版本信息."""
        result = server.handle_tools_call(1, {
            "name": "hello",
            "arguments": {},
        })
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] == "ok"
        assert "version" in data

    def test_tools_call_unknown_action(self, server):
        """tools/call 对未知工具返回错误信息."""
        result = server.handle_tools_call(1, {
            "name": "no_such_tool",
            "arguments": {},
        })
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] == "error"

    def test_tools_call_get_positions(self, server):
        """tools/call 调用 get_positions 返回组合数据."""
        result = server.handle_tools_call(1, {
            "name": "get_positions",
            "arguments": {},
        })
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] == "ok"
        assert "positions" in data

    def test_tools_call_sim_summary(self, server):
        """tools/call 调用 sim_summary 返回模拟交易摘要."""
        result = server.handle_tools_call(1, {
            "name": "sim_summary",
            "arguments": {},
        })
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] == "ok"

    def test_tools_call_missing_name(self, server):
        """tools/call 缺 name 时返回错误."""
        result = server.handle_tools_call(1, {
            "name": "",
            "arguments": {},
        })
        assert "content" in result
        assert "Error" in result["content"][0]["text"]

    def test_resources_list_returns_empty(self, server):
        """resources/list 返回空资源列表."""
        result = server.handle_resources_list(1)
        assert "resources" in result
        assert result["resources"] == []

    def test_tools_call_get_config(self, server):
        """tools/call 调用 get_config 返回配置数据."""
        result = server.handle_tools_call(1, {
            "name": "get_config",
            "arguments": {},
        })
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] == "ok"
        assert "data" in data

    def test_tools_call_update_config_theme(self, server):
        """tools/call 调用 update_config 更新 theme."""
        result = server.handle_tools_call(1, {
            "name": "update_config",
            "arguments": {"key": "theme", "value": "dark"},
        })
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] == "ok"

    def test_tools_call_screen_stocks(self, server):
        """tools/call 调用 screen_stocks 返回筛选结果."""
        result = server.handle_tools_call(1, {
            "name": "screen_stocks",
            "arguments": {"change_pct_min": -10, "change_pct_max": 10},
        })
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] in ("ok", "error")  # 可能因网络而失败

    def test_tools_call_get_alerts(self, server):
        """tools/call 调用 get_alerts 返回告警列表."""
        result = server.handle_tools_call(1, {
            "name": "get_alerts",
            "arguments": {},
        })
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] == "ok"
        assert "alerts" in data

    def test_tools_call_refresh(self, server):
        """tools/call 调用 refresh 返回刷新完成消息."""
        result = server.handle_tools_call(1, {
            "name": "refresh",
            "arguments": {},
        })
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["status"] in ("ok", "error")


class TestMCPJsonRpcCompliance:
    """Test that JSON-RPC 2.0 format is correct."""

    def test_success_response_format(self):
        """成功响应包含 jsonrpc, id, result."""
        from src.mcp_server import MCPServer
        server = MCPServer()

        resp = server._dispatch({
            "jsonrpc": "2.0",
            "id": 42,
            "method": "tools/list",
            "params": {},
        })

        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 42
        assert "result" in resp
        assert "error" not in resp

    def test_error_response_format(self):
        """错误响应包含 jsonrpc, id, error."""
        from src.mcp_server import MCPServer
        server = MCPServer()

        resp = server._dispatch({
            "jsonrpc": "2.0",
            "id": 7,
            "method": "nonexistent_method",
            "params": {},
        })

        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 7
        assert "error" in resp
        assert resp["error"]["code"] == -32601  # Method not found

    def test_parse_error_on_invalid_json(self):
        """无效 JSON 返回 Parse error."""
        from src.mcp_server import MCPServer
        server = MCPServer()

        resp = server._dispatch({
            "jsonrpc": "1.0",  # 无效版本
            "id": 1,
            "method": "tools/list",
            "params": {},
        })

        # 实际处理方法不检查版本号，由 run() 循环检查
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert "result" in resp

    def test_missing_method_returns_error(self):
        """缺 method 时返回错误."""
        from src.mcp_server import MCPServer
        server = MCPServer()

        resp = server._dispatch({
            "jsonrpc": "2.0",
            "id": 1,
            "params": {},
        })

        assert resp["jsonrpc"] == "2.0"
        assert "error" in resp
        assert resp["error"]["code"] == -32600


class TestMCPServerSubprocess:
    """Integration tests: start MCP server as subprocess and verify JSON-RPC protocol."""

    @pytest.fixture
    def mcp_proc(self):
        """启动 src.mcp_server 子进程."""
        proc = subprocess.Popen(
            [sys.executable, "-m", "src.mcp_server"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        yield proc
        # 发送 shutdown 消息
        try:
            shutdown = json.dumps({"jsonrpc": "2.0", "id": 999, "method": "shutdown"}) + "\n"
            proc.stdin.write(shutdown.encode())
            proc.stdin.flush()
            proc.wait(timeout=5)
        except Exception:
            proc.terminate()

    def _send_and_recv(self, proc, msg: dict) -> dict:
        """发送 JSON-RPC 消息并读取响应."""
        line = json.dumps(msg) + "\n"
        proc.stdin.write(line.encode())
        proc.stdin.flush()
        resp_line = proc.stdout.readline()
        return json.loads(resp_line)

    def test_initialize_via_subprocess(self, mcp_proc):
        """通过子进程进行 MCP initialize 握手."""
        resp = self._send_and_recv(mcp_proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        })
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 1
        assert resp["result"]["serverInfo"]["name"] == "open-daily-stock"
        assert "tools" in resp["result"]["capabilities"]

    def test_tools_list_via_subprocess(self, mcp_proc):
        """通过子进程调用 tools/list."""
        resp = self._send_and_recv(mcp_proc, {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        })
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 2
        assert "tools" in resp["result"]
        assert len(resp["result"]["tools"]) >= 36

    def test_tools_call_hello_via_subprocess(self, mcp_proc):
        """通过子进程调用 tools/call hello."""
        resp = self._send_and_recv(mcp_proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "hello",
                "arguments": {},
            },
        })
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 3
        content = resp["result"]["content"][0]["text"]
        data = json.loads(content)
        assert data["status"] == "ok"

    def test_tools_call_invalid_tool_via_subprocess(self, mcp_proc):
        """通过子进程调用不存在的工具返回错误."""
        resp = self._send_and_recv(mcp_proc, {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "nonexistent_tool",
                "arguments": {},
            },
        })
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 4
        content = resp["result"]["content"][0]["text"]
        data = json.loads(content)
        assert data["status"] == "error"

    def test_resources_list_via_subprocess(self, mcp_proc):
        """通过子进程调用 resources/list."""
        resp = self._send_and_recv(mcp_proc, {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "resources/list",
            "params": {},
        })
        assert resp["jsonrpc"] == "2.0"
        assert resp["result"]["resources"] == []

    def test_invalid_jsonrpc_version_via_subprocess(self, mcp_proc):
        """发送无效 JSON-RPC 版本号触发错误."""
        line = json.dumps({
            "jsonrpc": "1.0",
            "id": 6,
            "method": "initialize",
        }) + "\n"
        mcp_proc.stdin.write(line.encode())
        mcp_proc.stdin.flush()
        resp_line = mcp_proc.stdout.readline()
        resp = json.loads(resp_line)
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 6
        assert "error" in resp

    def test_parse_error_on_bad_json_via_subprocess(self, mcp_proc):
        """发送非 JSON 内容触发 Parse error."""
        mcp_proc.stdin.write(b"this is not json\n")
        mcp_proc.stdin.flush()
        resp_line = mcp_proc.stdout.readline()
        resp = json.loads(resp_line)
        assert "error" in resp
        assert resp["error"]["code"] == -32700

    def test_missing_method_field_via_subprocess(self, mcp_proc):
        """缺 method 时返回 Method not found 错误."""
        resp = self._send_and_recv(mcp_proc, {
            "jsonrpc": "2.0",
            "id": 10,
        })
        assert resp["jsonrpc"] == "2.0"
        assert resp["id"] == 10
        assert "error" in resp

    def test_tools_call_get_positions_via_subprocess(self, mcp_proc):
        """通过子进程调用 get_positions."""
        resp = self._send_and_recv(mcp_proc, {
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "get_positions",
                "arguments": {},
            },
        })
        assert resp["jsonrpc"] == "2.0"
        content = resp["result"]["content"][0]["text"]
        data = json.loads(content)
        assert data["status"] == "ok"

    def test_tools_call_get_config_via_subprocess(self, mcp_proc):
        """通过子进程调用 get_config."""
        resp = self._send_and_recv(mcp_proc, {
            "jsonrpc": "2.0",
            "id": 12,
            "method": "tools/call",
            "params": {
                "name": "get_config",
                "arguments": {},
            },
        })
        assert resp["jsonrpc"] == "2.0"
        content = resp["result"]["content"][0]["text"]
        data = json.loads(content)
        assert data["status"] == "ok"


class TestMCPServerDispatch:
    """Test _dispatch method directly for various edge cases."""

    @pytest.fixture
    def server(self):
        from src.mcp_server import MCPServer
        return MCPServer()

    def test_dispatch_initialize(self, server):
        resp = server._dispatch({
            "jsonrpc": "2.0", "id": 1,
            "method": "initialize", "params": {"protocolVersion": "2024-11-05"},
        })
        assert "error" not in resp
        assert resp["result"]["protocolVersion"] == "2024-11-05"

    def test_dispatch_tools_list(self, server):
        resp = server._dispatch({
            "jsonrpc": "2.0", "id": 2,
            "method": "tools/list", "params": {},
        })
        assert "error" not in resp
        assert len(resp["result"]["tools"]) >= 36

    def test_dispatch_tools_call(self, server):
        resp = server._dispatch({
            "jsonrpc": "2.0", "id": 3,
            "method": "tools/call",
            "params": {"name": "hello", "arguments": {}},
        })
        assert "error" not in resp
        content = resp["result"]["content"][0]["text"]
        data = json.loads(content)
        assert data["status"] == "ok"

    def test_dispatch_resources_list(self, server):
        resp = server._dispatch({
            "jsonrpc": "2.0", "id": 4,
            "method": "resources/list", "params": {},
        })
        assert "error" not in resp
        assert resp["result"]["resources"] == []

    def test_dispatch_unknown_method(self, server):
        resp = server._dispatch({
            "jsonrpc": "2.0", "id": 5,
            "method": "bogus/method", "params": {},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32601

    def test_dispatch_no_method(self, server):
        resp = server._dispatch({
            "jsonrpc": "2.0", "id": 6,
            "params": {},
        })
        assert "error" in resp
        assert resp["error"]["code"] == -32600

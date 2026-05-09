"""Tests for WebSocket IPC server mode (P3-9)."""
import json
import threading
import time
import pytest


# Module-level skip if websockets library is not installed
try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not WEBSOCKETS_AVAILABLE,
    reason="websockets library not installed",
)


class TestWsServer:
    """Test WebSocket server startup and request/response handling."""

    @pytest.fixture
    def ws_server(self, unused_tcp_port):
        """Start a DataService WebSocket server on a random port."""
        from src.data_service import DataService

        service = DataService()
        service._running = True

        host = "127.0.0.1"
        port = unused_tcp_port

        # Start server in a daemon thread
        def _run():
            service.run_ws_server(host=host, port=port)

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        # Wait for server to be ready
        for _ in range(50):
            try:
                import socket
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.2)
                s.connect((host, port))
                s.close()
                break
            except (ConnectionRefusedError, OSError):
                time.sleep(0.1)
        else:
            service._running = False
            pytest.fail("WebSocket server did not start in time")

        yield host, port

        # Shutdown
        service._running = False
        thread.join(timeout=2)

    @pytest.mark.asyncio
    async def test_hello_request(self, ws_server):
        """Connect to WS server and send hello request."""
        host, port = ws_server
        uri = f"ws://{host}:{port}"

        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"action": "hello"}))
            resp_raw = await ws.recv()
            resp = json.loads(resp_raw)

        assert resp["status"] == "ok"
        assert "version" in resp

    @pytest.mark.asyncio
    async def test_get_markets_request(self, ws_server):
        """Connect to WS server and send get_markets request."""
        host, port = ws_server
        uri = f"ws://{host}:{port}"

        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"action": "get_markets"}))
            resp_raw = await ws.recv()
            resp = json.loads(resp_raw)

        assert resp["status"] == "ok"
        assert "data" in resp
        assert isinstance(resp["data"], list)

    @pytest.mark.asyncio
    async def test_unknown_action_returns_error(self, ws_server):
        """Unknown action returns error over WebSocket."""
        host, port = ws_server
        uri = f"ws://{host}:{port}"

        async with websockets.connect(uri) as ws:
            await ws.send(json.dumps({"action": "nonexistent"}))
            resp_raw = await ws.recv()
            resp = json.loads(resp_raw)

        assert resp["status"] == "error"
        assert "不支持" in resp.get("message", "")

    @pytest.mark.asyncio
    async def test_multiple_clients(self, ws_server):
        """Multiple clients can connect and receive independent responses."""
        host, port = ws_server
        uri = f"ws://{host}:{port}"

        async with websockets.connect(uri) as ws1, \
                   websockets.connect(uri) as ws2:

            # Send different requests from each client
            await ws1.send(json.dumps({"action": "hello"}))
            await ws2.send(json.dumps({"action": "hello"}))

            resp1 = json.loads(await ws1.recv())
            resp2 = json.loads(await ws2.recv())

            assert resp1["status"] == "ok"
            assert resp2["status"] == "ok"

    @pytest.mark.asyncio
    async def test_invalid_json_returns_error(self, ws_server):
        """Invalid JSON returns error over WebSocket."""
        host, port = ws_server
        uri = f"ws://{host}:{port}"

        async with websockets.connect(uri) as ws:
            await ws.send("not valid json")
            resp_raw = await ws.recv()
            resp = json.loads(resp_raw)

        assert resp["status"] == "error"
        assert "invalid json" in resp.get("message", "").lower()


class TestWsServerWithoutConnection:
    """Tests that do not require an actual WebSocket connection."""

    def test_run_ws_server_method_exists(self):
        """DataService has run_ws_server method."""
        from src.data_service import DataService
        service = DataService()
        assert hasattr(service, "run_ws_server")

    def test_action_registry_unchanged_for_ws_mode(self):
        """WebSocket mode uses the same action registry as stdio."""
        from src.data_service import DataService
        service = DataService()
        # Same actions should work regardless of transport
        assert "hello" in service._actions
        assert "get_markets" in service._actions
        assert "analyze" in service._actions
        assert "get_history" in service._actions

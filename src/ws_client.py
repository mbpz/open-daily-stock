"""
WebSocket client for streaming communication with DataService.

Provides an async client that connects to the DataService WebSocket
server and streams analysis results token-by-token. Used by both the
TUI (Textual) and GUI (Flet) frontends for reduced perceived latency.

P7-2: Added automatic reconnection with exponential backoff,
      targeted push support, and connection health monitoring.

Usage (TUI / asyncio context):
    client = WsClient()
    await client.connect()
    async for event in client.analyze_stream("600519"):
        if event["type"] == "stream_chunk":
            view.append_stream_chunk(event["chunk"])
        elif event["type"] == "stream_done":
            view.finish_stream(event["result"])
    await client.close()
"""

import asyncio
import json
import logging
import time
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

# Default DataService WebSocket address (matches config default)
DEFAULT_WS_HOST = "127.0.0.1"
DEFAULT_WS_PORT = 9876
MAX_RECONNECT_ATTEMPTS = 10
BASE_RECONNECT_DELAY = 1.0  # seconds
MAX_RECONNECT_DELAY = 30.0  # seconds


class WsClient:
    """Async WebSocket client for DataService streaming API.

    Connects to the DataService WebSocket IPC server and provides
    a high-level `analyze_stream()` method that yields streaming
    analysis events.

    P7-2: Supports automatic reconnection with exponential backoff.
    """

    def __init__(
        self,
        host: str = DEFAULT_WS_HOST,
        port: int = DEFAULT_WS_PORT,
        auto_reconnect: bool = True,
        max_retries: int = MAX_RECONNECT_ATTEMPTS,
    ):
        self.uri = f"ws://{host}:{port}"
        self._ws: Optional[any] = None
        self._auto_reconnect = auto_reconnect
        self._max_retries = max_retries
        self._reconnect_count = 0
        self._connected = False

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Establish WebSocket connection to DataService with retry.

        Returns:
            True if connected, False after exhausting all retries.
        """
        import websockets

        for attempt in range(1, self._max_retries + 1):
            try:
                self._ws = await websockets.connect(
                    self.uri,
                    ping_interval=20,
                    ping_timeout=10,
                    close_timeout=5,
                )
                self._connected = True
                self._reconnect_count = 0
                logger.info(f"WsClient connected to DataService at {self.uri} (attempt {attempt})")
                return True
            except (OSError, asyncio.TimeoutError) as e:
                if attempt < self._max_retries and self._auto_reconnect:
                    delay = min(
                        BASE_RECONNECT_DELAY * (2 ** (attempt - 1)),
                        MAX_RECONNECT_DELAY,
                    )
                    logger.warning(
                        f"WsClient connection failed (attempt {attempt}/{self._max_retries}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"WsClient connection failed after {attempt} attempts: {e}")
                    self._connected = False
                    return False
        return False

    async def reconnect(self) -> bool:
        """Force a reconnection, closing existing connection first."""
        await self.close()
        self._reconnect_count += 1
        return await self.connect()

    async def is_connected(self) -> bool:
        """Check if the WebSocket connection is alive."""
        if self._ws is None:
            return False
        try:
            # Lightweight ping to check connection
            pong_waiter = await self._ws.ping()
            await asyncio.wait_for(pong_waiter, timeout=5)
            return True
        except Exception:
            return False

    async def ensure_connected(self) -> bool:
        """Ensure connection is active; reconnect if needed."""
        if not await self.is_connected():
            logger.info("WsClient connection lost, reconnecting...")
            return await self.reconnect()
        return True

    # ------------------------------------------------------------------
    # Request / Response
    # ------------------------------------------------------------------

    async def request(self, action: str, **params) -> dict:
        """Send a request and wait for a single response.

        Args:
            action: Action name (e.g. "hello", "get_markets").
            **params: Additional request parameters.

        Returns:
            Response dict from DataService.
        """
        await self.ensure_connected()

        payload = {"action": action, **params}
        await self._ws.send(json.dumps(payload))
        raw = await self._ws.recv()
        return json.loads(raw)

    # ------------------------------------------------------------------
    # Streaming
    # ------------------------------------------------------------------

    async def analyze_stream(self, code: str) -> AsyncIterator[dict]:
        """Stream analysis results for a stock code.

        Sends an analyze_stream request and yields events as they arrive.
        The stream ends after a stream_done or stream_error event.

        Event types yielded:
          {"type": "stream_start", "task_id": ..., "code": ...}
          {"type": "stream_chunk", "chunk": "partial text..."}
          {"type": "stream_done", "task_id": ..., "result": {...}}
          {"type": "stream_error", "task_id": ..., "message": "..."}

        Args:
            code: Stock code to analyze (e.g. "600519")

        Yields:
            dict: One streaming event per message from the server
        """
        await self.ensure_connected()

        await self._ws.send(json.dumps({"action": "analyze_stream", "code": code}))

        async for raw_msg in self._ws:
            try:
                event = json.loads(raw_msg)
                yield event
                if event.get("type") in ("stream_done", "stream_error"):
                    break
            except json.JSONDecodeError:
                logger.warning(f"WsClient received invalid JSON: {str(raw_msg)[:100]}")
                continue

    # ------------------------------------------------------------------
    # Listen (for push events)
    # ------------------------------------------------------------------

    async def listen(self) -> AsyncIterator[dict]:
        """Listen for server-pushed events (market updates, alerts, etc.).

        Yields each push event as a dict. Never terminates unless
        connection is lost. Use for background listeners.

        Event types:
          {"type": "market_update", "data": [...]}
          {"type": "alert_triggered", ...}
        """
        await self.ensure_connected()

        async for raw_msg in self._ws:
            try:
                event = json.loads(raw_msg)
                yield event
            except json.JSONDecodeError:
                logger.warning(f"WsClient received invalid JSON: {str(raw_msg)[:100]}")
                continue
            except Exception:
                break

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------

    async def hello(self) -> dict:
        """Test connectivity by sending a hello request.

        Returns:
            dict: {"status": "ok", "version": "..."}
        """
        return await self.request("hello")

    async def get_markets(self) -> dict:
        """Get current market data."""
        return await self.request("get_markets")

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None
            self._connected = False
            logger.info("WsClient disconnected")

"""
WebSocket client for streaming communication with DataService.

Provides an async client that connects to the DataService WebSocket
server and streams analysis results token-by-token. Used by both the
TUI (Textual) and GUI (Flet) frontends for reduced perceived latency.

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
from typing import AsyncIterator, Optional

logger = logging.getLogger(__name__)

# Default DataService WebSocket address (matches config default)
DEFAULT_WS_HOST = "127.0.0.1"
DEFAULT_WS_PORT = 9876


class WsClient:
    """Async WebSocket client for DataService streaming API.

    Connects to the DataService WebSocket IPC server and provides
    a high-level `analyze_stream()` method that yields streaming
    analysis events.
    """

    def __init__(self, host: str = DEFAULT_WS_HOST, port: int = DEFAULT_WS_PORT):
        self.uri = f"ws://{host}:{port}"
        self._ws: Optional[any] = None

    async def connect(self) -> None:
        """Establish WebSocket connection to DataService.

        Raises:
            ImportError: if websockets library is not installed
            OSError: if connection is refused (server not running)
        """
        import websockets

        self._ws = await websockets.connect(self.uri)
        logger.info(f"WsClient connected to DataService at {self.uri}")

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
        if self._ws is None:
            await self.connect()

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

    async def hello(self) -> dict:
        """Test connectivity by sending a hello request.

        Returns:
            dict: {"status": "ok", "version": "..."}
        """
        if self._ws is None:
            await self.connect()

        await self._ws.send(json.dumps({"action": "hello"}))
        raw = await self._ws.recv()
        return json.loads(raw)

    async def close(self) -> None:
        """Close the WebSocket connection."""
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
            logger.info("WsClient disconnected")

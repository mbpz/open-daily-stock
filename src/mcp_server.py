"""
MCP (Model Context Protocol) Server Bridge for open-daily-stock.

Wraps DataService actions as MCP tools, allowing AI agents (e.g., Claude Code)
to directly call open-daily-stock for stock data, analysis, and backtesting.

Protocol: JSON-RPC 2.0 over stdio (line-delimited JSON)
"""

from __future__ import annotations

import json
import sys
import logging
from typing import Any, Dict, List, Optional

from .data_service import DataService
from .mcp_tools import MCP_TOOLS

logger = logging.getLogger(__name__)


class MCPServer:
    """
    Minimal MCP JSON-RPC server that bridges DataService actions to MCP tools.

    Protocol: JSON-RPC 2.0 over stdio.
    Each line on stdin is a JSON-RPC request.
    Each line on stdout is a JSON-RPC response.

    Handled methods:
      - initialize: MCP handshake, returns server capabilities
      - tools/list: Returns all MCP tool definitions
      - tools/call: Calls a tool by dispatching to DataService._handle_request
      - resources/list: Returns available MCP resources (empty for now)
    """

    def __init__(self):
        self._service = DataService()
        self._initialized = False
        self._server_info = {
            "name": "open-daily-stock",
            "version": "0.4.0",
        }
        self._capabilities = {
            "tools": {},
        }

    def _send_response(self, id_val: Any, result: Any = None, error: Any = None) -> None:
        """Send a JSON-RPC 2.0 response to stdout."""
        response = {"jsonrpc": "2.0", "id": id_val}
        if error is not None:
            response["error"] = error
        else:
            response["result"] = result
        try:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, default=str) + "\n")
            sys.stdout.flush()
        except BrokenPipeError:
            sys.exit(0)

    def _send_notification(self, method: str, params: dict = None) -> None:
        """Send a JSON-RPC 2.0 notification (no id field)."""
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        try:
            sys.stdout.write(json.dumps(msg, ensure_ascii=False, default=str) + "\n")
            sys.stdout.flush()
        except BrokenPipeError:
            sys.exit(0)

    def _make_jsonrpc_error(self, code: int, message: str, id_val: Any = None) -> Dict[str, Any]:
        """Build a JSON-RPC error object."""
        return {
            "jsonrpc": "2.0",
            "id": id_val,
            "error": {
                "code": code,
                "message": message,
            },
        }

    # ============================================================
    # MCP Method Handlers
    # ============================================================

    def handle_initialize(self, id_val: Any, params: dict) -> dict:
        """Handle the MCP initialize handshake."""
        client_info = params.get("clientInfo", {}) if params else {}
        logger.info(f"MCP initialized by client: {client_info.get('name', 'unknown')} v{client_info.get('version', '?')}")
        self._initialized = True
        return {
            "protocolVersion": "2024-11-05",
            "serverInfo": self._server_info,
            "capabilities": self._capabilities,
        }

    def handle_tools_list(self, id_val: Any, params: dict = None) -> dict:
        """Handle tools/list: return all MCP tool definitions."""
        return {"tools": MCP_TOOLS}

    def handle_tools_call(self, id_val: Any, params: dict) -> dict:
        """Handle tools/call: execute a DataService action and return the result."""
        if not params:
            return {"content": [{"type": "text", "text": "Error: missing params"}]}

        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not tool_name:
            return {"content": [{"type": "text", "text": "Error: missing tool name"}]}

        logger.info(f"MCP tools/call: {tool_name} with args={arguments}")

        # Build the internal request format expected by DataService
        req = {"action": tool_name}
        req.update(arguments)

        try:
            result = self._service._handle_request(req)
        except Exception as e:
            logger.error(f"Tool call '{tool_name}' failed: {e}")
            return {"content": [{"type": "text", "text": f"Error executing {tool_name}: {str(e)}"}]}

        # Format result as MCP content response
        try:
            text = json.dumps(result, ensure_ascii=False, default=str, indent=2)
        except (TypeError, ValueError):
            text = str(result)

        return {"content": [{"type": "text", "text": text}]}

    def handle_resources_list(self, id_val: Any, params: dict = None) -> dict:
        """Handle resources/list: return available MCP resources."""
        return {"resources": []}

    # ============================================================
    # JSON-RPC Dispatch
    # ============================================================

    def _dispatch(self, msg: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Dispatch a JSON-RPC message to the appropriate handler.

        Returns a response dict for requests (has 'id'), or None for notifications.
        """
        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if not method:
            return self._jsonrpc_error(-32600, "Missing method", msg_id)

        handlers = {
            "initialize": self.handle_initialize,
            "tools/list": self.handle_tools_list,
            "tools/call": self.handle_tools_call,
            "resources/list": self.handle_resources_list,
        }

        handler = handlers.get(method)
        if handler is None:
            return self._jsonrpc_error(-32601, f"Method not found: {method}", msg_id)

        try:
            result = handler(msg_id, params)
            if isinstance(result, dict) and "jsonrpc" in result:
                # Already a JSON-RPC response (error case)
                return result
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}
        except Exception as e:
            logger.exception(f"Error handling method '{method}': {e}")
            return self._jsonrpc_error(-32603, f"Internal error: {str(e)}", msg_id)

    def _jsonrpc_error(self, code: int, message: str, msg_id: Any = None) -> Dict[str, Any]:
        """Build a JSON-RPC error response."""
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {
                "code": code,
                "message": message,
            },
        }

    # ============================================================
    # Main Run Loop
    # ============================================================

    def run(self) -> int:
        """
        Main loop: read JSON-RPC messages from stdin, dispatch, write responses to stdout.

        Runs until stdin closes or a shutdown notification is received.
        """
        logger.info("MCP Server starting (open-daily-stock v0.4.0)")
        logger.info("Ready to accept MCP JSON-RPC requests on stdin")

        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                error_resp = self._jsonrpc_error(-32700, "Parse error")
                self._send_response(error_resp.get("id"), error=error_resp.get("error"))
                continue

            # Validate JSON-RPC version
            if msg.get("jsonrpc") != "2.0":
                error_resp = self._jsonrpc_error(-32600, "Invalid JSON-RPC version", msg.get("id"))
                self._send_response(error_resp.get("id"), error=error_resp.get("error"))
                continue

            # Check for shutdown
            if msg.get("method") == "shutdown":
                self._send_response(msg.get("id"), result=None)
                break

            # Dispatch
            try:
                response = self._dispatch(msg)
                if response is not None:
                    # Must have an id (was a request, not a notification)
                    rid = response.get("id")
                    if "error" in response:
                        self._send_response(rid, error=response["error"])
                    else:
                        self._send_response(rid, result=response["result"])
            except Exception as e:
                logger.exception(f"Unhandled error in dispatch: {e}")
                self._send_response(msg.get("id"), error={
                    "code": -32603,
                    "message": f"Internal error: {str(e)}",
                })

        logger.info("MCP Server stopped")
        return 0


# ============================================================
# Module-level entry point
# ============================================================

def main():
    """Entry point for `python -m src.mcp_server`."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        stream=sys.stderr,  # MCP protocol goes on stdout, logs go to stderr
    )
    server = MCPServer()
    return server.run()


if __name__ == "__main__":
    sys.exit(main())

"""ServiceClient - TUI/GUI 与 DataService 通信的客户端库"""
import json
import subprocess
import sys
import time
from typing import Dict, Any, List, Optional


class ServiceClientError(Exception):
    """Raised when DataService communication fails irrecoverably."""


class ServiceClient:
    """客户端与 DataService 通信

    设计要点：
    - 默认 30s read timeout，避免 DataService 崩溃后永久挂起
    - 单次失败自动重启 DataService 并重试一次
    - 进程管理在 quit()/__del__/上下文管理器三处统一收口
    """

    DEFAULT_TIMEOUT = 30.0
    MAX_RESTART_ATTEMPTS = 1
    RESTART_BACKOFF_SECONDS = 0.5

    def __init__(self, timeout: Optional[float] = None):
        self._timeout = timeout if timeout is not None else self.DEFAULT_TIMEOUT
        self._proc = self._spawn()

    def _spawn(self) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-m", "src.data_service"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def _is_alive(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def _ensure_alive(self) -> None:
        if self._is_alive():
            return
        # Stale handle; respawn.
        self._proc = self._spawn()

    def _read_line_with_timeout(self) -> str:
        """Block on stdout for one line, but enforce a wall-clock timeout.

        Uses a background reader thread because Popen.stdout is not
        interruptible in a portable way. The thread is joined on every
        code path, so it never leaks.
        """
        import threading
        result: Dict[str, Any] = {"line": None, "error": None}

        def _reader() -> None:
            try:
                result["line"] = self._proc.stdout.readline()
            except Exception as e:  # noqa: BLE001
                result["error"] = e

        reader = threading.Thread(target=_reader, daemon=True)
        reader.start()
        reader.join(timeout=self._timeout)
        if reader.is_alive():
            # Process is stuck; terminate and surface timeout.
            try:
                self._proc.terminate()
            except Exception:
                pass
            raise ServiceClientError(
                f"DataService did not respond within {self._timeout}s"
            )
        if result["error"] is not None:
            raise ServiceClientError(f"stdout read failed: {result['error']}")
        if not result["line"]:
            # EOF: process likely crashed.
            stderr = ""
            try:
                stderr = self._proc.stderr.read().decode("utf-8", errors="replace")[-500:]
            except Exception:
                pass
            raise ServiceClientError(
                f"DataService closed stdout unexpectedly. stderr: {stderr}"
            )
        return result["line"]

    def _send_request(self, action: str, data: Optional[Dict] = None) -> Dict:
        """发送请求到 DataService。失败时自动重启并重试一次。"""
        req: Dict[str, Any] = {"action": action}
        if data:
            req.update(data)
        payload = (json.dumps(req) + "\n").encode("utf-8")

        last_error: Optional[Exception] = None
        for attempt in range(self.MAX_RESTART_ATTEMPTS + 1):
            try:
                self._ensure_alive()
                self._proc.stdin.write(payload)
                self._proc.stdin.flush()
                line = self._read_line_with_timeout()
                return json.loads(line)
            except (ServiceClientError, BrokenPipeError, ValueError) as e:
                last_error = e
                # Best-effort cleanup before respawn.
                try:
                    if self._proc is not None and self._proc.poll() is None:
                        self._proc.terminate()
                except Exception:
                    pass
                if attempt < self.MAX_RESTART_ATTEMPTS:
                    time.sleep(self.RESTART_BACKOFF_SECONDS)
                    self._proc = self._spawn()
                    continue
                break

        raise ServiceClientError(
            f"action={action!r} failed after {self.MAX_RESTART_ATTEMPTS + 1} attempts: {last_error}"
        )

    def hello(self) -> Dict[str, Any]:
        """测试连接，返回版本"""
        return self._send_request("hello")

    def get_markets(self) -> List[Dict]:
        """获取行情数据"""
        resp = self._send_request("get_markets")
        return resp.get("data", [])

    def refresh(self) -> bool:
        """刷新行情数据"""
        resp = self._send_request("refresh")
        return resp.get("status") == "ok"

    def get_market_review(self, force: bool = False) -> Dict[str, Any]:
        """Generate market review report (P6-2)."""
        return self._send_request("get_market_review", {"force": force})

    def get_market_reviews_history(self, limit: int = 10) -> Dict[str, Any]:
        """Get historical market review reports (P6-2)."""
        return self._send_request("get_market_reviews_history", {"limit": limit})

    def analyze(self, code: str) -> Dict[str, Any]:
        """分析股票"""
        return self._send_request("analyze", {"code": code})

    def deep_analyze(self, code: str, agents: Optional[List[str]] = None) -> Dict[str, Any]:
        """深度分析股票（多 Agent 模式）

        Args:
            code: 股票代码
            agents: 启用的专家代理列表，如 ["technical", "fundamental", "news"]
        """
        data = {"code": code}
        if agents:
            data["deep_analysis_agents"] = ",".join(agents)
        return self._send_request("deep_analyze", data)

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return self._send_request("get_config")

    def update_config(self, config: Dict) -> bool:
        """更新配置"""
        resp = self._send_request("update_config", {"data": config})
        return resp.get("status") == "ok"

    def quit(self) -> None:
        """关闭 DataService"""
        try:
            if self._is_alive():
                try:
                    self._send_request("quit")
                except Exception:
                    # best-effort; we are tearing down anyway
                    pass
        finally:
            if self._proc is not None:
                try:
                    self._proc.terminate()
                except Exception:
                    pass
                self._proc = None

    def __enter__(self) -> "ServiceClient":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.quit()

    def __del__(self) -> None:
        """析构时确保进程关闭"""
        try:
            self.quit()
        except Exception:
            pass

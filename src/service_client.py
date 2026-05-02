"""ServiceClient - TUI/GUI 与 DataService 通信的客户端库"""
import json
import subprocess
import sys
from typing import Dict, Any, List, Optional

class ServiceClient:
    """客户端与 DataService 通信"""

    def __init__(self):
        self._proc = subprocess.Popen(
            [sys.executable, '-m', 'src.data_service'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def _send_request(self, action: str, data: Optional[Dict] = None) -> Dict:
        """发送请求到 DataService"""
        req = {"action": action}
        if data:
            req.update(data)

        self._proc.stdin.write(json.dumps(req).encode())
        self._proc.stdin.flush()

        line = self._proc.stdout.readline()
        return json.loads(line)

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

    def analyze(self, code: str) -> Dict[str, Any]:
        """分析股票"""
        return self._send_request("analyze", {"code": code})

    def get_config(self) -> Dict[str, Any]:
        """获取配置"""
        return self._send_request("get_config")

    def update_config(self, config: Dict) -> bool:
        """更新配置"""
        resp = self._send_request("update_config", {"data": config})
        return resp.get("status") == "ok"

    def quit(self):
        """关闭 DataService"""
        try:
            self._send_request("quit")
        except:
            pass
        self._proc.terminate()

    def __del__(self):
        """析构时确保进程关闭"""
        if hasattr(self, '_proc') and self._proc:
            self.quit()
"""DataService 后端守护进程"""
import json
import sys
import sqlite3
from datetime import datetime
from typing import Dict, Any, List

class DataService:
    def __init__(self):
        self._running = True
        self._db_path = ".open-daily-stock.db"
        self._init_db()

    def _init_db(self):
        """初始化 SQLite 数据库"""
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS markets (
                code TEXT PRIMARY KEY,
                name TEXT,
                price REAL,
                change_pct REAL,
                volume INTEGER,
                updated_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def _send(self, data: Dict[str, Any]):
        """发送 JSON 到 stdout"""
        print(json.dumps(data), flush=True)

    def _handle_request(self, req: Dict[str, Any]):
        """处理请求"""
        action = req.get("action", "")

        if action == "hello":
            self._send({"status": "ok", "version": "0.3.0"})
        elif action == "get_markets":
            markets = self._get_markets()
            self._send({"status": "ok", "data": markets})
        elif action == "refresh":
            self._refresh_markets()
            self._send({"status": "ok", "message": "refreshed"})
        elif action == "quit":
            self._running = False
        else:
            self._send({"status": "error", "message": f"unknown action: {action}"})

    def _get_markets(self) -> List[Dict]:
        """从数据库获取行情数据"""
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        c.execute("SELECT code, name, price, change_pct, volume FROM markets")
        rows = c.fetchall()
        conn.close()
        return [{"code": r[0], "name": r[1], "price": r[2], "change_pct": r[3], "volume": r[4]} for r in rows]

    def _refresh_markets(self):
        """刷新行情数据（TODO: 调用 AkShare/YFinance）"""
        pass

    def run(self):
        """主循环：读取 stdin，处理请求"""
        while self._running:
            line = sys.stdin.readline()
            if not line:
                break
            try:
                req = json.loads(line)
                self._handle_request(req)
            except json.JSONDecodeError:
                self._send({"status": "error", "message": "invalid json"})
            except Exception as e:
                self._send({"status": "error", "message": str(e)})

if __name__ == "__main__":
    service = DataService()
    service.run()
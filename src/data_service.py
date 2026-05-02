"""DataService 后端守护进程"""
import json
import sys
import sqlite3
from datetime import datetime
from typing import Dict, Any, List

from .config import get_config

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
        """刷新行情数据"""
        from data_provider.efinance_fetcher import EfinanceFetcher

        # 使用 EfinanceFetcher 作为主要数据源
        fetcher = EfinanceFetcher()

        # 获取配置中的股票列表
        config = get_config()
        stocks = config.stock_list

        for stock in stocks:
            try:
                # 获取日线数据
                df = fetcher.get_daily_data(stock, days=1)
                if df is not None and len(df) > 0:
                    latest = df.iloc[-1]
                    self._save_market({
                        "code": stock,
                        "name": latest.get("name", ""),
                        "price": latest.get("close", 0),
                        "change_pct": latest.get("pct_chg", 0),
                        "volume": latest.get("volume", 0),
                    })
            except Exception as e:
                print(f"Failed to fetch {stock}: {e}", file=sys.stderr)

    def _save_market(self, market: Dict):
        """保存行情到数据库"""
        conn = sqlite3.connect(self._db_path)
        c = conn.cursor()
        c.execute("""
            INSERT OR REPLACE INTO markets (code, name, price, change_pct, volume, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (market["code"], market["name"], market["price"],
              market["change_pct"], market["volume"], datetime.now().isoformat()))
        conn.commit()
        conn.close()

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
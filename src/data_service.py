"""DataService 后端守护进程"""
import json
import sys
import sqlite3
import logging
from datetime import datetime
from typing import Dict, Any, List

from .config import get_config
from .alert_service import AlertService

logger = logging.getLogger(__name__)

class DataService:
    def __init__(self):
        self._running = True
        self._db_path = ".open-daily-stock.db"
        self._init_db()
        self._alert_service = AlertService()

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
            try:
                markets = self._get_markets()
                self._send({"status": "ok", "data": markets})
            except Exception as e:
                logger.error(f"获取行情失败: {e}")
                self._send({"status": "error", "message": "获取行情失败，请稍后重试"})
        elif action == "refresh":
            try:
                self._refresh_markets()
                self._check_alerts()
                self._send({"status": "ok", "message": "刷新完成"})
            except Exception as e:
                logger.error(f"刷新行情失败: {e}")
                self._send({"status": "error", "message": "刷新失败，请检查网络连接"})
        elif action == "quit":
            self._running = False
        else:
            self._send({"status": "error", "message": f"不支持的操作: {action}"})

    def _get_markets(self) -> List[Dict]:
        """从数据库获取行情数据"""
        try:
            conn = sqlite3.connect(self._db_path)
            c = conn.cursor()
            c.execute("SELECT code, name, price, change_pct, volume FROM markets")
            rows = c.fetchall()
            conn.close()
            return [{"code": r[0], "name": r[1], "price": r[2], "change_pct": r[3], "volume": r[4]} for r in rows]
        except Exception as e:
            logger.error(f"获取行情数据失败: {e}")
            return []

    def _refresh_markets(self):
        """刷新行情数据"""
        from data_provider.efinance_fetcher import EfinanceFetcher

        # 使用 EfinanceFetcher 作为主要数据源
        fetcher = EfinanceFetcher()

        # 获取配置中的股票列表
        config = get_config()
        stocks = config.stock_list

        success_count = 0
        fail_count = 0
        errors = []

        for stock in stocks:
            try:
                # 获取日线数据
                df = fetcher.get_daily_data(stock, days=1)
                if df is not None and len(df) > 0:
                    latest = df.iloc[-1]
                    market = {
                        "code": stock,
                        "name": latest.get("name", ""),
                        "price": latest.get("close", 0),
                        "change_pct": latest.get("pct_chg", 0),
                        "volume": latest.get("volume", 0),
                    }
                    self._save_market(market)
                    # 检查是否需要发送异动提醒
                    self._alert_service.check_and_alert_from_change_pct(market)
                    success_count += 1
                else:
                    fail_count += 1
                    errors.append(f"{stock}: 无数据返回")
            except Exception as e:
                fail_count += 1
                error_msg = f"{stock}: 获取失败({str(e)})"
                errors.append(error_msg)
                logger.error(f"获取股票 {stock} 数据失败: {e}")

        if errors and fail_count > 0:
            logger.warning(f"行情刷新完成: 成功 {success_count}, 失败 {fail_count}, 错误: {'; '.join(errors[:5])}")
        elif success_count > 0:
            logger.info(f"行情刷新完成: 成功 {success_count}, 失败 {fail_count}")

    def _save_market(self, market: Dict):
        """保存行情到数据库"""
        try:
            conn = sqlite3.connect(self._db_path)
            c = conn.cursor()
            c.execute("""
                INSERT OR REPLACE INTO markets (code, name, price, change_pct, volume, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (market["code"], market["name"], market["price"],
                  market["change_pct"], market["volume"], datetime.now().isoformat()))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"保存行情数据失败 [{market.get('code', 'unknown')}]: {e}")

    def _check_alerts(self):
        """检查行情异动"""
        config = get_config()
        if not config.alerts_enabled:
            return

        threshold = config.alerts_threshold_pct

        for market in self._get_markets():
            if abs(market.get("change_pct", 0)) > threshold:
                self._send_alert(market)

    def _send_alert(self, market):
        """发送异动通知"""
        try:
            from src.notification import NotificationService
            notifier = NotificationService()
            message = f"\U0001f6a8 {market['code']} 异动: {market['change_pct']:+.2f}% (价格: {market['price']})"
            if notifier.send(message):
                logger.info(f"异动提醒发送成功: {market['code']}")
            else:
                logger.warning(f"异动提醒发送失败: {market['code']}")
        except Exception as e:
            logger.error(f"发送异动提醒异常 [{market['code']}]: {e}")

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
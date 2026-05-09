"""DataService 后端守护进程"""
import json
import sys
import sqlite3
import logging
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable

from .config import get_config
from .alert_service import AlertService

logger = logging.getLogger(__name__)


# Action handler type: takes request dict, returns response dict
ActionHandler = Callable[[Dict[str, Any]], Dict[str, Any]]


class DataService:
    """
    DataService 后端守护进程

    使用 action registry 模式分发请求到各 handler。
    每个 handler 是类的一个方法，接受 request dict，返回 response dict。
    """

    def __init__(self):
        self._running = True
        self._db_path = ".open-daily-stock.db"
        self._init_db()
        self._alert_service = AlertService()

        # === Action Registry ===
        # 映射 action name -> handler method name
        self._actions: Dict[str, str] = {
            "hello": "_handle_hello",
            "get_markets": "_handle_get_markets",
            "refresh": "_handle_refresh",
            "analyze": "_handle_analyze",
            "get_history": "_handle_get_history",
            "search_news": "_handle_search_news",
            "get_tasks": "_handle_get_tasks",
            "get_task": "_handle_get_task",
            "cancel_task": "_handle_cancel_task",
            "quit": "_handle_quit",
        }

        # Task storage for async operations
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()

    def _handle_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """根据 action 分发到对应 handler"""
        action = req.get("action", "")

        if action not in self._actions:
            return {"status": "error", "message": f"不支持的操作: {action}"}

        handler_name = self._actions[action]
        handler: ActionHandler = getattr(self, handler_name)
        return handler(req)

    # === Existing Handlers ===

    def _handle_hello(self, req: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "version": "0.4.0"}

    def _handle_get_markets(self, req: Dict[str, Any]) -> Dict[str, Any]:
        try:
            markets = self._get_markets()
            return {"status": "ok", "data": markets}
        except Exception as e:
            logger.error(f"获取行情失败: {e}")
            return {"status": "error", "message": "获取行情失败，请稍后重试"}

    def _handle_refresh(self, req: Dict[str, Any]) -> Dict[str, Any]:
        try:
            self._refresh_markets()
            self._check_alerts()
            return {"status": "ok", "message": "刷新完成"}
        except Exception as e:
            logger.error(f"刷新行情失败: {e}")
            return {"status": "error", "message": "刷新失败，请检查网络连接"}

    def _handle_quit(self, req: Dict[str, Any]) -> Dict[str, Any]:
        self._running = False
        return {"status": "ok", "message": "退出"}

    # === Stub Handlers for New Actions ===

    def _handle_analyze(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """触发 AI 分析任务"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        # 生成 task_id
        task_id = f"task_{len(self._tasks) + 1}_{code}_{int(datetime.now().timestamp())}"

        # 创建任务记录
        with self._tasks_lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "code": code,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "result": None,
                "error": None,
            }

        # 异步执行分析（不阻塞 DataService）
        thread = threading.Thread(target=self._run_analyze_task, args=(task_id, code))
        thread.daemon = True
        thread.start()

        return {"status": "ok", "task_id": task_id, "message": "分析任务已创建"}

    def _run_analyze_task(self, task_id: str, code: str):
        """后台执行 AI 分析"""
        try:
            with self._tasks_lock:
                self._tasks[task_id]["status"] = "running"

            # 获取分析上下文
            from src.storage import get_analysis_context
            context = get_analysis_context(code)

            # 执行 AI 分析
            from src.analyzer import GeminiAnalyzer
            analyzer = GeminiAnalyzer()
            result = analyzer.analyze(context)

            # 保存结果
            with self._tasks_lock:
                self._tasks[task_id]["status"] = "completed"
                self._tasks[task_id]["result"] = result.to_dict()
                self._tasks[task_id]["completed_at"] = datetime.now().isoformat()

            # 发送通知
            self._send_analysis_notification(code, result)

        except Exception as e:
            logger.error(f"AI 分析失败 [{code}]: {e}")
            with self._tasks_lock:
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)

    def _send_analysis_notification(self, code: str, result):
        """发送分析完成通知"""
        try:
            from src.notification import NotificationService
            notifier = NotificationService()
            message = f"📊 {result.name}({code}) 分析完成: {result.operation_advice} (评分: {result.sentiment_score})"
            notifier.send(message)
        except Exception as e:
            logger.warning(f"发送分析通知失败: {e}")

    def _handle_get_history(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取股票历史数据"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        days = req.get("days", 30)  # 默认 30 天

        try:
            from data_provider.efinance_fetcher import EfinanceFetcher
            fetcher = EfinanceFetcher()
            df = fetcher.get_daily_data(code, days=days)

            if df is None or len(df) == 0:
                return {"status": "ok", "data": [], "message": "无历史数据"}

            # 转换为 dict 列表
            data = []
            for _, row in df.iterrows():
                data.append({
                    "date": str(row.get("date", "")),
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)),
                    "pct_chg": float(row.get("pct_chg", 0)),
                })

            return {"status": "ok", "data": data}

        except Exception as e:
            logger.error(f"获取历史数据失败 [{code}]: {e}")
            return {"status": "error", "message": f"获取历史数据失败: {str(e)}"}

    def _handle_search_news(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """搜索股票相关新闻"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        try:
            from src.search_service import SearchService
            from src.config import get_config

            config = get_config()
            search_service = SearchService(
                bocha_keys=config.bocha_api_keys,
                tavily_keys=config.tavily_api_keys,
                serpapi_keys=config.serpapi_keys
            )

            # 获取股票名称
            from src.analyzer import STOCK_NAME_MAP
            name = STOCK_NAME_MAP.get(code, code)

            # 执行搜索
            news_results = search_service.search_stock_news(code, name)

            return {"status": "ok", "data": news_results.results}

        except Exception as e:
            logger.error(f"搜索新闻失败 [{code}]: {e}")
            return {"status": "error", "message": f"搜索新闻失败: {str(e)}"}

    def _handle_get_tasks(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取所有任务列表"""
        with self._tasks_lock:
            tasks = []
            for task_id, task in self._tasks.items():
                tasks.append({
                    "task_id": task_id,
                    "code": task["code"],
                    "status": task["status"],
                    "created_at": task["created_at"],
                    "completed_at": task.get("completed_at"),
                })
            # 按时间倒序
            tasks.sort(key=lambda x: x["created_at"], reverse=True)
        return {"status": "ok", "tasks": tasks}

    def _handle_get_task(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取单个任务详情"""
        task_id = req.get("task_id")
        if not task_id:
            return {"status": "error", "message": "缺少 task_id 参数"}

        with self._tasks_lock:
            if task_id not in self._tasks:
                return {"status": "error", "message": f"任务 {task_id} 不存在"}

            task = self._tasks[task_id]
        return {"status": "ok", "task": task}

    def _handle_cancel_task(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """取消任务"""
        task_id = req.get("task_id")
        if not task_id:
            return {"status": "error", "message": "缺少 task_id 参数"}

        with self._tasks_lock:
            if task_id not in self._tasks:
                return {"status": "error", "message": f"任务 {task_id} 不存在"}

            task = self._tasks[task_id]
            if task["status"] in ["completed", "failed", "cancelled"]:
                return {"status": "error", "message": f"任务已 {task['status']}，无法取消"}

            task["status"] = "cancelled"
        return {"status": "ok", "message": "任务已取消"}

    # === Existing Helper Methods ===

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
                resp = self._handle_request(req)
                self._send(resp)
            except json.JSONDecodeError:
                self._send({"status": "error", "message": "invalid json"})
            except Exception as e:
                self._send({"status": "error", "message": str(e)})

if __name__ == "__main__":
    service = DataService()
    service.run()
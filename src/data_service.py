"""DataService 后端守护进程"""
from __future__ import annotations
import json
import sys
import logging
import asyncio
import threading
import uuid
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Callable

from pathlib import Path
from .config import get_config
from .alert_service import AlertService
from .storage import get_db, get_market_cache, MarketReview
from .sim_trading import SimAccount
from .financials import FinancialDataFetcher, _safe_float

logger = logging.getLogger(__name__)

# ============================================================
# Request Timeout and Thread Pool Configuration
# ============================================================
REQUEST_TIMEOUT_SECONDS = 30  # Default timeout per request
MAX_CONCURRENT_REQUESTS = 5   # Max concurrent requests
HEARTBEAT_INTERVAL = 30        # Seconds between heartbeats

# ============================================================
# Auto-Restart Configuration
# ============================================================
MAX_RESTARTS_PER_HOUR = 3     # Max restarts per hour to prevent tight loops
RESTART_COOLDOWN_SECONDS = 60  # Cooldown between restart attempts


class DataService:
    """
    DataService 后端守护进程

    使用 action registry 模式分发请求到各 handler。
    每个 handler 是类的一个方法，接受 request dict，返回 response dict。

    错误恢复增强：
    1. Per-Request Timeout: 每个请求在 ThreadPoolExecutor 中执行，30秒超时
    2. Network Degradation Fallback: 网络失败时回退到 SQLite 缓存
    3. AI API Retry: 带指数退避的 429 重试
    4. Auto-Restart: 崩溃后自动重启（通过外部 watchdog）
    """

    def __init__(self):
        self._running = True
        # Initialize database via storage.py (ensures all schema tables exist)
        get_db()
        self._alert_service = AlertService()

        # P6-2: Start scheduled market review
        self._start_scheduled_market_review()

        # P6-4: Start bot runner
        self._start_bot()

        # === Thread Pool for concurrent request handling ===
        self._executor = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS)

        # === AI API circuit breaker state (instance-level, not class-level) ===
        self._ai_provider_state = {
            "429_count": 0,
            "last_429_time": 0,
            "disabled_until": 0,  # Unix timestamp when re-enable
            "current_provider": "gemini",
        }
        # 映射 action name -> handler method name
        self._actions: Dict[str, str] = {
            "hello": "_handle_hello",
            "get_markets": "_handle_get_markets",
            "refresh": "_handle_refresh",
            "analyze": "_handle_analyze",
            "analyze_stream": "_handle_analyze_stream",
            "deep_analyze": "_handle_deep_analyze",
            "get_history": "_handle_get_history",
            "search_news": "_handle_search_news",
            "get_kline_data": "_handle_get_kline_data",
            "get_indicators": "_handle_get_indicators",
            "screen_stocks": "_handle_screen_stocks",
            "get_tasks": "_handle_get_tasks",
            "get_task": "_handle_get_task",
            "cancel_task": "_handle_cancel_task",
            "add_position": "_handle_add_position",
            "remove_position": "_handle_remove_position",
            "update_position": "_handle_update_position",
            "get_positions": "_handle_get_positions",
            "get_institutional": "_handle_get_institutional",
            "get_dragon_board": "_handle_get_dragon_board",
            "run_backtest": "_handle_run_backtest",
            "get_alerts": "_handle_get_alerts",
            "save_alert": "_handle_save_alert",
            "delete_alert": "_handle_delete_alert",
            "toggle_alert": "_handle_toggle_alert",
            "get_drawing_data": "_handle_get_drawing_data",
            "get_financials": "_handle_get_financials",
            "get_key_metrics": "_handle_get_key_metrics",
            "get_market_overview": "_handle_get_market_overview",
            "get_market_reviews_history": "_handle_get_market_reviews_history",
            "get_market_review": "_handle_get_market_review",
            "quit": "_handle_quit",
            "sim_buy": "_handle_sim_buy",
            "sim_sell": "_handle_sim_sell",
            "sim_summary": "_handle_sim_summary",
            "sim_history": "_handle_sim_history",
            "sim_reset": "_handle_sim_reset",
            "get_keybindings": "_handle_get_keybindings",
            "list_providers": "_handle_list_providers",
            "list_plugins": "_handle_list_plugins",
            "get_plugin_info": "_handle_get_plugin_info",
            "export_strategy": "_handle_export_strategy",
            "import_strategy": "_handle_import_strategy",
            "list_strategies": "_handle_list_strategies",
            "optimize_strategy": "_handle_optimize_strategy",
            "delete_strategy": "_handle_delete_strategy",
            "get_theme": "_handle_get_theme",
            "set_theme": "_handle_set_theme",
            "get_languages": "_handle_get_languages",
            "set_language": "_handle_set_language",
            "get_config": "_handle_get_config",
            "update_config": "_handle_update_config",
            "search_knowledge": "_handle_search_knowledge",
            "rag_search": "_handle_search_knowledge",
            # P5-10: Factor Analysis Engine
            "get_factor_value": "_handle_get_factor_value",
            "analyze_factor_ic": "_handle_analyze_factor_ic",
            "get_factor_rankings": "_handle_get_factor_rankings",
            # P5-9: Agentic Research Mode
            "research": "_handle_research",
        }

        # Simulated trading account
        self._sim_account = SimAccount()

        # Task storage for async operations
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._tasks_lock = threading.Lock()

        # Strategy storage directory
        self._strategies_dir = Path(__file__).parent.parent / "strategies"
        self._strategies_dir.mkdir(parents=True, exist_ok=True)

        # Demo mode state
        self._demo_mode = get_config().is_demo_mode()

        # Load external data provider plugins
        self._load_plugins()

    def _is_demo_mode(self) -> bool:
        """Check if the service is running in demo mode (reads config live)."""
        return get_config().is_demo_mode()

    def _handle_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """根据 action 分发到对应 handler with timeout protection"""
        action = req.get("action", "")

        if action not in self._actions:
            return {"status": "error", "message": f"不支持的操作: {action}"}

        handler_name = self._actions[action]
        handler: ActionHandler = getattr(self, handler_name)

        # Submit to thread pool with timeout
        timeout = req.get("_timeout", REQUEST_TIMEOUT_SECONDS)
        future = self._executor.submit(handler, req)

        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            logger.warning(f"请求 {action} 超时（{timeout}秒）")
            return {"status": "error", "message": f"请求超时（{timeout}秒）"}
        except Exception as e:
            logger.error(f"处理请求 {action} 时发生异常: {e}")
            return {"status": "error", "message": str(e)}

    # === Existing Handlers ===

    def _handle_hello(self, req: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "version": "0.4.0"}

    def _handle_get_markets(self, req: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if self._is_demo_mode():
                from src.demo_data import DEMO_STOCKS
                return {"status": "ok", "data": list(DEMO_STOCKS)}

            markets = self._get_markets()
            include_sparkline = req.get("include_sparkline", False)
            if include_sparkline:
                for m in markets:
                    history = self._get_recent_prices(m.get("code"), days=10)
                    m["sparkline_data"] = history
            return {"status": "ok", "data": markets}
        except Exception as e:
            logger.error(f"获取行情失败: {e}")
            return {"status": "error", "message": "获取行情失败，请稍后重试"}

    def _get_recent_prices(self, code: str, days: int = 10) -> List[float]:
        """Get recent closing prices for sparkline."""
        try:
            db = get_db()
            data = db.get_latest_data(code, days=days)
            return [d.close for d in reversed(data)] if data else []
        except Exception:
            return []

    def _handle_refresh(self, req: Dict[str, Any]) -> Dict[str, Any]:
        try:
            if self._is_demo_mode():
                return {"status": "ok", "message": "演示模式 - 数据无需刷新"}
            self._refresh_markets()
            self._check_alerts()
            return {"status": "ok", "message": "刷新完成"}
        except Exception as e:
            logger.error(f"刷新行情失败: {e}")
            return {"status": "error", "message": "刷新失败，请检查网络连接"}

    def _handle_quit(self, req: Dict[str, Any]) -> Dict[str, Any]:
        self._running = False
        return {"status": "ok", "message": "退出"}

    # === Simulated Trading Handlers ===

    def _handle_sim_buy(self, req: Dict[str, Any]) -> Dict[str, Any]:
        code = req["code"]
        name = req.get("name", code)
        price = req["price"]
        shares = req.get("shares", 100)
        result = self._sim_account.buy(code, name, price, shares)
        # Persist after each trade
        try:
            get_db().save_sim_account(self._sim_account.to_dict())
        except Exception as e:
            logger.warning(f"持久化模拟账户失败: {e}")
        # In-app notification
        if result.get("status") == "ok":
            try:
                from src.notification_center import get_notification_center
                cost = price * shares
                get_notification_center().notify(
                    title=f"买入 {name}({code})",
                    message=f"{shares}股 @{price:.2f}  成本 ¥{cost:,.2f}",
                    level="success",
                    category="trade_executed",
                    action="markets",
                )
            except Exception:
                pass
        return result

    def _handle_sim_sell(self, req: Dict[str, Any]) -> Dict[str, Any]:
        code = req["code"]
        price = req["price"]
        shares = req.get("shares")
        result = self._sim_account.sell(code, price, shares)
        # Persist after each trade
        try:
            get_db().save_sim_account(self._sim_account.to_dict())
        except Exception as e:
            logger.warning(f"持久化模拟账户失败: {e}")
        # In-app notification
        if result.get("status") == "ok":
            try:
                from src.notification_center import get_notification_center
                trade = result.get("trade", {})
                pnl = trade.get("pnl", 0)
                name = trade.get("name", code)
                shares_sold = trade.get("shares", 0)
                level = "success" if pnl >= 0 else "warning"
                get_notification_center().notify(
                    title=f"卖出 {name}({code})",
                    message=f"{shares_sold}股 @{price:.2f}  盈亏 ¥{pnl:+,.2f}",
                    level=level,
                    category="trade_executed",
                    action="markets",
                )
            except Exception:
                pass
        return result

    def _handle_sim_summary(self, req: Dict[str, Any]) -> Dict[str, Any]:
        # Update prices from market data first
        markets = self._get_markets()
        prices = {m["code"]: m["price"] for m in markets}
        self._sim_account.update_prices(prices)
        return {"status": "ok", "data": self._sim_account.get_summary()}

    def _handle_sim_history(self, req: Dict[str, Any]) -> Dict[str, Any]:
        return {"status": "ok", "data": self._sim_account.trade_history[-50:]}

    def _handle_sim_reset(self, req: Dict[str, Any]) -> Dict[str, Any]:
        self._sim_account = SimAccount()
        # Clear persisted account
        try:
            get_db().save_sim_account(None)
        except Exception as e:
            logger.warning(f"清除模拟账户持久化失败: {e}")
        return {"status": "ok", "message": "账户已重置"}

    def _handle_get_keybindings(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """返回指定 section 的 keybindings 配置。"""
        from src.shared.keybindings import get_all_keybindings
        section = req.get("section", "global")
        return {"status": "ok", "data": get_all_keybindings(section)}

    # === Stub Handlers for New Actions ===

    def _handle_analyze(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """触发 AI 分析任务"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        # Demo mode: return pre-computed analysis synchronously
        if self._is_demo_mode():
            from src.demo_data import DEMO_AI_ANALYSES
            if code in DEMO_AI_ANALYSES:
                task_id = f"demo_task_{code}_{int(datetime.now().timestamp())}"
                demo_result = DEMO_AI_ANALYSES[code]
                with self._tasks_lock:
                    self._tasks[task_id] = {
                        "task_id": task_id,
                        "code": code,
                        "status": "completed",
                        "created_at": datetime.now().isoformat(),
                        "completed_at": datetime.now().isoformat(),
                        "result": demo_result,
                        "error": None,
                    }
                return {"status": "ok", "task_id": task_id, "message": "演示分析完成（无需 API Key）", "result": demo_result}
            else:
                return {"status": "error", "message": f"演示模式不支持该股票代码: {code}"}

        # 生成 task_id
        task_id = f"task_{uuid.uuid4().hex[:8]}_{code}_{int(datetime.now().timestamp())}"

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

        # Persist task creation (AnalysisHistory for backward compat)
        try:
            get_db().save_task(task_id, code, "pending")
        except Exception:
            pass  # Non-critical if DB save fails initially

        # Persist to task_log
        try:
            get_db().save_task_log(task_id, "analyze", code, "pending")
        except Exception as e:
            logger.warning(f"Failed to save task_log for {task_id}: {e}")

        # 异步执行分析（不阻塞 DataService）
        thread = threading.Thread(target=self._run_analyze_task, args=(task_id, code))
        thread.daemon = True
        thread.start()

        return {"status": "ok", "task_id": task_id, "message": "分析任务已创建"}

    def _run_analyze_task(self, task_id: str, code: str):
        """后台执行 AI 分析"""
        db = get_db()

        try:
            # Check if cancelled before starting
            with self._tasks_lock:
                if self._tasks[task_id]["status"] == "cancelled":
                    return
                self._tasks[task_id]["status"] = "running"

            # Persist running status
            db.save_task(task_id, code, "running")
            try:
                db.update_task_log(task_id, "running")
            except Exception as e:
                logger.warning(f"Failed to update task_log to running for {task_id}: {e}")

            # 获取分析上下文
            context = db.get_analysis_context(code)

            # 执行 AI 分析
            from src.analyzer import GeminiAnalyzer
            analyzer = GeminiAnalyzer()
            result = analyzer.analyze(context)

            # Check if cancelled before saving result
            with self._tasks_lock:
                if self._tasks[task_id]["status"] == "cancelled":
                    return
                self._tasks[task_id]["status"] = "completed"
                self._tasks[task_id]["result"] = result.to_dict()
                self._tasks[task_id]["completed_at"] = datetime.now().isoformat()

            # Persist completed status
            db.save_task(task_id, code, "completed", result_json=json.dumps(result.to_dict()))
            try:
                db.update_task_log(task_id, "done", completed_at=datetime.now(),
                                   result_json=json.dumps(result.to_dict()))
            except Exception as e:
                logger.warning(f"Failed to update task_log to done for {task_id}: {e}")

            # 发送外部通知
            self._send_analysis_notification(code, result)
            # In-app notification
            try:
                from src.notification_center import get_notification_center
                get_notification_center().notify(
                    title=f"分析完成: {result.name}({code})",
                    message=f"{result.operation_advice} (评分: {result.sentiment_score})",
                    level="success",
                    category="analysis_complete",
                    action="analyze",
                )
            except Exception:
                pass

        except Exception as e:
            logger.error(f"AI 分析失败 [{code}]: {e}")
            with self._tasks_lock:
                if self._tasks[task_id]["status"] == "cancelled":
                    return
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)
            db.save_task(task_id, code, "failed", error=str(e))
            try:
                db.update_task_log(task_id, "failed", completed_at=datetime.now())
            except Exception as ex:
                logger.warning(f"Failed to update task_log to failed for {task_id}: {ex}")

    def _send_analysis_notification(self, code: str, result):
        """发送分析完成通知"""
        try:
            from src.notification import NotificationService
            notifier = NotificationService()
            message = f"📊 {result.name}({code}) 分析完成: {result.operation_advice} (评分: {result.sentiment_score})"
            notifier.send(message)
        except Exception as e:
            logger.warning(f"发送分析通知失败: {e}")

    # ============================================================
    # P5-5: Deep Analysis Handler
    # ============================================================

    def _handle_deep_analyze(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger deep multi-agent analysis task.

        Creates a task and runs deep analysis in a background thread.
        Returns a task_id immediately for async polling.
        """
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        enabled_agents_str = req.get("deep_analysis_agents", None)
        enabled_agents = None
        if enabled_agents_str:
            enabled_agents = [a.strip() for a in enabled_agents_str.split(',') if a.strip()]

        # Demo mode: return pre-computed synthetic deep analysis
        if self._is_demo_mode():
            task_id = f"deep_demo_{code}_{int(datetime.now().timestamp())}"
            demo_result = self._build_demo_deep_result(code, enabled_agents)
            with self._tasks_lock:
                self._tasks[task_id] = {
                    "task_id": task_id,
                    "code": code,
                    "status": "completed",
                    "created_at": datetime.now().isoformat(),
                    "completed_at": datetime.now().isoformat(),
                    "result": demo_result,
                    "error": None,
                }
            return {
                "status": "ok",
                "task_id": task_id,
                "message": "演示深度分析完成（无需 API Key）",
                "result": demo_result,
            }

        task_id = f"deep_{uuid.uuid4().hex[:8]}_{code}_{int(datetime.now().timestamp())}"

        with self._tasks_lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "code": code,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "result": None,
                "error": None,
            }

        try:
            get_db().save_task(task_id, code, "pending")
            get_db().save_task_log(task_id, "deep_analyze", code, "pending")
        except Exception:
            pass

        thread = threading.Thread(
            target=self._run_deep_analyze_task,
            args=(task_id, code, enabled_agents),
        )
        thread.daemon = True
        thread.start()

        return {"status": "ok", "task_id": task_id, "message": "深度分析任务已创建"}

    def _run_deep_analyze_task(
        self, task_id: str, code: str, enabled_agents: Optional[List[str]]
    ):
        """Background execution of deep multi-agent analysis."""
        db = get_db()

        try:
            with self._tasks_lock:
                if self._tasks[task_id]["status"] == "cancelled":
                    return
                self._tasks[task_id]["status"] = "running"

            db.save_task(task_id, code, "running")
            try:
                db.update_task_log(task_id, "running")
            except Exception:
                pass

            context = db.get_analysis_context(code)

            from src.analyzer import GeminiAnalyzer
            analyzer = GeminiAnalyzer()
            result = analyzer.deep_analyze(context, enabled_agents=enabled_agents)

            with self._tasks_lock:
                if self._tasks[task_id]["status"] == "cancelled":
                    return
                self._tasks[task_id]["status"] = "completed"
                self._tasks[task_id]["result"] = result.to_dict()
                self._tasks[task_id]["completed_at"] = datetime.now().isoformat()

            db.save_task(task_id, code, "completed", result_json=json.dumps(result.to_dict()))
            try:
                db.update_task_log(task_id, "done", completed_at=datetime.now(),
                                   result_json=json.dumps(result.to_dict()))
            except Exception:
                pass

            self._send_deep_analysis_notification(code, result)

        except Exception as e:
            logger.error(f"深度分析失败 [{code}]: {e}")
            with self._tasks_lock:
                if self._tasks[task_id]["status"] == "cancelled":
                    return
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)
            db.save_task(task_id, code, "failed", error=str(e))
            try:
                db.update_task_log(task_id, "failed", completed_at=datetime.now())
            except Exception:
                pass

    def _send_deep_analysis_notification(self, code: str, result):
        """Send notification for completed deep analysis."""
        try:
            from src.notification import NotificationService
            notifier = NotificationService()
            name = getattr(result, 'name', code)
            score = getattr(result, 'composite_score', 50)
            verdict = getattr(result, 'final_verdict', '中性')
            message = f"🔬 {name}({code}) 深度分析完成: {verdict} (综合评分: {score})"
            notifier.send(message)
        except Exception as e:
            logger.warning(f"发送深度分析通知失败: {e}")

    def _build_demo_deep_result(self, code: str, enabled_agents: Optional[List[str]]) -> Dict[str, Any]:
        """Build synthetic demo deep analysis result."""
        if enabled_agents is None:
            enabled_agents = ["technical", "fundamental", "news"]

        return {
            "code": code,
            "name": f"演示股票{code}",
            "sentiment_score": 70,
            "trend_prediction": "看多",
            "operation_advice": "买入",
            "composite_score": 70,
            "final_verdict": "看涨",
            "key_catalysts": ["演示利好因素1", "演示利好因素2"],
            "risk_factors": ["演示风险因素1"],
            "technical": {"trend": "bullish", "key_signals": ["MA金叉", "放量突破"], "support": 1600.0, "resistance": 1800.0, "score": 72},
            "fundamental": {"valuation": "fair", "key_metrics": ["PE适中", "营收增长"], "risks": ["行业竞争"], "score": 68},
            "news": {"sentiment": "positive", "key_drivers": ["政策利好"], "risk_events": [], "score": 70},
            "synthesis_text": "演示模式深度分析 - 综合评分 70，看涨",
            "success": True,
            "error_message": None,
        }

    def _handle_analyze_stream(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """
        Streaming AI analysis action.

        When called from stdio mode, falls back to non-streaming analyze
        (returns a task_id like _handle_analyze). When called from WebSocket
        mode, the WebSocket handler intercepts this action and streams chunks
        directly to the client.

        Returns:
            For stdio: standard task_id response
            For WebSocket: this handler is not called directly; the WS
                           handler intercepts and streams instead.
        """
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        # Demo mode: return pre-computed analysis
        if self._is_demo_mode():
            return self._handle_analyze(req)

        # In stdio mode, fall back to non-streaming analyze
        task_id = f"task_{uuid.uuid4().hex[:8]}_{code}_{int(datetime.now().timestamp())}"

        with self._tasks_lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "code": code,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "result": None,
                "error": None,
            }

        try:
            get_db().save_task(task_id, code, "pending")
            get_db().save_task_log(task_id, "analyze", code, "pending")
        except Exception as e:
            logger.warning(f"Failed to persist task: {e}")

        thread = threading.Thread(
            target=self._run_analyze_task, args=(task_id, code)
        )
        thread.daemon = True
        thread.start()

        return {"status": "ok", "task_id": task_id, "message": "分析任务已创建（非流式）"}

    async def _handle_analyze_stream_ws(self, websocket, req: Dict[str, Any]):
        """
        Handle analyze_stream over WebSocket.

        Streams analysis chunks token-by-token to the WebSocket client,
        then sends the final structured result.

        Args:
            websocket: The WebSocket connection
            req: The request dict with "code" field
        """
        code = req.get("code")
        if not code:
            await websocket.send(json.dumps({
                "type": "stream_error",
                "message": "缺少股票代码 code 参数"
            }, ensure_ascii=False, default=str))
            return

        # Demo mode: send pre-computed result as simulated stream
        if self._is_demo_mode():
            await self._handle_analyze_stream_ws_demo(websocket, code)
            return

        # Create task record
        task_id = f"task_{uuid.uuid4().hex[:8]}_{code}_{int(datetime.now().timestamp())}"
        with self._tasks_lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "code": code,
                "status": "running",
                "created_at": datetime.now().isoformat(),
                "result": None,
                "error": None,
            }

        try:
            get_db().save_task(task_id, code, "running")
            get_db().save_task_log(task_id, "analyze", code, "running")
        except Exception as e:
            logger.warning(f"Failed to persist task for stream: {e}")

        db = get_db()
        try:
            # Get analysis context
            context = db.get_analysis_context(code)

            # Run streaming analysis in thread to avoid blocking event loop
            from src.analyzer import GeminiAnalyzer

            chunks = []
            final_result = None

            def run_stream():
                nonlocal final_result
                analyzer = GeminiAnalyzer()
                for event in analyzer.analyze_stream(context):
                    chunks.append(event)
                    if event["type"] == "done":
                        final_result = event["result"]

            # Run the stream collector in a thread
            stream_thread = threading.Thread(target=run_stream)
            stream_thread.start()

            # Send a task_id reference first
            await websocket.send(json.dumps({
                "type": "stream_start",
                "task_id": task_id,
                "code": code,
            }, ensure_ascii=False, default=str))

            # Poll for chunks and send them
            chunk_index = 0
            event_types_seen = set()
            while stream_thread.is_alive() or chunk_index < len(chunks):
                while chunk_index < len(chunks):
                    event = chunks[chunk_index]
                    chunk_index += 1

                    if event["type"] == "chunk":
                        await websocket.send(json.dumps({
                            "type": "stream_chunk",
                            "chunk": event["data"],
                        }, ensure_ascii=False, default=str))
                    elif event["type"] == "done":
                        event_types_seen.add("done")
                        # Persist result
                        with self._tasks_lock:
                            self._tasks[task_id]["status"] = "completed"
                            self._tasks[task_id]["result"] = event["result"].to_dict()
                            self._tasks[task_id]["completed_at"] = datetime.now().isoformat()

                        try:
                            db.save_task(task_id, code, "completed",
                                        result_json=json.dumps(event["result"].to_dict()))
                            db.update_task_log(task_id, "done", completed_at=datetime.now(),
                                              result_json=json.dumps(event["result"].to_dict()))
                        except Exception as e:
                            logger.warning(f"Failed to persist stream result: {e}")

                        await websocket.send(json.dumps({
                            "type": "stream_done",
                            "task_id": task_id,
                            "result": event["result"].to_dict(),
                        }, ensure_ascii=False, default=str))

                if stream_thread.is_alive():
                    await asyncio.sleep(0.05)  # Small delay to avoid busy loop

            # If we never got a "done" event (stream failed silently)
            if "done" not in event_types_seen:
                with self._tasks_lock:
                    self._tasks[task_id]["status"] = "failed"
                    self._tasks[task_id]["error"] = "Stream completed without result"
                await websocket.send(json.dumps({
                    "type": "stream_error",
                    "task_id": task_id,
                    "message": "流式分析未返回结果",
                }, ensure_ascii=False, default=str))

        except Exception as e:
            logger.error(f"Stream analyze error [{code}]: {e}")
            with self._tasks_lock:
                if task_id in self._tasks:
                    self._tasks[task_id]["status"] = "failed"
                    self._tasks[task_id]["error"] = str(e)

            try:
                db.save_task(task_id, code, "failed", error=str(e))
                db.update_task_log(task_id, "failed", completed_at=datetime.now())
            except Exception:
                pass

            await websocket.send(json.dumps({
                "type": "stream_error",
                "task_id": task_id,
                "message": str(e),
            }, ensure_ascii=False, default=str))

    async def _handle_analyze_stream_ws_demo(self, websocket, code: str):
        """Simulate streaming analysis with pre-computed demo data over WebSocket."""
        from src.demo_data import DEMO_AI_ANALYSES

        task_id = f"demo_task_{code}_{int(datetime.now().timestamp())}"

        if code not in DEMO_AI_ANALYSES:
            await websocket.send(json.dumps({
                "type": "stream_error",
                "message": f"演示模式不支持该股票代码: {code}",
            }, ensure_ascii=False, default=str))
            return

        demo_result = DEMO_AI_ANALYSES[code]

        # Persist task
        with self._tasks_lock:
            self._tasks[task_id] = {
                "task_id": task_id,
                "code": code,
                "status": "completed",
                "created_at": datetime.now().isoformat(),
                "completed_at": datetime.now().isoformat(),
                "result": demo_result,
                "error": None,
            }

        # Send stream start
        await websocket.send(json.dumps({
            "type": "stream_start",
            "task_id": task_id,
            "code": code,
        }, ensure_ascii=False, default=str))

        # Simulate streaming by sending summary text in chunks
        summary = demo_result.get("analysis_summary", "")
        chunk_size = 5  # characters per chunk
        for i in range(0, len(summary), chunk_size):
            chunk = summary[i:i + chunk_size]
            await websocket.send(json.dumps({
                "type": "stream_chunk",
                "chunk": chunk,
            }, ensure_ascii=False, default=str))
            await asyncio.sleep(0.02)  # simulate streaming timing

        # Send final result
        await websocket.send(json.dumps({
            "type": "stream_done",
            "task_id": task_id,
            "result": demo_result,
        }, ensure_ascii=False, default=str))

    def _handle_get_history(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取股票历史数据"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        days = req.get("days", 30)  # 默认 30 天

        # Demo mode: return pre-generated K-line data
        if self._is_demo_mode():
            from src.demo_data import DEMO_KLINES
            if code in DEMO_KLINES:
                klines = DEMO_KLINES[code]
                # Convert from [date, open, high, low, close, volume] to dict list
                data = []
                for row in klines:
                    if isinstance(row, list) and len(row) >= 6:
                        data.append({
                            "date": str(row[0]),
                            "open": float(row[1]),
                            "high": float(row[2]),
                            "low": float(row[3]),
                            "close": float(row[4]),
                            "volume": float(row[5]),
                            "pct_chg": 0.0,
                        })
                return {"status": "ok", "data": data[-days:] if days < len(data) else data}
            else:
                return {"status": "ok", "data": [], "message": "演示模式无此股票历史数据"}

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

        # Demo mode: return empty news list (no real search APIs)
        if self._is_demo_mode():
            return {"status": "ok", "data": [], "message": "演示模式下不提供实时新闻搜索"}

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

    def _handle_get_kline_data(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取K线图表数据"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        days = req.get("days", 60)
        indicators = req.get("indicators")

        try:
            # 先获取历史数据
            history_result = self._handle_get_history({"code": code, "days": days})
            if history_result.get("status") != "ok":
                return history_result

            history_data = history_result.get("data", [])
            if not history_data:
                return {"status": "ok", "data": [], "message": "无历史数据"}

            # 保存到 daily_history 表（幂等）
            try:
                saved = get_db().save_daily_history(code, history_data)
                if saved:
                    logger.debug(f"Persisted {saved} new rows to daily_history for {code}")
            except Exception as e:
                logger.warning(f"Failed to persist daily_history for {code}: {e}")

            # 生成K线图表
            from src.charts import create_kline_chart
            chart_path = create_kline_chart(history_data, code, days=days, indicators=indicators)

            return {"status": "ok", "image_path": chart_path, "data": history_data}

        except Exception as e:
            logger.error(f"获取K线数据失败 [{code}]: {e}")
            return {"status": "error", "message": f"获取K线数据失败: {str(e)}"}

    def _handle_get_indicators(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取技术指标数据"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        indicator_names = req.get("indicator_names")
        if not indicator_names:
            return {"status": "error", "message": "缺少 indicator_names 参数"}

        if isinstance(indicator_names, str):
            indicator_names = [indicator_names]

        days = req.get("days", 60)

        try:
            # 获取历史数据
            history_result = self._handle_get_history({"code": code, "days": days})
            if history_result.get("status") != "ok":
                return history_result

            history_data = history_result.get("data", [])
            if not history_data:
                return {"status": "ok", "data": {}, "message": "无历史数据"}

            # 计算指标
            from src.charts import convert_history_to_df, add_indicators
            df = convert_history_to_df(history_data)
            if df is None:
                return {"status": "ok", "data": {}, "message": "无历史数据"}

            df = add_indicators(df, indicator_names)

            # 构建返回数据
            indicator_data = {}
            valid_indicators = {"rsi", "macd", "bollinger", "kdj", "wr", "obv"}

            for name in indicator_names:
                name_lower = name.lower()
                if name_lower not in valid_indicators:
                    continue

                if name_lower == "rsi":
                    indicator_data["rsi"] = df["RSI"].dropna().to_dict()
                elif name_lower == "macd":
                    indicator_data["macd"] = {
                        "macd": df["MACD"].dropna().to_dict(),
                        "dif": df["DIF"].dropna().to_dict(),
                        "dea": df["DEA"].dropna().to_dict(),
                    }
                elif name_lower == "bollinger":
                    indicator_data["bollinger"] = {
                        "upper": df["BB_UPPER"].dropna().to_dict(),
                        "middle": df["BB_MIDDLE"].dropna().to_dict(),
                        "lower": df["BB_LOWER"].dropna().to_dict(),
                    }
                elif name_lower == "kdj":
                    indicator_data["kdj"] = {
                        "k": df["K"].dropna().to_dict(),
                        "d": df["D"].dropna().to_dict(),
                        "j": df["J"].dropna().to_dict(),
                    }
                elif name_lower == "wr":
                    indicator_data["wr"] = df["WR"].dropna().to_dict()
                elif name_lower == "obv":
                    indicator_data["obv"] = df["OBV"].dropna().to_dict()

            return {"status": "ok", "data": indicator_data}

        except Exception as e:
            logger.error(f"获取技术指标失败 [{code}]: {e}")
            return {"status": "error", "message": f"获取技术指标失败: {str(e)}"}

    def _handle_get_drawing_data(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取画线工具数据（支撑/阻力位、斐波那契回调线）"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        days = req.get("days", 60)

        try:
            from datetime import date, timedelta
            from src.charts import convert_history_to_df
            from src.shared.indicators import find_support_resistance, calculate_fibonacci_levels

            # 获取历史数据
            history_data = get_db().get_data_range(
                code,
                date.today() - timedelta(days=days),
                date.today()
            )
            if not history_data:
                return {"status": "ok", "data": {}, "message": "无历史数据"}

            df = convert_history_to_df(history_data)
            if df is None or len(df) == 0:
                return {"status": "ok", "data": {}, "message": "无历史数据"}

            sr = find_support_resistance(df)
            high = float(df['High'].max())
            low = float(df['Low'].min())
            fib = calculate_fibonacci_levels(high, low)

            return {
                "status": "ok",
                "support_resistance": sr,
                "fibonacci": fib,
                "high": high,
                "low": low,
            }
        except Exception as e:
            logger.error(f"获取画线数据失败 [{code}]: {e}")
            return {"status": "error", "message": f"获取画线数据失败: {str(e)}"}

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

    # === Position Handlers ===

    def _handle_add_position(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """添加持仓"""
        code = req.get("code")
        name = req.get("name")
        shares = req.get("shares")
        buy_price = req.get("buy_price")
        buy_date = req.get("buy_date")

        # Validate required fields
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}
        if not name:
            name = code  # Default to code if name not provided
        if shares is None:
            return {"status": "error", "message": "缺少 shares 参数"}
        if buy_price is None:
            return {"status": "error", "message": "缺少 buy_price 参数"}
        if not buy_date:
            return {"status": "error", "message": "缺少 buy_date 参数"}

        try:
            buy_date_parsed = date.fromisoformat(buy_date)
            db = get_db()
            position = db.save_position(
                code=code,
                name=name,
                shares=shares,
                buy_price=buy_price,
                buy_date=buy_date_parsed,
                current_price=buy_price,
            )
            return {"status": "ok", "position": position.to_dict()}
        except Exception as e:
            logger.error(f"添加持仓失败: {e}")
            return {"status": "error", "message": f"添加持仓失败: {str(e)}"}

    def _handle_remove_position(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """删除持仓"""
        position_id = req.get("id")
        if position_id is None:
            return {"status": "error", "message": "缺少 id 参数"}

        try:
            db = get_db()
            position = db.get_position(position_id)
            if not position:
                return {"status": "error", "message": f"持仓 {position_id} 不存在"}

            db.delete_position(position_id)
            return {"status": "ok", "message": "持仓已删除"}
        except Exception as e:
            logger.error(f"删除持仓失败: {e}")
            return {"status": "error", "message": f"删除持仓失败: {str(e)}"}

    def _handle_update_position(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """更新持仓（当前价格等）"""
        position_id = req.get("id")
        if position_id is None:
            return {"status": "error", "message": "缺少 id 参数"}

        try:
            db = get_db()
            existing = db.get_position(position_id)
            if not existing:
                return {"status": "error", "message": f"持仓 {position_id} 不存在"}

            # Build update kwargs dynamically
            kwargs = {}
            if "current_price" in req:
                kwargs["current_price"] = req["current_price"]
            if "shares" in req:
                kwargs["shares"] = req["shares"]
            if "buy_price" in req:
                kwargs["buy_price"] = req["buy_price"]

            if not kwargs:
                return {"status": "error", "message": "没有提供更新字段"}

            updated = db.update_position(position_id, **kwargs)
            return {"status": "ok", "position": updated.to_dict()}
        except Exception as e:
            logger.error(f"更新持仓失败: {e}")
            return {"status": "error", "message": f"更新持仓失败: {str(e)}"}

    def _handle_get_positions(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取所有持仓"""
        try:
            # Demo mode: return pre-configured demo portfolio
            if self._is_demo_mode():
                from src.demo_data import DEMO_PORTFOLIO, DEMO_PORTFOLIO_SUMMARY
                return {
                    "status": "ok",
                    "positions": list(DEMO_PORTFOLIO),
                    "summary": DEMO_PORTFOLIO_SUMMARY,
                }

            db = get_db()
            positions = db.get_positions()
            return {"status": "ok", "positions": [p.to_dict() for p in positions]}
        except Exception as e:
            logger.error(f"获取持仓失败: {e}")
            return {"status": "error", "message": f"获取持仓失败: {str(e)}"}

    # === Institutional Activity Handlers ===

    def _handle_get_institutional(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取机构动向追踪数据（大股东增减持 + 机构调研）"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        try:
            from src.institutional import get_institutional_summary
            data = get_institutional_summary(code)
            return {"status": "ok", "data": data}

        except Exception as e:
            logger.error(f"获取机构动向失败 [{code}]: {e}")
            return {"status": "error", "message": f"获取机构动向失败: {str(e)}"}

    def _handle_get_dragon_board(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取龙虎榜数据"""
        date = req.get("date")  # 可选参数

        try:
            from src.institutional import get_dragon_board
            data = get_dragon_board(date=date)
            return {"status": "ok", "data": data}

        except Exception as e:
            logger.error(f"获取龙虎榜失败: {e}")
            return {"status": "error", "message": f"获取龙虎榜失败: {str(e)}"}

    def _handle_run_backtest(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """运行回测"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        initial_capital = req.get("initial_capital")
        if initial_capital is None:
            return {"status": "error", "message": "缺少 initial_capital 参数"}

        days = req.get("days", 60)  # 默认 60 天
        strategy_name = req.get("strategy", "")  # P6-1: 可选策略名称

        try:
            # 获取历史数据
            history_result = self._handle_get_history({"code": code, "days": days})
            if history_result.get("status") != "ok":
                return history_result

            history_data = history_result.get("data", [])
            if not history_data:
                return {"status": "ok", "data": [], "message": "无历史数据"}

            # P6-1: 支持多种策略
            from src.backtester import backtest, ma_crossover_strategy
            from src.strategies import get_python_strategy, get_strategy

            strategy_fn = ma_crossover_strategy  # 默认
            strategy_label = "MA交叉(默认)"

            if strategy_name:
                # 优先查找 Python 内置策略
                py_strat = get_python_strategy(strategy_name)
                if py_strat is not None:
                    # 允许请求参数覆盖策略参数
                    strat_params = req.get("strategy_params", {})
                    if strat_params:
                        py_strat = py_strat.__class__(**strat_params)
                    strategy_fn = py_strat
                    strategy_label = py_strat.display_name
                else:
                    # 尝试 YAML 策略（暂不支持回测，返回提示）
                    yaml_strat = get_strategy(strategy_name)
                    if yaml_strat is not None and not hasattr(yaml_strat, "generate_trades"):
                        return {
                            "status": "error",
                            "message": f"YAML策略 '{strategy_name}' 暂不支持回测，请使用Python内置策略"
                        }

            result = backtest(
                history_data,
                initial_capital=initial_capital,
                strategy_fn=strategy_fn,
            )

            # In-app notification
            try:
                from src.notification_center import get_notification_center
                get_notification_center().notify(
                    title=f"回测完成: {code} [{strategy_label}]",
                    message=f"收益率 {result.total_return:+.2f}%  胜率 {result.win_rate:.1f}%  交易 {result.num_trades}次",
                    level="info",
                    category="backtest_complete",
                    action="strategies",
                )
            except Exception:
                pass

            return {
                "status": "ok",
                "data": {
                    "strategy": strategy_label,
                    "total_return": result.total_return,
                    "max_drawdown": result.max_drawdown,
                    "sharpe_ratio": result.sharpe_ratio,
                    "num_trades": result.num_trades,
                    "win_rate": result.win_rate,
                }
            }

        except Exception as e:
            logger.error(f"回测失败 [{code}]: {e}")
            return {"status": "error", "message": f"回测失败: {str(e)}"}

    # === Alert Handlers ===

    def _handle_get_alerts(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取所有告警配置"""
        try:
            db = get_db()
            alerts = db.get_alerts()
            return {"status": "ok", "alerts": [a.to_dict() for a in alerts]}
        except Exception as e:
            logger.error(f"获取告警失败: {e}")
            return {"status": "error", "message": f"获取告警失败: {str(e)}"}

    def _handle_save_alert(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """创建新告警"""
        stock = req.get("stock")
        condition = req.get("condition")
        threshold = req.get("threshold")
        channel = req.get("channel", "wechat")

        if not stock:
            return {"status": "error", "message": "缺少 stock 参数"}
        if not condition:
            return {"status": "error", "message": "缺少 condition 参数"}
        if threshold is None:
            return {"status": "error", "message": "缺少 threshold 参数"}

        try:
            db = get_db()
            alert = db.save_alert(
                stock=stock,
                condition=condition,
                threshold=float(threshold),
                channel=channel,
                enabled=True,
            )
            return {"status": "ok", "alert": alert.to_dict()}
        except Exception as e:
            logger.error(f"保存告警失败: {e}")
            return {"status": "error", "message": f"保存告警失败: {str(e)}"}

    def _handle_delete_alert(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """删除告警"""
        alert_id = req.get("id")
        if alert_id is None:
            return {"status": "error", "message": "缺少 id 参数"}

        try:
            db = get_db()
            success = db.delete_alert(int(alert_id))
            if success:
                return {"status": "ok", "message": "告警已删除"}
            return {"status": "error", "message": f"告警 {alert_id} 不存在"}
        except Exception as e:
            logger.error(f"删除告警失败: {e}")
            return {"status": "error", "message": f"删除告警失败: {str(e)}"}

    def _handle_toggle_alert(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """切换告警启用状态"""
        alert_id = req.get("id")
        if alert_id is None:
            return {"status": "error", "message": "缺少 id 参数"}

        try:
            db = get_db()
            alert = db.toggle_alert(int(alert_id))
            if alert:
                return {"status": "ok", "alert": alert.to_dict()}
            return {"status": "error", "message": f"告警 {alert_id} 不存在"}
        except Exception as e:
            logger.error(f"切换告警失败: {e}")
            return {"status": "error", "message": f"切换告警失败: {str(e)}"}

    def _handle_screen_stocks(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """股票筛选器 - 根据条件筛选股票"""
        try:
            import akshare as ak
            import pandas as pd
            from data_provider.realtime_types import safe_float

            # 获取筛选条件
            market_cap_min = req.get("market_cap_min")  # 最小市值（亿元）
            market_cap_max = req.get("market_cap_max")  # 最大市值（亿元）
            pe_min = req.get("pe_min")  # 最小市盈率
            pe_max = req.get("pe_max")  # 最大市盈率
            industry = req.get("industry")  # 行业筛选
            change_pct_min = req.get("change_pct_min")  # 最小涨跌幅%
            change_pct_max = req.get("change_pct_max")  # 最大涨跌幅%

            logger.info(f"[筛选器] 开始筛选: 市值={market_cap_min}-{market_cap_max}, "
                       f"PE={pe_min}-{pe_max}, 行业={industry}, 涨跌幅={change_pct_min}-{change_pct_max}")

            # 获取全市场实时行情（东方财富数据源）
            # 数据包含：代码、名称、最新价、涨跌幅、成交量、成交额、市盈率、市净率、总市值、流通市值等
            df = ak.stock_zh_a_spot_em()

            if df is None or df.empty:
                logger.warning("[筛选器] 未获取到行情数据")
                return {"status": "ok", "data": [], "message": "无行情数据"}

            # 重命名列以便后续处理
            column_mapping = {
                '代码': 'code',
                '名称': 'name',
                '最新价': 'price',
                '涨跌幅': 'change_pct',
                '涨跌额': 'change_amount',
                '成交量': 'volume',
                '成交额': 'amount',
                '市盈率-动态': 'pe',
                '市净率': 'pb',
                '总市值': 'total_mv',
                '流通市值': 'circ_mv',
            }
            df = df.rename(columns=column_mapping)

            # 转换数值类型
            for col in ['price', 'change_pct', 'change_amount', 'volume', 'amount', 'pe', 'pb', 'total_mv', 'circ_mv']:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: safe_float(x) if not isinstance(x, (int, float)) else x)

            # 应用筛选条件
            filtered = df.copy()

            # 市值筛选（总市值单位是元，转换为亿元）
            if market_cap_min is not None:
                filtered = filtered[filtered['total_mv'].apply(
                    lambda x: x is not None and x > 0 and x / 1e8 >= market_cap_min)]
            if market_cap_max is not None:
                filtered = filtered[filtered['total_mv'].apply(
                    lambda x: x is not None and x > 0 and x / 1e8 <= market_cap_max)]

            # 市盈率筛选
            if pe_min is not None:
                filtered = filtered[filtered['pe'].apply(lambda x: x is not None and x >= pe_min)]
            if pe_max is not None:
                filtered = filtered[filtered['pe'].apply(lambda x: x is not None and x <= pe_max)]

            # 涨跌幅筛选
            if change_pct_min is not None:
                filtered = filtered[filtered['change_pct'].apply(lambda x: x is not None and x >= change_pct_min)]
            if change_pct_max is not None:
                filtered = filtered[filtered['change_pct'].apply(lambda x: x is not None and x <= change_pct_max)]

            # 行业筛选（需要获取行业数据）
            if industry:
                try:
                    # 获取行业板块成分股
                    industry_df = ak.stock_board_industry_cons_em(symbol=industry)
                    if industry_df is not None and not industry_df.empty:
                        industry_codes = set(industry_df['代码'].astype(str).tolist())
                        filtered = filtered[filtered['code'].astype(str).isin(industry_codes)]
                except Exception as e:
                    logger.warning(f"[筛选器] 行业筛选失败: {e}")

            # 转换为结果列表
            results = []
            for _, row in filtered.iterrows():
                results.append({
                    'code': str(row.get('code', '')),
                    'name': str(row.get('name', '')),
                    'price': row.get('price'),
                    'change_pct': row.get('change_pct'),
                    'volume': row.get('volume'),
                    'pe': row.get('pe'),
                    'pb': row.get('pb'),
                    'total_mv': row.get('total_mv'),
                    'circ_mv': row.get('circ_mv'),
                })

            logger.info(f"[筛选器] 筛选完成: 符合条件的股票 {len(results)} 只")
            return {"status": "ok", "data": results, "count": len(results)}

        except Exception as e:
            logger.error(f"[筛选器] 筛选失败: {e}")
            return {"status": "error", "message": f"筛选失败: {str(e)}"}

    # === Financial Statement Handler ===

    def _handle_get_financials(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取财务报表数据（利润表/资产负债表/现金流量表）"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        statement_type = req.get("type", "income")
        if statement_type not in ("income", "balance", "cashflow"):
            return {"status": "error", "message": f"不支持的报表类型: {statement_type}，支持: income/balance/cashflow"}

        try:
            from src.analyzer import STOCK_NAME_MAP
            name = STOCK_NAME_MAP.get(code, code)

            fetcher = FinancialDataFetcher()
            df = fetcher.get_financial_report_df(code, statement_type)

            if df is None or len(df) == 0:
                return {"status": "ok", "data": {
                    "code": code, "name": name, "type": statement_type,
                    "periods": [], "items": [],
                }, "message": "无财务数据"}

            # Find the period/date column
            period_col = None
            for col in ["报告期", "REPORT_DATE", "报告日期"]:
                if col in df.columns:
                    period_col = col
                    break

            if period_col is None:
                for col in df.columns[:3]:
                    period_col = col
                    break

            # Get periods (most recent first)
            periods = df[period_col].astype(str).tolist()[-8:]

            # Get key financial items with column name mappings
            if statement_type == "income":
                key_items = [
                    ("营业总收入", "TOTALOPERATEREVE", "OPERATEREVE"),
                    ("营业收入", "OPERATEREVE", "营业总收入"),
                    ("营业成本", "TOTALOPERATEEXP", "OPERATEEXP"),
                    ("净利润", "NETPROFIT", "KCFL"),
                    ("营业利润", "OPERATEPROFIT", "TOTALPROFIT"),
                ]
            elif statement_type == "balance":
                key_items = [
                    ("资产总计", "TOTALASSETS"),
                    ("负债合计", "TOTALLIABILITIES"),
                    ("股东权益合计", "EQUITYTOTAL", "归属于母公司股东权益合计"),
                    ("流动资产合计", "TOTALCURRENTASSETS"),
                    ("流动负债合计", "TOTALCURRENTLIABILITIES"),
                ]
            else:
                key_items = [
                    ("经营活动现金流量净额", "CASHFLOWOPERATE"),
                    ("投资活动现金流量净额", "CASHFLOWINVEST"),
                    ("筹资活动现金流量净额", "CASHFLOWFINANCE"),
                    ("期末现金余额", "期末现金及现金等价物余额"),
                ]

            # Extract items from dataframe
            items = []
            for item_def in key_items:
                chinese_name = item_def[0]
                candidates = list(item_def)
                col_name = None
                for candidate in candidates:
                    if candidate and candidate in df.columns:
                        col_name = candidate
                        break

                if col_name is None:
                    for col in df.columns:
                        if isinstance(col, str) and chinese_name[:2] in col:
                            col_name = col
                            break

                if col_name is not None:
                    values = df[col_name].tolist()[-8:]
                    values = [_safe_float(v) for v in values]
                    items.append({"name": chinese_name, "values": values})

            return {"status": "ok", "data": {
                "code": code,
                "name": name,
                "type": statement_type,
                "periods": periods,
                "items": items,
            }}

        except ImportError:
            logger.warning(f"获取财务报表失败 [{code}]: akshare 未安装")
            return {"status": "error", "message": "财务报表功能需要 akshare 库支持，请安装 akshare"}
        except Exception as e:
            logger.error(f"获取财务报表失败 [{code}]: {e}")
            return {"status": "error", "message": f"获取财务报表失败: {str(e)}"}

    def _handle_get_key_metrics(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """获取股票关键财务指标（PE/PB/ROE/市值/增长率等）"""
        code = req.get("code")
        if not code:
            return {"status": "error", "message": "缺少股票代码 code 参数"}

        try:
            fetcher = FinancialDataFetcher()
            data = fetcher.get_key_metrics(code)
            if data is None:
                return {"status": "error", "message": f"获取 {code} 关键指标失败: 无数据"}
            return {"status": "ok", "data": data}
        except ImportError:
            logger.warning(f"获取关键指标失败 [{code}]: akshare 未安装")
            return {"status": "error", "message": "关键指标功能需要 akshare 库支持，请安装 akshare"}
        except Exception as e:
            logger.error(f"获取关键指标失败 [{code}]: {e}")
            return {"status": "error", "message": f"获取关键指标失败: {str(e)}"}

    # ============================================================
    # P6-4: Market Review & Overview
    # ============================================================

    def _handle_get_market_overview(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Get current market overview (indices, sectors, breadth)."""
        try:
            from src.market_analyzer import MarketAnalyzer
            analyzer = MarketAnalyzer(search_service=None, analyzer=None)
            overview = analyzer.get_market_overview()
            return {
                "status": "ok",
                "data": {
                    "date": overview.date,
                    "indices": [
                        {"name": i.name, "change": i.change, "pct_chg": i.pct_chg}
                        for i in overview.indices
                    ] if overview.indices else [],
                    "total_stocks": overview.total_stocks,
                    "up_count": overview.up_count,
                    "down_count": overview.down_count,
                    "hot_sectors": [
                        {"name": s.name, "pct_chg": s.pct_chg}
                        for s in (overview.hot_sectors or [])
                    ],
                    "cold_sectors": [
                        {"name": s.name, "pct_chg": s.pct_chg}
                        for s in (overview.cold_sectors or [])
                    ],
                }
            }
        except Exception as e:
            logger.error(f"获取市场概览失败: {e}")
            return {"status": "error", "message": str(e)}

    def _handle_get_market_review(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Generate end-of-day market review report and save to DB (P6-2).

        Supports optional `force` param to regenerate even if today's report exists.
        """
        try:
            today = datetime.now().strftime('%Y-%m-%d')
            force = req.get("force", False)

            # Check if today's report already exists (cache)
            if not force:
                try:
                    db = get_db()
                    with db.get_session() as session:
                        existing = session.query(MarketReview).filter(
                            MarketReview.review_date == today
                        ).first()
                        if existing:
                            return {
                                "status": "ok",
                                "report": existing.report_md,
                                "review_date": today,
                                "cached": True,
                            }
                except Exception:
                    pass

            # Build MarketAnalyzer with configured AI provider
            from src.market_analyzer import MarketAnalyzer
            from src.analyzer import GeminiAnalyzer

            ai_analyzer = GeminiAnalyzer()
            if not ai_analyzer.is_available():
                ai_analyzer = None

            market_analyzer = MarketAnalyzer(
                search_service=None,
                analyzer=ai_analyzer,
            )
            report = market_analyzer.run_market_review()

            if not report:
                return {"status": "error", "message": "生成复盘报告失败（数据获取异常）"}

            # Extract short summary
            summary = report[:200].replace("#", "").replace("*", "").strip()

            # Save to DB
            try:
                db = get_db()
                with db.get_session() as session:
                    review = MarketReview(
                        review_date=today,
                        report_md=report,
                        market_summary=summary,
                    )
                    session.add(review)
                    session.commit()
                logger.info(f"Market review saved to DB for {today}")
            except Exception as e:
                logger.warning(f"Failed to save market review to DB: {e}")

            # Send notification
            try:
                from src.notification import NotificationService
                ns = NotificationService()
                ns.send(f"🎯 大盘复盘 {today}\n\n{summary}...")
            except Exception:
                pass

            return {
                "status": "ok",
                "report": report,
                "review_date": today,
                "cached": False,
            }
        except Exception as e:
            logger.error(f"生成市场复盘报告失败: {e}")
            return {"status": "error", "message": str(e)}

    def _handle_get_market_reviews_history(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve historical market review reports (P6-2)."""
        try:
            limit = req.get("limit", 10)
            db = get_db()
            with db.get_session() as session:
                reviews = session.query(MarketReview).order_by(
                    MarketReview.review_date.desc()
                ).limit(limit).all()
                return {
                    "status": "ok",
                    "data": [
                        {"review_date": r.review_date, "summary": r.market_summary, "report": r.report_md}
                        for r in reviews
                    ],
                }
        except Exception as e:
            logger.error(f"查询历史复盘失败: {e}")
            return {"status": "error", "message": str(e)}

    # === P6-2: Scheduled Market Review ===

    def _start_scheduled_market_review(self):
        """Start a background thread that runs market review at configured time."""
        import threading

        def _schedule_loop():
            import time
            last_run_date: Optional[str] = None

            while self._running:
                try:
                    config = get_config()
                    if not config.market_review_enabled:
                        time.sleep(60)
                        continue

                    now = datetime.now()
                    today = now.strftime('%Y-%m-%d')

                    # Parse schedule time
                    try:
                        hour, minute = map(int, config.schedule_time.split(':'))
                    except (ValueError, AttributeError):
                        hour, minute = 15, 30

                    # Check if it's time to run and hasn't run today
                    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

                    if now >= target and last_run_date != today:
                        logger.info(f"⏰ Scheduled market review triggered at {now.strftime('%H:%M')}")
                        try:
                            result = self._handle_get_market_review({"force": True})
                            if result.get("status") == "ok":
                                last_run_date = today
                                logger.info(f"✅ Scheduled market review completed for {today}")
                            else:
                                logger.warning(f"Scheduled market review failed: {result.get('message', 'unknown')}")
                        except Exception as e:
                            logger.error(f"Scheduled market review error: {e}")

                    time.sleep(60)
                except Exception as e:
                    logger.error(f"Scheduler loop error: {e}")
                    time.sleep(60)

        t = threading.Thread(target=_schedule_loop, daemon=True, name="market-review-scheduler")
        t.start()
        logger.info(
            f"Market review scheduler started (enabled={get_config().market_review_enabled}, time={get_config().schedule_time})"
        )

    def _start_bot(self):
        """Start bot polling loop if configured (P6-4)."""
        config = get_config()
        if not config.bot_enabled:
            return
        if not config.telegram_bot_token:
            logger.info("No Telegram bot token configured, skipping bot")
            return
        try:
            from src.bot.dispatcher import build_dispatcher, BotRunner
            dispatcher = build_dispatcher(self)
            self._bot_runner = BotRunner(dispatcher, config)
            self._bot_runner.start()
            logger.info("Bot runner started (Telegram polling)")
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")


    # === P7-3: EventBus Integration ===

    # === P7-5: Strategy Optimization ===

    def _handle_optimize_strategy(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Optimize strategy hyperparameters (P7-5)."""
        strategy_name = req.get("strategy", "ma_cross")
        code = req.get("code", "600519")
        days = req.get("days", 120)
        n_trials = req.get("trials", 30)

        try:
            from src.strategies.optimizer import HyperOptimizer
            from src.strategies import get_python_strategy

            strategy_cls = type(get_python_strategy(strategy_name))
            if strategy_cls is None:
                return {"status": "error", "message": f"策略 '{strategy_name}' 不存在"}

            # Get history data
            history_result = self._handle_get_history({"code": code, "days": days})
            if history_result.get("status") != "ok":
                return history_result

            history_data = history_result.get("data", [])
            if len(history_data) < 30:
                return {"status": "error", "message": "历史数据不足（需要至少30天）"}

            opt = HyperOptimizer()
            result = opt.optimize(strategy_cls, history_data, n_trials=n_trials)

            return {
                "status": "ok",
                "data": result.to_dict(),
            }
        except Exception as e:
            logger.error(f"Strategy optimization failed: {e}")
            return {"status": "error", "message": str(e)}

    # === P7-3: EventBus Integration ===

    # === P7-4: Plugin Manager Handlers ===

    def _handle_list_plugins(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """List all registered plugins (P7-4)."""
        try:
            from src.plugin_manager import list_all_plugins
            domain = req.get("domain")
            plugins = list_all_plugins()
            if domain:
                plugins = [p for p in plugins if p["domain"] == domain]
            return {"status": "ok", "data": plugins}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _handle_get_plugin_info(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Get plugin details (P7-4)."""
        try:
            from src.plugin_manager import get_plugin_manager
            pm = get_plugin_manager()
            domain = req.get("domain", "")
            name = req.get("name", "")
            plugins = pm.get_domain_plugins(domain)
            info = plugins.get(name)
            return {"status": "ok", "data": str(info)[:500] if info else None}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def _init_event_bus(self):
        """Wire internal handlers to EventBus for decoupled communication."""
        from src.event_bus import get_event_bus, StandardEvents
        bus = get_event_bus()

        def on_market_refreshed(event_type, data):
            logger.debug(f"[EventBus] market.refreshed")
        bus.subscribe(StandardEvents.MARKET_REFRESHED, on_market_refreshed, priority=90)

        def on_analysis_complete(event_type, data):
            if data:
                logger.info(f"[EventBus] analysis.completed: {data.get('code', '?')}")
        bus.subscribe(StandardEvents.ANALYSIS_COMPLETED, on_analysis_complete, priority=60)

        def on_alert_triggered(event_type, data):
            if data:
                logger.info(f"[EventBus] alert.triggered: {data.get('stock', '?')}")
        bus.subscribe(StandardEvents.ALERT_TRIGGERED, on_alert_triggered, priority=70)

        def on_shutdown(event_type, data):
            bus.shutdown()
        bus.subscribe(StandardEvents.SYSTEM_SHUTDOWN, on_shutdown, priority=100)


    # === Existing Helper Methods ===

    def _send(self, data: Dict[str, Any]):
        """发送 JSON 到 stdout"""
        print(json.dumps(data), flush=True)

    # === Strategy Import/Export Handlers ===

    def _get_strategy_path(self, name: str) -> Path:
        """Get file path for a strategy name (sanitized)."""
        safe_name = "".join(c for c in name if c.isalnum() or c in " _-").rstrip()
        if not safe_name:
            safe_name = "unnamed"
        return self._strategies_dir / f"{safe_name}.json"

    def _load_all_strategies(self) -> List[Dict[str, Any]]:
        """Load all strategy files from the strategies directory."""
        strategies = []
        if not self._strategies_dir.exists():
            return strategies
        for file_path in sorted(self._strategies_dir.glob("*.json")):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["_filename"] = file_path.name
                strategies.append(data)
            except (json.JSONDecodeError, OSError) as e:
                logger.warning(f"Failed to load strategy file {file_path}: {e}")
        return strategies

    def _handle_export_strategy(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Export current backtest configuration as a strategy JSON file."""
        name = req.get("name", "").strip()
        if not name:
            return {"status": "error", "message": "missing strategy name parameter"}

        strategy = {
            "name": name,
            "version": req.get("version", "1.0"),
            "description": req.get("description", ""),
            "author": req.get("author", ""),
            "params": req.get("params", {
                "fast_ma": 5,
                "slow_ma": 20,
                "initial_capital": 100000,
                "stop_loss_pct": -5.0,
            }),
            "code": req.get("code", "python"),
            "indicators": req.get("indicators", ["ma5", "ma20"]),
            "entry_rule": req.get("entry_rule", ""),
            "exit_rule": req.get("exit_rule", ""),
        }

        file_path = self._get_strategy_path(name)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(strategy, f, ensure_ascii=False, indent=2)
            return {"status": "ok", "data": strategy, "message": f"Strategy '{name}' exported"}
        except OSError as e:
            logger.error(f"Failed to export strategy '{name}': {e}")
            return {"status": "error", "message": f"Export failed: {str(e)}"}

    def _handle_import_strategy(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Import a strategy from JSON data (string or dict)."""
        data = req.get("data")
        if not data:
            return {"status": "error", "message": "missing strategy data parameter"}

        if isinstance(data, str):
            try:
                strategy = json.loads(data)
            except json.JSONDecodeError as e:
                return {"status": "error", "message": f"JSON parse failed: {str(e)}"}
        elif isinstance(data, dict):
            strategy = data
        else:
            return {"status": "error", "message": "data must be JSON string or dict"}

        name = strategy.get("name", "").strip()
        if not name:
            return {"status": "error", "message": "strategy data missing name field"}

        strategy.setdefault("version", "1.0")
        strategy.setdefault("description", "")
        strategy.setdefault("author", "")
        strategy.setdefault("params", {})
        strategy.setdefault("code", "python")
        strategy.setdefault("indicators", [])
        strategy.setdefault("entry_rule", "")
        strategy.setdefault("exit_rule", "")

        file_path = self._get_strategy_path(name)
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(strategy, f, ensure_ascii=False, indent=2)
            return {"status": "ok", "data": strategy, "message": f"Strategy '{name}' imported"}
        except OSError as e:
            logger.error(f"Failed to import strategy '{name}': {e}")
            return {"status": "error", "message": f"Import failed: {str(e)}"}

    def _handle_list_strategies(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """List all saved strategies."""
        try:
            # 加载 JSON 策略文件
            json_strategies = self._load_all_strategies()

            # P6-1: 合并 Python 内置策略
            from src.strategies.builtin import BUILTIN_STRATEGIES
            builtin_list = []
            for cls in BUILTIN_STRATEGIES:
                instance = cls()
                builtin_list.append({
                    "name": instance.name,
                    "display_name": instance.display_name,
                    "description": instance.description,
                    "category": instance.category,
                    "params": instance.get_params(),
                    "type": "python",
                })

            return {
                "status": "ok",
                "data": builtin_list + json_strategies,
            }
        except Exception as e:
            logger.error(f"Failed to list strategies: {e}")
            return {"status": "error", "message": f"List failed: {str(e)}"}

    def _handle_delete_strategy(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Delete a saved strategy by name."""
        name = req.get("name", "").strip()
        if not name:
            return {"status": "error", "message": "missing strategy name parameter"}

        file_path = self._get_strategy_path(name)
        if not file_path.exists():
            return {"status": "error", "message": f"Strategy '{name}' not found"}

        try:
            file_path.unlink()
            return {"status": "ok", "message": f"Strategy '{name}' deleted"}
        except OSError as e:
            logger.error(f"Failed to delete strategy '{name}': {e}")
            return {"status": "error", "message": f"Delete failed: {str(e)}"}

    def _handle_list_providers(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """列出所有已注册的数据源插件"""
        from src.data_provider.plugin import ProviderRegistry
        market = req.get("market", "ALL")
        registry = ProviderRegistry.get_instance()
        providers = registry.list_providers(market)
        return {
            "status": "ok",
            "data": [
                {
                    "name": p.name,
                    "priority": p.priority,
                    "market": p.market,
                    "available": p.is_available(),
                }
                for p in providers
            ],
        }

    def _handle_get_theme(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Get current theme and color palette."""
        from src.shared.theme import get_current_theme
        config = get_config()
        return {
            "status": "ok",
            "data": {
                "theme": config.theme,
                "colors": get_current_theme(),
            },
        }

    def _handle_set_theme(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Set theme at runtime ('dark' or 'light')."""
        theme_name = req.get("theme", "dark")
        if theme_name not in ("dark", "light"):
            return {"status": "error", "message": "theme must be 'dark' or 'light'"}
        config = get_config()
        config.theme = theme_name
        config.save_json_config({"theme": theme_name})
        return {"status": "ok", "message": f"主题已切换为 {theme_name}", "theme": theme_name}

    def _handle_get_languages(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Get available languages and current language."""
        from src.shared.i18n import get_available_languages, get_current_lang
        return {
            "status": "ok",
            "data": {
                "available": get_available_languages(),
                "current": get_current_lang(),
            },
        }

    def _handle_set_language(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Set current language at runtime."""
        from src.shared.i18n import TRANSLATIONS, get_available_languages
        lang = req.get("language", "zh")
        if lang not in TRANSLATIONS:
            return {"status": "error", "message": f"不支持的语言: {lang}"}
        config = get_config()
        config.language = lang
        config.save_json_config({"language": lang})
        return {"status": "ok", "message": f"语言已切换为 {get_available_languages()[lang]}"}

    def _handle_get_config(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Get current application configuration.

        If a specific 'key' is provided, returns only that config value.
        Otherwise returns all UI-serializable config fields.
        """
        config = get_config()
        key = req.get("key")

        # Mapping of known config keys to their values
        config_data = {
            "theme": config.theme,
            "language": config.language,
            "schedule_enabled": config.schedule_enabled,
            "schedule_time": config.schedule_time,
            "market_review_enabled": config.market_review_enabled,
            "report_type": config.report_type,
            "single_stock_notify": config.single_stock_notify,
            "analysis_delay": config.analysis_delay,
            "max_workers": config.max_workers,
            "debug": config.debug,
            "mode": config.mode,
            "indicators": config.indicators,
            "chart_draw_support_resistance": config.chart_draw_support_resistance,
            "chart_draw_fibonacci": config.chart_draw_fibonacci,
            "keybindings": config.keybindings,
            "schedule_refresh_enabled": config.schedule_refresh_enabled,
            "schedule_refresh_time": config.schedule_refresh_time,
            "data_provider_plugins": config.data_provider_plugins,
            "stock_list": config.stock_list,
            "log_dir": config.log_dir,
            "log_level": config.log_level,
        }

        if key:
            if key not in config_data:
                return {"status": "error", "message": f"Unknown config key: {key}"}
            return {"status": "ok", "data": {key: config_data[key]}}

        return {"status": "ok", "data": config_data}

    def _handle_update_config(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Update application configuration at runtime.

        Supported keys: theme, language, schedule_time, report_type,
        single_stock_notify, mode, analysis_delay, max_workers, debug,
        schedule_enabled, market_review_enabled, indicators,
        chart_draw_support_resistance, chart_draw_fibonacci,
        schedule_refresh_enabled, schedule_refresh_time.
        """
        config = get_config()
        key = req.get("key")
        value = req.get("value")

        if not key:
            return {"status": "error", "message": "缺少 key 参数"}
        if value is None:
            return {"status": "error", "message": "缺少 value 参数"}

        # Map of writable config keys: (attribute, should_save_to_json)
        writable_config = {
            "theme": ("theme", True),
            "language": ("language", True),
            "schedule_time": ("schedule_time", False),
            "report_type": ("report_type", False),
            "single_stock_notify": ("single_stock_notify", False),
            "mode": ("mode", True),
            "analysis_delay": ("analysis_delay", False),
            "max_workers": ("max_workers", False),
            "debug": ("debug", False),
            "schedule_enabled": ("schedule_enabled", False),
            "market_review_enabled": ("market_review_enabled", False),
            "indicators": ("indicators", True),
            "chart_draw_support_resistance": ("chart_draw_support_resistance", True),
            "chart_draw_fibonacci": ("chart_draw_fibonacci", True),
            "schedule_refresh_enabled": ("schedule_refresh_enabled", False),
            "schedule_refresh_time": ("schedule_refresh_time", False),
        }

        if key not in writable_config:
            return {"status": "error", "message": f"不支持的配置项: {key}"}

        attr_name, save_to_json = writable_config[key]

        # Validate specific keys
        if key == "theme" and value not in ("dark", "light"):
            return {"status": "error", "message": "theme 必须是 'dark' 或 'light'"}

        if key == "language":
            from src.shared.i18n import TRANSLATIONS
            if value not in TRANSLATIONS:
                return {"status": "error", "message": f"不支持的语言: {value}"}

        if key == "report_type" and value not in ("simple", "full"):
            return {"status": "error", "message": "report_type 必须是 'simple' 或 'full'"}

        # Update the config attribute
        setattr(config, attr_name, value)

        # Persist if applicable
        if save_to_json:
            config.save_json_config({key: value})
        else:
            config.save_to_env({key.upper(): str(value)})

        return {"status": "ok", "message": f"配置已更新: {key} = {value}"}

    def _handle_search_knowledge(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """P5-6: Search historical analysis knowledge base via FTS5 full-text index.

        Expected request fields:
            query (required): FTS5 search query string.
            code (optional): Stock code filter.
            limit (optional, default 5): Max results to return.
        """
        query = req.get("query", "")
        if not query:
            return {"status": "error", "message": "缺少 query 参数"}

        code = req.get("code")
        limit = req.get("limit", 5)
        try:
            limit = int(limit)
        except (ValueError, TypeError):
            limit = 5

        db = get_db()
        results = db.search_analyses(query=query, code=code, limit=limit)
        return {"status": "ok", "results": results}

    # ============================================================
    # P5-10: Factor Analysis Engine Handlers
    # ============================================================

    def _handle_get_factor_value(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Get factor value for a single stock.

        Request params:
            code (required): Stock code
            factor_name (required): Factor name (pe_ratio, pb_ratio, momentum_5d,
                                    momentum_20d, volume_ratio, ma_golden_cross, rsi_14)
        """
        code = req.get("code")
        factor_name = req.get("factor_name")

        if not code:
            return {"status": "error", "message": "缺少 code 参数"}
        if not factor_name:
            return {"status": "error", "message": "缺少 factor_name 参数"}

        try:
            from src.factor_engine import get_factor_engine
            engine = get_factor_engine()
            value = engine.get_factor_value(code, factor_name)
            return {"status": "ok", "code": code, "factor_name": factor_name, "value": value}
        except Exception as e:
            logger.error(f"get_factor_value failed [{code}/{factor_name}]: {e}")
            return {"status": "error", "message": str(e)}

    def _handle_analyze_factor_ic(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze factor IC/IR and decay metrics.

        Request params:
            factor_name (required): Factor name to analyze
            start_date (optional): Analysis start date (ISO string)
            end_date (optional): Analysis end date (ISO string)
        """
        factor_name = req.get("factor_name")
        if not factor_name:
            return {"status": "error", "message": "缺少 factor_name 参数"}

        from datetime import date as date_class
        start_date = req.get("start_date")
        end_date = req.get("end_date")

        if start_date:
            try:
                start_date = date_class.fromisoformat(start_date)
            except ValueError:
                return {"status": "error", "message": f"无效的 start_date: {start_date}"}
        if end_date:
            try:
                end_date = date_class.fromisoformat(end_date)
            except ValueError:
                return {"status": "error", "message": f"无效的 end_date: {end_date}"}

        try:
            from src.factor_engine import get_factor_engine
            engine = get_factor_engine()
            result = engine.analyze_factor_ic(factor_name, start_date, end_date)
            return {"status": "ok", "data": result}
        except Exception as e:
            logger.error(f"analyze_factor_ic failed [{factor_name}]: {e}")
            return {"status": "error", "message": str(e)}

    def _handle_get_factor_rankings(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """Get factor rankings across all stocks.

        Request params:
            factor_name (required): Factor name to rank
            date (optional): Ranking date (ISO string), defaults to today
            top_n (optional): Number of top stocks to return (default 50)
        """
        factor_name = req.get("factor_name")
        if not factor_name:
            return {"status": "error", "message": "缺少 factor_name 参数"}

        from datetime import date as date_class
        ranking_date = req.get("date")
        if ranking_date:
            try:
                ranking_date = date_class.fromisoformat(ranking_date)
            except ValueError:
                return {"status": "error", "message": f"无效的 date: {ranking_date}"}

        top_n = req.get("top_n", 50)
        try:
            top_n = int(top_n)
        except (ValueError, TypeError):
            top_n = 50

        try:
            from src.factor_engine import get_factor_engine
            engine = get_factor_engine()
            rankings = engine.get_factor_rankings(factor_name, ranking_date, top_n)
            return {"status": "ok", "factor_name": factor_name, "rankings": rankings}
        except Exception as e:
            logger.error(f"get_factor_rankings failed [{factor_name}]: {e}")
            return {"status": "error", "message": str(e)}

    def _handle_research(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """P5-9: Agentic research mode - LLM-controlled multi-step research.

        Request params:
            code (required): Stock code
            topic (required): Research topic/question
            max_iterations (optional): Max tool-call iterations (default 5)
        """
        code = req.get("code")
        topic = req.get("topic")
        if not code or not topic:
            return {"status": "error", "message": "缺少 code 或 topic 参数"}

        max_iterations = req.get("max_iterations", 5)
        try:
            max_iterations = int(max_iterations)
        except (ValueError, TypeError):
            max_iterations = 5

        try:
            from src.agents.research_agent import ResearchAgent
            agent = ResearchAgent(max_iterations=max_iterations)
            report = agent.research(code, topic, context={"stock_name": req.get("name", code)})
            return {
                "status": "ok",
                "code": report.code,
                "topic": report.topic,
                "tool_calls": report.tool_calls,
                "duration_seconds": report.duration_seconds,
                "steps": [
                    {
                        "iteration": s.iteration,
                        "thinking": s.thinking,
                        "action": s.action,
                        "observation": s.observation,
                        "is_final": s.is_final,
                    }
                    for s in report.steps
                ],
                "final_report": report.final_report,
                "timestamp": report.timestamp,
            }
        except Exception as e:
            logger.error(f"research failed [{code}]: {e}")
            return {"status": "error", "message": str(e)}

    def _load_plugins(self):
        """根据配置加载外部数据源插件"""
        import importlib
        config = get_config()
        for plugin_path in config.data_provider_plugins:
            try:
                module_name, class_name = plugin_path.rsplit(".", 1)
                module = importlib.import_module(f"data_provider.{module_name}")
                provider_class = getattr(module, class_name)
                from src.data_provider.plugin import ProviderRegistry
                ProviderRegistry.get_instance().register(provider_class())
                logger.info(f"Loaded data provider plugin: {plugin_path}")
            except Exception as e:
                logger.warning(f"Failed to load plugin {plugin_path}: {e}")

    def _get_markets(self) -> List[Dict]:
        """从数据库获取行情数据"""
        try:
            db = get_db()
            markets = db.get_markets()
            return [m.to_dict() for m in markets]
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
            db = get_db()
            db.save_market(
                code=market["code"],
                name=market["name"],
                price=market["price"],
                change_pct=market["change_pct"],
                volume=market["volume"],
            )
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

        # In-app notification for price alerts
        try:
            from src.notification_center import get_notification_center
            code = market.get("code", "")
            name = market.get("name", code)
            chg = market.get("change_pct", 0)
            price_val = market.get("price", 0)
            level = "warning" if abs(chg) > 5 else "info"
            direction = "上涨" if chg > 0 else "下跌"
            get_notification_center().notify(
                title=f"价格异动: {name}({code})",
                message=f"{direction} {abs(chg):.2f}%  当前价: {price_val:.2f}",
                level=level,
                category="price_alert",
                action="markets",
            )
        except Exception:
            pass

    # ============================================================
    # Network Degradation Fallback
    # ============================================================

    def _fetch_with_fallback(self, code: str, fetch_fn: callable) -> Dict[str, Any]:
        """
        尝试获取数据，失败时回退到缓存

        Args:
            code: 股票代码
            fetch_fn: 获取数据的函数，签名 () -> Dict[str, Any]

        Returns:
            (data, is_cached, is_stale, cache_age)
        """
        cache = get_market_cache()

        try:
            # 尝试获取实时数据
            data = fetch_fn()

            # 保存到缓存
            if data and data.get("price"):
                cache.set(code, data, data.get("_source", "unknown"))

            return data, False, False, 0

        except Exception as e:
            logger.warning(f"获取 {code} 数据失败，尝试缓存 fallback: {e}")

            # 尝试从缓存获取
            cached_data, is_stale, age = cache.get_with_staleness(code)

            if cached_data:
                logger.info(f"使用缓存数据 for {code} (age: {age:.0f}s, stale: {is_stale})")
                return cached_data, True, is_stale, age
            else:
                # 没有缓存数据
                raise Exception(f"无法获取 {code} 数据，且无缓存可用")

    def _fetch_market_data(self, code: str) -> Dict[str, Any]:
        """使用降级策略获取市场数据"""
        from data_provider.efinance_fetcher import EfinanceFetcher

        def fetch_live():
            fetcher = EfinanceFetcher()
            df = fetcher.get_daily_data(code, days=1)
            if df is None or len(df) == 0:
                raise Exception("No data returned")
            latest = df.iloc[-1]
            return {
                "code": code,
                "name": latest.get("name", ""),
                "price": latest.get("close", 0),
                "change_pct": latest.get("pct_chg", 0),
                "volume": latest.get("volume", 0),
                "_source": "EfinanceFetcher",
            }

        data, is_cached, is_stale, cache_age = self._fetch_with_fallback(code, fetch_live)

        if is_cached and is_stale:
            data["_warning"] = f"数据可能过时（缓存于 {cache_age:.0f}秒前）"

        return data

    # ============================================================
    # AI API 429 Retry with Circuit Breaker
    # (state is initialized in __init__ as self._ai_provider_state)
    # ============================================================

    def _analyze_with_retry(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        AI 分析带指数退避重试和 circuit breaker

        策略：
        1. 429 时指数退避：60s -> 300s -> ...
        2. 连续 3 次 429 后禁用 provider 30 分钟
        3. retry_count 记录重试次数
        """
        from src.analyzer import GeminiAnalyzer

        state = self._ai_provider_state
        now = time.time()

        # 检查 provider 是否被禁用
        if state["disabled_until"] > now:
            wait_time = state["disabled_until"] - now
            logger.warning(f"AI provider 已被禁用，还需等待 {wait_time:.0f}秒")
            return {
                "status": "error",
                "message": f"AI provider 限流中，请等待 {wait_time:.0f}秒",
                "retry_count": 0,
            }

        analyzer = GeminiAnalyzer()
        max_retries = 5

        for attempt in range(max_retries):
            try:
                result = analyzer.analyze(context, news_context=None)

                # 成功后重置 429 计数
                state["429_count"] = 0

                return {
                    "status": "ok" if result.success else "error",
                    "data": result.to_dict() if result.success else None,
                    "error_message": result.error_message,
                    "retry_count": attempt,
                    "provider": state["current_provider"],
                }

            except Exception as e:
                error_str = str(e)
                is_429 = "429" in error_str or "rate" in error_str.lower() or "quota" in error_str.lower()

                if is_429:
                    state["429_count"] += 1
                    state["last_429_time"] = now

                    # 连续 3 次 429，启用 circuit breaker
                    if state["429_count"] >= 3:
                        state["disabled_until"] = now + 1800  # 30 minutes
                        logger.error(f"AI API 连续 429，禁用 30 分钟")
                        return {
                            "status": "error",
                            "message": "AI provider 限流严重，30分钟内不可用",
                            "retry_count": attempt,
                            "429_count": state["429_count"],
                        }

                    # 指数退避：60s, 300s, 600s, ...
                    if attempt == 0:
                        wait_time = 60
                    elif attempt == 1:
                        wait_time = 300
                    else:
                        wait_time = min(600, 60 * (2 ** attempt))

                    logger.warning(f"AI API 429，第 {attempt + 1} 次重试，等待 {wait_time}秒")
                    time.sleep(wait_time)
                else:
                    # 非 429 错误，直接抛出
                    raise

        # 所有重试都失败
        return {
            "status": "error",
            "message": f"AI 分析失败，已重试 {max_retries} 次",
            "retry_count": max_retries,
        }

    # ============================================================
    # Heartbeat for Watchdog
    # ============================================================

    def _send_heartbeat(self):
        """发送心跳信号（用于外部 watchdog 检测）"""
        self._send({
            "type": "heartbeat",
            "timestamp": datetime.now().isoformat(),
            "running": self._running,
        })

    # ============================================================
    # WebSocket IPC Server
    # ============================================================

    def run_ws_server(self, host: str = "127.0.0.1", port: int = 9876):
        """
        Run DataService as a WebSocket server.

        Each connected client sends JSON request lines and receives JSON responses.
        The action registry (same as stdio mode) dispatches requests to handlers.
        Market data updates are broadcast to all connected clients every 30 seconds.
        """
        import asyncio

        try:
            import websockets
            from websockets.asyncio.server import serve
        except ImportError:
            logger.error(
                "websockets library is required for WebSocket server mode. "
                "Install it with: pip install websockets"
            )
            return 1

        connected = set()

        async def handle_client(websocket):
            """Handle a single WebSocket client connection."""
            connected.add(websocket)
            logger.info(f"WebSocket client connected (total: {len(connected)})")
            try:
                async for raw_message in websocket:
                    if not self._running:
                        break
                    try:
                        req = json.loads(raw_message)
                    except json.JSONDecodeError:
                        await websocket.send(json.dumps({"status": "error", "message": "invalid json"}))
                        continue

                    # Streaming actions get special treatment: they write
                    # multiple messages back to the WebSocket.
                    if req.get("action") == "analyze_stream":
                        try:
                            await self._handle_analyze_stream_ws(websocket, req)
                        except Exception as e:
                            logger.error(f"WS stream error: {e}")
                            try:
                                await websocket.send(json.dumps({
                                    "type": "stream_error",
                                    "message": str(e),
                                }, ensure_ascii=False, default=str))
                            except Exception:
                                break
                        continue

                    # _handle_request blocks (thread pool + future.result()),
                    # so run it in a thread to avoid blocking the event loop
                    try:
                        resp = await asyncio.to_thread(self._handle_request, req)
                    except Exception as e:
                        logger.error(f"WS request error: {e}")
                        resp = {"status": "error", "message": str(e)}
                    try:
                        await websocket.send(json.dumps(resp, ensure_ascii=False, default=str))
                    except Exception:
                        break  # Client disconnected, exit message loop
            except Exception:
                pass  # Client disconnected
            finally:
                connected.discard(websocket)
                logger.info(f"WebSocket client disconnected (total: {len(connected)})")

        async def broadcast_loop():
            """Periodically broadcast market data to all connected clients."""
            while self._running:
                await asyncio.sleep(30)
                if not connected:
                    continue
                try:
                    markets = self._get_markets()
                    msg = json.dumps(
                        {"type": "market_update", "data": markets},
                        ensure_ascii=False,
                        default=str,
                    )
                    stale = set()
                    for ws in connected:
                        try:
                            await ws.send(msg)
                        except Exception:
                            stale.add(ws)
                    connected.difference_update(stale)
                except Exception as e:
                    logger.error(f"Broadcast error: {e}")

        async def serve_forever():
            async with serve(handle_client, host, port) as server:
                logger.info(f"WebSocket server listening on ws://{host}:{port}")
                broadcast_task = asyncio.create_task(broadcast_loop())
                try:
                    while self._running:
                        await asyncio.sleep(1)
                finally:
                    broadcast_task.cancel()
                    try:
                        await broadcast_task
                    except asyncio.CancelledError:
                        pass
                logger.info("WebSocket server stopped")

        try:
            asyncio.run(serve_forever())
        except KeyboardInterrupt:
            logger.info("WebSocket server interrupted")

        return 0

    # ============================================================
    # Main Run Loop (stdio mode)
    # ============================================================

    def _run_ws_server_sync(self, host: str = "127.0.0.1", port: int = 9876):
        """
        Run the WebSocket server in a daemon thread.

        This method blocks forever (or until self._running becomes False).
        It calls run_ws_server() which creates its own asyncio event loop.
        """
        try:
            self.run_ws_server(host=host, port=port)
        except Exception as e:
            logger.error(f"WebSocket server thread error: {e}")

    def _start_ws_server(self):
        """
        Start the WebSocket IPC server in a background daemon thread.

        Reads ws_server_host and ws_server_port from config.
        Logs a warning and returns silently if websockets is not installed.
        """
        try:
            import websockets  # noqa: F401
        except ImportError:
            logger.info("websockets not installed, WebSocket server disabled")
            return

        config = get_config()
        host = config.ws_server_host
        port = config.ws_server_port
        ws_thread = threading.Thread(
            target=self._run_ws_server_sync,
            args=(host, port),
            daemon=True,
            name="ws-server",
        )
        ws_thread.start()
        logger.info(f"WebSocket server started on ws://{host}:{port} (background thread)")

    # === P7-2: Targeted Push ===

    def _ws_push_event(self, event_type: str, data: Any) -> None:
        """Push an event to all connected WebSocket clients.

        Used by handlers to notify clients of async events
        (analysis complete, alert triggered, market review ready, etc.)
        without requiring polling.

        Args:
            event_type: Event type string (e.g. "analysis_complete", "alert_triggered").
            data: Event payload (dict or serializable object).
        """
        # The push is queued for the next broadcast cycle or sent immediately
        # via the broadcast loop in run_ws_server().
        # For now, we rely on the 30-second broadcast for market updates.
        # Targeted per-client push requires client identification (future enhancement).
        logger.debug(f"WS push queued: {event_type}")

    def run(self):
        """主循环：读取 stdin，处理请求，发送心跳"""
        # Start WebSocket IPC server in background daemon thread (P5-1)
        self._start_ws_server()

        last_heartbeat = time.time()
        heartbeat_interval = HEARTBEAT_INTERVAL

        while self._running:
            # 计算距上次心跳的时间
            elapsed = time.time() - last_heartbeat

            # 发送心跳（每 HEARTBEAT_INTERVAL 秒）
            if elapsed >= heartbeat_interval:
                self._send_heartbeat()
                last_heartbeat = time.time()

            # 使用非阻塞方式读取 stdin（设置超时避免 busy loop）
            import select
            if select.select([sys.stdin], [], [], 0.5)[0]:
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
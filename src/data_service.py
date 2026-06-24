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
# Error model: handlers raise DataServiceError for known/expected
# failures (validation, not-found, upstream 4xx). Anything else is
# treated as a bug: we log the traceback with a request_id and
# return a sanitized message so internal details (file paths, SQL,
# env vars) never leak to the GUI client.
# ============================================================


class DataServiceError(Exception):
    """Base class for known/expected errors that should be surfaced to clients.

    Subclasses map to stable error codes so the GUI can branch on them
    without parsing English messages.
    """

    code: str = "internal_error"

    def __init__(self, message: str, *, code: str | None = None, http_status: int | None = None):
        super().__init__(message)
        if code is not None:
            self.code = code
        self.http_status = http_status


class BadRequestError(DataServiceError):
    code = "bad_request"


class NotFoundError(DataServiceError):
    code = "not_found"


class UpstreamError(DataServiceError):
    code = "upstream_error"


class TimeoutError_(DataServiceError):  # noqa: A001  (shadows builtin on purpose)
    code = "timeout"


import uuid as _uuid
import traceback as _traceback


def _safe_call(handler, req: Dict[str, Any]) -> Dict[str, Any]:
    """Invoke a handler with structured error handling.

    Returns:
        dict with at least {"status": "ok"|"error"}.
        On error: also includes "code" (stable id) and "message" (safe for UI).
        On unexpected exception: includes "request_id" that can be grepped in logs.
    """
    action = req.get("action", "?")
    try:
        return handler(req)
    except DataServiceError as e:
        logger.warning(f"[{action}] known error ({e.code}): {e}")
        return {
            "status": "error",
            "code": e.code,
            "message": str(e),
        }
    except Exception as e:
        request_id = _uuid.uuid4().hex[:12]
        logger.error(
            f"[{action}] unexpected error (request_id={request_id}): {e}",
            exc_info=True,
        )
        return {
            "status": "error",
            "code": "internal_error",
            "message": f"内部错误，请稍后重试（request_id={request_id}）",
            "request_id": request_id,
        }


# ============================================================
# Request Timeout and Thread Pool Configuration
# ============================================================
REQUEST_TIMEOUT_SECONDS = 30  # Default timeout per request

# Maximum bytes we'll accept for a single IPC request frame. Real client
# payloads are < 100 KB; 1 MB is a hard ceiling to prevent a misbehaving
# or hostile client from making us allocate gigabytes via readline().
MAX_REQUEST_BYTES = 1 * 1024 * 1024  # 1 MB
MAX_ACTION_LENGTH = 64
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
        self._current_request_id: Optional[str] = None
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
        # Handler 注册表 — 由 src.handlers.register_all() 填充。
        # 每个 src/handlers/<domain>.py 的 register() 会同时挂 service._handle_X
        # 实例属性（通过 functools.partial(fn, service)）+ 写入 _actions dict。
        # dispatch 路径见 _handle_request：getattr(self, _actions[action])(req)。
        self._actions: Dict[str, str] = {}

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

        # Handler 域拆分（P0-4 迁移）：各 src/handlers/<domain>.py 模块的
        # register() 会把 module-level 函数挂为 service 实例属性，并覆盖
        # service._actions dict 同名条目。dispatch 路径（_handle_request）
        # 保持不变——getattr(self, _actions[action]) 先命中实例属性。
        from src.handlers import register_all
        register_all(self)

    def _is_demo_mode(self) -> bool:
        """Check if the service is running in demo mode (reads config live)."""
        return get_config().is_demo_mode()

    def _handle_request(self, req: Dict[str, Any]) -> Dict[str, Any]:
        """根据 action 分发到对应 handler with timeout + sanitized error."""
        action = req.get("action", "")

        if action not in self._actions:
            return {
                "status": "error",
                "code": "bad_request",
                "message": f"不支持的操作: {action}",
            }

        handler_name = self._actions[action]
        handler: ActionHandler = getattr(self, handler_name)

        timeout = req.get("_timeout", REQUEST_TIMEOUT_SECONDS)
        future = self._executor.submit(_safe_call, handler, req)

        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError:
            logger.warning(f"请求 {action} 超时（{timeout}秒）")
            return {
                "status": "error",
                "code": "timeout",
                "message": f"请求超时（{timeout}秒）",
            }
        # Anything raised from _safe_call itself (shouldn't happen) is a bug.
        except Exception as e:
            request_id = _uuid.uuid4().hex[:12]
            logger.error(
                f"[{action}] dispatcher error (request_id={request_id}): {e}",
                exc_info=True,
            )
            return {
                "status": "error",
                "code": "internal_error",
                "message": f"内部错误（request_id={request_id}）",
                "request_id": request_id,
            }

    # === Existing Handlers ===

    def _get_recent_prices(self, code: str, days: int = 10) -> List[float]:
        """Get recent closing prices for sparkline."""
        try:
            db = get_db()
            data = db.get_latest_data(code, days=days)
            return [d.close for d in reversed(data)] if data else []
        except Exception:
            return []

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
            from src.notify import NotificationService
            notifier = NotificationService()
            message = f"📊 {result.name}({code}) 分析完成: {result.operation_advice} (评分: {result.sentiment_score})"
            notifier.send(message)
        except Exception as e:
            logger.warning(f"发送分析通知失败: {e}")

    # ============================================================
    # P5-5: Deep Analysis Handler
    # ============================================================

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
            from src.notify import NotificationService
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
            from src.notify import NotificationService
            notifier = NotificationService()
            message = f"\U0001f6a8 {market['code']} 异动: {market['change_pct']:+.2f}% (价格: {market['price']})"
            results = notifier.send(message)
            if any(r.success for r in results):
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
        """主循环：读取 stdin，处理请求，发送心跳

        协议：每行一条 JSON 请求。读取时强制字节上限 (MAX_REQUEST_BYTES)，
        防止恶意/异常 client 用超长单行撑爆内存。
        """
        # Start WebSocket IPC server in background daemon thread (P5-1)
        self._start_ws_server()

        last_heartbeat = time.time()
        heartbeat_interval = HEARTBEAT_INTERVAL

        while self._running:
            elapsed = time.time() - last_heartbeat
            if elapsed >= heartbeat_interval:
                self._send_heartbeat()
                last_heartbeat = time.time()

            import select
            ready, _, _ = select.select([sys.stdin], [], [], 0.5)
            if not ready:
                continue

            frame = self._read_request_frame()
            if frame is None:
                # EOF or fatal protocol error; loop will exit on next iteration.
                if not self._running:
                    break
                continue

            try:
                req = json.loads(frame)
            except json.JSONDecodeError:
                self._send({"status": "error", "code": "bad_request", "message": "invalid json"})
                continue

            if not isinstance(req, dict):
                self._send({"status": "error", "code": "bad_request", "message": "request must be a JSON object"})
                continue

            # Propagate the client-supplied request_id so the client can
            # correlate responses when it pipelines multiple requests.
            request_id = req.get("request_id")
            if isinstance(request_id, str) and len(request_id) <= 64:
                self._current_request_id = request_id
            else:
                self._current_request_id = None

            try:
                resp = self._handle_request(req)
            except Exception:
                # Defence-in-depth: _handle_request already wraps handlers in
                # _safe_call, so reaching here is a bug. Log and return a
                # sanitized error rather than crashing the daemon.
                request_id = _uuid.uuid4().hex[:12]
                logger.exception("未捕获异常 in _handle_request")
                resp = {
                    "status": "error",
                    "code": "internal_error",
                    "message": f"内部错误（request_id={request_id}）",
                    "request_id": request_id,
                }
            finally:
                self._current_request_id = None

            if self._current_request_id:
                resp["request_id"] = self._current_request_id
            self._send(resp)

    def _read_request_frame(self) -> Optional[bytes]:
        """Read exactly one newline-terminated request frame, capped at MAX_REQUEST_BYTES.

        Returns:
            The frame bytes (without the trailing newline) on success.
            None on EOF or on protocol violation; the caller decides whether
            to shut down or continue.
        """
        buf = bytearray()
        while True:
            chunk = sys.stdin.buffer.read1(4096) if hasattr(sys.stdin.buffer, "read1") else sys.stdin.buffer.read(4096)
            if not chunk:
                # EOF
                if buf:
                    logger.warning("stdin 在帧中间关闭，丢弃部分数据")
                self._running = False
                return None
            buf.extend(chunk)
            # Newline-terminated frame?
            nl = buf.find(b"\n")
            if nl != -1:
                frame = bytes(buf[:nl])
                # Push the rest back to stdin for the next iteration.
                # (Python's stdin is a buffered text stream; we don't try to
                # push back bytes — instead we leave them in the buffer for
                # the next read1() call. The newline frame delimiter is
                # the contract.)
                return frame
            if len(buf) > MAX_REQUEST_BYTES:
                # Drain until newline so the next frame can be parsed.
                logger.warning(
                    f"收到的请求超过 {MAX_REQUEST_BYTES} 字节上限，已丢弃"
                )
                # Consume up to the next newline so we stay in sync.
                sys.stdin.buffer.readline()
                self._send({
                    "status": "error",
                    "code": "payload_too_large",
                    "message": f"request exceeds {MAX_REQUEST_BYTES} bytes",
                })
                return b""

if __name__ == "__main__":
    service = DataService()
    service.run()
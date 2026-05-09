"""DataService 后端守护进程"""
import json
import sys
import logging
import threading
import uuid
from datetime import datetime, date
from typing import Dict, Any, List, Optional, Callable

import sqlite3
from .config import get_config
from .alert_service import AlertService
from .storage import get_db

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
        # Initialize database via storage.py (ensures schema tables exist)
        get_db()
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

        # Persist task creation
        try:
            get_db().save_task(task_id, code, "pending")
        except Exception:
            pass  # Non-critical if DB save fails initially

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

            # 发送通知
            self._send_analysis_notification(code, result)

        except Exception as e:
            logger.error(f"AI 分析失败 [{code}]: {e}")
            with self._tasks_lock:
                if self._tasks[task_id]["status"] == "cancelled":
                    return
                self._tasks[task_id]["status"] = "failed"
                self._tasks[task_id]["error"] = str(e)
            db.save_task(task_id, code, "failed", error=str(e))

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

        try:
            # 获取历史数据
            history_result = self._handle_get_history({"code": code, "days": days})
            if history_result.get("status") != "ok":
                return history_result

            history_data = history_result.get("data", [])
            if not history_data:
                return {"status": "ok", "data": [], "message": "无历史数据"}

            # 运行回测
            from src.backtester import backtest, ma_crossover_strategy
            result = backtest(history_data, initial_capital=initial_capital, strategy_fn=ma_crossover_strategy)

            return {
                "status": "ok",
                "data": {
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

    # === Existing Helper Methods ===

    def _init_db(self):
        """Initialize DataService's legacy SQLite database (for backward compat).

        Creates the legacy markets/positions/schema_version tables.
        Note: storage.py manages the main application DB (stock_daily, analysis_history).
        """
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
        c.execute("""
            CREATE TABLE IF NOT EXISTS positions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL,
                name TEXT NOT NULL,
                shares REAL NOT NULL,
                buy_price REAL NOT NULL,
                buy_date TEXT NOT NULL,
                current_price REAL,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER NOT NULL,
                applied_at TEXT,
                description TEXT
            )
        """)
        # Record schema version if not present
        c.execute("SELECT COUNT(*) FROM schema_version")
        if c.fetchone()[0] == 0:
            c.execute("INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                       (2, datetime.now().isoformat(), "Initial schema v2"))
            logger.info("Schema version set to v2")
        conn.commit()
        conn.close()

    def _send(self, data: Dict[str, Any]):
        """发送 JSON 到 stdout"""
        print(json.dumps(data), flush=True)

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
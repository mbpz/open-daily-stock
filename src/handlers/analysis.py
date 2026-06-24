"""analysis handlers — AI 分析 + 深度分析 + 流式 + Agentic Research + task 管理。

注意：
- 后台执行的私有 helper（_run_analyze_task / _run_deep_analyze_task /
  _send_*_notification / _build_demo_deep_result）保留在 DataService 类内，因为
  它们与 self._tasks dict + self._tasks_lock 紧耦合。本模块仅迁移 dispatcher
  handler 函数，handler 通过 `service._xxx_method` 调用类方法。
- WebSocket 异步 handler (_handle_analyze_stream_ws) 仍由 DataService 类持有，
  因为它在 WS dispatcher 中以方法名 lookup（不走 _actions dict）。
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime
from functools import partial
from typing import TYPE_CHECKING, Any, Dict

from src.storage import get_db

if TYPE_CHECKING:
    from src.data_service import DataService

logger = logging.getLogger(__name__)


# ─── Analyze (single-LLM) ─────────────────────────────────────


def analyze(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """触发 AI 分析任务"""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    # Demo mode: return pre-computed analysis synchronously
    if service._is_demo_mode():
        from src.demo_data import DEMO_AI_ANALYSES
        if code in DEMO_AI_ANALYSES:
            task_id = f"demo_task_{code}_{int(datetime.now().timestamp())}"
            demo_result = DEMO_AI_ANALYSES[code]
            with service._tasks_lock:
                service._tasks[task_id] = {
                    "task_id": task_id,
                    "code": code,
                    "status": "completed",
                    "created_at": datetime.now().isoformat(),
                    "completed_at": datetime.now().isoformat(),
                    "result": demo_result,
                    "error": None,
                }
            return {"status": "ok", "task_id": task_id,
                    "message": "演示分析完成（无需 API Key）", "result": demo_result}
        else:
            return {"status": "error", "message": f"演示模式不支持该股票代码: {code}"}

    # 生成 task_id
    task_id = f"task_{uuid.uuid4().hex[:8]}_{code}_{int(datetime.now().timestamp())}"

    # 创建任务记录
    with service._tasks_lock:
        service._tasks[task_id] = {
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
        pass

    try:
        get_db().save_task_log(task_id, "analyze", code, "pending")
    except Exception as e:
        logger.warning(f"Failed to save task_log for {task_id}: {e}")

    # 异步执行分析（不阻塞 DataService）
    thread = threading.Thread(target=service._run_analyze_task, args=(task_id, code))
    thread.daemon = True
    thread.start()

    return {"status": "ok", "task_id": task_id, "message": "分析任务已创建"}


# ─── Deep Analyze (multi-agent) ───────────────────────────────


def deep_analyze(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Trigger deep multi-agent analysis task."""
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    enabled_agents_str = req.get("deep_analysis_agents", None)
    enabled_agents = None
    if enabled_agents_str:
        enabled_agents = [a.strip() for a in enabled_agents_str.split(',') if a.strip()]

    # Demo mode: return pre-computed synthetic deep analysis
    if service._is_demo_mode():
        task_id = f"deep_demo_{code}_{int(datetime.now().timestamp())}"
        demo_result = service._build_demo_deep_result(code, enabled_agents)
        with service._tasks_lock:
            service._tasks[task_id] = {
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

    with service._tasks_lock:
        service._tasks[task_id] = {
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
        target=service._run_deep_analyze_task,
        args=(task_id, code, enabled_agents),
    )
    thread.daemon = True
    thread.start()

    return {"status": "ok", "task_id": task_id, "message": "深度分析任务已创建"}


# ─── Analyze Stream (stdio fallback) ──────────────────────────


def analyze_stream(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """Streaming AI analysis action (stdio fallback).

    For stdio mode, falls back to non-streaming analyze. For WebSocket
    mode, the WS handler intercepts before reaching this dispatcher.
    """
    code = req.get("code")
    if not code:
        return {"status": "error", "message": "缺少股票代码 code 参数"}

    # Demo mode: return pre-computed analysis
    if service._is_demo_mode():
        return analyze(service, req)

    # In stdio mode, fall back to non-streaming analyze
    task_id = f"task_{uuid.uuid4().hex[:8]}_{code}_{int(datetime.now().timestamp())}"

    with service._tasks_lock:
        service._tasks[task_id] = {
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
        target=service._run_analyze_task, args=(task_id, code)
    )
    thread.daemon = True
    thread.start()

    return {"status": "ok", "task_id": task_id, "message": "分析任务已创建（非流式）"}


# ─── Research (P5-9 Agentic Mode) ─────────────────────────────


def research(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """P5-9: Agentic research mode - LLM-controlled multi-step research."""
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


# ─── Task Management ──────────────────────────────────────────


def get_tasks(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取所有任务列表"""
    with service._tasks_lock:
        tasks = []
        for task_id, task in service._tasks.items():
            tasks.append({
                "task_id": task_id,
                "code": task["code"],
                "status": task["status"],
                "created_at": task["created_at"],
                "completed_at": task.get("completed_at"),
            })
        tasks.sort(key=lambda x: x["created_at"], reverse=True)
    return {"status": "ok", "tasks": tasks}


def get_task(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """获取单个任务详情"""
    task_id = req.get("task_id")
    if not task_id:
        return {"status": "error", "message": "缺少 task_id 参数"}

    with service._tasks_lock:
        if task_id not in service._tasks:
            return {"status": "error", "message": f"任务 {task_id} 不存在"}

        task = service._tasks[task_id]
    return {"status": "ok", "task": task}


def cancel_task(service: "DataService", req: Dict[str, Any]) -> Dict[str, Any]:
    """取消任务"""
    task_id = req.get("task_id")
    if not task_id:
        return {"status": "error", "message": "缺少 task_id 参数"}

    with service._tasks_lock:
        if task_id not in service._tasks:
            return {"status": "error", "message": f"任务 {task_id} 不存在"}

        task = service._tasks[task_id]
        if task["status"] in ["completed", "failed", "cancelled"]:
            return {"status": "error", "message": f"任务已 {task['status']}，无法取消"}

        task["status"] = "cancelled"
    return {"status": "ok", "message": "任务已取消"}


# ─── Register ─────────────────────────────────────────────────


def register(service: "DataService") -> None:
    """注入到 service._actions + 用 partial 绑 service 作为首参。"""
    service._handle_analyze = partial(analyze, service)
    service._actions["analyze"] = "_handle_analyze"

    service._handle_deep_analyze = partial(deep_analyze, service)
    service._actions["deep_analyze"] = "_handle_deep_analyze"

    service._handle_analyze_stream = partial(analyze_stream, service)
    service._actions["analyze_stream"] = "_handle_analyze_stream"

    service._handle_research = partial(research, service)
    service._actions["research"] = "_handle_research"

    service._handle_get_tasks = partial(get_tasks, service)
    service._actions["get_tasks"] = "_handle_get_tasks"

    service._handle_get_task = partial(get_task, service)
    service._actions["get_task"] = "_handle_get_task"

    service._handle_cancel_task = partial(cancel_task, service)
    service._actions["cancel_task"] = "_handle_cancel_task"

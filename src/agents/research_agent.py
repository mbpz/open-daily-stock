# -*- coding: utf-8 -*-
"""
P5-9: Agentic Research Mode - LLM 自主决策多步研究

ResearchAgent uses a REPL-style loop:
    think → decide tool → call → observe → repeat (max N iterations)

Unlike P5-5's parallel agents (3 run simultaneously), P5-9 is a SINGLE agent
that iteratively uses tools to gather and analyze information.

Tools available:
- search_news: Search for news about a stock
- rag_search: Search historical analysis from FTS5 knowledge base
- get_kline_data: Get K-line OHLCV data
- get_financials: Get financial statements
- get_institutional: Get institutional investor data
- analyze_basic: Run a basic single-agent analysis

Each iteration produces a thinking log. Results stored in SQLite research_logs table.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Callable
from enum import Enum

from src.storage import get_db
from sqlalchemy import text

logger = logging.getLogger(__name__)


class ResearchAction(Enum):
    """Actions the research agent can decide to take."""
    SEARCH_NEWS = "search_news"
    RAG_SEARCH = "rag_search"
    GET_KLINE = "get_kline"
    GET_FINANCIALS = "get_financials"
    GET_INSTITUTIONAL = "get_institutional"
    ANALYZE_BASIC = "analyze_basic"
    GIVE_REPORT = "give_report"  # Final report, no more tools

    def __str__(self) -> str:
        return self.value


@dataclass
class ResearchStep:
    """A single step in the research loop."""
    iteration: int
    thinking: str          # What the agent is thinking/decided
    action: str            # Which action was taken
    tool_input: Dict[str, Any]  # Input passed to tool
    tool_output: Any       # Raw output from tool
    observation: str       # Key observation from output
    is_final: bool = False


@dataclass
class ResearchReport:
    """Final research report with all steps."""
    code: str
    topic: str
    steps: List[ResearchStep]
    final_report: str
    tool_calls: int
    duration_seconds: float
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M:%S"))


class ResearchAgent:
    """LLM-powered research agent with iterative tool-calling.

    Uses a REPL loop to research stocks by autonomously deciding
    which tools to call and in what sequence.

    Usage:
        agent = ResearchAgent()
        report = agent.research("600519", "分析贵州茅台的投资价值")
    """

    def __init__(
        self,
        max_iterations: int = 5,
        llm_callable: Optional[Callable] = None,
    ):
        """
        Args:
            max_iterations: Maximum number of tool-call iterations (default 5).
            llm_callable: LLM call function. If None, uses mock for testing.
        """
        self.max_iterations = max_iterations
        self._llm = llm_callable

    def research(
        self,
        code: str,
        topic: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ResearchReport:
        """Run agentic research for a stock on a given topic.

        Args:
            code: Stock code
            topic: Research topic/question
            context: Optional context dict (stock_name, etc.)

        Returns:
            ResearchReport with all steps and final report.
        """
        context = context or {}
        code = code.strip()
        topic = topic.strip()

        start_time = time.time()
        steps: List[ResearchStep] = []
        iteration = 0

        # Accumulated research context from all tool outputs
        accumulated_context: Dict[str, Any] = {
            "code": code,
            "stock_name": context.get("stock_name", code),
            "topic": topic,
            "tool_results": [],
        }

        logger.info(f"[ResearchAgent] Starting research for {code}: {topic}")

        while iteration < self.max_iterations:
            iteration += 1

            # Step 1: Think - decide what to do next based on accumulated context
            decision = self._decide_next_action(code, topic, accumulated_context, iteration)

            if decision["action"] == ResearchAction.GIVE_REPORT.value:
                # No more tools needed, produce final report
                break

            # Step 2: Execute the tool
            tool_name = decision["action"]
            tool_input = decision.get("input", {})
            tool_output = self._execute_tool(tool_name, tool_input, code, context)

            # Step 3: Observe - extract key observation from tool output
            observation = self._extract_observation(tool_name, tool_output)

            step = ResearchStep(
                iteration=iteration,
                thinking=decision.get("thinking", ""),
                action=tool_name,
                tool_input=tool_input,
                tool_output=tool_output,
                observation=observation,
                is_final=False,
            )
            steps.append(step)

            # Accumulate context for next iteration
            accumulated_context["tool_results"].append({
                "tool": tool_name,
                "observation": observation,
                "output": tool_output,
            })

            logger.debug(
                f"[ResearchAgent] Iteration {iteration}: {tool_name} → {observation[:50]}..."
            )

        # Final report from LLM
        final_report = self._generate_final_report(code, topic, steps)

        duration = time.time() - start_time

        # Mark last step as final
        if steps:
            steps[-1].is_final = True

        report = ResearchReport(
            code=code,
            topic=topic,
            steps=steps,
            final_report=final_report,
            tool_calls=len(steps),
            duration_seconds=duration,
        )

        # Persist to storage
        self._save_report(report)

        logger.info(
            f"[ResearchAgent] Research complete for {code}: "
            f"{len(steps)} tool calls in {duration:.1f}s"
        )

        return report

    def _decide_next_action(
        self,
        code: str,
        topic: str,
        accumulated: Dict[str, Any],
        iteration: int,
    ) -> Dict[str, Any]:
        """Decide the next action using LLM reasoning.

        Returns dict with: action, thinking, input (for tool call).
        """
        if self._llm:
            return self._llm_decide(code, topic, accumulated, iteration)
        else:
            return self._mock_decide(code, topic, accumulated, iteration)

    def _llm_decide(
        self,
        code: str,
        topic: str,
        accumulated: Dict[str, Any],
        iteration: int,
    ) -> Dict[str, Any]:
        """Use LLM to decide next action (for production)."""
        prior_results = accumulated.get("tool_results", [])

        # Build prompt for decision making
        prior_summary = self._summarize_prior_results(prior_results)

        prompt = f"""你是一个股票研究助手。用户要求："{topic}"

当前股票代码：{code}
研究进度：第 {iteration} 轮（最多 {self.max_iterations} 轮）

已有信息：
{prior_summary}

决定下一步行动。可选操作：
- search_news: 搜索新闻和公告
- rag_search: 在历史分析知识库中搜索
- get_kline: 获取K线技术数据
- get_financials: 获取财务报表数据
- get_institutional: 获取机构持仓数据
- analyze_basic: 运行基础AI分析
- give_report: 信息已足够，生成最终报告

JSON格式回复（不要加markdown）：
{{"action": "操作名", "thinking": "你的思考过程", "input": {{"参数"}}}}"""
        try:
            response = self._llm(prompt)
            # Try to parse JSON from response
            import re
            match = re.search(r'\{.*\}', response, re.DOTALL)
            if match:
                return json.loads(match.group())
        except Exception as e:
            logger.warning(f"[ResearchAgent] LLM decision failed: {e}")

        return {"action": ResearchAction.GIVE_REPORT.value, "thinking": "无法决策", "input": {}}

    def _mock_decide(
        self,
        code: str,
        topic: str,
        accumulated: Dict[str, Any],
        iteration: int,
    ) -> Dict[str, Any]:
        """Mock decision for testing without LLM."""
        tool_results = accumulated.get("tool_results", [])
        count = len(tool_results)

        # Simple progression based on iteration count
        if count == 0:
            return {
                "action": ResearchAction.SEARCH_NEWS.value,
                "thinking": "首先搜索最新新闻",
                "input": {"query": f"{code} {accumulated.get('stock_name', code)}"},
            }
        elif count == 1:
            return {
                "action": ResearchAction.RAG_SEARCH.value,
                "thinking": "查看历史分析记录",
                "input": {"code": code, "query": topic},
            }
        elif count == 2:
            return {
                "action": ResearchAction.GET_KLINE.value,
                "thinking": "获取K线数据进行技术分析",
                "input": {"code": code},
            }
        elif count == 3:
            return {
                "action": ResearchAction.GET_FINANCIALS.value,
                "thinking": "查看财务数据",
                "input": {"code": code},
            }
        else:
            return {
                "action": ResearchAction.GIVE_REPORT.value,
                "thinking": "信息收集充分，生成报告",
                "input": {},
            }

    def _execute_tool(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        code: str,
        context: Dict[str, Any],
    ) -> Any:
        """Execute a tool by name and return its output."""
        try:
            if tool_name == ResearchAction.SEARCH_NEWS.value:
                return self._tool_search_news(tool_input.get("query", code))
            elif tool_name == ResearchAction.RAG_SEARCH.value:
                return self._tool_rag_search(
                    tool_input.get("code", code),
                    tool_input.get("query", ""),
                )
            elif tool_name == ResearchAction.GET_KLINE.value:
                return self._tool_get_kline(tool_input.get("code", code))
            elif tool_name == ResearchAction.GET_FINANCIALS.value:
                return self._tool_get_financials(tool_input.get("code", code))
            elif tool_name == ResearchAction.GET_INSTITUTIONAL.value:
                return self._tool_get_institutional(tool_input.get("code", code))
            elif tool_name == ResearchAction.ANALYZE_BASIC.value:
                return self._tool_analyze_basic(code, context)
            else:
                return {"error": f"Unknown tool: {tool_name}"}
        except Exception as e:
            logger.warning(f"[ResearchAgent] Tool {tool_name} failed: {e}")
            return {"error": str(e)}

    def _tool_search_news(self, query: str) -> Dict[str, Any]:
        """Search news using search_service."""
        try:
            from src.search_pkg import get_search_service
            svc = get_search_service()
            if svc:
                results = svc.search(query, count=5)
                if results:
                    return {
                        "success": True,
                        "results": [
                            {
                                "title": r.title,
                                "snippet": r.snippet,
                                "source": r.source,
                                "date": r.published_date,
                            }
                            for r in results
                        ],
                    }
            return {"success": False, "error": "Search service not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _tool_rag_search(self, code: str, query: str) -> Dict[str, Any]:
        """Search RAG knowledge base."""
        try:
            from src.rag import build_rag_context
            ctx = build_rag_context(code, question=query, top_k_self=3, top_k_similar=2)
            return {"success": True, "context": ctx} if ctx else {"success": False, "context": ""}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _tool_get_kline(self, code: str) -> Dict[str, Any]:
        """Get K-line data via DataService."""
        try:
            from src.data_service import DataService
            svc = DataService()
            result = svc._handle_get_kline_data({"code": code})
            return result
        except Exception as e:
            return {"error": str(e)}

    def _tool_get_financials(self, code: str) -> Dict[str, Any]:
        """Get financial data via DataService."""
        try:
            from src.data_service import DataService
            svc = DataService()
            result = svc._handle_get_financials({"code": code})
            return result
        except Exception as e:
            return {"error": str(e)}

    def _tool_get_institutional(self, code: str) -> Dict[str, Any]:
        """Get institutional data via DataService."""
        try:
            from src.data_service import DataService
            svc = DataService()
            result = svc._handle_get_institutional({"code": code})
            return result
        except Exception as e:
            return {"error": str(e)}

    def _tool_analyze_basic(self, code: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run basic single-agent analysis."""
        try:
            from src.analyzer import get_analyzer
            analyzer = get_analyzer()
            if analyzer and analyzer.is_available():
                db = get_db()
                ctx = db.get_analysis_context(code)
                result = analyzer.analyze(code, ctx)
                return {
                    "success": True,
                    "summary": result.analysis_summary if hasattr(result, 'analysis_summary') else str(result),
                    "score": result.sentiment_score if hasattr(result, 'sentiment_score') else 0,
                }
            return {"success": False, "error": "Analyzer not available"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _extract_observation(self, tool_name: str, output: Any) -> str:
        """Extract a brief key observation from tool output."""
        if isinstance(output, dict):
            if output.get("error"):
                return f"错误: {output['error'][:50]}"
            if tool_name == ResearchAction.SEARCH_NEWS.value:
                results = output.get("results", [])
                if results:
                    first = results[0]
                    return f"找到 {len(results)} 条新闻，最新: {first.get('title', '')[:40]}"
                return "未找到相关新闻"
            if tool_name == ResearchAction.RAG_SEARCH.value:
                ctx = output.get("context", "")
                if ctx:
                    return f"历史分析上下文: {len(ctx)} 字符"
                return "知识库中无相关记录"
            if tool_name == ResearchAction.GET_KLINE.value:
                klines = output.get("klines", output.get("data", []))
                return f"K线数据: {len(klines) if isinstance(klines, list) else 'N/A'} 条记录"
            if tool_name == ResearchAction.GET_FINANCIALS.value:
                status = output.get("status", "")
                return f"财务报表: {status}"
            if tool_name == ResearchAction.GET_INSTITUTIONAL.value:
                status = output.get("status", "")
                return f"机构数据: {status}"
            if tool_name == ResearchAction.ANALYZE_BASIC.value:
                score = output.get("score", 0)
                return f"基础分析: 评分 {score}"
        return str(output)[:80] if output else "无输出"

    def _summarize_prior_results(self, tool_results: List[Dict]) -> str:
        """Summarize prior tool results for LLM decision prompt."""
        if not tool_results:
            return "（尚未收集任何信息）"
        lines = []
        for i, r in enumerate(tool_results, 1):
            tool = r.get("tool", "?")
            obs = r.get("observation", "")[:100]
            lines.append(f"{i}. [{tool}] {obs}")
        return "\n".join(lines)

    def _generate_final_report(self, code: str, topic: str, steps: List[ResearchStep]) -> str:
        """Generate final research report from accumulated steps."""
        if not steps:
            return f"针对 {code} 的研究 '{topic}' 完成，未收集到有效信息。"

        # Build report from steps
        lines = [f"# {code} 研究报告: {topic}", ""]
        lines.append(f"**研究耗时**: {steps[-1].iteration} 轮工具调用")
        lines.append("")

        for step in steps:
            lines.append(f"## 第 {step.iteration} 轮: {step.action}")
            lines.append(f"**思考**: {step.thinking}")
            lines.append(f"**观察**: {step.observation}")
            lines.append("")

        # Synthesize from tool results
        tool_results = [
            {"tool": s.action, "observation": s.observation, "output": s.tool_output}
            for s in steps
        ]
        lines.append("## 综合分析")

        # Extract key findings per tool type
        news_obs = [r["observation"] for r in tool_results if r["tool"] == ResearchAction.SEARCH_NEWS.value]
        if news_obs:
            lines.append(f"**新闻动态**: {news_obs[0]}")

        rag_obs = [r["observation"] for r in tool_results if r["tool"] == ResearchAction.RAG_SEARCH.value]
        if rag_obs:
            lines.append(f"**历史参考**: {rag_obs[0]}")

        kline_obs = [r["observation"] for r in tool_results if r["tool"] == ResearchAction.GET_KLINE.value]
        if kline_obs:
            lines.append(f"**技术数据**: {kline_obs[0]}")

        financials_obs = [r["observation"] for r in tool_results if r["tool"] == ResearchAction.GET_FINANCIALS.value]
        if financials_obs:
            lines.append(f"**财务数据**: {financials_obs[0]}")

        lines.append("")
        lines.append(f"*研究完成时间: {time.strftime('%Y-%m-%d %H:%M:%S')}*")

        return "\n".join(lines)

    def _save_report(self, report: ResearchReport) -> None:
        """Persist research report to SQLite.

        Schema (P7-4):
          - ``research_logs`` stores metadata + a slim ``steps_json``
            (no ``tool_output`` field, which may be a multi-KB dict
            from search_news / get_financials / etc.).
          - ``research_artifacts`` stores each step's full ``tool_output``
            as a separate row keyed by ``research_log_id`` + iteration.

        This split keeps research_logs queries (history list, search
        by code/topic, VACUUM) fast even when individual artifacts
        are large. The artifacts can be fetched lazily when the user
        opens a specific report.
        """
        try:
            db = get_db()
            with db.get_session() as session:
                # Ensure both tables exist (research_artifacts may not
                # exist on databases that pre-date the v5 migration, e.g.
                # in tests that don't run the full storage bootstrap).
                session.execute(
                    text("""
                        CREATE TABLE IF NOT EXISTS research_logs (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            code TEXT NOT NULL,
                            topic TEXT NOT NULL,
                            steps_json TEXT NOT NULL,
                            final_report TEXT NOT NULL,
                            tool_calls INTEGER NOT NULL,
                            duration_seconds REAL NOT NULL,
                            timestamp TEXT NOT NULL
                        )
                    """)
                )
                session.execute(
                    text("""
                        CREATE TABLE IF NOT EXISTS research_artifacts (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            research_log_id INTEGER NOT NULL,
                            iteration INTEGER NOT NULL,
                            tool_name TEXT NOT NULL,
                            output_json TEXT NOT NULL,
                            output_size_bytes INTEGER NOT NULL,
                            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (research_log_id) REFERENCES research_logs(id) ON DELETE CASCADE
                        )
                    """)
                )

                # Build slim step dicts (omit tool_output).
                slim_steps = [
                    {
                        "iteration": s.iteration,
                        "thinking": s.thinking,
                        "action": s.action,
                        "tool_input": s.tool_input,
                        "observation": s.observation,
                        "is_final": s.is_final,
                    }
                    for s in report.steps
                ]

                result = session.execute(
                    text("""
                        INSERT INTO research_logs
                        (code, topic, steps_json, final_report, tool_calls, duration_seconds, timestamp)
                        VALUES (:code, :topic, :steps_json, :final_report, :tool_calls, :duration_seconds, :timestamp)
                    """),
                    {
                        "code": report.code,
                        "topic": report.topic,
                        "steps_json": json.dumps(slim_steps, ensure_ascii=False),
                        "final_report": report.final_report,
                        "tool_calls": report.tool_calls,
                        "duration_seconds": report.duration_seconds,
                        "timestamp": report.timestamp,
                    },
                )
                research_log_id = result.lastrowid

                # Persist each step's tool_output as a separate row.
                artifact_rows = []
                for s in report.steps:
                    payload = json.dumps(s.tool_output, ensure_ascii=False, default=str)
                    artifact_rows.append({
                        "research_log_id": research_log_id,
                        "iteration": s.iteration,
                        "tool_name": s.action,
                        "output_json": payload,
                        "output_size_bytes": len(payload.encode("utf-8")),
                    })
                if artifact_rows:
                    session.execute(
                        text("""
                            INSERT INTO research_artifacts
                            (research_log_id, iteration, tool_name, output_json, output_size_bytes)
                            VALUES (:research_log_id, :iteration, :tool_name, :output_json, :output_size_bytes)
                        """),
                        artifact_rows,
                    )

                session.commit()
                # Log a tiny summary line so operators can spot bloating.
                if artifact_rows:
                    total = sum(r["output_size_bytes"] for r in artifact_rows)
                    logger.info(
                        f"[ResearchAgent] Saved report id={research_log_id} "
                        f"with {len(artifact_rows)} artifacts "
                        f"(total {total / 1024:.1f} KB)"
                    )
        except Exception as e:
            logger.warning(f"[ResearchAgent] Failed to save report: {e}")

    def load_report(self, report_id: int) -> Optional[ResearchReport]:
        """Load a previously-saved report including its full tool artifacts.

        Returns None if the id doesn't exist. Used by the GUI to lazily
        fetch the heavy tool_output payloads only when the user opens a
        specific report.
        """
        try:
            db = get_db()
            with db.get_session() as session:
                row = session.execute(
                    text("""
                        SELECT code, topic, steps_json, final_report,
                               tool_calls, duration_seconds, timestamp
                        FROM research_logs WHERE id = :id
                    """),
                    {"id": report_id},
                ).fetchone()
                if row is None:
                    return None
                code, topic, steps_json, final_report, tool_calls, duration, ts = row

                artifact_rows = session.execute(
                    text("""
                        SELECT iteration, tool_name, output_json
                        FROM research_artifacts
                        WHERE research_log_id = :id
                        ORDER BY iteration
                    """),
                    {"id": report_id},
                ).fetchall()
                artifacts_by_iter: Dict[int, Any] = {}
                for it, _tool, payload in artifact_rows:
                    try:
                        artifacts_by_iter[it] = json.loads(payload)
                    except (TypeError, ValueError):
                        artifacts_by_iter[it] = payload

                # Rehydrate slim steps with their full tool_output.
                slim_steps = json.loads(steps_json) if steps_json else []
                steps: List[ResearchStep] = []
                for s in slim_steps:
                    steps.append(ResearchStep(
                        iteration=s.get("iteration", 0),
                        thinking=s.get("thinking", ""),
                        action=s.get("action", ""),
                        tool_input=s.get("tool_input", {}),
                        tool_output=artifacts_by_iter.get(s.get("iteration", 0)),
                        observation=s.get("observation", ""),
                        is_final=s.get("is_final", False),
                    ))

                return ResearchReport(
                    code=code, topic=topic, steps=steps,
                    final_report=final_report, tool_calls=tool_calls,
                    duration_seconds=duration, timestamp=ts,
                )
        except Exception as e:
            logger.warning(f"[ResearchAgent] Failed to load report {report_id}: {e}")
            return None


def research_stock(code: str, topic: str, context: Optional[Dict[str, Any]] = None) -> ResearchReport:
    """Convenience function for one-shot research."""
    agent = ResearchAgent()
    return agent.research(code, topic, context)
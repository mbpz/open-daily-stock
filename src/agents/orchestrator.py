# -*- coding: utf-8 -*-
"""Multi-agent orchestrator for deep stock analysis.

Coordinates three parallel specialist agents (Technical, Fundamental, News)
and a Synthesizer agent to produce a comprehensive AnalysisResult.

Architecture:
    1. Run 3 specialist agents in parallel via ThreadPoolExecutor
    2. Collect results (with timeout and error handling per specialist)
    3. Feed specialist reports into SynthesizerAgent
    4. Return final AnalysisResult
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import Dict, Any, TYPE_CHECKING

from .technical_agent import TechnicalAgent
from .fundamental_agent import FundamentalAgent
from .news_agent import NewsAgent
from .synthesizer_agent import SynthesizerAgent

if TYPE_CHECKING:
    from src.analyzer import GeminiAnalyzer, AnalysisResult

logger = logging.getLogger(__name__)

# Per-specialist timeout in seconds
SPECIALIST_TIMEOUT = 90


class MultiAgentOrchestrator:
    """Orchestrates parallel multi-agent stock analysis.

    Runs Technical, Fundamental, and News specialist agents concurrently,
    then synthesizes their outputs into a single AnalysisResult.

    Usage:
        analyzer = GeminiAnalyzer()
        orchestrator = MultiAgentOrchestrator(analyzer)
        result = orchestrator.analyze("600519", context)
    """

    def __init__(self, analyzer: "GeminiAnalyzer"):
        """
        Args:
            analyzer: Initialized GeminiAnalyzer instance for LLM calls.
        """
        self.analyzer = analyzer
        self.agents = [
            TechnicalAgent(),
            FundamentalAgent(),
            NewsAgent(),
        ]
        self.synthesizer = SynthesizerAgent()

    def analyze(
        self, code: str, context: Dict[str, Any]
    ) -> "AnalysisResult":
        """Run full multi-agent analysis pipeline.

        Args:
            code: Stock code (e.g. '600519')
            context: Analysis context dict from storage.get_analysis_context()

        Returns:
            AnalysisResult with synthesized multi-agent analysis.
        """
        from src.analyzer import AnalysisResult

        name = context.get("stock_name", code)

        # Check if AI is available at all
        if not self.analyzer.is_available():
            logger.warning(f"AI not available, cannot run multi-agent analysis for {code}")
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction="震荡",
                operation_advice="持有",
                confidence_level="低",
                analysis_summary="AI分析功能未启用（未配置API Key），多智能体分析不可用",
                risk_warning="请配置Gemini API Key后重试",
                success=False,
                error_message="AI API Key未配置",
            )

        logger.info(f"[Orchestrator] Starting multi-agent analysis for {name}({code})")

        # Phase 1: Run 3 specialist agents in parallel
        specialist_results = self._run_specialists(code, context)

        # Log results summary
        for agent_name, result in specialist_results.items():
            if isinstance(result, dict) and "error" in result:
                logger.warning(
                    f"[Orchestrator] {agent_name} agent failed: {result['error']}"
                )
            else:
                logger.info(
                    f"[Orchestrator] {agent_name} agent completed "
                    f"({len(str(result))} chars)"
                )

        # Phase 2: Synthesize results
        logger.info(f"[Orchestrator] Starting synthesis for {name}({code})")
        final_result = self.synthesizer.synthesize(
            code, context, specialist_results, self.analyzer
        )

        logger.info(
            f"[Orchestrator] Multi-agent analysis complete for {name}({code}): "
            f"{final_result.trend_prediction}, score={final_result.sentiment_score}"
        )
        return final_result

    def _run_specialists(
        self, code: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Run all specialist agents in parallel.

        Each agent builds its own prompt and calls the LLM independently.
        Failures are captured per-agent and stored as dicts with 'error' key.

        Returns:
            Dict mapping agent name to result text or error dict.
        """
        results: Dict[str, Any] = {}

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            for agent in self.agents:
                future = executor.submit(self._run_single_agent, agent, code, context)
                futures[future] = agent

            for future in as_completed(futures):
                agent = futures[future]
                try:
                    result = future.result(timeout=SPECIALIST_TIMEOUT)
                    results[agent.name] = result
                except TimeoutError:
                    logger.warning(
                        f"[Orchestrator] {agent.name} agent timed out "
                        f"({SPECIALIST_TIMEOUT}s)"
                    )
                    results[agent.name] = {
                        "error": f"Analysis timed out after {SPECIALIST_TIMEOUT}s"
                    }
                except Exception as e:
                    logger.warning(
                        f"[Orchestrator] {agent.name} agent failed: {e}"
                    )
                    results[agent.name] = {"error": str(e)}

        return results

    def _run_single_agent(
        self, agent, code: str, context: Dict[str, Any]
    ) -> str:
        """Execute a single specialist agent's analysis.

        Builds the agent's prompt, calls the LLM via the shared analyzer,
        and returns the raw response text.

        Args:
            agent: BaseAgent subclass instance
            code: Stock code
            context: Analysis context dict

        Returns:
            Raw response text from the LLM.
        """
        prompt = agent.build_prompt(code, context)

        generation_config = {
            "temperature": 0.3,
            "max_output_tokens": 4096,
        }

        logger.debug(
            f"[Orchestrator] {agent.name} agent prompt length: {len(prompt)} chars"
        )

        response_text = self.analyzer._call_api_with_retry(
            prompt, generation_config
        )

        logger.debug(
            f"[Orchestrator] {agent.name} agent response length: "
            f"{len(response_text)} chars"
        )
        return response_text

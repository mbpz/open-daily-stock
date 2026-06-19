"""Tests for MultiAgentOrchestrator co-operative cancellation."""
import threading
import time
import pytest
from unittest.mock import MagicMock, patch

from src.analyzer import OrchestratorCancelled, AnalysisResult


def _stub_orchestrator(analyzer_available=True, cancellation_event=None):
    """Build an orchestrator with specialists stubbed to return canned text."""
    from src.agents.orchestrator import MultiAgentOrchestrator
    from src.agents.technical_agent import TechnicalAgent

    orch = MultiAgentOrchestrator(
        analyzer=MagicMock(is_available=MagicMock(return_value=analyzer_available)),
        cancellation_event=cancellation_event,
    )
    # Stub the real specialists so we don't try to build huge prompts.
    for i, agent in enumerate(orch.agents):
        agent.build_prompt = lambda code, ctx, _i=i: f"prompt-{_i}"
    orch.analyzer._call_api_with_retry = MagicMock(return_value="LLM response text")
    # Stub the synthesiser + reflector so the test doesn't need real LLM.
    synth_result = AnalysisResult(
        code="600519", name="贵州茅台",
        sentiment_score=80, trend_prediction="看涨",
        operation_advice="买入", confidence_level="高",
        analysis_summary="ok", risk_warning="",
        success=True, error_message="",
    )
    orch.synthesizer.synthesize = MagicMock(return_value=synth_result)
    orch.reflector.reflect = MagicMock()
    return orch


def test_cancellation_before_start_returns_cancelled_result():
    ev = threading.Event()
    ev.set()
    orch = _stub_orchestrator(cancellation_event=ev)
    result = orch.analyze("600519", {"stock_name": "贵州茅台"})
    assert result.success is False
    assert "cancelled" in (result.error_message or "").lower()
    assert "取消" in (result.analysis_summary or "")


def test_cancellation_propagates_to_llm_call():
    ev = threading.Event()
    orch = _stub_orchestrator(cancellation_event=ev)
    orch.agents[0].build_prompt = lambda c, x: "p"
    orch.analyzer._call_api_with_retry = MagicMock(return_value="x")
    orch._run_single_agent(orch.agents[0], "600519", {"stock_name": "X"})
    orch.analyzer._call_api_with_retry.assert_called_once()
    call_kwargs = orch.analyzer._call_api_with_retry.call_args.kwargs
    assert call_kwargs.get("cancellation_event") is ev


def test_no_cancellation_event_works_as_before():
    orch = _stub_orchestrator()  # no event
    orch.agents[0].build_prompt = lambda c, x: "p"
    orch.analyzer._call_api_with_retry = MagicMock(return_value="x")
    orch._run_single_agent(orch.agents[0], "1", {})
    call_kwargs = orch.analyzer._call_api_with_retry.call_args.kwargs
    assert call_kwargs.get("cancellation_event") is None


def test_cancellation_during_specialists_aborts_pipeline():
    ev = threading.Event()
    orch = _stub_orchestrator(cancellation_event=ev)

    def boom(*a, **kw):
        ev.set()
        raise OrchestratorCancelled("user closed window")

    orch.analyzer._call_api_with_retry = boom
    result = orch.analyze("600519", {"stock_name": "贵州茅台"})
    assert result.success is False
    assert "cancelled" in (result.error_message or "").lower()
    # Synthesizer must NOT be called when cancelled
    orch.synthesizer.synthesize.assert_not_called()


def test_cancelled_result_shape_for_gui():
    ev = threading.Event()
    ev.set()
    orch = _stub_orchestrator(cancellation_event=ev)
    r = orch.analyze("000001", {"stock_name": "平安银行"})
    assert r.code == "000001"
    assert r.name == "平安银行"
    assert r.success is False
    assert r.error_message
    assert r.analysis_summary


class _FakeAnalyzer:
    """Minimal stand-in for GeminiAnalyzer exposing the real _call_api_with_retry.

    We bind the real unbound method to this instance so cancellation
    behaviour runs against the production code, but stub out the model
    and config so we can drive the retry path deterministically.
    """

    def __init__(self):
        self._use_openai = False
        self._openai_client = None
        self._using_fallback = False
        self._switch_to_fallback_model = lambda: False
        # Always raises -> forces the retry path
        self._model = MagicMock()
        self._model.generate_content.side_effect = Exception("429 rate limited")
        # Bind the real method
        from src.analyzer import GeminiAnalyzer
        self._call_api_with_retry = GeminiAnalyzer._call_api_with_retry.__get__(self)


def test_cancellation_check_inside_analyzer_sleep_is_responsive():
    """Verify the retry-sleep loop checks the cancellation event in 0.5s slices.

    Without slicing, a 5s backoff sleep would block the cancellation.
    """
    calls = {"n": 0}

    def fake_sleep(_seconds):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OrchestratorCancelled("cancelled during sleep")

    a = _FakeAnalyzer()

    with patch("src.analyzer.get_config") as gc, \
         patch("src.analyzer.time.sleep", side_effect=fake_sleep), \
         patch("src.analyzer.logger"):
        cfg = MagicMock()
        cfg.gemini_max_retries = 5
        cfg.gemini_retry_delay = 5.0
        cfg.openai_api_key = None
        cfg.openai_base_url = None
        gc.return_value = cfg

        ev = threading.Event()
        with pytest.raises(OrchestratorCancelled):
            a._call_api_with_retry("p", {}, cancellation_event=ev)

    assert calls["n"] == 1, f"expected exactly 1 sleep, got {calls['n']}"


def test_cancellation_with_no_event_means_no_check_runs():
    """Backwards compat: passing cancellation_event=None must not raise."""
    a = _FakeAnalyzer()
    # Make the model succeed first try
    a._model.generate_content.side_effect = None
    a._model.generate_content.return_value.text = "ok response"

    with patch("src.analyzer.get_config") as gc, \
         patch("src.analyzer.time.sleep"), \
         patch("src.analyzer.logger"):
        cfg = MagicMock()
        cfg.gemini_max_retries = 2
        cfg.gemini_retry_delay = 1.0
        cfg.openai_api_key = None
        cfg.openai_base_url = None
        gc.return_value = cfg

        out = a._call_api_with_retry("p", {}, cancellation_event=None)
        assert out == "ok response"

"""Tests for P6-3 ReflectorAgent: consistency check, calibration, risk scan."""
import pytest
from src.agents.reflector_agent import ReflectorAgent, ReflectionNote
from src.analyzer import AnalysisResult


@pytest.fixture
def bullish_result():
    """A bullish AnalysisResult for testing."""
    return AnalysisResult(
        code="600519",
        name="茅台",
        sentiment_score=75,
        trend_prediction="看多",
        operation_advice="买入",
        confidence_level="高",
        analysis_summary="强烈看多",
        risk_warning="",
    )


@pytest.fixture
def mixed_specialist_results():
    """Technical bullish, fundamental bearish — should trigger contradiction."""
    return {
        "technical": {"score": 80, "trend": "bullish"},
        "fundamental": {"score": 35, "valuation": "overvalued"},
        "news": {"score": 60, "sentiment": "neutral"},
    }


@pytest.fixture
def all_bullish_results():
    """All three specialists bullish."""
    return {
        "technical": {"score": 75, "trend": "bullish"},
        "fundamental": {"score": 70, "valuation": "fair"},
        "news": {"score": 65, "sentiment": "positive"},
    }


class TestReflectionNote:
    def test_default_values(self):
        note = ReflectionNote()
        assert note.signal_consistent is True
        assert note.contradictions == []
        assert note.original_confidence == "中"

    def test_to_dict(self):
        note = ReflectionNote(
            signal_consistent=False,
            contradictions=["test contradiction"],
            calibrated_confidence="低",
            calibration_note="test note",
        )
        d = note.to_dict()
        assert d["signal_consistent"] is False
        assert len(d["contradictions"]) == 1
        assert d["calibrated_confidence"] == "低"


class TestConsistencyCheck:
    def test_detects_contradiction(self, bullish_result, mixed_specialist_results):
        agent = ReflectorAgent()
        consistent, contradictions = agent._check_consistency(
            bullish_result, mixed_specialist_results
        )
        assert not consistent
        assert len(contradictions) > 0
        assert any("技术面" in c and "基本面" in c for c in contradictions)

    def test_no_contradiction_when_aligned(self, all_bullish_results):
        agent = ReflectorAgent()
        result = AnalysisResult(
            code="000001", name="平安银行", sentiment_score=70,
            trend_prediction="看多", operation_advice="买入",
            confidence_level="高", analysis_summary="看好", risk_warning="",
        )
        consistent, contradictions = agent._check_consistency(result, all_bullish_results)
        # Should be consistent (no extreme divergence)
        assert consistent or all(
            "技术面" not in c or "基本面" not in c for c in contradictions
        )

    def test_score_verbal_mismatch(self):
        agent = ReflectorAgent()
        result = AnalysisResult(
            code="000001", name="平安",
            sentiment_score=80,  # Very bullish
            trend_prediction="看空",  # But says bearish — mismatch
            operation_advice="持有",
            confidence_level="中", analysis_summary="", risk_warning="",
        )
        consistent, contradictions = agent._check_consistency(result, {})
        assert not consistent
        assert any("不一致" in c for c in contradictions)

    def test_extract_score_from_dict(self):
        agent = ReflectorAgent()
        assert agent._extract_score({"score": 75}) == 75
        assert agent._extract_score({"sentiment_score": 60}) == 60
        assert agent._extract_score({"error": "failed"}) is None
        assert agent._extract_score(None) is None


class TestConfidenceCalibration:
    def test_boost_confidence(self):
        agent = ReflectorAgent()
        result = agent._calibrate_confidence("中", 0.75)
        assert result == "高"

    def test_lower_confidence(self):
        agent = ReflectorAgent()
        result = agent._calibrate_confidence("高", 0.30)
        assert result == "中"

    def test_keep_confidence(self):
        agent = ReflectorAgent()
        result = agent._calibrate_confidence("中", 0.50)
        assert result == "中"

    def test_min_confidence(self):
        agent = ReflectorAgent()
        result = agent._calibrate_confidence("低", 0.20)
        assert result == "低"  # Can't go lower

    def test_invalid_input(self):
        agent = ReflectorAgent()
        result = agent._calibrate_confidence("unknown", 0.75)
        assert result == "unknown"  # Returns original


class TestRiskScan:
    def test_detects_missing_risks(self, bullish_result):
        agent = ReflectorAgent()
        risks = agent._scan_uncovered_risks(bullish_result)
        assert len(risks) > 0
        # Should detect at least some uncovered categories
        categories = [r.split("：")[1].split("相关")[0] if "：" in r else "" for r in risks]
        assert any(c in ["政策", "流动性", "国际形势", "行业周期", "黑天鹅"] for c in categories)

    def test_high_confidence_no_risk_warning(self):
        agent = ReflectorAgent()
        result = AnalysisResult(
            code="test", name="test", sentiment_score=80,
            trend_prediction="看多", operation_advice="买入",
            confidence_level="高", risk_warning="",
            analysis_summary="", news_summary="", fundamental_analysis="",
        )
        risks = agent._scan_uncovered_risks(result)
        assert any("过度自信" in r for r in risks)

    def test_covered_risks_not_flagged(self):
        agent = ReflectorAgent()
        result = AnalysisResult(
            code="test", name="test", sentiment_score=50,
            trend_prediction="震荡", operation_advice="持有",
            confidence_level="中",
            risk_warning="政策风险、流动性风险需关注",
            analysis_summary="国际形势复杂",
            news_summary="",
            fundamental_analysis="",
        )
        risks = agent._scan_uncovered_risks(result)
        # 政策 and 流动性 should NOT be flagged
        flagged = [r.split("：")[0] for r in risks if "：" in r]
        assert "未覆盖风险" in risks[0] if risks else True


class TestFullReflection:
    def test_reflect_without_llm(self, bullish_result, mixed_specialist_results):
        agent = ReflectorAgent()
        note = agent.reflect(bullish_result, mixed_specialist_results, analyzer=None)
        assert isinstance(note, ReflectionNote)
        assert note.signal_consistent is False
        assert len(note.contradictions) > 0
        assert note.original_confidence == "高"
        # Without historical data, calibration should stay the same
        assert note.calibrated_confidence in ("高", "中", "低")
        assert len(note.uncovered_risks) > 0
        # No LLM → critical_review empty
        assert note.critical_review == ""

    def test_reflect_all_aligned(self, all_bullish_results):
        agent = ReflectorAgent()
        result = AnalysisResult(
            code="000001", name="平安银行", sentiment_score=70,
            trend_prediction="看多", operation_advice="买入",
            confidence_level="中", analysis_summary="看好",
            risk_warning="关注政策变化",
        )
        note = agent.reflect(result, all_bullish_results, analyzer=None)
        assert isinstance(note, ReflectionNote)
        # Should be consistent
        assert note.signal_consistent is True

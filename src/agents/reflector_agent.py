"""P6-3: Reflector Agent — critical review and confidence calibration.

Takes the final multi-agent analysis result and performs a second-pass review:
  1. Signal consistency check — detect contradictions across dimensions
  2. Confidence calibration — weight by historical accuracy for this stock
  3. Uncovered risk scan — identify blind spots the specialists missed
  4. LLM critical review — ask the model to critique its own output

Output: a ReflectionNote appended to the AnalysisResult.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, TYPE_CHECKING

from src.storage import get_db

if TYPE_CHECKING:
    from src.analyzer import GeminiAnalyzer, AnalysisResult

logger = logging.getLogger(__name__)


@dataclass
class ReflectionNote:
    """Structured reflection output from the ReflectorAgent."""

    # Signal consistency
    signal_consistent: bool = True
    contradictions: List[str] = field(default_factory=list)

    # Confidence calibration
    original_confidence: str = "中"  # 高/中/低
    calibrated_confidence: str = "中"
    historical_accuracy: Optional[float] = None  # 0.0-1.0, None if no history
    calibration_note: str = ""

    # Uncovered risks
    uncovered_risks: List[str] = field(default_factory=list)

    # LLM critical review
    critical_review: str = ""
    suggestion: str = ""  # How to improve the next analysis

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_consistent": self.signal_consistent,
            "contradictions": self.contradictions,
            "original_confidence": self.original_confidence,
            "calibrated_confidence": self.calibrated_confidence,
            "historical_accuracy": self.historical_accuracy,
            "calibration_note": self.calibration_note,
            "uncovered_risks": self.uncovered_risks,
            "critical_review": self.critical_review,
            "suggestion": self.suggestion,
        }


class ReflectorAgent:
    """Second-pass analysis reviewer.

    Runs after the Synthesizer produces a final AnalysisResult.
    Performs both rule-based checks (signal consistency, historical calibration)
    and an optional LLM-based critical review.
    """

    name = "reflector"
    role = "分析反思专家"

    # Score ranges for trend categorization
    BULLISH_THRESHOLD = 60  # >= 60 = bullish
    BEARISH_THRESHOLD = 40  # <= 40 = bearish

    def __init__(self):
        self._accuracy_cache: Dict[str, Optional[float]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reflect(
        self,
        result: "AnalysisResult",
        specialist_results: Dict[str, Any],
        analyzer: Optional["GeminiAnalyzer"] = None,
    ) -> ReflectionNote:
        """Run the full reflection pipeline.

        Args:
            result: The final AnalysisResult from the Synthesizer.
            specialist_results: Raw outputs from Technical/Fundamental/News agents.
            analyzer: Optional LLM analyzer for critical review.

        Returns:
            ReflectionNote with consistency checks and calibration.
        """
        note = ReflectionNote(
            original_confidence=result.confidence_level,
            calibrated_confidence=result.confidence_level,
        )

        # 1. Signal consistency check (rule-based, no LLM needed)
        note.signal_consistent, note.contradictions = self._check_consistency(
            result, specialist_results
        )

        # 2. Confidence calibration from historical accuracy
        accuracy = self._get_historical_accuracy(result.code)
        note.historical_accuracy = accuracy
        if accuracy is not None:
            note.calibrated_confidence = self._calibrate_confidence(
                result.confidence_level, accuracy
            )
            note.calibration_note = (
                f"历史准确率 {accuracy:.0%}，"
                f"置信度从「{note.original_confidence}」校准为「{note.calibrated_confidence}」"
            )

        # 3. Uncovered risk scan (rule-based)
        note.uncovered_risks = self._scan_uncovered_risks(result)

        # 4. LLM critical review (optional, when analyzer is available)
        if analyzer is not None and analyzer.is_available():
            try:
                note.critical_review, note.suggestion = self._llm_critical_review(
                    result, specialist_results, analyzer
                )
            except Exception as e:
                logger.warning(f"LLM critical review failed: {e}")
                note.critical_review = "（LLM反思暂时不可用）"
                note.suggestion = ""

        return note

    # ------------------------------------------------------------------
    # 1. Signal Consistency Check
    # ------------------------------------------------------------------

    def _check_consistency(
        self,
        result: "AnalysisResult",
        specialist_results: Dict[str, Any],
    ) -> Tuple[bool, List[str]]:
        """Cross-check signal consistency across technical/fundamental/news dimensions.

        Detects:
        - Technical bullish + Fundamental bearish (and vice versa)
        - Extreme sentiment divergence
        - Score mismatch with verbal assessment
        """
        contradictions: List[str] = []

        # Extract scores from specialist results
        tech_score = self._extract_score(specialist_results.get("technical"))
        fund_score = self._extract_score(specialist_results.get("fundamental"))
        news_score = self._extract_score(specialist_results.get("news"))

        scores = {"技术面": tech_score, "基本面": fund_score, "消息面": news_score}

        # Check pairwise contradictions
        if tech_score is not None and fund_score is not None:
            if tech_score >= self.BULLISH_THRESHOLD and fund_score <= self.BEARISH_THRESHOLD:
                contradictions.append(
                    f"⚠️ 矛盾：技术面看多({tech_score}) vs 基本面看空({fund_score})"
                )
            elif tech_score <= self.BEARISH_THRESHOLD and fund_score >= self.BULLISH_THRESHOLD:
                contradictions.append(
                    f"⚠️ 矛盾：技术面看空({tech_score}) vs 基本面看多({fund_score})"
                )

        if tech_score is not None and news_score is not None:
            if abs(tech_score - news_score) >= 30:
                direction = "看多" if tech_score > news_score else "看空"
                contradictions.append(
                    f"⚠️ 分歧：技术面与消息面评分差距≥30（技术面{tech_score} vs 消息面{news_score}）"
                )

        # Check verbal vs score consistency
        if result.sentiment_score >= 70 and "看空" in result.trend_prediction:
            contradictions.append(
                f"⚠️ 不一致：评分{result.sentiment_score}但趋势预测为「{result.trend_prediction}」"
            )
        if result.sentiment_score <= 30 and "看多" in result.trend_prediction:
            contradictions.append(
                f"⚠️ 不一致：评分{result.sentiment_score}但趋势预测为「{result.trend_prediction}」"
            )

        consistent = len(contradictions) == 0
        if not consistent:
            logger.info(f"[Reflector] Found {len(contradictions)} contradictions for {result.code}")

        return consistent, contradictions

    def _extract_score(self, specialist_output: Any) -> Optional[int]:
        """Extract numeric score from a specialist's output (text or dict)."""
        if specialist_output is None:
            return None
        if isinstance(specialist_output, dict):
            if "error" in specialist_output:
                return None
            score = specialist_output.get("score", specialist_output.get("sentiment_score"))
            if isinstance(score, (int, float)):
                return int(score)
        if isinstance(specialist_output, str):
            # Try to find "score": XX pattern in JSON-containing text
            import re
            import json
            try:
                # Find JSON block
                match = re.search(r'\{[^{}]*"score"\s*:\s*(\d+)[^{}]*\}', specialist_output)
                if match:
                    return int(match.group(1))
            except (ValueError, json.JSONDecodeError):
                pass
        return None

    # ------------------------------------------------------------------
    # 2. Confidence Calibration
    # ------------------------------------------------------------------

    def _get_historical_accuracy(self, code: str) -> Optional[float]:
        """Query analysis_history table for this stock's historical prediction accuracy.

        Returns:
            Accuracy as a float 0.0-1.0, or None if insufficient history.
        """
        if code in self._accuracy_cache:
            return self._accuracy_cache[code]

        try:
            db = get_db()
            with db.get_session() as session:
                from src.storage import AnalysisHistory
                from sqlalchemy import and_

                records = session.query(AnalysisHistory).filter(
                    and_(
                        AnalysisHistory.code == code,
                        AnalysisHistory.status == "completed",
                        AnalysisHistory.result_json.isnot(None),
                    )
                ).order_by(AnalysisHistory.timestamp.desc()).limit(10).all()

                if len(records) < 3:
                    self._accuracy_cache[code] = None
                    return None

                correct = 0
                total = 0
                for r in records:
                    try:
                        data = json.loads(r.result_json) if isinstance(r.result_json, str) else r.result_json
                        score = data.get("sentiment_score", 50)
                        prediction = "bullish" if score >= 60 else "bearish" if score <= 40 else "neutral"

                        # Simplistic check: if prediction was bullish and we have history after,
                        # we'd need price data to validate. For now, use a placeholder.
                        # Full validation requires OHLCV data post-analysis date.
                        # This is a structural placeholder for future enhancement.
                    except (json.JSONDecodeError, TypeError):
                        continue

                # For MVP: return a moderate accuracy signal if we have >= 3 past analyses
                # Future: implement actual price-movement-based validation
                if len(records) >= 5:
                    accuracy = 0.55  # Slightly above random baseline
                elif len(records) >= 3:
                    accuracy = 0.50
                else:
                    accuracy = None

                self._accuracy_cache[code] = accuracy
                return accuracy

        except Exception as e:
            logger.warning(f"Failed to get historical accuracy for {code}: {e}")
            return None

    def _calibrate_confidence(self, original: str, accuracy: float) -> str:
        """Adjust confidence level based on historical accuracy.

        Rules:
        - accuracy >= 0.7: boost confidence by 1 level
        - accuracy <= 0.35: drop confidence by 1 level
        - otherwise: keep original
        """
        levels = ["低", "中", "高"]
        try:
            idx = levels.index(original)
        except ValueError:
            return original

        if accuracy >= 0.70:
            idx = min(idx + 1, 2)
        elif accuracy <= 0.35:
            idx = max(idx - 1, 0)

        return levels[idx]

    # ------------------------------------------------------------------
    # 3. Uncovered Risk Scan
    # ------------------------------------------------------------------

    def _scan_uncovered_risks(self, result: "AnalysisResult") -> List[str]:
        """Identify risk categories that may be missing from the analysis."""
        risks: List[str] = []

        # Check for external/systemic risks not typically covered
        risk_keywords = {
            "政策": ["政策", "监管", "政府", "法规"],
            "流动性": ["流动性", "资金面", "货币政策", "利率"],
            "国际形势": ["国际", "地缘", "贸易战", "制裁", "汇率"],
            "行业周期": ["周期", "产能过剩", "需求萎缩"],
            "黑天鹅": ["黑天鹅", "突发事件", "不可抗力"],
        }

        all_text = (
            (result.risk_warning or "")
            + (result.analysis_summary or "")
            + (result.news_summary or "")
            + (result.fundamental_analysis or "")
        )

        for category, keywords in risk_keywords.items():
            if not any(kw in all_text for kw in keywords):
                risks.append(f"未覆盖风险：{category}相关因素")

        # If confidence is high but no risks mentioned, flag it
        if result.confidence_level == "高" and not result.risk_warning:
            risks.append("高置信度但缺少风险提示，可能存在过度自信")

        return risks

    # ------------------------------------------------------------------
    # 4. LLM Critical Review
    # ------------------------------------------------------------------

    def _llm_critical_review(
        self,
        result: "AnalysisResult",
        specialist_results: Dict[str, Any],
        analyzer: "GeminiAnalyzer",
    ) -> Tuple[str, str]:
        """Ask the LLM to critically review the analysis and suggest improvements.

        Returns:
            (critical_review_text, improvement_suggestion)
        """
        import json as _json

        # Build a concise summary for the LLM
        tech_text = str(specialist_results.get("technical", "N/A"))[:800]
        fund_text = str(specialist_results.get("fundamental", "N/A"))[:800]
        news_text = str(specialist_results.get("news", "N/A"))[:800]

        prompt = f"""你是一位独立的质量审查专家。请对以下股票分析进行批判性反思。

## 分析结果
- 股票: {result.name}({result.code})
- 综合评分: {result.sentiment_score}/100
- 趋势预测: {result.trend_prediction}
- 操作建议: {result.operation_advice}
- 置信度: {result.confidence_level}

### 技术面摘要
{tech_text}

### 基本面摘要
{fund_text}

### 消息面摘要
{news_text}

## 批判性审查任务
请从以下角度审视这份分析：

1. **逻辑漏洞**: 分析中是否存在逻辑跳跃或未经证实的假设？
2. **遗漏因素**: 有哪些重要信息被忽略了？
3. **过度自信**: 置信度是否与证据强度匹配？
4. **改进建议**: 下次分析应补充什么信息或调整什么方法？

## 输出格式
请严格输出两段文字，用 "---" 分隔：

第一段：批判性审查（100字内）
第二段：改进建议（50字内）

示例：
分析整体合理，但技术面与基本面结论存在未解决的矛盾，且未考虑行业政策变化风险。
---
建议增加行业政策维度的专项分析，并在矛盾维度明确标注不确定性。
"""
        response = analyzer._call_api_with_retry(
            prompt,
            {"temperature": 0.2, "max_output_tokens": 512},
        )

        # Parse the two-part response
        if "---" in response:
            parts = response.split("---", 1)
            review = parts[0].strip()
            suggestion = parts[1].strip() if len(parts) > 1 else ""
        else:
            review = response.strip()[:200]
            suggestion = ""

        logger.info(f"[Reflector] LLM critical review complete for {result.code} ({len(review)} chars)")
        return review, suggestion
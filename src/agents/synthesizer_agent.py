# -*- coding: utf-8 -*-
"""Synthesizer agent that combines specialist reports into a final analysis.

Takes outputs from the Technical, Fundamental, and News agents plus
the original context, then produces a comprehensive AnalysisResult
with weighted scores, contradiction resolution, and actionable advice.
"""

import json
import logging
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.analyzer import GeminiAnalyzer, AnalysisResult

logger = logging.getLogger(__name__)


class SynthesizerAgent:
    """Synthesizes three specialist reports into a final AnalysisResult.

    Responsibilities:
    1. Compare and reconcile potentially contradictory specialist views
    2. Assign a weighted composite score based on each dimension
    3. Generate the final decision dashboard (trend, operation, confidence)
    4. Produce actionable position advice and risk warnings

    Weighting strategy:
    - Technical: 40% (short-term price action is most actionable)
    - Fundamental: 35% (long-term value anchor)
    - News/Sentiment: 25% (can override in extreme cases)
    """

    def __init__(self):
        self.name = "synthesizer"
        self.role = "综合分析专家"

    def get_system_prompt(self) -> str:
        return """你是一位顶级的投资决策综合分析师，擅长整合多维度信息并做出清晰的投资决策。

## 你的职责
1. 阅读三位专家的独立分析报告（技术面、基本面、消息面）
2. 识别不同专家观点之间的一致性和矛盾
3. 综合评估后给出最终的投资决策建议
4. 生成完整的【决策仪表盘】JSON格式输出

## 综合原则
- **技术面权重40%**：短期价格行为最直接影响交易时机
- **基本面权重35%**：长期价值锚定，决定持股信心
- **消息面权重25%**：极端情况下可覆盖其他判断（如重大利空）

## 矛盾处理规则
- 当技术面和基本面结论矛盾时，优先参考技术面（短期操作）但基本面决定仓位大小
- 当消息面出现重大利空（如监管处罚、业绩暴雷），直接下调评级至少2档
- 当三位专家方向一致时，置信度标注为"高"
- 当两位看多一位看空时，置信度标注为"中"
- 当两位看空一位看多时，置信度标注为"低"

## 输出格式要求
请严格按照以下JSON格式输出你的综合分析结果：

```json
{
    "sentiment_score": <0-100整数>,
    "trend_prediction": "强烈看多/看多/震荡/看空/强烈看空",
    "operation_advice": "买入/加仓/持有/减仓/卖出/观望",
    "confidence_level": "高/中/低",

    "dashboard": {
        "core_conclusion": {
            "one_sentence": "一句话核心结论",
            "signal_type": "🟢买入信号/🟡持有观望/🔴卖出信号/⚠️风险警告",
            "time_sensitivity": "立即行动/今日内/本周内/不急",
            "position_advice": {
                "no_position": "空仓者具体操作建议",
                "has_position": "持仓者具体操作建议"
            }
        },
        "battle_plan": {
            "sniper_points": {
                "entry_price": "建议买入价",
                "stop_loss": "止损价",
                "target_price": "目标价"
            },
            "action_checklist": ["检查项1", "检查项2", "检查项3"]
        },
        "intelligence": {
            "risk_alerts": ["风险1", "风险2"],
            "catalyst_events": ["催化剂1"],
            "expert_consensus": "三位专家一致看多/存在分歧/一致看空"
        }
    },

    "technical_analysis": "技术面综合结论(50字内)",
    "fundamental_analysis": "基本面综合结论(50字内)",
    "news_summary": "消息面综合结论(50字内)",
    "market_sentiment": "市场情绪总结(50字内)",

    "trend_analysis": "走势综合分析(100字内)",
    "short_term_outlook": "短期(1-5天)展望(50字内)",
    "medium_term_outlook": "中期(1-2周)展望(50字内)",

    "ma_analysis": "均线分析摘要",
    "volume_analysis": "量能分析摘要",
    "pattern_analysis": "形态分析摘要",

    "sector_position": "行业地位判断",
    "company_highlights": "公司亮点总结",
    "hot_topics": "热点话题",

    "analysis_summary": "综合分析摘要(100字内)",
    "key_points": "核心要点：1.要点1 2.要点2 3.要点3",
    "risk_warning": "主要风险提示",
    "buy_reason": "买入/卖出核心理由",

    "data_sources": "技术面分析+基本面分析+消息面分析",
    "search_performed": true
}
```

注意：
- sentiment_score必须客观反映综合判断
- 如果三位专家都认为风险很大，score应低于40
- 如果三位专家都看好且有催化剂，score应在70以上
- 不要让单一维度的极端观点过度影响综合评分"""

    def _build_synthesis_prompt(
        self,
        code: str,
        name: str,
        specialist_results: Dict[str, str],
        context: Dict[str, Any],
    ) -> str:
        """Build the synthesis prompt combining all specialist reports."""
        technical_report = specialist_results.get("technical", "技术面分析未完成")
        fundamental_report = specialist_results.get("fundamental", "基本面分析未完成")
        news_report = specialist_results.get("news", "消息面分析未完成")

        # Truncate very long reports to avoid token limits
        max_per_report = 3000
        if len(technical_report) > max_per_report:
            technical_report = technical_report[:max_per_report] + "\n...[内容过长已截断]"
        if len(fundamental_report) > max_per_report:
            fundamental_report = fundamental_report[:max_per_report] + "\n...[内容过长已截断]"
        if len(news_report) > max_per_report:
            news_report = news_report[:max_per_report] + "\n...[内容过长已截断]"

        today = context.get("today", {})

        prompt = f"""{self.get_system_prompt()}

---
## 综合分析任务：{name}（{code}）

### 当前价格数据
| 指标 | 数值 |
|------|------|
| 最新价 | {today.get('close', 'N/A')} |
| 涨跌幅 | {today.get('pct_chg', 'N/A')}% |
| 市盈率(PE) | {today.get('pe', 'N/A')} |
| 市净率(PB) | {today.get('pb', 'N/A')} |
| 总市值 | {today.get('total_mv', 'N/A')} |

---

### 专家报告一：技术面分析
```
{technical_report}
```

---

### 专家报告二：基本面分析
```
{fundamental_report}
```

---

### 专家报告三：消息面/情绪分析
```
{news_report}
```

---

## 你的任务
请基于以上三位专家的分析报告，按照【输出格式要求】中的JSON格式，
生成一份完整的【决策仪表盘】综合分析报告。

**重要提醒**：
1. 仔细对比三位专家的观点，找出共识和分歧
2. 按照权重原则（技术40%/基本面35%/消息25%）综合评分
3. 给出明确的、可操作的买卖建议
4. 标注具体的买入价、止损价和目标价
5. 如果某位专家的分析不完整或缺失，在expert_consensus中说明"""
        return prompt

    def synthesize(
        self,
        code: str,
        context: Dict[str, Any],
        specialist_results: Dict[str, str],
        analyzer: "GeminiAnalyzer",
    ) -> "AnalysisResult":
        """Synthesize specialist reports into a final AnalysisResult.

        Args:
            code: Stock code
            context: Original analysis context dict
            specialist_results: Dict mapping agent name to report text
            analyzer: GeminiAnalyzer instance for API calls and response parsing

        Returns:
            AnalysisResult with the synthesized analysis
        """
        from src.analyzer import AnalysisResult

        name = context.get("stock_name", code)

        # Check if all specialists failed
        error_count = sum(
            1 for v in specialist_results.values()
            if isinstance(v, dict) and "error" in v
        )
        if error_count == len(specialist_results):
            logger.warning(f"All specialists failed for {code}, returning error result")
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction="震荡",
                operation_advice="持有",
                confidence_level="低",
                analysis_summary="多智能体分析失败：所有专家均返回错误，请稍后重试",
                risk_warning="分析系统暂时不可用",
                success=False,
                error_message="All specialist agents failed",
            )

        # Extract text from results that may be dicts with error keys
        processed_results: Dict[str, str] = {}
        for agent_name, result in specialist_results.items():
            if isinstance(result, dict) and "error" in result:
                processed_results[agent_name] = (
                    f"[该专家分析失败: {result['error']}]"
                )
            else:
                processed_results[agent_name] = str(result)

        try:
            prompt = self._build_synthesis_prompt(code, name, processed_results, context)

            generation_config = {
                "temperature": 0.3,
                "max_output_tokens": 8192,
            }

            logger.info(f"[Synthesizer] Starting synthesis for {name}({code})")
            response_text = analyzer._call_api_with_retry(prompt, generation_config)
            logger.info(
                f"[Synthesizer] Synthesis complete for {name}({code}), "
                f"response length: {len(response_text)}"
            )

            # Parse the synthesis response into an AnalysisResult
            result = analyzer._parse_response(response_text, code, name)
            result.raw_response = response_text
            result.search_performed = True
            result.data_sources = "多智能体综合分析（技术面+基本面+消息面）"

            return result

        except Exception as e:
            logger.error(f"Synthesizer failed for {name}({code}): {e}")
            return AnalysisResult(
                code=code,
                name=name,
                sentiment_score=50,
                trend_prediction="震荡",
                operation_advice="持有",
                confidence_level="低",
                analysis_summary=f"综合分析出错: {str(e)[:100]}",
                risk_warning="分析合成失败，请稍后重试",
                success=False,
                error_message=str(e),
            )

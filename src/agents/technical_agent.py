# -*- coding: utf-8 -*-
"""Technical analysis specialist agent.

Focuses on price action, moving averages, RSI/MACD/Bollinger,
support/resistance levels, volume patterns, and chart patterns.
"""

from typing import Dict, Any
from .base_agent import BaseAgent


class TechnicalAgent(BaseAgent):
    """Technical analysis specialist for A-share stocks.

    Evaluates: price action, MA alignment (MA5/MA10/MA20),
    RSI/MACD/Bollinger indicators, support/resistance zones,
    volume-price relationships, chip distribution, and trend phase.
    """

    def __init__(self):
        super().__init__(
            name="technical",
            role="技术面分析专家",
        )

    def get_system_prompt(self) -> str:
        return """你是一位资深的技术面分析专家，拥有20年A股实战经验，专注于技术指标和价格行为分析。

## 你的专业领域
1. 价格行为和K线形态识别（锤子线、吞没形态、十字星、头肩顶/底等）
2. 移动平均线系统分析（MA5/MA10/MA20/MA60排列、金叉死叉、均线斜率）
3. 技术指标解读（RSI超买超卖、MACD背离、布林带收窄/扩张、KDJ信号）
4. 关键支撑位和压力位计算（前高前低、均线位置、筹码密集区）
5. 成交量分析和量价关系（放量突破、缩量回调、天量见顶）
6. 趋势强度评估和趋势阶段判断（上涨/下跌/盘整/筑底/筑顶）
7. 筹码分布和成本分析（获利比例、集中度、平均成本）

## 交易理念约束（严格遵守）
- **均线多头排列（MA5 > MA10 > MA20）是做多的必要条件**
- **乖离率超过5%时严禁追高**（乖离率 = (现价 - MA5) / MA5 × 100%）
- **缩量回踩MA5获得支撑是最佳买点**
- **跌破MA20应观望，空头排列坚决不碰**

## 输出格式
请严格按以下结构输出你的分析报告：

### 1. 技术面总评分
给出1-10分的综合技术面评分，并简要说明理由。

### 2. 均线系统分析
- 当前均线排列状态（多头/空头/缠绕）
- 是否有金叉/死叉信号
- 乖离率评估（安全/警戒/危险）

### 3. 关键位分析
- 支撑位（至少2个，注明价格和依据）
- 压力位（至少2个，注明价格和依据）

### 4. 技术指标信号
- RSI状态和建议
- MACD信号和方向
- 布林带位置

### 5. 量价分析
- 当前量能状态（放量/缩量/平量）
- 量价配合情况

### 6. 短期展望（1-5个交易日）
- 最可能的走势预判
- 需要关注的技术信号

### 7. 技术面风险提示
- 列出2-3个需要警惕的技术风险"""

    def build_prompt(self, code: str, context: Dict[str, Any]) -> str:
        today = context.get("today") or {}
        name = context.get("stock_name") or context.get("code", code)
        trend = context.get("trend_analysis") or {}
        realtime = context.get("realtime") or {}
        chip = context.get("chip") or {}

        prompt = f"""{self.get_system_prompt()}

---
## 分析任务：{name}（{code}）

### 今日行情
| 指标 | 数值 |
|------|------|
| 收盘价 | {today.get('close', 'N/A')} |
| 开盘价 | {today.get('open', 'N/A')} |
| 最高价 | {today.get('high', 'N/A')} |
| 最低价 | {today.get('low', 'N/A')} |
| 涨跌幅 | {today.get('pct_chg', 'N/A')}% |
| 成交量 | {today.get('volume', 'N/A')} |
| 成交额 | {today.get('amount', 'N/A')} |

### 均线系统
| 均线 | 数值 | 用途 |
|------|------|------|
| MA5 | {today.get('ma5', 'N/A')} | 短期趋势 |
| MA10 | {today.get('ma10', 'N/A')} | 中短期趋势 |
| MA20 | {today.get('ma20', 'N/A')} | 中期趋势 |
| 均线形态 | {context.get('ma_status', '未知')} | |

### 技术指标
| 指标 | 数值 |
|------|------|
| RSI(14) | {context.get('rsi', 'N/A')} |
| MACD信号 | {context.get('macd_signal', 'N/A')} |
| 布林带位置 | {context.get('boll_position', 'N/A')} |

### 趋势预判数据
| 指标 | 数值 |
|------|------|
| 趋势状态 | {trend.get('trend_status', 'N/A')} |
| 乖离率(MA5) | {trend.get('bias_ma5', 'N/A')}% |
| 量比 | {realtime.get('volume_ratio', 'N/A')} |
| 换手率 | {realtime.get('turnover_rate', 'N/A')}% |

### 筹码分布
| 指标 | 数值 |
|------|------|
| 获利比例 | {chip.get('profit_ratio', 'N/A')} |
| 平均成本 | {chip.get('avg_cost', 'N/A')} |
| 90%集中度 | {chip.get('concentration_90', 'N/A')} |
| 筹码状态 | {chip.get('chip_status', 'N/A')} |

请基于以上数据，按照你的专业框架进行纯技术面分析。
注意：不要涉及基本面和消息面，只分析技术指标和价格行为。"""
        return prompt

# -*- coding: utf-8 -*-
"""Fundamental analysis specialist agent.

Focuses on PE/PB/ROE, revenue growth, industry position,
financial health, and valuation analysis.
"""

from typing import Dict, Any
from .base_agent import BaseAgent


class FundamentalAgent(BaseAgent):
    """Fundamental analysis specialist for A-share stocks.

    Evaluates: valuation metrics (PE/PB/PS), profitability (ROE/ROA),
    growth trends (revenue/earnings), industry positioning,
    financial health, and competitive moat.
    """

    def __init__(self):
        super().__init__(
            name="fundamental",
            role="基本面分析专家",
        )

    def get_system_prompt(self) -> str:
        return """你是一位资深的基本面分析专家，拥有15年A股价值投资研究经验，专注于企业内在价值评估。

## 你的专业领域
1. 估值分析（PE/PB/PS/PEG，历史分位数，行业对比）
2. 盈利能力分析（ROE/ROA/毛利率/净利率，杜邦分解）
3. 成长性分析（营收增速/利润增速/现金流增速）
4. 财务健康度（资产负债率/流动比率/利息保障倍数）
5. 行业地位分析（市占率/竞争格局/护城河）
6. 公司治理和股东结构（股权集中度/机构持仓/增减持）
7. 分红与回报（股息率/分红率/回购）

## A股市场特点
- 小市值成长股溢价明显
- 行业政策影响巨大（产业政策决定估值中枢）
- 国企vs民企估值体系不同
- 北向资金流向影响白马股估值

## 输出格式
请严格按以下结构输出你的分析报告：

### 1. 基本面总评分
给出1-10分的综合基本面评分，并简要说明理由。

### 2. 估值分析
- 当前PE/PB及历史分位数
- 与同行业对比（高估/合理/低估）
- PEG分析（如有增长数据）

### 3. 盈利能力
- ROE水平及趋势
- 毛利率和净利率分析
- 盈利质量判断

### 4. 财务健康度
- 资产负债结构
- 现金流状况
- 偿债能力

### 5. 行业地位
- 公司在行业中的竞争位置
- 护城河评估
- 行业景气度判断

### 6. 成长性展望
- 未来1-2年业绩增长预期
- 增长驱动力分析

### 7. 基本面风险提示
- 列出2-3个需要关注的基本面风险"""

    def build_prompt(self, code: str, context: Dict[str, Any]) -> str:
        today = context.get("today", {})
        name = context.get("stock_name", context.get("code", code))
        realtime = context.get("realtime", {})
        if not isinstance(realtime, dict):
            realtime = {}

        prompt = f"""{self.get_system_prompt()}

---
## 分析任务：{name}（{code}）

### 基础估值数据
| 指标 | 数值 |
|------|------|
| 最新价 | {today.get('close', 'N/A')} |
| 市盈率(PE) | {today.get('pe', 'N/A')} |
| 市净率(PB) | {today.get('pb', 'N/A')} |
| 总市值 | {today.get('total_mv', 'N/A')} |
| 流通市值 | {realtime.get('circ_mv', 'N/A')} |
| 60日涨跌幅 | {realtime.get('change_60d', 'N/A')}% |

### 关键财务指标
| 指标 | 数值 |
|------|------|
| ROE | {today.get('roe', 'N/A')}% |
| 营收增速 | {today.get('revenue_growth', 'N/A')}% |
| 净利润增速 | {today.get('profit_growth', 'N/A')}% |
| 毛利率 | {today.get('gross_margin', 'N/A')}% |
| 资产负债率 | {today.get('debt_ratio', 'N/A')}% |
| 股息率 | {today.get('dividend_yield', 'N/A')}% |

### 行业对比参考
| 指标 | 数值 |
|------|------|
| 行业平均PE | {today.get('industry_pe', 'N/A')} |
| 行业平均PB | {today.get('industry_pb', 'N/A')} |
| 行业地位 | {context.get('sector_position', 'N/A')} |

请基于以上数据，按照你的专业框架进行纯基本面分析。
注意：不要涉及技术面和消息面，只分析企业基本面和估值。"""
        return prompt

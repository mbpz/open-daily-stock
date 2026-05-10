# -*- coding: utf-8 -*-
"""News and sentiment analysis specialist agent.

Focuses on recent news sentiment, catalyst events, regulatory risks,
institutional activity, and social media sentiment.
"""

from typing import Dict, Any
from .base_agent import BaseAgent


class NewsAgent(BaseAgent):
    """News and sentiment analysis specialist for A-share stocks.

    Evaluates: recent news sentiment, catalyst events (earnings,
    product launches, policy changes), regulatory and compliance risks,
    institutional trading activity, and broader market sentiment.
    """

    def __init__(self):
        super().__init__(
            name="news",
            role="消息面与情绪分析专家",
        )

    def get_system_prompt(self) -> str:
        return """你是一位资深的消息面和市场情绪分析专家，专注于从海量信息中提取对股价有实质影响的关键信号。

## 你的专业领域
1. 新闻事件解读（利好/利空判断、影响程度评估、持续性判断）
2. 政策影响分析（行业政策、监管变化、宏观政策对个股的影响）
3. 公告解读（业绩预告、重大合同、股权变动、增减持、分红方案）
4. 机构动向监测（龙虎榜、北向资金、大宗交易、机构调研）
5. 市场情绪判断（热点概念、板块轮动、投资者情绪指标）
6. 事件催化识别（即将发生的可能影响股价的事件）
7. 风险事件预警（解禁、减持、诉讼、监管处罚）

## A股消息面特点
- 政策驱动性强：行业政策可以完全改变估值逻辑
- 概念炒作普遍：热点概念短期影响大
- 业绩预告窗口期敏感：1月、4月、7月、10月为业绩披露密集期
- 北向资金是重要情绪指标
- 龙虎榜数据对短期走势指引性强

## 输出格式
请严格按以下结构输出你的分析报告：

### 1. 消息面总评分
给出1-10分的综合消息面评分，说明整体情绪偏向（利好/中性/利空）。

### 2. 近期重要新闻摘要
- 列出近期关键新闻标题和核心内容
- 标注每条新闻的影响性质（重大利好/利好/中性/利空/重大利空）

### 3. 政策与监管环境
- 当前行业政策方向
- 是否有新的监管变化
- 政策对公司的潜在影响

### 4. 机构动向
- 近期北向资金流向
- 龙虎榜活跃度
- 机构调研频率

### 5. 事件催化剂
- 近期可能影响股价的重大事件
- 事件发生的时间窗口

### 6. 市场情绪判断
- 当前市场对该股的情绪倾向
- 散户和机构的看法分歧

### 7. 消息面风险提示
- 列出2-3个需要警惕的消息面风险（如解禁、减持、诉讼等）"""

    def build_prompt(self, code: str, context: Dict[str, Any]) -> str:
        today = context.get("today", {})
        name = context.get("stock_name", context.get("code", code))
        news_context = context.get("_news_context", "")

        prompt = f"""{self.get_system_prompt()}

---
## 分析任务：{name}（{code}）

### 基础信息
| 指标 | 数值 |
|------|------|
| 最新价 | {today.get('close', 'N/A')} |
| 涨跌幅 | {today.get('pct_chg', 'N/A')}% |
| 总市值 | {today.get('total_mv', 'N/A')} |
| 所属行业 | {context.get('industry', 'N/A')} |
| 市场类型 | {context.get('market', 'A股')} |

### 新闻与舆情数据
{news_context if news_context else '当前无可用新闻数据，请基于市场常识和行业研判进行分析。'}

### 近期公告与事件
{context.get('recent_events', '无近期重大事件数据')}

请基于以上数据和你的专业知识，进行纯消息面和情绪面分析。
注意：不要涉及技术面分析和深度基本面分析，只关注消息、情绪、政策和事件驱动因素。"""
        return prompt

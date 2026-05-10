# -*- coding: utf-8 -*-
"""A-share specific analysis prompt templates."""
from typing import Dict, Optional


# === Prompt Templates ===

CN_ANALYST_SYSTEM_PROMPT = """你是一位专业的A股分析师，精通以下分析框架：
1. 市场情绪与资金流向分析
2. 行业轮动与主题投资
3. 技术面与资金面共振
4. 宏观经济政策影响
5. 个股基本面深度研究

请用中文回复。分析应包含：评分（1-5星）、看涨/看跌判断、核心逻辑、风险提示。"""

CN_FACTOR_ANALYSIS_TEMPLATE = """
## {stock_name}（{stock_code}）A股深度分析

### 基础数据
- 最新价: {price}
- 涨跌幅: {change_pct}%
- 成交量: {volume}
- 市盈率(PE): {pe}
- 市净率(PB): {pb}
- 总市值: {total_mv}

### 技术指标
- MA5: {ma5}, MA10: {ma10}, MA20: {ma20}
- 均线形态: {ma_status}
- RSI(14): {rsi}
- MACD: {macd_signal}

### 机构动向
{institutional_context}

### 行业对比
{industry_context}

### 近期新闻
{news_context}

### 分析要求
请从以下维度进行分析：
1. **技术面**：当前价格处于什么阶段？关键支撑/压力位在哪？
2. **资金面**：机构动向如何？主力资金是流入还是流出？
3. **行业面**：所处行业当前景气度？板块轮动情况？
4. **情绪面**：近期新闻和市场情绪如何？
5. **综合判断**：给出明确的看涨/看跌/中性评级，附详细理由。
"""

CN_SECTOR_ROTATION_PROMPT = """
当前行业轮动分析：
{industry_data}

请分析：
1. 当前哪些行业处于强势期？
2. 哪些行业开始出现轮动信号？
3. {stock_name}（{stock_code}）所在行业的前景判断
"""

CN_INSTITUTIONAL_PROMPT = """
{stock_name}（{stock_code}）机构动向：
{institutional_data}

请分析：
1. 机构整体持仓趋势（增持/减持）
2. 近期龙虎榜活跃度
3. 北向资金对该股的关注度
4. 机构动向对股价的潜在影响
"""

CN_MACRO_PROMPT = """
宏观经济与政策分析：
- GDP增速: {gdp}
- CPI: {cpi}
- PMI: {pmi}
- 货币供应M2: {m2}
- 政策关键词: {policy_keywords}

请分析这些宏观因子对{stock_name}（{stock_code}）的影响：
1. 货币政策松紧对估值的影响
2. 产业政策对该行业的支持力度
3. 宏观周期下该股的防御/进攻属性
"""


class CNPromptBuilder:
    """Build A-share specific analysis prompts from context data."""

    @staticmethod
    def build_analysis_prompt(
        context: Dict,
        inst_context: str = "",
        news_context: str = "",
        industry_context: str = "",
    ) -> str:
        """Build full A-share analysis prompt from context dict."""
        today = context.get("today", {})
        return CN_FACTOR_ANALYSIS_TEMPLATE.format(
            stock_name=context.get("stock_name", context.get("code", "")),
            stock_code=context.get("code", ""),
            price=today.get("close", "N/A"),
            change_pct=today.get("pct_chg", "N/A"),
            volume=today.get("volume", "N/A"),
            pe=today.get("pe", "N/A"),
            pb=today.get("pb", "N/A"),
            total_mv=today.get("total_mv", "N/A"),
            ma5=today.get("ma5", "N/A"),
            ma10=today.get("ma10", "N/A"),
            ma20=today.get("ma20", "N/A"),
            ma_status=context.get("ma_status", "N/A"),
            rsi=context.get("rsi", "N/A"),
            macd_signal=context.get("macd_signal", "N/A"),
            institutional_context=inst_context or "无机构动向数据",
            industry_context=industry_context or "无行业对比数据",
            news_context=news_context or "无近期新闻",
        )

    @staticmethod
    def build_verdict_badge(result: Dict) -> Dict:
        """Parse AI result into verdict badge data.

        Returns: {"verdict": "bullish|bearish|neutral", "score": 1-5, "confidence": 0-100}
        """
        # Simple keyword-based parsing
        text = str(result).lower()
        if any(w in text for w in ["看涨", "牛市", "买入", "bullish", "buy signal"]):
            verdict = "bullish"
        elif any(w in text for w in ["看跌", "熊市", "卖出", "bearish", "sell signal"]):
            verdict = "bearish"
        else:
            verdict = "neutral"

        # Extract star rating if present
        import re
        stars = re.search(r"(\d)[\s★]?星", str(result))
        score = int(stars.group(1)) if stars else 3

        # Count bullish/bearish signals for confidence
        text_lower = str(result).lower()
        bullish_count = sum(1 for w in ["看涨", "买入", "bullish", "上涨", "利好", "增持"] if w in text_lower)
        bearish_count = sum(1 for w in ["看跌", "卖出", "bearish", "下跌", "利空", "减持"] if w in text_lower)
        total_signals = max(bullish_count + bearish_count, 1)
        confidence = min(95, 50 + (total_signals * 10))

        return {"verdict": verdict, "score": score, "confidence": confidence}

    @staticmethod
    def build_summary_bulletpoints(result_text: str) -> list:
        """Extract key bullet points from AI result."""
        lines = result_text.strip().split("\n")
        bullets = [
            l.strip("- *").strip()
            for l in lines
            if l.strip().startswith(("-", "*", "•", "1.", "2.", "3."))
        ]
        return bullets[:5]  # Top 5 points

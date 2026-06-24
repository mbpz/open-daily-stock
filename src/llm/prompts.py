"""Prompts + 股票名称映射 — 迁自 src/analyzer.py。

包含：
- 4 个 specialist system prompts（TECHNICAL/FUNDAMENTAL/NEWS/SYNTHESIZER）
- DEEP_AGENTS / DEEP_PROMPTS 注册表
- STOCK_NAME_MAP（60+ 常见股票代码→中文名）
- get_stock_name_multi_source（多来源获取股票名称）
- _format_volume / _format_amount（格式化成交量和成交额）
- format_prompt（生成决策仪表盘 prompt）
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================
# P5-5: Deep Analysis Specialist System Prompts
# ============================================================

TECHNICAL_SYSTEM_PROMPT = """You are a technical analysis specialist.
Analyze: price trends, MA crossovers, RSI/MACD/Bollinger/KDJ signals, support/resistance, volume patterns.
Output structured JSON: {"trend": "bullish/bearish/neutral", "key_signals": [...], "support": float, "resistance": float, "score": 0-100}"""

FUNDAMENTAL_SYSTEM_PROMPT = """You are a fundamental analysis specialist.
Analyze: PE/PB ratios, revenue growth, profit margins, institutional flows, industry position.
Output structured JSON: {"valuation": "undervalued/fair/overvalued", "key_metrics": [...], "risks": [...], "score": 0-100}"""

NEWS_SYSTEM_PROMPT = """You are a market sentiment specialist.
Analyze: recent news sentiment, social media buzz, regulatory changes, sector rotation.
Output structured JSON: {"sentiment": "positive/negative/neutral", "key_drivers": [...], "risk_events": [...], "score": 0-100}"""

SYNTHESIZER_PROMPT = """You are a lead investment analyst. Synthesize the three specialist reports into a final decision.
Output: final verdict (看涨/看跌/中性), composite score, key catalysts, risk factors, operation advice."""

DEEP_AGENTS = ["technical", "fundamental", "news"]
DEEP_PROMPTS = {
    "technical": TECHNICAL_SYSTEM_PROMPT,
    "fundamental": FUNDAMENTAL_SYSTEM_PROMPT,
    "news": NEWS_SYSTEM_PROMPT,
}


# ============================================================
# STOCK_NAME_MAP — 股票名称映射（常见股票）
# ============================================================

STOCK_NAME_MAP: Dict[str, str] = {
    # === A股 ===
    '600519': '贵州茅台',
    '000001': '平安银行',
    '300750': '宁德时代',
    '002594': '比亚迪',
    '600036': '招商银行',
    '601318': '中国平安',
    '000858': '五粮液',
    '600276': '恒瑞医药',
    '601012': '隆基绿能',
    '002475': '立讯精密',
    '300059': '东方财富',
    '002415': '海康威视',
    '600900': '长江电力',
    '601166': '兴业银行',
    '600028': '中国石化',
    # === 美股 ===
    'AAPL': '苹果',
    'TSLA': '特斯拉',
    'MSFT': '微软',
    'GOOGL': '谷歌A',
    'GOOG': '谷歌C',
    'AMZN': '亚马逊',
    'NVDA': '英伟达',
    'META': 'Meta',
    'AMD': 'AMD',
    'INTC': '英特尔',
    'BABA': '阿里巴巴',
    'PDD': '拼多多',
    'JD': '京东',
    'BIDU': '百度',
    'NIO': '蔚来',
    'XPEV': '小鹏汽车',
    'LI': '理想汽车',
    'COIN': 'Coinbase',
    'MSTR': 'MicroStrategy',
    # === 港股 (5位数字) ===
    '00700': '腾讯控股',
    '03690': '美团',
    '01810': '小米集团',
    '09988': '阿里巴巴',
    '09618': '京东集团',
    '09888': '百度集团',
    '01024': '快手',
    '00981': '中芯国际',
    '02015': '理想汽车',
    '09868': '小鹏汽车',
    '00005': '汇丰控股',
    '01299': '友邦保险',
    '00941': '中国移动',
    '00883': '中国海洋石油',
}


def get_stock_name_multi_source(
    stock_code: str,
    context: Optional[Dict] = None,
    data_manager=None,
) -> str:
    """多来源获取股票中文名称

    获取策略（按优先级）：
    1. 从传入的 context 中获取（realtime 数据）
    2. 从静态映射表 STOCK_NAME_MAP 获取
    3. 从 DataFetcherManager 获取（各数据源）
    4. 返回默认名称（股票+代码）
    """
    # 1. 从上下文获取（实时行情数据）
    if context:
        if context.get('stock_name'):
            name = context['stock_name']
            if name and not name.startswith('股票'):
                return name
        if 'realtime' in context and context['realtime'].get('name'):
            return context['realtime']['name']

    # 2. 从静态映射表获取
    if stock_code in STOCK_NAME_MAP:
        return STOCK_NAME_MAP[stock_code]

    # 3. 从数据源获取
    if data_manager is None:
        try:
            from data_provider.base import DataFetcherManager
            data_manager = DataFetcherManager()
        except Exception as e:
            logger.debug(f"无法初始化 DataFetcherManager: {e}")

    if data_manager:
        try:
            name = data_manager.get_stock_name(stock_code)
            if name:
                STOCK_NAME_MAP[stock_code] = name
                return name
        except Exception as e:
            logger.debug(f"从数据源获取股票名称失败: {e}")

    # 4. 返回默认名称
    return f'股票{stock_code}'


# ============================================================
# 格式化工具
# ============================================================


def format_volume(volume: Optional[float]) -> str:
    """格式化成交量显示"""
    if volume is None:
        return 'N/A'
    if volume >= 1e8:
        return f"{volume / 1e8:.2f} 亿股"
    elif volume >= 1e4:
        return f"{volume / 1e4:.2f} 万股"
    else:
        return f"{volume:.0f} 股"


def format_amount(amount: Optional[float]) -> str:
    """格式化成交额显示"""
    if amount is None:
        return 'N/A'
    if amount >= 1e8:
        return f"{amount / 1e8:.2f} 亿元"
    else:
        return f"{amount / 1e4:.2f} 万元"


# ============================================================
# 分析 Prompt 构建（决策仪表盘 v2.0）
# ============================================================


def build_analysis_prompt(
    context: Dict[str, Any],
    name: str,
    news_context: Optional[str] = None,
) -> str:
    """格式化分析提示词（决策仪表盘 v2.0）

    包含：技术指标、实时行情（量比/换手率）、筹码分布、趋势分析、新闻

    迁自 src/analyzer.py:GeminiAnalyzer._format_prompt。
    """
    code = context.get('code', 'Unknown')

    # 优先使用上下文中的股票名称
    stock_name = context.get('stock_name', name)
    if not stock_name or stock_name == f'股票{code}':
        stock_name = STOCK_NAME_MAP.get(code, f'股票{code}')

    today = context.get('today', {})

    # ========== 构建决策仪表盘格式的输入 ==========
    prompt = f"""# 决策仪表盘分析请求

## 📊 股票基础信息
| 项目 | 数据 |
|------|------|
| 股票代码 | **{code}** |
| 股票名称 | **{stock_name}** |
| 分析日期 | {context.get('date', '未知')} |

---

## 📈 技术面数据

### 今日行情
| 指标 | 数值 |
|------|------|
| 收盘价 | {today.get('close', 'N/A')} 元 |
| 开盘价 | {today.get('open', 'N/A')} 元 |
| 最高价 | {today.get('high', 'N/A')} 元 |
| 最低价 | {today.get('low', 'N/A')} 元 |
| 涨跌幅 | {today.get('pct_chg', 'N/A')}% |
| 成交量 | {format_volume(today.get('volume'))} |
| 成交额 | {format_amount(today.get('amount'))} |

### 均线系统（关键判断指标）
| 均线 | 数值 | 说明 |
|------|------|------|
| MA5 | {today.get('ma5', 'N/A')} | 短期趋势线 |
| MA10 | {today.get('ma10', 'N/A')} | 中短期趋势线 |
| MA20 | {today.get('ma20', 'N/A')} | 中期趋势线 |
| 均线形态 | {context.get('ma_status', '未知')} | 多头/空头/缠绕 |
"""

    # 添加实时行情数据（量比、换手率等）
    if 'realtime' in context:
        rt = context['realtime']
        prompt += f"""
### 实时行情增强数据
| 指标 | 数值 | 解读 |
|------|------|------|
| 当前价格 | {rt.get('price', 'N/A')} 元 | |
| **量比** | **{rt.get('volume_ratio', 'N/A')}** | {rt.get('volume_ratio_desc', '')} |
| **换手率** | **{rt.get('turnover_rate', 'N/A')}%** | |
| 市盈率(动态) | {rt.get('pe_ratio', 'N/A')} | |
| 市净率 | {rt.get('pb_ratio', 'N/A')} | |
| 总市值 | {format_amount(rt.get('total_mv'))} | |
| 流通市值 | {format_amount(rt.get('circ_mv'))} | |
| 60日涨跌幅 | {rt.get('change_60d', 'N/A')}% | 中期表现 |
"""

    # 添加筹码分布数据
    if 'chip' in context:
        chip = context['chip']
        profit_ratio = chip.get('profit_ratio', 0)
        prompt += f"""
### 筹码分布数据（效率指标）
| 指标 | 数值 | 健康标准 |
|------|------|----------|
| **获利比例** | **{profit_ratio:.1%}** | 70-90%时警惕 |
| 平均成本 | {chip.get('avg_cost', 'N/A')} 元 | 现价应高于5-15% |
| 90%筹码集中度 | {chip.get('concentration_90', 0):.2%} | <15%为集中 |
| 70%筹码集中度 | {chip.get('concentration_70', 0):.2%} | |
| 筹码状态 | {chip.get('chip_status', '未知')} | |
"""

    # 添加趋势分析结果（基于交易理念的预判）
    if 'trend_analysis' in context:
        trend = context['trend_analysis']
        bias_warning = "🚨 超过5%，严禁追高！" if trend.get('bias_ma5', 0) > 5 else "✅ 安全范围"
        prompt += f"""
### 趋势分析预判（基于交易理念）
| 指标 | 数值 | 判定 |
|------|------|------|
| 趋势状态 | {trend.get('trend_status', '未知')} | |
| 均线排列 | {trend.get('ma_alignment', '未知')} | MA5>MA10>MA20为多头 |
| 趋势强度 | {trend.get('trend_strength', 0)}/100 | |
| **乖离率(MA5)** | **{trend.get('bias_ma5', 0):+.2f}%** | {bias_warning} |
| 乖离率(MA10) | {trend.get('bias_ma10', 0):+.2f}% | |
| 量能状态 | {trend.get('volume_status', '未知')} | {trend.get('volume_trend', '')} |
| 系统信号 | {trend.get('buy_signal', '未知')} | |
| 系统评分 | {trend.get('signal_score', 0)}/100 | |

#### 系统分析理由
**买入理由**：
{chr(10).join('- ' + r for r in trend.get('signal_reasons', ['无'])) if trend.get('signal_reasons') else '- 无'}

**风险因素**：
{chr(10).join('- ' + r for r in trend.get('risk_factors', ['无'])) if trend.get('risk_factors') else '- 无'}
"""

    # 添加昨日对比数据
    if 'yesterday' in context:
        volume_change = context.get('volume_change_ratio', 'N/A')
        prompt += f"""
### 量价变化
- 成交量较昨日变化：{volume_change}倍
- 价格较昨日变化：{context.get('price_change_ratio', 'N/A')}%
"""

    # 添加新闻搜索结果（重点区域）
    prompt += """
---

## 📰 舆情情报
"""
    if news_context:
        prompt += f"""
以下是 **{stock_name}({code})** 近7日的新闻搜索结果，请重点提取：
1. 🚨 **风险警报**：减持、处罚、利空
2. 🎯 **利好催化**：业绩、合同、政策
3. 📊 **业绩预期**：年报预告、业绩快报

```
{news_context}
```
"""
    else:
        prompt += """
未搜索到该股票近期的相关新闻。请主要依据技术面数据进行分析。
"""

    # 注入缺失数据警告
    if context.get('data_missing'):
        prompt += """
⚠️ **数据缺失警告**
由于接口限制，当前无法获取完整的实时行情和技术指标数据。
请 **忽略上述表格中的 N/A 数据**，重点依据 **【📰 舆情情报】** 中的新闻进行基本面和情绪面分析。
在回答技术面问题（如均线、乖离率）时，请直接说明"数据缺失，无法判断"，**严禁编造数据**。
"""

    # 明确的输出要求
    prompt += f"""
---

## ✅ 分析任务

请为 **{stock_name}({code})** 生成【决策仪表盘】，严格按照 JSON 格式输出。

### 重点关注（必须明确回答）：
1. ❓ 是否满足 MA5>MA10>MA20 多头排列？
2. ❓ 当前乖离率是否在安全范围内（<5%）？—— 超过5%必须标注"严禁追高"
3. ❓ 量能是否配合（缩量回调/放量突破）？
4. ❓ 筹码结构是否健康？
5. ❓ 消息面有无重大利空？（减持、处罚、业绩变脸等）

### 决策仪表盘要求：
- **核心结论**：一句话说清该买/该卖/该等
- **持仓分类建议**：空仓者怎么做 vs 持仓者怎么做
- **具体狙击点位**：买入价、止损价、目标价（精确到分）
- **检查清单**：每项用 ✅/⚠️/❌ 标记

请输出完整的 JSON 格式决策仪表盘。"""

    return prompt

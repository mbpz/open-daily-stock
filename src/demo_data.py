# -*- coding: utf-8 -*-
"""Demo data for first-launch experience (P5-4).

Provides realistic sample market data so users can explore the product
before configuring any API keys.
"""
from datetime import datetime, timedelta
from typing import Dict, List, Any
import random

random.seed(42)


# ═══════════════════════════════════════════════════════════════
# 1. Stock metadata
# ═══════════════════════════════════════════════════════════════

DEMO_STOCKS: List[Dict[str, Any]] = [
    {
        "code": "600519",
        "name": "贵州茅台",
        "market": "SH",
        "price": 1688.50,
        "change": "+0.83%",
        "change_amount": "+13.90",
        "pe": 29.82,
        "market_cap": "2,123亿",
        "volume": "234万手",
        "industry": "白酒",
    },
    {
        "code": "000001",
        "name": "平安银行",
        "market": "SZ",
        "price": 12.34,
        "change": "-0.64%",
        "change_amount": "-0.08",
        "pe": 5.62,
        "market_cap": "2,396亿",
        "volume": "1,256万手",
        "industry": "银行",
    },
    {
        "code": "00700",
        "name": "腾讯控股",
        "market": "HK",
        "price": 382.60,
        "change": "+1.52%",
        "change_amount": "+5.70",
        "pe": 22.18,
        "market_cap": "36,480亿港元",
        "volume": "1,890万股",
        "industry": "互联网",
    },
    {
        "code": "AAPL",
        "name": "Apple Inc.",
        "market": "US",
        "price": 191.85,
        "change": "+0.45%",
        "change_amount": "+0.86",
        "pe": 31.20,
        "market_cap": "$2.98万亿",
        "volume": "4,523万股",
        "industry": "科技",
    },
    {
        "code": "000858",
        "name": "五粮液",
        "market": "SZ",
        "price": 152.30,
        "change": "+0.32%",
        "change_amount": "+0.49",
        "pe": 21.45,
        "market_cap": "5,910亿",
        "volume": "345万手",
        "industry": "白酒",
    },
]


# ═══════════════════════════════════════════════════════════════
# 2. K-line history (60 trading days per stock)
#    Format: [date, open, high, low, close, volume]
#    Prices oscillate around current price with mild trends.
# ═══════════════════════════════════════════════════════════════

def _generate_klines(
    base_price: float,
    volatility: float = 0.02,
    trend: float = 0.0005,
    days: int = 60,
) -> List[List]:
    """Generate realistic K-line data for one stock.

    Args:
        base_price: Current price (last day's close).
        volatility: Daily volatility range (fraction of price).
        trend: Daily bias (positive = uptrend, negative = downtrend).
        days: Number of trading days to generate.

    Returns:
        List of [date_str, open, high, low, close, volume] records.
    """
    records = []
    price = base_price
    for i in range(days):
        date = datetime.now() - timedelta(days=days - 1 - i)
        date_str = date.strftime("%Y-%m-%d")
        open_price = price
        # Add trend bias plus random walk
        daily_move = random.gauss(trend * base_price, volatility * base_price)
        close_price = price + daily_move
        high_price = max(open_price, close_price) + abs(random.gauss(0, volatility * base_price * 0.3))
        low_price = min(open_price, close_price) - abs(random.gauss(0, volatility * base_price * 0.3))
        volume = int(random.gauss(500000, 100000))
        volume = max(volume, 50000)
        records.append([date_str, round(open_price, 2), round(high_price, 2),
                        round(low_price, 2), round(close_price, 2), volume])
        price = close_price
    return records


DEMO_KLINES: Dict[str, List[List]] = {
    "600519": _generate_klines(1688.50, volatility=0.012, trend=0.0003, days=60),
    "000001": _generate_klines(12.34, volatility=0.015, trend=-0.0002, days=60),
    "00700": _generate_klines(382.60, volatility=0.018, trend=0.0005, days=60),
    "AAPL":   _generate_klines(191.85, volatility=0.014, trend=0.0004, days=60),
    "000858": _generate_klines(152.30, volatility=0.013, trend=0.0001, days=60),
}


# ═══════════════════════════════════════════════════════════════
# 3. Pre-computed AI analysis results
# ═══════════════════════════════════════════════════════════════

DEMO_AI_ANALYSES: Dict[str, Dict[str, Any]] = {
    "600519": {
        "code": "600519",
        "name": "贵州茅台",
        "sentiment_score": 85,
        "sentiment_emoji": "🟢",
        "trend_prediction": "短期震荡偏强，MA5上穿MA10，成交量温和放大，技术面看多",
        "operation_advice": "建议持有/逢低加仓",
        "confidence": 82,
        "support_level": "1620",
        "resistance_level": "1750",
        "risk_alert": "关注消费税政策变化及消费复苏节奏",
        "analysis_summary": (
            "贵州茅台作为白酒龙头，品牌壁垒深厚，估值处于历史中位。"
            "近期动销数据回暖，批价企稳，渠道库存处于健康水平。"
            "技术面短期均线多头排列，MACD金叉，建议关注突破前高机会。"
        ),
        "model_used": "(演示数据)",
    },
    "000001": {
        "code": "000001",
        "name": "平安银行",
        "sentiment_score": 62,
        "sentiment_emoji": "🟡",
        "trend_prediction": "横盘整理，成交量萎缩，等待方向选择",
        "operation_advice": "观望，等待放量突破信号",
        "confidence": 70,
        "support_level": "11.80",
        "resistance_level": "12.80",
        "risk_alert": "银行业净息差收窄压力持续，关注不良率变化",
        "analysis_summary": (
            "平安银行零售转型持续推进，但宏观经济承压影响信贷需求。"
            "估值处于历史低位，股息率具备一定吸引力。"
            "技术面弱势整理，需等待量能配合确认方向。"
        ),
        "model_used": "(演示数据)",
    },
    "00700": {
        "code": "00700",
        "name": "腾讯控股",
        "sentiment_score": 78,
        "sentiment_emoji": "🟢",
        "trend_prediction": "中期趋势向好，视频号商业化加速，大模型能力持续提升",
        "operation_advice": "建议持有，可逢回调加仓",
        "confidence": 80,
        "support_level": "355",
        "resistance_level": "400",
        "risk_alert": "关注游戏版号审批节奏及监管政策变化",
        "analysis_summary": (
            "腾讯核心业务稳健，视频号广告收入高速增长，AI大模型赋能各业务线。"
            "回购持续进行，股东回报积极。"
            "估值修复空间仍在，港股通资金持续流入。"
        ),
        "model_used": "(演示数据)",
    },
    "AAPL": {
        "code": "AAPL",
        "name": "Apple Inc.",
        "sentiment_score": 75,
        "sentiment_emoji": "🟢",
        "trend_prediction": "短期受益于AI终端升级周期，服务收入持续增长",
        "operation_advice": "建议持有",
        "confidence": 78,
        "support_level": "180",
        "resistance_level": "200",
        "risk_alert": "关注iPhone出货量及中国市场表现",
        "analysis_summary": (
            "Apple Intelligence推动终端升级需求，服务业务毛利率持续提升。"
            "Vision Pro生态逐步完善，印度市场增长强劲。"
            "但中国市场面临华为等本土品牌竞争压力。"
        ),
        "model_used": "(演示数据)",
    },
    "000858": {
        "code": "000858",
        "name": "五粮液",
        "sentiment_score": 80,
        "sentiment_emoji": "🟢",
        "trend_prediction": "估值修复中，消费旺季预期支撑股价",
        "operation_advice": "建议持有/逢低关注",
        "confidence": 76,
        "support_level": "145",
        "resistance_level": "162",
        "risk_alert": "二线白酒竞争加剧，关注批价走势",
        "analysis_summary": (
            "五粮液品牌力仅次于茅台，普五系列动销稳健。"
            "公司持续推进渠道改革和产品结构升级。"
            "当前估值处于历史低位，性价比凸显。"
        ),
        "model_used": "(演示数据)",
    },
}


# ═══════════════════════════════════════════════════════════════
# 4. Sample portfolio positions
# ═══════════════════════════════════════════════════════════════

DEMO_PORTFOLIO: List[Dict[str, Any]] = [
    {
        "code": "600519",
        "name": "贵州茅台",
        "shares": 100,
        "cost": 1650.00,
        "current_price": 1688.50,
        "market_value": 168850.00,
        "profit": 3850.00,
        "profit_pct": "+2.33%",
        "weight": "45.2%",
    },
    {
        "code": "00700",
        "name": "腾讯控股",
        "shares": 500,
        "cost": 370.00,
        "current_price": 382.60,
        "market_value": 191300.00,
        "profit": 6300.00,
        "profit_pct": "+3.41%",
        "weight": "31.1%",
    },
    {
        "code": "000858",
        "name": "五粮液",
        "shares": 300,
        "cost": 148.00,
        "current_price": 152.30,
        "market_value": 45690.00,
        "profit": 1290.00,
        "profit_pct": "+2.91%",
        "weight": "7.4%",
    },
    {
        "code": "000001",
        "name": "平安银行",
        "shares": 5000,
        "cost": 12.80,
        "current_price": 12.34,
        "market_value": 61700.00,
        "profit": -2300.00,
        "profit_pct": "-3.59%",
        "weight": "10.0%",
    },
    {
        "code": "AAPL",
        "name": "Apple Inc.",
        "shares": 200,
        "cost": 188.00,
        "current_price": 191.85,
        "market_value": 38370.00,
        "profit": 770.00,
        "profit_pct": "+2.05%",
        "weight": "6.3%",
    },
]

# Portfolio summary
DEMO_PORTFOLIO_SUMMARY = {
    "total_market_value": 505910.00,
    "total_cost": 492700.00,
    "total_profit": 13210.00,
    "total_profit_pct": "+2.68%",
    "cash": 94090.00,
    "total_assets": 600000.00,
}


# ═══════════════════════════════════════════════════════════════
# 5. Helper: apply demo data to config
# ═══════════════════════════════════════════════════════════════

def apply_demo_mode(config) -> None:
    """Apply demo mode to a Config instance.

    Sets mode to "demo", populates stock list from demo data,
    and saves the mode to config.json.
    """
    config.mode = "demo"
    config.stock_list = [s["code"] for s in DEMO_STOCKS]
    config.save_json_config({"mode": "demo"})


def exit_demo_mode(config) -> None:
    """Remove demo mode from a Config instance."""
    config.mode = None
    config.save_json_config({"mode": "live"})

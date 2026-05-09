"""Market status detection for A股/港股/美股."""
from datetime import datetime, time
from enum import Enum
from typing import Dict

class MarketStatus(Enum):
    OPEN = "交易中"
    PRE_CLOSE = "盘前/盘后"
    CLOSED = "休市"
    LUNCH = "午休"

def get_china_status(t: time) -> MarketStatus:
    """A股状态（北京时间）"""
    if time(9, 15) <= t < time(9, 30):
        return MarketStatus.PRE_CLOSE
    if time(9, 30) <= t < time(11, 30):
        return MarketStatus.OPEN
    if time(11, 30) <= t < time(13, 0):
        return MarketStatus.LUNCH
    if time(13, 0) <= t < time(15, 5):
        return MarketStatus.OPEN
    if time(15, 5) <= t < time(15, 30):
        return MarketStatus.PRE_CLOSE
    return MarketStatus.CLOSED

def get_hk_status(t: time) -> MarketStatus:
    """港股状态（北京时间）"""
    if time(9, 30) <= t < time(12, 0):
        return MarketStatus.OPEN
    if time(12, 0) <= t < time(13, 0):
        return MarketStatus.LUNCH
    if time(13, 0) <= t < time(16, 0):
        return MarketStatus.OPEN
    return MarketStatus.CLOSED

def get_us_status(now: datetime) -> MarketStatus:
    """美股状态（北京时间）"""
    h, m = now.hour, now.minute
    total_min = h * 60 + m
    # 21:30-04:00 北京时间 = 美股交易时段（夏令时）
    if (total_min >= 21 * 60 + 30) or (total_min < 4 * 60):
        return MarketStatus.OPEN
    # 04:00-09:30 及 16:00-21:30 = 盘前/盘后
    if (total_min >= 4 * 60 and total_min < 9 * 60 + 30) or \
       (total_min >= 16 * 60 and total_min < 21 * 60 + 30):
        return MarketStatus.PRE_CLOSE
    return MarketStatus.CLOSED

def get_market_statuses() -> Dict[str, Dict[str, str]]:
    """返回所有市场当前状态，含颜色信息。"""
    now = datetime.now()
    t = now.time()
    china = get_china_status(t)
    hk = get_hk_status(t)
    us = get_us_status(now)
    status_map = {
        MarketStatus.OPEN: ("🟢", "green"),
        MarketStatus.PRE_CLOSE: ("🟡", "yellow"),
        MarketStatus.LUNCH: ("🟡", "yellow"),
        MarketStatus.CLOSED: ("⚪", "grey"),
    }
    def fmt(status: MarketStatus) -> Dict[str, str]:
        emoji, color = status_map[status]
        return {"emoji": emoji, "text": status.value, "color": color}
    return {"A股": fmt(china), "港股": fmt(hk), "美股": fmt(us)}


def get_all_market_statuses() -> Dict[str, tuple]:
    """Return flat dict of market statuses for legacy compatibility.

    Returns:
        Dict mapping market name to (emoji, text) tuple.
    """
    statuses = get_market_statuses()
    return {market: (info["emoji"], info["text"]) for market, info in statuses.items()}
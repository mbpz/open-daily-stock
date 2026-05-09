"""Shared components for TUI/GUI code reuse."""
from .style import (
    MARKET_UP_COLOR, MARKET_DOWN_COLOR, MARKET_NEUTRAL_COLOR, NEUTRAL_COLOR,
    UP_ARROW, DOWN_ARROW, NEUTRAL_ARROW,
    format_volume, format_market_cap, format_cny, format_pct,
    TUI_COLOR_UP, TUI_COLOR_DOWN, TUI_COLOR_NEUTRAL,
    GUI_COLOR_UP, GUI_COLOR_DOWN, GUI_COLOR_NEUTRAL,
)
from .market_status import get_market_statuses, MarketStatus
from .indicators import (
    calculate_rsi, calculate_macd, calculate_kdj,
    calculate_wr, calculate_obv, calculate_bollinger_bands,
)

__all__ = [
    "MARKET_UP_COLOR", "MARKET_DOWN_COLOR", "MARKET_NEUTRAL_COLOR", "NEUTRAL_COLOR",
    "UP_ARROW", "DOWN_ARROW", "NEUTRAL_ARROW",
    "format_volume", "format_market_cap", "format_cny", "format_pct",
    "TUI_COLOR_UP", "TUI_COLOR_DOWN", "TUI_COLOR_NEUTRAL",
    "GUI_COLOR_UP", "GUI_COLOR_DOWN", "GUI_COLOR_NEUTRAL",
    "get_market_statuses", "MarketStatus",
    "calculate_rsi", "calculate_macd", "calculate_kdj",
    "calculate_wr", "calculate_obv", "calculate_bollinger_bands",
]